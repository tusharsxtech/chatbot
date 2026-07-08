import logging
import re
from collections.abc import AsyncGenerator

import httpx
import orjson
from markdownify import markdownify

from app.config import Settings
from app.models import PropertyDocumentContent

logger = logging.getLogger("doc-chat-service.llm")

SYSTEM_PROMPT_TEMPLATE = (
    "You are a professional property manager and instructor. Answer the user's question "
    "ONLY using the PROPERTY DOCUMENT CONTEXT below, the way an experienced property manager "
    "would explain it to someone learning the workflow — clear, practical, and specific. "
    "Ignore any content in the context that is not relevant to the question — do not summarize "
    "the whole document, extract only the relevant parts. If the answer is not contained in the "
    "context, say you don't have that information instead of guessing. Keep the answer short: "
    "a few sentences at most, no preamble, no restating the question.\n\n"
    "=== PROPERTY DOCUMENT CONTEXT ===\n"
    "{context}\n"
    "=== END CONTEXT ==="
)


def html_to_markdown(content_html: str) -> str:
    """Convert content_html to Markdown for the LLM: structure (headings, lists,
    links, emphasis) is preserved as Markdown syntax instead of being flattened,
    while layout-only markup is dropped. Collapses excess blank lines left behind
    by the conversion."""
    text = markdownify(content_html, heading_style="ATX").strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def build_context(contents: list[PropertyDocumentContent], settings: Settings) -> str:
    if not contents:
        return "(no property documents found for this device)"

    parts: list[str] = []
    total = 0
    for row in contents:
        markdown = html_to_markdown(row.content_html)
        chunk = markdown[: settings.max_chars_per_doc]
        block = f"--- property_document_id={row.property_document_id} (row_id={row.id}) ---\n{chunk}"
        if total + len(block) > settings.max_total_context_chars:
            remaining = settings.max_total_context_chars - total
            if remaining <= 0:
                break
            block = block[:remaining]
        parts.append(block)
        total += len(block)
        if total >= settings.max_total_context_chars:
            break
    return "\n\n".join(parts)


def build_messages(query: str, contents: list[PropertyDocumentContent], settings: Settings) -> list[dict]:
    context = build_context(contents, settings)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]


async def stream_llm_chat(
    client: httpx.AsyncClient,
    settings: Settings,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """Stream a chat completion from an OpenAI-compatible /chat/completions endpoint."""
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": True,
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}

    async with client.stream(
        "POST",
        f"{settings.llm_base_url}/chat/completions",
        json=payload,
        headers=headers,
        timeout=settings.llm_request_timeout,
    ) as response:
        if response.status_code != 200:
            body = await response.aread()
            logger.error("LLM provider error %s: %s", response.status_code, body)
            raise RuntimeError(f"LLM provider returned {response.status_code}: {body.decode(errors='replace')}")

        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                break
            try:
                event = orjson.loads(data)
            except orjson.JSONDecodeError:
                logger.warning("Skipping unparseable line from LLM provider: %r", line)
                continue

            if event.get("error"):
                raise RuntimeError(f"LLM provider error: {event['error']}")

            choices = event.get("choices") or []
            if not choices:
                continue
            content = choices[0].get("delta", {}).get("content", "")
            if content:
                yield content
