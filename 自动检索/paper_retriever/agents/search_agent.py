import logging
import xml.etree.ElementTree as ET
from typing import List, Optional
from datetime import datetime
import time

import requests

from paper_retriever.config import (
    SEMANTIC_SCHOLAR_API_KEY,
    SEMANTIC_SCHOLAR_BASE_URL,
    CANDIDATE_LIMIT,
    MAX_RETRY_ATTEMPTS
)
from paper_retriever.models.schemas import QueryConcepts, RawPaper
from paper_retriever.utils.retry import retry_with_backoff

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ARXIV_BASE_URL = "http://export.arxiv.org/api/query"


class QueryExpansionAgent:
    def __init__(self, max_results: int = CANDIDATE_LIMIT):
        self.headers = {
            "User-Agent": "PaperRetriever/1.0 (Academic Research Tool)"
        }
        if SEMANTIC_SCHOLAR_API_KEY:
            self.headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
        self.max_results = max_results
    
    def build_query_expression(self, concepts: QueryConcepts) -> str:
        """
        === SemRank Core Logic: Query Expansion ===
        构建检索表达式，充分利用所有核心概念和同义词

        策略：
        1. 优先使用英文概念和同义词
        2. 每个概念的主词 + 同义词用 OR 连接
        3. 不同概念之间用 AND 连接（提高相关性）
        4. 如果概念过多，选择最重要的3个概念
        """
        # 收集所有英文术语，按概念分组
        concept_groups = []

        for concept in concepts.concepts:
            terms_in_concept = set()

            # 检查主概念是否为英文
            if self._is_english(concept.concept):
                terms_in_concept.add(concept.concept.lower())

            # 添加英文同义词
            for synonym in concept.synonyms:
                if self._is_english(synonym):
                    terms_in_concept.add(synonym.lower())

            # 如果这个概念有英文术语，加入分组
            if terms_in_concept:
                concept_groups.append(terms_in_concept)

        # 如果没有英文术语，使用所有术语（包括中文翻译后的英文）
        if not concept_groups:
            for concept in concepts.concepts:
                terms = {concept.concept.lower()}
                for synonym in concept.synonyms:
                    terms.add(synonym.lower())
                concept_groups.append(terms)

        # 限制概念数量（最多3个核心概念，避免查询过长）
        if len(concept_groups) > 3:
            # 选择术语数量最多的3个概念（通常更重要）
            concept_groups.sort(key=len, reverse=True)
            concept_groups = concept_groups[:3]

        # 构建查询表达式
        # 每个概念内部的同义词用 OR 连接
        # 不同概念之间用 AND 连接
        query_parts = []
        for group in concept_groups:
            group_terms = []
            for term in group:
                if len(term.split()) > 1:
                    group_terms.append(f'"{term}"')
                else:
                    group_terms.append(term)

            if group_terms:
                # 每个概念组内部用 OR
                query_parts.append(f"({' OR '.join(group_terms)})")

        # 不同概念组之间用 AND 连接（提高精确度）
        if query_parts:
            return " AND ".join(query_parts)
        else:
            # Fallback: 如果没有任何有效术语，返回空查询
            return ""
    
    def _is_english(self, text: str) -> bool:
        """检查文本是否为英文"""
        return all(ord(c) < 128 or c.isspace() or c in '-_.' for c in text)
    
    @retry_with_backoff(max_retries=MAX_RETRY_ATTEMPTS, initial_delay=1.0, backoff_factor=2.0)
    async def search(self, concepts: QueryConcepts) -> List[RawPaper]:
        logger.info("Starting paper search...")
        
        query_expr = self.build_query_expression(concepts)
        logger.info(f"Search query: {query_expr}")
        
        papers = []
        
        # 优先使用 Semantic Scholar（有 API Key 时）
        if SEMANTIC_SCHOLAR_API_KEY:
            logger.info("Using Semantic Scholar API (priority)...")
            try:
                #添加延迟避免限流
                time.sleep(1.0)
                semantic_papers = await self._search_semantic_scholar(query_expr)
                papers.extend(semantic_papers)
                logger.info(f"Semantic Scholar found {len(semantic_papers)} papers")
                #papers = await self._search_semantic_scholar(query_expr)
            except Exception as e:
                logger.warning(f"Semantic Scholar failed: {e}")

        #如果结果不足，使用 arXiv 补充
        if len(papers) < CANDIDATE_LIMIT:
            logger.info(f"Supplementing with arXiv (current: {len(papers)}, target: {CANDIDATE_LIMIT})...")
            try:
                # 添加延迟避免频繁请求
                time.sleep(0.5)
                arxiv_papers = await self._search_arxiv(query_expr)
                # 去重：基于标题或 URL
                existing_urls = {p.url for p in papers if p.url}
                existing_titles = {p.title.lower() for p in papers if p.title}

                unique_added = 0

                for paper in arxiv_papers:
                    is_duplicate = False
                    if paper.url and paper.url in existing_urls:
                        is_duplicate = True
                    if paper.title and paper.title.lower() in existing_titles:
                        is_duplicate = True

                    # if not is_duplicate:
                    #     papers.append(paper)
                    #     existing_urls.add(paper.url) if paper.url else None
                    #     existing_titles.add(paper.title.lower()) if paper.title else None

                    if not is_duplicate:
                        papers.append(paper)
                        if paper.url:
                            existing_urls.add(paper.url)
                        if paper.title:
                            existing_titles.add(paper.title.lower())
                        unique_added += 1

                # logger.info(
                #     f"arXiv added {len([p for p in arxiv_papers if p.url not in existing_urls or p.title.lower() not in existing_titles])} unique papers")
                logger.info(f"arXiv added {unique_added} unique papers")
            except Exception as e:
                logger.warning(f"arXiv supplement failed: {e}")

        # 限制总数不超过 CANDIDATE_LIMIT
        papers = papers[:CANDIDATE_LIMIT]
        logger.info(f"Found {len(papers)} papers in total")
        return papers
    
    async def _search_semantic_scholar(self, query_expr: str) -> List[RawPaper]:
        url = f"{SEMANTIC_SCHOLAR_BASE_URL}/paper/search"
        params = {
            "query": query_expr,
            "limit": CANDIDATE_LIMIT,
            "fields": "title,abstract,authors.name,year,citationCount,referenceCount,url,paperId"
        }
        
        try:
            # 添加延迟避免触发限流
            time.sleep(3.0)
            response = requests.get(url, headers=self.headers, params=params, timeout=30)

            # 特殊处理 429 错误
            if response.status_code == 429:
                logger.warning("Semantic Scholar API rate limit exceeded (429). Waiting 5 seconds before retry...")
                time.sleep(5)
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            papers = []
            
            for item in data.get('data', []):
                # 处理作者字段
                authors = []
                if 'authors' in item:
                    for author in item['authors']:
                        if isinstance(author, dict) and 'name' in author:
                            authors.append(author['name'])
                        elif isinstance(author, str):
                            authors.append(author)
                
                paper = RawPaper(
                    paperId=item.get('paperId'),
                    title=item.get('title'),
                    abstract=item.get('abstract'),
                    authors=authors,
                    year=item.get('year'),
                    citationCount=item.get('citationCount', 0),
                    referenceCount=item.get('referenceCount', 0),
                    url=item.get('url')
                )
                papers.append(paper)
            
            return papers

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error("Semantic Scholar API rate limit still exceeded after retry. Falling back to arXiv.")
                return []
            else:
                logger.error(f"Semantic Scholar HTTP error: {e}")
                return []
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Semantic Scholar search failed: {e}")
            return []
    
    async def _search_arxiv(self, query_expr: str) -> List[RawPaper]:
        """使用 arXiv API 搜索论文（免费，无地区限制）"""
        # 将 OR 查询转换为 arXiv 格式
        arxiv_query = query_expr.replace(" OR ", " OR ").replace('"', '')
        
        params = {
            "search_query": f"all:{arxiv_query}",
            "start": 0,
            "max_results": CANDIDATE_LIMIT
        }
        
        try:
            response = requests.get(ARXIV_BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            
            # 解析 XML 响应
            root = ET.fromstring(response.content)
            
            # 定义命名空间
            namespaces = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }
            
            papers = []
            for entry in root.findall('atom:entry', namespaces):
                # 提取标题
                title_elem = entry.find('atom:title', namespaces)
                title = title_elem.text.strip() if title_elem is not None else ""
                
                # 提取摘要
                summary_elem = entry.find('atom:summary', namespaces)
                abstract = summary_elem.text.strip() if summary_elem is not None else ""
                
                # 提取作者
                authors = []
                for author in entry.findall('atom:author', namespaces):
                    name_elem = author.find('atom:name', namespaces)
                    if name_elem is not None:
                        authors.append({'name': name_elem.text})
                
                # 提取年份
                published_elem = entry.find('atom:published', namespaces)
                year = None
                if published_elem is not None:
                    try:
                        pub_date = datetime.fromisoformat(published_elem.text.replace('Z', '+00:00'))
                        year = pub_date.year
                    except:
                        pass
                
                # 提取链接
                link_elem = entry.find('atom:id', namespaces)
                url = link_elem.text if link_elem is not None else ""
                
                # 提取 arXiv ID
                paper_id = url.split('/')[-1] if url else ""
                
                paper = RawPaper(
                    paperId=paper_id,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    year=year,
                    citationCount=0,  # arXiv 不提供引用数
                    referenceCount=0,
                    url=url
                )
                papers.append(paper)

            # 按相关性排序
            papers = self._rank_arxiv_papers_by_relevance(papers, arxiv_query)
            
            logger.info(f"arXiv found {len(papers)} papers")
            return papers
        
        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return []

    def _rank_arxiv_papers_by_relevance(self, papers: List[RawPaper], query: str) -> List[RawPaper]:
        """
        对 arXiv 论文按相关性排序

        排序策略：
        1. 标题匹配度（权重 0.6）
        2. 摘要匹配度（权重 0.4）
        3. 年份加分（近 3 年 +0.1）
        """
        if not papers or not query:
            return papers

        # 提取查询关键词（去除引号和布尔运算符）
        query_terms = query.lower().replace('"', '').replace('(', '').replace(')', '').split()
        query_terms = [term for term in query_terms if term not in ['and', 'or', 'not']]

        scored_papers = []

        for paper in papers:
            title = (paper.title or "").lower()
            abstract = (paper.abstract or "").lower()

            # 1. 标题匹配度
            title_score = 0
            for term in query_terms:
                if term in title:
                    title_score += 1
            title_score = title_score / len(query_terms) if query_terms else 0

            # 2. 摘要匹配度
            abstract_score = 0
            for term in query_terms:
                if term in abstract:
                    abstract_score += 1
            abstract_score = abstract_score / len(query_terms) if query_terms else 0

            # 3. 综合得分
            relevance_score = 0.6 * title_score + 0.4 * abstract_score

            # 4. 年份加分（近 3 年）
            from datetime import datetime
            current_year = datetime.now().year
            if paper.year and (current_year - paper.year) <= 3:
                relevance_score += 0.1

            scored_papers.append((relevance_score, paper))

        # 按相关性降序排序
        scored_papers.sort(key=lambda x: x[0], reverse=True)

        return [paper for _, paper in scored_papers]
    
    async def search_with_custom_query(self, query_expr: str) -> List[RawPaper]:
        """
        使用自定义查询表达式进行搜索
        
        Args:
            query_expr: 自定义的查询表达式
            
        Returns:
            论文列表
        """
        logger.info(f"Starting custom search with query: {query_expr}")
        
        papers = []
        
        # 优先使用 Semantic Scholar（有 API Key 时）
        if SEMANTIC_SCHOLAR_API_KEY:
            logger.info("Using Semantic Scholar API for custom query...")
            try:
                time.sleep(1.0)
                semantic_papers = await self._search_semantic_scholar_custom(query_expr)
                papers.extend(semantic_papers)
                logger.info(f"Semantic Scholar found {len(semantic_papers)} papers")
            except Exception as e:
                logger.warning(f"Semantic Scholar custom search failed: {e}")
        
        # 如果结果不足，使用 arXiv 补充
        if len(papers) < self.max_results:
            logger.info(f"Supplementing custom search with arXiv...")
            try:
                time.sleep(0.5)
                arxiv_papers = await self._search_arxiv_custom(query_expr)
                # 去重
                existing_urls = {p.url for p in papers if p.url}
                existing_titles = {p.title.lower() for p in papers if p.title}
                
                for paper in arxiv_papers:
                    is_duplicate = False
                    if paper.url and paper.url in existing_urls:
                        is_duplicate = True
                    if paper.title and paper.title.lower() in existing_titles:
                        is_duplicate = True
                    
                    if not is_duplicate:
                        papers.append(paper)
                        if paper.url:
                            existing_urls.add(paper.url)
                        if paper.title:
                            existing_titles.add(paper.title.lower())
                
                logger.info(f"arXiv added {len(arxiv_papers)} papers")
            except Exception as e:
                logger.warning(f"arXiv custom search failed: {e}")
        
        papers = papers[:self.max_results]
        logger.info(f"Custom search completed, found {len(papers)} papers")
        return papers
    
    async def _search_semantic_scholar_custom(self, query_expr: str) -> List[RawPaper]:
        """使用自定义查询搜索 Semantic Scholar"""
        return await self._search_semantic_scholar(query_expr)
    
    async def _search_arxiv_custom(self, query_expr: str) -> List[RawPaper]:
        """使用自定义查询搜索 arXiv"""
        return await self._search_arxiv(query_expr)