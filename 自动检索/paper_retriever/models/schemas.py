from pydantic import BaseModel
from typing import List, Optional


class QueryConcept(BaseModel):
    concept: str
    synonyms: List[str]


class QueryConcepts(BaseModel):
    concepts: List[QueryConcept]


class RawPaper(BaseModel):
    paperId: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    authors: List = []  # 接受字符串列表或字典列表
    year: Optional[int] = None
    citationCount: Optional[int] = 0
    referenceCount: Optional[int] = 0
    url: Optional[str] = None


class PaperConcept(BaseModel):
    concept: str
    relevance: float


class ScoredPaper(BaseModel):
    paper: RawPaper
    semantic_score: float
    citation_score: float
    final_score: float
    matched_concepts: List[str]


class FinalPaperResult(BaseModel):
    paper_id: str
    title: str
    abstract: Optional[str] = None
    url: Optional[str] = None
    year: Optional[int] = None
    citation_count: Optional[int] = 0
    relevance_score: float
    matched_concepts: List[str]