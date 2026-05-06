from typing import TypedDict, List, Optional, Any
from datetime import datetime


class SearchResult(TypedDict):
    title: str
    url: str
    content: str
    score: float
    published_date: Optional[str]


class ScrapedContent(TypedDict):
    url: str
    title: str
    content: str
    excerpt: str
    author: Optional[str]
    published_date: Optional[str]
    fetched_at: str
    chunks: Optional[List[str]]


class ExtractedFact(TypedDict):
    source_url: str
    source_title: str
    fact: str
    category: str
    confidence: float
    source_sentence: Optional[str] = ""


class Citation(TypedDict):
    index: int
    url: str
    title: str
    context: str


class AgentState(TypedDict):
    original_query: str
    query_intent: Optional[str]
    refined_query: Optional[str]
    search_results: List[SearchResult]
    scraped_content: List[ScrapedContent]
    extracted_facts: List[ExtractedFact]
    final_answer: str
    citations: List[Citation]
    sub_queries: List[str]
    hyde_document: Optional[str]
    critiques: List[str]
    reflexion_steps: int
    reasoning_trace: List[str]
    error: Optional[str]
    status: str
    metadata: dict
    next_step: Optional[str] = None
    analysis_round: int = 0
    retry_count: int = 0


AGENT_DEFAULTS = {
    "quick": {
        "max_sources": 5,
        "max_search_results": 10,
        "max_sources_to_analyze": 5,
        "max_content_for_analyzer": 3000,
        "max_content_for_synthesizer": 1500,
        "analyzer_concurrency": 5,
        "min_facts_threshold": 5,
        "max_analysis_rounds": 1,
    },
    "deep": {
        "max_sources": 15,
        "max_search_results": 20,
        "max_sources_to_analyze": 10,
        "max_content_for_analyzer": 5000,
        "max_content_for_synthesizer": 2000,
        "analyzer_concurrency": 10,
        "min_facts_threshold": 8,
        "max_analysis_rounds": 3,
    },
}


def get_agent_settings(deep_research: bool = False) -> dict:
    return AGENT_DEFAULTS["deep"] if deep_research else AGENT_DEFAULTS["quick"]