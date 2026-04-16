"""
Exact-match LRU cache for RAG responses (same normalized query + same RAG fingerprint).
Thread-safe for concurrent FastAPI workers (single process).
"""
from __future__ import annotations

import copy
import hashlib
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional


def normalize_query(text: str) -> str:
    """Lowercase, trim, collapse internal whitespace for exact-match keys."""
    return " ".join((text or "").strip().split()).lower()


def build_cache_key(
    query: str,
    top_k: int,
    cfg: Dict[str, Any],
    source: Optional[str] = None,
) -> str:
    """
    Stable key for exact response reuse. Includes anything that changes retrieval or generation.
    """
    norm = normalize_query(query)
    parts = [
        norm,
        str(top_k),
        str(source or ""),
        str(cfg.get("ollama_model", "")),
        str(cfg.get("ollama_think", True)),
        str(cfg.get("collection_name", "")),
        str(cfg.get("embedding_model_name", "")),
        str(cfg.get("system_prompt", "")),
        str(cfg.get("response_cache_version", "1")),
    ]
    raw = "\x1f".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ExactResponseCache:
    """In-process LRU cache keyed by build_cache_key output."""

    def __init__(self, max_entries: int) -> None:
        self._max = max(1, int(max_entries))
        self._data: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return copy.deepcopy(self._data[key])

    def set(self, key: str, value: Dict[str, Any]) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
            self._data[key] = copy.deepcopy(value)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_cache: Optional[ExactResponseCache] = None
_cache_max_entries: int = -1


def get_response_cache(max_entries: int) -> ExactResponseCache:
    """Return process-wide cache, recreating if max_entries changes."""
    global _cache, _cache_max_entries
    if _cache is None or max_entries != _cache_max_entries:
        _cache = ExactResponseCache(max_entries)
        _cache_max_entries = max_entries
    return _cache


def clear_response_cache() -> None:
    """Clear all entries (e.g. tests)."""
    global _cache
    if _cache is not None:
        _cache.clear()
