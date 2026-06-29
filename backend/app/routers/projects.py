"""POST /api/fetch-projects — rank GitHub projects for a JD (SSE).
GET  /api/projects/cache — report whether a user's embeddings are cached.

When a database + embedding key are available, projects are crawled, summarized,
and embedded ONCE into pgvector, then future ranking is a fast cosine search
(no re-crawl). `force_reembed=true` refreshes the cache. Without those, it falls
back to crawling + LLM ranking every time.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Form, Query
from fastapi.responses import StreamingResponse

from app import db
from app.deps import get_llm, https
from app.embeddings import resolve_embedder
from app.services import rag
from app.services.github_parser import parse_github_profile, parse_github_url
from app.services.project_matcher import rank_projects_for_jd
from app.sse import SSE_HEADERS, stream_work

router = APIRouter(prefix="/api", tags=["projects"])


@router.get("/projects/cache")
def projects_cache(github_url: str = Query("")):  # sync: DB call runs in a threadpool
    """Cache status for the UI: whether this GitHub user's projects are embedded."""
    user = parse_github_url(https(github_url)) if github_url.strip() else None
    if not user or not db.is_enabled():
        return {"enabled": db.is_enabled(), "cached": False, "count": 0, "embedded_at": None}
    return {"enabled": True, **db.cache_status(user)}


@router.post("/fetch-projects")
async def fetch_projects(
    provider: str = Form("anthropic"),
    model: str = Form(""),
    github_url: str = Form(...),
    gh_token: str = Form(""),
    api_key: str = Form(""),
    jd_structured: str = Form(...),  # JSON string
    force_reembed: str = Form("false"),
):
    llm = get_llm(provider, model, api_key)
    jd_dict = json.loads(jd_structured)
    gh = https(github_url)
    user = parse_github_url(gh)
    token = (gh_token or "").strip() or None
    reembed = force_reembed.lower() == "true"
    embedder = resolve_embedder(provider, api_key)
    use_rag = bool(user) and db.is_enabled() and embedder is not None

    def crawl_summarize(progress):
        # Cap fan-out: each repo costs several GitHub calls + an LLM call, so crawl
        # only the 30 most-recently-updated (repos are returned newest-first).
        gh_result = parse_github_profile(
            gh, llm, token=token, max_repos=30, progress_callback=progress
        )
        if not gh_result["success"]:
            raise RuntimeError(gh_result["error"])
        return gh_result["projects"]

    def work(progress):
        all_projects: list = []
        if use_rag:
            try:
                cached = db.cache_status(user)
                # Reuse the cache only if it exists AND was embedded with this same
                # model (a different engine -> different vector space -> re-embed).
                fresh = (
                    cached["cached"]
                    and not reembed
                    and db.cached_model(user) == embedder[1]
                )
                if fresh:
                    progress(
                        f"Using {cached['count']} cached projects "
                        f"(embedded {cached['embedded_at']})."
                    )
                else:
                    all_projects = crawl_summarize(progress)
                    count = rag.embed_and_store(user, all_projects, embedder, progress)
                    progress(f"Cached {count} embedded projects.")
                progress("Ranking projects for this JD (vector search)...")
                ranked = rag.rank(user, jd_dict, embedder, top_n=10)
                if ranked:
                    return {"ranked": ranked, "count": len(ranked), "mode": "rag"}
                progress("Vector search returned nothing — using direct ranking...")
            except Exception as e:  # noqa: BLE001 - degrade to the LLM path
                progress(f"Embedding path unavailable — using direct ranking. ({e})")

        # Fallback: crawl (if not already) + LLM rank.
        if not all_projects:
            all_projects = crawl_summarize(progress)
        progress("Ranking top 10 projects for this JD...")
        ranked = rank_projects_for_jd(jd_dict, all_projects, llm, top_n=10)
        return {"ranked": ranked, "count": len(ranked), "mode": "llm"}

    return StreamingResponse(
        stream_work(work), media_type="text/event-stream", headers=SSE_HEADERS
    )
