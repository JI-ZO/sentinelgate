"""Guardrail inspection and direct testing endpoints."""

import time

from fastapi import APIRouter

from sentinelgate.api.v1.chat import pipeline
from sentinelgate.models.guardrail_specs import (
    InspectionRequest,
    InspectionResponse,
)

router = APIRouter()


@router.post("/guardrails/inspect", response_model=InspectionResponse)
async def inspect_text(req: InspectionRequest):
    """Directly test any prompt or completion against SentinelGate guardrails without calling LLM."""
    start_time = time.perf_counter()

    if req.stage == "output":
        result = await pipeline.execute_output_pipeline(
            generated_text=req.text,
            context={"context_documents": req.context_documents},
        )
    else:
        result = await pipeline.execute_input_pipeline(
            prompt_text=req.text,
            context={"context_documents": req.context_documents},
        )

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return InspectionResponse(
        input_text=req.text,
        passed=result.passed,
        recommended_action=result.action,
        sanitized_text=result.sanitized_text,
        results=result.guardrail_results,
        latency_ms=latency_ms,
    )
