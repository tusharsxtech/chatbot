import sys
sys.path.insert(0, "/app")

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class IntentType(str, Enum):
    GREETING = "greeting"
    ESCALATION = "escalation"
    MULTI_QUERY = "multi_query"
    SERVICE_QUERY = "service_query"
    GENERAL = "general"
    UNKNOWN = "unknown"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ChatMessage:
    role: MessageRole
    content: str
    portal_id: str = "portal_a"
    session_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class GuardrailResult:
    passed: bool
    reason: Optional[str] = None
    sanitized_input: Optional[str] = None


@dataclass
class IntentResult:
    primary_intent: IntentType
    sub_intents: list[IntentType] = field(default_factory=list)
    entities: dict = field(default_factory=dict)
    confidence: float = 1.0
    is_multi_query: bool = False
    sub_queries: list[str] = field(default_factory=list)


@dataclass
class EscalationResult:
    triggered: bool
    reason: str = ""
    ticket_id: Optional[str] = None


@dataclass
class AIResponse:
    content: str
    intent: IntentType
    escalation: Optional[EscalationResult] = None
    sub_responses: list[str] = field(default_factory=list)
    is_multi_query: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class OrchestratorState:
    messages: list[ChatMessage] = field(default_factory=list)
    current_input: str = ""
    sanitized_input: str = ""
    intent: Optional[IntentResult] = None
    escalation: Optional[EscalationResult] = None
    guardrail_result: Optional[GuardrailResult] = None
    final_response: Optional[AIResponse] = None
    portal_id: str = "portal_a"
    session_id: str = ""
    user_role: str = "user"
    frontend_version: str = "0.0.0"
    l1_hit: bool = False
    l2_hit: bool = False
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None