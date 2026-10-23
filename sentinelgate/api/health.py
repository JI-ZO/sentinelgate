"""Health and Prometheus metrics endpoints."""

import time

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from sentinelgate.config import settings

router = APIRouter()
_START_TIME = time.time()


@router.get("/healthz")
async def health_check():
    """Health check endpoint indicating service readiness and uptime."""
    uptime_seconds = round(time.time() - _START_TIME, 2)
    return {
        "status": "healthy",
        "service": "SentinelGate",
        "version": "0.1.0",
        "uptime_seconds": uptime_seconds,
        "environment": settings.environment,
        "upstream_provider": settings.upstream_provider,
    }


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus exposition format metrics scraper endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
