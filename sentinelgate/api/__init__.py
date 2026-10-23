"""API router initialization."""

from sentinelgate.api.health import router as health_router
from sentinelgate.api.v1.analytics import router as analytics_router
from sentinelgate.api.v1.chat import router as chat_router
from sentinelgate.api.v1.guardrails import router as guardrails_router

__all__ = ["health_router", "chat_router", "guardrails_router", "analytics_router"]
