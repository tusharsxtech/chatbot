import sys
sys.path.insert(0, "/app")

import os
import time
import json
import random
import logging
import threading
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from packages.shared.types import ChatMessage, MessageRole

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

MODEL = os.getenv("LLM_MODEL", "alibaba-qwen3-32b")

client = ChatOpenAI(
    model=MODEL,
    temperature=0.7,
    max_tokens=1024,
    base_url=os.getenv("LLM_BASE_URL", "https://inference.do-ai.run/v1"),
    api_key=os.getenv("LLM_API_KEY"),
    timeout=60.0,
    max_retries=1,
)


class LLMServiceError(Exception):
    pass


class CircuitBreakerOpenError(LLMServiceError):
    pass


class RateLimitExceededError(LLMServiceError):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "closed"
        self.opened_at = None
        self._lock = threading.Lock()

    def allow_request(self):
        with self._lock:
            if self.state == "open":
                if self.opened_at is not None and (time.time() - self.opened_at) >= self.recovery_timeout:
                    self.state = "half_open"
                    return True
                return False
            return True

    def record_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = "closed"
            self.opened_at = None

    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                self.opened_at = time.time()


class TokenBucketRateLimiter:
    def __init__(self, max_calls_per_minute=30):
        self.capacity = max(1, max_calls_per_minute)
        self.tokens = float(self.capacity)
        self.refill_rate = self.capacity / 60.0
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def acquire(self, timeout=10.0):
        deadline = time.time() + timeout
        while True:
            with self._lock:
                self._refill()
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True
            if time.time() >= deadline:
                return False
            time.sleep(0.1)


_circuit_breaker = CircuitBreaker(
    failure_threshold=int(os.getenv("LLM_CB_FAILURE_THRESHOLD", "5")),
    recovery_timeout=float(os.getenv("LLM_CB_RECOVERY_TIMEOUT", "30")),
)

_rate_limiter = TokenBucketRateLimiter(
    max_calls_per_minute=int(os.getenv("LLM_RATE_LIMIT_PER_MINUTE", "30"))
)

MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
BASE_BACKOFF_SECONDS = float(os.getenv("LLM_BASE_BACKOFF_SECONDS", "0.5"))
MAX_BACKOFF_SECONDS = float(os.getenv("LLM_MAX_BACKOFF_SECONDS", "8.0"))
RATE_LIMIT_WAIT_TIMEOUT = float(os.getenv("LLM_RATE_LIMIT_WAIT_TIMEOUT", "10"))
LLM_REQUEST_TIMEOUT = float(os.getenv("LLM_REQUEST_TIMEOUT", "60.0"))


def safe_invoke(messages, llm_client=None):
    target = llm_client or client

    if not _circuit_breaker.allow_request():
        raise CircuitBreakerOpenError("LLM circuit breaker is open; failing fast.")

    if not _rate_limiter.acquire(timeout=RATE_LIMIT_WAIT_TIMEOUT):
        raise RateLimitExceededError("LLM rate limit exceeded; request throttled.")

    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            result = target.invoke(messages)
            _circuit_breaker.record_success()
            return result
        except Exception as e:
            last_exc = e
            _circuit_breaker.record_failure()
            logger.warning("LLM invoke attempt %s/%s failed: %s", attempt + 1, MAX_RETRIES, e)
            logger.error("LLM error detail — type: %s | args: %s", type(e).__name__, e.args)
            if attempt < MAX_RETRIES - 1:
                delay = min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2 ** attempt)) + random.uniform(0, 0.25)
                time.sleep(delay)

    raise LLMServiceError(f"LLM call failed after {MAX_RETRIES} attempts: {last_exc}")


def call_llm(
    system_prompt: str,
    messages: list[ChatMessage],
    user_input: str,
) -> str:
    formatted = []

    if system_prompt:
        formatted.append(SystemMessage(content=system_prompt))

    for msg in messages[-10:]:
        role_val = msg.role.value if hasattr(msg.role, "value") else msg.role
        if role_val == "user":
            formatted.append(HumanMessage(content=msg.content))
        else:
            formatted.append(AIMessage(content=msg.content))

    formatted.append(HumanMessage(content=user_input))

    response = safe_invoke(formatted)
    return response.content


