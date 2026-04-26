import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_agent_state():
    return {
        "original_query": "What is LangGraph?",
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


@pytest.fixture
def sample_search_result():
    return {
        "title": "Test Article",
        "url": "https://example.com/article",
        "content": "This is the content of the test article about LangGraph.",
        "score": 0.95,
        "published_date": "2024-01-15",
    }


@pytest.fixture
def sample_search_results(sample_search_result):
    return [
        sample_search_result,
        {
            "title": "Another Article",
            "url": "https://example.com/another",
            "content": "More content about AI and LangGraph.",
            "score": 0.88,
            "published_date": "2024-01-10",
        },
    ]


@pytest.fixture
def sample_scraped_content():
    return {
        "url": "https://example.com/article",
        "title": "Test Article",
        "content": "This is the full content of the test article.",
        "excerpt": "Short excerpt",
        "author": "John Doe",
        "published_date": "2024-01-15",
        "fetched_at": "2024-01-20T10:00:00Z",
    }


@pytest.fixture
def sample_llm_config():
    return {
        "provider": "ollama",
        "model": "gemma4:e2b",
        "api_key": "ollama",
        "base_url": "http://localhost:11434/v1",
    }
