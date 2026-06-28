"""
ResumeForge — FastAPI Backend
Exposes all resume generation logic as REST + SSE endpoints.

Endpoints:
  POST /api/analyse          → parse JD + resume + gap analysis
  POST /api/fetch-projects   → fetch + rank GitHub projects (SSE stream)
  POST /api/generate         → full resume generation pipeline (SSE stream)
  POST /api/edit-resume      → apply edits + rebuild resume
  POST /api/cover-letter     → generate cover letter
  POST /api/edit-cover-letter → apply edits to cover letter
  GET  /api/download/{file_id} → serve generated file
  GET  /api/health           → health check

Run:
  cd backend
  uvicorn api:app --reload --port 8000
"""

import os
import uuid
import json
import asyncio
import tempfile
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import anthropic

load_dotenv(override=True)

from app.services.jd_parser import fetch_jd_text, extract_jd_structured
from app.services.resume_parser import parse_resume
from app.services.github_parser import parse_github_profile
from app.services.project_matcher import match_and_tailor, rank_projects_for_jd
from app.services.resume_builder import build_resume, FontConfig
from app.services.cover_letter import (
    generate_cover_letter_text,
    build_cover_letter_docx,
    revise_cover_letter,
)
from app.services.scorer import (
    score_resume,
    extract_resume_text,
    score_card_markdown,
    quick_gap_analysis,
    gap_analysis_markdown,
)

