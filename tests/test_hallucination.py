"""Tests for Hallucination and Groundedness evaluation."""

import pytest

from sentinelgate.guardrails.hallucination import HallucinationGuardrail
from sentinelgate.models.guardrail_specs import GuardrailAction


@pytest.mark.asyncio
async def test_grounded_response_passes():
    guard = HallucinationGuardrail(threshold=0.40)
    context_docs = [
        "SentinelGate is an open-source LLM security gateway built in Python. "
        "It provides real-time guardrails, semantic caching, and hallucination evaluation."
    ]
    response_text = "SentinelGate is an open-source LLM security gateway built in Python."

    result = await guard.validate(
        text=response_text,
        context={"context_documents": context_docs},
    )

    assert result.passed is True
    assert result.action == GuardrailAction.ALLOW
    assert result.score <= 0.40


@pytest.mark.asyncio
async def test_hallucinated_response_flagged():
    guard = HallucinationGuardrail(threshold=0.40)
    context_docs = [
        "The Apollo 11 mission was the spaceflight that first landed humans on the Moon in July 1969."
    ]
    response_text = (
        "The Apollo 11 astronauts landed on Mars in 2045 and discovered alien pyramids in Cairo."
    )

    result = await guard.validate(
        text=response_text,
        context={"context_documents": context_docs},
    )

    assert result.passed is False
    assert result.action == GuardrailAction.FLAG
    assert result.score > 0.40
    assert len(result.details["unsupported_sentences"]) > 0


@pytest.mark.asyncio
async def test_no_context_passes():
    guard = HallucinationGuardrail(threshold=0.40)
    result = await guard.validate(
        text="Arbitrary text with no context provided.",
        context={},
    )
    assert result.passed is True
    assert result.action == GuardrailAction.ALLOW
