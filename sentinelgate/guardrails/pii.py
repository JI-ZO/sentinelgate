"""PII and secret leak detection and masking guardrail."""

import re
from typing import Any

from sentinelgate.guardrails.base import BaseGuardrail
from sentinelgate.models.guardrail_specs import GuardrailAction, GuardrailResult


def _luhn_checksum_valid(card_number_str: str) -> bool:
    """Validate credit card number using the Luhn checksum algorithm."""
    digits = [int(c) for c in card_number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = d * 2
            checksum += (doubled - 9) if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0


class PIIGuardrail(BaseGuardrail):
    """Detects and redacts or blocks Personal Identifiable Information (PII) and secrets."""

    def __init__(self, action: str = "mask", enabled: bool = True):
        super().__init__(name="pii_redaction", enabled=enabled)
        self.default_action = action.lower()  # 'mask' or 'block'

        # Regex patterns for various PII entity types
        self._email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
        self._ssn_pattern = re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
        self._phone_pattern = re.compile(
            r"\b(?:\+?(\d{1,3}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})\b"
        )
        self._aws_key_pattern = re.compile(r"\b(AKIA[0-9A-Z]{16})\b")
        self._openai_key_pattern = re.compile(r"\b(sk-[a-zA-Z0-9_\-]{20,})\b")
        self._jwt_pattern = re.compile(r"\beyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b")
        self._private_key_pattern = re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----")
        # 13 to 19 digit candidate numbers with optional dashes or spaces
        self._credit_card_candidate = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

    def scan_and_redact(self, text: str) -> tuple[str, list[dict[str, str]]]:
        """Scan text, redact matches with placeholders, and return found entities."""
        redacted = text
        findings: list[dict[str, str]] = []

        # 1. Private keys
        if self._private_key_pattern.search(redacted):
            redacted = self._private_key_pattern.sub("[REDACTED_PRIVATE_KEY]", redacted)
            findings.append({"type": "PRIVATE_KEY", "action": "masked"})

        # 2. AWS Keys
        for match in self._aws_key_pattern.finditer(redacted):
            findings.append({"type": "AWS_API_KEY", "value": match.group(0)[:6] + "..."})
        redacted = self._aws_key_pattern.sub("[REDACTED_AWS_KEY]", redacted)

        # 3. OpenAI / Provider Keys
        for match in self._openai_key_pattern.finditer(redacted):
            findings.append({"type": "LLM_API_KEY", "value": match.group(0)[:5] + "..."})
        redacted = self._openai_key_pattern.sub("[REDACTED_API_KEY]", redacted)

        # 4. JWT tokens
        for match in self._jwt_pattern.finditer(redacted):
            findings.append({"type": "JWT_TOKEN", "value": match.group(0)[:10] + "..."})
        redacted = self._jwt_pattern.sub("[REDACTED_JWT]", redacted)

        # 5. SSN
        for match in self._ssn_pattern.finditer(redacted):
            findings.append({"type": "SSN", "value": "***-**-" + match.group(0)[-4:]})
        redacted = self._ssn_pattern.sub("[REDACTED_SSN]", redacted)

        # 6. Credit Cards (verified via Luhn check)
        for match in self._credit_card_candidate.finditer(text):
            candidate = match.group(0)
            cleaned = re.sub(r"\D", "", candidate)
            if 13 <= len(cleaned) <= 19 and _luhn_checksum_valid(cleaned):
                findings.append({"type": "CREDIT_CARD", "value": f"****-****-****-{cleaned[-4:]}"})
                redacted = redacted.replace(candidate, "[REDACTED_CREDIT_CARD]")

        # 7. Emails
        for match in self._email_pattern.finditer(redacted):
            findings.append({"type": "EMAIL", "value": match.group(0)})
        redacted = self._email_pattern.sub("[REDACTED_EMAIL]", redacted)

        # 8. Phone Numbers
        for match in self._phone_pattern.finditer(redacted):
            matched_str = match.group(0)
            # Avoid masking plain short numbers
            digits = re.sub(r"\D", "", matched_str)
            if len(digits) >= 10:
                findings.append({"type": "PHONE_NUMBER", "value": f"***-***-{digits[-4:]}"})
                redacted = redacted.replace(matched_str, "[REDACTED_PHONE]")

        return redacted, findings

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
                reason="Guardrail disabled or empty input",
            )

        sanitized_text, findings = self.scan_and_redact(text)
        has_pii = len(findings) > 0

        if not has_pii:
            return GuardrailResult(
                name=self.name,
                passed=True,
                action=GuardrailAction.ALLOW,
                score=0.0,
                reason="No sensitive PII or credentials detected",
                modified_text=text,
                details={"findings": []},
            )

        should_block = self.default_action == "block"
        risk_score = min(1.0, 0.4 + (len(findings) * 0.2))

        return GuardrailResult(
            name=self.name,
            passed=not should_block,
            action=GuardrailAction.BLOCK if should_block else GuardrailAction.MASK,
            score=round(risk_score, 2),
            reason=f"Detected {len(findings)} sensitive PII/credential entities",
            modified_text=sanitized_text,
            details={
                "action_taken": "blocked" if should_block else "masked",
                "findings": findings,
            },
        )
