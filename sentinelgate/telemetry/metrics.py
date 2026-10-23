"""Prometheus metrics instrumentation for SentinelGate."""

from prometheus_client import Counter, Gauge, Histogram

REQUESTS_TOTAL = Counter(
    "sentinelgate_requests_total",
    "Total incoming completion requests",
    ["model", "status"],
)

GUARDRAIL_VIOLATIONS = Counter(
    "sentinelgate_guardrail_violations_total",
    "Total guardrail rule activations or blocks",
    ["guardrail_name", "action"],
)

CACHE_HITS = Counter(
    "sentinelgate_cache_hits_total",
    "Total cache inquiries resulting in hits",
    ["hit_type"],
)

REQUEST_LATENCY = Histogram(
    "sentinelgate_request_duration_seconds",
    "Total request latency in seconds",
    ["status"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

TOKENS_PROCESSED = Counter(
    "sentinelgate_tokens_processed_total",
    "Total prompt and completion tokens processed",
    ["token_type"],
)

ACTIVE_SESSIONS = Gauge(
    "sentinelgate_active_requests",
    "Number of requests currently in flight",
)
