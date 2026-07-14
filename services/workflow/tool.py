import sys
sys.path.insert(0, "/app")

# registers doc-chat-service (per-device property document Q&A) as a tool —
# answers directly from the device's own documents, bypassing LLM synthesis.
# Never cached (see packages/ai_layer/orchestrator.py _NO_CACHE_TOOLS): answers
# are scoped to a specific device_id and shouldn't leak across sessions/devices.
#
# doc-chat-service gates requests on user_role == its configured required role
# (default "agent") — this is a self-declared flag, not real auth, forwarded
# here verbatim from the session's user_role so that gate still applies.

import os
import json
import logging
import httpx

from packages.ai_layer.tool_registry import register_tool

logger = logging.getLogger(__name__)

DOC_CHAT_URL = os.getenv("DOC_CHAT_URL", "http://localhost:8000")
DOC_CHAT_TIMEOUT = float(os.getenv("DOC_CHAT_TIMEOUT", "60.0"))


def _call_doc_chat(question: str, device_id: str, user_role: str) -> dict:
    payload = {"query": question, "device_id": device_id, "user_role": user_role}
    full_answer = ""
    error = None

    with httpx.Client(timeout=DOC_CHAT_TIMEOUT) as client:
        with client.stream("POST", f"{DOC_CHAT_URL}/chat", json=payload) as resp:
            resp.raise_for_status()
            event_name = None
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    event_name = line[len("event:"):].strip()
                    continue
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                if event_name == "token":
                    full_answer += event.get("content", "")
                elif event_name == "error":
                    error = event.get("detail", "doc-chat service error")
                    break
                elif event_name == "done":
                    break

    if error:
        return {"error": error}
    return {"answer": full_answer}


@register_tool(
    name="kiotel_property_docs",
    description=(
        '''Kiotel Property Document Assistant
           Use this tool to answer questions about a SPECIFIC property/device's own uploaded
           documents — lease terms, property-specific instructions, on-site procedures,
           property workflows (e.g. move-in/move-out steps, pet policy, parking rules,
           maintenance requests, amenity access), and other content stored as property
           documents for that device. Requires a device_id (the device/kiosk currently in
           context) to scope the search — if no device is in context, do not select this tool.

           Do NOT use this tool for general Kiotel dashboard/software how-to questions (use the
           documentation RAG tool) or for live business-data lookups (use the customer_module tool).

           Example queries that SHOULD use this service:
               'what is the pet policy', 'what is the property workflow',
               'what is the move-in process', 'what are the parking rules',
               'how do I submit a maintenance request for this property',
               'what does the lease say about renewal' '''
    ),
    keywords=[
        "property document", "lease", "this property", "this device",
        "site procedure", "property instructions", "on-site",
        # Condensed from a real property manual's table of contents — grouped
        # by topic rather than listed as every raw heading, to avoid bloating
        "night audit", "shift summary", "no-show policy", "payments and deposits",
        "check-in and check-out", "room allocation", "pet policy", "service animal",
        "smoking policy", "housekeeping", "PMS login", "OTA support",
        "vendor contacts", "dashboard password", "facilities and amenities",
        "property rules", "rate plans", "breakfast service", "safety and incidents",
    ],
    intents=["knowledge_query", "general"],
    input_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The user question about the property's documents."},
            "device_id": {"type": "string", "description": "The device/property ID currently in context."},
        },
        "required": ["question", "device_id"],
    },
    portal_ids=["*"],
)
def handle_property_docs(inputs: dict) -> dict:
    question = (inputs.get("question") or "").strip()
    device_id = (inputs.get("device_id") or "").strip()
    user_role = (inputs.get("user_role") or "user").strip()

    if not question:
        return {"found": False, "error": "No question provided to kiotel_property_docs tool."}
    if not device_id:
        return {"found": False, "error": "No device_id in context for kiotel_property_docs tool."}

    try:
        data = _call_doc_chat(question, device_id, user_role)
    except httpx.HTTPStatusError as e:
        logger.error("kiotel_property_docs HTTP error %s: %s", e.response.status_code, e)
        if e.response.status_code == 404:
            return {"found": False, "error": "No property documents found for this device."}
        if e.response.status_code == 403:
            return {"found": False, "error": "Not authorized to access this device's property documents."}
        return {"found": False, "error": f"Property document service returned HTTP {e.response.status_code}."}
    except httpx.RequestError as e:
        logger.error("kiotel_property_docs request error: %s", e)
        return {"found": False, "error": "Property document service unreachable."}

    if data.get("error"):
        return {"found": False, "error": data["error"]}

    answer = (data.get("answer") or "").strip()
    if not answer:
        return {"found": False, "error": "Property document service returned an empty answer."}

    return {"found": True, "answer": answer, "device_id": device_id}
