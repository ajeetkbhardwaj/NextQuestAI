import os
import sys
import asyncio
import streamlit as st
from typing import List
from dotenv import load_dotenv

load_dotenv()

from src.workflow import research_graph
from src.database import save_research, get_all_research


LLM_PROVIDERS = {
    "nvidia": {
        "name": "Nvidia NIM",
        "needs_api_key": True,
        "base_url_default": "https://integrate.api.nvidia.com/v1",
        "models": [
            "mistralai/mistral-nemotron",
            "meta/llama-4-maverick-17b-128e-instruct",
            "google/gemma-3-27b-it",
            "nvidia/nemotron-3-super-120b-a12b",
            "google/gemma-3n-e4b-it",
            "deepseek-ai/deepseek-v4-flash",
        ],
        "default_model": "mistralai/mistral-nemotron",
    },
    "openrouter": {
        "name": "OpenRouter",
        "needs_api_key": True,
        "base_url_default": "https://openrouter.ai/api/v1",
        "models": [
            "google/gemini-2.0-flash-001",
            "anthropic/claude-3.5-sonnet",
            "deepseek/deepseek-r1",
            "meta-llama/llama-3.3-70b-instruct",
        ],
        "default_model": "google/gemini-2.0-flash-001",
    },
    "gemini": {
        "name": "Google Gemini",
        "needs_api_key": True,
        "base_url_default": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": [
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
        "default_model": "gemini-2.0-flash",
    },
    "huggingface": {
        "name": "HuggingFace",
        "needs_api_key": True,
        "base_url_default": "https://api-inference.huggingface.co/v1/",
        "models": [
            "meta-llama/Llama-3.2-3B-Instruct",
            "meta-llama/Llama-3.1-8B-Instruct",
            "Qwen/Qwen2-7B-Instruct",
        ],
        "default_model": "meta-llama/Llama-3.2-3B-Instruct",
    },
}


def create_initial_state(query: str, llm_config: dict, agent_config: dict):
    return {
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
            "llm_config": llm_config,
            "agent_config": agent_config,
        },
    }


async def run_research_async(query: str, llm_config: dict, agent_config: dict):
    state = create_initial_state(query, llm_config, agent_config)

    async for event in research_graph.astream(state):
        for node_name, node_state in event.items():
            yield node_name, node_state


def run_research_streaming(query: str, llm_config: dict, agent_config: dict):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run():
        async for node_name, node_state in run_research_async(
            query, llm_config, agent_config
        ):
            yield node_name, node_state

    async_gen = run()

    try:
        while True:
            try:
                node_name, node_state = loop.run_until_complete(async_gen.__anext__())
                yield node_name, node_state
            except StopAsyncIteration:
                break
    finally:
        loop.close()


@st.cache_data(ttl=300)
def get_dynamic_models(provider: str, api_key: str, base_url: str) -> List[str]:
    try:
        from src.llm import LLMFactory
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        models = loop.run_until_complete(LLMFactory.get_models(provider, api_key, base_url))
        loop.close()
        if models:
            return models
    except Exception:
        pass
    return LLM_PROVIDERS[provider]["models"]

