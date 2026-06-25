import sys
sys.path.insert(0, "/app")

import json
import logging
from langgraph.graph import StateGraph, END

from packages.shared.types import (
    OrchestratorState, ChatMessage, MessageRole,
    IntentResult, IntentType, AIResponse,
    GuardrailResult, EscalationResult,
)
from packages.shared.utils import split_multi_query, detect_escalation_triggers
from packages.ai_layer.guardrails import check_input, check_output
from packages.ai_layer.gateway import (
    call_llm, call_llm_for_rewrite,
    call_llm_for_faithfulness, call_llm_for_classify_and_route,
    LLMServiceError,
)
from packages.ai_layer.prompt_manager import build_prompt
from packages.ai_layer.task_executor import log_interaction, trigger_escalation
from packages.ai_layer.tool_loader import load_all_tools
# route() removed — tool dispatch now handled by call_llm_for_tool_dispatch in node_tool_router
from packages.ai_layer.tool_router import execute_tools
from services.cache import l1_store, l2_store

logger = logging.getLogger(__name__)

load_all_tools()

try:
    l2_store.init_db()
except Exception:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record_error(state: OrchestratorState, node_name: str, exc: Exception) -> None:
    logger.error("Node '%s' failed: %s", node_name, exc, exc_info=True)
    state.metadata.setdefault("errors", []).append({"node": node_name, "error": str(exc)})


def _rag_tool_result(tool_results: dict) -> dict | None:
    """Return the RAG result if it succeeded, else None."""
    result = tool_results.get("kiotel_dashboard_step_guide") or tool_results.get("kiotel_dashboard_rag")
    if result and result.get("found") and result.get("answer"):
        return result
    return None


