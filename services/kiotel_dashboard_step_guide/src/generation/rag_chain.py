from dataclasses import dataclass, field
import json
from typing import Iterator, List, Optional

from configs.settings import get_settings
from configs.logging_config import get_logger
from src.retrieval.hybrid_retriever import HybridRetriever
from src.generation.llm_client import get_llm_client
from src.generation.prompts import build_rag_messages, build_condense_messages, format_context
from src.guardrails.guardrail import Guardrail, GuardrailResult

logger = get_logger(__name__)


@dataclass
class RAGResponse:
    answer: str
    source_documents: List[dict]
    guardrail_result: Optional[GuardrailResult] = None
    query_used: str = ""
    blocked: bool = False


@dataclass
class ChatMessage:
    role: str
    content: str


class RAGChain:
    def __init__(self):
        self.retriever = HybridRetriever()
        self.llm = get_llm_client()
        self.guardrail = Guardrail()
        self.settings = get_settings()

    def query(
    self,
    question: str,
    chat_history: Optional[List[ChatMessage]] = None,
    ) -> Iterator[str]:

     input_check = self.guardrail.check_input(question)
     if input_check.blocked:
        logger.warning("query_blocked_by_guardrail", reason=input_check.reason)
        yield json.dumps({"type": "blocked", "message": input_check.message, "source_documents": [], "query_used": ""})
        return

     standalone_query = question
     if chat_history and len(chat_history) >= 2:
        standalone_query = self._condense_question(question, chat_history)

     retrieved = self.retriever.retrieve(standalone_query)

     relevance_check = self.guardrail.check_relevance(standalone_query, retrieved)
     if relevance_check.blocked:
        logger.warning("low_relevance_blocked", score=relevance_check.score)
        yield json.dumps({"type": "blocked", "message": relevance_check.message, "source_documents": retrieved, "query_used": standalone_query})
        return

     context = format_context(retrieved)
     messages = build_rag_messages(standalone_query, context)

    # send metadata first before chunks
     yield json.dumps({"type": "metadata", "source_documents": retrieved, "query_used": standalone_query, "blocked": False})

     full_answer = ""
     for chunk in self.llm.chat(messages, temperature=0.1, max_tokens=self.settings.guardrail_max_output_tokens, stream=True):
        full_answer += chunk
        yield json.dumps({"type": "chunk", "text": chunk})

     output_check = self.guardrail.check_output(full_answer)
     if output_check.blocked:
        logger.warning("output_blocked_by_guardrail", reason=output_check.reason)
        yield json.dumps({"type": "blocked", "message": output_check.message, "source_documents": retrieved, "query_used": standalone_query})

     logger.info("rag_query_complete", query=standalone_query[:80], sources=len(retrieved))   

    @staticmethod
    def _extract_question(raw: str) -> str:
        raw = raw.strip()
        for marker in ["Standalone Question:", "standalone question:", "Question:"]:
            if marker in raw:
                raw = raw.split(marker, 1)[-1].strip()
        raw = raw.strip('"').strip("'").strip()
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        return lines[-1] if lines else raw