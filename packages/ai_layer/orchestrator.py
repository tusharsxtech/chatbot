import sys
sys.path.insert(0, "/app")

import asyncio
import json
import logging
import os
import time
import functools
import httpx
from langgraph.graph import StateGraph, END

from packages.shared.types import (
    OrchestratorState, ChatMessage, MessageRole,
    IntentResult, IntentType, AIResponse,
    GuardrailResult, EscalationResult,
)
from packages.shared.utils import split_multi_query, detect_escalation_triggers
from packages.ai_layer.guardrails import check_input, check_output, OFF_TOPIC_REDIRECT_MESSAGE
from packages.ai_layer.gateway import (
    call_llm, call_llm_stream, call_llm_for_rewrite,
    call_llm_for_faithfulness, call_llm_for_classify_and_route,
    call_ollama_receptionist,
    LLMServiceError,
)
from packages.ai_layer.prompt_manager import build_prompt
from packages.ai_layer.task_executor import log_interaction, trigger_escalation
from packages.ai_layer.tool_loader import load_all_tools
from packages.ai_layer.tool_router import execute_tools
from packages.ai_layer.context_manager import get_safe_messages_for_llm, estimate_context_usage_pct
from services.cache import l1_store, l2_store

logger = logging.getLogger(__name__)

_RAG_BASE_URL = os.getenv("KIOTEL_RAG_URL", "http://localhost:8001")
_RAG_TIMEOUT = float(os.getenv("KIOTEL_RAG_TIMEOUT", "180.0"))
_DOC_CHAT_URL = os.getenv("DOC_CHAT_URL", "http://localhost:8000")
_DOC_CHAT_TIMEOUT = float(os.getenv("DOC_CHAT_TIMEOUT", "60.0"))

# Tools whose answer becomes the final response directly, bypassing LLM
# synthesis entirely (success or failure). kiotel_customer_module and
# kiotel_property_docs are additionally never cached — see _NO_CACHE_TOOLS.
_DIRECT_ANSWER_TOOLS = (
    "kiotel_dashboard_step_guide",
    "kiotel_dashboard_rag",
    "kiotel_customer_module",
    "kiotel_property_docs",
)


