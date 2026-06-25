import sys
sys.path.insert(0, "/app")

# registers ticket creation and lookup as tools — used for bugs, complaints, escalations

from packages.ai_layer.tool_registry import register_tool
from services.ticket.service import create_ticket, get_ticket


@register_tool(
    name="create_support_ticket",
    description="Create a support ticket when the user reports a bug, requests a refund, or has an urgent problem needing human attention.",
    keywords=["ticket", "bug", "issue", "refund", "broken", "not working", "urgent", "complaint", "escalate", "human", "agent"],
    intents=["escalation"],
    input_schema={"subject": "string", "description": "string", "priority": "low|normal|high|urgent"},
)
def create_support_ticket(inputs: dict) -> dict:
    return create_ticket(inputs.get("subject", "Support Request"), inputs.get("description", ""), inputs.get("priority", "normal"), inputs.get("user_email", ""))


@register_tool(
    name="lookup_ticket",
    description="Look up the status of an existing support ticket by ticket ID.",
    keywords=["ticket status", "my ticket", "check ticket", "TKT-"],
    intents=["knowledge_query"],
    input_schema={"ticket_id": "string"},
)
def lookup_ticket(inputs: dict) -> dict:
    return get_ticket(inputs.get("ticket_id", ""))