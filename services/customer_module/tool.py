import sys
sys.path.insert(0, "/app")

# registers customer_module (QueryWeaver — natural-language -> SQL -> Postgres)
# as a tool — answers live-data questions directly, bypassing LLM synthesis.
# Never cached (see packages/ai_layer/orchestrator.py _NO_CACHE_TOOLS): results
# reflect the current DB state and can change between identical questions.

import os
import logging
import httpx

from packages.ai_layer.tool_registry import register_tool

logger = logging.getLogger(__name__)

CUSTOMER_MODULE_URL = os.getenv("CUSTOMER_MODULE_URL", "http://localhost:8000")
CUSTOMER_MODULE_TIMEOUT = float(os.getenv("CUSTOMER_MODULE_TIMEOUT", "60.0"))
CUSTOMER_MODULE_API_KEY = os.getenv("CUSTOMER_MODULE_API_KEY", "")
CUSTOMER_MODULE_MAX_ROWS = int(os.getenv("CUSTOMER_MODULE_MAX_ROWS", "20"))

# Compulsory access gate — only these session user_roles may use this tool.
_ALLOWED_ROLES = {"admin", "customer"}


def _format_rows(rows: list[dict]) -> str:
    if not rows:
        return "No matching records found."

    shown = rows[:CUSTOMER_MODULE_MAX_ROWS]
    lines = ["- " + ", ".join(f"{k}: {v}" for k, v in row.items()) for row in shown]
    text = "\n".join(lines)
    if len(rows) > len(shown):
        text += f"\n... and {len(rows) - len(shown)} more row(s)."
    return text


def _call_customer_module(question: str) -> dict:
    headers = {"X-API-Key": CUSTOMER_MODULE_API_KEY} if CUSTOMER_MODULE_API_KEY else {}
    with httpx.Client(timeout=CUSTOMER_MODULE_TIMEOUT) as client:
        resp = client.post(
            f"{CUSTOMER_MODULE_URL}/ask",
            json={"question": question, "execute": True},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


@register_tool(
    name="kiotel_customer_module",
    description=(
        '''Kiotel Live Data Query Assistant (customer_module / QueryWeaver)
           Use this tool to answer questions that need REAL, CURRENT data from the Kiotel
           business database — counts, lists, statuses, and records for devices, accounts,
           transactions, licenses, tickets, and similar entities. It converts the question
           into a read-only SQL query, runs it, and returns the matching rows.

           Use this tool whenever the user asks for actual data rather than documentation, e.g.:
               'how many devices are currently licensed', 'list active transactions today',
               'show me accounts created this month', 'what is the status of device X'.

           Do NOT use this tool for how-to / feature-explanation questions — use the
           documentation RAG tool for those instead.'''
    ),
    keywords=[
        "how many", "list", "show me", "count", "total", "active", "status of",
        "devices", "accounts", "transactions", "licenses", "records", "data", "query",
    ],
    intents=["knowledge_query", "service_query", "general"],
    input_schema={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The natural-language data question to convert into SQL and run.",
            },
        },
        "required": ["question"],
    },
    portal_ids=["*"],
)
def handle_customer_module(inputs: dict) -> dict:
    user_role = inputs.get("user_role")
    if user_role not in _ALLOWED_ROLES:
        return {"found": False, "error": "Not authorized to use the customer_module tool."}

    question = (inputs.get("question") or "").strip()
    if not question:
        return {"found": False, "error": "No question provided to kiotel_customer_module tool."}

    try:
        data = _call_customer_module(question)
    except httpx.HTTPStatusError as e:
        logger.error("kiotel_customer_module HTTP error %s: %s", e.response.status_code, e)
        return {"found": False, "error": f"customer_module service returned HTTP {e.response.status_code}."}
    except httpx.RequestError as e:
        logger.error("kiotel_customer_module request error: %s", e)
        return {"found": False, "error": "customer_module service unreachable."}

    if data.get("error"):
        return {
            "found": False,
            "error": data["error"],
            "sql": data.get("generated_sql") or data.get("sql"),
        }

    rows = data.get("rows")
    if rows is None:
        return {"found": False, "error": "customer_module did not return any rows."}

    return {
        "found": True,
        "answer": _format_rows(rows),
        "rows": rows,
        "sql": data.get("sql"),
    }