def main():
    st.set_page_config(
        page_title="QuestNextAI - Deep Research Assistant",
        page_icon="🔮",
        layout="wide",
    )

    st.title("QuestNextAI")
    st.markdown("*Multi-Agent Research Assistant powered by LangGraph*")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_answer" not in st.session_state:
        st.session_state.current_answer = ""
    if "current_citations" not in st.session_state:
        st.session_state.current_citations = []
    if "research_trace" not in st.session_state:
        st.session_state.research_trace = []
    if "history" not in st.session_state:
        st.session_state.history = get_all_research(limit=20)


    with st.sidebar:
        st.header("⚙️ LLM Configuration")

        selected_provider = st.selectbox(
            "Provider",
            options=list(LLM_PROVIDERS.keys()),
            format_func=lambda x: LLM_PROVIDERS[x]["name"],
            index=0,
        )

        provider_info = LLM_PROVIDERS[selected_provider]

        api_key = ""
        env_key = os.getenv("NVIDIA_API_KEY") if selected_provider == "nvidia" else None
        
        if provider_info["needs_api_key"]:
            api_key = st.text_input(
                "🔑 API Key",
                type="password",
                value=env_key if env_key else "",
                placeholder=f"Enter your {provider_info['name']} API key",
                help="Leave empty to use the key from environment variables/secrets."
            )
            
            if not api_key and not env_key:
                st.warning(f"⚠️ API key required for {provider_info['name']}")
            elif not api_key and env_key:
                api_key = env_key

        dynamic_models = get_dynamic_models(selected_provider, api_key, provider_info.get("base_url_default"))

        model = st.selectbox(
            "Model",
            options=dynamic_models,
            index=0,
        )

        base_url = None

        st.divider()

        st.subheader("🔍 Research Settings")
        max_sources = st.slider("Max Sources", 3, 10, 5)
        deep_research = st.checkbox("Deep Research", value=True)

        st.divider()

        st.subheader("📜 History")

        if st.session_state.history:
            for item in st.session_state.history[:10]:
                with st.expander(f"Q: {item['query'][:40]}...", expanded=False):
                    st.markdown(f"**Query:** {item['query']}")
                    st.markdown(f"**Answer:** {item['answer'][:200]}...")
                    if item["sources"]:
                        st.markdown("**Sources:**")
                        for src in item["sources"][:5]:
                            st.markdown(
                                f"- [{src.get('title', 'Unknown')}]({src.get('url', '#')})"
                            )
        else:
            st.info("No history yet")


    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What would you like to research?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.research_trace = []
        st.session_state.current_answer = ""
        st.session_state.current_citations = []

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            answer_placeholder = st.empty()
            answer_placeholder.markdown("🔍 *Researching...*")

            research_container = st.expander("🧠 Research Process", expanded=False)
            sources_container = st.expander("📚 Sources", expanded=False)

            full_answer = ""
            citations = []
            reasoning = []
            search_count = 0
            scrape_count = 0
            analyze_count = 0

            for node_name, node_state in run_research_streaming(
                prompt,
                llm_config={
                    "provider": selected_provider,
                    "model": model,
                    "api_key": api_key if api_key else None,
                    "base_url": base_url,
                },
                agent_config={
                    "deep_research": deep_research,
                    "max_sources": max_sources,
                    "streaming": True,
                    "temperature": 0.7,
                    "max_tokens": 4000,
                },
            ):
                if node_name == "router":
                    next_step = node_state.get("next_step", "research")
                    if next_step == "direct":
                        research_container.markdown("🎯 **Router:** Direct answer possible")
                        answer_placeholder.markdown("✍️ *Synthesizing direct answer...*")
                    else:
                        research_container.markdown("🔍 **Router:** Research required")
                        answer_placeholder.markdown("📝 *Planning research strategy...*")

                elif node_name == "planner" and "refined_query" in node_state:
                    query = node_state.get("refined_query", "")
                    research_container.markdown(f"📝 **Planning:** {query}")
                    answer_placeholder.markdown("🌍 *Searching the web...*")

                elif node_name == "search" and "search_results" in node_state:
                    results = node_state.get("search_results", [])
                    search_count = len(results)
                    research_container.markdown(
                        f"🔍 **Search:** Found {search_count} results"
                    )
                    for r in results[:5]:
                        title = r.get("title", "Unknown")[:50]
                        url = r.get("url", "")
                        research_container.markdown(f"   - {title}...")
                        research_container.markdown(f"     🔗 {url}")
                    answer_placeholder.markdown("📄 *Scraping source contents...*")

                elif node_name == "scrape" and "scraped_content" in node_state:
                    scraped = node_state.get("scraped_content", [])
                    scrape_count = len(scraped)
                    research_container.markdown(
                        f"📄 **Scraping:** Extracted {scrape_count} pages"
                    )
                    answer_placeholder.markdown(f"🧠 *Parallel processing & analyzing {scrape_count} sources... (This takes a moment)*")

                elif node_name == "analyzer" and "extracted_facts" in node_state:
                    facts = node_state.get("extracted_facts", [])
                    analyze_count = len(facts)
                    research_container.markdown(
                        f"🧠 **Analyzing:** Extracted {analyze_count} facts"
                    )
                    answer_placeholder.markdown("✍️ *Synthesizing final answer...*")

                elif node_name == "synthesize" and "final_answer" in node_state:
                    full_answer = node_state.get("final_answer", "")
                    citations = node_state.get("citations", [])
                    reasoning = node_state.get("reasoning_trace", [])
                    research_container.markdown("✅ **Complete!**")

            answer_placeholder.markdown(full_answer)

            if citations:
                for i, cit in enumerate(citations, 1):
                    url = cit.get("url", "#")
                    title = cit.get("title", "Unknown")
                    sources_container.markdown(f"**[{i}]** [{title}]({url})")
                    sources_container.markdown(f"    🔗 {url}")
            else:
                sources_container.markdown("*No sources*")

            if reasoning:
                research_container.markdown("### 📋 Full Trace")
                for t in reasoning[-15:]:
                    research_container.markdown(f"- {t}")
            else:
                research_container.markdown("*No reasoning trace*")

            st.session_state.current_answer = full_answer
            st.session_state.current_citations = citations
            st.session_state.research_trace = reasoning
            st.session_state.messages.append({"role": "assistant", "content": full_answer})

            if full_answer:
                save_research(prompt, full_answer, citations, reasoning)
                st.session_state.history = get_all_research(limit=20)

if __name__ == "__main__":
    import sys
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    
    if get_script_run_ctx() is not None:
        main()
    else:
        from streamlit.web import cli as stcli
        sys.argv = ["streamlit", "run", sys.argv[0]]
        sys.exit(stcli.main())