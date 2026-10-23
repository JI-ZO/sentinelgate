"""Telemetry and observability utilities."""

from sentinelgate.telemetry.audit_logger import (
    get_recent_audit_events,
    logger,
    record_audit_event,
)
from sentinelgate.telemetry.metrics import (
    CACHE_HITS,
    GUARDRAIL_VIOLATIONS,
    REQUEST_LATENCY,
    REQUESTS_TOTAL,
    TOKENS_PROCESSED,
)

__all__ = [
    "REQUESTS_TOTAL",
    "GUARDRAIL_VIOLATIONS",
    "CACHE_HITS",
    "REQUEST_LATENCY",
    "TOKENS_PROCESSED",
    "record_audit_event",
    "get_recent_audit_events",
    "logger",
]
