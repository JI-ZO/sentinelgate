"""Data models for Guardrail evaluation results and pipeline flow."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GuardrailAction(str, Enum):
    """Action to take based on guardrail evaluation."""

    ALLOW = "allow"
    MASK = "mask"
    BLOCK = "block"
    FLAG = "flag"


class GuardrailResult(BaseModel):
    """Result from an individual guardrail validator."""

    name: str = Field(..., description="Name of the guardrail")
    passed: bool = Field(..., description="Whether the check passed without blocking")
    action: GuardrailAction = Field(default=GuardrailAction.ALLOW)
    score: float = Field(default=0.0, description="Risk or anomaly score between 0.0 and 1.0")
    reason: str | None = Field(default=None, description="Human-readable explanation of findings")
    modified_text: str | None = Field(
        default=None, description="Sanitized/masked text if applicable"
    )
    details: dict[str, Any] = Field(default_factory=dict, description="Metadata or sub-scores")


class PipelineResult(BaseModel):
    """Aggregated result across all input or output guardrails."""

    passed: bool = True
    action: GuardrailAction = GuardrailAction.ALLOW
    block_reason: str | None = None
    sanitized_text: str
    guardrail_results: list[GuardrailResult] = Field(default_factory=list)
    latency_ms: float = 0.0


class InspectionRequest(BaseModel):
    """Request schema for directly inspecting prompt or response against guardrails."""

    text: str = Field(..., description="The prompt or generated text to analyze")
    context_documents: list[str] | None = Field(
        default=None, description="Optional list of reference texts for hallucination verification"
    )
    stage: str = Field(default="input", description="'input' or 'output'")


class InspectionResponse(BaseModel):
    """Response schema from the guardrail inspection endpoint."""

    input_text: str
    passed: bool
    recommended_action: GuardrailAction
    sanitized_text: str
    results: list[GuardrailResult]
    latency_ms: float
