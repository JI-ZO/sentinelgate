"""Abstract Base Cache interface."""

from abc import ABC, abstractmethod
from typing import Any


class BaseCache(ABC):
    """Abstract interface for caching LLM responses."""

    @abstractmethod
    async def get(
        self,
        prompt: str,
        model: str,
    ) -> tuple[dict[str, Any], str, float] | None:
        """Retrieve cached response if exact or semantic match exists.

        Returns:
            Tuple of (response_dict, match_type: 'exact'|'semantic', similarity_score)
            or None if cache miss.
        """
        pass

    @abstractmethod
    async def set(
        self,
        prompt: str,
        model: str,
        response: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        """Store prompt and model response in cache."""
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Return cache hits, misses, hit ratio, and size."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached entries."""
        pass
