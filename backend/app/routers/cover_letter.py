"""POST /api/cover-letter — generate; POST /api/edit-cover-letter — revise."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Form

from app.deps import get_llm
from app.services.cover_letter import (
    build_cover_letter_docx,
    generate_cover_letter_text,
    revise_cover_letter,
)
from app.store import get_store

router = APIRouter(prefix="/api", tags=["cover-letter"])


def _file_fields(cl_result: dict) -> dict:
    store = get_store()
    docx_path = cl_result.get("docx_path")
    pdf_path = cl_result.get("pdf_path")
    return {
        "docx_id": store.register(docx_path) if docx_path else None,
        "pdf_id": store.register(pdf_path) if pdf_path else None,
        "docx_name": Path(docx_path).name if docx_path else None,
        "pdf_name": Path(pdf_path).name if pdf_path else None,
    }


@router.post("/cover-letter")
async def generate_cover_letter(
    provider: str = Form("anthropic"),
    model: str = Form(""),
    tone: str = Form("Professional"),
    extra_instructions: str = Form(""),
    jd_structured: str = Form(...),
    resume_data: str = Form(...),
    matched_payload: str = Form(...),
    selected_keywords: str = Form("[]"),
    font_size: str = Form("10.5"),
    bold_body: str = Form("false"),
    api_key: str = Form(""),
):
    llm = get_llm(provider, model, api_key)
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
        llm=llm,
        extra_instructions=extra_instructions.strip(),
    )
    cl_result = build_cover_letter_docx(
        letter_text, resume_dict, jd_dict, font_size=fs, bold_body=bold
    )
    return {"letter_text": letter_text, **_file_fields(cl_result)}


@router.post("/edit-cover-letter")
async def edit_cover_letter(
    provider: str = Form("anthropic"),
    model: str = Form(""),
    edit_instructions: str = Form(...),
    letter_text: str = Form(...),
    jd_structured: str = Form(...),
    resume_data: str = Form(...),
    font_size: str = Form("10.5"),
    bold_body: str = Form("false"),
    api_key: str = Form(""),
):
    llm = get_llm(provider, model, api_key)
    jd_dict = json.loads(jd_structured)
    resume_dict = json.loads(resume_data)
    fs = float(font_size) if font_size else 10.5
    bold = bold_body.lower() == "true"

    updated_text = revise_cover_letter(letter_text, edit_instructions, jd_dict, resume_dict, llm)
    cl_result = build_cover_letter_docx(
        updated_text, resume_dict, jd_dict, font_size=fs, bold_body=bold
    )
    return {"letter_text": updated_text, **_file_fields(cl_result)}
