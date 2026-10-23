"""Abstract base class for Guardrail validators."""

from abc import ABC, abstractmethod
from typing import Any

from sentinelgate.models.guardrail_specs import GuardrailResult


class BaseGuardrail(ABC):
    """Base interface for all pre-execution and post-execution guardrails."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled

    @abstractmethod
    async def validate(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        """Validate input or output text and return a GuardrailResult.

        Args:
            text: Text to evaluate.
            context: Additional contextual data (e.g. RAG documents, user metadata).

        Returns:
            GuardrailResult with pass status, score, action, and any modified text.
        """
        pass
