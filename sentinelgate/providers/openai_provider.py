"""Async Upstream OpenAI / Compatible Provider via HTTPX."""

import httpx
from fastapi import HTTPException

from sentinelgate.models.openai_specs import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    UsageInfo,
)
from sentinelgate.providers.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """Proxies chat completion requests to OpenAI or compatible endpoints (e.g. Groq, Ollama, vLLM)."""

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        timeout_seconds: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout_seconds

    async def generate_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": request.model,
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": False,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        url = f"{self.base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Upstream provider error: {response.text}",
                    )
                data = response.json()
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to communicate with upstream provider: {str(exc)}",
                )

        choice_data = data["choices"][0]
        choice = ChatCompletionChoice(
            index=choice_data.get("index", 0),
            message=ChatMessage(
                role=choice_data["message"]["role"],
                content=choice_data["message"]["content"],
            ),
            finish_reason=choice_data.get("finish_reason", "stop"),
        )
        usage_data = data.get("usage", {})
        usage = UsageInfo(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return ChatCompletionResponse(
            id=data.get("id", "chatcmpl-custom"),
            model=data.get("model", request.model),
            created=data.get("created", 0),
            choices=[choice],
            usage=usage,
        )
