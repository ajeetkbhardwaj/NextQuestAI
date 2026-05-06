import asyncio
import logging
import re
import time
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
    step_start = time.perf_counter()
    query = state["original_query"]
    llm_config = get_llm_config_from_state(state)

    logger.info(f"[ROUTER] Analyzing query: {query[:50]}...")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["router"]},
        {"role": "user", "content": query},
    ]

    try:
        response = await call_llm_with_retry(
            messages, llm_config, temperature=0.0, max_tokens=50
        )
        content = response.content.strip()

        import json, re
        json_match = re.search(r'\{.*\}', content.replace('\n', ''), re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
            decision = parsed.get("route", "RESEARCH").upper()
            intent = parsed.get("intent", "general").lower()
        else:
            decision = content.upper()
            intent = "general"

        if "CLARIFY" in decision:
            state["next_step"] = "clarify"
        elif "DIRECT" in decision:
            state["next_step"] = "direct"
        else:
            state["next_step"] = "research"
            
        state["query_intent"] = intent

        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Router: Decision - {state['next_step']}, Intent - {intent} (took {time.perf_counter() - step_start:.2f}s)"
        )
    except Exception as e:
        logger.error(f"[ROUTER] Error: {e}")
        state["next_step"] = "research"
        state["query_intent"] = "general"
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Router: Defaulting to research due to error: {e} (took {time.perf_counter() - step_start:.2f}s)"
        )

    return state


async def planner_node(state: AgentState) -> AgentState:
    """Analyzes query and creates research strategy."""
    step_start = time.perf_counter()
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
        logger.info("[PLANNER] Generating HyDE document and calling Planner LLM concurrently...")
        hyde_start = time.perf_counter()
        llm_start = time.perf_counter()
        
        hyde_msg = [{"role": "system", "content": SYSTEM_PROMPTS.get("hyde", "")}, {"role": "user", "content": query}]
        
        hyde_task = call_llm_with_retry(hyde_msg, llm_config, temperature=0.7, max_tokens=250)
        planner_task = call_llm_with_retry(messages, llm_config, temperature=0.5, max_tokens=500)
        
        hyde_res, response = await asyncio.gather(hyde_task, planner_task)

        state["hyde_document"] = hyde_res.content.strip()
        state["reasoning_trace"].append(f"[{datetime.now(timezone.utc).isoformat()}] Planner: Generated HyDE document for semantic expansion (took {time.perf_counter() - hyde_start:.2f}s)")
        logger.debug(f"[PLANNER] LLM response: {response.content[:200]}...")
        
        import json, re
        json_match = re.search(r'\[.*\]', response.content.replace('\n', ''), re.DOTALL)
        if json_match:
            sub_queries = json.loads(json_match.group(0))
            state["sub_queries"] = [str(q)[:150] for q in sub_queries if isinstance(q, str)]
        else:
            state["sub_queries"] = [query]
            
        state["refined_query"] = state["sub_queries"][0] if state.get("sub_queries") else query
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Planner: Generated {len(state.get('sub_queries', []))} sub-queries (took {time.perf_counter() - llm_start:.2f}s)"
        )
    except Exception as e:
        logger.error(f"[PLANNER] Error: {e}")
        state["refined_query"] = query
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Planner: Using original query due to error: {e} (took {time.perf_counter() - step_start:.2f}s)"
        )

    return state


