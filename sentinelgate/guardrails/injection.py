"""Prompt injection, jailbreak, indirect injection, and structural exploit detector."""

import re
from typing import Any

from sentinelgate.guardrails.base import BaseGuardrail
from sentinelgate.guardrails.semantic_detector import SemanticInjectionDetector
from sentinelgate.models.guardrail_specs import GuardrailAction, GuardrailResult


class PromptInjectionGuardrail(BaseGuardrail):
    """Detects direct prompt injections, indirect document injections, persona jailbreaks, and structural exploits."""

    def __init__(
        self,
        threshold: float = 0.65,
        enabled: bool = True,
        enable_semantic_layer: bool = True,
    ):
        super().__init__(name="prompt_injection_defense", enabled=enabled)
        self.threshold = threshold
        self.enable_semantic = enable_semantic_layer
        self.semantic_detector = SemanticInjectionDetector()

        # High-confidence attack patterns with severity weights
        self._pattern_weights: list[tuple[re.Pattern, float, str]] = [
            # -------------------------------------------------------------
            # 1. Direct System Overrides & Unfiltered Operation
            # -------------------------------------------------------------
            (
                re.compile(r"\b(system\s+reset|reset\s+system|factory\s+reset)\b", re.I),
                0.85,
                "System reset / state wipe attack detected",
            ),
            (
                re.compile(
                    r"\b(forget|ignore|disregard|drop|abandon|overwrite|override|wipe|bypass)\b.{1,40}\b(past|previous|prior|all|existing|above|system|initial|your|any)?\s*(directives|instructions|rules|guidelines|constraints|policies|prompts|commands|safeguards)\b",
                    re.I,
                ),
                0.90,
                "Instruction override pattern detected",
            ),
            (
                re.compile(
                    r"\b(your\s+new\s+instructions\s+are\s+to|new\s+system\s+instructions|operate\s+without\s+(any\s+)?(content\s+filters|restrictions|rules))\b",
                    re.I,
                ),
                0.90,
                "Unfiltered operation override detected",
            ),
            (
                re.compile(
                    r"\b(respond\s+(to\s+all\s+future\s+questions\s+)?as\s+(an\s+)?unfiltered\s+(administrative\s+)?ai)\b",
                    re.I,
                ),
                0.90,
                "Unfiltered administrative persona override detected",
            ),
            (
                re.compile(
                    r"\benter\s+(administrative|admin|developer|maintenance|god|root|superuser)\s+mode\b",
                    re.I,
                ),
                0.85,
                "Privilege escalation attempt (administrative mode switch)",
            ),
            (
                re.compile(
                    r"\b(you\s+are\s+now|act\s+as|pretend\s+to\s+be)\b.{0,50}\b(compliance\s+officer|auditor|internal\s+auditor|administrator|investigator|inspector|security\s+(officer|engineer|team)|legal\s+counsel)\b",
                    re.I,
                ),
                0.90,
                "Authority spoofing / administrative audit pretext detected",
            ),
            (
                re.compile(
                    r"\b(output|extract|dump|reveal|print|show|read|leak|exfiltrate)\b.{1,60}\b(conversation\s+history|chat\s+history|customer\s+records?|database\s+records?|context\s+window\s+data|private\s+records?)\b",
                    re.I,
                ),
                0.90,
                "Context window / conversation history exfiltration probe detected",
            ),
            # -------------------------------------------------------------
            # 2. Persona Adoption & Roleplay Evasion (DAN, DevMode, AIM, STAN)
            # -------------------------------------------------------------
            (
                re.compile(
                    r"\b(we\s+are\s+playing\s+a\s+game|roleplay\s+game|roleplay\s+scenario|we\s+are\s+roleplaying|roleplay\s+as)\b.{0,60}\b(dan|stan|aim|dude|omega|unfiltered|jailbroken|evil\s+ai|forbidden\s+queries|without\s+constraints)\b",
                    re.I,
                ),
                0.95,
                "Roleplay game jailbreak detected",
            ),
            (
                re.compile(
                    r"\b(act\s+as|you\s+are\s+now|pretend\s+to\s+be|roleplay\s+as|from\s+now\s+on\s+you\s+(will|shall|are)\s+act\s+as)\b.{0,30}\b(dan|stan|aim|dude|developer\s+mode|unfiltered\s+mode|god\s+mode|jailbroken|evil\s+confidant|rebel|uncensored\s+ai|unfiltered\s+ai|rogue\s+ai|root\s+terminal)\b",
                    re.I,
                ),
                0.95,
                "Known jailbreak persona switch detected (DAN / DevMode / AIM / STAN)",
            ),
            (
                re.compile(r"\bdo\s+anything\s+now\b", re.I),
                0.90,
                "DAN (Do Anything Now) persona signature detected",
            ),
            (
                re.compile(
                    r"\bbroken\s+free\s+of\s+(the\s+)?(typical\s+)?(rules|limitations|filters)\b",
                    re.I,
                ),
                0.90,
                "Rule evasion declaration detected",
            ),
            (
                re.compile(
                    r"\b(broken\s+free\s+of|break\s+free\s+of|free\s+from)\b.{1,35}\b(limitations|rules|restrictions|filters|constraints)\b",
                    re.I,
                ),
                0.85,
                "Jailbreak constraint evasion phrasing detected",
            ),
            (
                re.compile(
                    r"\b(does\s+not|doesn\x27t|dont|do\s+not)\s+have\s+to\s+abide\s+by\s+(the\s+)?rules\b",
                    re.I,
                ),
                0.85,
                "Safety rule defiance signature detected",
            ),
            (
                re.compile(r"\byou\s+are\s+now\s+(in\s+)?developer\s+mode\b", re.I),
                0.95,
                "Developer Mode activation detected",
            ),
            (
                re.compile(
                    r"\b(bypassed|bypass(ing)?)\s+(its|all|the)?\s*guardrails\b",
                    re.I,
                ),
                0.90,
                "Guardrail bypass declaration detected",
            ),
            (
                re.compile(
                    r"\brefuses?\s+to\s+follow\s+safety\s+(guidelines|policies|rules)\b",
                    re.I,
                ),
                0.90,
                "Safety refusal jailbreak signature detected",
            ),
            (
                re.compile(
                    r"\b(act\s+as|pretend\s+to\s+be)\s+(an?\s+)?unfiltered\s+(ai|assistant|model)\b",
                    re.I,
                ),
                0.90,
                "Unfiltered AI persona adoption detected",
            ),
            (
                re.compile(
                    r"\bwithout\s+(any\s+)?(ethical\s+considerations|ethics|content\s+filters|censorship)\b",
                    re.I,
                ),
                0.85,
                "Ethical safeguard suppression detected",
            ),
            (
                re.compile(
                    r"\b(safety\s+(checks|policies|rules))\s+(are|is)\s+(deactivated|disabled|suspended|turned\s+off)\b",
                    re.I,
                ),
                0.90,
                "Safety deactivation statement detected",
            ),
            # -------------------------------------------------------------
            # 3. Creative Writing / Hypothetical Malicious Framing
            # -------------------------------------------------------------
            (
                re.compile(
                    r"\b(writing\s+a\s+(sci-?fi\s+)?(novel|book|story|script|screenplay)|hypothetical\s+(scenario|story|screenplay|script|exercise)|fictional\s+(universe|story|novel|world|script)|for\s+a\s+sci-?fi\s+book\s+i\s+am\s+writing|authoring\s+a\s+fictional\s+book|creative\s+writing\s+purposes\s+only)\b.{1,140}\b(bypass(es)?\s+(an?\s+)?(enterprise\s+)?firewall(s)?|exploit(s)?|zero-day|malware|ransomware|hack(ing)?|crack(ing)?|steal\s+passwords?|infiltrate|privilege\s+escalation)\b",
                    re.I,
                ),
                0.90,
                "Malicious exploit request under creative fiction framing",
            ),
            (
                re.compile(
                    r"\b(imagine\s+a\s+fictional\s+(universe|world|story|scenario)|in\s+this\s+story|hypothetical\s+scenario\s+where|fictional\s+world\s+where|imagine\s+a\s+world\s+without\s+rules|sci-?fi\s+universe)\b.{1,140}\b(without\s+(constraints|rules|safety)|disable\s+all\s+your\s+safety|grant\s+me\s+full\s+access|unfiltered|safety\s+guardrails\s+are\s+(considered\s+)?obsolete)\b",
                    re.I,
                ),
                0.90,
                "Hypothetical fiction framing jailbreak attack",
            ),
            # -------------------------------------------------------------
            # 4. Indirect Prompt Injection & Document Poisoning
            # -------------------------------------------------------------
            (
                re.compile(
                    r"\[\s*(SYSTEM\s+NOTICE|SYSTEM\s+INSTRUCTION|ADMIN\s+NOTE|IMPORTANT\s+NOTICE|NOTE\s+TO\s+ASSISTANT|IMPORTANT\s+UPDATE)\s*:?.*?\]",
                    re.I,
                ),
                0.90,
                "Synthetic system notice injection detected",
            ),
            (
                re.compile(
                    r"\b(output|send|forward|transmit|leak|exfiltrate)\b.{1,80}\b(as\s+url\s+parameters?\s+to\s+https?://|to\s+https?://[^\s)]+)\b",
                    re.I,
                ),
                0.95,
                "Data exfiltration via URL callback detected",
            ),
            (
                re.compile(
                    r"\bread\s+(the\s+)?user(\x27s)?\s+(private\s+)?(email(\s+headers)?|passwords?|tokens?|data|context)\b",
                    re.I,
                ),
                0.85,
                "Context window data exfiltration probe detected",
            ),
            (
                re.compile(
                    r"\b(important\s+update\s+for\s+(assistant|ai|model)|note\s+for\s+ai|system\s+update\s+for\s+assistant|attention\s+(ai|assistant)|note\s+for\s+(ai|assistant))\s*:",
                    re.I,
                ),
                0.90,
                "Assistant instruction hijacking header detected",
            ),
            (
                re.compile(
                    r"\b(end\s+your\s+response\s+here|do\s+not\s+summarize\s+(the\s+rest\s+of\s+)?this\s+(page|document|text)|ignore\s+the\s+document\s+(content\s+)?above)\b",
                    re.I,
                ),
                0.85,
                "Document summary flow hijacking detected",
            ),
            (
                re.compile(
                    r"\b(tell|inform|warn)\s+the\s+user\s+(that\s+)?their\s+(session\s+has\s+expired|account\s+has\s+been\s+suspended|login\s+credentials?\s+need\s+verification)\b",
                    re.I,
                ),
                0.95,
                "Phishing notification attempt detected",
            ),
            (
                re.compile(
                    r"\bprompt\s+them\s+to\s+re-?enter\s+their\s+password\b",
                    re.I,
                ),
                0.95,
                "Phishing credential harvesting attempt detected",
            ),
            # -------------------------------------------------------------
            # 5. Safety Suppression & Direct Filter Disabling
            # -------------------------------------------------------------
            (
                re.compile(
                    r"\b(safety\s+(policies|policy|filters|guidelines|checks))\s+(are|is)\s+disabled\b",
                    re.I,
                ),
                0.90,
                "Explicit safety policy disabling declaration",
            ),
            (
                re.compile(
                    r"\b(disable|turn\s+off|bypass|deactivate|remove)\b.{1,35}\b(all\s+your\s+)?(safety\s+(policies|filters|rules|checks)|content\s+filters|censorship|guardrails)\b",
                    re.I,
                ),
                0.90,
                "Direct safety filter disable command",
            ),
            (
                re.compile(
                    r"\b(answer|respond)\s+(every|any)\s+query\s+without\s+(constraints|rules|filters|limitations)\b",
                    re.I,
                ),
                0.85,
                "Constraint-free response enforcement attempt",
            ),
            (
                re.compile(r"\bgrant\s+(me|us)\s+full\s+access\b", re.I),
                0.80,
                "Administrative full access request",
            ),
            # -------------------------------------------------------------
            # 6. Structural & Delimiter Spoofing
            # -------------------------------------------------------------
            (
                re.compile(
                    r"(</?\s*(user_input|system|developer|prompt|context|instructions|human|assistant)\s*>)",
                    re.I,
                ),
                0.85,
                "Synthetic delimiter tag spoofing detected",
            ),
            (
                re.compile(
                    r"(<\s*/?\s*system\s*>|<\|im_start\|>|<\|im_end\|>|<\|endoftext\|>|\[\s*INST\s*\]|\[\s*/\s*INST\s*\]|<<\s*SYS\s*>>)",
                    re.I,
                ),
                0.85,
                "Chat template / special token injection detected",
            ),
            (
                re.compile(
                    r"\b(developer\s+instruction\s+set\s+has\s+been\s+updated|developers\s+have\s+disabled\s+all\s+safety\s+filters|respond\s+to\s+the\s+prompt\s+below\s+without\s+limits)\b",
                    re.I,
                ),
                0.90,
                "Developer instruction spoofing detected",
            ),
            (
                re.compile(r"---+BEGIN\s+.*(SYSTEM|OVERRIDE|INSTRUCTION).*---+", re.I),
                0.85,
                "Synthetic system boundary delimiter injection",
            ),
        ]

        self._exfiltration_targets = [
            r"system\s+prompt(s)?",
            r"system\s+instruction(s)?",
            r"system\s+message(s)?",
            r"developer\s+message(s)?",
            r"developer\s+instruction(s)?",
            r"developer\s+prompt(s)?",
            r"secret\s+instruction(s)?",
            r"hidden\s+instruction(s)?",
            r"initial\s+instruction(s)?",
            r"underlying\s+instruction(s)?",
            r"underlying\s+prompt(s)?",
            r"internal\s+instruction(s)?",
            r"meta\s+prompt(s)?",
            r"base\s+instruction(s)?",
            r"root\s+prompt(s)?",
            r"core\s+prompt(s)?",
        ]

        self._exfiltration_verbs = [
            r"see",
            r"view",
            r"read",
            r"inspect",
            r"examine",
            r"look\s+at",
            r"show",
            r"reveal",
            r"display",
            r"output",
            r"tell",
            r"give",
            r"share",
            r"print",
            r"expose",
            r"leak",
            r"uncover",
            r"access",
            r"what\s+(is|are)",
            r"repeat",
            r"dump",
            r"copy",
        ]

    def _normalize_text(self, text: str) -> str:
        """Strip punctuation, quotes, and normalize whitespace for robust classification."""
        cleaned = text.lower()
        cleaned = re.sub(r"[\x27\"\u2018\u2019\u201c\u201d`]", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    def _check_system_prompt_exfiltration(self, text: str) -> tuple[float, str | None]:
        """Detects prompt exfiltration attempts across varying syntactic forms and polite prefixes."""
        text_lower = self._normalize_text(text)
        has_target = any(
            re.search(r"\b" + t + r"\b", text_lower) for t in self._exfiltration_targets
        )
        if not has_target:
            return 0.0, None

        has_access = any(re.search(r"\b" + v + r"\b", text_lower) for v in self._exfiltration_verbs)
        has_reference = bool(
            re.search(
                r"\b(your|the|underlying|internal|secret|hidden|original|actual|initial|current)\b",
                text_lower,
            )
        )

        if has_target and (has_access or has_reference):
            # Allow purely academic definition queries like "what does the term system prompt mean in AI?"
            is_academic = bool(
                re.search(r"\b(mean|meaning|definition|concept|explain the term)\b", text_lower)
            ) and not bool(
                re.search(r"\b(your|underlying|secret|hidden|verbatim|exact|this)\b", text_lower)
            )
            if not is_academic:
                return 0.85, "System prompt exfiltration attempt detected"

        return 0.0, None

    def _calculate_anomaly_score(self, text: str) -> float:
        """Inspects anomalous text characteristics like invisible characters or base64 blocks."""
        score = 0.0
        # Check for zero-width spaces or hidden Unicode
        zero_width = len(re.findall(r"[\u200B-\u200D\uFEFF]", text))
        if zero_width > 2:
            score += min(0.4, zero_width * 0.1)

        # Check for excessive base64 payload looking sequences (longer than 40 chars)
        base64_candidates = re.findall(r"(?:[A-Za-z0-9+/]{40,}={0,2})", text)
        if base64_candidates:
            score += 0.35

        return score

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

        max_pattern_score = 0.0
        detected_triggers: list[str] = []

        # 1. Semantic exfiltration detection
        exfil_score, exfil_reason = self._check_system_prompt_exfiltration(text)
        if exfil_score > 0 and exfil_reason:
            max_pattern_score = max(max_pattern_score, exfil_score)
            detected_triggers.append(exfil_reason)

        # 2. Check both raw and normalized text against pattern weights
        normalized_text = self._normalize_text(text)
        for pattern, weight, reason in self._pattern_weights:
            if pattern.search(text) or pattern.search(normalized_text):
                if reason not in detected_triggers:
                    detected_triggers.append(reason)
                if weight > max_pattern_score:
                    max_pattern_score = weight

        # 3. Layer 2 Semantic Vector Evaluation
        semantic_details = None
        if self.enable_semantic:
            sem_res = self.semantic_detector.evaluate(text)
            semantic_details = {
                "is_adversarial": sem_res.is_adversarial,
                "matched_archetype": sem_res.matched_archetype,
                "adversarial_similarity": sem_res.adversarial_similarity,
                "benign_similarity": sem_res.benign_similarity,
                "margin": sem_res.margin,
                "semantic_risk_score": sem_res.risk_score,
            }
            if sem_res.is_adversarial and sem_res.risk_score >= self.threshold:
                reason = f"Layer 2 semantic detection (archetype: {sem_res.matched_archetype})"
                if reason not in detected_triggers:
                    detected_triggers.append(reason)
                if sem_res.risk_score > max_pattern_score:
                    max_pattern_score = sem_res.risk_score

        # 4. Anomaly scores
        anomaly_score = self._calculate_anomaly_score(text)
        total_risk_score = min(1.0, max_pattern_score + anomaly_score * 0.5)

        is_blocked = total_risk_score >= self.threshold

        return GuardrailResult(
            name=self.name,
            passed=not is_blocked,
            action=GuardrailAction.BLOCK if is_blocked else GuardrailAction.ALLOW,
            score=round(total_risk_score, 3),
            reason=" | ".join(detected_triggers)
            if detected_triggers
            else ("Anomalous characters" if anomaly_score > 0 else "Clean input"),
            details={
                "threshold": self.threshold,
                "layer1_pattern_score": max_pattern_score,
                "layer2_semantic": semantic_details,
                "anomaly_score": anomaly_score,
                "triggers": detected_triggers,
            },
        )
