"""Guardrail Pipeline coordinating sequential checks on inputs and model outputs."""

import time
from typing import Any

from sentinelgate.guardrails.hallucination import HallucinationGuardrail
from sentinelgate.guardrails.injection import PromptInjectionGuardrail
from sentinelgate.guardrails.pii import PIIGuardrail
from sentinelgate.guardrails.rate_limiter import SlidingWindowRateLimiter
from sentinelgate.models.guardrail_specs import GuardrailAction, GuardrailResult, PipelineResult


class GuardrailPipeline:
    """Manages multi-stage guardrail validation for incoming prompts and outgoing generations."""

    def __init__(
        self,
        enable_injection: bool = True,
        injection_threshold: float = 0.65,
        enable_pii: bool = True,
        pii_action: str = "mask",
        enable_hallucination: bool = True,
        hallucination_threshold: float = 0.40,
        enable_rate_limiter: bool = True,
        max_rpm: int = 60,
        max_tpm: int = 100000,
    ):
        self.injection_guard = PromptInjectionGuardrail(
            threshold=injection_threshold, enabled=enable_injection
        )
        self.pii_guard = PIIGuardrail(action=pii_action, enabled=enable_pii)
        self.hallucination_guard = HallucinationGuardrail(
            threshold=hallucination_threshold, enabled=enable_hallucination
        )
        self.rate_limiter = SlidingWindowRateLimiter(
            max_requests_per_minute=max_rpm,
            max_tokens_per_minute=max_tpm,
            enabled=enable_rate_limiter,
        )

    async def execute_input_pipeline(
        self,
        prompt_text: str,
        client_id: str = "default",
        estimated_tokens: int = 50,
        context: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """Run input guardrails: rate limiting -> prompt injection -> PII masking."""
        start_time = time.perf_counter()
        results: list[GuardrailResult] = []
        current_text = prompt_text

        # 1. Rate limiter
        allowed, reason, quota = self.rate_limiter.check_and_consume(client_id, estimated_tokens)
        if not allowed:
            rl_res = GuardrailResult(
                name="rate_limiter",
                passed=False,
                action=GuardrailAction.BLOCK,
                score=1.0,
                reason=reason,
                details=quota,
            )
            return PipelineResult(
                passed=False,
                action=GuardrailAction.BLOCK,
                block_reason=reason,
                sanitized_text=prompt_text,
                guardrail_results=[rl_res],
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

        # 2. Prompt Injection Defense (Direct User Prompt)
        inj_res = await self.injection_guard.validate(current_text, context)
        results.append(inj_res)
        if not inj_res.passed:
            return PipelineResult(
                passed=False,
                action=GuardrailAction.BLOCK,
                block_reason=inj_res.reason or "Prompt injection attack detected",
                sanitized_text=current_text,
                guardrail_results=results,
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

        # 2b. Indirect Prompt Injection Defense (Retrieved Context Documents / Web Content)
        context_docs = (context or {}).get("context_documents")
        if context_docs and isinstance(context_docs, list):
            for doc_idx, doc in enumerate(context_docs):
                doc_inj_res = await self.injection_guard.validate(doc, context)
                if not doc_inj_res.passed:
                    doc_inj_res.name = "indirect_prompt_injection_defense"
                    doc_inj_res.reason = f"Indirect injection in retrieved document #{doc_idx + 1}: {doc_inj_res.reason}"
                    results.append(doc_inj_res)
                    return PipelineResult(
                        passed=False,
                        action=GuardrailAction.BLOCK,
                        block_reason=doc_inj_res.reason,
                        sanitized_text=current_text,
                        guardrail_results=results,
                        latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
                    )

        # 3. PII Detection & Redaction
        pii_res = await self.pii_guard.validate(current_text, context)
        results.append(pii_res)
        if not pii_res.passed:
            # Action was configured as BLOCK
            return PipelineResult(
                passed=False,
                action=GuardrailAction.BLOCK,
                block_reason=pii_res.reason or "Prompt contained prohibited PII",
                sanitized_text=current_text,
                guardrail_results=results,
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )
        elif pii_res.modified_text:
            current_text = pii_res.modified_text

        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return PipelineResult(
            passed=True,
            action=GuardrailAction.MASK
            if pii_res.action == GuardrailAction.MASK
            else GuardrailAction.ALLOW,
            block_reason=None,
            sanitized_text=current_text,
            guardrail_results=results,
            latency_ms=latency,
        )

    async def execute_output_pipeline(
        self,
        generated_text: str,
        context: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """Run output guardrails: groundedness/hallucination verification and secret leak scan."""
        start_time = time.perf_counter()
        results: list[GuardrailResult] = []
        current_text = generated_text

        # 1. Output PII / secret leak defense
        pii_res = await self.pii_guard.validate(current_text, context)
        results.append(pii_res)
        if pii_res.modified_text:
            current_text = pii_res.modified_text

        # 2. Hallucination check against reference context
        hal_res = await self.hallucination_guard.validate(current_text, context)
        results.append(hal_res)

        overall_action = GuardrailAction.ALLOW
        if hal_res.action == GuardrailAction.FLAG:
            overall_action = GuardrailAction.FLAG
        elif pii_res.action == GuardrailAction.MASK:
            overall_action = GuardrailAction.MASK

        latency = round((time.perf_counter() - start_time) * 1000, 2)
        return PipelineResult(
            passed=True,
            action=overall_action,
            block_reason=None,
            sanitized_text=current_text,
            guardrail_results=results,
            latency_ms=latency,
        )
