# ADR 0006 — Split DOCX→PDF into a separate converter service

**Status:** Accepted (2026-06-29)

## Context

PDF export uses LibreOffice headless (ADR 0003). On Render's **512 MB** free
instance, `soffice` spikes ~300 MB *in addition to* the resident Python process
(FastAPI + an LLM SDK + document libraries). In a single container the two sum
past 512 MB, so Render OOM-killed the instance during `/generate` — the request
that triggers conversion — and the "Forge" action appeared to fail. Timing the
conversion differently doesn't help: Python keeps its libraries resident, so the
LibreOffice spike always lands on top of them in the same container.

## Decision

Run LibreOffice in its **own** container — a tiny `pdf-service` (FastAPI +
LibreOffice, one `POST /convert` endpoint). The main API delegates conversion to
it over HTTP via `PDF_SERVICE_URL` and no longer installs LibreOffice. Each
container then fits 512 MB on its own: the API holds only Python (~200–300 MB),
and the converter holds a minimal app plus the LibreOffice spike (~350 MB).

Degradation is preserved: if `PDF_SERVICE_URL` is unset (and no local
LibreOffice, e.g. dev), `docx_to_pdf` raises and the build still returns the
DOCX — the app delivers a resume, just without the PDF.

## Consequences

- **The OOM is gone:** the memory-heavy work is isolated; the API stays light and
  its image is smaller/faster to deploy.
- **Free:** two free Render services (or host the converter on any container PaaS
  — e.g. a Hugging Face Space with far more RAM). `render.yaml` defines both and
  auto-injects `PDF_SERVICE_URL`.
- **Clean service boundary** — a small, real microservice split (a nice
  architecture signal), with conversion reusable by anything.
- **Trade-offs:** one more deployable unit; a network hop per conversion; the
  converter cold-starts on the free tier (keep it warm with the same keep-alive
  approach if needed). The interface is a single multipart endpoint, so swapping
  the converter implementation later is trivial.
```
