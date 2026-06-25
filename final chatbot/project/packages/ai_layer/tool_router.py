import sys
sys.path.insert(0, "/app")

import json
from dataclasses import dataclass
from packages.ai_layer.tool_registry import registry
from packages.ai_layer.gateway import safe_invoke, MODEL, LLMServiceError
from langchain_core.messages import SystemMessage, HumanMessage


@dataclass
class ToolRouteResult:
    selected_tools: list[str]
    confidence: dict
    reasoning: str
    inputs: dict


def route(query: str, portal_id: str = "*") -> ToolRouteResult:
    available = registry.as_llm_schema(portal_id)
    if not available:
        return ToolRouteResult(selected_tools=[], confidence={}, reasoning="No tools registered.", inputs={})

    system = """You are a tool router. Given a user query and a list of available tools, decide which tool(s) to call.
Return ONLY a JSON object:
{
  "selected_tools": ["tool_name"],
  "confidence": {"tool_name": 0.95},
  "reasoning": "brief reason",
  "inputs": {"tool_name": {"param": "value"}}
}
Rules: only pick from the list, select multiple if needed, extract inputs from the query, return ONLY valid JSON."""

    prompt = f"Available tools:\n{json.dumps(available, indent=2)}\n\nUser query: {query}"
    chat_messages = [
        SystemMessage(content=system),
        HumanMessage(content=prompt)
    ]

    try:
        response = safe_invoke(chat_messages)
    except LLMServiceError:
        return ToolRouteResult(selected_tools=[], confidence={}, reasoning="Tool routing unavailable; skipping tools.", inputs={})

    raw = (response.content or "").strip().lstrip("```json").lstrip("```").rstrip("```").strip()

    try:
        parsed = json.loads(raw)
        return ToolRouteResult(
            selected_tools=parsed.get("selected_tools", []),
            confidence=parsed.get("confidence", {}),
            reasoning=parsed.get("reasoning", ""),
            inputs=parsed.get("inputs", {}),
        )
    except Exception:
        return ToolRouteResult(selected_tools=[], confidence={}, reasoning="Routing failed.", inputs={})


def execute_tools(route_result: ToolRouteResult, portal_id=None) -> dict:
    results = {}
    for tool_name in route_result.selected_tools:
        tool = registry.get(tool_name)
        if not tool or not tool.enabled:
            results[tool_name] = {"error": f"Tool '{tool_name}' unavailable."}
            continue
        try:
            results[tool_name] = tool.handler(route_result.inputs.get(tool_name, {}))
        except Exception as e:
            results[tool_name] = {"error": str(e)}
    return results