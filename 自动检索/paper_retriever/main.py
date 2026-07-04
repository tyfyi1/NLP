import asyncio
import logging
import re
from collections import Counter
from typing import List

from paper_retriever.agents.query_agent import QueryUnderstandingAgent
from paper_retriever.agents.search_agent import QueryExpansionAgent
from paper_retriever.agents.ranking_agent import SemRankRankingAgent
from paper_retriever.models.schemas import FinalPaperResult, QueryConcepts, RawPaper
from paper_retriever.utils.llm_client import LLMClient

logging.basicConfig(level=logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
#logging.getLogger('paper_retriever').setLevel(logging.INFO)
logging.getLogger('paper_retriever').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# === SemRank Core Logic: Term Extraction Prompt ===
# 术语提取 Prompt 模板
TERM_EXTRACTION_PROMPT = """
You are a scientific terminology extractor. Your task is to extract REAL academic terms from the candidate papers that are relevant to the user's query.

IMPORTANT GUIDELINES:
1. Extract terms that ACTUALLY APPEAR in the candidate papers (titles and abstracts)
2. Focus on technical terms, methods, models, datasets, and evaluation metrics
3. All terms must be in ENGLISH and lowercase
4. Avoid generic terms like "method", "approach", "model" - be specific
5. Output a JSON list of strings (e.g., ["transformer architecture", "bleu score", "zero-shot learning"])

User's Initial Query Concepts: {initial_concepts}

Candidate Papers:
{papers_text}

Based on the above candidate papers, extract 10-15 specific technical terms that are:
- Relevant to the user's query concepts
- Actually present in the candidate papers
- Specific enough to improve retrieval precision

Output ONLY the JSON list (nothing else):
"""



class PaperRetriever:
    def __init__(self, llm_client: LLMClient, top_k: int = 10):
        self.llm_client = llm_client
        self.query_agent = QueryUnderstandingAgent(llm_client)
        self.search_agent = QueryExpansionAgent()
        self.ranking_agent = SemRankRankingAgent(llm_client, top_k=top_k)
    
    async def retrieve(self, query: str, ranking_mode: str = "A") -> List[FinalPaperResult]:
        """
        单阶段检索（原有方法，保持不变）
        
        Args:
            query: 中文关键词或研究问题
            ranking_mode: 排序模式（A=快速模式，B=LLM精排）
        
        Returns:
            List[FinalPaperResult]: 排序后的论文列表
        """
        logger.info(f"Starting single-stage paper retrieval for query: {query}")
        
        query_concepts = await self.query_agent.analyze(query)
        logger.info(f"Concept extraction completed: {[c.concept for c in query_concepts.concepts]}")
        
        papers = await self.search_agent.search(query_concepts)
        logger.info(f"Search completed, found {len(papers)} papers")
        
        results = await self.ranking_agent.rank(query_concepts, papers, mode=ranking_mode)
        logger.info(f"Ranking completed, returning {len(results)} results")
        
        return results
    
    async def retrieve_two_stage(
        self, 
        query: str, 
        ranking_mode: str = "A",
        first_stage_limit: int = 40,
        final_top_k: int = 10
    ) -> List[FinalPaperResult]:
        """
        === SemRank Core Logic: Two-Stage Retrieval with Candidate Term Constraint ===
        
        两阶段检索流程（借鉴 SemRank 的 Candidate Topic 思想）
        
        Stage 1: 初步概念提取 → 第一次检索（获取候选论文）
        Stage 2: 从候选论文提取真实术语 → 构造增强查询 → 第二次检索
        Stage 3: 最终排序 → 返回 Top-K
        
        Args:
            query: 中文关键词或研究问题
            ranking_mode: 排序模式（A=快速模式，B=LLM精排）
            first_stage_limit: 第一阶段检索的论文数量
            final_top_k: 最终返回的论文数量
        
        Returns:
            List[FinalPaperResult]: 排序后的论文列表
        """
        logger.info(f"=== Starting Two-Stage Retrieval for: {query} ===")
        
        # Stage 1: 初步概念提取
        logger.info("Stage 1: Initial Concept Extraction")
        query_concepts = await self.query_agent.analyze(query)
        logger.info(f"Extracted concepts: {[c.concept for c in query_concepts.concepts]}")
        
        # Stage 2: 第一次检索（获取候选论文）
        logger.info(f"Stage 2: First Retrieval (limit={first_stage_limit})")
        first_stage_search_agent = QueryExpansionAgent(max_results=first_stage_limit)
        candidate_papers = await first_stage_search_agent.search(query_concepts)
        
        if not candidate_papers:
            logger.warning("No candidate papers found in first stage, falling back to single-stage")
            return await self.retrieve(query, ranking_mode)

        # === 新增：验证候选论文的相关性 ===
        if not self._validate_candidate_relevance(candidate_papers, query_concepts):
            logger.warning("Candidate papers are not relevant, falling back to single-stage")
            return await self.retrieve(query, ranking_mode)
        
        logger.info(f"Found {len(candidate_papers)} candidate papers")
        
        # Stage 3: 从候选论文提取真实术语
        logger.info("Stage 3: Real Term Extraction from Candidates")
        real_terms = await self._extract_real_terms_from_candidates(candidate_papers, query_concepts)
        logger.info(f"Extracted {len(real_terms)} real terms: {real_terms}")
        
        # Stage 4: 构造增强查询
        logger.info("Stage 4: Enhanced Query Construction")
        enhanced_query = self._build_enhanced_query(real_terms, query_concepts)
        logger.info(f"Enhanced query: {enhanced_query}")
        
        # Stage 5: 第二次检索（使用增强查询）
        logger.info("Stage 5: Second Retrieval with Enhanced Query")
        second_stage_search_agent = QueryExpansionAgent(max_results=40)
        try:
            final_papers = await second_stage_search_agent.search_with_custom_query(enhanced_query)
        except Exception as e:
            logger.warning(f"Second stage retrieval failed: {e}, using first stage results")
            final_papers = candidate_papers
        
        if not final_papers:
            logger.warning("Second stage returned no results, using first stage results")
            final_papers = candidate_papers
        
        # Stage 6: 最终排序
        logger.info("Stage 6: Final Ranking")
        results = await self.ranking_agent.rank(query_concepts, final_papers, mode=ranking_mode)
        
        logger.info(f"=== Two-Stage Retrieval completed, returning {len(results)} results ===")
        return results[:final_top_k]
    
    async def _extract_real_terms_from_candidates(
        self,
        candidate_papers: List[RawPaper],
        initial_concepts: QueryConcepts
    ) -> List[str]:
        """
        === SemRank Core Logic: Candidate Term Extraction ===
        
        从候选论文中提取真实术语（类似 SemRank 的 Candidate Topics）
        
        Args:
            candidate_papers: 候选论文列表
            initial_concepts: 初始查询概念
        
        Returns:
            List[str]: 提取的真实术语列表
        """
        if not self.llm_client.is_available:
            logger.info("LLM not available, using fallback term extraction")
            return self._fallback_term_extraction(candidate_papers, initial_concepts)
        
        # 构建术语提取 Prompt
        prompt = self._build_term_extraction_prompt(candidate_papers, initial_concepts)
        
        try:
            result = await self.llm_client.async_generate_json(prompt)
            if result and isinstance(result, list):
                # 解析 JSON list
                terms = [str(t).lower().strip() for t in result if t and len(str(t).strip()) > 2]
                # 去重并限制数量
                unique_terms = list(dict.fromkeys(terms))[:25]
                logger.info(f"Extracted {len(unique_terms)} real terms")
                return unique_terms
        except Exception as e:
            logger.warning(f"LLM term extraction failed: {e}, using fallback")
        
        # 降级到词频统计
        return self._fallback_term_extraction(candidate_papers, initial_concepts)
    
    def _build_term_extraction_prompt(
        self,
        candidate_papers: List[RawPaper],
        initial_concepts: QueryConcepts
    ) -> str:
        """构建术语提取 Prompt"""
        # 准备初始概念字符串
        concept_str = ", ".join([c.concept for c in initial_concepts.concepts])
        
        # 准备候选论文文本（最多取15篇，每篇限制长度）
        papers_text = ""
        for i, paper in enumerate(candidate_papers[:15]):
            title = (paper.title or "")[:100]
            abstract = (paper.abstract or "")[:200]
            papers_text += f"Paper {i+1}:\nTitle: {title}\nAbstract: {abstract}\n\n"
        
        return TERM_EXTRACTION_PROMPT.format(
            initial_concepts=concept_str,
            papers_text=papers_text
        )
    
    def _fallback_term_extraction(
        self,
        candidate_papers: List[RawPaper],
        initial_concepts: QueryConcepts
    ) -> List[str]:
        """
        LLM 不可用时的降级方案：词频统计
        
        Args:
            candidate_papers: 候选论文列表
            initial_concepts: 初始查询概念
        
        Returns:
            List[str]: 提取的高频术语列表
        """
        # 收集所有文本
        all_text = ""
        for paper in candidate_papers[:15]:
            all_text += (paper.title or "") + " " + (paper.abstract or "")
        
        # 提取双词和三词短语
        words = re.findall(r'[a-z]+(?:[-\s][a-z]+)*', all_text.lower())
        
        # 过滤停用词和通用词
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                      'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
                      'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
                      'that', 'these', 'those', 'method', 'approach', 'model', 'algorithm',
                      'system', 'framework', 'technique', 'based', 'using', 'via', 'through',
                      'study', 'research', 'paper', 'work', 'results', 'show', 'demonstrate',
                      'propose', 'introduce', 'present', 'develop', 'evaluate', 'compare'}
        
        # 统计词频（双词和三词短语）
        phrase_counts = Counter()
        for i in range(len(words) - 1):
            # 双词短语
            bigram = f"{words[i]} {words[i+1]}"
            if len(bigram) > 5 and not any(w in stop_words for w in bigram.split()):
                phrase_counts[bigram] += 1
            
            # 三词短语
            if i < len(words) - 2:
                trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
                if len(trigram) > 8 and not any(w in stop_words for w in trigram.split()):
                    phrase_counts[trigram] += 1
        
        # 获取前25个高频短语
        top_phrases = [phrase for phrase, count in phrase_counts.most_common(25)]
        
        # 添加初始概念中的术语
        for concept in initial_concepts.concepts:
            term = concept.concept.lower()
            if term not in top_phrases and len(term) > 3:
                top_phrases.append(term)
        
        # 取前20个术语
        return list(dict.fromkeys(top_phrases))[:25]
    
    def _build_enhanced_query(
        self,
        real_terms: List[str],
        initial_concepts: QueryConcepts
    ) -> str:
        """
        === SemRank Core Logic: Enhanced Query Construction ===
        
        结合初始概念和真实术语构造增强查询
        
        Args:
            real_terms: 从候选论文中提取的真实术语
            initial_concepts: 初始查询概念
        
        Returns:
            str: 增强后的查询表达式
        """
        # 收集所有术语
        all_terms = set()
        
        # 添加初始概念的术语
        for concept in initial_concepts.concepts:
            all_terms.add(concept.concept.lower())
            for synonym in concept.synonyms:
                all_terms.add(synonym.lower())
        
        # 添加真实术语
        for term in real_terms:
            all_terms.add(term.lower())
        
        # 限制最多30个术语
        all_terms = list(all_terms)[:30]
        
        # 构建查询表达式（用 OR 连接）
        query_parts = []
        for term in all_terms:
            if len(term.split()) > 1:
                query_parts.append(f'"{term}"')
            else:
                query_parts.append(term)
        
        return " OR ".join(query_parts)

    def _validate_candidate_relevance(self, candidate_papers: List[RawPaper],
                                      query_concepts: QueryConcepts) -> bool:
        """
        验证候选论文是否与查询相关
        至少 30% 的论文应该包含至少一个查询概念
        """
        if not candidate_papers:
            return False

        # 获取所有查询术语
        query_terms = set()
        for concept in query_concepts.concepts:
            query_terms.add(concept.concept.lower())
            for synonym in concept.synonyms:
                query_terms.add(synonym.lower())

        # 检查有多少论文包含至少一个查询术语
        relevant_count = 0
        for paper in candidate_papers:
            title = (paper.title or "").lower()
            abstract = (paper.abstract or "").lower()
            full_text = f"{title} {abstract}"

            # 检查是否包含任何查询术语
            if any(term in full_text for term in query_terms):
                relevant_count += 1

        # 至少 30% 的论文应该相关
        relevance_ratio = relevant_count / len(candidate_papers)
        logger.info(f"Candidate relevance ratio: {relevance_ratio:.2%} ({relevant_count}/{len(candidate_papers)})")

        return relevance_ratio >= 0.5


