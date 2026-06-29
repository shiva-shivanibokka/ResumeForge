---
title: ResumeForge API
emoji: 🔥
colorFrom: purple
colorTo: red
sdk: docker
app_port: 8000
pinned: false
---

# ResumeForge API

FastAPI backend for [ResumeForge](https://github.com/shiva-shivanibokka/ResumeForge)
— multi-provider AI resume/cover-letter generation, RAG project matching
(pgvector), and DOCX/PDF export.

This folder is deployable as a **Hugging Face Space** (Docker). The frontmatter
above tells HF to build the `Dockerfile` and route traffic to port 8000.

## Run locally
```bash
pip install -r requirements.txt
cp .env.example .env          # add provider keys, DATABASE_URL, etc.
uvicorn app.main:app --reload --port 8000
```
Tests: `pytest` · Lint: `ruff check app`.

## Required environment variables (set as Space secrets)
| Var | Purpose |
|---|---|
| `ALLOWED_ORIGINS` | Frontend origin(s); `*.vercel.app` is allowed by default |
| `PDF_SERVICE_URL` | URL of the DOCX→PDF converter service |
| `DATABASE_URL` | Postgres (Neon) for the RAG embedding cache |
| `GOOGLE_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GROQ_API_KEY` | Optional server-side LLM keys |
| `GITHUB_TOKEN` | Optional — raises GitHub API rate limit |

See the [main README](https://github.com/shiva-shivanibokka/ResumeForge) for full
architecture and ADRs.
