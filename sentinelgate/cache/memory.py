"""In-memory semantic and exact match cache with vector cosine similarity."""

import hashlib
import re
import time
from typing import Any

import numpy as np

from sentinelgate.cache.base import BaseCache


def _compute_embedding_vector(text: str, dim: int = 128) -> np.ndarray:
    """Compute deterministic, L2-normalized pseudo-embedding using n-gram hashing trick.

    Provides fast, local, sub-millisecond semantic representation without requiring heavy ML models.
    """
    tokens = re.findall(r"\b\w+\b", text.lower())
    if not tokens:
        return np.zeros(dim, dtype=np.float32)

    vec = np.zeros(dim, dtype=np.float32)
    # 1-grams and 2-grams
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16) % dim
        vec[h] += 1.0

    for i in range(len(tokens) - 1):
        bigram = f"{tokens[i]}_{tokens[i + 1]}"
        h = int(hashlib.md5(bigram.encode()).hexdigest(), 16) % dim
        vec[h] += 1.5

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


class CacheEntry:
    """Represents a cached response with prompt embedding and timestamp."""

    def __init__(
        self,
        prompt: str,
        model: str,
        response: dict[str, Any],
        embedding: np.ndarray,
        ttl_seconds: int = 3600,
    ):
        self.prompt = prompt
        self.model = model
        self.response = response
        self.embedding = embedding
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class InMemorySemanticCache(BaseCache):
    """High-performance in-memory cache supporting both exact hashing and semantic cosine similarity."""

    def __init__(
        self,
        similarity_threshold: float = 0.92,
        default_ttl_seconds: int = 3600,
        max_entries: int = 1000,
    ):
        self.similarity_threshold = similarity_threshold
        self.default_ttl = default_ttl_seconds
        self.max_entries = max_entries

        # Map: sha256_hash -> CacheEntry
        self._exact_cache: dict[str, CacheEntry] = {}
        # List of entries for semantic search
        self._entries: list[CacheEntry] = []

        # Metrics
        self._hits_exact = 0
        self._hits_semantic = 0
        self._misses = 0
        self._tokens_saved = 0

    def _hash_key(self, prompt: str, model: str) -> str:
        content = f"{model}::{prompt.strip()}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def get(
        self,
        prompt: str,
        model: str,
    ) -> tuple[dict[str, Any], str, float] | None:
        cleaned = prompt.strip()
        if not cleaned:
            return None

        # 1. Check exact match O(1)
        key = self._hash_key(cleaned, model)
        exact_entry = self._exact_cache.get(key)
        if exact_entry and not exact_entry.is_expired():
            self._hits_exact += 1
            tokens = exact_entry.response.get("usage", {}).get("total_tokens", 25)
            self._tokens_saved += tokens
            return exact_entry.response, "exact", 1.0

        # Purge expired entries lazily
        now = time.time()
        self._entries = [e for e in self._entries if e.expires_at > now]

        # 2. Check semantic similarity
        if not self._entries:
            self._misses += 1
            return None

        query_vec = _compute_embedding_vector(cleaned)
        best_entry: CacheEntry | None = None
        best_sim = -1.0

        for entry in self._entries:
            if entry.model != model:
                continue
            sim = float(np.dot(query_vec, entry.embedding))
            if sim > best_sim:
                best_sim = sim
                best_entry = entry

        if best_entry and best_sim >= self.similarity_threshold:
            self._hits_semantic += 1
            tokens = best_entry.response.get("usage", {}).get("total_tokens", 25)
            self._tokens_saved += tokens
            return best_entry.response, "semantic", round(best_sim, 4)

        self._misses += 1
        return None

    async def set(
        self,
        prompt: str,
        model: str,
        response: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        cleaned = prompt.strip()
        if not cleaned:
            return

        ttl = ttl_seconds or self.default_ttl
        vec = _compute_embedding_vector(cleaned)
        entry = CacheEntry(
            prompt=cleaned,
            model=model,
            response=response,
            embedding=vec,
            ttl_seconds=ttl,
        )

        key = self._hash_key(cleaned, model)
        self._exact_cache[key] = entry
        self._entries.append(entry)

        # Evict oldest if exceeding max entries
        if len(self._entries) > self.max_entries:
            oldest = self._entries.pop(0)
            oldest_key = self._hash_key(oldest.prompt, oldest.model)
            self._exact_cache.pop(oldest_key, None)

    async def get_stats(self) -> dict[str, Any]:
        total_requests = self._hits_exact + self._hits_semantic + self._misses
        hit_ratio = (
            round((self._hits_exact + self._hits_semantic) / total_requests, 4)
            if total_requests > 0
            else 0.0
        )
        # Assuming avg cost of $0.005 per 1k tokens saved
        estimated_cost_saved = round((self._tokens_saved / 1000.0) * 0.005, 4)

        return {
            "total_requests": total_requests,
            "hits_exact": self._hits_exact,
            "hits_semantic": self._hits_semantic,
            "total_hits": self._hits_exact + self._hits_semantic,
            "misses": self._misses,
            "hit_ratio": hit_ratio,
            "tokens_saved": self._tokens_saved,
            "estimated_cost_saved_usd": estimated_cost_saved,
            "active_cache_entries": len(self._entries),
        }

    async def clear(self) -> None:
        self._exact_cache.clear()
        self._entries.clear()
