"""Text embeddings — fixed to Google Gemini's free embedding model.

The embedding model MUST be fixed: project vectors and the JD query vector have
to come from the same model, or cosine similarity is meaningless. Gemini's
text-embedding-004 (768-dim) is free, which keeps the RAG feature usable on the
free tier regardless of which *chat* engine the user picked.
"""

from __future__ import annotations

from app.config import get_settings

EMBED_MODEL = "text-embedding-004"
EMBED_DIM = 768


def resolve_embed_key(provider: str, api_key: str | None) -> str | None:
    """A Google key for embeddings: the user's key if they're already on Gemini,
    otherwise the server-side GOOGLE_API_KEY. None ⇒ embeddings unavailable."""
    if provider == "gemini" and (api_key or "").strip():
        return api_key.strip()
    return (get_settings().google_api_key or "").strip() or None


def embed_texts(texts: list[str], api_key: str) -> list[list[float]]:
    """Embed a batch of texts. Raises on failure (callers fall back to LLM rank)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    resp = client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
    )
    return [list(e.values) for e in resp.embeddings]


def embed_one(text: str, api_key: str) -> list[float]:
    return embed_texts([text], api_key)[0]
