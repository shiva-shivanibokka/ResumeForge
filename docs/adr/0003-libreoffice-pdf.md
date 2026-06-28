# ADR 0003 — Render PDFs with LibreOffice headless

**Status:** Accepted (2026-06-28)

## Context

The resume and cover-letter builders produced PDFs with `docx2pdf`, which drives
Microsoft Word via COM automation (Windows) or AppleScript (macOS). There is no
Word on a Linux container, so **every PDF conversion would fail on the deploy
target** — the app would silently ship DOCX-only in production. One call site
even shelled out to `python -c "...convert(r'{path}', ...)"` with file paths
interpolated into the source string (a fragile injection vector).

## Decision

Replace `docx2pdf` with a small `app/services/pdf.py` that converts via
**LibreOffice headless**: `soffice --headless --convert-to pdf`. Arguments are
passed as a list (no shell, no string interpolation), each conversion gets its
own throwaway user-profile directory to avoid lock contention under concurrency,
and there are timeouts and clear errors. The Docker image installs
`libreoffice-writer`.

## Consequences

- **PDF export works on Linux/containers** — the actual deployment target.
- **Both DOCX and PDF** downloads work in production (a hard requirement).
- **No code-injection surface** from path interpolation; no `time.sleep` COM
  band-aid.
- **Trade-off:** the image is larger (LibreOffice + fonts ≈ a few hundred MB) and
  the first conversion is a little slow. Acceptable for this workload; the page
  count and fit logic degrade gracefully to "assume 1 page" if `soffice` is
  absent (e.g. a bare local dev box without LibreOffice).
