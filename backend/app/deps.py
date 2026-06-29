"""Shared request helpers used by the routers."""

from __future__ import annotations

import os
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
    """Validate the type, then stream the upload to a temp file enforcing the size
    cap as we go — so an oversized file is rejected without buffering it all in RAM
    (which could OOM a small instance before a post-read size check fires)."""
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    # Cheap extension check up front (size 0 => validate type only), before reading.
    try:
        validate_upload(file.filename or "", 0, settings.max_upload_mb)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    suffix = Path(file.filename).suffix if file.filename else ".pdf"
    fd, tmp = tempfile.mkstemp(suffix=suffix, prefix="rf_upload_")
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Max is {settings.max_upload_mb} MB.",
                    )
                out.write(chunk)
    except HTTPException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return tmp
