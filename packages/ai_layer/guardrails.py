import sys
sys.path.insert(0, "/app")

from packages.shared.types import GuardrailResult

MAX_INPUT_LENGTH = 1500

PORTAL_GUARDRAIL_CONFIG = {
    "kiotel_chatbot": {
        "blocked_topics": [
            {"pattern": "how to hack", "reason": "Security policy violation."},
            {"pattern": "make a bomb", "reason": "Safety policy violation."},
            {"pattern": "drug synthesis", "reason": "Safety policy violation."},
            {"pattern": "malware", "reason": "Security policy violation."},
        ],
        "restricted_topics": [
            {"pattern": "user data", "allowed_roles": ["admin", "superadmin"], "reason": "Access to user data requires admin role."},
            {"pattern": "internal logs", "allowed_roles": ["superadmin"], "reason": "Internal logs are restricted to superadmin only."},
            {"pattern": "delete account", "allowed_roles": ["admin", "superadmin"], "reason": "Account deletion requires admin role."},
            {"pattern": "billing override", "allowed_roles": ["superadmin"], "reason": "Billing overrides are restricted to superadmin only."},
        ],
    },
    "portal_b": {
        "blocked_topics": [
            {"pattern": "competitor pricing", "reason": "Competitor data queries are not allowed."},
        ],
        "restricted_topics": [
            {"pattern": "raw analytics", "allowed_roles": ["analyst", "admin"], "reason": "Raw analytics access requires analyst role."},
        ],
    },
}

DEFAULT_CONFIG = {"blocked_topics": [], "restricted_topics": []}

# Deterministic, code-enforced reply for off-topic chit_chat (no Kiotel service
# matched the query). Never sent to any LLM — the receptionist persona prompt
# alone is not a reliable guardrail against small local models answering
# general-knowledge questions anyway.
OFF_TOPIC_REDIRECT_MESSAGE = (
    "I'm the Kiotel assistant, so I can only help with things related to Kiotel — "
    "the dashboard, your account, property documents, or step-by-step guidance. "
    "What would you like help with in Kiotel?"
)


def check_input(raw_text: str, portal_id: str = "kiotel_chatbot", user_role: str = "user") -> GuardrailResult:
    if not raw_text or not raw_text.strip():
        return GuardrailResult(passed=False, reason="Input is empty.")

    if len(raw_text) > MAX_INPUT_LENGTH:
        return GuardrailResult(passed=False, reason="Input exceeds maximum allowed length.")

    config = PORTAL_GUARDRAIL_CONFIG.get(portal_id, DEFAULT_CONFIG)
    lower = raw_text.lower()

    for rule in config.get("blocked_topics", []):
        if rule["pattern"] in lower:
            return GuardrailResult(passed=False, reason=rule["reason"])

    for rule in config.get("restricted_topics", []):
        if rule["pattern"] in lower:
            if user_role not in rule["allowed_roles"]:
                return GuardrailResult(
                    passed=False,
                    reason=f"Access denied: {rule['reason']} (your role: {user_role})"
                )

    return GuardrailResult(passed=True, sanitized_input=raw_text.strip()[:MAX_INPUT_LENGTH])


def check_output(response_text: str) -> GuardrailResult:
    if not response_text or not response_text.strip():
        return GuardrailResult(passed=False, reason="Empty response from AI.")

    SENSITIVE_LEAKS = ["google_api_key", "bearer token", "api_key="]
    lower = response_text.lower()
    for leak in SENSITIVE_LEAKS:
        if leak in lower:
            return GuardrailResult(passed=False, reason="Potential sensitive data in response.")

    return GuardrailResult(passed=True, sanitized_input=response_text)