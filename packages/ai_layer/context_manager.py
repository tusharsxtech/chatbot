import sys
sys.path.insert(0, "/app")

import logging
from packages.shared.types import ChatMessage, MessageRole

logger = logging.getLogger(__name__)

# ── Token estimation ──────────────────────────────────────────────────────────
# Rough estimate: 1 token ≈ 4 chars for English text.
# Alibaba Qwen3-32b context window: 128k tokens.
# We target 80% = ~102k tokens before triggering management.

CHARS_PER_TOKEN = 4
MODEL_CONTEXT_LIMIT_TOKENS = int(128_000 * 0.80)   # 80% of 128k = 102,400 tokens
MODEL_CONTEXT_LIMIT_CHARS = MODEL_CONTEXT_LIMIT_TOKENS * CHARS_PER_TOKEN  # ~409,600 chars

# How many recent messages to always keep verbatim (never summarize these)
RECENT_MESSAGES_TO_KEEP = 6   # last 3 turns

# Minimum messages before we even consider summarizing
MIN_MESSAGES_BEFORE_SUMMARY = 10


def estimate_tokens(text: str) -> int:
    """Rough token estimate — 1 token per 4 chars."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_messages_tokens(messages: list[ChatMessage]) -> int:
    """Estimate total tokens across all messages."""
    return sum(estimate_tokens(m.content) for m in messages)


def estimate_context_usage_pct(messages: list[ChatMessage], system_prompt: str = "") -> float:
    """Return what % of context window is used (0.0 to 1.0)."""
    total_chars = sum(len(m.content) for m in messages) + len(system_prompt)
    return total_chars / (MODEL_CONTEXT_LIMIT_TOKENS * CHARS_PER_TOKEN)


def needs_context_management(messages: list[ChatMessage], system_prompt: str = "") -> bool:
    """Returns True if context is at or above 80% capacity."""
    if len(messages) < MIN_MESSAGES_BEFORE_SUMMARY:
        return False
    return estimate_context_usage_pct(messages, system_prompt) >= 0.80


async def summarize_old_messages(
    messages: list[ChatMessage],
    call_llm_fn,  # async callable: (system_prompt, messages, user_input) -> str
) -> str:
    """
    Summarize the older part of the conversation into a compact paragraph.
    Called when context window hits 80%.
    """
    if not messages:
        return ""

    conversation_text = "\n".join(
        f"{m.role.value if hasattr(m.role, 'value') else m.role}: {m.content}"
        for m in messages
    )

    summary_system = (
        "You are a conversation summarizer. "
        "Summarize the following conversation history into a concise paragraph (max 150 words). "
        "Preserve: key facts mentioned, questions asked, answers given, user's main goals. "
        "Discard: pleasantries, repeated information, failed attempts. "
        "Write in third person. Return ONLY the summary, no preamble."
    )

    try:
        summary = await call_llm_fn(summary_system, [], conversation_text)
        return summary.strip()
    except Exception as e:
        logger.error("Context summarization failed: %s", e)
        # Fallback: just return last few messages as text
        return conversation_text[-500:]


async def manage_context(
    messages: list[ChatMessage],
    system_prompt: str,
    call_llm_fn,
    session_id: str = "",
    portal_id: str = "",
) -> tuple[list[ChatMessage], str]:
    """
    Main entry point. Checks context usage and manages it if needed.

    Returns:
        (pruned_messages, conversation_summary)
        - pruned_messages: safe list of messages to pass to LLM
        - conversation_summary: summary of older context (empty string if not needed)

    Strategy:
        If context < 80%  → return messages as-is
        If context >= 80% → summarize older messages, keep last RECENT_MESSAGES_TO_KEEP verbatim
    """
    if not needs_context_management(messages, system_prompt):
        return messages, ""

    pct = estimate_context_usage_pct(messages, system_prompt)
    logger.warning(
        "Context window at %.0f%% for session=%s — triggering management",
        pct * 100, session_id
    )

    # Split: old messages to summarize vs recent to keep
    if len(messages) <= RECENT_MESSAGES_TO_KEEP:
        return messages, ""

    old_messages = messages[:-RECENT_MESSAGES_TO_KEEP]
    recent_messages = messages[-RECENT_MESSAGES_TO_KEEP:]

    # Summarize the old part
    summary = await summarize_old_messages(old_messages, call_llm_fn)

    logger.info(
        "Context managed: summarized %d messages into %d chars, keeping %d recent",
        len(old_messages), len(summary), len(recent_messages)
    )

    return recent_messages, summary


async def get_safe_messages_for_llm(
    messages: list[ChatMessage],
    system_prompt: str,
    call_llm_fn,
    session_id: str = "",
) -> tuple[list[ChatMessage], str]:
    """
    Convenience wrapper used by the orchestrator before any LLM call.
    Returns (safe_messages, summary_context).
    The summary_context should be injected into the system prompt if non-empty.
    """
    return await manage_context(messages, system_prompt, call_llm_fn, session_id)
