from functools import lru_cache
from typing import Iterator, List, Union

from openai import OpenAI

from configs.settings import get_settings
from configs.logging_config import get_logger

logger = get_logger(__name__)


class LLMClient:
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        self.model = settings.llm_model
        logger.info("llm_client_initialized", model=self.model, base_url=settings.llm_base_url)

    def chat(
        self,
        messages: List[dict],
        temperature: float = 0.1,
        max_tokens: int = 1024,
        stream: bool = False,
    ) -> Union[str, Iterator[str]]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )
        if stream:
            def _stream_chunks() -> Iterator[str]:
                for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
            return _stream_chunks()
        content = response.choices[0].message.content or ""
        logger.info(
            "llm_response",
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )
        return content


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    return LLMClient()
