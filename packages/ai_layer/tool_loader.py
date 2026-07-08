


import sys
sys.path.insert(0, "/app")

import importlib

_loaded = False

# kiotel_dashboard_rag.tool replaces them as the primary retrieval tool.
# Add further service tools below as the project grows.
TOOL_MODULES = [
    "services.ticket.tool",
    "services.account.tool",
    "services.kiotel_dashboard_step_guide.tool",
    "services.customer_module.tool",
    "services.workflow.tool",
]


def load_all_tools() -> None:
    global _loaded
    if _loaded:
        return
    for module_path in TOOL_MODULES:
        try:
            importlib.import_module(module_path)
        except Exception as e:
            print(f"[tool_loader] Failed to load {module_path}: {e}")
    _loaded = True