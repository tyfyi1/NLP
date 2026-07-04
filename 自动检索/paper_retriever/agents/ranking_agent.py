import logging
import re
from typing import List, Tuple

from paper_retriever.config import SEMANTIC_WEIGHT, CITATION_WEIGHT, TOP_K_DEFAULT
from paper_retriever.models.schemas import QueryConcepts, RawPaper, ScoredPaper, FinalPaperResult
from paper_retriever.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

PAPER_CONCEPT_EXTRACTION_PROMPT = """
You are a research paper analyzer. Extract 3-5 core scientific concepts from the following paper.

IMPORTANT: 
- Output must be a JSON list of concept strings (e.g., ["reinforcement learning", "multi-agent system"])
- Concepts should be in English, lowercase, and represent the main technical topics
- Focus on the most important technical concepts, not general terms

Title: {title}
Abstract: {abstract}

Output ONLY the JSON list (nothing else):
"""

LLM_RANKING_PROMPT = """
You are a research paper relevance evaluator. Rate the relevance of the following paper to the query concepts on a scale of 1-10.

Query Concepts: {query_concepts}

Paper Title: {title}
Paper Abstract: {abstract}

Consider:
- How well the paper's main topics align with the query concepts
- Whether the paper addresses the core research question
- The depth of relevance (not just keyword overlap)

Output ONLY a single number from 1 to 10 (e.g., 7):
"""


