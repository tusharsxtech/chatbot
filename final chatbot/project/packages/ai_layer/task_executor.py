import sys
sys.path.insert(0, "/app")
import os
import uuid
import json
from datetime import datetime

from packages.shared.types import EscalationResult, OrchestratorState
from packages.shared.pii_masker import mask_pii

LOG_FILE = os.path.join(os.path.dirname(__file__), "../../logs/interactions.jsonl")


def log_interaction(state: OrchestratorState) -> None:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": state.session_id,
        "portal_id": state.portal_id,
        "input": mask_pii(state.current_input),
        "intent": state.intent.primary_intent if state.intent else "unknown",
        "response_length": len(state.final_response.content) if state.final_response else 0,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def trigger_escalation(state: OrchestratorState, reason: str) -> EscalationResult:
    ticket_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "ticket_id": ticket_id,
        "session_id": state.session_id,
        "portal_id": state.portal_id,
        "reason": reason,
        "user_message": mask_pii(state.current_input),
    }
    escalation_log = os.path.join(os.path.dirname(LOG_FILE), "../logs/escalations.jsonl")
    os.makedirs(os.path.dirname(escalation_log), exist_ok=True)
    with open(escalation_log, "a") as f:
        f.write(json.dumps(record) + "\n")

    return EscalationResult(triggered=True, reason=reason, ticket_id=ticket_id)