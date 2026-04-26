import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.search import SearchResult, DuckDuckGoSearch, TavilySearch
from src.performance import CircuitBreaker, AdaptiveConcurrency, PersistentCache, HealthMonitor, HealthStatus, FallbackChain
from src.performance import CircuitBreaker, AdaptiveConcurrency, PersistentCache, HealthMonitor, HealthStatus


class TestSearchResult:
    def test_search_result_creation(self):
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            content="Test content",
            score=0.95,
            published_date="2024-01-01",
        )
        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.score == 0.95


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_success(self):
        cb = CircuitBreaker(failure_threshold=3)

        async def success():
            return "success"

        result = await cb.call(success)
        assert result == "success"
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=2)

        async def fail():
            raise Exception("test error")

        for _ in range(2):
            try:
                await cb.call(fail)
            except:
                pass

        assert cb.state == "open"


class TestAdaptiveConcurrency:
    def test_initial_value(self):
        ac = AdaptiveConcurrency(initial=3, min_val=1, max_val=10)
        assert ac.current == 3

    def test_increase_on_success(self):
        ac = AdaptiveConcurrency(initial=3, min_val=1, max_val=10)
        for _ in range(5):
            ac.record_success()
        assert ac.current == 4

    def test_decrease_on_failure(self):
        ac = AdaptiveConcurrency(initial=3, min_val=1, max_val=10)
        for _ in range(2):
            ac.record_failure()
        assert ac.current == 2

    def test_respect_max(self):
        ac = AdaptiveConcurrency(initial=9, min_val=1, max_val=10)
        for _ in range(10):
            ac.record_success()
        assert ac.current == 10

    def test_respect_min(self):
        ac = AdaptiveConcurrency(initial=2, min_val=1, max_val=10)
        for _ in range(5):
            ac.record_failure()
        assert ac.current == 1


class TestPersistentCache:
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        cache = PersistentCache(max_age_seconds=3600)
        await cache.set("test_key", {"data": "value"})
        result = await cache.get("test_key")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        cache = PersistentCache(max_age_seconds=3600)
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        cache = PersistentCache(max_age_seconds=3600)
        await cache.set("key1", "value1")
        await cache.get("key1")
        await cache.get("key2")
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1


class TestHealthMonitor:
    @pytest.mark.asyncio
    async def test_register_and_run_check(self):
        monitor = HealthMonitor()

        async def mock_check():
            from src.performance import HealthCheck
            return HealthCheck("test_component", HealthStatus.HEALTHY, 10.0, "OK")

        await monitor.register("test_component", mock_check)
        result = await monitor.run_check("test_component")
        assert result.component == "test_component"
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_get_overall_status_healthy(self):
        monitor = HealthMonitor()
        from src.performance import HealthCheck
        checks = {
            "comp1": HealthCheck("comp1", HealthStatus.HEALTHY, 5.0),
            "comp2": HealthCheck("comp2", HealthStatus.HEALTHY, 5.0),
        }
        status = monitor.get_overall_status(checks)
        assert status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_get_overall_status_degraded(self):
        monitor = HealthMonitor()
        from src.performance import HealthCheck
        checks = {
            "comp1": HealthCheck("comp1", HealthStatus.HEALTHY, 5.0),
            "comp2": HealthCheck("comp2", HealthStatus.DEGRADED, 5.0),
        }
        status = monitor.get_overall_status(checks)
        assert status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_get_overall_status_unhealthy(self):
        monitor = HealthMonitor()
        from src.performance import HealthCheck
        checks = {
            "comp1": HealthCheck("comp1", HealthStatus.HEALTHY, 5.0),
            "comp2": HealthCheck("comp2", HealthStatus.UNHEALTHY, 5.0),
        }
        status = monitor.get_overall_status(checks)
        assert status == HealthStatus.UNHEALTHY
