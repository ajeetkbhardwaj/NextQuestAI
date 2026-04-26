import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper import ContentScraper, ScrapedContent


class TestContentScraper:
    def test_scraped_content_structure(self):
        content = ScrapedContent(
            url="https://example.com",
            title="Test Article",
            content="Full article text here",
            excerpt="Short excerpt",
            author="John Doe",
            published_date="2024-01-15",
            fetched_at="2024-01-20T10:00:00Z",
        )
        assert content.url == "https://example.com"
        assert content.title == "Test Article"
        assert content.author == "John Doe"

    def test_scraped_content_optional_fields(self):
        content = ScrapedContent(
            url="https://example.com",
            title="Test",
            content="Content",
            excerpt="Excerpt",
            author=None,
            published_date=None,
            fetched_at="2024-01-20T10:00:00Z",
        )
        assert content.author is None
        assert content.published_date is None


class TestScraperAsync:
    @pytest.mark.asyncio
    async def test_scraper_context_manager(self):
        scraper = ContentScraper(timeout=10.0)
        async with scraper:
            assert scraper._session is not None

    @pytest.mark.asyncio
    async def test_scraper_open_session(self):
        scraper = ContentScraper()
        scraper.open_session()
        assert scraper._session is not None
        await scraper.close()
