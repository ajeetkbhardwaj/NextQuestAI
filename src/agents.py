import asyncio
import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from .prompts import SYSTEM_PROMPTS
from .models import AgentState, SearchResult, ScrapedContent, ExtractedFact, Citation, get_agent_settings
from .search import search_manager
from .scraper import scraper
from .llm import llm_factory
from .config import config as default_config
from .resilience import retry_with_backoff, search_cache

logger = logging.getLogger(__name__)


def get_llm_config_from_state(state: AgentState) -> dict:
    return state.get("metadata", {}).get(
        "llm_config",
        {
            "provider": "nvidia",
            "model": "mistralai/mistral-nemotron",
            "api_key": None,
        },
    )


def get_deep_research_flag(state: AgentState) -> bool:
    metadata = state.get("metadata", {})
    if "deep_research" in metadata:
        return bool(metadata["deep_research"])
    return state.get("deep_research", False)


async def call_llm_with_retry(
    messages, llm_config: dict, temperature=0.5, max_tokens=500
):
    async def _call():
        llm = llm_factory.create(
            llm_config.get("provider", "nvidia"),
            llm_config.get("model"),
            api_key=llm_config.get("api_key"),
            base_url=llm_config.get("base_url") if llm_config.get("provider") in ("huggingface", "openrouter") else None,
            timeout=120.0,
        )
        return await llm.generate(
            messages, temperature=temperature, max_tokens=max_tokens
        )

    return await retry_with_backoff(
        _call,
        max_retries=2,
        base_delay=1.0,
        exponential_base=2.0,
    )


def extract_refined_query(response_content: str, fallback_query: str) -> str:
    patterns = [
        r'[""]([^""]+)[""]',
        r'\*\*Refined Search Query:\*\*\s*(.+?)(?:\n|$)',
        r'Refined Query:\s*(.+?)(?:\n|$)',
        r'Search query:\s*(.+?)(?:\n|$)',
    ]

    for pattern in patterns:
        match = re.search(pattern, response_content, re.IGNORECASE | re.MULTILINE)
        if match:
            query = match.group(1).strip()[:500]
            if query and len(query) >= 3:
                return query

    lines = response_content.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line and len(line) >= 10 and not line.startswith(("=", "-", "*", "#")):
            cleaned = re.sub(r'^\d+[.)]\s*', '', line)[:500]
            if cleaned:
                return cleaned

    return fallback_query[:500]


async def router_node(state: AgentState) -> AgentState:
    """Decides if the query needs web research or a direct answer."""
    query = state["original_query"]
    llm_config = get_llm_config_from_state(state)

    logger.info(f"[ROUTER] Analyzing query: {query[:50]}...")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["router"]},
        {"role": "user", "content": query},
    ]

    try:
        response = await call_llm_with_retry(
            messages, llm_config, temperature=0.0, max_tokens=10
        )
        decision = response.content.strip().upper()
        
        # Default to RESEARCH if unclear
        if "DIRECT" in decision:
            state["next_step"] = "direct"
        else:
            state["next_step"] = "research"
            
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Router: Decision - {state['next_step']}"
        )
    except Exception as e:
        logger.error(f"[ROUTER] Error: {e}")
        state["next_step"] = "research"
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Router: Defaulting to research due to error: {e}"
        )

    return state


async def planner_node(state: AgentState) -> AgentState:
    """Analyzes query and creates research strategy."""
    query = state["original_query"]
    llm_config = get_llm_config_from_state(state)
    deep_research = get_deep_research_flag(state)
    state["deep_research"] = deep_research

    settings = get_agent_settings(deep_research)
    state["metadata"]["agent_settings"] = settings

    logger.info(
        f"[PLANNER] Mode: {'Deep' if deep_research else 'Quick'}, "
        f"provider={llm_config.get('provider')}, model={llm_config.get('model')}"
    )

    state["reasoning_trace"].append(
        f"[{datetime.now(timezone.utc).isoformat()}] Planner: {'Deep' if deep_research else 'Quick'} research mode"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["planner"]},
        {
            "role": "user",
            "content": f"User question: {query}\n\nCreate a refined search query and brief plan.",
        },
    ]

    try:
        logger.info("[PLANNER] Calling LLM...")
        response = await call_llm_with_retry(
            messages, llm_config, temperature=0.5, max_tokens=500
        )
        logger.debug(f"[PLANNER] LLM response: {response.content[:200]}...")

        state["refined_query"] = extract_refined_query(response.content, query)
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Planner: Refined query - {state['refined_query'][:100]}"
        )
    except Exception as e:
        logger.error(f"[PLANNER] Error: {e}")
        state["refined_query"] = query
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Planner: Using original query due to error: {e}"
        )

    return state


