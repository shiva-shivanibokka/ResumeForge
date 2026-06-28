"""Provider factory: resolve provider + key + model into a ready LLMProvider.

Key resolution order: explicit per-request key (BYO key from the UI) → server-side
env fallback. If neither is present, raise an auth-kind LLMError so the API layer
can return a clean 401 telling the user to supply a key.
"""

from __future__ import annotations

from app.config import get_settings
from app.llm.base import LLMError, LLMProvider
from app.llm.registry import PROVIDERS


def _resolve_key(provider_key: str, api_key: str | None) -> str:
    explicit = (api_key or "").strip()
    if explicit:
        return explicit
    settings = get_settings()
    env_attr = {
        "anthropic": "anthropic_api_key",
        "openai": "openai_api_key",
        "gemini": "google_api_key",
        "groq": "groq_api_key",
    }[provider_key]
    return (getattr(settings, env_attr, None) or "").strip()


def get_provider(
    provider: str, *, api_key: str | None = None, model: str | None = None
) -> LLMProvider:
    key = (provider or "").strip().lower()
    info = PROVIDERS.get(key)
    if info is None:
        raise LLMError(
            f"Unknown provider '{provider}'. Choose one of: {', '.join(PROVIDERS)}.",
            provider=provider or "unknown",
            kind="bad_request",
        )

    resolved_key = _resolve_key(key, api_key)
    if not resolved_key:
        raise LLMError(
            f"No API key for {info.label}. Enter your key in the app or set "
            f"{info.env_key_name} on the server.",
            provider=key,
            kind="auth",
        )

    default_model = model or info.default_model

    if key == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(resolved_key, default_model)
    if key == "openai":
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(resolved_key, default_model)
    if key == "gemini":
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider(resolved_key, default_model)
    if key == "groq":
        from app.llm.groq_provider import GroqProvider

        return GroqProvider(resolved_key, default_model)

    raise LLMError(
        f"Provider '{key}' is in the registry but has no adapter.",
        provider=key,
        kind="server",
    )
