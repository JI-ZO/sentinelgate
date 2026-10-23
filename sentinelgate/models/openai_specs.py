"""OpenAI-compatible request and response schemas."""

import time
from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message within a chat completion conversation."""

    role: str = Field(..., description="Role of the author: system, user, assistant, or tool")
    content: str = Field(..., description="The contents of the message")
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request schema."""

    model: str = Field(default="gpt-4o", description="ID of the model to use")
    messages: list[ChatMessage] = Field(
        ..., description="A list of messages comprising the conversation so far"
    )
    temperature: float | None = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float | None = Field(default=1.0, ge=0.0, le=1.0)
    n: int | None = Field(default=1, ge=1)
    stream: bool | None = Field(default=False)
    max_tokens: int | None = Field(default=None)
    user: str | None = Field(
        default=None, description="A unique identifier representing your end-user"
    )

    # Extra SentinelGate parameters (optional pass-through or RAG context)
    context_documents: list[str] | None = Field(
        default=None,
        description="Optional list of retrieved reference documents for groundedness/hallucination checks",
    )


class ChatCompletionChoice(BaseModel):
    """A choice returned in the chat completion response."""

    index: int = 0
    message: ChatMessage
    finish_reason: str | None = "stop"


class UsageInfo(BaseModel):
    """Usage statistics for the completion request."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response schema."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{int(time.time() * 1000)}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageInfo = Field(default_factory=UsageInfo)

    # SentinelGate telemetry headers/metadata
    guardrail_metadata: dict[str, Any] | None = None
