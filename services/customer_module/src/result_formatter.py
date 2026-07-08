"""Post-fetch formatting: keeps long text fields from dumping raw walls of
text into the UI by summarizing them, unless the question explicitly asks
for raw data (e.g. "show raw ocr data").
"""
import re

from openai import OpenAI

from src.config import settings

_RAW_PATTERN = re.compile(r"\braw\b", re.IGNORECASE)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    return _client


def wants_raw(question: str) -> bool:
    return bool(_RAW_PATTERN.search(question))


def _summarize_text(text: str) -> str:
    response = _get_client().chat.completions.create(
        model=settings.llm_model,
        messages=[{
            "role": "user",
            "content": f"Summarize the following in one short sentence, no preamble:\n\n{text}",
        }],
        max_tokens=settings.summary_max_tokens,
    )
    return response.choices[0].message.content.strip()


def format_rows(rows: list[dict], question: str) -> list[dict]:
    """Summarizes any field whose text is longer than the configured word
    threshold, unless the question asks for raw data.
    """
    if wants_raw(question):
        return rows

    formatted = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            if isinstance(value, str) and len(value.split()) > settings.summary_word_threshold:
                new_row[key] = _summarize_text(value)
            else:
                new_row[key] = value
        formatted.append(new_row)
    return formatted