async def search_node(state: AgentState) -> AgentState:
    """Executes web search using configured provider with caching."""
    query = state.get("refined_query") or state["original_query"]
    llm_config = get_llm_config_from_state(state)
    deep_research = state.get("deep_research", False)
    settings = state.get("metadata", {}).get("agent_settings", get_agent_settings(deep_research))

    agent_config = state.get("metadata", {}).get("agent_config", {})
    search_provider = agent_config.get("search_provider", "duckduckgo")
    max_results = settings.get("max_search_results", 10)

    is_retry = state.get("retry_count", 0) > 0
    if is_retry:
        query = f"{query} detailed explanation"

    logger.info(f"[SEARCH] Query: {query}, provider: {search_provider}, deep={deep_research}")
    state["reasoning_trace"].append(
        f"[{datetime.now(timezone.utc).isoformat()}] Search: Searching for '{query[:50]}...'"
    )

    cache_key = f"{search_provider}:{query}:{max_results}:{deep_research}"
    
    if not is_retry:
        cached = search_cache.get_sync(cache_key)
        if cached:
            state["search_results"] = cached
            state["reasoning_trace"].append(
                f"[{datetime.now(timezone.utc).isoformat()}] Search: Using cached results ({len(cached)} items)"
            )
            return state

    async def _do_search():
        return await search_manager.search(
            query=query,
            provider=search_provider,
            max_results=max_results,
        )

    try:
        results = await retry_with_backoff(
            _do_search,
            max_retries=2,
            base_delay=1.0,
            exponential_base=2.0,
        )
        logger.info(f"[SEARCH] Found {len(results)} results")

        if len(results) == 0:
            logger.warning("[SEARCH] No results found!")

        valid_results = [r for r in results if r.title and r.url and len(r.url) > 5]

        state["search_results"] = [
            {
                "title": r.title,
                "url": r.url,
                "content": r.content,
                "score": r.score,
                "published_date": r.published_date,
            }
            for r in valid_results
        ]

        search_cache.set_sync(cache_key, state["search_results"])

        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Search: Found {len(valid_results)} valid results"
        )

    except Exception as e:
        logger.error(f"[SEARCH] Error: {e}")
        state["error"] = f"Search failed: {str(e)}"
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Search: Error - {str(e)}"
        )

    return state


async def scrape_node(state: AgentState) -> AgentState:
    """Fetches and extracts content from top search results."""
    search_results = state.get("search_results", [])
    deep_research = state.get("deep_research", False)
    settings = state.get("metadata", {}).get("agent_settings", get_agent_settings(deep_research))

    max_sources = settings.get("max_sources", 5)
    max_concurrent = settings.get("analyzer_concurrency", 3)

    logger.info(f"[SCRAPE] search_results count: {len(search_results)}")
    if not search_results:
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Scrape: No results to scrape"
        )
        return state

    urls = [r["url"] for r in search_results[:max_sources]]
    logger.info(f"[SCRAPE] Fetching {len(urls)} URLs (max_concurrent={max_concurrent})")
    state["reasoning_trace"].append(
        f"[{datetime.now(timezone.utc).isoformat()}] Scrape: Fetching {len(urls)} URLs"
    )

    try:
        scraped = await scraper.fetch_multiple(urls, max_concurrent=max_concurrent)
        logger.info(f"[SCRAPE] Scraped {len(scraped)} items")

        scraped_dict = {s.url: s for s in scraped if s}
        max_scraped_content = settings.get("max_content_for_scraping", 5000)
        final_content = []

        for r in search_results[:max_sources]:
            url = r["url"]
            if url in scraped_dict and scraped_dict[url].content:
                s = scraped_dict[url]
                final_content.append(
                    {
                        "url": s.url,
                        "title": s.title,
                        "content": s.content[:max_scraped_content],
                        "excerpt": s.excerpt,
                        "author": s.author,
                        "published_date": s.published_date,
                        "fetched_at": s.fetched_at,
                    }
                )
            elif r.get("content"):
                logger.info(f"[SCRAPE] Using search snippet fallback for: {url}")
                snippet = r["content"]
                final_content.append(
                    {
                        "url": url,
                        "title": r.get("title", "Unknown"),
                        "content": snippet,
                        "excerpt": snippet[:300] + "..." if len(snippet) > 300 else snippet,
                        "author": None,
                        "published_date": r.get("published_date"),
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

        state["scraped_content"] = final_content

        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Scrape: Successfully extracted content from {len(scraped)} sources"
        )
    except Exception as e:
        logger.error(f"[SCRAPE] Error: {e}")
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Scrape: Error - {str(e)}"
        )

    return state


