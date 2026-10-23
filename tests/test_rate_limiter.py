"""Tests for Token-Bucket Sliding Window Rate Limiter."""

from sentinelgate.guardrails.rate_limiter import SlidingWindowRateLimiter


def test_rate_limiter_allows_under_quota():
    limiter = SlidingWindowRateLimiter(max_requests_per_minute=5, max_tokens_per_minute=1000)
    for _ in range(5):
        allowed, reason, stats = limiter.check_and_consume("user1", estimated_tokens=100)
        assert allowed is True
        assert reason is None

    # 6th request exceeds RPM
    allowed, reason, stats = limiter.check_and_consume("user1", estimated_tokens=100)
    assert allowed is False
    assert "Rate limit exceeded" in reason


def test_token_quota_exceeded():
    limiter = SlidingWindowRateLimiter(max_requests_per_minute=100, max_tokens_per_minute=500)
    allowed, reason, stats = limiter.check_and_consume("user2", estimated_tokens=600)
    assert allowed is False
    assert "Token budget exceeded" in reason
