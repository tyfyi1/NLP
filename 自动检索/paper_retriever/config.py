import os
from dotenv import load_dotenv

load_dotenv()

SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))

SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"

TOP_K_DEFAULT = 5
CANDIDATE_LIMIT = 40
MAX_RETRY_ATTEMPTS = 3

# 语义分数和引用分数的权重配置
SEMANTIC_WEIGHT = 0.85
CITATION_WEIGHT = 0.15