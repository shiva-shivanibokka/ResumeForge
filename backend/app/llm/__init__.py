"""Multi-provider LLM abstraction.

A single `LLMProvider` interface with concrete adapters for Anthropic, OpenAI,
Google Gemini, and Groq. Call sites depend only on `LLMProvider.complete(...)`
and never import a provider SDK directly, so adding or swapping a provider is a
one-file change. See `factory.get_provider` for construction.
"""

from app.llm.base import LLMError, LLMProvider, LLMResponse
from app.llm.factory import get_provider
from app.llm.registry import PROVIDERS, list_providers

__all__ = [
    "LLMError",
    "LLMProvider",
    "LLMResponse",
    "get_provider",
    "PROVIDERS",
    "list_providers",
]