async def interactive_mode():
    """交互式查询模式（支持单阶段/两阶段检索切换）"""
    llm_client = LLMClient()
    retriever = PaperRetriever(llm_client, top_k=10)
    
    # 默认使用两阶段检索
    use_two_stage = True
    
    print("=" * 70)
    print("          AI 学术论文检索系统（基于 SemRank）")
    print("=" * 70)
    print("欢迎使用学术论文检索系统！")
    print("输入研究问题或关键词，我将为您检索相关论文。")
    print("输入 'quit' 或 'exit' 退出程序")
    print("输入 'help' 查看帮助")
    print("输入 'mode' 切换检索模式（单阶段/两阶段）")
    print("=" * 70)
    
    while True:
        try:
            # 获取用户输入
            query = input("\n请输入查询内容: ").strip()
            
            # 退出命令
            if query.lower() in ['quit', 'exit', 'q']:
                print("\n感谢使用！再见！")
                break
            
            # 帮助命令
            if query.lower() == 'help':
                print("\n帮助信息:")
                print("  - 输入中文关键词或研究问题进行检索")
                print("  - 例如: 大模型微调中的灾难性遗忘")
                print("  - 输入 'quit' 或 'exit' 退出")
                print("  - 输入 'help' 显示此帮助")
                print("  - 输入 'mode' 切换检索模式")
                print("  - 当前模式: " + ("两阶段检索（推荐）" if use_two_stage else "单阶段检索"))
                continue
            
            # 模式切换命令
            if query.lower() == 'mode':
                use_two_stage = not use_two_stage
                print(f"\n检索模式已切换为: {'两阶段检索（推荐）' if use_two_stage else '单阶段检索'}")
                continue
            
            # 空输入
            if not query:
                print("请输入有效的查询内容")
                continue
            
            # 默认使用 LLM 精排模式，失败时自动降级
            ranking_mode = "B"
            actual_mode = "LLM精排"
            retrieval_mode = "两阶段" if use_two_stage else "单阶段"
            
            print(f"\n正在检索: {query}")
            print(f"   检索模式: {retrieval_mode}")
            print("   排序模式: LLM精排（自动降级到快速模式）")
            print("   请稍候...\n")
            
            # 执行检索
            try:
                if use_two_stage:
                    results = await retriever.retrieve_two_stage(query, ranking_mode=ranking_mode)
                else:
                    results = await retriever.retrieve(query, ranking_mode=ranking_mode)
            except Exception as e:
                print(f"   LLM精排模式失败: {str(e)[:50]}")
                print("   正在切换到快速模式...")
                ranking_mode = "A"
                actual_mode = "快速模式"
                if use_two_stage:
                    results = await retriever.retrieve_two_stage(query, ranking_mode=ranking_mode)
                else:
                    results = await retriever.retrieve(query, ranking_mode=ranking_mode)
            
            # 显示结果
            if not results:
                print("未找到相关论文，请尝试其他关键词")
                continue
            
            print("=" * 70)
            print(f"检索完成！共找到 {len(results)} 篇相关论文")
            print(f"   检索模式: {retrieval_mode}")
            print(f"   排序模式: {actual_mode}")
            print("=" * 70)
            
            for i, result in enumerate(results, 1):
                print(f"\n[{i}] {result.title}")
                print(f"   年份: {result.year or '未知'}")
                print(f"   相关性: {result.relevance_score:.4f}")
                print(f"   匹配概念: {', '.join(result.matched_concepts[:3]) if result.matched_concepts else 'N/A'}")
                print(f"   URL: {result.url}")
            
            print("\n" + "=" * 70)
        
        except KeyboardInterrupt:
            print("\n\n用户中断，程序退出")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")
            print("请检查网络连接或稍后重试")


async def batch_mode(queries):
    """批量查询模式"""
    llm_client = LLMClient()
    retriever = PaperRetriever(llm_client, top_k=5)
    
    for query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        
        try:
            # 使用模式 B（LLM 精排）
            results = await retriever.retrieve(query, ranking_mode="B")
            
            for i, result in enumerate(results, 1):
                print(f"\n[{i}] {result.title}")
                print(f"   Year: {result.year}")
                print(f"   Relevance: {result.relevance_score:.4f}")
                print(f"   Matched: {', '.join(result.matched_concepts[:3]) if result.matched_concepts else 'N/A'}")
                print(f"   URL: {result.url}")
        except Exception as e:
            print(f"Error: {e}")
            print("Falling back to mode A...")
            results = await retriever.retrieve(query, ranking_mode="A")
            for i, result in enumerate(results, 1):
                print(f"\n[{i}] {result.title}")
                print(f"   Year: {result.year}")
                print(f"   Relevance: {result.relevance_score:.4f}")
                print(f"   Matched: {', '.join(result.matched_concepts[:3]) if result.matched_concepts else 'N/A'}")
                print(f"   URL: {result.url}")


if __name__ == "__main__":
    asyncio.run(interactive_mode())