"""Pytest configuration and shared fixtures for SentinelGate."""

import pytest
from starlette.testclient import TestClient

from sentinelgate.api.v1.chat import cache
from sentinelgate.main import app


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
async def reset_cache():
    """Reset cache state before each test."""
    await cache.clear()
    yield
    await cache.clear()
