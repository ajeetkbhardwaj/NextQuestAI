import os
import asyncio
import logging
import time
from typing import Optional, Callable, Any, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    component: str
    status: HealthStatus
    latency_ms: float
    message: str = ""
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    async def call(self, fn: Callable, *args, **kwargs):
        async with self._lock:
            if self._state == "open":
                if (
                    self._last_failure_time
                    and time.time() - self._last_failure_time > self.recovery_timeout
                ):
                    logger.info(f"CircuitBreaker: transitioning open -> half-open")
                    self._state = "half-open"
                    self._failure_count = 0
                else:
                    raise Exception(f"CircuitBreaker is open, call rejected")

        try:
            result = await fn(*args, **kwargs)
            async with self._lock:
                if self._state == "half-open":
                    logger.info(f"CircuitBreaker: half-open -> closed")
                    self._state = "closed"
                    self._failure_count = 0
            return result
        except self.expected_exception as e:
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()
                if self._failure_count >= self.failure_threshold:
                    logger.warning(f"CircuitBreaker: closed -> open (failures={self._failure_count})")
                    self._state = "open"
            raise


class FallbackChain:
    def __init__(self, providers: list[tuple[str, Callable]]):
        self.providers = providers

    async def execute(self, *args, **kwargs):
        errors = []
        for name, fn in self.providers:
            try:
                logger.info(f"[FallbackChain] Trying provider: {name}")
                return await fn(*args, **kwargs)
            except Exception as e:
                logger.warning(f"[FallbackChain] {name} failed: {e}")
                errors.append(f"{name}: {str(e)}")
                continue
        raise Exception(f"All providers failed: {'; '.join(errors)}")


class AdaptiveConcurrency:
    def __init__(self, initial: int = 3, min_val: int = 1, max_val: int = 10):
        self.current = initial
        self.min = min_val
        self.max = max_val
        self._successes = 0
        self._failures = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> asyncio.Semaphore:
        async with self._lock:
            sem = asyncio.Semaphore(self.current)
        return sem

    def record_success(self):
        self._successes += 1
        if self._successes >= 5 and self.current < self.max:
            self.current = min(self.max, self.current + 1)
            self._successes = 0
            logger.debug(f"[Concurrency] Increased to {self.current}")

    def record_failure(self):
        self._failures += 1
        if self._failures >= 2 and self.current > self.min:
            self.current = max(self.min, self.current - 1)
            self._failures = 0
            logger.debug(f"[Concurrency] Decreased to {self.current}")


class PersistentCache:
    def __init__(self, cache_dir: str = ".cache", max_age_seconds: float = 3600.0):
        self.cache_dir = cache_dir
        self.max_age = max_age_seconds
        self._memory: dict[str, tuple[Any, float]] = {}
        self._hits = 0
        self._misses = 0

    def _cache_path(self, key: str) -> str:
        import hashlib
        hashed = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{hashed}.json")

    async def get(self, key: str) -> Optional[Any]:
        if key in self._memory:
            value, timestamp = self._memory[key]
            if time.time() - timestamp < self.max_age:
                self._hits += 1
                return value
            else:
                del self._memory[key]

        cache_file = self._cache_path(key)
        if os.path.exists(cache_file):
            try:
                import json
                stat = os.stat(cache_file)
                if time.time() - stat.st_mtime < self.max_age:
                    with open(cache_file) as f:
                        value = json.load(f)
                    self._memory[key] = (value, time.time())
                    self._hits += 1
                    return value
                else:
                    os.remove(cache_file)
            except Exception as e:
                logger.debug(f"[Cache] Failed to read cache file: {e}")

        self._misses += 1
        return None

    async def set(self, key: str, value: Any):
        self._memory[key] = (value, time.time())
        try:
            import json
            os.makedirs(self.cache_dir, exist_ok=True)
            cache_file = self._cache_path(key)
            with open(cache_file, "w") as f:
                json.dump(value, f)
        except Exception as e:
            logger.debug(f"[Cache] Failed to write cache file: {e}")

    def stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {"hits": self._hits, "misses": self._misses, "hit_rate_pct": round(hit_rate, 1)}


class HealthMonitor:
    def __init__(self):
        self._checks: dict[str, HealthCheck] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        component: str,
        check_fn: Callable[[], Awaitable[HealthCheck]],
    ):
        async with self._lock:
            self._checks[component] = check_fn

    async def run_check(self, component: str) -> HealthCheck:
        if component not in self._checks:
            return HealthCheck(component, HealthStatus.UNHEALTHY, 0, "Unknown component")
        try:
            start = time.perf_counter()
            result = await self._checks[component]()
            latency = (time.perf_counter() - start) * 1000
            result.latency_ms = round(latency, 1)
            return result
        except Exception as e:
            return HealthCheck(component, HealthStatus.UNHEALTHY, 0, str(e))

    async def run_all_checks(self) -> dict[str, HealthCheck]:
        results = {}
        for component in list(self._checks.keys()):
            results[component] = await self.run_check(component)
        return results

    def get_overall_status(self, checks: dict[str, HealthCheck]) -> HealthStatus:
        if not checks:
            return HealthStatus.UNHEALTHY
        statuses = [c.status for c in checks.values()]
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        if any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY


_global_health_monitor = HealthMonitor()


def get_health_monitor() -> HealthMonitor:
    return _global_health_monitor
