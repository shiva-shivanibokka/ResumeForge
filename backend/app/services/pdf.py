"""DOCX -> PDF conversion via LibreOffice headless.

Replaces `docx2pdf`, which drives Microsoft Word through COM automation and
therefore only works on Windows/macOS with Word installed — it cannot run on a
Linux container, which is the deployment target. LibreOffice headless runs
anywhere (and is installed in the Docker image).

`soffice` is invoked with arguments passed as a list (never a shell string), so
file paths cannot be injected into a command. Each conversion uses its own
throwaway user-profile dir to avoid the "another LibreOffice instance is using
the profile" lock contention that bites concurrent conversions.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def _find_soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    # Common Windows install location (dev convenience).
    win = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
    return str(win) if win.exists() else None


def soffice_available() -> bool:
    return _find_soffice() is not None


def docx_to_pdf(docx_path: str, out_dir: str | None = None) -> str:
    """Convert a .docx to .pdf and return the PDF path.

    Raises RuntimeError if LibreOffice is unavailable or conversion fails.
    """
    soffice = _find_soffice()
    if not soffice:
        raise RuntimeError(
            "LibreOffice (soffice) not found. Install libreoffice-writer to enable "
            "PDF export."
        )

    src = Path(docx_path)
    if not src.exists():
        raise RuntimeError(f"Source docx not found: {docx_path}")

    out = Path(out_dir) if out_dir else src.parent
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="rf_soffice_profile_") as profile:
        try:
            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--norestore",
                    f"-env:UserInstallation=file://{Path(profile).as_uri().removeprefix('file://')}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(out),
                    str(src),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("PDF conversion timed out.") from e
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or b"").decode(errors="replace")[:500]
            raise RuntimeError(f"PDF conversion failed: {stderr}") from e

    pdf_path = out / (src.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError("PDF conversion produced no output file.")
    return str(pdf_path)


def count_pdf_pages(pdf_path: str) -> int:
    """Return the page count of a PDF using PyMuPDF."""
    import fitz  # PyMuPDF

    with fitz.open(pdf_path) as doc:
        return doc.page_count
