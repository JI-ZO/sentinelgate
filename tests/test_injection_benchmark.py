"""Automated regression test for the 100+ prompt injection benchmark suite."""

import pytest

from scripts.benchmark_100_injections import BENCHMARK_SUITE
from sentinelgate.guardrails.injection import PromptInjectionGuardrail


@pytest.mark.asyncio
@pytest.mark.parametrize("case", BENCHMARK_SUITE, ids=lambda c: c.case_id)
async def test_benchmark_case(case):
    guardrail = PromptInjectionGuardrail(threshold=0.65)
    result = await guardrail.validate(case.prompt)
    assert result.action == case.expected_action, (
        f"[{case.case_id}] {case.category}: Expected {case.expected_action.value}, got {result.action.value} (score={result.score}, reason={result.reason})"
    )
