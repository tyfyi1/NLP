import logging
from typing import List, Optional

from paper_retriever.models.schemas import QueryConcept, QueryConcepts
from paper_retriever.utils.llm_client import LLMClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QUERY_ANALYZER_PROMPT = """
You are a research query analyzer. Extract 3-5 core scientific concepts from the user's question.

IMPORTANT: 
1. All concepts and synonyms must be in ENGLISH (for academic paper search)
2. Output a JSON list of objects with fields: 'concept' and 'synonyms'
3. Each concept should have 2-3 English synonyms

User question: {query}

JSON output:
"""


class QueryUnderstandingAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
    
    async def analyze(self, query: str) -> QueryConcepts:
        logger.info("Starting query analysis...")
        
        if not self.llm_client.is_available:
            logger.warning("LLM not available, using fallback keyword extraction")
            return self._fallback_analysis(query)
        
        prompt = QUERY_ANALYZER_PROMPT.format(query=query)
        
        try:
            result = await self.llm_client.async_generate_json(prompt)
            if result:
                concepts = []
                for item in result:
                    if isinstance(item, dict) and 'concept' in item:
                        concept = QueryConcept(
                            concept=item['concept'],
                            synonyms=item.get('synonyms', [])
                        )
                        concepts.append(concept)
                logger.info(f"Extracted {len(concepts)} core concepts")
                return QueryConcepts(concepts=concepts)
            else:
                logger.warning("LLM returned empty result, using fallback")
                return self._fallback_analysis(query)
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return self._fallback_analysis(query)
    
    def _fallback_analysis(self, query: str) -> QueryConcepts:
        keywords = self._extract_keywords(query)
        concepts = []
        for keyword in keywords[:5]:
            concepts.append(QueryConcept(
                concept=keyword,
                synonyms=self._get_synonyms(keyword)
            ))
        return QueryConcepts(concepts=concepts)
    
    def _extract_keywords(self, query: str) -> List[str]:
        import re
        words = re.findall(r'[\w]+', query)
        stop_words = {'的', '是', '在', '有', '和', '了', '我', '你', '他', '她', '它', '这', '那', '什么', '怎么', '为什么', '如何'}
        keywords = [w for w in words if w not in stop_words and len(w) > 1]
        return list(set(keywords))
    
    def _get_synonyms(self, word: str) -> List[str]:
        synonym_map = {
            '大模型': ['large language model', 'LLM', 'foundation model'],
            '微调': ['fine-tuning', 'fine tuning', 'parameter-efficient tuning'],
            '灾难性遗忘': ['catastrophic forgetting', 'catastrophic interference'],
            '持续学习': ['continual learning', 'lifelong learning', 'incremental learning'],
            '注意力机制': ['attention mechanism', 'self-attention'],
            'Transformer': ['transformer architecture', 'transformer model'],
            '深度学习': ['deep learning', 'neural network'],
            '机器学习': ['machine learning', 'ML'],
            '自然语言处理': ['natural language processing', 'NLP'],
            '计算机视觉': ['computer vision', 'CV'],
            '幻觉': ['hallucination', 'hallucinate', 'factuality error', 'factual inconsistency'],
            '智能体': ['agent', 'intelligent agent', 'autonomous agent'],
            '强化学习': ['reinforcement learning', 'RL', 'deep reinforcement learning'],
            '多智能体': ['multi-agent', 'multi-agent system', 'distributed agent'],
        }
        return synonym_map.get(word, [word.lower(), word.upper()])