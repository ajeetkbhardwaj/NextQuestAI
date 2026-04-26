import asyncio
import os
import logging
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
import sys

sys.path.insert(0, str(project_root))

from src.config import config
from src.workflow import research_graph
from src.models import AgentState

# Configure logging to see progress from the agents
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')


async def test_workflow():
    print("=" * 60)
    print("🔮 NexusAI Workflow Test")
    print("=" * 60)

    # Config is loaded automatically from your .env file via src/config.py
    # To override them manually for testing, uncomment and change the lines below:
    config.llm.provider = "nvidia"
    config.llm.model = "google/gemma-3n-e4b-it"
    # If your API key is not in your .env file, uncomment and set it directly here:
    #os.environ["NVIDIA_API_KEY"] = "nvapi-your-key-goes-here"
    
    config.search.provider = "duckduckgo"
    config.agent.max_sources = 3
    
    # Example: How to use a custom provider like Groq or DeepSeek
    # config.llm.provider = "custom"
    # config.llm.model = "llama3-8b-8192"
    # config.llm.base_url = "https://api.groq.com/openai/v1"
    # os.environ["CUSTOM_API_KEY"] = "gsk_your_groq_key"

    print(f"\n📋 Config:")
    print(f"   LLM Provider: {config.llm.provider}")
    print(f"   LLM Model: {config.llm.model}")
    print(f"   LLM Base URL: {config.llm.base_url}")
    print(f"   Search Provider: {config.search.provider}")
    print(f"   Max Sources: {config.agent.max_sources}")

    # Test query
    query = "What is LangGraph?"
    print(f"\n🔍 Test Query: {query}")
    print("-" * 40)

    # Create initial state
    state: AgentState = {
        "original_query": query,
        "refined_query": None,
        "search_results": [],
        "scraped_content": [],
        "extracted_facts": [],
        "final_answer": "",
        "citations": [],
        "reasoning_trace": [],
        "error": None,
        "status": "pending",
        "metadata": {
            "deep_research": False,  # Set to False for a faster test run
            "llm_config": {
                "provider": config.llm.provider,
                "model": config.llm.model,
                "base_url": config.llm.base_url,
                "api_key": config.llm.api_key,
            }
        },
    }

    # Run the workflow
    try:
        async for event in research_graph.astream(state):
            for node_name, node_state in event.items():
                print(f"\n📍 Node: {node_name}")

                if node_name == "planner":
                    print(f"   refined_query: {node_state.get('refined_query', 'N/A')}")

                elif node_name == "search":
                    results = node_state.get("search_results", [])
                    print(f"   Found {len(results)} search results")
                    for r in results[:3]:
                        print(
                            f"   - {r.get('title', 'Untitled')[:50]}... -> {r.get('url', '')[:40]}..."
                        )

                elif node_name == "scrape":
                    scraped = node_state.get("scraped_content", [])
                    print(f"   Scraped {len(scraped)} pages")
                    for s in scraped[:3]:
                        print(f"   - {s.get('title', 'Untitled')[:50]}")

                elif node_name == "analyzer":
                    facts = node_state.get("extracted_facts", [])
                    print(f"   Extracted {len(facts)} facts")

                elif node_name == "synthesize":
                    answer = node_state.get("final_answer", "")
                    citations = node_state.get("citations", [])
                    trace = node_state.get("reasoning_trace", [])

                    print(f"\n✅ FINAL ANSWER:")
                    print("-" * 40)
                    print(answer[:500] + "..." if len(answer) > 500 else answer)

                    print(f"\n📚 CITATIONS ({len(citations)}):")
                    for c in citations:
                        print(f"   [{c.get('index')}] {c.get('title', 'Untitled')}")
                        print(f"       {c.get('url', '')}")

                    print(f"\n🧠 REASONING TRACE:")
                    for t in trace[-5:]:
                        print(f"   {t}")

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60)
    print("✅ Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_workflow())
