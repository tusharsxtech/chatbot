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

    # Estimate tokens and trim if needed
    # Keep most recent messages that fit within a safe limit
    MAX_HISTORY_TOKENS = 4000   # reserve most tokens for system prompt + response
    kept = []
    token_count = 0
    for msg in reversed(messages):
        msg_tokens = max(1, len(msg.content) // 4)
        if token_count + msg_tokens > MAX_HISTORY_TOKENS:
            break
        kept.insert(0, msg)
        token_count += msg_tokens

    for msg in kept:
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
- Preserve the original intent and meaning exactly. Do not add new facts, assumptions, or details.
- If the message is already clear and self-contained, return it unchanged.
- Return ONLY the rewritten query text. No explanation, no quotes, no markdown."""


def call_llm_for_rewrite(user_input: str, history_context: str = "") -> str:
    # Skip rewrite if no history — nothing to resolve
    if not history_context or not history_context.strip():
        return user_input

    messages = [SystemMessage(content=REWRITE_SYSTEM_PROMPT)]
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

CLASSIFY_AND_ROUTE_SYSTEM = """You are the brain of a support chatbot. Your job is to understand the user query and route it to the correct service.

Each service has a name, description, and example queries. Use these to decide routing.

Query types:
- greeting: "hi", "hello", "thanks", "how are you", "who are you", casual small talk
- escalation: urgent problem, angry user, billing error, legal threat, emergency
- chit_chat: general knowledge with no service match ("what is AI", "tell me a joke", "what year is it")
- service_query: the query matches a service domain or its example queries
- multi_query: user asked 2+ distinct questions in one message

How to route:
1. Read each service description and its example queries carefully
2. If the user query is similar in intent to any example query → pick that service
3. If the query is about the service domain even without an exact example match → pick that service
4. If nothing matches → chit_chat with services=[]
5. If multiple services match → include all of them

Return ONLY this JSON, no markdown, no explanation, no extra text:
{
  "query_type": "greeting|escalation|chit_chat|service_query|multi_query",
  "services": ["service_name"],
  "is_multi_query": false,
  "sub_queries": [],
  "reasoning": "one line explanation"
}

Rules:
- greeting/escalation/chit_chat → services=[]
- service_query → list matched service names exactly as given
- multi_query → is_multi_query=true, fill sub_queries, pick services per sub-query
- Return ONLY valid JSON, nothing else"""


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