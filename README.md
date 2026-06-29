# ResumeForge 🔥

**Forge a tailored, ATS-scored resume and cover letter from a job description, your resume, and your GitHub — using the LLM provider of your choice.**

ResumeForge takes your raw materials (a job posting, your current resume, your GitHub profile), reforges them for one specific role, and scores the result against the job. Pick your engine — **Anthropic Claude, OpenAI, Google Gemini, or Groq** — and bring your own key (Gemini and Groq have free tiers, so the live demo costs nothing to run).

> **Live demo:** https://resume-forge-eight-olive.vercel.app · **API docs:** https://resumeforge-api-pe93.onrender.com/docs (auto-generated OpenAPI)
>
> _The backend is on Render's free tier — the first request after idle may take ~30–60s to wake._

---

## What it does

1. **Materials** — paste a job URL or text, upload your resume (PDF/DOCX), point at your GitHub.
2. **Heat** — the app extracts the job's structured requirements, runs a gap analysis (which keywords you're missing), crawls and ranks your public repos for relevance, and lets you pick what to feature.
3. **Forge** — it rewrites your projects/skills/experience tailored to the role, builds an auto-fit A4 resume (DOCX **and** PDF), and scores ATS-readiness + JD-match.
4. **Temper** — generates a matching cover letter you can refine and download.

## Architecture

A **Vite + React SPA** talks to a **FastAPI** backend over REST + SSE. The backend hides every LLM behind one `LLMProvider` interface, so the provider is a runtime choice. PDFs render via **LibreOffice headless** (works on Linux/containers, unlike `docx2pdf`).

```
                        ┌──────────────────────────────────────────────┐
  Browser               │  FastAPI backend (app/)                      │
 ┌─────────────┐  REST  │  routers ─ deps ─ services ─┐                │
 │ Vite + React│ ◄────► │   /analyse   /generate(SSE) │                │
 │   SPA       │  +SSE  │   /fetch-projects(SSE)      │                │
 │ (the Forge) │        │   /cover-letter  /providers │                │
 └─────────────┘        │        │           │        │                │
   VITE_API_URL         │        ▼           ▼        ▼                │
                        │   LLMProvider    LibreOffice   TTL FileStore │
                        │   ├ Anthropic    (DOCX→PDF)    (downloads)   │
                        │   ├ OpenAI                                    │
                        │   ├ Gemini   ──► one .complete() interface    │
                        │   └ Groq                                      │
                        └──────────────────────────────────────────────┘
```

Key design decisions are recorded as ADRs in [`docs/adr/`](docs/adr/):
- [0001 — SPA + FastAPI split (dropping Next.js)](docs/adr/0001-spa-fastapi-split.md)
- [0002 — Multi-provider LLM abstraction](docs/adr/0002-multi-provider-llm.md)
- [0003 — LibreOffice for PDF rendering](docs/adr/0003-libreoffice-pdf.md)
- [0004 — Ephemeral TTL file store](docs/adr/0004-ephemeral-file-store.md)

## Tech stack

| Layer | Choices |
|---|---|
| Frontend | Vite, React 19, TypeScript (strict), Tailwind v4, Motion, Zustand |
| Backend | Python 3.11, FastAPI, pydantic-settings, structlog |
| LLM | Anthropic / OpenAI / Google Gemini / Groq (pluggable) |
| Documents | python-docx, PyMuPDF, LibreOffice headless |
| Ops | Docker, GitHub Actions CI, Render (API) + Cloudflare Pages/Vercel (SPA) |

## Run it locally

**Backend** (Python 3.11+; LibreOffice optional locally — PDF export degrades to DOCX-only without it):

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate    # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                 # optional: add provider keys
uvicorn app.main:app --reload --port 8000
```

Or prod-like with Docker (LibreOffice included):

```bash
docker compose up --build        # backend on http://localhost:8000
```

**Frontend**:

```bash
cd frontend
npm install
cp .env.example .env             # leave VITE_API_URL blank to use the dev proxy
npm run dev                      # http://localhost:5173
```

Open http://localhost:5173, pick a provider, paste a key, and forge.

## Configuration

Backend env vars (see `backend/.env.example`) — all optional except CORS in prod:

| Var | Purpose |
|---|---|
| `ALLOWED_ORIGINS` | Comma-separated frontend origins (CORS) |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` / `GROQ_API_KEY` | Optional server-side keys (users can also bring their own) |
| `GITHUB_TOKEN` | Optional — raises GitHub API rate limit 60→5000/hr |
| `FILE_TTL_SECONDS`, `MAX_UPLOAD_MB`, `REQUEST_TIMEOUT_S`, `LLM_MAX_RETRIES` | Tunables (sensible defaults) |

Frontend: `VITE_API_URL` — the backend base URL (blank → Vite proxy in dev).

## Deploy (free tier)

**Backend → Render** (Docker): push to GitHub, then Render → New → Blueprint → select this repo (`render.yaml`). Set `ALLOWED_ORIGINS` to your frontend URL and any provider keys. Health check is `/api/health`. (Free instances cold-start after idle.)

**Frontend → Cloudflare Pages / Vercel**: build command `npm run build`, output `dist`, and set `VITE_API_URL` to the Render URL. Then add that frontend origin to the backend's `ALLOWED_ORIGINS`.

## Tests & quality

```bash
cd backend && pytest          # unit + API smoke tests
cd backend && ruff check app  # lint
cd frontend && npm run build  # type-check + bundle
```

CI (`.github/workflows/ci.yml`) runs all of the above on every push/PR.

## Security notes

- No secrets in the repo; keys come from env or per-request (BYO key).
- The JD-URL fetcher has an **SSRF guard** (rejects private/loopback/metadata hosts).
- Uploads are validated (type + size); generated files expire from a TTL store.
