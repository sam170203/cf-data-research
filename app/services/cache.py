from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("cache")

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

MEMO_CACHE: dict[str, Any] = {}
CACHE_STATS: dict[str, dict[str, int]] = {}


def _stats(cache_key: str) -> dict[str, int]:
    if cache_key not in CACHE_STATS:
        CACHE_STATS[cache_key] = {"hits": 0, "misses": 0}
    return CACHE_STATS[cache_key]


def get_cache_stats() -> dict[str, Any]:
    total_hits = 0
    total_misses = 0
    details = {}
    for key, stats in CACHE_STATS.items():
        total_hits += stats["hits"]
        total_misses += stats["misses"]
        details[key] = dict(stats)
    total = total_hits + total_misses
    return {
        "total_hits": total_hits,
        "total_misses": total_misses,
        "overall_hit_rate": round(total_hits / total * 100, 1) if total > 0 else 0,
        "details": details,
    }


class FileCache:
    def __init__(self, name: str, ttl_seconds: int = 86400):
        self.name = name
        self.ttl = ttl_seconds
        self.path = CACHE_DIR / f"{name}.json"

    def get(self) -> Any | None:
        stats = _stats(self.name)
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text())
                fetched_at = data.get("_fetched_at", 0)
                age = time.time() - fetched_at
                if age < self.ttl:
                    stats["hits"] += 1
                    logger.debug("FileCache HIT %s (age=%.1fs)", self.name, age)
                    return data.get("data")
                else:
                    logger.info("FileCache EXPIRED %s (age=%.1fs > ttl=%ds)", self.name, age, self.ttl)
        except Exception as e:
            logger.warning("FileCache read error %s: %s", self.name, e)
        stats["misses"] += 1
        return None

    def set(self, data: Any) -> None:
        payload = {
            "_fetched_at": time.time(),
            "_timestamp": datetime.now(UTC).isoformat(),
            "data": data,
        }
        try:
            self.path.write_text(json.dumps(payload, default=str))
            logger.info("FileCache STORE %s (%d bytes)", self.name, self.path.stat().st_size)
        except Exception as e:
            logger.warning("FileCache write error %s: %s", self.name, e)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
            logger.info("FileCache CLEAR %s", self.name)


class MemoryCache:
    def __init__(self, name: str, ttl_seconds: int = 3600):
        self.name = name
        self.ttl = ttl_seconds

    def get(self) -> Any | None:
        stats = _stats(f"mem_{self.name}")
        entry = MEMO_CACHE.get(self.name)
        if entry is not None:
            age = time.time() - entry["_ts"]
            if age < self.ttl:
                stats["hits"] += 1
                return entry["data"]
            else:
                del MEMO_CACHE[self.name]
        stats["misses"] += 1
        return None

    def set(self, data: Any) -> None:
        MEMO_CACHE[self.name] = {"data": data, "_ts": time.time()}


def cached(
    cache_key: str,
    file_ttl: int = 86400,
    mem_ttl: int = 3600,
) -> Callable:
    def decorator(fn: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            mem = MemoryCache(cache_key, mem_ttl)
            cached = mem.get()
            if cached is not None:
                return cached

            fc = FileCache(cache_key, file_ttl)
            cached = fc.get()
            if cached is not None:
                mem.set(cached)
                return cached

            result = await fn(*args, **kwargs)
            if result:
                mem.set(result)
                fc.set(result)
            return result
        return wrapper
    return decorator
