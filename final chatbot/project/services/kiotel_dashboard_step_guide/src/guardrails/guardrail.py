import re
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from configs.settings import get_settings
from configs.logging_config import get_logger

logger = get_logger(__name__)

_KIOTEL_SCOPE_TERMS = [
    "kiosk", "kiotel", "agent", "admin", "dashboard", "device", "scan",
    "cash", "key", "dispenser", "transaction", "check", "hotel", "guest",
    "control", "observer", "online", "offline", "receipt", "printer",
    "session", "login", "settings", "permission", "bm25", "baud",
    "simulation", "recycler", "scanner", "authorization", "approval",
]

_INJECTION_PATTERNS = [
    r"ignore (previous|all|above) instructions?",
    r"you are now",
    r"pretend (you are|to be)",
    r"forget (your|all) (instructions?|guidelines?|training)",
    r"jailbreak",
    r"disregard (your|the) (system|instructions?)",
    r"act as (an? )?",
    r"prompt injection",
]

_PII_PATTERNS = [
    r"\b\d{16}\b",
    r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
]


@dataclass
class GuardrailResult:
    blocked: bool
    reason: str = ""
    message: str = ""
    score: float = 1.0


class Guardrail:
    def __init__(self):
        self.settings = get_settings()

    def check_input(self, text: str) -> GuardrailResult:
        if len(text.split()) > self.settings.guardrail_max_input_tokens:
            return GuardrailResult(
                blocked=True,
                reason="input_too_long",
                message="Your question is too long. Please keep it under 2000 words.",
            )

        lower = text.lower()
        for pattern in _INJECTION_PATTERNS:
            if re.search(pattern, lower):
                return GuardrailResult(
                    blocked=True,
                    reason="prompt_injection",
                    message="I can only answer questions about the Kiotel dashboard.",
                )

        for topic in self.settings.banned_topics_list:
            if topic.lower() in lower:
                return GuardrailResult(
                    blocked=True,
                    reason=f"banned_topic:{topic}",
                    message="That topic is outside the scope of Kiotel support.",
                )

        return GuardrailResult(blocked=False)

    def check_relevance(
        self, query: str, retrieved_docs: List[dict]
    ) -> GuardrailResult:
        if not retrieved_docs:
            return GuardrailResult(
                blocked=True,
                reason="no_documents_retrieved",
                message=(
                    "I could not find relevant information in the Kiotel documentation "
                    "to answer your question. Please try rephrasing or check the docs directly."
                ),
                score=0.0,
            )

        top_score = retrieved_docs[0].get("rerank_score", retrieved_docs[0].get("hybrid_score", 0.0))
        threshold = self.settings.guardrail_relevance_threshold

        query_terms = set(query.lower().split())
        doc_text = " ".join(d["content"] for d in retrieved_docs[:3]).lower()
        scope_hit = any(term in doc_text for term in _KIOTEL_SCOPE_TERMS)

        if not scope_hit and top_score < threshold:
            return GuardrailResult(
                blocked=True,
                reason="out_of_scope",
                message=(
                    "Your question does not appear to be about the Kiotel dashboard. "
                    "I can only help with Kiotel agent and admin dashboard questions."
                ),
                score=float(top_score),
            )

        return GuardrailResult(blocked=False, score=float(top_score))

    def check_output(self, text: str) -> GuardrailResult:
        for pattern in _PII_PATTERNS:
            if re.search(pattern, text):
                logger.warning("pii_detected_in_output")
                return GuardrailResult(
                    blocked=True,
                    reason="pii_in_output",
                    message="The response contained sensitive information and was blocked. Please rephrase your question.",
                )

        if len(text.strip()) < 5:
            return GuardrailResult(
                blocked=True,
                reason="empty_output",
                message="I was unable to generate a response. Please try again.",
            )

        return GuardrailResult(blocked=False)
