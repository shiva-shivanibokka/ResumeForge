"""LLM provider contract: the protocol, the response/error types, nothing else.

Keeping the contract in its own module means adapters and call sites share one
definition and there are no import cycles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

ErrorKind = Literal[
    "auth", "rate_limit", "timeout", "bad_request", "server", "unknown"
]


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    usage: dict | None = None


class LLMError(Exception):
    """Normalized error across providers.

    `kind` lets call sites react (e.g. surface a 401 vs a 429) without importing
    each SDK's exception hierarchy.
    """

    def __init__(self, message: str, *, provider: str, kind: ErrorKind = "unknown"):
        super().__init__(message)
        self.provider = provider
        self.kind: ErrorKind = kind


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.2,
        model: str | None = None,
    ) -> LLMResponse:
        """Single-turn completion. Returns the assistant text or raises LLMError."""
        ...
