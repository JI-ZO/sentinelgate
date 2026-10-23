"""Sliding window token-bucket rate limiter for RPM (requests) and TPM (tokens)."""

import time


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter tracking requests and tokens per client key."""

    def __init__(
        self,
        max_requests_per_minute: int = 60,
        max_tokens_per_minute: int = 100000,
        enabled: bool = True,
    ):
        self.max_requests = max_requests_per_minute
        self.max_tokens = max_tokens_per_minute
        self.enabled = enabled

        # Map: client_id -> List of (timestamp, token_count)
        self._history: dict[str, list[tuple[float, int]]] = {}

    def _cleanup_window(self, client_id: str, now: float) -> None:
        """Remove entries older than 60 seconds from the client's history."""
        cutoff = now - 60.0
        if client_id in self._history:
            self._history[client_id] = [
                entry for entry in self._history[client_id] if entry[0] > cutoff
            ]
            if not self._history[client_id]:
                del self._history[client_id]

    def check_and_consume(
        self,
        client_id: str = "default",
        estimated_tokens: int = 100,
    ) -> tuple[bool, str | None, dict[str, int]]:
        """Check if request is within quota and record it.

        Returns:
            Tuple of (allowed, violation_reason, quota_stats)
        """
        if not self.enabled:
            return True, None, {"remaining_requests": 9999, "remaining_tokens": 999999}

        now = time.time()
        self._cleanup_window(client_id, now)

        history = self._history.get(client_id, [])
        current_requests = len(history)
        current_tokens = sum(t for _, t in history)

        # Check RPM
        if current_requests + 1 > self.max_requests:
            return (
                False,
                f"Rate limit exceeded: {current_requests}/{self.max_requests} requests per minute",
                {
                    "remaining_requests": 0,
                    "remaining_tokens": max(0, self.max_tokens - current_tokens),
                },
            )

        # Check TPM
        if current_tokens + estimated_tokens > self.max_tokens:
            return (
                False,
                f"Token budget exceeded: {current_tokens + estimated_tokens}/{self.max_tokens} tokens per minute",
                {
                    "remaining_requests": max(0, self.max_requests - current_requests),
                    "remaining_tokens": 0,
                },
            )

        # Record usage
        if client_id not in self._history:
            self._history[client_id] = []
        self._history[client_id].append((now, estimated_tokens))

        remaining_reqs = self.max_requests - (current_requests + 1)
        remaining_toks = self.max_tokens - (current_tokens + estimated_tokens)

        return (
            True,
            None,
            {
                "remaining_requests": max(0, remaining_reqs),
                "remaining_tokens": max(0, remaining_toks),
            },
        )
