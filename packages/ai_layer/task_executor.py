import sys
sys.path.insert(0, "/app")
import os
import uuid
import json
import queue
import threading
from datetime import datetime

from packages.shared.types import EscalationResult, OrchestratorState
from packages.shared.pii_masker import mask_pii

LOG_FILE = os.path.join(os.path.dirname(__file__), "../../logs/interactions.jsonl")

_log_queue: queue.Queue = queue.Queue()


def _log_writer():
    while True:
        filepath, content = _log_queue.get()
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "a") as f:
                f.write(content + "\n")
        except Exception:
            pass
        _log_queue.task_done()


threading.Thread(target=_log_writer, daemon=True).start()


def log_interaction(state: OrchestratorState) -> None:
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": state.session_id,
        "portal_id": state.portal_id,
        "input": mask_pii(state.current_input),
        "intent": state.intent.primary_intent if state.intent else "unknown",
        "response_length": len(state.final_response.content) if state.final_response else 0,
    }
    _log_queue.put((LOG_FILE, json.dumps(record)))


def trigger_escalation(state: OrchestratorState, reason: str) -> EscalationResult:
    ticket_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "ticket_id": ticket_id,
        "session_id": state.session_id,
        "portal_id": state.portal_id,
        "reason": reason,
        "user_message": mask_pii(state.current_input),
    }
    escalation_log = os.path.join(os.path.dirname(LOG_FILE), "../logs/escalations.jsonl")
    _log_queue.put((escalation_log, json.dumps(record)))
    return EscalationResult(triggered=True, reason=reason, ticket_id=ticket_id)