class SemRankRankingAgent:
    def __init__(self, llm_client: LLMClient, top_k: int = TOP_K_DEFAULT):
        self.llm_client = llm_client
        self.top_k = top_k
    
    async def rank(self, query_concepts: QueryConcepts, papers: List[RawPaper], mode: str = "A") -> List[FinalPaperResult]:
        logger.info(f"Starting SemRank ranking with mode {mode}...")
        
        if not papers:
            logger.warning("No papers to rank")
            return []
        
        # === SemRank Core Logic ===
        # Step 1: 为每篇候选论文提取核心概念 (Paper Concepts)
        # Step 2: 计算查询概念与论文概念的语义匹配分数
        # Step 3: 结合引用数计算综合排名分数
        scored_papers = []
        all_citation_counts = [p.citationCount or 0 for p in papers]
        max_citation = max(all_citation_counts) if all_citation_counts else 1
        
        for paper in papers:
            # Step 1: 提取论文概念（通过 LLM）
            paper_concepts = await self._extract_paper_concepts(paper)
            
            # Step 2: 计算语义匹配分数（Jaccard + LLM）
            semantic_score, matched_concepts = await self._calculate_semantic_score(
                query_concepts, paper_concepts, paper, mode
            )
            
            # Step 3: 计算引用分数（对数归一化）
            citation_score = self._normalize_citation(paper.citationCount or 0, max_citation)
            
            # 综合评分：语义分数 + 引用分数
            final_score = SEMANTIC_WEIGHT * semantic_score + CITATION_WEIGHT * citation_score
            
            scored_papers.append(ScoredPaper(
                paper=paper,
                semantic_score=semantic_score,
                citation_score=citation_score,
                final_score=final_score,
                matched_concepts=matched_concepts
            ))
        
        # 按综合分数降序排序
        scored_papers.sort(key=lambda x: x.final_score, reverse=True)
        
        logger.info(f"Ranking completed, top {self.top_k} papers selected")
        
        return self._format_results(scored_papers[:self.top_k])
    
    async def _extract_paper_concepts(self, paper: RawPaper) -> List[str]:
        """
        === SemRank 核心步骤 ===
        使用 LLM 提取论文的核心科学概念 (Paper Concepts)。
        这是 SemRank 算法的关键步骤之一。
        """
        title = paper.title or ""
        abstract = paper.abstract or ""
        
        if not title and not abstract:
            return []
        
        if not self.llm_client.is_available:
            return self._fallback_paper_concepts(paper)
        
        prompt = PAPER_CONCEPT_EXTRACTION_PROMPT.format(title=title, abstract=abstract)
        
        try:
            result = await self.llm_client.async_generate_json(prompt)
            if result and isinstance(result, list):
                concepts = [str(c).lower().strip() for c in result if c]
                if concepts:
                    return concepts[:5]  # 最多取 5 个概念
        except Exception as e:
            logger.debug(f"LLM concept extraction failed: {e}")
        
        return self._fallback_paper_concepts(paper)
    
    def _fallback_paper_concepts(self, paper: RawPaper) -> List[str]:
        """
        LLM 不可用时的降级方案：从标题中提取关键短语
        """
        concepts = []
        title = (paper.title or "").lower()
        
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                      'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
                      'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
                      'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'}
        
        words = re.findall(r'[a-z]+(?:[-\s][a-z]+)*', title)
        filtered = [w for w in words if w not in stop_words and len(w) > 2]
        filtered.sort(key=len, reverse=True)
        
        return filtered[:5]
    
    async def _calculate_semantic_score(self, query_concepts: QueryConcepts, paper_concepts: List[str], 
                                        paper: RawPaper, mode: str) -> Tuple[float, List[str]]:
        """
        === SemRank 核心算法 ===
        计算查询概念与论文概念的语义匹配分数。
        
        SemRank 思想：
        1. 提取查询概念 (Query Concepts) - 已在 query_agent 中完成
        2. 提取论文概念 (Paper Concepts) - 通过 LLM 提取
        3. 语义匹配：计算概念集合的重叠度
        4. 集合重叠度（轻量模式）：Jaccard 相似度
        """
        # 1. 构建查询概念集合（包含同义词）
        query_concept_set = set()
        query_synonym_map = {}
        for concept in query_concepts.concepts:
            concept_lower = concept.concept.lower().strip()
            query_concept_set.add(concept_lower)
            query_synonym_map[concept_lower] = set()
            for synonym in concept.synonyms:
                syn_lower = synonym.lower().strip()
                query_concept_set.add(syn_lower)
                query_synonym_map[concept_lower].add(syn_lower)
        
        # 2. 构建论文概念集合
        paper_concept_set = set()
        for c in paper_concepts:
            if c:
                paper_concept_set.add(c.lower().strip())
        
        # 3. 找出匹配的概念
        matched_concepts = []
        matched_query_concepts = set()
        
        for query_term in query_concept_set:
            if query_term in paper_concept_set:
                matched_concepts.append(query_term)
                for main_concept, synonyms in query_synonym_map.items():
                    if query_term == main_concept or query_term in synonyms:
                        matched_query_concepts.add(main_concept)
                        break
        
        # 4. 如果没有精确匹配，尝试模糊匹配
        if not matched_query_concepts:
            title = (paper.title or "").lower()
            abstract = (paper.abstract or "").lower()
            full_text = f"{title} {abstract}"
            
            for main_concept in query_synonym_map.keys():
                if main_concept in full_text:
                    matched_query_concepts.add(main_concept)
                    continue
                
                for synonym in query_synonym_map[main_concept]:
                    if synonym in full_text:
                        matched_query_concepts.add(main_concept)
                        break
        
        # 5. 计算 Jaccard 相似度
        if not query_concept_set or not paper_concept_set:
            jaccard_score = 0.0
        else:
            intersection = query_concept_set & paper_concept_set
            union = query_concept_set | paper_concept_set
            jaccard_score = len(intersection) / len(union) if union else 0.0
        
        # 6. Mode B: LLM 精排模式
        if mode == "B" and self.llm_client.is_available:
            llm_score, llm_matched = await self._calculate_llm_score_with_concepts(
                query_concepts, paper, matched_query_concepts, ""
            )
            llm_normalized = llm_score
            # 6:4 比例结合 LLM 和 Jaccard
            combined_score = 0.6 * llm_normalized + 0.4 * jaccard_score
            all_matched_lower = [c.lower().strip() for c in matched_query_concepts]
            llm_matched_lower = [c.lower().strip() for c in llm_matched]
            all_matched = list(dict.fromkeys(all_matched_lower + llm_matched_lower))
            return combined_score, all_matched
        else:
            matched_lower = [c.lower().strip() for c in matched_query_concepts]
            return jaccard_score, list(dict.fromkeys(matched_lower))
    
    async def _calculate_llm_score_with_concepts(self, query_concepts: QueryConcepts, paper: RawPaper,
                                                  existing_matched: set, full_text: str = "") -> Tuple[float, List[str]]:
        """
        LLM 精排评分（1-10）
        """
        query_concept_list = [c.concept for c in query_concepts.concepts]
        prompt = LLM_RANKING_PROMPT.format(
            query_concepts=", ".join(query_concept_list),
            title=paper.title or "",
            abstract=paper.abstract or ""
        )
        
        try:
            result = await self.llm_client.async_generate(prompt)
            if result:
                result = result.strip().lstrip('\ufeff')
                numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', result)
                if numbers:
                    score = float(numbers[0])
                    score = max(1.0, min(10.0, score))
                    
                    text_matched = self._extract_matched_concepts_from_text(query_concepts, full_text)
                    existing_lower = [c.lower().strip() for c in existing_matched]
                    text_matched_lower = [c.lower().strip() for c in text_matched]
                    all_matched = list(dict.fromkeys(existing_lower + text_matched_lower))
                    
                    return score / 10.0, all_matched
                else:
                    logger.warning(f"LLM returned no valid number: {result[:100]}")
        except Exception as e:
            logger.debug(f"LLM scoring failed: {e}")
        
        score, matched = self._improved_fallback_with_concepts(query_concepts, paper)
        return score, matched
    
    def _extract_matched_concepts_from_text(self, query_concepts: QueryConcepts, full_text: str) -> List[str]:
        """从论文文本中提取匹配的查询概念"""
        if not full_text:
            return []
        
        matched = []
        seen_concepts = set()
        full_text_lower = full_text.lower()
        
        for concept in query_concepts.concepts:
            main_concept = concept.concept.strip().lower()
            if main_concept in seen_concepts:
                continue
            
            if main_concept in full_text_lower:
                matched.append(main_concept)
                seen_concepts.add(main_concept)
                continue
            
            for synonym in concept.synonyms:
                synonym_lower = synonym.strip().lower()
                if synonym_lower in full_text_lower:
                    matched.append(main_concept)
                    seen_concepts.add(main_concept)
                    break
        
        return matched
    
    def _improved_fallback_with_concepts(self, query_concepts: QueryConcepts, paper: RawPaper) -> Tuple[float, List[str]]:
        """改进的 fallback 相似度计算"""
        query_terms = set()
        query_synonym_map = {}
        for concept in query_concepts.concepts:
            concept_lower = concept.concept.lower().strip()
            query_terms.add(concept_lower)
            query_synonym_map[concept_lower] = set()
            for synonym in concept.synonyms:
                syn_lower = synonym.lower().strip()
                query_terms.add(syn_lower)
                query_synonym_map[concept_lower].add(syn_lower)
        
        title = (paper.title or "").lower()
        abstract = (paper.abstract or "").lower()
        full_text = f"{title} {abstract}"
        
        if not query_terms or not title.strip():
            return 0.0, []
        
        matched_count = 0
        matched_concepts = []
        seen_concepts = set()
        
        for main_concept in query_synonym_map.keys():
            if main_concept in seen_concepts:
                continue
            
            is_matched = False
            match_in_title = False
            
            if main_concept in title:
                is_matched = True
                match_in_title = True
            elif main_concept in abstract:
                is_matched = True
            
            if not is_matched:
                for synonym in query_synonym_map[main_concept]:
                    if synonym in title:
                        is_matched = True
                        match_in_title = True
                        break
                    elif synonym in abstract:
                        is_matched = True
                        break
            
            if is_matched:
                matched_concepts.append(main_concept)
                seen_concepts.add(main_concept)
                matched_count += 1.5 if match_in_title else 1.0
        
        match_ratio = matched_count / len(query_synonym_map) if query_synonym_map else 0.0
        title_bonus = 0.0
        title_matched_count = sum(1 for c in matched_concepts if c.lower() in title)
        if title_matched_count >= 2:
            title_bonus = 0.1
        
        final_score = min(1.0, match_ratio + title_bonus)
        return final_score, matched_concepts
    
    async def _calculate_llm_score(self, query_concepts: QueryConcepts, paper: RawPaper) -> float:
        """LLM 精排评分（1-10）- 保留旧接口兼容性"""
        score, _ = await self._calculate_llm_score_with_concepts(query_concepts, paper, set())
        return score
    
    def _normalize_citation(self, citation_count: int, max_citation: int) -> float:
        """引用数归一化（对数缩放）"""
        if max_citation == 0:
            return 0.5
        if citation_count == 0:
            return 0.2
        import math
        return min(1.0, max(0.2, math.log(1 + citation_count) / math.log(1 + max_citation)))
    
    def _format_results(self, scored_papers: List[ScoredPaper]) -> List[FinalPaperResult]:
        results = []
        for scored in scored_papers:
            paper = scored.paper
            results.append(FinalPaperResult(
                paper_id=paper.paperId or "",
                title=paper.title or "",
                abstract=paper.abstract,
                url=paper.url,
                year=paper.year,
                citation_count=paper.citationCount,
                relevance_score=round(scored.final_score, 4),
                matched_concepts=scored.matched_concepts
            ))
        return results
