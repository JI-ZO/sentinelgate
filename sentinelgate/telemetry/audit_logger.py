"""Audit logging and in-memory trace buffer for observability."""

import collections
import logging
import time
from typing import Any

logger = logging.getLogger("sentinelgate")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)

# Circular buffer storing the last 200 requests for the dashboard
_RECENT_EVENTS_BUFFER: collections.deque = collections.deque(maxlen=200)


def record_audit_event(event: dict[str, Any]) -> None:
    """Record an audit event to the circular buffer and standard logger."""
    event_with_time = {
        "timestamp": time.time(),
        "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        **event,
    }
    _RECENT_EVENTS_BUFFER.appendleft(event_with_time)

    # Log structured message
    req_id = event.get("request_id", "req-unknown")
    status = event.get("status", "ok")
    latency = event.get("latency_ms", 0)
    logger.info(f"[{req_id}] status={status} latency={latency}ms action={event.get('action')}")


def get_recent_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve recent events from the in-memory circular buffer."""
    return list(_RECENT_EVENTS_BUFFER)[:limit]