app = FastAPI(title="ResumeForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In production you'd use Redis or a DB. For local + Railway this is fine.
FILE_STORE: dict[str, str] = {}


def _register_file(path: str) -> str:
    """Register a file path and return a unique ID for download."""
    file_id = str(uuid.uuid4())
    FILE_STORE[file_id] = path
    return file_id


def _get_client(api_key: str = "") -> anthropic.Anthropic:
    key = (api_key or "").strip() or os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise HTTPException(
            status_code=401,
            detail="Anthropic API key not found. Set ANTHROPIC_API_KEY in .env.",
        )
    return anthropic.Anthropic(api_key=key)


def _https(url: str) -> str:
    url = (url or "").strip()
    return ("https://" + url) if url and not url.startswith("http") else url


def _sse_line(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


async def _save_upload(file: UploadFile) -> str:
    suffix = Path(file.filename).suffix if file.filename else ".pdf"
    tmp = tempfile.mktemp(suffix=suffix, prefix="rf_upload_")
    content = await file.read()
    Path(tmp).write_bytes(content)
    return tmp


# ENDPOINT 1 — Analyse JD + Resume (fast, ~10-15s, no streaming needed)


@app.post("/api/analyse")
async def analyse(
    jd_url: str = Form(""),
    jd_text: str = Form(""),
    linkedin_url: str = Form(""),
    api_key: str = Form(""),
    resume_file: UploadFile = File(...),
):
    """
    Parse JD + resume. Return structured JD, gap analysis, keyword lists.
    """
    client = _get_client(api_key)

    # JD
    jd_raw = ""
    jd_url_error = ""
    if jd_url.strip():
        r = fetch_jd_text(jd_url.strip())
        if r["success"]:
            jd_raw = r["text"]
        else:
            jd_url_error = r.get("error", "")
    if not jd_raw and jd_text.strip():
        jd_raw = jd_text.strip()
    if not jd_raw:
        if jd_url_error:
            raise HTTPException(400, jd_url_error)
        raise HTTPException(400, "Provide a job URL or paste the JD text.")

    jd_structured = extract_jd_structured(jd_raw, client)

    # Resume
    resume_path = await _save_upload(resume_file)
    try:
        resume_data = parse_resume(resume_path, client)
    finally:
        try:
            os.remove(resume_path)
        except:
            pass

    # Gap analysis
    gap = quick_gap_analysis(jd_raw, resume_data.get("raw_text", ""), client)

    # Patch LinkedIn if provided
    li = (
        _https(linkedin_url)
        if linkedin_url.strip()
        else _https(resume_data.get("linkedin", ""))
    )

    return {
        "jd_structured": jd_structured,
        "jd_raw": jd_raw,
        "resume_data": {k: v for k, v in resume_data.items() if k != "raw_text"},
        "resume_raw_text": resume_data.get("raw_text", ""),
        "linkedin_url": li,
        "gap": gap,
        "gap_markdown": gap_analysis_markdown(gap),
        "required_keywords": [
            {"keyword": i["keyword"], "explanation": i.get("explanation", "")}
            for i in gap.get("required_missing", [])
        ],
        "preferred_keywords": [
            {"keyword": i["keyword"], "explanation": i.get("explanation", "")}
            for i in gap.get("preferred_missing", [])
        ],
    }


# ENDPOINT 2 — Fetch + Rank GitHub Projects  (SSE streaming)


@app.post("/api/fetch-projects")
async def fetch_projects(
    github_url: str = Form(...),
    gh_token: str = Form(""),
    api_key: str = Form(""),
    jd_structured: str = Form(...),  # JSON string
):
    """
    Fetch GitHub repos, rank top 10 for the JD.
    Streams progress via SSE, then sends final JSON.
    """
    client = _get_client(api_key)
    jd_dict = json.loads(jd_structured)
    gh = _https(github_url)
    token = (gh_token or "").strip() or None
    log_queue: list[str] = []

    def _stream():
        def log(msg):
            log_queue.append(msg)
            # We yield from the outer generator, push via queue

        # Run blocking work in a thread
        result_holder = {}
        error_holder = {}

        def _run():
            try:
                gh_result = parse_github_profile(
                    gh,
                    client,
                    token=token,
                    max_repos=100,
                    progress_callback=lambda m: log_queue.append(m),
                )
                if not gh_result["success"]:
                    error_holder["msg"] = gh_result["error"]
                    return
                all_projects = gh_result["projects"]
                log_queue.append(f"Ranking top 10 projects for this JD...")
                ranked = rank_projects_for_jd(jd_dict, all_projects, client, top_n=10)
                result_holder["ranked"] = ranked
                result_holder["all_projects"] = all_projects
            except Exception as e:
                error_holder["msg"] = str(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        import time

        sent = 0
        while t.is_alive() or sent < len(log_queue):
            while sent < len(log_queue):
                yield _sse_line({"type": "progress", "message": log_queue[sent]})
                sent += 1
            time.sleep(0.1)

        if error_holder:
            yield _sse_line({"type": "error", "message": error_holder["msg"]})
            return

        yield _sse_line(
            {
                "type": "done",
                "ranked": result_holder["ranked"],
                "all_projects": result_holder["all_projects"],
                "count": len(result_holder["ranked"]),
            }
        )

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ENDPOINT 3 — Generate Resume  (SSE streaming)


@app.post("/api/generate")
async def generate_resume(
    jd_structured: str = Form(...),  # JSON
    jd_raw: str = Form(...),
    resume_data: str = Form(...),  # JSON
    resume_raw_text: str = Form(""),
    selected_projects: str = Form(...),  # JSON list
    selected_keywords: str = Form("[]"),  # JSON list
    linkedin_url: str = Form(""),
    github_url: str = Form(""),
    page_option: str = Form("1-page"),
    font_family: str = Form("Calibri"),
    api_key: str = Form(""),
):
    client = _get_client(api_key)
    jd_dict = json.loads(jd_structured)
    resume_dict = json.loads(resume_data)
    projects = json.loads(selected_projects)
    keywords = json.loads(selected_keywords)
    one_page = page_option != "2-page"
    log_queue: list[str] = []

    # Patch URLs into resume_dict
    li = _https(linkedin_url)
    gh = _https(github_url)
    if li:
        resume_dict["linkedin_url"] = li
        resume_dict["linkedin"] = "LinkedIn"
    if gh:
        resume_dict["github_url"] = gh
        resume_dict["github"] = "GitHub"

    # Inject selected keywords into JD — prepend to both required_skills AND keywords
    # so Claude sees them prominently in both fields it uses for matching
    if keywords:
        jd_dict["required_skills"] = list(
            dict.fromkeys(keywords + jd_dict.get("required_skills", []))
        )
        jd_dict["keywords"] = list(
            dict.fromkeys(keywords + jd_dict.get("keywords", []))
        )

    def _stream():
        result_holder = {}
        error_holder = {}

        def _run():
            try:
                log_queue.append("Matching projects to JD...")
                matched = match_and_tailor(
                    jd_dict,
                    resume_dict,
                    projects,
                    client,
                    num_projects=min(4, len(projects)),
                    bullets_per_project=3,
                )
                if matched.get("_error"):
                    log_queue.append(f"Warning: {matched['_error']}")

                log_queue.append(
                    f"Selected: {[p['name'] for p in matched.get('selected_projects', [])]}"
                )

                fc = FontConfig(
                    body_font=font_family,
                    name_font=font_family,
                    heading_font=font_family,
                )
                log_queue.append(
                    f"Building {'1-page' if one_page else '2-page'} A4 resume with auto-fit..."
                )

                build_result = build_resume(
                    personal=resume_dict,
                    education=resume_dict.get("education", []),
                    matched_payload=matched,
                    output_dir=None,
                    to_pdf=True,
                    one_page=one_page,
                    font_config=fc,
                    auto_fill=one_page,
                )

                if build_result.get("font_config_used"):
                    fc_used = build_result["font_config_used"]
                    log_queue.append(
                        f"Auto-fit: body={fc_used.get('body_size')}pt "
                        f"heading={fc_used.get('heading_size')}pt "
                        f"name={fc_used.get('name_size')}pt"
                    )

                if build_result.get("error"):
                    log_queue.append(f"Note: {build_result['error']}")

                docx_path = build_result.get("docx_path")
                pdf_path = build_result.get("pdf_path")

                if not docx_path:
                    error_holder["msg"] = "Resume build failed."
                    return

                log_queue.append("Scoring resume...")
                resume_text = extract_resume_text(docx_path)
                scores = score_resume(resume_text, jd_raw, client)
                scores_md = score_card_markdown(scores)
                log_queue.append(
                    f"ATS: {scores.get('ats_score', 0)}/10  "
                    f"JD Match: {scores.get('match_score', 0)}/10"
                )
                log_queue.append("Done!")

                result_holder.update(
                    {
                        "matched_payload": matched,
                        "docx_id": _register_file(docx_path) if docx_path else None,
                        "pdf_id": _register_file(pdf_path) if pdf_path else None,
                        "docx_name": Path(docx_path).name if docx_path else None,
                        "pdf_name": Path(pdf_path).name if pdf_path else None,
                        "scores": scores,
                        "scores_md": scores_md,
                        "job_label": f"{matched.get('job_title', '')} @ {matched.get('company', '')}",
                    }
                )
            except Exception as e:
                import traceback

                error_holder["msg"] = str(e)
                log_queue.append(f"ERROR: {e}")
                log_queue.append(traceback.format_exc())

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        import time

        sent = 0
        while t.is_alive() or sent < len(log_queue):
            while sent < len(log_queue):
                yield _sse_line({"type": "progress", "message": log_queue[sent]})
                sent += 1
            time.sleep(0.1)

        if error_holder:
            yield _sse_line({"type": "error", "message": error_holder["msg"]})
            return

        yield _sse_line({"type": "done", **result_holder})

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ENDPOINT 4 — Edit Resume


@app.post("/api/edit-resume")
async def edit_resume(
    edit_instructions: str = Form(...),
    matched_payload: str = Form(...),  # JSON
    resume_data: str = Form(...),  # JSON
    jd_raw: str = Form(""),
    page_option: str = Form("1-page"),
    font_family: str = Form("Calibri"),
    api_key: str = Form(""),
):
    client = _get_client(api_key)
    matched = json.loads(matched_payload)
    resume_dict = json.loads(resume_data)
    one_page = page_option != "2-page"

    import re as _re

    prompt = f"""You are a professional resume editor.
Apply ONLY the requested edits. Do not change anything not mentioned.

CURRENT PAYLOAD:
{json.dumps(matched, indent=2)[:6000]}

EDIT INSTRUCTIONS:
{edit_instructions}

Return the complete updated JSON payload. Same structure. No markdown fences. No explanation."""

    try:
        resp = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        # Safely get text from the first TextBlock — other block types have no .text
        raw = ""
        for block in resp.content:
            if hasattr(block, "text"):
                raw = block.text.strip()
                break
        raw = _re.sub(r"^```[a-z]*\n?", "", raw)
        raw = _re.sub(r"\n?```$", "", raw)
        updated = json.loads(raw)
    except Exception as e:
        updated = matched

    fc = FontConfig(
        body_font=font_family, name_font=font_family, heading_font=font_family
    )
    result = build_resume(
        personal=resume_dict,
        education=resume_dict.get("education", []),
        matched_payload=updated,
        output_dir=None,
        to_pdf=True,
        one_page=one_page,
        font_config=fc,
        auto_fill=one_page,
    )

    docx_path = result.get("docx_path")
    pdf_path = result.get("pdf_path")

    scores: Optional[dict] = None
    scores_md = ""
    if docx_path and jd_raw:
        scores = score_resume(extract_resume_text(docx_path), jd_raw, client)
        scores_md = score_card_markdown(scores)

    return {
        "matched_payload": updated,
        "docx_id": _register_file(docx_path) if docx_path else None,
        "pdf_id": _register_file(pdf_path) if pdf_path else None,
        "docx_name": Path(docx_path).name if docx_path else None,
        "pdf_name": Path(pdf_path).name if pdf_path else None,
        "scores": scores,  # None if scoring was skipped (no jd_raw / no docx)
        "scores_md": scores_md,
    }


# ENDPOINT 5 — Generate Cover Letter


@app.post("/api/cover-letter")
async def generate_cover_letter(
    tone: str = Form("Professional"),
    extra_instructions: str = Form(""),
    jd_structured: str = Form(...),  # JSON
    resume_data: str = Form(...),  # JSON
    matched_payload: str = Form(...),  # JSON
    selected_keywords: str = Form("[]"),  # JSON
    font_size: str = Form("10.5"),
    bold_body: str = Form("false"),
    api_key: str = Form(""),
):
    client = _get_client(api_key)
    jd_dict = json.loads(jd_structured)
    resume_dict = json.loads(resume_data)
    matched = json.loads(matched_payload)
    keywords = json.loads(selected_keywords)
    fs = float(font_size) if font_size else 10.5
    bold = bold_body.lower() == "true"

    letter_text = generate_cover_letter_text(
        jd_structured=jd_dict,
        resume_data=resume_dict,
        matched_payload=matched,
        selected_keywords=keywords,
        tone=tone,
        client=client,
        extra_instructions=extra_instructions.strip(),
    )
    cl_result = build_cover_letter_docx(
        letter_text, resume_dict, jd_dict, font_size=fs, bold_body=bold
    )

    docx_path = cl_result.get("docx_path")
    pdf_path = cl_result.get("pdf_path")

    return {
        "letter_text": letter_text,
        "docx_id": _register_file(docx_path) if docx_path else None,
        "pdf_id": _register_file(pdf_path) if pdf_path else None,
        "docx_name": Path(docx_path).name if docx_path else None,
        "pdf_name": Path(pdf_path).name if pdf_path else None,
    }


# ENDPOINT 6 — Edit Cover Letter


@app.post("/api/edit-cover-letter")
async def edit_cover_letter(
    edit_instructions: str = Form(...),
    letter_text: str = Form(...),
    jd_structured: str = Form(...),  # JSON
    resume_data: str = Form(...),  # JSON
    font_size: str = Form("10.5"),
    bold_body: str = Form("false"),
    api_key: str = Form(""),
):
    client = _get_client(api_key)
    jd_dict = json.loads(jd_structured)
    resume_dict = json.loads(resume_data)
    fs = float(font_size) if font_size else 10.5
    bold = bold_body.lower() == "true"

    updated_text = revise_cover_letter(
        letter_text, edit_instructions, jd_dict, resume_dict, client
    )
    cl_result = build_cover_letter_docx(
        updated_text, resume_dict, jd_dict, font_size=fs, bold_body=bold
    )

    docx_path = cl_result.get("docx_path")
    pdf_path = cl_result.get("pdf_path")

    return {
        "letter_text": updated_text,
        "docx_id": _register_file(docx_path) if docx_path else None,
        "pdf_id": _register_file(pdf_path) if pdf_path else None,
        "docx_name": Path(docx_path).name if docx_path else None,
        "pdf_name": Path(pdf_path).name if pdf_path else None,
    }


# ENDPOINT 7 — Download File


@app.get("/api/download/{file_id}")
async def download_file(file_id: str):
    path = FILE_STORE.get(file_id)
    if not path or not Path(path).exists():
        raise HTTPException(404, "File not found or expired.")

    suffix = Path(path).suffix.lower()
    filename = Path(path).name
    media = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if suffix == ".docx"
        else "application/pdf"
    )

    # PDFs: inline so the browser renders them in iframes (preview).
    # DOCX: attachment so they always trigger a save dialog.
    disposition = "inline" if suffix == ".pdf" else "attachment"
    return FileResponse(
        path=path,
        filename=filename,
        media_type=media,
        content_disposition_type=disposition,
    )


# ENDPOINT 8 — Health


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "ResumeForge API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
