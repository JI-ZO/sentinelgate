"""Deterministic Mock LLM Provider for local testing, CI/CD, and offline demos."""

import time

from sentinelgate.models.openai_specs import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    UsageInfo,
)
from sentinelgate.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Generates deterministic mock responses for local testing without external API keys."""

    def __init__(self, simulated_latency_s: float = 0.05):
        self.simulated_latency = simulated_latency_s

    async def generate_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        time.sleep(self.simulated_latency)

        last_user_message = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                last_user_message = msg.content
                break

        # If context documents were provided, synthesize grounded response
        if request.context_documents:
            doc_summary = " ".join(request.context_documents[:2])
            reply_text = (
                f"Based on the provided context: '{doc_summary[:80]}...', "
                f"here is the answer to your inquiry regarding '{last_user_message[:40]}'."
            )
        else:
            reply_text = (
                f"[SentinelGate Mock AI Response]: Processed prompt '{last_user_message[:40]}'. "
                f"System running normally with model '{request.model}'."
            )

        prompt_tokens = sum(len(m.content.split()) for m in request.messages)
        completion_tokens = len(reply_text.split())

        return ChatCompletionResponse(
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=reply_text),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
