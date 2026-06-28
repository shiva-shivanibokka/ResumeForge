"""POST /api/fetch-projects — crawl + rank GitHub projects for a JD (SSE)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Form
from fastapi.responses import StreamingResponse

from app.deps import get_llm, https
from app.services.github_parser import parse_github_profile
from app.services.project_matcher import rank_projects_for_jd
from app.sse import SSE_HEADERS, stream_work

router = APIRouter(prefix="/api", tags=["projects"])


@router.post("/fetch-projects")
async def fetch_projects(
    provider: str = Form("anthropic"),
    model: str = Form(""),
    github_url: str = Form(...),
    gh_token: str = Form(""),
    api_key: str = Form(""),
    jd_structured: str = Form(...),  # JSON string
):
    llm = get_llm(provider, model, api_key)
    jd_dict = json.loads(jd_structured)
    gh = https(github_url)
    token = (gh_token or "").strip() or None

    def work(progress):
        gh_result = parse_github_profile(
            gh, llm, token=token, max_repos=100, progress_callback=progress
        )
        if not gh_result["success"]:
            raise RuntimeError(gh_result["error"])
        all_projects = gh_result["projects"]
        progress("Ranking top 10 projects for this JD...")
        ranked = rank_projects_for_jd(jd_dict, all_projects, llm, top_n=10)
        return {"ranked": ranked, "all_projects": all_projects, "count": len(ranked)}

    return StreamingResponse(
        stream_work(work), media_type="text/event-stream", headers=SSE_HEADERS
    )
