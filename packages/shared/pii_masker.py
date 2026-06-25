import sys
sys.path.insert(0, "/app")

import re

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(\+?\d{1,3}[\s.-]?)?(\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)")
CREDIT_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)")
SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
IP_RE = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
API_KEY_RE = re.compile(r"(?i)(sk-[a-zA-Z0-9]{10,}|bearer\s+[a-zA-Z0-9._-]{10,}|api[_-]?key\s*[=:]\s*\S+)")
LONG_DIGIT_RE = re.compile(r"(?<!\d)\d{8,}(?!\d)")

MASK_PATTERNS = [
    (EMAIL_RE, "[EMAIL_REDACTED]"),
    (API_KEY_RE, "[CREDENTIAL_REDACTED]"),
    (SSN_RE, "[SSN_REDACTED]"),
    (CREDIT_CARD_RE, "[CARD_REDACTED]"),
    (PHONE_RE, "[PHONE_REDACTED]"),
    (IP_RE, "[IP_REDACTED]"),
    (LONG_DIGIT_RE, "[ID_REDACTED]"),
]


def mask_pii(text: str) -> str:
    if not text:
        return text
    masked = text
    for pattern, placeholder in MASK_PATTERNS:
        masked = pattern.sub(placeholder, masked)
    return masked


def mask_fields(record: dict, fields: list[str]) -> dict:
    masked_record = dict(record)
    for field in fields:
        if field in masked_record and isinstance(masked_record[field], str):
            masked_record[field] = mask_pii(masked_record[field])
    return masked_record