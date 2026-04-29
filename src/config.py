import os
from typing import Optional, Literal
from pydantic import BaseModel, Field


class SearchConfig(BaseModel):
    provider: Literal["tavily", "duckduckgo", "serper"] = "duckduckgo"
    max_results: int = Field(default=5, ge=1, le=20)
    include_raw_content: bool = True
    include_answer: bool = True


class LLMConfig(BaseModel):
    provider: Literal["gemini", "huggingface", "nvidia", "openrouter"] = "nvidia"
    model: str = "mistralai/mistral-nemotron"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, ge=1000, le=32000)
    api_key: Optional[str] = None


class ObservabilityConfig(BaseModel):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_sql: bool = False
    trace_nodes: bool = True
    track_tokens: bool = True
    progress_interval: float = 0.5


class PerformanceConfig(BaseModel):
    max_concurrent_scrape: int = Field(default=5, ge=1, le=15)
    max_concurrent_analyze: int = Field(default=3, ge=1, le=10)
    circuit_breaker_threshold: int = Field(default=5, ge=1, le=20)
    circuit_breaker_timeout: float = Field(default=60.0, ge=5.0, le=300.0)
    cache_ttl_seconds: float = Field(default=3600.0, ge=60.0, le=86400.0)
    adaptive_concurrency: bool = True


class AgentConfig(BaseModel):
    deep_research: bool = True
    max_sources: int = Field(default=5, ge=1, le=20)
    streaming: bool = True
    citation_style: Literal["numbered", "apa", "mla"] = "numbered"
    timeout: int = Field(default=120, ge=30, le=300)


class Config(BaseModel):
    search: SearchConfig = Field(default_factory=SearchConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)

    def __init__(self, **data):
        super().__init__(**data)
        self.llm.model = os.getenv("LLM_MODEL", self.llm.model)
        self.llm.provider = os.getenv("LLM_PROVIDER", self.llm.provider)
        self.search.provider = os.getenv("SEARCH_PROVIDER", self.search.provider)


config = Config()
