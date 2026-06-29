"""RAG project matching: embed GitHub projects once, cache them, and rank future
job descriptions by vector similarity instead of re-crawling + re-LLM-ranking.

The embedder (provider, model, key) follows the user's chat engine — see
app/embeddings.resolve_embedder. The model is stored with the cache; ranking
embeds the JD with the same model the cache used (the router re-embeds on a
model mismatch). Enabled only when a database and an embedder are available.
"""

from __future__ import annotations

from collections.abc import Callable

from app import db
from app.embeddings import Embedder, embed_one, embed_texts


def _project_text(p: dict) -> str:
    parts = [
        p.get("name", ""),
        p.get("one_line", ""),
        p.get("category", ""),
        " ".join(p.get("tech_stack", []) or []),
        " ".join(p.get("keywords", []) or []),
        " ".join(p.get("bullets", []) or []),
    ]
    return "\n".join(s for s in parts if s).strip() or p.get("name", "project")


def _jd_text(jd: dict) -> str:
    parts = [
        jd.get("job_title", ""),
        jd.get("company", ""),
        " ".join(jd.get("required_skills", []) or []),
        " ".join(jd.get("preferred_skills", []) or []),
        " ".join(jd.get("keywords", []) or []),
        " ".join(jd.get("responsibilities", []) or []),
    ]
    return "\n".join(s for s in parts if s).strip() or "software engineer"


def embed_and_store(
    github_user: str,
    projects: list[dict],
    embedder: Embedder,
    progress: Callable[[str], None] = lambda _m: None,
) -> int:
    """Embed every project and replace the user's cached vectors. Returns the count."""
    if not projects:
        return 0
    _provider, model, _key = embedder
    progress(f"Embedding {len(projects)} projects ({model}) for re-use...")
    vectors = embed_texts([_project_text(p) for p in projects], embedder)
    items = [
        (p.get("name", f"project-{i}"), p, vec)
        for i, (p, vec) in enumerate(zip(projects, vectors, strict=True))
    ]
    db.replace_user_projects(github_user, items, model)
    return len(items)


def rank(github_user: str, jd_structured: dict, embedder: Embedder, top_n: int = 10) -> list[dict]:
    """Embed the JD (same model as the cache) and cosine-rank cached projects."""
    jd_vec = embed_one(_jd_text(jd_structured), embedder)
    return db.rank_by_vector(github_user, jd_vec, top_n=top_n)
