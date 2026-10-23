"""Analytics and real-time observability telemetry endpoints."""

from typing import Any

from fastapi import APIRouter

from sentinelgate.api.v1.chat import cache
from sentinelgate.telemetry.audit_logger import get_recent_audit_events

router = APIRouter()


@router.get("/analytics/stats")
async def get_system_stats() -> dict[str, Any]:
    """Retrieve aggregate cache metrics, hit ratios, tokens, and cost savings."""
    cache_stats = await cache.get_stats()
    return {
        "status": "online",
        "cache": cache_stats,
    }


@router.get("/analytics/recent-logs")
async def get_recent_logs(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve recent request audit trails for real-time dashboard visualization."""
    return get_recent_audit_events(limit=limit)