async def analyze_source(
    source: dict, query: str, llm, semaphore: asyncio.Semaphore, settings: dict
) -> List[dict]:
    """Analyze a single source and extract facts."""
    async with semaphore:
        max_content = settings.get("max_content_for_analyzer", 3000)
        content = source.get("content", "")[:max_content]
        if not content:
            logger.warning(f"[ANALYZER] No content for source: {source.get('url', 'unknown')}")
            return []

        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["analyzer"]},
            {
                "role": "user",
                "content": f"User question: {query}\n\nSource title: {source.get('title', 'Unknown')}\nSource URL: {source.get('url', '')}\n\nContent:\n{content}\n\nExtract key facts relevant to the question. Format as: FACT | CATEGORY | CONFIDENCE\n\nAlso extract the source sentence that best supports each fact.",
            },
        ]

        for attempt in range(2):
            try:
                logger.info(
                    f"[ANALYZER] Calling LLM for {source.get('url', 'unknown')[:30]}... (attempt {attempt + 1})"
                )
                response = await llm.generate(
                    messages, temperature=0.3, max_tokens=2500
                )
                logger.debug(
                    f"[ANALYZER] LLM response: {response.content[:200] if response.content else 'EMPTY'}"
                )

                if not response.content or not response.content.strip():
                    logger.warning(f"[ANALYZER] Empty response from LLM")
                    return []

                facts = []
                captured_facts = False

                for line in response.content.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    if "|" in line:
                        parts = line.split("|")
                        if len(parts) >= 2:
                            try:
                                confidence = (
                                    float(parts[2].strip()) if len(parts) > 2 else 0.8
                                )
                            except ValueError:
                                confidence = 0.8
                            facts.append(
                                {
                                    "source_url": source.get("url", ""),
                                    "source_title": source.get("title", ""),
                                    "fact": parts[0].strip(),
                                    "category": parts[1].strip(),
                                    "confidence": confidence,
                                    "source_sentence": parts[0].strip(),
                                }
                            )
                            captured_facts = True
                    elif (
                        len(line) > 20
                        and not line.startswith("-")
                        and not line.startswith("*")
                    ):
                        facts.append(
                            {
                                "source_url": source.get("url", ""),
                                "source_title": source.get("title", ""),
                                "fact": line,
                                "category": "general",
                                "confidence": 0.7,
                                "source_sentence": line[:200],
                            }
                        )
                        captured_facts = True

                if not captured_facts and response.content.strip():
                    facts.append(
                        {
                            "source_url": source.get("url", ""),
                            "source_title": source.get("title", ""),
                            "fact": response.content.strip()[:500],
                            "category": "general",
                            "confidence": 0.7,
                            "source_sentence": response.content.strip()[:200],
                        }
                    )

                logger.info(
                    f"[ANALYZER] Extracted {len(facts)} facts from {source.get('url', 'unknown')[:30]}"
                )
                return facts

            except Exception as e:
                logger.error(f"[ANALYZER] Error analyzing source: {e}")
                if attempt == 0:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                return []


async def analyzer_node(state: AgentState) -> AgentState:
    """Extracts key facts from scraped content with parallel processing."""
    scraped = state.get("scraped_content", [])
    query = state["original_query"]
    deep_research = state.get("deep_research", False)
    settings = state.get("metadata", {}).get("agent_settings", get_agent_settings(deep_research))
    analysis_round = state.get("analysis_round", 0)

    if not scraped:
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Analyzer: No content to analyze"
        )
        return state

    state["analysis_round"] = analysis_round + 1
    llm_config = get_llm_config_from_state(state)

    max_sources_to_analyze = settings.get("max_sources_to_analyze", 5)
    sources_to_analyze = scraped[:max_sources_to_analyze]

    state["reasoning_trace"].append(
        f"[{datetime.now(timezone.utc).isoformat()}] Analyzer: Round {state['analysis_round']}, analyzing {len(sources_to_analyze)} sources"
    )

    model = llm_config.get("model") or "deepseek-ai/deepseek-r1"
    logger.info(f"[ANALYZER] Using model: {model}, round={state['analysis_round']}")

    llm = llm_factory.create(
        llm_config.get("provider", "nvidia"),
        model,
        api_key=llm_config.get("api_key"),
        base_url=llm_config.get("base_url") if llm_config.get("provider") in ("huggingface", "openrouter") else None,
        timeout=120.0,
    )

    concurrency = settings.get("analyzer_concurrency", 3)
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [analyze_source(source, query, llm, semaphore, settings) for source in sources_to_analyze]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    facts = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"[ANALYZER] Exception in results: {result}")
            state["reasoning_trace"].append(f"[{datetime.now(timezone.utc).isoformat()}] Analyzer: Partial failure during extraction.")
        elif isinstance(result, list):
            facts.extend(result)

    existing_facts = state.get("extracted_facts", [])
    all_facts = existing_facts + facts
    state["extracted_facts"] = all_facts

    state["reasoning_trace"].append(
        f"[{datetime.now(timezone.utc).isoformat()}] Analyzer: Extracted {len(facts)} facts (total: {len(all_facts)})"
    )

    min_facts_threshold = settings.get("min_facts_threshold", 3)
    retry_count = state.get("retry_count", 0)

    if len(facts) < min_facts_threshold and retry_count == 0 and analysis_round == 0:
        logger.warning(f"[ANALYZER] Insufficient facts ({len(facts)} < {min_facts_threshold}), triggering retry")
        state["retry_count"] = 1
        state["analysis_round"] = 0
        state["extracted_facts"] = []
        state["scraped_content"] = []
        state["search_results"] = []

    return state