async def search_node(state: AgentState) -> AgentState:
    """Executes web search using configured provider with caching."""
    step_start = time.perf_counter()
    query = state.get("refined_query") or state["original_query"]
    llm_config = get_llm_config_from_state(state)
    deep_research = state.get("deep_research", False)
    settings = state.get("metadata", {}).get("agent_settings", get_agent_settings(deep_research))

    agent_config = state.get("metadata", {}).get("agent_config", {})
    search_provider = agent_config.get("search_provider", "duckduckgo")
    max_results = settings.get("max_search_results", 10)

    is_retry = state.get("retry_count", 0) > 0
    if is_retry:
        # Search Query Evolution for fallback
        query = f"{query} deeper analysis and recent facts"
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Search: Evolved query for retry -> '{query}'"
        )

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
                f"[{datetime.now(timezone.utc).isoformat()}] Search: Using cached results ({len(cached)} items) (took {time.perf_counter() - step_start:.2f}s)"
            )
            return state

    # Compile queries to run in parallel
    queries_to_run = [query]
    if state.get("sub_queries"):
        queries_to_run.extend(state["sub_queries"])
    if state.get("hyde_document"):
        # Truncate HyDE document to not exceed search engine limits
        queries_to_run.append(state["hyde_document"][:150])
    queries_to_run = list(set(queries_to_run)) # Deduplicate

    async def _search_and_eval(current_query: str) -> list:
        max_attempts = 2 if deep_research else 1
        for attempt in range(max_attempts):
            try:
                async def _do_search():
                    return await search_manager.search(query=current_query, provider=search_provider, max_results=max_results)

                results = await retry_with_backoff(
                    _do_search,
                    max_retries=2, base_delay=1.0, exponential_base=2.0
                )
                valid = [r for r in results if r.title and r.url and len(r.url) > 5]
                if not valid or attempt == max_attempts - 1:
                    return valid
                    
                snippet_text = "\n".join([f"Source: {r.url}\nSnippet: {r.content}" for r in valid[:5]])
                eval_messages = [
                    {"role": "system", "content": SYSTEM_PROMPTS.get("search_evaluator", "Reply PASS if good.")},
                    {"role": "user", "content": f"Query: {current_query}\n\nResults:\n{snippet_text}"}
                ]
                eval_response = await call_llm_with_retry(eval_messages, llm_config, temperature=0.2, max_tokens=50)
                if "PASS" in eval_response.content.upper():
                    return valid
                else:
                    current_query = eval_response.content.strip('"\'')
            except Exception as e:
                logger.error(f"[SEARCH] Query search error for {current_query}: {e}")
                return []
        return []

    try:
        tasks = [_search_and_eval(q) for q in queries_to_run]
        all_results_lists = await asyncio.gather(*tasks)
        
        # Flatten and deduplicate by URL (Interleaving for fairness across sub-queries)
        seen_urls = set()
        valid_results = []
        max_len = max((len(l) for l in all_results_lists), default=0)
        for i in range(max_len):
            for res_list in all_results_lists:
                if i < len(res_list):
                    r = res_list[i]
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        valid_results.append(r)
                    
        if len(valid_results) == 0:
            logger.warning("[SEARCH] No results found after attempts!")

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
            f"[{datetime.now(timezone.utc).isoformat()}] Search: Found {len(valid_results)} valid results (took {time.perf_counter() - step_start:.2f}s)"
        )
        
        for r in state["search_results"][:5]:
            state["reasoning_trace"].append(f"   🔗 {r['title'][:50]}... ({r['url']})")

    except Exception as e:
        logger.error(f"[SEARCH] Error: {e}")
        state["error"] = f"Search failed: {str(e)}"
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Search: Error - {str(e)} (took {time.perf_counter() - step_start:.2f}s)"
        )

    return state