def _build_tool_context(tool_results: dict) -> str:
    """Serialise non-RAG tool results for injection into the LLM system prompt."""
    relevant = {k: v for k, v in tool_results.items() if not _rag_tool_result({k: v})}
    return ("\n\nTool results:\n" + json.dumps(relevant, indent=2)) if relevant else ""


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def node_guardrail_input(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    try:
        result = check_input(state.current_input, portal_id=state.portal_id, user_role=state.user_role)
        state.guardrail_result = result
        if result.passed:
            state.sanitized_input = result.sanitized_input
    except Exception as e:
        _record_error(state, "guardrail_input", e)
        state.guardrail_result = GuardrailResult(passed=False, reason="Input validation failed due to an internal error.")
    return {"state": state}


def node_query_rewrite(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if not state.guardrail_result or not state.guardrail_result.passed:
        return {"state": state}
    try:
        if detect_escalation_triggers(state.sanitized_input):
            return {"state": state}
        l1_ctx = l1_store.summary(state.session_id, state.portal_id)
        state.metadata["l1_context"] = l1_ctx
        original_input = state.sanitized_input
        rewritten = call_llm_for_rewrite(original_input, l1_ctx)
        rewritten = (rewritten or "").strip()
        if rewritten and rewritten != original_input:
            state.metadata["original_input"] = original_input
            state.sanitized_input = rewritten
            state.metadata["query_rewrite_applied"] = True
    except Exception as e:
        _record_error(state, "query_rewrite", e)
    return {"state": state}


def node_l1_check(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if not state.guardrail_result or not state.guardrail_result.passed:
        return {"state": state}
    try:
        hit = l1_store.get(state.session_id, state.portal_id, state.sanitized_input)
        if hit:
            state.l1_hit = True
            state.final_response = AIResponse(
                content=hit["answer"],
                intent=IntentType(hit["intent"]),
                metadata={"cache": "l1"},
            )
    except Exception as e:
        _record_error(state, "l1_check", e)
    return {"state": state}


def node_l2_check(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if state.l1_hit:
        return {"state": state}
    try:
        if "l1_context" not in state.metadata:
            state.metadata["l1_context"] = l1_store.summary(state.session_id, state.portal_id)
        intent_guess = state.intent.primary_intent.value if state.intent else "general"
        hit = l2_store.get(state.sanitized_input, state.portal_id, state.frontend_version, intent_guess)
        if hit:
            state.l2_hit = True
            state.final_response = AIResponse(
                content=hit["answer"],
                intent=IntentType(hit["intent"]),
                metadata={"cache": "l2", "score": hit.get("score")},
            )
            l1_store.set(state.session_id, state.portal_id, state.sanitized_input, hit["answer"], hit["intent"])
    except Exception as e:
        _record_error(state, "l2_check", e)
    return {"state": state}


def node_detect_intent(data: dict) -> dict:
    """
    Kept as a lightweight escalation/multi-query pre-check using rules only.
    Full intent classification + routing now happens in node_tool_router via
    call_llm_for_classify_and_route — one smart LLM call that does both.
    """
    state: OrchestratorState = data["state"]
    if not state.guardrail_result or not state.guardrail_result.passed:
        return {"state": state}

    try:
        # Rule-based escalation check — no LLM needed
        escalation_reason = detect_escalation_triggers(state.sanitized_input)
        if escalation_reason:
            state.intent = IntentResult(
                primary_intent=IntentType.ESCALATION,
                entities={"trigger": escalation_reason},
            )
            return {"state": state}
    except Exception as e:
        _record_error(state, "detect_intent", e)

    # Defer full classification to node_tool_router
    state.intent = IntentResult(primary_intent=IntentType.GENERAL)
    return {"state": state}


def node_tool_router(data: dict) -> dict:
    """
    Brain of the orchestrator.

    One LLM call does classify + route together:
        greeting/escalation/chit_chat → no tools → LLM handles
        service_query                 → call matched service(s)
            RAG answered              → return directly, no extra LLM
            other tools               → LLM generates using tool context
        multi_query                   → split + route each sub-query independently

    Adding a new service: register it with a rich description in @register_tool.
    No other code changes needed — the LLM picks it up automatically.
    """
    from packages.ai_layer.tool_registry import registry

    state: OrchestratorState = data["state"]
    if not state.intent:
        return {"state": state}

    # Skip if escalation already detected by rule-based check
    if state.intent.primary_intent == IntentType.ESCALATION:
        state.metadata["tool_results"] = {}
        return {"state": state}

    # Build service schema — rich descriptions are what make routing smart
    services_schema = [
        {"name": t.name, "description": t.description}
        for t in registry.all_tools(state.portal_id)
    ]

    l1_ctx = state.metadata.get("l1_context", "")

    # ONE smart LLM call: classify intent + decide which services to call
    try:
        decision = call_llm_for_classify_and_route(
            state.sanitized_input,
            services_schema,
            history_context=l1_ctx,
        )
    except Exception as e:
        _record_error(state, "tool_router.classify", e)
        decision = {
            "query_type": "service_query",
            "services": [services_schema[0]["name"]] if services_schema else [],
            "is_multi_query": False,
            "sub_queries": [],
            "reasoning": f"Classifier error: {e}",
        }

    logger.info("classify_and_route: %s", decision)

    # Update intent based on what the LLM decided
    query_type = decision["query_type"]
    if query_type == "greeting":
        state.intent = IntentResult(primary_intent=IntentType.GREETING)
    elif query_type == "escalation":
        state.intent = IntentResult(primary_intent=IntentType.ESCALATION)
    elif query_type == "multi_query" or decision["is_multi_query"]:
        state.intent = IntentResult(
            primary_intent=IntentType.MULTI_QUERY,
            is_multi_query=True,
            sub_queries=decision["sub_queries"],
        )
    elif query_type == "chit_chat":
        state.intent = IntentResult(primary_intent=IntentType.GENERAL)
    else:
        state.intent = IntentResult(primary_intent=IntentType.GENERAL)

    state.metadata["tool_route"] = {
        "query_type": query_type,
        "selected_tools": decision["services"],
        "reasoning": decision["reasoning"],
        "is_chit_chat": query_type in ("greeting", "chit_chat"),
    }

    # No services needed → LLM handles it
    if query_type in ("greeting", "chit_chat") or not decision["services"]:
        state.metadata["tool_results"] = {}
        return {"state": state}

    # Multi-query → handled by node_handle_multi_query, skip tool execution here
    if state.intent.is_multi_query:
        state.metadata["tool_results"] = {}
        return {"state": state}

    # Execute selected services
    chat_history = [
        {"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content}
        for m in state.messages[-6:]
    ]
    tool_results = {}
    for service_name in decision["services"]:
        tool = registry.get(service_name)
        if not tool or not tool.enabled:
            tool_results[service_name] = {"error": f"Service '{service_name}' unavailable."}
            continue
        try:
            # Pass question + history — each tool uses what it needs
            inputs = {"question": state.sanitized_input, "chat_history": chat_history or None}
            tool_results[service_name] = tool.handler(inputs)
            logger.info("service %s result found=%s", service_name, tool_results[service_name].get("found"))
        except Exception as e:
            _record_error(state, f"tool_router.execute.{service_name}", e)
            tool_results[service_name] = {"error": str(e)}

    state.metadata["tool_results"] = tool_results
    return {"state": state}


def node_handle_escalation(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if not state.intent or state.intent.primary_intent != IntentType.ESCALATION:
        return {"state": state}
    reason = state.intent.entities.get("trigger", "unspecified")
    try:
        state.escalation = trigger_escalation(state, reason)
    except Exception as e:
        _record_error(state, "handle_escalation", e)
        state.escalation = EscalationResult(triggered=True, reason=reason, ticket_id="ESC-PENDING")
    return {"state": state}


def node_handle_multi_query(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if not state.intent or not state.intent.is_multi_query:
        return {"state": state}
    l1_ctx = state.metadata.get("l1_context", "")
    sub_responses = []
    from packages.ai_layer.tool_registry import registry
    services_schema = [{"name": t.name, "description": t.description} for t in registry.all_tools(state.portal_id)]

    for sub_q in state.intent.sub_queries:
        try:
            # Use unified classify+route for each sub-query
            decision = call_llm_for_classify_and_route(sub_q, services_schema, history_context=l1_ctx)
            sub_tools = {}

            if decision["query_type"] not in ("greeting", "chit_chat") and decision["services"]:
                chat_history = [
                    {"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content}
                    for m in state.messages[-6:]
                ]
                for tool_name in decision["services"]:
                    tool = registry.get(tool_name)
                    if tool and tool.enabled:
                        try:
                            sub_tools[tool_name] = tool.handler({"question": sub_q, "chat_history": chat_history or None})
                        except Exception as te:
                            sub_tools[tool_name] = {"error": str(te)}

            # RAG answered → use directly
            rag = _rag_tool_result(sub_tools)
            if rag:
                sub_responses.append(f"Q: {sub_q}\n{rag['answer']}")
                continue

            # Other tools or no tools → LLM generates
            tool_context = _build_tool_context(sub_tools)
            ctx = (f"\n\nSession context:\n{l1_ctx}" if l1_ctx else "") + tool_context
            response = call_llm(build_prompt(state.portal_id) + ctx, state.messages, sub_q)
            sub_responses.append(f"Q: {sub_q}\n{response}")
        except Exception as e:
            _record_error(state, f"handle_multi_query:{sub_q}", e)
            sub_responses.append(f"Q: {sub_q}\nI couldn't generate an answer for this part due to a temporary issue. Please try asking it again.")

    state.final_response = AIResponse(
        content="\n\n---\n\n".join(sub_responses),
        intent=IntentType.MULTI_QUERY,
        sub_responses=sub_responses,
        is_multi_query=True,
    )
    return {"state": state}


def node_generate_response(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if state.final_response:
        return {"state": state}

    if not state.guardrail_result or not state.guardrail_result.passed:
        state.final_response = AIResponse(
            content=f"I'm unable to process that request. {state.guardrail_result.reason if state.guardrail_result else 'Invalid input.'}",
            intent=IntentType.UNKNOWN,
        )
        return {"state": state}

    if state.escalation and state.escalation.triggered:
        ticket_msg = f"\n\nEscalation ticket created: {state.escalation.ticket_id}. Our team will reach out shortly."
        try:
            response = call_llm(
                build_prompt(state.portal_id), state.messages,
                f"User needs urgent help: {state.escalation.reason}. Be empathetic, tell them a ticket has been raised. Input: {state.sanitized_input}",
            )
        except Exception as e:
            _record_error(state, "generate_response.escalation", e)
            response = "I understand this is urgent, and I've raised a ticket for our team to follow up with you as soon as possible."
        state.final_response = AIResponse(content=response + ticket_msg, intent=IntentType.ESCALATION, escalation=state.escalation)
        return {"state": state}

    tool_results = state.metadata.get("tool_results", {})

    # --- RAG short-circuit: return RAG answer directly, no extra LLM call ---
    rag = _rag_tool_result(tool_results)
    if rag:
        state.final_response = AIResponse(
            content=rag["answer"],
            intent=state.intent.primary_intent if state.intent else IntentType.GENERAL,
            metadata={
                **state.metadata.get("tool_route", {}),
                "rag_query_used": rag.get("query_used"),
                "rag_sources": rag.get("source_documents", []),
            },
        )
        return {"state": state}

    # --- Normal LLM generation path (non-RAG tools or no tools) ---
    l1_ctx = state.metadata.get("l1_context", "")
    tool_context = _build_tool_context(tool_results)
    ctx = (f"\n\nSession context:\n{l1_ctx}" if l1_ctx else "") + tool_context
    system_prompt = build_prompt(state.portal_id) + ctx
    intent = state.intent.primary_intent if state.intent else IntentType.GENERAL
    try:
        response_text = call_llm(system_prompt, state.messages, state.sanitized_input)
    except Exception as e:
        _record_error(state, "generate_response", e)
        response_text = "I'm having trouble generating a response right now. Please try again in a moment, or let me know if you'd like to be connected with our support team."
    state.final_response = AIResponse(
        content=response_text,
        intent=intent,
        metadata=state.metadata.get("tool_route", {}),
    )
    return {"state": state}


def node_faithfulness_check(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if not state.final_response or state.l1_hit or state.l2_hit:
        return {"state": state}
    if state.final_response.intent in (IntentType.ESCALATION, IntentType.MULTI_QUERY, IntentType.UNKNOWN):
        return {"state": state}

    # RAG answers are already grounded at source — skip the extra judge call.
    tool_results = state.metadata.get("tool_results", {})
    if _rag_tool_result(tool_results):
        state.metadata["faithfulness"] = {"grounded": True, "reason": "Answer sourced directly from RAG pipeline."}
        return {"state": state}

    context_parts = []
    if tool_results:
        context_parts.append(json.dumps({k: v for k, v in tool_results.items() if k != "kiotel_dashboard_rag"}))

    grounding_context = "\n".join(context_parts).strip()
    if not grounding_context:
        return {"state": state}

    try:
        verdict = call_llm_for_faithfulness(state.final_response.content, grounding_context)
        state.metadata["faithfulness"] = verdict
        if not verdict.get("grounded", True):
            try:
                strict_prompt = build_prompt(state.portal_id) + \
                    "\n\nIMPORTANT: Only use facts explicitly present in the tool context above. Do not invent details."
                regenerated = call_llm(strict_prompt, state.messages, state.sanitized_input)
                state.final_response.content = regenerated
                state.metadata["faithfulness_retried"] = True
            except Exception as regen_e:
                _record_error(state, "faithfulness_check.regenerate", regen_e)
                state.metadata["faithfulness_flagged"] = True
    except Exception as e:
        _record_error(state, "faithfulness_check", e)
    return {"state": state}


def node_l2_write(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if not state.final_response or state.l1_hit or state.l2_hit:
        return {"state": state}
    cacheable = {IntentType.GENERAL, IntentType.GENERAL, IntentType.GENERAL}
    intent = state.final_response.intent
    if intent in cacheable:
        try:
            l2_store.set(state.sanitized_input, state.final_response.content, state.portal_id, state.frontend_version, intent.value)
            l1_store.set(state.session_id, state.portal_id, state.sanitized_input, state.final_response.content, intent.value)
        except Exception as e:
            _record_error(state, "l2_write", e)
    return {"state": state}


def node_guardrail_output(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if not state.final_response:
        return {"state": state}
    try:
        result = check_output(state.final_response.content)
        if not result.passed:
            state.final_response.content = "I encountered an issue generating a safe response. Please try rephrasing your question."
    except Exception as e:
        _record_error(state, "guardrail_output", e)
        state.final_response.content = "I encountered an issue generating a safe response. Please try rephrasing your question."
    return {"state": state}


def node_log(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    try:
        log_interaction(state)
    except Exception as e:
        logger.error("Failed to log interaction: %s", e, exc_info=True)
    return {"state": state}


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def route_after_guardrail(data: dict) -> str:
    state: OrchestratorState = data["state"]
    if not state.guardrail_result or not state.guardrail_result.passed:
        return "generate_response"
    return "query_rewrite"


def route_after_l1(data: dict) -> str:
    state: OrchestratorState = data["state"]
    if state.l1_hit:
        return "guardrail_output"
    return "l2_check"


def route_after_l2(data: dict) -> str:
    state: OrchestratorState = data["state"]
    if state.l2_hit:
        return "guardrail_output"
    return "detect_intent"


def route_after_intent(data: dict) -> str:
    state: OrchestratorState = data["state"]
    if not state.intent:
        return "generate_response"
    if state.intent.primary_intent == IntentType.ESCALATION:
        return "handle_escalation"
    return "tool_router"


def route_after_tool_router(data: dict) -> str:
    state: OrchestratorState = data["state"]
    if not state.intent:
        return "generate_response"
    if state.intent.primary_intent == IntentType.ESCALATION:
        return "handle_escalation"
    if state.intent.is_multi_query:
        return "handle_multi_query"
    return "generate_response"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(dict)

    graph.add_node("guardrail_input", node_guardrail_input)
    graph.add_node("query_rewrite", node_query_rewrite)
    graph.add_node("l1_check", node_l1_check)
    graph.add_node("l2_check", node_l2_check)
    graph.add_node("detect_intent", node_detect_intent)
    graph.add_node("tool_router", node_tool_router)
    graph.add_node("handle_escalation", node_handle_escalation)
    graph.add_node("handle_multi_query", node_handle_multi_query)
    graph.add_node("generate_response", node_generate_response)
    graph.add_node("faithfulness_check", node_faithfulness_check)
    graph.add_node("l2_write", node_l2_write)
    graph.add_node("guardrail_output", node_guardrail_output)
    graph.add_node("log", node_log)

    graph.set_entry_point("guardrail_input")

    graph.add_conditional_edges("guardrail_input", route_after_guardrail, {
        "query_rewrite": "query_rewrite",
        "generate_response": "generate_response",
    })
    graph.add_edge("query_rewrite", "l1_check")
    graph.add_conditional_edges("l1_check", route_after_l1, {
        "guardrail_output": "guardrail_output",
        "l2_check": "l2_check",
    })
    graph.add_conditional_edges("l2_check", route_after_l2, {
        "guardrail_output": "guardrail_output",
        "detect_intent": "detect_intent",
    })
    graph.add_conditional_edges("detect_intent", route_after_intent, {
        "handle_escalation": "handle_escalation",
        "tool_router": "tool_router",
        "generate_response": "generate_response",
    })
    graph.add_conditional_edges("tool_router", route_after_tool_router, {
        "handle_multi_query": "handle_multi_query",
        "generate_response": "generate_response",
    })

    graph.add_edge("handle_escalation", "generate_response")
    graph.add_edge("generate_response", "faithfulness_check")
    graph.add_edge("faithfulness_check", "l2_write")
    graph.add_edge("handle_multi_query", "l2_write")
    graph.add_edge("l2_write", "guardrail_output")
    graph.add_edge("guardrail_output", "log")
    graph.add_edge("log", END)

    return graph.compile(checkpointer=l1_store.get_checkpointer())


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def run_orchestrator(state: OrchestratorState) -> OrchestratorState:
    graph = get_graph()
    config = {"configurable": {"thread_id": f"{state.portal_id}:{state.session_id}"}}
    result = graph.invoke({"state": state}, config=config)
    return result["state"]