async def ranker_node(state: AgentState) -> AgentState:
    """Ranks and filters extracted facts based on relevance to the query."""
    query = state["original_query"]
    facts = state.get("extracted_facts", [])
    llm_config = get_llm_config_from_state(state)

    if not facts or len(facts) < 10:
        return state

    logger.info(f"[RANKER] Ranking {len(facts)} facts...")
    state["reasoning_trace"].append(
        f"[{datetime.now(timezone.utc).isoformat()}] Ranker: Filtering {len(facts)} facts for relevance"
    )

    # Group facts into blocks for ranking to save tokens
    fact_texts = [f"- {f['fact']}" for f in facts]
    
    messages = [
        {"role": "system", "content": "You are a relevance filter. Given a query and a list of facts, return ONLY the facts that directly answer the query. Remove duplicates and minor details. Output each relevant fact on a new line."},
        {
            "role": "user",
            "content": f"Query: {query}\n\nFacts:\n" + "\n".join(fact_texts[:50]), # Limit to top 50 for safety
        },
    ]

    try:
        response = await call_llm_with_retry(
            messages, llm_config, temperature=0.1, max_tokens=2000
        )
        ranked_lines = response.content.split("\n")
        
        # Simple string matching to find original fact objects
        ranked_facts = []
        for line in ranked_lines:
            line = line.strip().lstrip("- ").lower()
            if not line: continue
            for f in facts:
                if line in f['fact'].lower() or f['fact'].lower() in line:
                    if f not in ranked_facts:
                        ranked_facts.append(f)
                    break
        
        if ranked_facts:
            logger.info(f"[RANKER] Kept {len(ranked_facts)} relevant facts")
            state["extracted_facts"] = ranked_facts
        
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Ranker: Reduced to {len(state['extracted_facts'])} high-relevance facts"
        )
    except Exception as e:
        logger.error(f"[RANKER] Error: {e}")
        
    return state


