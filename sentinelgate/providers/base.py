"""Abstract Base LLM Provider."""

from abc import ABC, abstractmethod

from sentinelgate.models.openai_specs import ChatCompletionRequest, ChatCompletionResponse


class BaseLLMProvider(ABC):
    """Abstract interface for upstream LLM providers."""

    @abstractmethod
    async def generate_chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        """Call the upstream LLM and return a standardized response."""
        pass
