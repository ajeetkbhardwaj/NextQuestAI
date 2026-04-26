import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import (
    AgentState,
    SearchResult,
    ScrapedContent,
    ExtractedFact,
    Citation,
    get_agent_settings,
    AGENT_DEFAULTS,
)
from src.agents import (
    extract_refined_query,
    get_deep_research_flag,
    get_llm_config_from_state,
)
from src.workflow import (
    should_skip_to_synthesize,
    should_skip_to_synthesize_after_scrape,
    should_retry_or_synthesize,
    create_research_graph,
)


class TestModels:
    def test_get_agent_settings_quick(self):
        settings = get_agent_settings(deep_research=False)
        assert settings["max_sources"] == 5
        assert settings["max_search_results"] == 10
        assert settings["max_analysis_rounds"] == 1

    def test_get_agent_settings_deep(self):
        settings = get_agent_settings(deep_research=True)
        assert settings["max_sources"] == 15
        assert settings["max_search_results"] == 20
        assert settings["max_analysis_rounds"] == 3

    def test_agent_defaults_structure(self):
        assert "quick" in AGENT_DEFAULTS
        assert "deep" in AGENT_DEFAULTS
        for mode, settings in AGENT_DEFAULTS.items():
            assert "max_sources" in settings
            assert "max_search_results" in settings
            assert "analyzer_concurrency" in settings


class TestAgentHelpers:
    def test_extract_refined_query_with_quotes(self):
        response = 'The refined query is "latest AI breakthroughs 2026" for the user.'
        result = extract_refined_query(response, "fallback")
        assert result == "latest AI breakthroughs 2026"

    def test_extract_refined_query_with_markdown(self):
        response = """**Refined Search Query:**
        quantum computing advances"""
        result = extract_refined_query(response, "fallback")
        assert "quantum computing" in result.lower()

    def test_extract_refined_query_fallback(self):
        response = "Just some random text without any query pattern."
        result = extract_refined_query(response, "default_query")
        assert result == "Just some random text without any query pattern."

    def test_get_deep_research_flag_true(self):
        state = {"metadata": {"deep_research": True}}
        assert get_deep_research_flag(state) is True

    def test_get_deep_research_flag_false(self):
        state = {"metadata": {"deep_research": False}}
        assert get_deep_research_flag(state) is False

    def test_get_deep_research_flag_missing(self):
        state = {"metadata": {}}
        assert get_deep_research_flag(state) is False

    def test_get_llm_config_from_state(self):
        state = {
            "metadata": {
                "llm_config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key": "sk-test",
                    "base_url": None,
                }
            }
        }
        config = get_llm_config_from_state(state)
        assert config["provider"] == "openai"
        assert config["model"] == "gpt-4o"


class TestWorkflowConditionals:
    def test_should_skip_to_synthesize_on_error(self):
        state = {"error": "Something went wrong", "search_results": [{"title": "a", "url": "b"}]}
        result = should_skip_to_synthesize(state)
        assert result == "synthesize"

    def test_should_skip_to_synthesize_no_results(self):
        state = {"error": None, "search_results": []}
        result = should_skip_to_synthesize(state)
        assert result == "synthesize"

    def test_should_skip_to_synthesize_continue(self):
        state = {"error": None, "search_results": [{"title": "a", "url": "b"}]}
        result = should_skip_to_synthesize(state)
        assert result == "scrape"

    def test_should_skip_to_synthesize_after_scrape_on_error(self):
        state = {"error": "Scrape failed", "scraped_content": [{"url": "a"}]}
        result = should_skip_to_synthesize_after_scrape(state)
        assert result == "synthesize"

    def test_should_skip_to_synthesize_after_scrape_no_content(self):
        state = {"error": None, "scraped_content": []}
        result = should_skip_to_synthesize_after_scrape(state)
        assert result == "synthesize"

    def test_should_skip_to_synthesize_after_scrape_continue(self):
        state = {"error": None, "scraped_content": [{"url": "a", "content": "text"}]}
        result = should_skip_to_synthesize_after_scrape(state)
        assert result == "analyzer"

    def test_should_retry_or_synthesize_retry(self):
        state = {"retry_count": 2}
        result = should_retry_or_synthesize(state)
        assert result == "search"
        assert state["retry_count"] == 1

    def test_should_retry_or_synthesize_synthesize(self):
        state = {"retry_count": 0}
        result = should_retry_or_synthesize(state)
        assert result == "synthesize"


class TestWorkflowGraph:
    def test_create_research_graph(self):
        graph = create_research_graph()
        assert graph is not None
        assert hasattr(graph, "astream")


class TestAgentState:
    def test_agent_state_structure(self):
        state: AgentState = {
            "original_query": "What is AI?",
            "refined_query": None,
            "search_results": [],
            "scraped_content": [],
            "extracted_facts": [],
            "final_answer": "",
            "citations": [],
            "reasoning_trace": [],
            "error": None,
            "status": "pending",
            "metadata": {"deep_research": True},
        }
        assert state["original_query"] == "What is AI?"
        assert state["metadata"]["deep_research"] is True

    def test_extracted_fact_structure(self):
        fact: ExtractedFact = {
            "source_url": "https://example.com",
            "source_title": "Example",
            "fact": "AI is transformative",
            "category": "technology",
            "confidence": 0.9,
            "source_sentence": "AI is changing the world",
        }
        assert fact["confidence"] == 0.9

    def test_citation_structure(self):
        citation: Citation = {
            "index": 1,
            "url": "https://example.com",
            "title": "Example Article",
            "context": "Relevant context",
        }
        assert citation["index"] == 1
