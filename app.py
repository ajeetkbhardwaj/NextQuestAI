import os
import sys
import asyncio
import streamlit as st
from typing import List
from dotenv import load_dotenv

load_dotenv()

from src.workflow import research_graph


LLM_PROVIDERS = {
    "ollama": {
        "name": "Ollama (Local)",
        "needs_api_key": False,
        "base_url_default": "http://localhost:11434/v1",
        "models": [
            "gemma4:e2b",
            "llama3.2",
            "llama3.2:1b",
            "llama3.2:3b",
            "llama3.1",
            "mistral",
            "phi3",
            "qwen2.5",
            "codellama",
        ],
        "default_model": "gemma4:e2b",
    },
    "openai": {
        "name": "OpenAI",
        "needs_api_key": True,
        "base_url_default": None,
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ],
        "default_model": "gpt-4o",
    },
    "anthropic": {
        "name": "Anthropic",
        "needs_api_key": True,
        "base_url_default": None,
        "models": [
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet-20240620",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
        ],
        "default_model": "claude-3-5-sonnet-20241022",
    },
    "gemini": {
        "name": "Google Gemini",
        "needs_api_key": True,
        "base_url_default": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": [
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
        ],
        "default_model": "gemini-2.0-flash",
    },
    "huggingface": {
        "name": "HuggingFace",
        "needs_api_key": True,
        "base_url_default": "https://api-inference.huggingface.co/v1/",
        "models": [
            "meta-llama/Llama-3.2-3B-Instruct",
            "meta-llama/Llama-3.2-1B-Instruct",
            "meta-llama/Llama-3.1-8B-Instruct",
            "microsoft/Phi-3-mini-128k-instruct",
            "Qwen/Qwen2-7B-Instruct",
            "mistralai/Mistral-7B-Instruct-v0.2",
        ],
        "default_model": "meta-llama/Llama-3.2-3B-Instruct",
    },
    "nvidia": {
        "name": "Nvidia NIM",
        "needs_api_key": True,
        "base_url_default": None,
        "models": [
            "google/gemma-3n-e4b-it",
            "deepseek-ai/deepseek-v3.2",
            "meta/llama-3.1-70b-instruct",
            "nvidia/llama-3.1-nemotron-70b-instruct",
        ],
        "default_model": "google/gemma-3n-e4b-it",
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
        st.session_state.history = []


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
        if provider_info["needs_api_key"]:
            api_key = st.text_input(
                "🔑 API Key",
                type="password",
                placeholder=f"Enter your {provider_info['name']} API key",
            )
            if not api_key:
                st.warning(f"⚠️ API key required for {provider_info['name']}")

        dynamic_models = get_dynamic_models(selected_provider, api_key, provider_info.get("base_url_default"))

        model = st.selectbox(
            "Model",
            options=dynamic_models,
            index=0,
        )

        base_url = None
        if selected_provider == "ollama":
            base_url = st.text_input(
                "Base URL",
                value=provider_info["base_url_default"],
                placeholder="http://localhost:11434/v1",
            )

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
                if node_name == "planner" and "refined_query" in node_state:
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
                st.session_state.history.insert(0, {
                    "query": prompt,
                    "answer": full_answer,
                    "sources": citations
                })

if __name__ == "__main__":
    import sys
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    
    if get_script_run_ctx() is not None:
        main()
    else:
        from streamlit.web import cli as stcli
        sys.argv = ["streamlit", "run", sys.argv[0]]
        sys.exit(stcli.main())