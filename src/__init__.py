"""NexusAI - Multi-Agent Research Assistant

A Perplexity-like AI system with:
- LangGraph-based multi-agent orchestration
- Web search (Tavily, DuckDuckGo, Serper)
- LLM reasoning (OpenAI, Anthropic)
- Gradio UI for HuggingFace Spaces
"""

__version__ = "1.0.0"
__author__ = "NexusAI Team"

from .config import config, Config
from .models import AgentState, SearchResult, ScrapedContent
from .workflow import research_graph

__all__ = [
    "config",
    "Config",
    "AgentState",
    "SearchResult",
    "ScrapedContent",
    "research_graph",
]
