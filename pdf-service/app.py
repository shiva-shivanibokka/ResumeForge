"""ResumeForge PDF converter — a tiny, single-purpose service.

LibreOffice spikes ~300 MB, which OOM-kills the main API on Render's 512 MB free
tier when it sits on top of the resident Python app. Isolating conversion here
means this container holds only a minimal FastAPI app + LibreOffice, so the spike
has the whole 512 MB to itself, and the main API stays light.

POST /convert  (multipart 'file' = .docx)  -> application/pdf
GET  /health
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

app = FastAPI(title="ResumeForge PDF Service", version="1.0.0")


def _soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    return None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "pdf", "soffice": _soffice() is not None}


@app.post("/convert")
async def convert(file: UploadFile = File(...)):
    soffice = _soffice()
    if not soffice:
        raise HTTPException(500, "LibreOffice not available in the converter image.")
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(400, "Expected a .docx file.")

    content = await file.read()
    with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as profile:
        src = Path(work) / "input.docx"
        src.write_bytes(content)
        try:
            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--norestore",
                    f"-env:UserInstallation=file://{profile}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    work,
                    str(src),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as e:
            raise HTTPException(504, "Conversion timed out.") from e
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or b"").decode(errors="replace")[:300]
            raise HTTPException(500, f"Conversion failed: {detail}") from e

        pdf = src.with_suffix(".pdf")
        if not pdf.exists():
            raise HTTPException(500, "Conversion produced no output.")
        return Response(content=pdf.read_bytes(), media_type="application/pdf")
