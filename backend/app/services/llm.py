"""LLM abstraction layer — provider-agnostic interface for chat and embeddings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import httpx
from openai import AsyncOpenAI

from app.config import settings
from app.utils.logging import get_logger

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletion, CreateEmbeddingResponse

log = get_logger(__name__)


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Send a chat completion request and return the assistant's message."""
        raise NotImplementedError

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text."""
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible LLM provider (OpenAI, Azure, local Ollama, etc.)."""

    def __init__(self, api_key: str, base_url: str, model: str, embedding_model: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.embedding_model = embedding_model

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> str:
        """Send a chat completion request."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LLM returned empty response")
        return content

    async def embed(self, text: str) -> list[float]:
        """Generate a text embedding."""
        # Truncate to avoid token limits (max ~8000 tokens)
        truncated = text[:12_000]
        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=truncated,
        )
        return response.data[0].embedding


class NoOpProvider(LLMProvider):
    """Fallback provider for when no API key is configured."""

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        return "No LLM configured. Set OPENAI_API_KEY in your environment."

    async def embed(self, text: str) -> list[float]:
        return [0.0] * settings.embedding_dimensions


def get_llm_provider() -> LLMProvider:
    """Factory to get the configured LLM provider."""
    if settings.openai_api_key:
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            model=settings.llm_model,
            embedding_model=settings.embedding_model,
        )
    log.warning("No OPENAI_API_KEY set — using NoOp provider")
    return NoOpProvider()


llm_provider = get_llm_provider()