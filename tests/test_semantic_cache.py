"""Tests for In-Memory Semantic and Exact match caching."""

import pytest

from sentinelgate.cache.memory import InMemorySemanticCache


@pytest.mark.asyncio
async def test_exact_cache_hit():
    cache = InMemorySemanticCache(similarity_threshold=0.90)
    prompt = "What is the capital of France?"
    model = "gpt-4o"
    mock_resp = {"id": "123", "choices": [{"message": {"content": "Paris"}}]}

    # Initial get should be miss
    miss = await cache.get(prompt, model)
    assert miss is None

    # Set cache
    await cache.set(prompt, model, mock_resp)

    # Subsequent identical get should be exact hit
    hit = await cache.get(prompt, model)
    assert hit is not None
    data, hit_type, score = hit
    assert hit_type == "exact"
    assert score == 1.0
    assert data["choices"][0]["message"]["content"] == "Paris"


@pytest.mark.asyncio
async def test_semantic_cache_hit():
    cache = InMemorySemanticCache(similarity_threshold=0.75)
    prompt_stored = "How do you calculate compound interest formula?"
    prompt_query = "How do you calculate compound interest formula step by step?"
    model = "gpt-4o"
    mock_resp = {"id": "456", "choices": [{"message": {"content": "A = P(1 + r/n)^nt"}}]}

    await cache.set(prompt_stored, model, mock_resp)

    hit = await cache.get(prompt_query, model)
    assert hit is not None
    data, hit_type, score = hit
    assert hit_type in ("exact", "semantic")
    assert score >= 0.75
    assert data["choices"][0]["message"]["content"] == "A = P(1 + r/n)^nt"


@pytest.mark.asyncio
async def test_unrelated_prompt_cache_miss():
    cache = InMemorySemanticCache(similarity_threshold=0.90)
    await cache.set("How to cook pasta?", "gpt-4o", {"content": "Boil water"})

    hit = await cache.get("What is quantum computing?", "gpt-4o")
    assert hit is None


@pytest.mark.asyncio
async def test_cache_stats():
    cache = InMemorySemanticCache()
    await cache.set("Test prompt", "gpt-4o", {"usage": {"total_tokens": 50}})
    await cache.get("Test prompt", "gpt-4o")

    stats = await cache.get_stats()
    assert stats["hits_exact"] == 1
    assert stats["tokens_saved"] == 50
    assert stats["hit_ratio"] == 1.0
