import os
import asyncio
import logging
from typing import List, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_TIMEOUT = 30.0
DEFAULT_MAX_RESULTS = 5

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        DDGS_AVAILABLE = True
    except ImportError:
        DDGS_AVAILABLE = False
        logger.warning("DuckDuckGo search not available (ddgs package not installed)")


@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    score: float
    published_date: Optional[str] = None


class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> List[SearchResult]:
        pass


class TavilySearch(SearchProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")

    async def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> List[SearchResult]:
        if not self.api_key:
            logger.error("[Tavily] API key not configured")
            return []

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_SEARCH_TIMEOUT) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "query": query,
                        "max_results": max_results,
                        "include_answer": True,
                        "include_raw_content": False,
                    },
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("results", []):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        score=item.get("score", 0.0),
                    )
                )
            logger.info(f"[Tavily] Found {len(results)} results for query: {query[:50]}")
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"[Tavily] HTTP error {e.response.status_code}: {e}")
            return []
        except httpx.RequestError as e:
            logger.error(f"[Tavily] Request error: {e}")
            return []
        except Exception as e:
            logger.error(f"[Tavily] Unexpected error: {e}", exc_info=True)
            return []


class DuckDuckGoSearch(SearchProvider):
    def __init__(self):
        pass

    async def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> List[SearchResult]:
        if not DDGS_AVAILABLE:
            logger.warning("[DuckDuckGo] DDGS not available")
            return []

        def _sync_search():
            results = []
            try:
                with DDGS() as ddgs:
                    for i, r in enumerate(ddgs.text(query, max_results=max_results)):
                        results.append(
                            {
                                "title": r.get("title", ""),
                                "url": r.get("href", ""),
                                "content": r.get("body", ""),
                                "score": 1.0 - (i * 0.1),
                            }
                        )
            except Exception as e:
                logger.error(f"[DuckDuckGo] Search error: {e}")
                return []
            return results

        try:
            raw_results = await asyncio.get_running_loop().run_in_executor(None, _sync_search)

            results = [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                )
                for r in raw_results
            ]
            logger.info(f"[DuckDuckGo] Found {len(results)} results for query: {query[:50]}")
            return results

        except Exception as e:
            logger.error(f"[DuckDuckGo] Unexpected error: {e}", exc_info=True)
            return []


class SerperSearch(SearchProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPER_API_KEY")

    async def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> List[SearchResult]:
        if not self.api_key:
            logger.error("[Serper] API key not configured")
            return []

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_SEARCH_TIMEOUT) as client:
                response = await client.post(
                    "https://google.serper.dev/search",
                    json={"q": query, "num": max_results},
                    headers={
                        "X-API-KEY": self.api_key,
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("organic", []):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        content=item.get("snippet", ""),
                        score=item.get("position", 0) / 10,
                    )
                )
            logger.info(f"[Serper] Found {len(results)} results for query: {query[:50]}")
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"[Serper] HTTP error {e.response.status_code}: {e}")
            return []
        except httpx.RequestError as e:
            logger.error(f"[Serper] Request error: {e}")
            return []
        except Exception as e:
            logger.error(f"[Serper] Unexpected error: {e}", exc_info=True)
            return []


class SearchManager:
    def __init__(self):
        self.providers = {
            "tavily": TavilySearch(),
            "duckduckgo": DuckDuckGoSearch(),
            "serper": SerperSearch(),
        }

    async def search(
        self, query: str, provider: str = "duckduckgo", max_results: int = DEFAULT_MAX_RESULTS
    ) -> List[SearchResult]:
        if provider in self.providers:
            results = await self.providers[provider].search(query, max_results)
            if results:
                return results
            logger.warning(f"[SearchManager] Provider {provider} returned no results, trying fallback")

        if provider != "duckduckgo":
            fallback_results = await self.providers["duckduckgo"].search(query, max_results)
            if fallback_results:
                return fallback_results

        logger.error("[SearchManager] All search providers returned empty results")
        return []


search_manager = SearchManager()