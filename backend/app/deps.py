"""Shared request helpers used by the routers."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import get_settings
from app.llm import LLMError, LLMProvider, get_provider
from app.security import validate_upload

_KIND_TO_STATUS = {
    "auth": 401,
    "rate_limit": 429,
    "timeout": 504,
    "bad_request": 400,
    "server": 502,
    "unknown": 502,
}


def get_llm(provider: str, model: str, api_key: str) -> LLMProvider:
    """Resolve an LLMProvider or raise an HTTPException with a sensible status."""
    try:
        return get_provider(provider, api_key=api_key or None, model=model or None)
    except LLMError as e:
        raise HTTPException(status_code=_KIND_TO_STATUS.get(e.kind, 400), detail=str(e)) from e


def https(url: str) -> str:
    url = (url or "").strip()
    return ("https://" + url) if url and not url.startswith("http") else url


async def save_upload(file: UploadFile) -> str:
    """Validate (type + size) and persist an upload to a temp file; return its path."""
    content = await file.read()
    settings = get_settings()
    try:
        validate_upload(file.filename or "", len(content), settings.max_upload_mb)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    suffix = Path(file.filename).suffix if file.filename else ".pdf"
    fd, tmp = tempfile.mkstemp(suffix=suffix, prefix="rf_upload_")
    Path(tmp).write_bytes(content)
    import os

    os.close(fd)
    return tmp
