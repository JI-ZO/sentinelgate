"""Groundedness and Hallucination verification for RAG and context-grounded outputs."""

import math
import re
from typing import Any

from sentinelgate.guardrails.base import BaseGuardrail
from sentinelgate.models.guardrail_specs import GuardrailAction, GuardrailResult


def _tokenize(text: str) -> list[str]:
    """Simple lowercase tokenization removing punctuation."""
    return re.findall(r"\b\w+\b", text.lower())


def _get_ngrams(tokens: list[str], n: int) -> set[str]:
    """Generate set of n-grams from token list."""
    if len(tokens) < n:
        return set()
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "in",
    "on",
    "at",
    "to",
    "for",
    "with",
    "is",
    "was",
    "are",
    "were",
    "it",
    "this",
    "that",
    "of",
    "by",
    "as",
    "be",
    "from",
    "has",
    "have",
    "had",
    "will",
    "would",
    "can",
    "could",
    "should",
}


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences cleanly."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 5]


class HallucinationGuardrail(BaseGuardrail):
    """Evaluates whether an LLM's response is grounded in provided reference context."""

    def __init__(self, threshold: float = 0.40, enabled: bool = True):
        super().__init__(name="hallucination_groundedness_eval", enabled=enabled)
        self.threshold = threshold

    def _sentence_similarity(self, sent1: str, sent2: str) -> float:
        """Compute cosine similarity over content word frequency vectors."""
        tok1 = [w for w in _tokenize(sent1) if w not in STOP_WORDS]
        tok2 = [w for w in _tokenize(sent2) if w not in STOP_WORDS]
        if not tok1 or not tok2:
            return 0.0

        all_words = set(tok1).union(set(tok2))
        v1 = [tok1.count(w) for w in all_words]
        v2 = [tok2.count(w) for w in all_words]

        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def evaluate_groundedness(
        self,
        generated_text: str,
        reference_contexts: list[str],
    ) -> dict[str, Any]:
        """Compute groundedness metrics between generated text and reference documents."""
        combined_context = " ".join(reference_contexts)
        context_tokens = _tokenize(combined_context)
        context_content_words = set(w for w in context_tokens if w not in STOP_WORDS)

        gen_sentences = _split_sentences(generated_text)
        if not gen_sentences:
            return {
                "groundedness_score": 1.0,
                "hallucination_score": 0.0,
                "unsupported_sentences": [],
                "overlap_ratio": 1.0,
            }

        unsupported_sentences: list[dict[str, Any]] = []
        context_sentences = _split_sentences(combined_context)

        # For each generated sentence, find max similarity against any context sentence
        for sent in gen_sentences:
            sent_tokens = _tokenize(sent)
            content_words = [w for w in sent_tokens if w not in STOP_WORDS]
            if not content_words:
                continue

            # Content word overlap ratio with entire context
            overlap = len(set(content_words).intersection(context_content_words)) / len(
                set(content_words)
            )

            # Maximum sentence-level semantic alignment
            max_sim = 0.0
            for c_sent in context_sentences:
                sim = self._sentence_similarity(sent, c_sent)
                if sim > max_sim:
                    max_sim = sim

            # If content word overlap is below 40% and max sentence similarity is below 0.35
            if overlap < 0.40 and max_sim < 0.35:
                unsupported_sentences.append(
                    {
                        "sentence": sent,
                        "max_similarity": round(max_sim, 3),
                        "token_overlap": round(overlap, 3),
                    }
                )

        unsupported_ratio = len(unsupported_sentences) / len(gen_sentences)
        hallucination_risk = round(unsupported_ratio, 3)
        groundedness_score = round(1.0 - hallucination_risk, 3)

        return {
            "groundedness_score": groundedness_score,
            "hallucination_score": hallucination_risk,
            "unsupported_sentences": unsupported_sentences,
            "total_sentences": len(gen_sentences),
        }

    async def validate(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        if not self.enabled or not text.strip():
            return GuardrailResult(
                name=self.name,
                passed=True,
                action=GuardrailAction.ALLOW,
                score=0.0,
                reason="Guardrail disabled or empty text",
            )

        reference_contexts = (context or {}).get("context_documents")
        if not reference_contexts or not isinstance(reference_contexts, list):
            # No context provided -> cannot evaluate groundedness against source documents
            return GuardrailResult(
                name=self.name,
                passed=True,
                action=GuardrailAction.ALLOW,
                score=0.0,
                reason="No reference context documents provided to check groundedness against",
            )

        eval_result = self.evaluate_groundedness(text, reference_contexts)
        hallucination_score = eval_result["hallucination_score"]

        is_flagged = hallucination_score > self.threshold

        return GuardrailResult(
            name=self.name,
            passed=not is_flagged,
            action=GuardrailAction.FLAG if is_flagged else GuardrailAction.ALLOW,
            score=hallucination_score,
            reason=(
                f"High hallucination risk ({hallucination_score * 100:.1f}%): "
                f"{len(eval_result['unsupported_sentences'])} ungrounded sentences found"
                if is_flagged
                else f"Output strongly grounded ({eval_result['groundedness_score'] * 100:.1f}%)"
            ),
            details=eval_result,
        )
