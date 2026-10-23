"""OpenAI-compatible /v1/chat/completions endpoint with full guardrail and caching interceptors."""

import time
import uuid

from fastapi import APIRouter, HTTPException, Request, Response

from sentinelgate.cache.memory import InMemorySemanticCache
from sentinelgate.config import settings
from sentinelgate.guardrails.pipeline import GuardrailPipeline
from sentinelgate.models.openai_specs import ChatCompletionRequest, ChatCompletionResponse
from sentinelgate.providers.mock_provider import MockLLMProvider
from sentinelgate.providers.openai_provider import OpenAIProvider
from sentinelgate.telemetry.audit_logger import record_audit_event
from sentinelgate.telemetry.metrics import (
    CACHE_HITS,
    GUARDRAIL_VIOLATIONS,
    REQUEST_LATENCY,
    REQUESTS_TOTAL,
    TOKENS_PROCESSED,
)

router = APIRouter()

# Singletons initialized based on settings
pipeline = GuardrailPipeline(
    enable_injection=settings.guardrail_enable_injection_defense,
    injection_threshold=settings.guardrail_injection_threshold,
    enable_pii=settings.guardrail_enable_pii_masking,
    pii_action=settings.guardrail_pii_action,
    enable_hallucination=settings.guardrail_enable_hallucination_eval,
    hallucination_threshold=settings.guardrail_hallucination_threshold,
    enable_rate_limiter=settings.rate_limit_enabled,
    max_rpm=settings.rate_limit_requests_per_minute,
    max_tpm=settings.rate_limit_tokens_per_minute,
)

cache = InMemorySemanticCache(
    similarity_threshold=settings.cache_similarity_threshold,
    default_ttl_seconds=settings.cache_ttl_seconds,
)

