import os
import asyncio
import logging
from typing import List, Optional, Any
import json
from datetime import datetime, timezone
from dataclasses import dataclass

import httpx
import trafilatura
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

logger = logging.getLogger(__name__)

DEFAULT_SCRAPE_TIMEOUT = 30.0

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
}


@dataclass
class ScrapedContent:
    url: str
    title: str
    content: str
    excerpt: str
    author: Optional[str]
    published_date: Optional[str]
    fetched_at: str


class ContentScraper:
    def __init__(self, timeout: float = DEFAULT_SCRAPE_TIMEOUT):
        self.timeout = timeout
        self._session: Optional[httpx.AsyncClient] = None

    def _create_client(self):
        if CURL_CFFI_AVAILABLE:
            return curl_requests.AsyncSession(
                impersonate="chrome124",
                timeout=self.timeout,
                headers={"Referer": "https://www.google.com/"},
            )
        else:
            return httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers=DEFAULT_HEADERS,
            )

    async def __aenter__(self):
        self._session = self._create_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def open_session(self) -> None:
        if self._session is None:
            self._session = self._create_client()

    async def close(self) -> None:
        if self._session:
            if hasattr(self._session, "aclose"):
                await self._session.aclose()
            elif hasattr(self._session, "close"):
                if asyncio.iscoroutinefunction(self._session.close):
                    await self._session.close()
                else:
                    self._session.close()
            self._session = None

    @property
    def session(self) -> Any:
        if self._session is None:
            raise RuntimeError("ContentScraper must be used as context manager or call open_session() first")
        return self._session

    async def fetch(self, url: str, client: Any = None) -> Optional[ScrapedContent]:
        use_temp_client = False
        if client is None:
            if self._session:
                client = self._session
            else:
                client = self._create_client()
                use_temp_client = True
        try:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                output_format="json",
            )

            data = {}
            if extracted:
                if isinstance(extracted, dict):
                    data = extracted
                else:
                    try:
                        data = json.loads(extracted)
                    except Exception:
                        pass

            content = data.get("text", "") or ""
            title = data.get("title", "") or ""

            if not content or len(content) < 50:
                content = await self._fallback_extract(html)
            if not title:
                title = await self._extract_title(html)

            if not content:
                logger.warning(f"[SCRAPE] Failed to extract content from: {url}")
                return None

            excerpt = content[:300] + "..." if len(content) > 300 else content

            return ScrapedContent(
                url=url,
                title=title,
                content=content,
                excerpt=excerpt,
                author=data.get("author"),
                published_date=data.get("date"),
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as e:
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            
            if status_code:
                if status_code in (401, 403, 406, 429, 503):
                    logger.warning(f"[SCRAPE] HTTP {status_code} for {url}. Trying Jina Reader fallback...")
                    fallback = await self._jina_fallback(url, client)
                    if fallback:
                        return fallback
                logger.warning(f"[SCRAPE] HTTP error {status_code} for {url}")
                return None

            logger.error(f"[SCRAPE] Request error for {url}: {e}")
            logger.warning(f"[SCRAPE] Connection failed. Trying Jina Reader fallback...")
            fallback = await self._jina_fallback(url, client)
            if fallback:
                return fallback
            return None
        finally:
            if use_temp_client:
                if hasattr(client, "aclose"):
                    await client.aclose()
                elif hasattr(client, "close"):
                    if asyncio.iscoroutinefunction(client.close):
                        await client.close()
                    else:
                        client.close()

    async def _jina_fallback(self, url: str, client: Any) -> Optional[ScrapedContent]:
        try:
            fallback_response = await client.get(
                f"https://r.jina.ai/{url}",
                headers={"Accept": "text/plain"}
            )
            fallback_response.raise_for_status()
            content = fallback_response.text
            if content and len(content) > 50:
                title = "Extracted via Fallback"
                for line in content.split('\n')[:5]:
                    if line.startswith('Title: '):
                        title = line.replace('Title: ', '').strip()
                        break
                excerpt = content[:300] + "..." if len(content) > 300 else content
                return ScrapedContent(
                    url=url,
                    title=title,
                    content=content,
                    excerpt=excerpt,
                    author=None,
                    published_date=None,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
        except Exception as fallback_e:
            status_code = getattr(getattr(fallback_e, "response", None), "status_code", None)
            if status_code:
                logger.warning(f"[SCRAPE] Jina Reader fallback blocked for {url}: HTTP {status_code}")
            else:
                logger.warning(f"[SCRAPE] Jina Reader fallback also failed for {url}: {fallback_e}")
        return None

    async def _extract_title(self, html: str) -> str:
        try:
            soup = BeautifulSoup(html, "lxml")
            title_tag = soup.find("title")
            if title_tag:
                return title_tag.get_text(strip=True)
            h1 = soup.find("h1")
            if h1:
                return h1.get_text(strip=True)
        except Exception as e:
            logger.debug(f"[SCRAPE] Title extraction error: {e}")
        return "Untitled"

    async def _fallback_extract(self, html: str) -> str:
        try:
            soup = BeautifulSoup(html, "lxml")
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            text = soup.get_text(separator=" ")
            import re
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:15000]
        except Exception as e:
            logger.debug(f"[SCRAPE] Fallback extraction error: {e}")
            return ""

    async def fetch_multiple(
        self, urls: List[str], max_concurrent: int = 5
    ) -> List[ScrapedContent]:
        semaphore = asyncio.Semaphore(max_concurrent)

        client = self._session
        owns_client = False
        if not client:
            client = self._create_client()
            owns_client = True

        try:
            async def fetch_with_limit(url: str):
                async with semaphore:
                    return await self.fetch(url, client=client)

            tasks = [fetch_with_limit(url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            valid_results = [r for r in results if isinstance(r, ScrapedContent) and r.content]
            logger.info(f"[SCRAPE] Successfully scraped {len(valid_results)}/{len(urls)} URLs")
            return valid_results
        finally:
            if owns_client:
                if hasattr(client, "aclose"):
                    await client.aclose()
                elif hasattr(client, "close"):
                    if asyncio.iscoroutinefunction(client.close):
                        await client.close()
                    else:
                        client.close()


scraper = ContentScraper()