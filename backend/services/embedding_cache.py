"""
services/embedding_cache.py — In-memory cache for ICD embeddings.

Prevents re-generating embeddings for the same ICD code within a session
or across requests in the same process lifetime.

Phase 4 upgrade: Replace dict with Redis for multi-process caching.
"""
from typing import Optional
from logger import get_logger

log = get_logger(__name__)

# Simple in-memory cache: { icd_code: embedding_vector (list[float]) }
_cache: dict[str, list[float]] = {}
_hit_count: int = 0
_miss_count: int = 0


def get_cached_embedding(icd_code: str) -> Optional[list[float]]:
    """Returns cached embedding for an ICD code, or None if not cached."""
    global _hit_count, _miss_count
    if icd_code in _cache:
        _hit_count += 1
        log.debug("embedding_cache_hit", icd_code=icd_code, hit_count=_hit_count)
        return _cache[icd_code]
    _miss_count += 1
    return None


def set_cached_embedding(icd_code: str, embedding: list[float]) -> None:
    """Stores an embedding in the cache."""
    _cache[icd_code] = embedding
    log.debug("embedding_cache_set", icd_code=icd_code, cache_size=len(_cache))


def cache_stats() -> dict:
    """Returns cache performance stats."""
    total = _hit_count + _miss_count
    return {
        "cache_size": len(_cache),
        "hits": _hit_count,
        "misses": _miss_count,
        "hit_rate": round(_hit_count / total, 3) if total > 0 else 0.0,
    }


def clear_cache() -> None:
    """Clears the embedding cache (e.g. on shutdown or test reset)."""
    global _cache, _hit_count, _miss_count
    _cache = {}
    _hit_count = 0
    _miss_count = 0
    log.info("embedding_cache_cleared")