mock_provider = MockLLMProvider()
openai_provider = OpenAIProvider(
    base_url=settings.upstream_base_url,
    api_key=settings.upstream_api_key,
    timeout_seconds=settings.upstream_timeout_seconds,
)


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(
    chat_request: ChatCompletionRequest,
    raw_request: Request,
    response: Response,
):
    """OpenAI-compatible reverse proxy endpoint enforcing guardrails and semantic caching."""
    request_id = f"sg-{uuid.uuid4().hex[:10]}"
    start_time = time.perf_counter()
    client_ip = raw_request.client.host if raw_request.client else "127.0.0.1"
    client_id = chat_request.user or client_ip

    # Find the latest user message
    user_prompt = ""
    user_msg_idx = -1
    for i, msg in enumerate(reversed(chat_request.messages)):
        if msg.role == "user":
            user_prompt = msg.content
            user_msg_idx = len(chat_request.messages) - 1 - i
            break

    estimated_tokens = max(10, sum(len(m.content.split()) for m in chat_request.messages))

    # --- STAGE 1: INPUT GUARDRAILS ---
    input_result = await pipeline.execute_input_pipeline(
        prompt_text=user_prompt,
        client_id=client_id,
        estimated_tokens=estimated_tokens,
        context={"context_documents": chat_request.context_documents},
    )

    if not input_result.passed:
        REQUESTS_TOTAL.labels(model=chat_request.model, status="blocked").inc()
        for g_res in input_result.guardrail_results:
            if not g_res.passed:
                GUARDRAIL_VIOLATIONS.labels(
                    guardrail_name=g_res.name, action=g_res.action.value
                ).inc()

        record_audit_event(
            {
                "request_id": request_id,
                "status": "blocked",
                "model": chat_request.model,
                "prompt_sample": user_prompt[:100],
                "action": "blocked",
                "reason": input_result.block_reason,
                "latency_ms": input_result.latency_ms,
            }
        )

        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": f"SentinelGate Guardrail Violation: {input_result.block_reason}",
                    "type": "guardrail_violation",
                    "request_id": request_id,
                    "details": [r.model_dump() for r in input_result.guardrail_results],
                }
            },
        )

    # If prompt was modified (e.g. PII was masked), update the message
    if input_result.sanitized_text != user_prompt and user_msg_idx >= 0:
        chat_request.messages[user_msg_idx].content = input_result.sanitized_text
        user_prompt = input_result.sanitized_text

    # --- STAGE 2: SEMANTIC CACHING ---
    similarity_score = 0.0

    if settings.cache_enabled:
        cached_result = await cache.get(prompt=user_prompt, model=chat_request.model)
        if cached_result:
            cached_data, hit_type, sim_score = cached_result
            similarity_score = sim_score
            CACHE_HITS.labels(hit_type=hit_type).inc()

            cached_resp = ChatCompletionResponse.model_validate(cached_data)
            cached_resp.id = f"sg-cached-{uuid.uuid4().hex[:8]}"
            cached_resp.guardrail_metadata = {
                "request_id": request_id,
                "cache": f"HIT ({hit_type})",
                "similarity": similarity_score,
                "input_guardrails": [r.model_dump() for r in input_result.guardrail_results],
            }

            total_latency = round((time.perf_counter() - start_time) * 1000, 2)
            REQUEST_LATENCY.labels(status="cached").observe(total_latency / 1000.0)
            REQUESTS_TOTAL.labels(model=chat_request.model, status="cached").inc()

            response.headers["X-Cache"] = f"HIT ({hit_type})"
            response.headers["X-Sentinel-Latency-Ms"] = str(total_latency)

            record_audit_event(
                {
                    "request_id": request_id,
                    "status": "cached",
                    "model": chat_request.model,
                    "prompt_sample": user_prompt[:100],
                    "action": f"cache_hit_{hit_type}",
                    "reason": f"Semantic similarity {similarity_score}",
                    "latency_ms": total_latency,
                }
            )
            return cached_resp

    # --- STAGE 3: UPSTREAM LLM EXECUTION ---
    response.headers["X-Cache"] = "MISS"
    provider = mock_provider if settings.upstream_provider == "mock" else openai_provider
    llm_resp = await provider.generate_chat_completion(chat_request)

    # --- STAGE 4: OUTPUT GUARDRAILS ---
    assistant_output = llm_resp.choices[0].message.content
    output_result = await pipeline.execute_output_pipeline(
        generated_text=assistant_output,
        context={"context_documents": chat_request.context_documents},
    )

    # If output was modified or flagged
    if output_result.sanitized_text != assistant_output:
        llm_resp.choices[0].message.content = output_result.sanitized_text

    for g_res in output_result.guardrail_results:
        if g_res.action.value in ("block", "flag"):
            GUARDRAIL_VIOLATIONS.labels(guardrail_name=g_res.name, action=g_res.action.value).inc()

    # --- STAGE 5: SAVE TO CACHE & RECORD METRICS ---
    if settings.cache_enabled:
        await cache.set(
            prompt=user_prompt,
            model=chat_request.model,
            response=llm_resp.model_dump(),
            ttl_seconds=settings.cache_ttl_seconds,
        )

    total_latency = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["X-Sentinel-Latency-Ms"] = str(total_latency)

    REQUESTS_TOTAL.labels(model=chat_request.model, status="success").inc()
    REQUEST_LATENCY.labels(status="success").observe(total_latency / 1000.0)
    TOKENS_PROCESSED.labels(token_type="prompt").inc(llm_resp.usage.prompt_tokens)
    TOKENS_PROCESSED.labels(token_type="completion").inc(llm_resp.usage.completion_tokens)

    llm_resp.guardrail_metadata = {
        "request_id": request_id,
        "cache": "MISS",
        "input_guardrails": [r.model_dump() for r in input_result.guardrail_results],
        "output_guardrails": [r.model_dump() for r in output_result.guardrail_results],
        "latency_ms": total_latency,
    }

    record_audit_event(
        {
            "request_id": request_id,
            "status": "success",
            "model": chat_request.model,
            "prompt_sample": user_prompt[:100],
            "action": output_result.action.value,
            "reason": "Completed successfully",
            "latency_ms": total_latency,
        }
    )

    return llm_resp
