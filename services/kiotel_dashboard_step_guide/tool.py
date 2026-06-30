import sys
sys.path.insert(0, "/app")

import os
import logging
import httpx
import json

from packages.ai_layer.tool_registry import register_tool

logger = logging.getLogger(__name__)

RAG_BASE_URL = os.getenv("KIOTEL_RAG_URL", "http://localhost:8001")
RAG_TIMEOUT = float(os.getenv("KIOTEL_RAG_TIMEOUT", "180.0"))  # RAG uses heavy models, needs more time


def _call_rag(question: str, chat_history: list[dict] | None = None) -> dict:
    payload: dict = {"question": question}
    if chat_history:
        payload["chat_history"] = chat_history

    metadata = {}
    full_answer = ""
    blocked = False
    blocked_message = ""

    with httpx.Client(timeout=RAG_TIMEOUT) as client:
        with client.stream("POST", f"{RAG_BASE_URL}/query", json=payload) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                if event["type"] == "metadata":
                    metadata = event
                elif event["type"] == "chunk":
                    full_answer += event.get("text", "")
                elif event["type"] == "blocked":
                    blocked = True
                    blocked_message = event.get("message", "")
                    break

    if blocked:
        return {"blocked": True, "answer": blocked_message}

    return {
        "answer": full_answer,
        "source_documents": metadata.get("source_documents", []),
        "query_used": metadata.get("query_used", question),
        "blocked": False,
        "latency_ms": None,
    }


@register_tool(
    name="kiotel_dashboard_rag",
    description=(
        '''Kiotel Documentation RAG Assistant
           Use this tool to answer questions about the Kiotel Dashboard, Agent Dashboard, Admin Console,
           kiosk hardware, transactions, permissions, device control, troubleshooting, workflows, and system configuration.
           The tool retrieves relevant sections from the official Kiotel documentation and provides grounded answers based only on documented behavior.
           It can explain page functionality, buttons, workflows, permissions, troubleshooting steps, hardware operations, transaction requirements, control handoff procedures, and admin settings.

            Use this tool whenever the user asks:
                - How a Kiotel feature works
                - What a button, page, setting, or status means
                - Troubleshooting steps for dashboard or kiosk issues
                - Agent or admin workflows
                - Transaction, control, device, scanner, cash dispenser, printer, key dispenser, or video call behavior
                - Permissions and configuration questions

                Always answer using information retrieved from the documentation. 
                If the documentation does not contain the requested information, clearly state that the information is not documented.
                Example queries that SHOULD use this service:
                    'how to scan an ID', 'how to start a transaction', 
                    'how to dispense cash', 'Common status indicators'''
    ),
    keywords=[
        "kiotel", "dashboard", "report", "analytics", "configuration",
        "feature", "guide", "step", "setup", "user management", "widget",
        "metric", "export", "integration", "filter", "chart",
    ],
    intents=["knowledge_query", "step_guide", "general"],
    input_schema={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The user question to answer using the Kiotel RAG pipeline.",
            },
            "chat_history": {
                "type": "array",
                "description": "Optional prior turns as [{role, content}] for context-aware retrieval.",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string", "enum": ["user", "assistant"]},
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
            },
        },
        "required": ["question"],
    },
    portal_ids=["*"],
)
def handle_kiotel_rag(inputs: dict) -> dict:
    question = inputs.get("question", "").strip()
    if not question:
        return {"found": False, "error": "No question provided to kiotel_dashboard_rag tool."}

    chat_history = inputs.get("chat_history")

    try:
        data = _call_rag(question, chat_history)
    except httpx.HTTPStatusError as e:
        logger.error("kiotel_dashboard_rag HTTP error %s: %s", e.response.status_code, e)
        return {"found": False, "error": f"RAG service returned HTTP {e.response.status_code}."}
    except httpx.RequestError as e:
        logger.error("kiotel_dashboard_rag request error: %s", e)
        return {"found": False, "error": "RAG service unreachable."}

    if data.get("blocked"):
        return {"found": False, "blocked": True, "error": "Query was blocked by the RAG guardrail."}

    answer = (data.get("answer") or "").strip()
    if not answer:
        return {"found": False, "error": "RAG returned an empty answer."}

    return {
        "found": True,
        "answer": answer,
        "source_documents": data.get("source_documents", []),
        "query_used": data.get("query_used", question),
        "latency_ms": data.get("latency_ms"),
    }