async def _stream_rag(question: str, chat_history: list | None = None):
    """Async generator — yields (token: str|None, meta: dict|None) from the RAG service SSE stream."""
    payload: dict = {"question": question}
    if chat_history:
        payload["chat_history"] = chat_history
    try:
        async with httpx.AsyncClient(timeout=_RAG_TIMEOUT) as client:
            async with client.stream("POST", f"{_RAG_BASE_URL}/query", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[len("data:"):].strip()
                    if raw == "[DONE]":
                        return
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if event["type"] == "chunk":
                        yield event.get("text", ""), None
                    elif event["type"] == "metadata":
                        yield None, event
                    elif event["type"] == "blocked":
                        yield None, {"blocked": True, "message": event.get("message", "")}
                        return
    except Exception as e:
        logger.error("_stream_rag failed: %s", e)
        yield None, {"error": str(e)}


async def _stream_workflow(question: str, device_id: str, user_role: str):
    """Async generator — yields (token: str|None, meta: dict|None) from the doc-chat-service SSE stream."""
    payload = {"query": question, "device_id": device_id, "user_role": user_role}
    try:
        async with httpx.AsyncClient(timeout=_DOC_CHAT_TIMEOUT) as client:
            async with client.stream("POST", f"{_DOC_CHAT_URL}/chat", json=payload) as resp:
                resp.raise_for_status()
                event_name = None
                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        event_name = line[len("event:"):].strip()
                        continue
                    if not line.startswith("data:"):
                        continue
                    raw = line[len("data:"):].strip()
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if event_name == "token":
                        yield event.get("content", ""), None
                    elif event_name == "error":
                        yield None, {"error": event.get("detail", "doc-chat service error")}
                        return
                    elif event_name == "done":
                        return
    except Exception as e:
        logger.error("_stream_workflow failed: %s", e)
        yield None, {"error": str(e)}


load_all_tools()

try:
    l2_store.init_db()
except Exception:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def timed_node(fn):
    @functools.wraps(fn)
    async def wrapper(data: dict) -> dict:
        t0 = time.perf_counter()
        result = await fn(data)
        logger.info("%s took %.0fms", fn.__name__, (time.perf_counter() - t0) * 1000)
        return result
    return wrapper

def _record_error(state: OrchestratorState, node_name: str, exc: Exception) -> None:
    logger.error("Node '%s' failed: %s", node_name, exc, exc_info=True)
    state.metadata.setdefault("errors", []).append({"node": node_name, "error": str(exc)})


def _direct_tool_result(tool_results: dict) -> dict | None:
    """Return the first successful direct-answer tool result (RAG, customer_module,
    property docs), else None. A failed direct-answer tool result is NOT
    returned here — it falls through to _build_tool_context so the LLM can
    still synthesize a fallback response referencing it."""
    for name in _DIRECT_ANSWER_TOOLS:
        result = tool_results.get(name)
        if result and result.get("found") and result.get("answer"):
            return result
    return None


def _build_tool_context(tool_results: dict) -> str:
    """Serialise non-direct-answer tool results for injection into the LLM system prompt."""
    relevant = {k: v for k, v in tool_results.items() if not _direct_tool_result({k: v})}
    return ("\n\nTool results:\n" + json.dumps(relevant, indent=2)) if relevant else ""


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------
@timed_node
async def node_guardrail_input(data: dict) -> dict:
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


@timed_node
async def node_query_rewrite(data: dict) -> dict:
    # Only sets l1_context for downstream nodes — LLM rewrite removed (was adding 20-25s per turn).
    # classify_and_route already receives l1_context so routing quality is unchanged.
    state: OrchestratorState = data["state"]
    if not state.guardrail_result or not state.guardrail_result.passed:
        return {"state": state}
    try:
        state.metadata["l1_context"] = l1_store.summary(state.session_id, state.portal_id)
    except Exception as e:
        _record_error(state, "query_rewrite", e)
    return {"state": state}

@timed_node
async def node_l1_check(data: dict) -> dict:
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

@timed_node
async def node_l2_check(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if state.l1_hit:
        return {"state": state}
    try:
        if "l1_context" not in state.metadata:
            state.metadata["l1_context"] = l1_store.summary(state.session_id, state.portal_id)
        intent_guess = state.intent.primary_intent.value if state.intent else "general"
        hit = await asyncio.to_thread(
            l2_store.get, state.sanitized_input, state.portal_id, state.frontend_version, intent_guess
        )
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

@timed_node
async def node_detect_intent(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if not state.guardrail_result or not state.guardrail_result.passed:
        return {"state": state}

    try:
        escalation_reason = detect_escalation_triggers(state.sanitized_input)
        if escalation_reason:
            state.intent = IntentResult(
                primary_intent=IntentType.ESCALATION,
                entities={"trigger": escalation_reason},
            )
            return {"state": state}
    except Exception as e:
        _record_error(state, "detect_intent", e)

    state.intent = IntentResult(primary_intent=IntentType.GENERAL)
    return {"state": state}


@timed_node
async def node_tool_router(data: dict) -> dict:
    from packages.ai_layer.tool_registry import registry

    state: OrchestratorState = data["state"]
    if not state.intent:
        return {"state": state}

    if state.intent.primary_intent == IntentType.ESCALATION:
        state.metadata["tool_results"] = {}
        return {"state": state}

    services_schema = registry.as_llm_schema(state.portal_id)
    l1_ctx = state.metadata.get("l1_context", "")
    chat_history = [
        {"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content}
        for m in state.messages[-6:]
    ]

    async def run_classify():
        try:
            return await call_llm_for_classify_and_route(
                state.sanitized_input, services_schema, history_context=l1_ctx
            )
        except Exception as e:
            _record_error(state, "tool_router.classify", e)
            return {
                "query_type": "service_query",
                "services": [services_schema[0]["name"]] if services_schema else [],
                "is_multi_query": False,
                "sub_queries": [],
                "reasoning": f"Classifier error: {e}",
            }

    decision = await run_classify()
    logger.info("classify_and_route: %s", decision)

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
    else:
        state.intent = IntentResult(primary_intent=IntentType.GENERAL)

    state.metadata["tool_route"] = {
        "query_type": query_type,
        "selected_tools": decision["services"],
        "reasoning": decision["reasoning"],
        "is_chit_chat": query_type in ("greeting", "chit_chat"),
    }

    if query_type in ("greeting", "chit_chat") or not decision["services"]:
        state.metadata["tool_results"] = {}
        return {"state": state}

    if state.intent.is_multi_query:
        state.metadata["tool_results"] = {}
        return {"state": state}

    # Direct-answer tools (RAG, customer_module, property docs) are NOT pre-fetched
    # here — streaming path pipes them directly in run_orchestrator_stream,
    # non-streaming path fetches them in node_generate_response.
    non_rag_services = [s for s in decision["services"] if s not in _DIRECT_ANSWER_TOOLS]

    async def _call_service(service_name: str):
        tool = registry.get(service_name)
        if not tool or not tool.enabled:
            return service_name, {"error": f"Service '{service_name}' unavailable."}
        try:
            inputs = {"question": state.sanitized_input, "chat_history": chat_history or None}
            result = await asyncio.to_thread(tool.handler, inputs)
            logger.info("service %s result found=%s", service_name, result.get("found"))
            return service_name, result
        except Exception as e:
            _record_error(state, f"tool_router.execute.{service_name}", e)
            return service_name, {"error": str(e)}

    tool_results = {}
    if non_rag_services:
        service_results = await asyncio.gather(*[_call_service(s) for s in non_rag_services])
        for name, result in service_results:
            tool_results[name] = result

    state.metadata["tool_results"] = tool_results
    return {"state": state}

@timed_node
async def node_handle_escalation(data: dict) -> dict:
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

@timed_node
async def node_handle_multi_query(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if not state.intent or not state.intent.is_multi_query:
        return {"state": state}

    l1_ctx = state.metadata.get("l1_context", "")
    from packages.ai_layer.tool_registry import registry
    services_schema = [{"name": t.name, "description": t.description} for t in registry.all_tools(state.portal_id)]
    chat_history = [
        {"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content}
        for m in state.messages[-6:]
    ]

    async def _process_sub_query(sub_q: str) -> str:
        try:
            decision = await call_llm_for_classify_and_route(sub_q, services_schema, history_context=l1_ctx)
            if decision["query_type"] == "chit_chat":
                return OFF_TOPIC_REDIRECT_MESSAGE
            if decision["query_type"] == "greeting":
                return await call_ollama_receptionist(sub_q, state.messages)

            sub_tools = {}
            if decision["query_type"] not in ("greeting", "chit_chat") and decision["services"]:
                async def _call_sub_tool(tool_name: str):
                    tool = registry.get(tool_name)
                    if tool and tool.enabled:
                        try:
                            return tool_name, await asyncio.to_thread(
                                tool.handler,
                                {
                                    "question": sub_q,
                                    "chat_history": chat_history or None,
                                    "device_id": state.device_id,
                                    "user_role": state.user_role,
                                },
                            )
                        except Exception as te:
                            return tool_name, {"error": str(te)}
                    return tool_name, None

                tool_results = await asyncio.gather(*[_call_sub_tool(t) for t in decision["services"]])
                sub_tools = {name: res for name, res in tool_results if res is not None}

            direct = _direct_tool_result(sub_tools)
            if direct:
                return direct["answer"]
            tool_context = _build_tool_context(sub_tools)
            ctx = (f"\n\nSession context:\n{l1_ctx}" if l1_ctx else "") + tool_context
            response = await call_llm(build_prompt(state.portal_id) + ctx, state.messages, sub_q)
            return response
        except Exception as e:
            logger.error("handle_multi_query sub_q='%s' failed: %s", sub_q, e, exc_info=True)
            return "I couldn't generate an answer for this part due to a temporary issue. Please try asking it again."

    sub_queries = state.intent.sub_queries
    sub_answers = list(await asyncio.gather(*[_process_sub_query(sq) for sq in sub_queries]))

    state.final_response = AIResponse(
        content="\n\n".join(sub_answers),
        intent=IntentType.MULTI_QUERY,
        sub_responses=sub_answers,
        is_multi_query=True,
    )
    return {"state": state}

@timed_node
async def node_generate_response(data: dict) -> dict:
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
            response = await call_llm(
                build_prompt(state.portal_id), state.messages,
                f"User needs urgent help: {state.escalation.reason}. Be empathetic, tell them a ticket has been raised. Input: {state.sanitized_input}",
            )
        except Exception as e:
            _record_error(state, "generate_response.escalation", e)
            response = "I understand this is urgent, and I've raised a ticket for our team to follow up with you as soon as possible."
        state.final_response = AIResponse(content=response + ticket_msg, intent=IntentType.ESCALATION, escalation=state.escalation)
        return {"state": state}

    tool_results = state.metadata.get("tool_results", {})
    selected = state.metadata.get("tool_route", {}).get("selected_tools", [])

    # Fetch direct-answer tools here for the non-streaming path (streaming
    # path handles them in run_orchestrator_stream).
    if any(name in selected and tool_results.get(name) is None for name in _DIRECT_ANSWER_TOOLS):
        from packages.ai_layer.tool_registry import registry
        chat_history_ctx = [
            {"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content}
            for m in state.messages[-6:]
        ]

        async def _fetch_direct(tool_name: str, inputs: dict) -> None:
            tool = registry.get(tool_name)
            if not tool or not tool.enabled:
                return
            try:
                tool_results[tool_name] = await asyncio.to_thread(tool.handler, inputs)
            except Exception as e:
                _record_error(state, f"generate_response.{tool_name}", e)

        if "kiotel_dashboard_rag" in selected and tool_results.get("kiotel_dashboard_rag") is None:
            await _fetch_direct(
                "kiotel_dashboard_rag",
                {"question": state.sanitized_input, "chat_history": chat_history_ctx or None},
            )
        if "kiotel_customer_module" in selected and tool_results.get("kiotel_customer_module") is None:
            await _fetch_direct(
                "kiotel_customer_module",
                {"question": state.sanitized_input, "user_role": state.user_role},
            )
        if "kiotel_property_docs" in selected and tool_results.get("kiotel_property_docs") is None:
            await _fetch_direct(
                "kiotel_property_docs",
                {"question": state.sanitized_input, "device_id": state.device_id, "user_role": state.user_role},
            )

        state.metadata["tool_results"] = tool_results

    direct = _direct_tool_result(tool_results)
    if direct:
        extra_meta = {}
        if direct.get("query_used") is not None:
            extra_meta["rag_query_used"] = direct.get("query_used")
        if direct.get("source_documents") is not None:
            extra_meta["rag_sources"] = direct.get("source_documents", [])
        if direct.get("sql") is not None:
            extra_meta["sql"] = direct.get("sql")
        if direct.get("device_id") is not None:
            extra_meta["device_id"] = direct.get("device_id")
        state.final_response = AIResponse(
            content=direct["answer"],
            intent=state.intent.primary_intent if state.intent else IntentType.GENERAL,
            metadata={**state.metadata.get("tool_route", {}), **extra_meta},
        )
        return {"state": state}

    intent = state.intent.primary_intent if state.intent else IntentType.GENERAL

    query_type = state.metadata.get("tool_route", {}).get("query_type")
    if query_type == "chit_chat":
        # Off-topic — no Kiotel service matched. Never sent to an LLM: the
        # receptionist persona prompt alone doesn't reliably stop a small
        # local model from just answering general-knowledge questions.
        state.final_response = AIResponse(
            content=OFF_TOPIC_REDIRECT_MESSAGE,
            intent=intent,
            metadata=state.metadata.get("tool_route", {}),
        )
        return {"state": state}

    if query_type == "greeting":
        try:
            response_text = await call_ollama_receptionist(state.sanitized_input, state.messages)
        except Exception as e:
            _record_error(state, "generate_response.receptionist", e)
            response_text = "I'm here to help with Kiotel's dashboard and tools — could you tell me what you'd like help with?"
        state.final_response = AIResponse(
            content=response_text,
            intent=intent,
            metadata=state.metadata.get("tool_route", {}),
        )
        return {"state": state}

    l1_ctx = state.metadata.get("l1_context", "")
    tool_context = _build_tool_context(tool_results)
    ctx = (f"\n\nSession context:\n{l1_ctx}" if l1_ctx else "") + tool_context
    system_prompt = build_prompt(state.portal_id) + ctx

    safe_messages, conv_summary = await get_safe_messages_for_llm(
        state.messages, system_prompt, call_llm, state.session_id
    )
    if conv_summary:
        system_prompt += f"\n\n--- CONVERSATION SUMMARY (earlier context) ---\n{conv_summary}\n---"
        pct = estimate_context_usage_pct(state.messages, system_prompt)
        logger.warning("Context managed at %.0f%% — using summarized history", pct * 100)

    try:
        response_text = await call_llm(system_prompt, safe_messages, state.sanitized_input)
    except Exception as e:
        _record_error(state, "generate_response", e)
        response_text = "I'm having trouble generating a response right now. Please try again in a moment, or let me know if you'd like to be connected with our support team."
    state.final_response = AIResponse(
        content=response_text,
        intent=intent,
        metadata=state.metadata.get("tool_route", {}),
    )
    return {"state": state}


# Phrases that indicate a failed/fallback response — never cache these
_FALLBACK_PHRASES = [
    "rag service",
    "temporarily unavailable",
    "try again",
    "couldn't process",
    "having trouble",
    "internal error",
    "unreachable",
    "service outage",
    "couldn't generate",
    "i apologize",
    "please try again",
    "escalate this",
    "cannot access",
    "don't have information",
    "unable to process",
]


# Tools whose answers are never cached — customer_module reflects live DB
# state and property-docs answers are scoped to a specific device_id, so a
# cached answer could serve stale data or leak across devices/sessions.
_NO_CACHE_TOOLS = {"kiotel_customer_module", "kiotel_property_docs"}


def _is_cacheable_response(response_text: str, tool_results: dict) -> bool:
    if not response_text or len(response_text.strip()) < 20:
        return False

    if _NO_CACHE_TOOLS & tool_results.keys():
        return False

    lower = response_text.lower()
    for phrase in _FALLBACK_PHRASES:
        if phrase in lower:
            return False

    rag_result = tool_results.get("kiotel_dashboard_rag")
    if rag_result is not None and not rag_result.get("found", False):
        return False

    return True


@timed_node
async def node_l2_write(data: dict) -> dict:
    state: OrchestratorState = data["state"]
    if not state.final_response or state.l1_hit or state.l2_hit:
        return {"state": state}

    tool_results = state.metadata.get("tool_results", {})
    response_text = state.final_response.content
    intent = state.final_response.intent

    if not _is_cacheable_response(response_text, tool_results):
        logger.info("Skipping cache write — response is fallback or RAG failed")
        return {"state": state}

    cacheable_intents = {IntentType.GENERAL, IntentType.SERVICE_QUERY}
    if intent not in cacheable_intents:
        return {"state": state}

    try:
        await asyncio.to_thread(
            l2_store.set, state.sanitized_input, response_text, state.portal_id, state.frontend_version, intent.value
        )
        l1_store.set(state.session_id, state.portal_id, state.sanitized_input, response_text, intent.value)
        logger.info("Cached response for query: %s", state.sanitized_input[:50])
    except Exception as e:
        _record_error(state, "l2_write", e)
    return {"state": state}

@timed_node
async def node_log(data: dict) -> dict:
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
        return "l2_write"
    return "l2_check"


def route_after_l2(data: dict) -> str:
    state: OrchestratorState = data["state"]
    if state.l2_hit:
        return "l2_write"
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
    graph.add_node("l2_write", node_l2_write)
    graph.add_node("log", node_log)

    graph.set_entry_point("guardrail_input")

    graph.add_conditional_edges("guardrail_input", route_after_guardrail, {
        "query_rewrite": "query_rewrite",
        "generate_response": "generate_response",
    })
    graph.add_edge("query_rewrite", "l1_check")
    graph.add_conditional_edges("l1_check", route_after_l1, {
        "l2_write": "l2_write",
        "l2_check": "l2_check",
    })
    graph.add_conditional_edges("l2_check", route_after_l2, {
        "l2_write": "l2_write",
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
    graph.add_edge("generate_response", "l2_write")
    graph.add_edge("handle_multi_query", "l2_write")
    graph.add_edge("l2_write", "log")
    graph.add_edge("log", END)

    return graph.compile(checkpointer=l1_store.get_checkpointer())


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


async def run_orchestrator(state: OrchestratorState) -> OrchestratorState:
    t0 = time.perf_counter()
    graph = get_graph()
    config = {"configurable": {"thread_id": f"{state.portal_id}:{state.session_id}"}}
    result = await graph.ainvoke({"state": state}, config=config)
    logger.info("run_orchestrator TOTAL took %.0fms", (time.perf_counter() - t0) * 1000)
    return result["state"]


async def run_orchestrator_stream(state: OrchestratorState):
    """
    Async generator — true token streaming.

    Phase 1: run the graph up to (but not including) generate_response.
             This covers guardrail → rewrite → cache checks → intent → tool_router.
             Metadata is yielded as soon as routing is done.
    Phase 2: stream the final LLM response token-by-token (or yield cached/RAG answer).
    Phase 3: fire-and-forget post-processing (l2_write + log).
    """
    t0 = time.perf_counter()
    graph = get_graph()
    config = {"configurable": {"thread_id": f"{state.portal_id}:{state.session_id}"}}

    # ── Phase 1: routing ───────────────────────────────────────────────────────
    partial_result = await graph.ainvoke(
        {"state": state},
        config=config,
        interrupt_before=["generate_response"],
    )
    ps: OrchestratorState = partial_result["state"]

    guardrail_blocked = bool(ps.guardrail_result and not ps.guardrail_result.passed)
    yield json.dumps({
        "type": "metadata",
        "session_id": state.session_id,
        "guardrail_blocked": guardrail_blocked,
        "l1_hit": ps.l1_hit,
        "l2_hit": ps.l2_hit,
        "intent": ps.intent.primary_intent.value if ps.intent else "unknown",
    })

    # ── Phase 2: generate / stream ─────────────────────────────────────────────
    tool_results = ps.metadata.get("tool_results", {})
    full_response: str = ""
    final_intent = ps.intent.primary_intent if ps.intent else IntentType.GENERAL
    final_metadata: dict = ps.metadata.get("tool_route", {})

    if ps.final_response:
        # l1 / l2 cache hit — already have the answer, stream word-by-word
        full_response = ps.final_response.content
        for word in full_response.split(" "):
            yield json.dumps({"type": "chunk", "text": word + " "})

    elif guardrail_blocked:
        reason = ps.guardrail_result.reason if ps.guardrail_result else "Invalid input."
        full_response = f"I'm unable to process that request. {reason}"
        yield json.dumps({"type": "chunk", "text": full_response})
        final_intent = IntentType.UNKNOWN

    elif ps.escalation and ps.escalation.triggered:
        ticket_msg = f"\n\nEscalation ticket created: {ps.escalation.ticket_id}. Our team will reach out shortly."
        prompt = f"User needs urgent help: {ps.escalation.reason}. Be empathetic, tell them a ticket has been raised. Input: {ps.sanitized_input}"
        try:
            parts = []
            async for token in call_llm_stream(build_prompt(ps.portal_id), ps.messages, prompt):
                parts.append(token)
                yield json.dumps({"type": "chunk", "text": token})
            full_response = "".join(parts) + ticket_msg
        except Exception:
            full_response = "I understand this is urgent, and I've raised a ticket for our team." + ticket_msg
            yield json.dumps({"type": "chunk", "text": full_response})
        final_intent = IntentType.ESCALATION

    else:
        selected_tools = ps.metadata.get("tool_route", {}).get("selected_tools", [])
        rag_selected = "kiotel_dashboard_rag" in selected_tools

        if rag_selected:
            # True RAG streaming — pipe tokens directly from RAG service as they arrive
            chat_history_for_rag = [
                {"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content}
                for m in ps.messages[-6:]
            ]
            parts = []
            try:
                async for token, meta in _stream_rag(ps.sanitized_input, chat_history_for_rag or None):
                    if token:
                        parts.append(token)
                        yield json.dumps({"type": "chunk", "text": token})
                    elif meta:
                        if meta.get("blocked") or meta.get("error"):
                            break
                        final_metadata.update({
                            "rag_query_used": meta.get("query_used"),
                            "rag_sources": meta.get("source_documents", []),
                        })
            except Exception as e:
                logger.error("RAG streaming failed: %s", e)
            if not parts:
                fallback = "I'm having trouble retrieving that information right now. Please try again."
                parts = [fallback]
                yield json.dumps({"type": "chunk", "text": fallback})
            full_response = "".join(parts)
            final_intent = ps.intent.primary_intent if ps.intent else IntentType.GENERAL

        elif "kiotel_customer_module" in selected_tools:
            # customer_module has no token stream (single blocking /ask call) —
            # fetch the full answer async, then stream it word-by-word.
            from packages.ai_layer.tool_registry import registry as _registry
            tool = _registry.get("kiotel_customer_module")
            try:
                result = (
                    await asyncio.to_thread(
                        tool.handler, {"question": ps.sanitized_input, "user_role": ps.user_role}
                    )
                    if tool and tool.enabled else {"found": False, "error": "Tool unavailable."}
                )
            except Exception as e:
                logger.error("customer_module fetch failed: %s", e)
                result = {"found": False, "error": str(e)}
            tool_results["kiotel_customer_module"] = result
            if result.get("found") and result.get("answer"):
                full_response = result["answer"]
                if result.get("sql") is not None:
                    final_metadata["sql"] = result.get("sql")
            else:
                full_response = "I couldn't retrieve that data right now. Please try again or rephrase your question."
            for word in full_response.split(" "):
                yield json.dumps({"type": "chunk", "text": word + " "})
            final_intent = ps.intent.primary_intent if ps.intent else IntentType.GENERAL

        elif "kiotel_property_docs" in selected_tools:
            tool_results.setdefault("kiotel_property_docs", {"found": False})
            if not ps.device_id:
                full_response = "I need to know which device/property you're asking about to check its documents."
                yield json.dumps({"type": "chunk", "text": full_response})
            else:
                parts = []
                error_meta = None
                try:
                    async for token, meta in _stream_workflow(ps.sanitized_input, ps.device_id, ps.user_role):
                        if token:
                            parts.append(token)
                            yield json.dumps({"type": "chunk", "text": token})
                        elif meta:
                            error_meta = meta
                            break
                except Exception as e:
                    logger.error("Property docs streaming failed: %s", e)
                    error_meta = {"error": str(e)}
                if not parts:
                    fallback = "I couldn't find an answer in this device's property documents. Please try again."
                    parts = [fallback]
                    yield json.dumps({"type": "chunk", "text": fallback})
                full_response = "".join(parts)
                tool_results["kiotel_property_docs"] = {
                    "found": bool(parts and not error_meta),
                    "answer": full_response,
                    "device_id": ps.device_id,
                }
                final_metadata["device_id"] = ps.device_id
            final_intent = ps.intent.primary_intent if ps.intent else IntentType.GENERAL

        elif ps.metadata.get("tool_route", {}).get("query_type") == "chit_chat":
            # Off-topic — no Kiotel service matched. Deterministic redirect,
            # never sent to an LLM (see node_generate_response for why).
            full_response = OFF_TOPIC_REDIRECT_MESSAGE
            for word in full_response.split(" "):
                yield json.dumps({"type": "chunk", "text": word + " "})

        elif ps.metadata.get("tool_route", {}).get("query_type") == "greeting":
            # Greeting / on-topic small talk — guardrailed receptionist (free Ollama,
            # paid-LLM fallback on breaker-open), no dedicated streaming path since replies are short.
            try:
                receptionist_reply = await call_ollama_receptionist(ps.sanitized_input, ps.messages)
            except Exception as e:
                logger.error("Receptionist failed: %s", e)
                receptionist_reply = "I'm here to help with Kiotel's dashboard and tools — could you tell me what you'd like help with?"
            for word in receptionist_reply.split(" "):
                yield json.dumps({"type": "chunk", "text": word + " "})
            full_response = receptionist_reply

        else:
            # No RAG — stream LLM generation token by token
            l1_ctx = ps.metadata.get("l1_context", "")
            tool_context = _build_tool_context(tool_results)
            ctx = (f"\n\nSession context:\n{l1_ctx}" if l1_ctx else "") + tool_context
            system_prompt = build_prompt(ps.portal_id) + ctx

            safe_messages, conv_summary = await get_safe_messages_for_llm(
                ps.messages, system_prompt, call_llm, ps.session_id
            )
            if conv_summary:
                system_prompt += f"\n\n--- CONVERSATION SUMMARY (earlier context) ---\n{conv_summary}\n---"

            parts = []
            try:
                async for token in call_llm_stream(system_prompt, safe_messages, ps.sanitized_input):
                    parts.append(token)
                    yield json.dumps({"type": "chunk", "text": token})
            except Exception as e:
                logger.error("Streaming generation failed: %s", e)
                fallback = "I'm having trouble generating a response right now. Please try again."
                parts = [fallback]
                yield json.dumps({"type": "chunk", "text": fallback})
            full_response = "".join(parts)

    # ── Phase 3: post-process (cache write + log) in background ───────────────
    ps.final_response = AIResponse(
        content=full_response,
        intent=final_intent,
        metadata=final_metadata,
    )

    async def _post_process():
        try:
            if not ps.l1_hit and not ps.l2_hit and _is_cacheable_response(full_response, tool_results):
                if final_intent in {IntentType.GENERAL, IntentType.SERVICE_QUERY}:
                    await asyncio.to_thread(
                        l2_store.set, ps.sanitized_input, full_response,
                        ps.portal_id, ps.frontend_version, final_intent.value,
                    )
                    l1_store.set(ps.session_id, ps.portal_id, ps.sanitized_input, full_response, final_intent.value)
            log_interaction(ps)
        except Exception as e:
            logger.error("Post-process failed: %s", e)

    asyncio.create_task(_post_process())
    logger.info("run_orchestrator_stream TOTAL took %.0fms", (time.perf_counter() - t0) * 1000)