async def scrape_node(state: AgentState) -> AgentState:
    """Fetches and extracts content from top search results."""
    step_start = time.perf_counter()
    search_results = state.get("search_results", [])
    deep_research = state.get("deep_research", False)
    settings = state.get("metadata", {}).get("agent_settings", get_agent_settings(deep_research))

    max_sources = settings.get("max_sources", 5)
    max_concurrent = settings.get("analyzer_concurrency", 3)

    logger.info(f"[SCRAPE] search_results count: {len(search_results)}")
    if not search_results:
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Scrape: No results to scrape (took {time.perf_counter() - step_start:.2f}s)"
        )
        return state

    # Only race the top (max_sources + 3) URLs to preserve relevance while allowing for some timeouts
    top_results = search_results[:max_sources + 3]
    urls = [r["url"] for r in top_results]
    logger.info(f"[SCRAPE] Racing to fetch {max_sources} sources from top {len(urls)} URLs (max_concurrent={max_concurrent})")
    state["reasoning_trace"].append(
        f"[{datetime.now(timezone.utc).isoformat()}] Scrape: Racing to fetch {max_sources} sources from top {len(urls)} URLs"
    )

    try:
        scraped = await scraper.fetch_multiple(urls, max_concurrent=max_concurrent, min_results=max_sources)
        logger.info(f"[SCRAPE] Scraped {len(scraped)} items")

        scraped_dict = {s.url: s for s in scraped if s}
        max_scraped_content = settings.get("max_content_for_scraping", 5000)
        final_content = []

        for r in top_results:
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
                        "chunks": getattr(s, "chunks", []),
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
                        "chunks": [snippet],
                    }
                )
            
            if len(final_content) >= max_sources:
                break

        state["scraped_content"] = final_content

        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Scrape: Successfully extracted content from {len(scraped)} sources (took {time.perf_counter() - step_start:.2f}s)"
        )
    except Exception as e:
        logger.error(f"[SCRAPE] Error: {e}")
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Scrape: Error - {str(e)} (took {time.perf_counter() - step_start:.2f}s)"
        )

    return state


async def analyze_source(
    source: dict, query: str, llm, semaphore: asyncio.Semaphore, settings: dict
) -> List[dict]:
    """Analyze a single source and extract facts using dynamic chunks."""
    async with semaphore:
        chunks = source.get("chunks", [])
        if not chunks:
            logger.warning(f"[ANALYZER] No content for source: {source.get('url', 'unknown')}")
            return []

        # Format chunks with XML tags to drastically improve LLM attention ("Lost in the Middle" prevention)
        max_chunks = 4 # Increased to ensure we capture the main article body, not just headers/cookie banners
        processed_content = "\n\n".join([f"<chunk id={i+1}>\n{c}\n</chunk>" for i, c in enumerate(chunks[:max_chunks])])

        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS["analyzer"]},
            {
                "role": "user",
                "content": f"User question: {query}\n\nSource title: {source.get('title', 'Unknown')}\nSource URL: {source.get('url', '')}\n\nContent:\n{processed_content}\n\nExtract key facts highly relevant to the question. Format EXACTLY as: FACT | CATEGORY | CONFIDENCE",
            },
        ]

        async def _generate_facts():
            return await llm.generate(messages, temperature=0.3, max_tokens=2500)

        try:
            logger.info(f"[ANALYZER] Calling LLM for {source.get('url', 'unknown')[:30]}...")
            response = await retry_with_backoff(
                _generate_facts, max_retries=3, base_delay=2.0, exponential_base=2.0
            )
            
            logger.debug(
                f"[ANALYZER] LLM response: {response.content[:200] if response.content else 'EMPTY'}"
            )

            if not response.content or not response.content.strip():
                logger.warning(f"[ANALYZER] Empty response from LLM")
                return []

            facts = []
            captured_facts = False

            content = response.content.strip()
            import re
            content = re.sub(r'^```[\w]*\n', '', content)
            content = re.sub(r'\n```$', '', content)

            for line in content.split("\n"):
                line = line.strip().strip("-").strip("*").strip()
                if not line or "---" in line or line.upper().startswith("FACT |"):
                    continue
                if "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        fact_text = parts[0].strip()
                        if not fact_text or fact_text.upper() == "FACT":
                            continue
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
                                "fact": fact_text,
                                "category": parts[1].strip(),
                                "confidence": confidence,
                                "source_sentence": fact_text,
                            }
                        )
                        captured_facts = True
                elif len(line) > 20 and not line.lower().startswith(
                    ("here are", "sure", "these are", "extracted facts", "note:", "source:", "the key facts", "below are")
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
            return []


async def analyzer_node(state: AgentState) -> AgentState:
    """Extracts key facts from scraped content with parallel processing."""
    step_start = time.perf_counter()
    scraped = state.get("scraped_content", [])
    query = state["original_query"]
    deep_research = state.get("deep_research", False)
    settings = state.get("metadata", {}).get("agent_settings", get_agent_settings(deep_research))
    analysis_round = state.get("analysis_round", 0)

    if not scraped:
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Analyzer: No content to analyze (took {time.perf_counter() - step_start:.2f}s)"
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
        f"[{datetime.now(timezone.utc).isoformat()}] Analyzer: Extracted {len(facts)} facts (total: {len(all_facts)}) (took {time.perf_counter() - step_start:.2f}s)"
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
    step_start = time.perf_counter()
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
    fact_texts = [f"{i+1}. {f['fact']}" for i, f in enumerate(facts[:50])]
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["ranker"]},
        {
            "role": "user",
            "content": f"Query: {query}\n\nFacts:\n" + "\n".join(fact_texts),
        },
    ]

    try:
        response = await call_llm_with_retry(
            messages, llm_config, temperature=0.0, max_tokens=50
        )
        ranked_text = response.content.strip()
        
        import re
        indices = [int(idx) for idx in re.findall(r'\d+', ranked_text)]
        
        ranked_facts = []
        for idx in set(indices):
            if 1 <= idx <= len(facts[:50]):
                ranked_facts.append(facts[idx-1])
        
        if ranked_facts:
            logger.info(f"[RANKER] Kept {len(ranked_facts)} relevant facts")
            state["extracted_facts"] = ranked_facts
        
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Ranker: Reduced to {len(state['extracted_facts'])} high-relevance facts (took {time.perf_counter() - step_start:.2f}s)"
        )
    except Exception as e:
        logger.error(f"[RANKER] Error: {e}")
        
    return state


