"""POST /api/analyse — parse JD + resume, return structured JD + gap analysis."""

from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.deps import get_llm, https, save_upload
from app.security import assert_public_http_url
from app.services.jd_parser import extract_jd_structured, fetch_jd_text
from app.services.resume_parser import parse_resume
from app.services.scorer import gap_analysis_markdown, quick_gap_analysis

router = APIRouter(prefix="/api", tags=["analyse"])


@router.post("/analyse")
async def analyse(
    provider: str = Form("anthropic"),
    model: str = Form(""),
    jd_url: str = Form(""),
    jd_text: str = Form(""),
    linkedin_url: str = Form(""),
    api_key: str = Form(""),
    resume_file: UploadFile = File(...),
):
    llm = get_llm(provider, model, api_key)

    jd_raw = ""
    jd_url_error = ""
    if jd_url.strip():
        try:
            safe_url = assert_public_http_url(jd_url.strip())
        except ValueError as e:
            raise HTTPException(400, f"Invalid job URL: {e}") from e
        # Blocking network call — keep it off the event loop.
        r = await run_in_threadpool(fetch_jd_text, safe_url)
        if r["success"]:
            jd_raw = r["text"]
        else:
            jd_url_error = r.get("error", "")
    if not jd_raw and jd_text.strip():
        jd_raw = jd_text.strip()
    if not jd_raw:
        raise HTTPException(400, jd_url_error or "Provide a job URL or paste the JD text.")

    jd_structured = await run_in_threadpool(extract_jd_structured, jd_raw, llm)

    resume_path = await save_upload(resume_file)
    try:
        resume_data = await run_in_threadpool(parse_resume, resume_path, llm)
    finally:
        try:
            os.remove(resume_path)
        except OSError:
            pass

    gap = await run_in_threadpool(
        quick_gap_analysis, jd_raw, resume_data.get("raw_text", ""), llm
    )
    li = https(linkedin_url) if linkedin_url.strip() else https(resume_data.get("linkedin", ""))

    return {
        "jd_structured": jd_structured,
        "jd_raw": jd_raw,
        "resume_data": {k: v for k, v in resume_data.items() if k != "raw_text"},
        "resume_raw_text": resume_data.get("raw_text", ""),
        "linkedin_url": li,
        "gap": gap,
        "gap_markdown": gap_analysis_markdown(gap),
        "required_keywords": [
            {"keyword": i.get("keyword"), "explanation": i.get("explanation", "")}
            for i in gap.get("required_missing", [])
            if i.get("keyword")
        ],
        "preferred_keywords": [
            {"keyword": i.get("keyword"), "explanation": i.get("explanation", "")}
            for i in gap.get("preferred_missing", [])
            if i.get("keyword")
        ],
    }