def call_llm_for_intent(user_input: str) -> str:
    """Legacy wrapper — kept for compatibility. Use call_llm_for_classify_and_route instead."""
    intent_system = """You are an intent classifier. Given user input, return ONLY a JSON object:
{
  "primary_intent": one of [greeting, knowledge_query, step_guide, escalation, multi_query, general, unknown],
  "sub_intents": [],
  "entities": {},
  "is_multi_query": false,
  "sub_queries": []
}
If the input contains multiple distinct questions, set is_multi_query=true and list them in sub_queries.
Return ONLY valid JSON. No markdown, no explanation, no extra text."""

    messages = [
        SystemMessage(content=intent_system),
        HumanMessage(content=user_input)
    ]

    intent_client = ChatOpenAI(
        model=MODEL,
        temperature=0.0,
        max_tokens=300,
        base_url=os.getenv("LLM_BASE_URL", "https://inference.do-ai.run/v1"),
        api_key=os.getenv("LLM_API_KEY"),
        timeout=60.0,
        max_retries=1,
    )
    response = safe_invoke(messages, llm_client=intent_client)
    return response.content


REWRITE_SYSTEM_PROMPT = """You are a query rewriting assistant for a support chatbot.
Rewrite the user's latest message into a single, self-contained, unambiguous query using the conversation context provided.
Rules:
- Resolve pronouns and vague references using the context.
- Ensure the rewritten query is clear and specific, suitable for processing by downstream tools.
- Do not add any additional information or context.
- Preserve the original intent and meaning exactly. Do not add new facts, assumptions, or details.
- If the message is already clear and self-contained, return it unchanged.
- Return ONLY the rewritten query text. No explanation, no quotes, no markdown."""


def call_llm_for_rewrite(user_input: str, history_context: str = "") -> str:
    messages = [SystemMessage(content=REWRITE_SYSTEM_PROMPT)]
    if history_context:
        messages.append(HumanMessage(content=f"Conversation context:\n{history_context}"))
    messages.append(HumanMessage(content=f"Latest user message: {user_input}"))

    rewrite_client = ChatOpenAI(
        model=MODEL,
        temperature=0.0,
        max_tokens=200,
        base_url=os.getenv("LLM_BASE_URL", "https://inference.do-ai.run/v1"),
        api_key=os.getenv("LLM_API_KEY"),
        timeout=60.0,
        max_retries=1,
    )
    response = safe_invoke(messages, llm_client=rewrite_client)
    rewritten = (response.content or "").strip().strip('"').strip()
    return rewritten or user_input


FAITHFULNESS_SYSTEM_PROMPT = """You are a strict faithfulness checker for an AI support assistant.
You will be given SOURCE CONTEXT (knowledge base entries and/or tool results) and a GENERATED RESPONSE.
Determine whether every factual claim in the GENERATED RESPONSE is supported by the SOURCE CONTEXT.
General greetings, clarifying questions, or empathy statements without factual claims should be considered grounded.
Return ONLY a JSON object:
{"grounded": true/false, "reason": "brief reason", "confidence": 0.0-1.0}
Return ONLY valid JSON, no markdown, no explanation."""


def call_llm_for_faithfulness(response_text: str, grounding_context: str) -> dict:
    messages = [
        SystemMessage(content=FAITHFULNESS_SYSTEM_PROMPT),
        HumanMessage(content=f"SOURCE CONTEXT:\n{grounding_context}\n\nGENERATED RESPONSE:\n{response_text}"),
    ]
    judge_client = ChatOpenAI(
        model=MODEL,
        temperature=0.0,
        max_tokens=200,
        base_url=os.getenv("LLM_BASE_URL", "https://inference.do-ai.run/v1"),
        api_key=os.getenv("LLM_API_KEY"),
        timeout=60.0,
        max_retries=1,
    )
    response = safe_invoke(messages, llm_client=judge_client)
    raw = (response.content or "").strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        parsed = json.loads(raw)
        return {
            "grounded": bool(parsed.get("grounded", True)),
            "reason": parsed.get("reason", ""),
            "confidence": parsed.get("confidence"),
        }
    except Exception:
        return {"grounded": True, "reason": "Faithfulness check parse failed; defaulting to grounded.", "confidence": None}

