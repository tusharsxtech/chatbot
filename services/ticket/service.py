import sys
sys.path.insert(0, "/app")

import uuid
import json
import os
import queue
import threading
from datetime import datetime

TICKETS_FILE = "/app/logs/tickets.jsonl"

_ticket_queue: queue.Queue = queue.Queue()


def _ticket_writer():
    while True:
        filepath, content = _ticket_queue.get()
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "a") as f:
                f.write(content + "\n")
        except Exception:
            pass
        _ticket_queue.task_done()


threading.Thread(target=_ticket_writer, daemon=True).start()


def create_ticket(subject: str, description: str, priority: str = "normal", user_email: str = "") -> dict:
    ticket = {
        "ticket_id": f"TKT-{uuid.uuid4().hex[:8].upper()}",
        "subject": subject, "description": description,
        "priority": priority, "user_email": user_email,
        "status": "open", "created_at": datetime.utcnow().isoformat(),
    }
    _ticket_queue.put((TICKETS_FILE, json.dumps(ticket)))
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
