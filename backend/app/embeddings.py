"""Text embeddings for the RAG project cache.

The embedding provider follows the user's chat engine: OpenAI chat -> OpenAI
embeddings (their key), Gemini chat -> Gemini embeddings (their key). Providers
without an embeddings API (Groq, Anthropic) fall back to a server-side key.

Different models produce different-sized, NON-comparable vectors (Gemini = 768,
OpenAI = 1536). So the embedding *model* is recorded with each cached project and
the JD query must be embedded with the same model — see app/db.py (dimension-
agnostic column) and app/services/rag.py (model-aware ranking).
"""

from __future__ import annotations

from app.config import get_settings

# provider key -> (embedding model id, dimension)
EMBED_MODELS: dict[str, tuple[str, int]] = {
    "gemini": ("text-embedding-004", 768),
    "openai": ("text-embedding-3-small", 1536),
}

# An embedder is (provider, model, api_key).
Embedder = tuple[str, str, str]


def resolve_embedder(provider: str, api_key: str | None) -> Embedder | None:
    """Pick an embedder: the user's engine+key if it supports embeddings, else a
    server-side key. None ⇒ embeddings unavailable (callers fall back to LLM rank)."""
    p = (provider or "").lower()
    key = (api_key or "").strip()
    if p in EMBED_MODELS and key:
        return (p, EMBED_MODELS[p][0], key)

    settings = get_settings()
    if settings.google_api_key:
        return ("gemini", EMBED_MODELS["gemini"][0], settings.google_api_key)
    if settings.openai_api_key:
        return ("openai", EMBED_MODELS["openai"][0], settings.openai_api_key)
    return None


def embed_texts(texts: list[str], embedder: Embedder) -> list[list[float]]:
    """Embed a batch with the chosen provider. Raises on failure."""
    provider, model, key = embedder
    if provider == "openai":
        from openai import OpenAI

        resp = OpenAI(api_key=key).embeddings.create(model=model, input=texts)
        return [list(d.embedding) for d in resp.data]

    # Gemini (default)
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    resp = client.models.embed_content(
        model=model,
        contents=texts,
        config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
    )
    return [list(e.values) for e in resp.embeddings]


def embed_one(text: str, embedder: Embedder) -> list[float]:
    return embed_texts([text], embedder)[0]
