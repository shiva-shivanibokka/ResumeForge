"""Catalog of supported providers and their selectable models.

Drives the `/api/providers` endpoint (so the frontend can render a provider +
model picker) and the factory's default-model resolution. `free` marks models
on a provider's free tier — Gemini and Groq both have real free tiers, which is
what lets the live demo run at no cost to the owner when a visitor brings their
own key.

Model IDs drift over time; update them here in one place. Anthropic's current
model is verified against the claude-api reference (claude-opus-4-8).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelInfo:
    id: str
    label: str
    free: bool = False


@dataclass
class ProviderInfo:
    key: str
    label: str
    env_key_name: str
    models: list[ModelInfo]
    default_model: str
    free_tier: bool = False
    notes: str = ""


PROVIDERS: dict[str, ProviderInfo] = {
    "anthropic": ProviderInfo(
        key="anthropic",
        label="Anthropic (Claude)",
        env_key_name="ANTHROPIC_API_KEY",
        default_model="claude-opus-4-8",
        models=[
            ModelInfo("claude-opus-4-8", "Claude Opus 4.8"),
            ModelInfo("claude-sonnet-4-6", "Claude Sonnet 4.6"),
            ModelInfo("claude-haiku-4-5", "Claude Haiku 4.5"),
        ],
        notes="Premium quality. Paid API key required.",
    ),
    "openai": ProviderInfo(
        key="openai",
        label="OpenAI (GPT)",
        env_key_name="OPENAI_API_KEY",
        default_model="gpt-4o-mini",
        models=[
            ModelInfo("gpt-4o", "GPT-4o"),
            ModelInfo("gpt-4o-mini", "GPT-4o mini"),
        ],
        notes="Widely recognized. Paid API key required.",
    ),
    "gemini": ProviderInfo(
        key="gemini",
        label="Google Gemini",
        env_key_name="GOOGLE_API_KEY",
        default_model="gemini-2.0-flash",
        free_tier=True,
        models=[
            ModelInfo("gemini-2.0-flash", "Gemini 2.0 Flash", free=True),
            ModelInfo("gemini-1.5-flash", "Gemini 1.5 Flash", free=True),
            ModelInfo("gemini-1.5-pro", "Gemini 1.5 Pro", free=True),
        ],
        notes="Generous free tier — great for a free live demo.",
    ),
    "groq": ProviderInfo(
        key="groq",
        label="Groq (open models)",
        env_key_name="GROQ_API_KEY",
        default_model="llama-3.3-70b-versatile",
        free_tier=True,
        models=[
            ModelInfo("llama-3.3-70b-versatile", "Llama 3.3 70B", free=True),
            ModelInfo("llama-3.1-8b-instant", "Llama 3.1 8B (fast)", free=True),
        ],
        notes="Free and very fast. Great for a free live demo.",
    ),
}


def list_providers() -> list[dict]:
    """Serializable provider catalog for the /api/providers endpoint."""
    return [
        {
            "key": p.key,
            "label": p.label,
            "env_key_name": p.env_key_name,
            "free_tier": p.free_tier,
            "notes": p.notes,
            "default_model": p.default_model,
            "models": [
                {"id": m.id, "label": m.label, "free": m.free} for m in p.models
            ],
        }
        for p in PROVIDERS.values()
    ]
