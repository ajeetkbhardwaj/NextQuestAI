import asyncio
import logging
import time
from typing import TypeVar, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from collections import OrderedDict
from functools import wraps
import hashlib

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_CACHE_MAX_SIZE = 1000
DEFAULT_CACHE_TTL = 1800


async def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retriable_exceptions: tuple = (Exception,),
) -> T:
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            return func()
        except retriable_exceptions as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (exponential_base**attempt), max_delay)
                logger.warning(
                    f"Retry attempt {attempt + 1}/{max_retries} after {delay:.1f}s "
                    f"due to: {e}"
                )
                await asyncio.sleep(delay)
                continue
            raise last_exception


@dataclass
class CacheEntry:
    value: Any
    timestamp: datetime
    ttl_seconds: int

    def is_expired(self) -> bool:
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds() > self.ttl_seconds


class InMemoryCache:
    def __init__(
        self,
        default_ttl: int = DEFAULT_CACHE_TTL,
        max_size: int = DEFAULT_CACHE_MAX_SIZE,
    ):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    def _make_key(self, *args, **kwargs) -> str:
        key_str = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_str.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    def get_sync(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired():
            del self._cache[key]
            self._misses += 1
            return None
        self._cache.move_to_end(key)
        self._hits += 1
        return entry.value

    def set_sync(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if key in self._cache:
            del self._cache[key]
        elif len(self._cache) >= self.max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"Evicted oldest cache entry: {oldest_key[:16]}...")

        self._cache[key] = CacheEntry(
            value=value,
            timestamp=datetime.now(timezone.utc),
            ttl_seconds=ttl or self.default_ttl,
        )
        self._cache.move_to_end(key)

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"Evicted oldest cache entry: {oldest_key[:16]}...")

            self._cache[key] = CacheEntry(
                value=value,
                timestamp=datetime.now(timezone.utc),
                ttl_seconds=ttl or self.default_ttl,
            )
            self._cache.move_to_end(key)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    async def cleanup_expired(self) -> int:
        async with self._lock:
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
            return len(expired_keys)

    def start_background_cleanup(self, interval_seconds: int = 300) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.debug("No running event loop, skipping background cleanup start")
            return

        async def _cleanup_loop():
            while True:
                await asyncio.sleep(interval_seconds)
                try:
                    await self.cleanup_expired()
                except Exception as e:
                    logger.error(f"Background cache cleanup failed: {e}")

        self._cleanup_task = asyncio.create_task(_cleanup_loop())

    def ensure_cleanup_started(self, interval_seconds: int = 300) -> None:
        if self._cleanup_task is None:
            self.start_background_cleanup(interval_seconds)

    def stop_background_cleanup(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._cache)


search_cache = InMemoryCache(default_ttl=DEFAULT_CACHE_TTL, max_size=DEFAULT_CACHE_MAX_SIZE)