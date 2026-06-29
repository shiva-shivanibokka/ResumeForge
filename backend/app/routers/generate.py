"""POST /api/generate — full resume generation pipeline (SSE).
POST /api/edit-resume — apply edits + rebuild + rescore.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, Form
from fastapi.responses import StreamingResponse

from app.deps import get_llm, https
from app.llm import LLMError
from app.services.project_matcher import match_and_tailor
from app.services.resume_builder import FontConfig, build_resume
from app.services.scorer import extract_resume_text, score_card_markdown, score_resume
from app.sse import SSE_HEADERS, stream_work
from app.store import get_store

router = APIRouter(prefix="/api", tags=["generate"])


def _inject_keywords(jd_dict: dict, keywords: list) -> None:
    if keywords:
        jd_dict["required_skills"] = list(
            dict.fromkeys(keywords + jd_dict.get("required_skills", []))
        )
        jd_dict["keywords"] = list(dict.fromkeys(keywords + jd_dict.get("keywords", [])))


def _flatten_skills(skills) -> list[str]:
    """Normalize skills (list | dict | comma-string | nested) to a flat string list."""
    out: list[str] = []
    if isinstance(skills, dict):
        for v in skills.values():
            out += _flatten_skills(v)
    elif isinstance(skills, list):
        for item in skills:
            if isinstance(item, str):
                out.append(item.strip())
            elif isinstance(item, dict):
                out += _flatten_skills(item.get("skills") or list(item.values()))
    elif isinstance(skills, str):
        out += [s.strip() for s in skills.split(",") if s.strip()]
    return [s for s in out if s]


def _augment_skills(matched: dict, resume_dict: dict, selected_keywords: list) -> None:
    """Guarantee the resume keeps EVERY existing skill plus the selected keywords.

    The LLM is asked to preserve skills, but it sometimes drops them — this is the
    safety net so the skills section is additive, never lossy.
    """
    tailored = matched.get("tailored_skills")
    if not isinstance(tailored, dict):
        tailored = {}

    present = {s.lower() for v in tailored.values() for s in _flatten_skills(v)}
    desired = _flatten_skills(resume_dict.get("skills")) + [
        k for k in (selected_keywords or []) if isinstance(k, str)
    ]

    missing, seen = [], set()
    for s in desired:
        key = s.lower()
        if key and key not in present and key not in seen:
            missing.append(s)
            seen.add(key)

    if missing:
        existing = _flatten_skills(tailored.get("Additional Skills"))
        tailored["Additional Skills"] = ", ".join(existing + missing)
    matched["tailored_skills"] = tailored


@router.post("/generate")
async def generate_resume(
    provider: str = Form("anthropic"),
    model: str = Form(""),
    jd_structured: str = Form(...),
    jd_raw: str = Form(...),
    resume_data: str = Form(...),
    resume_raw_text: str = Form(""),
    selected_projects: str = Form(...),
    selected_keywords: str = Form("[]"),
    linkedin_url: str = Form(""),
    github_url: str = Form(""),
    page_option: str = Form("1-page"),
    font_family: str = Form("Calibri"),
    api_key: str = Form(""),
):
    llm = get_llm(provider, model, api_key)
    jd_dict = json.loads(jd_structured)
    resume_dict = json.loads(resume_data)
    projects = json.loads(selected_projects)
    keywords = json.loads(selected_keywords)
    one_page = page_option != "2-page"

    li, gh = https(linkedin_url), https(github_url)
    if li:
        resume_dict["linkedin_url"], resume_dict["linkedin"] = li, "LinkedIn"
    if gh:
        resume_dict["github_url"], resume_dict["github"] = gh, "GitHub"
    _inject_keywords(jd_dict, keywords)

    store = get_store()

    def work(progress):
        progress("Matching projects to JD...")
        matched = match_and_tailor(
            jd_dict, resume_dict, projects, llm,
            num_projects=min(4, len(projects)), bullets_per_project=3,
        )
        if matched.get("_error"):
            detail = str(matched["_error"])
            is_quota = any(
                s in detail.lower()
                for s in ("resource_exhausted", "429", "quota", "rate limit", "rate_limit")
            )
            hint = (
                "rate limit or exhausted quota. Try a different engine/model "
                "(Groq is free and fast), or check your API key's quota."
                if is_quota
                else "the model returned an error. Try again, or pick a different engine/model."
            )
            raise RuntimeError(f"Couldn't tailor with {provider}/{model or 'default'}: {hint}")

        # Keep every existing skill + the user's selected keywords (never drop skills).
        _augment_skills(matched, resume_dict, keywords)
        progress(f"Selected: {[p.get('name', '') for p in matched.get('selected_projects', [])]}")

        fc = FontConfig(body_font=font_family, name_font=font_family, heading_font=font_family)
        progress(f"Building {'1-page' if one_page else '2-page'} A4 resume with auto-fit...")
        build_result = build_resume(
            personal=resume_dict, education=resume_dict.get("education", []),
            matched_payload=matched, output_dir=None, to_pdf=True,
            one_page=one_page, font_config=fc, auto_fill=one_page,
        )
        if build_result.get("error"):
            progress(f"Note: {build_result['error']}")

        docx_path = build_result.get("docx_path")
        pdf_path = build_result.get("pdf_path")
        if not docx_path:
            raise RuntimeError("Resume build failed.")

        progress("Scoring resume...")
        scores = score_resume(extract_resume_text(docx_path), jd_raw, llm)
        progress(f"ATS: {scores.get('ats_score', 0)}/10  JD Match: {scores.get('match_score', 0)}/10")
        progress("Done!")

        return {
            "matched_payload": matched,
            "docx_id": store.register(docx_path) if docx_path else None,
            "pdf_id": store.register(pdf_path) if pdf_path else None,
            "docx_name": Path(docx_path).name if docx_path else None,
            "pdf_name": Path(pdf_path).name if pdf_path else None,
            "scores": scores,
            "scores_md": score_card_markdown(scores),
            "job_label": f"{matched.get('job_title', '')} @ {matched.get('company', '')}",
        }

    return StreamingResponse(stream_work(work), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/edit-resume")
async def edit_resume(
    provider: str = Form("anthropic"),
    model: str = Form(""),
    edit_instructions: str = Form(...),
    matched_payload: str = Form(...),
    resume_data: str = Form(...),
    jd_raw: str = Form(""),
    page_option: str = Form("1-page"),
    font_family: str = Form("Calibri"),
    api_key: str = Form(""),
):
    llm = get_llm(provider, model, api_key)
    matched = json.loads(matched_payload)
    resume_dict = json.loads(resume_data)
    one_page = page_option != "2-page"

    prompt = (
        "You are a professional resume editor.\n"
        "Apply ONLY the requested edits. Do not change anything not mentioned.\n\n"
        f"CURRENT PAYLOAD:\n{json.dumps(matched, indent=2)[:6000]}\n\n"
        f"EDIT INSTRUCTIONS:\n{edit_instructions}\n\n"
        "Return the complete updated JSON payload. Same structure. No markdown fences. No explanation."
    )
    try:
        raw = llm.complete(prompt=prompt, max_tokens=4000).text
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        updated = json.loads(raw)
    except (LLMError, ValueError, json.JSONDecodeError):
        updated = matched  # keep prior payload if the edit can't be parsed

    fc = FontConfig(body_font=font_family, name_font=font_family, heading_font=font_family)
    result = build_resume(
        personal=resume_dict, education=resume_dict.get("education", []),
        matched_payload=updated, output_dir=None, to_pdf=True,
        one_page=one_page, font_config=fc, auto_fill=one_page,
    )
    docx_path = result.get("docx_path")
    pdf_path = result.get("pdf_path")

    scores: dict | None = None
    scores_md = ""
    if docx_path and jd_raw:
        scores = score_resume(extract_resume_text(docx_path), jd_raw, llm)
        scores_md = score_card_markdown(scores)

    store = get_store()
    return {
        "matched_payload": updated,
        "docx_id": store.register(docx_path) if docx_path else None,
        "pdf_id": store.register(pdf_path) if pdf_path else None,
        "docx_name": Path(docx_path).name if docx_path else None,
        "pdf_name": Path(pdf_path).name if pdf_path else None,
        "scores": scores,
        "scores_md": scores_md,
    }
