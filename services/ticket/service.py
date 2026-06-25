import sys
sys.path.insert(0, "/app")

# creates and looks up support tickets stored as JSONL

import uuid, json, os
from datetime import datetime

TICKETS_FILE = "/app/logs/tickets.jsonl"


def create_ticket(subject: str, description: str, priority: str = "normal", user_email: str = "") -> dict:
    os.makedirs(os.path.dirname(TICKETS_FILE), exist_ok=True)
    ticket = {
        "ticket_id": f"TKT-{uuid.uuid4().hex[:8].upper()}",
        "subject": subject, "description": description,
        "priority": priority, "user_email": user_email,
        "status": "open", "created_at": datetime.utcnow().isoformat(),
    }
    with open(TICKETS_FILE, "a") as f:
        f.write(json.dumps(ticket) + "\n")
    return ticket


def get_ticket(ticket_id: str) -> dict:
    if not os.path.exists(TICKETS_FILE):
        return {"found": False}
    with open(TICKETS_FILE) as f:
        for line in f:
            t = json.loads(line)
            if t["ticket_id"] == ticket_id:
                return {"found": True, **t}
    return {"found": False}