CLASSIFY_AND_ROUTE_SYSTEM = """You are the brain of a support chatbot. Given a user query and a list of available services, you must:
1. Understand what the user is asking
2. Decide the query type
3. Route to the right service(s)

Available query types:
- greeting: hi, hello, thanks, how are you, small talk
- escalation: urgent, angry, frustrated, billing error, legal threat, emergency
- chit_chat: general knowledge questions not related to any service ("what is AI", "tell me a joke", "what is 2+2")
- service_query: anything that a service below can answer
- multi_query: user asked multiple distinct questions in one message

You will be given services with descriptions of EXACTLY what domain they cover.
Read the descriptions carefully — route to a service only if the query is genuinely about that domain.

Return ONLY this JSON, no markdown, no explanation:
{
  "query_type": "greeting|escalation|chit_chat|service_query|multi_query",
  "services": ["service_name"],
  "is_multi_query": false,
  "sub_queries": [],
  "reasoning": "one line explanation"
}

Rules:
- greeting/escalation/chit_chat → services=[]
- service_query → pick ALL services whose domain matches
- multi_query → set is_multi_query=true, split into sub_queries, pick services for each
- If no service matches → query_type=chit_chat, services=[]
- Return ONLY valid JSON"""


def call_llm_for_classify_and_route(
    user_input: str,
    services_schema: list[dict],
    history_context: str = "",
) -> dict:
    """
    Single LLM call that classifies intent AND routes to services.
    This replaces the old separate intent + dispatch calls.
    
    Each service in services_schema should have:
        name: str
        description: str  — rich domain description drives routing accuracy
    """
    messages = [SystemMessage(content=CLASSIFY_AND_ROUTE_SYSTEM)]

    if history_context:
        messages.append(HumanMessage(content=f"Conversation so far:\n{history_context}"))

    prompt = (
        f"Available services:\n{json.dumps(services_schema, indent=2)}"
        f"\n\nUser query: {user_input}"
    )
    messages.append(HumanMessage(content=prompt))

    smart_client = ChatOpenAI(
        model=MODEL,
        temperature=0.0,
        max_tokens=400,
        base_url=os.getenv("LLM_BASE_URL", "https://inference.do-ai.run/v1"),
        api_key=os.getenv("LLM_API_KEY"),
        timeout=60.0,
        max_retries=1,
    )

    try:
        response = safe_invoke(messages, llm_client=smart_client)
        raw = (response.content or "").strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        if not raw:
            raise ValueError("Empty response from classifier")
        parsed = json.loads(raw)
        return {
            "query_type": parsed.get("query_type", "chit_chat"),
            "services": parsed.get("services", []),
            "is_multi_query": parsed.get("is_multi_query", False),
            "sub_queries": parsed.get("sub_queries", []),
            "reasoning": parsed.get("reasoning", ""),
        }
    except Exception as e:
        logger.error("classify_and_route failed: %s", e)
        # Safe fallback — treat as service_query so tools get a chance
        return {
            "query_type": "service_query",
            "services": [s["name"] for s in services_schema[:1]],  # try first service
            "is_multi_query": False,
            "sub_queries": [],
            "reasoning": f"Fallback due to classifier error: {e}",
        }


# Keep old dispatch for any legacy callers
def call_llm_for_tool_dispatch(user_input: str, tools_schema: list[dict], history_context: str = "") -> dict:
    """Legacy wrapper around call_llm_for_classify_and_route."""
    result = call_llm_for_classify_and_route(user_input, tools_schema, history_context)
    return {
        "tools": result["services"],
        "reasoning": result["reasoning"],
        "is_chit_chat": result["query_type"] in ("greeting", "chit_chat"),
    }