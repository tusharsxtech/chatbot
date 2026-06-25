import sys
sys.path.insert(0, "/app")

from dataclasses import dataclass, field
from typing import Callable, Any, Optional


@dataclass
class ToolDefinition:
    name: str
    description: str
    keywords: list[str]
    intents: list[str]
    handler: Callable[[dict], Any]
    input_schema: dict = field(default_factory=dict)
    enabled: bool = True
    portal_ids: list[str] = field(default_factory=lambda: ["*"])


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def all_tools(self, portal_id: str = None) -> list[ToolDefinition]:
        tools = [t for t in self._tools.values() if t.enabled]
        if portal_id:
            tools = [t for t in tools if "*" in t.portal_ids or portal_id in t.portal_ids]
        return tools

    def as_llm_schema(self, portal_id: str = None) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "keywords": t.keywords, "intents": t.intents}
            for t in self.all_tools(portal_id)
        ]


# singleton registry instance used by all tools and the router
registry = ToolRegistry()


def register_tool(name, description, keywords, intents, input_schema=None, portal_ids=None):
    # decorator — wraps a handler function and registers it into the global registry
    def decorator(fn: Callable):
        registry.register(ToolDefinition(
            name=name,
            description=description,
            keywords=keywords,
            intents=intents,
            handler=fn,
            input_schema=input_schema or {},
            portal_ids=portal_ids or ["*"],
        ))
        return fn
    return decorator