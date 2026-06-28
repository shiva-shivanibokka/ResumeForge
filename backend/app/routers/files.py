"""Serve generated files by opaque id (backed by the TTL file store)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.store import get_store

router = APIRouter(prefix="/api", tags=["files"])

_DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("/download/{file_id}")
async def download_file(file_id: str):
    path = get_store().get(file_id)
    if path is None:
        raise HTTPException(404, "File not found or expired.")

    suffix = path.suffix.lower()
    media = _DOCX_MEDIA if suffix == ".docx" else "application/pdf"
    # PDFs inline (iframe preview); DOCX as attachment (save dialog).
    disposition = "inline" if suffix == ".pdf" else "attachment"
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type=media,
        content_disposition_type=disposition,
    )
