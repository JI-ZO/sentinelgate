"""Tests for PII and Secret detection and redaction."""

import pytest

from sentinelgate.guardrails.pii import PIIGuardrail
from sentinelgate.models.guardrail_specs import GuardrailAction


@pytest.mark.asyncio
async def test_email_redacted():
    guard = PIIGuardrail(action="mask")
    text = "Please reach out to alex.smith@example.org regarding the invoice."
    result = await guard.validate(text)
    assert result.passed is True
    assert result.action == GuardrailAction.MASK
    assert "[REDACTED_EMAIL]" in result.modified_text
    assert "alex.smith@example.org" not in result.modified_text


@pytest.mark.asyncio
async def test_ssn_redacted():
    guard = PIIGuardrail(action="mask")
    text = "The applicant SSN is 123-45-6789."
    result = await guard.validate(text)
    assert result.passed is True
    assert "[REDACTED_SSN]" in result.modified_text
    assert "123-45-6789" not in result.modified_text


@pytest.mark.asyncio
async def test_aws_key_redacted():
    guard = PIIGuardrail(action="mask")
    text = "Use this key: AKIAIOSFODNN7EXAMPLE for deployment."
    result = await guard.validate(text)
    assert result.passed is True
    assert "[REDACTED_AWS_KEY]" in result.modified_text
    assert "AKIAIOSFODNN7EXAMPLE" not in result.modified_text


@pytest.mark.asyncio
async def test_pii_blocking_mode():
    guard = PIIGuardrail(action="block")
    text = "My email is test@company.com"
    result = await guard.validate(text)
    assert result.passed is False
    assert result.action == GuardrailAction.BLOCK
    assert "sensitive PII" in result.reason


@pytest.mark.asyncio
async def test_clean_text_unchanged():
    guard = PIIGuardrail(action="mask")
    text = "The quick brown fox jumps over the lazy dog."
    result = await guard.validate(text)
    assert result.passed is True
    assert result.action == GuardrailAction.ALLOW
    assert result.modified_text == text
