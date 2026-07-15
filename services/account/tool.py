import sys
sys.path.insert(0, "/app")

# registers account info and usage stats as tools — kiotel_chatbot only

from packages.ai_layer.tool_registry import register_tool
from services.account.service import get_account_info, get_usage


@register_tool(
    name="get_account_info",
    description="Retrieve account details info for a user.",
    keywords=["account id", "name", "attempts"],
    intents=["knowledge_query", "general"],
    input_schema={"email": "string"},
    portal_ids=["kiotel_chatbot"],
)
def get_account_info_tool(inputs: dict) -> dict:
    return get_account_info(inputs.get("email", ""))


@register_tool(
    name="get_usage_stats",
    description="Get current usage statistics like API calls and storage consumed for a user account.",
    keywords=["usage", "quota", "api calls", "storage", "limit", "consumed", "stats"],
    intents=["knowledge_query"],
    input_schema={"email": "string"},
    portal_ids=["kiotel_chatbot"],
)
def get_usage_stats_tool(inputs: dict) -> dict:
    return get_usage(inputs.get("email", ""))