async def synthesizer_node(state: AgentState) -> AgentState:
    """Generates final answer with citations."""
    query = state["original_query"]
    facts = state.get("extracted_facts", [])
    scraped = state.get("scraped_content", [])
    error = state.get("error")
    search_results = state.get("search_results", [])
    deep_research = state.get("deep_research", False)

    if error:
        logger.error(f"[SYNTHESIZER] Error in pipeline: {error}")
        state["final_answer"] = (
            f"I encountered an error during research: {error}\n\n"
            f"Search returned {len(search_results)} results. "
            f"Scraper found {len(scraped)} articles."
        )
        state["status"] = "complete"
        return state

    if not scraped and state.get("next_step") != "direct":
        logger.warning("[SYNTHESIZER] No content to synthesize")
        state["final_answer"] = (
            f"I couldn't find sufficient information to answer your question.\n\n"
            f"Search returned {len(search_results)} results."
        )
        state["status"] = "complete"
        return state

    state["reasoning_trace"].append(
        f"[{datetime.now(timezone.utc).isoformat()}] Synthesizer: Generating answer with {len(facts)} facts"
    )

    llm_config = get_llm_config_from_state(state)
    agent_config = state.get("metadata", {}).get("agent_config", {})
    settings = state.get("metadata", {}).get("agent_settings", get_agent_settings(deep_research))

    max_sources = settings.get("max_sources", 5)
    max_content_for_synth = settings.get("max_content_for_synthesizer", 1500)

    context_parts = []
    for i, source in enumerate(scraped[:max_sources], 1):
        context_parts.append(
            f"[{i}] {source.get('title', 'Unknown')}\n{source.get('url', '')}\n{source.get('content', '')[:max_content_for_synth]}\n"
        )

    context = "\n".join(context_parts)

    facts_context = ""
    if facts:
        facts_list = []
        for j, fact in enumerate(facts[:20], 1):
            source_title = fact.get("source_title", "")
            facts_list.append(f"{j}. {fact.get('fact', '')} (Source: {source_title}, Conf: {fact.get('confidence', 0):.1f})")
        facts_context = "\n\nExtracted Facts:\n" + "\n".join(facts_list)

    if state.get("next_step") == "direct":
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Answer the user's question directly and concisely based on your internal knowledge. Do not use citations since no web research was performed."},
            {"role": "user", "content": query},
        ]
    else:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["synthesizer"]},
            {
                "role": "user",
                "content": f"User question: {query}\n\nSources:\n{context}{facts_context}\n\nGenerate a comprehensive answer with proper citations. Use [1], [2], etc. format.",
            },
        ]

    async def _generate_with_retry():
        llm = llm_factory.create(
            llm_config.get("provider", "nvidia"),
            llm_config.get("model"),
            api_key=llm_config.get("api_key"),
            base_url=llm_config.get("base_url") if llm_config.get("provider") in ("huggingface", "openrouter") else None,
            timeout=120.0,
        )
        if agent_config.get("streaming", True):
            full_response = ""
            async for chunk in llm.stream_generate(
                messages,
                temperature=agent_config.get("temperature", 0.7),
                max_tokens=agent_config.get("max_tokens", 4000),
            ):
                full_response += chunk
            return full_response
        else:
            response = await llm.generate(
                messages,
                temperature=agent_config.get("temperature", 0.7),
                max_tokens=agent_config.get("max_tokens", 4000),
            )
            return response.content

    try:
        state["final_answer"] = await retry_with_backoff(
            _generate_with_retry,
            max_retries=2,
            base_delay=1.0,
            exponential_base=2.0,
        )
    except Exception as e:
        logger.error(f"[SYNTHESIZER] Error generating answer: {e}")
        state["final_answer"] = f"Error generating answer: {str(e)}"

    citations = []
    for i, source in enumerate(scraped[:max_sources], 1):
        citations.append(
            {
                "index": i,
                "url": source.get("url", ""),
                "title": source.get("title", "Unknown"),
                "context": source.get("excerpt", "")[:200],
            }
        )

    state["citations"] = citations
    state["reasoning_trace"].append(
        f"[{datetime.now(timezone.utc).isoformat()}] Synthesizer: Complete with {len(citations)} citations"
    )

    return state
async def verifier_node(state: AgentState) -> AgentState:
    """Verifies the final answer against extracted facts for accuracy."""
    answer = state.get("final_answer", "")
    facts = state.get("extracted_facts", [])
    llm_config = get_llm_config_from_state(state)

    if not answer or not facts:
        state["status"] = "complete"
        return state

    logger.info("[VERIFIER] Verifying answer accuracy...")
    state["reasoning_trace"].append(
        f"[{datetime.now(timezone.utc).isoformat()}] Verifier: Checking for hallucinations or inaccuracies"
    )

    fact_texts = [f"- {f['fact']}" for f in facts[:30]]
    
    messages = [
        {"role": "system", "content": "You are a fact-checker. Compare the Answer to the provided Facts. If the Answer contains information NOT in the Facts or contradicts them, rewrite the Answer to be accurate. If the Answer is already accurate, return it exactly as is. Always maintain citations [1], [2], etc."},
        {
            "role": "user",
            "content": f"Facts:\n" + "\n".join(fact_texts) + f"\n\nAnswer:\n{answer}",
        },
    ]

    try:
        response = await call_llm_with_retry(
            messages, llm_config, temperature=0.1, max_tokens=4000
        )
        if response.content and len(response.content) > 100:
            if response.content.strip() != answer.strip():
                logger.info("[VERIFIER] Self-correction applied to answer")
                state["final_answer"] = response.content
                state["reasoning_trace"].append(
                    f"[{datetime.now(timezone.utc).isoformat()}] Verifier: Applied self-correction to improve accuracy"
                )
            else:
                logger.info("[VERIFIER] Answer verified as accurate")
                state["reasoning_trace"].append(
                    f"[{datetime.now(timezone.utc).isoformat()}] Verifier: Answer verified against source facts"
                )
    except Exception as e:
        logger.error(f"[VERIFIER] Error: {e}")
        
    state["status"] = "complete"
    return state
