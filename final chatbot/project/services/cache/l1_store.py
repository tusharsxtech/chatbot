import sys
sys.path.insert(0, "/app")

from langgraph.checkpoint.memory import MemorySaver
from typing import Optional

_store: dict[str, dict[str, dict]] = {}
_checkpointer = MemorySaver()


def get_checkpointer() -> MemorySaver:
    return _checkpointer


def get(session_id: str, portal_id: str, query: str) -> Optional[dict]:
    key = f"{portal_id}:{session_id}"
    return _store.get(key, {}).get(query.strip().lower())


def set(session_id: str, portal_id: str, query: str, answer: str, intent: str) -> None:
    key = f"{portal_id}:{session_id}"
    if key not in _store:
        _store[key] = {}
    _store[key][query.strip().lower()] = {"answer": answer, "intent": intent}


def summary(session_id: str, portal_id: str) -> str:
    key = f"{portal_id}:{session_id}"
    session = _store.get(key, {})
    if not session:
        return ""
    pairs = list(session.items())[-5:]
    return "\n".join(f"Q: {q}\nA: {v['answer'][:120]}" for q, v in pairs)


def clear(session_id: str, portal_id: str) -> None:
    _store.pop(f"{portal_id}:{session_id}", None)