import re
import uuid
from typing import Optional


BLOCKED_PATTERNS = [
    r"(drop\s+table|delete\s+from|insert\s+into|select\s+\*)",
    r"(<script.*?>.*?</script>)",
    r"(javascript\s*:)",
    r"(\bexec\b|\beval\b|\bsystem\b|\bos\.)",
]

FILLER_WORDS = {"the", "a", "an", "is", "are", "was", "were", "i", "me", "my", "we", "our"}


def sanitize_input(text: str) -> str:
    text = text.strip()
    for pattern in BLOCKED_PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"[^\w\s\?\!\.\,\-\'\"@#&()]", "", text)
    return text[:2000]


def extract_keywords(text: str) -> list[str]:
    words = re.findall(r"\b\w{3,}\b", text.lower())
    return [w for w in words if w not in FILLER_WORDS]


def truncate(text: str, max_len: int = 500) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."


def generate_session_id() -> str:
    return str(uuid.uuid4())


def split_multi_query(text: str) -> list[str]:
    delimiters = [r"\band\b", r"\balso\b", r"\?(?=\s)", r"\n", r";"]
    pattern = "|".join(delimiters)
    parts = re.split(pattern, text, flags=re.IGNORECASE)
    cleaned = [p.strip() for p in parts if p and len(p.strip()) > 8]
    return cleaned if len(cleaned) > 1 else []


def detect_escalation_triggers(text: str) -> Optional[str]:
    triggers = {
        "urgent": ["urgent", "emergency", "critical", "asap", "immediately"],
        "frustrated": ["frustrated", "angry", "terrible", "worst", "useless", "broken"],
        "billing": ["refund", "charge", "overcharged", "billing error", "wrong charge"],
        "legal": ["legal", "lawsuit", "attorney", "gdpr", "data breach"],
    }
    lower = text.lower()
    for reason, words in triggers.items():
        if any(w in lower for w in words):
            return reason
    return None


def format_steps_as_text(steps: list[str]) -> str:
    return "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))