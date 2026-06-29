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


def _resume_font(font_family: str, font_size: str, one_page: bool) -> tuple[FontConfig, bool]:
    """Build (FontConfig, auto_fill). font_size 'auto'/'' → proportional auto-fit;
    a number → fixed body size (name ×2.2, heading ×1.1), auto-fit off."""
    size = (font_size or "auto").strip().lower()
    if size in ("", "auto", "auto-fit"):
        fc = FontConfig(body_font=font_family, name_font=font_family, heading_font=font_family)
        return fc, one_page
    try:
        b = float(size)
    except ValueError:
        fc = FontConfig(body_font=font_family, name_font=font_family, heading_font=font_family)
        return fc, one_page
    fc = FontConfig(
        body_font=font_family,
        name_font=font_family,
        heading_font=font_family,
        body_size=b,
        heading_size=round(b * 1.1, 1),
        name_size=round(b * 2.2, 1),
    )
    return fc, False


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


def merge_skills(tailored, extra: list[str] | None = None) -> dict:
    """Clean the skills section: drop duplicates across categories (case-insensitive,
    first occurrence wins, category order preserved) and append any `extra` skills not
    already present to the LAST category — no junk 'Additional/Other' catch-all heading.
    """
    if not isinstance(tailored, dict):
        tailored = {}
    seen: set[str] = set()
    cleaned: dict[str, str] = {}
    for cat, val in tailored.items():
        items = []
        for s in _flatten_skills(val):
            k = s.lower()
            if k not in seen:
                seen.add(k)
                items.append(s)
        if items:
            cleaned[cat] = ", ".join(items)

    leftovers = []
    for s in extra or []:
        if isinstance(s, str) and s.strip() and s.strip().lower() not in seen:
            seen.add(s.strip().lower())
            leftovers.append(s.strip())
    if leftovers:
        if cleaned:
            last = next(reversed(cleaned))
            cleaned[last] = cleaned[last] + ", " + ", ".join(leftovers)
        else:
            cleaned["Skills"] = ", ".join(leftovers)
    return cleaned


def _augment_skills(matched: dict, resume_dict: dict, selected_keywords: list) -> None:
    """Dedupe the LLM's skills and fold in the user's explicitly selected keywords.
    Relies on the prompt to keep the candidate's existing skills (it's told to), but
    guarantees a clean, non-redundant section without a catch-all heading."""
    matched["tailored_skills"] = merge_skills(
        matched.get("tailored_skills"),
        [k for k in (selected_keywords or []) if isinstance(k, str)],
    )


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
    font_size: str = Form("auto"),
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

        fc, auto = _resume_font(font_family, font_size, one_page)
        progress(f"Building {'1-page' if one_page else '2-page'} A4 resume...")
        build_result = build_resume(
            personal=resume_dict, education=resume_dict.get("education", []),
            matched_payload=matched, output_dir=None, to_pdf=True,
            one_page=one_page, font_config=fc, auto_fill=auto,
        )
        if build_result.get("error"):
            progress(f"Note: {build_result['error']}")

        docx_path = build_result.get("docx_path")
        pdf_path = build_result.get("pdf_path")
        if not docx_path:
            raise RuntimeError("Resume build failed.")

        # Score the ORIGINAL resume too, so the UI can show before → after lift.
        before_scores = None
        if resume_raw_text.strip():
            progress("Scoring your original resume for comparison...")
            try:
                before_scores = score_resume(resume_raw_text, jd_raw, llm)
            except Exception:  # noqa: BLE001 - comparison is best-effort
                before_scores = None

        progress("Scoring tailored resume...")
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
            "before_scores": before_scores,
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
    font_size: str = Form("auto"),
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

    fc, auto = _resume_font(font_family, font_size, one_page)
    result = build_resume(
        personal=resume_dict, education=resume_dict.get("education", []),
        matched_payload=updated, output_dir=None, to_pdf=True,
        one_page=one_page, font_config=fc, auto_fill=auto,
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


@router.post("/rebuild-resume")
async def rebuild_resume(
    matched_payload: str = Form(...),
    resume_data: str = Form(...),
    page_option: str = Form("1-page"),
    font_family: str = Form("Calibri"),
    font_size: str = Form("auto"),
    add_keywords: str = Form("[]"),  # JSON list of skills to insert before rebuilding
):
    """Re-render the resume with a new font/size/length and/or freshly inserted
    skills — NO LLM call. Used by 'Apply format' and the click-to-add missing
    keywords, so layout/skill tweaks are instant and don't cost a model call.
    Returns the (possibly updated) matched_payload so the client stays in sync."""
    matched = json.loads(matched_payload)
    resume_dict = json.loads(resume_data)
    extra = [k for k in json.loads(add_keywords or "[]") if isinstance(k, str)]
    if extra:
        matched["tailored_skills"] = merge_skills(matched.get("tailored_skills"), extra)

    one_page = page_option != "2-page"
    fc, auto = _resume_font(font_family, font_size, one_page)
    result = build_resume(
        personal=resume_dict, education=resume_dict.get("education", []),
        matched_payload=matched, output_dir=None, to_pdf=True,
        one_page=one_page, font_config=fc, auto_fill=auto,
    )
    docx_path = result.get("docx_path")
    pdf_path = result.get("pdf_path")
    store = get_store()
    return {
        "matched_payload": matched,
        "docx_id": store.register(docx_path) if docx_path else None,
        "pdf_id": store.register(pdf_path) if pdf_path else None,
        "docx_name": Path(docx_path).name if docx_path else None,
        "pdf_name": Path(pdf_path).name if pdf_path else None,
    }