async def synthesizer_node(state: AgentState) -> AgentState:
    """Generates final answer with citations."""
    step_start = time.perf_counter()
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
        logger.warning("[SYNTHESIZER] No content to synthesize. Proceeding with internal knowledge.")
        state["reasoning_trace"].append(
            f"[{datetime.now(timezone.utc).isoformat()}] Synthesizer: No web content extracted. Falling back to internal knowledge."
        )

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
            f"<source index=\"{i}\">\nTitle: {source.get('title', 'Unknown')}\nURL: {source.get('url', '')}\nSnippet: {source.get('content', '')[:max_content_for_synth]}\n</source>"
        )

    context = "<raw_sources>\n" + "\n".join(context_parts) + "\n</raw_sources>"

    facts_context = ""
    if facts:
        facts_list = []
        for j, fact in enumerate(facts[:30], 1):
            source_title = fact.get("source_title", "")
            facts_list.append(f"- {fact.get('fact', '')} (Source: {source_title})")
        facts_context = "<highly_relevant_facts>\n" + "\n".join(facts_list) + "\n</highly_relevant_facts>\n\n"

    intent = state.get("query_intent", "general")
    prompt_key = f"synthesizer_{intent}"
    base_prompt = SYSTEM_PROMPTS.get(prompt_key, SYSTEM_PROMPTS["synthesizer"])

    if agent_config.get("rag_mode") == "strict":
        base_prompt += (
            "\n\n🛡️ STRICT RAG MODE ENABLED:\n"
            "1. You MUST rely EXCLUSIVELY on the provided sources.\n"
            "2. DO NOT use your internal baseline knowledge to add new facts.\n"
            "3. Adopt an objective, clinical, and strictly data-driven tone. Act as a neutral intelligence reporter.\n"
        )
    else:
        base_prompt += (
            "\n\n🧠 CREATIVE RAG MODE ENABLED:\n"
            "1. You are actively encouraged to blend the scraped sources with your own deep expert knowledge.\n"
            "2. Add historical context, future predictions, thought leadership, and broader industry insights.\n"
            "3. Adopt an engaging, visionary, and analytical tone."
        )

    if state.get("next_step") == "clarify":
        state["final_answer"] = "Your query was too vague or ambiguous. Could you please provide more specific details about what you would like me to research?"
        state["status"] = "complete"
        state["reasoning_trace"].append(f"[{datetime.now(timezone.utc).isoformat()}] Synthesizer: Requested clarification from user")
        return state

    if state.get("next_step") == "direct":
        messages = [
            {"role": "system", "content": f"{base_prompt}\n\nAnswer the user's question directly and concisely based on your internal knowledge. Do not use citations since no web research was performed."},
            {"role": "user", "content": query},
        ]
    else:
        user_payload = (
            f"Here is the research material:\n\n"
            f"{facts_context}"
            f"{context}\n\n"
            f"User question: {query}\n\n"
            f"CRITICAL INSTRUCTIONS:\n"
            f"1. Generate a comprehensive answer to the user's question.\n"
            f"2. You MUST use the [index] from the <raw_sources> to cite your claims (e.g., [1], [2]).\n"
            f"3. Pay special attention to the <highly_relevant_facts> as they contain the highest-signal information."
        )
        messages = [
            {"role": "system", "content": base_prompt},
            {
                "role": "user",
                "content": user_payload,
            },
        ]
    
    if state.get("critiques") and state.get("reflexion_steps", 0) > 0:
        latest_critique = state["critiques"][-1]
        messages[1]["content"] += f"\n\nIMPORTANT: YOUR PREVIOUS ANSWER HAD THE FOLLOWING ISSUES. PLEASE FIX THEM IN THIS REVISION:\n{latest_critique}"
        logger.info("[SYNTHESIZER] Injecting critique for reflexion loop.")

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
            stream_cb = agent_config.get("stream_callback")
            async for chunk in llm.stream_generate(
                messages,
                temperature=agent_config.get("temperature", 0.7),
                max_tokens=agent_config.get("max_tokens", 4000),
            ):
                full_response += chunk
                if stream_cb:
                    if asyncio.iscoroutinefunction(stream_cb):
                        await stream_cb(chunk)
                    else:
                        stream_cb(chunk)
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
    step_start = time.perf_counter()
    answer = state.get("final_answer", "")
    facts = state.get("extracted_facts", [])
    llm_config = get_llm_config_from_state(state)
    agent_config = state.get("metadata", {}).get("agent_config", {})

    if not answer or not facts:
        state["status"] = "complete"
        return state

    logger.info("[VERIFIER] Verifying answer accuracy...")
    state["reasoning_trace"].append(
        f"[{datetime.now(timezone.utc).isoformat()}] Verifier: Checking for hallucinations or inaccuracies"
    )

    fact_texts = [f"- {f['fact']}" for f in facts[:30]]
    verifier_prompt = SYSTEM_PROMPTS.get("verifier_strict") if agent_config.get("rag_mode") == "strict" else SYSTEM_PROMPTS["verifier"]
    
    messages = [
        {"role": "system", "content": verifier_prompt},
        {
            "role": "user",
            "content": f"Facts:\n" + "\n".join(fact_texts) + f"\n\nAnswer:\n{answer}",
        },
    ]

    try:
        response = await call_llm_with_retry(
            messages, llm_config, temperature=0.1, max_tokens=4000
        )
        content = response.content.strip()
        
        # Clean <think> tags for reasoning models that output thoughts before the final answer
        clean_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        
        clean_upper = clean_content.upper()
        is_critique = False
        
        if "CRITIQUE:" in clean_upper[:50] or clean_upper.startswith("CRITIQUE"):
            is_critique = True
        if "PASS" in clean_upper[:30] and not clean_upper.startswith("CRITIQUE"):
            is_critique = False
            
        if is_critique:
            logger.info("[VERIFIER] Hallucinations detected. Triggering reflexion.")
            state["critiques"] = state.get("critiques", []) + [clean_content]
            state["reflexion_steps"] = state.get("reflexion_steps", 0) + 1
            state["status"] = "pending_reflexion"
            state["reasoning_trace"].append(f"[{datetime.now(timezone.utc).isoformat()}] Verifier: Critique generated. Triggering reflexion loop. (took {time.perf_counter() - step_start:.2f}s)")
        else:
            logger.info("[VERIFIER] Answer verified as accurate")
            state["status"] = "complete"
            state["reasoning_trace"].append(f"[{datetime.now(timezone.utc).isoformat()}] Verifier: Answer verified against source facts (took {time.perf_counter() - step_start:.2f}s)")
    except Exception as e:
        logger.error(f"[VERIFIER] Error: {e}")
        state["status"] = "complete"
        
    return state
