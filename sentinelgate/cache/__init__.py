"""Caching layer for SentinelGate."""

from sentinelgate.cache.base import BaseCache
from sentinelgate.cache.memory import InMemorySemanticCache

__all__ = ["BaseCache", "InMemorySemanticCache"]
