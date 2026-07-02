import sys
sys.path.insert(0, "/app")

import os
import time
import uuid
import logging
import threading
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import StreamingResponse
import json
from pydantic import BaseModel
from typing import Optional

from packages.shared.types import OrchestratorState, ChatMessage, MessageRole, IntentType
from packages.ai_layer.orchestrator import run_orchestrator_stream
from services.cache.l2_store import stats as l2_stats, invalidate_version
from services.cache.warmer import warm

logger = logging.getLogger(__name__)

app = FastAPI(title="Portal A - Intelligent Chatbot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



_static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_path), name="static")

PORTAL_ID = "portal_a"
_sessions: dict[str, list[ChatMessage]] = {}

RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("CHAT_RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("CHAT_RATE_LIMIT_MAX_REQUESTS", "20"))
_rate_limit_buckets: dict[str, deque] = defaultdict(deque)
_rate_limit_lock = threading.Lock()


def _check_rate_limit(key: str) -> bool:
    now = time.time()
    with _rate_limit_lock:
        bucket = _rate_limit_buckets[key]
        while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
            return False
        bucket.append(now)
        return True


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_role: Optional[str] = "user"
    frontend_version: Optional[str] = "v1"


class WarmRequest(BaseModel):
    old_version: str
    new_version: str
    top_k: Optional[int] = 50


class EscalationResponse(BaseModel):
    triggered: bool
    ticket_id: Optional[str] = None
    reason: str = ""


class ChatResponse(BaseModel):
    session_id: str
    response: str
    intent: str
    is_multi_query: bool
    escalation: Optional[EscalationResponse] = None
    sub_responses: list[str] = []
    guardrail_blocked: bool = False
    l1_hit: bool = False
    l2_hit: bool = False
    frontend_version: str = "v1"


@app.get("/", response_class=HTMLResponse)
async def root():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html")) as f:
        return HTMLResponse(content=f.read())


# @app.post("/chat", response_model=ChatResponse)
# async def chat(req: ChatRequest, request: Request):
#     if not req.message or not req.message.strip():
#         raise HTTPException(status_code=400, detail="Message cannot be empty.")

#     client_ip = request.client.host if request.client else "unknown"
#     if not _check_rate_limit(client_ip):
#         raise HTTPException(status_code=429, detail="Too many requests. Please slow down and try again shortly.")

#     session_id = req.session_id or str(uuid.uuid4())
#     history = _sessions.get(session_id, [])

#     state = OrchestratorState(
#         messages=history.copy(),
#         current_input=req.message.strip(),
#         portal_id=PORTAL_ID,
#         session_id=session_id,
#         user_role=req.user_role or "user",
#         frontend_version=req.frontend_version or "v1",
#     )

#     try:
#         result = run_orchestrator(state)
#     except Exception as e:
#         logger.error("Orchestrator failed: %s", e, exc_info=True)
#         raise HTTPException(status_code=503, detail="The assistant is temporarily unavailable. Please try again shortly.")

#     guardrail_blocked = bool(result.guardrail_result and not result.guardrail_result.passed)

#     if result.final_response and not guardrail_blocked:
#         history.append(ChatMessage(role=MessageRole.USER, content=req.message.strip(), portal_id=PORTAL_ID, session_id=session_id))
#         history.append(ChatMessage(role=MessageRole.ASSISTANT, content=result.final_response.content, portal_id=PORTAL_ID, session_id=session_id))
#         # Keep last 30 messages (15 turns) — context_manager handles deeper trimming at LLM call time
#         _sessions[session_id] = history[-30:]

#     response_text = result.final_response.content if result.final_response else "I'm sorry, I couldn't process that."
#     intent = result.final_response.intent if result.final_response else IntentType.UNKNOWN
#     is_multi = result.final_response.is_multi_query if result.final_response else False
#     sub_responses = result.final_response.sub_responses if result.final_response else []

#     escalation_resp = None
#     if result.escalation and result.escalation.triggered:
#         escalation_resp = EscalationResponse(
#             triggered=True,
#             ticket_id=result.escalation.ticket_id,
#             reason=result.escalation.reason,
#         )

#     return ChatResponse(
#         session_id=session_id,
#         response=response_text,
#         intent=intent.value if hasattr(intent, "value") else str(intent),
#         is_multi_query=is_multi,
#         escalation=escalation_resp,
#         sub_responses=sub_responses,
#         guardrail_blocked=guardrail_blocked,
#         l1_hit=result.l1_hit,
#         l2_hit=result.l2_hit,
#         frontend_version=req.frontend_version or "v1",
#     )



@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests.")

    session_id = req.session_id or str(uuid.uuid4())
    history = _sessions.get(session_id, [])

    state = OrchestratorState(
        messages=history.copy(),
        current_input=req.message.strip(),
        portal_id=PORTAL_ID,
        session_id=session_id,
        user_role=req.user_role or "user",
        frontend_version=req.frontend_version or "v1",
    )

    async def generate():
        async for event in run_orchestrator_stream(state):
            yield f"data: {event}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/cache/stats")
async def get_cache_stats(frontend_version: str = "v1"):
    return l2_stats(PORTAL_ID, frontend_version)


@app.post("/cache/warm")
async def warm_cache(req: WarmRequest):
    result = warm(PORTAL_ID, req.old_version, req.new_version, req.top_k)
    return result


@app.delete("/cache/version/{version}")
async def drop_version(version: str):
    deleted = invalidate_version(PORTAL_ID, version)
    return {"deleted": deleted, "version": version}


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    return {"status": "cleared", "session_id": session_id}


@app.get("/health")
async def health():
    return {"status": "ok", "portal": PORTAL_ID}


@app.get("/debug/tools")
async def debug_tools():
    from packages.ai_layer.tool_registry import registry
    return {"tools": [t.name for t in registry.all_tools()]}


@app.post("/chat/debug")
async def chat_debug(req: ChatRequest):
    import traceback
    session_id = req.session_id or str(uuid.uuid4())
    state = OrchestratorState(
        messages=[],
        current_input=req.message.strip(),
        portal_id=PORTAL_ID,
        session_id=session_id,
        user_role="user",
        frontend_version="v1",
    )
    try:
        result = run_orchestrator_stream(state)
        return {
            "response": result.final_response.content if result.final_response else None,
            "errors": result.metadata.get("errors", []),
            "tool_route": result.metadata.get("tool_route", {}),
            "tool_results": result.metadata.get("tool_results", {}),
        }
    except Exception as e:
        return {"exception": str(e), "traceback": traceback.format_exc()}