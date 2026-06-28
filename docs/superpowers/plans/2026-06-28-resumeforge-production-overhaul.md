# ResumeForge Production Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn ResumeForge from a dual Gradio/Next.js prototype into a single, production-grade, cloud-deployable, multi-provider AI resume-tailoring product that demonstrates senior-level engineering judgment to hiring teams.

**Architecture:** A FastAPI backend (consolidated into one `app/` package) exposes REST + SSE endpoints behind a clean service layer. An `LLMProvider` strategy abstraction lets the user pick Anthropic / OpenAI / Gemini / Groq with a bring-your-own-key model selector. PDFs are rendered with LibreOffice headless (Linux-safe) instead of `docx2pdf`. A Vite + React single-page app (Tailwind v4 + Framer Motion + a custom design system) replaces the Next.js frontend. Everything is containerized, CI-gated, observable, and documented with ADRs.

**Tech Stack:** Python 3.11, FastAPI, pydantic-settings, structlog, anthropic / openai / google-genai / groq SDKs, python-docx, PyMuPDF, LibreOffice (headless), pytest; Vite, React 19, TypeScript, Tailwind v4, Framer Motion, TanStack Query; Docker, GitHub Actions; Render (backend) + Cloudflare Pages/Vercel (frontend).

## Global Constraints

- **Free tier only.** Every hosted dependency must have a usable free tier. No paid-only services.
- **Both DOCX and PDF downloads must work on Linux/cloud.** No `docx2pdf` / MS Word / COM automation in any runtime path.
- **No secrets in code or git history.** All keys via env / user-supplied. `.env` stays gitignored.
- **BYO-key, multi-provider.** Users select provider + model and supply their own key; server-side keys are an optional fallback.
- **Single source of truth.** No duplicated modules. The Gradio app and root-level duplicate modules are removed.
- **Python:** 3.11+. **Node:** 20+. Pin dependencies (lockfiles committed).
- **Current Anthropic model:** `claude-opus-4-8` (verify exact ID + alternatives against the claude-api reference before writing provider code). Centralize all model IDs — never hardcode inline.
- **TDD where logic is non-trivial** (LLM layer, config, SSRF guard, file store, scorer math, PDF service). Mechanical migration need not be TDD but must keep the app runnable after each task.

---

## Target File Structure

```
ResumeForge/
├── README.md                       # NEW — product + run + deploy + architecture
├── docker-compose.yml              # NEW — backend + libreoffice for local prod-like run
├── .github/workflows/ci.yml        # NEW — lint + test + build, backend & frontend
├── docs/
│   ├── adr/                        # NEW — architecture decision records
│   │   ├── 0001-spa-fastapi-split.md
│   │   ├── 0002-multi-provider-llm.md
│   │   ├── 0003-libreoffice-pdf.md
│   │   └── 0004-ephemeral-file-store.md
│   └── superpowers/plans/2026-06-28-resumeforge-production-overhaul.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # app factory, middleware, router mounts, lifespan
│   │   ├── config.py               # pydantic-settings, validated at startup
│   │   ├── logging.py              # structlog JSON logging + request middleware
│   │   ├── store.py                # FileStore w/ TTL background cleanup
│   │   ├── security.py             # SSRF guard, upload validation
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Protocol + dataclasses + LLMError
│   │   │   ├── registry.py         # provider/model catalog (+ free flags)
│   │   │   ├── factory.py          # get_provider(...)
│   │   │   ├── anthropic_provider.py
│   │   │   ├── openai_provider.py
│   │   │   ├── gemini_provider.py
│   │   │   └── groq_provider.py
│   │   ├── services/               # migrated + hardened business logic
│   │   │   ├── jd_parser.py
│   │   │   ├── resume_parser.py
│   │   │   ├── github_parser.py
│   │   │   ├── project_matcher.py
│   │   │   ├── resume_builder.py
│   │   │   ├── cover_letter.py
│   │   │   ├── scorer.py
│   │   │   └── pdf.py              # LibreOffice headless conversion
│   │   └── routers/
│   │       ├── meta.py             # /health, /providers, /metrics
│   │       ├── analyse.py
│   │       ├── projects.py
│   │       ├── generate.py
│   │       ├── cover_letter.py
│   │       └── files.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_config.py
│   │   ├── test_security.py
│   │   ├── test_llm_factory.py
│   │   ├── test_store.py
│   │   ├── test_scorer.py
│   │   ├── test_pdf.py
│   │   └── test_api_smoke.py
│   ├── pyproject.toml              # deps + tooling (ruff, pytest, coverage)
│   ├── requirements.txt            # pinned, generated from pyproject
│   ├── Dockerfile                  # multi-stage, non-root, LibreOffice installed
│   └── .env.example
└── frontend/                       # REBUILT on Vite
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.ts / css
    ├── .env.example                # VITE_API_URL
    ├── Dockerfile                  # optional; static deploy is default
    └── src/
        ├── main.tsx, App.tsx
        ├── lib/api.ts, lib/types.ts, lib/sse.ts
        ├── design/                 # tokens, theme, primitives
        ├── components/             # presentational
        └── features/               # step-based feature components + store
```

---

# PHASE 0 — Repo Hygiene & Consolidation

Removes the second app and junk so there is one clear project. Low risk, high signal.

### Task 0.1: Remove junk and dead artifacts
**Files:**
- Delete: `nul`, `app_output.txt`, `frontend/nul`, `__pycache__/` (tracked or not)
- Modify: `.gitignore` (add `.venv/`, `*.egg-info/`, `dist/`, `build/`, `output/`, `*.pdf` in tmp, `.pytest_cache/`, `.ruff_cache/`, `frontend/dist/`)

- [ ] Delete the files above (`git rm` tracked ones; plain delete untracked).
- [ ] Expand `.gitignore`.
- [ ] Commit: `chore: remove build junk and expand gitignore`.

### Task 0.2: Remove the Gradio app and root duplicate modules
**Files:**
- Delete: `app.py`, and root-level `jd_parser.py`, `github_parser.py`, `resume_parser.py`, `resume_builder.py`, `scorer.py`, `cover_letter.py`, `project_matcher.py`, `requirements.txt` (root)
- Keep: everything under `backend/` (becomes the source of truth) and `frontend/` (rebuilt in Phase 5)

- [ ] Confirm `backend/` versions are the ones we keep (they are newer/diverged).
- [ ] `git rm` the root duplicates + `app.py` + root `requirements.txt`.
- [ ] Commit: `refactor: remove Gradio app and root duplicate modules (single source of truth)`.

### Task 0.3: Restructure backend into an `app/` package
**Files:**
- Create: `backend/app/__init__.py`, `backend/app/services/__init__.py`
- Move: `backend/{jd_parser,resume_parser,github_parser,project_matcher,resume_builder,cover_letter,scorer}.py` → `backend/app/services/`
- Move: `backend/api.py` → split later; for now move to `backend/app/_legacy_api.py` to keep imports working until routers exist
- Modify: imports in moved modules become relative within `app.services`

- [ ] `git mv` modules into `app/services/`.
- [ ] Fix imports (`from jd_parser import` → `from app.services.jd_parser import`).
- [ ] Run `python -c "import app.services.scorer"` from `backend/` to verify imports resolve.
- [ ] Commit: `refactor: move backend logic into app/ package`.

---

# PHASE 1 — Config, Logging, Security Foundation (TDD)

### Task 1.1: Typed settings with startup validation
**Files:**
- Create: `backend/app/config.py`, `backend/tests/test_config.py`, `backend/.env.example`

**Interfaces:**
- Produces: `Settings` (pydantic-settings `BaseSettings`); `get_settings() -> Settings` (lru_cached). Fields: `allowed_origins: list[str]`, `file_ttl_seconds: int = 1800`, `max_upload_mb: int = 10`, `request_timeout_s: int = 60`, `llm_max_retries: int = 2`, server-side optional keys `anthropic_api_key/openai_api_key/google_api_key/groq_api_key: str | None`, `github_token: str | None`, `log_level: str = "INFO"`, `environment: Literal["dev","prod"] = "dev"`.

- [ ] **Step 1: Failing test**
```python
# backend/tests/test_config.py
from app.config import get_settings
def test_defaults(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    get_settings.cache_clear()
    s = get_settings()
    assert s.file_ttl_seconds == 1800
    assert s.max_upload_mb == 10
    assert s.environment == "dev"
def test_origins_parsed_from_csv(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://a.com,http://b.com")
    get_settings.cache_clear()
    assert get_settings().allowed_origins == ["http://a.com", "http://b.com"]
```
- [ ] **Step 2:** Run `pytest tests/test_config.py -v` → FAIL (no module).
- [ ] **Step 3:** Implement `Settings` with a CSV validator for `allowed_origins` and `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`.
- [ ] **Step 4:** Run tests → PASS.
- [ ] **Step 5:** Write `.env.example` documenting every field.
- [ ] **Step 6:** Commit: `feat: typed settings with startup validation`.

### Task 1.2: Structured JSON logging + request middleware
**Files:**
- Create: `backend/app/logging.py`
- Test: assert a log line is valid JSON with `level`, `event`, `request_id`.

- [ ] Configure structlog → JSON renderer; `configure_logging(level)`.
- [ ] `RequestLoggingMiddleware` that assigns a `request_id`, times the request, logs method/path/status/duration_ms.
- [ ] Test JSON shape via `capsys`.
- [ ] Commit: `feat: structured JSON logging + request timing middleware`.

### Task 1.3: SSRF guard + upload validation (TDD)
**Files:**
- Create: `backend/app/security.py`, `backend/tests/test_security.py`

**Interfaces:**
- Produces: `assert_public_http_url(url: str) -> str` (raises `ValueError` for non-http(s), or hosts resolving to private/loopback/link-local/reserved ranges); `validate_upload(filename: str, size: int, max_mb: int) -> None` (raises `ValueError` for disallowed extension or oversize). Allowed upload extensions: `.pdf, .docx`.

- [ ] **Step 1: Failing tests**
```python
# backend/tests/test_security.py
import pytest
from app.security import assert_public_http_url, validate_upload
@pytest.mark.parametrize("bad", [
    "ftp://x", "file:///etc/passwd", "http://127.0.0.1/x",
    "http://localhost/x", "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/x", "http://192.168.1.1/x", "http://[::1]/x",
])
def test_blocks_ssrf(bad):
    with pytest.raises(ValueError):
        assert_public_http_url(bad)
def test_allows_public():
    assert assert_public_http_url("https://example.com/job/123").startswith("https://")
def test_upload_rejects_exe():
    with pytest.raises(ValueError):
        validate_upload("x.exe", 1000, 10)
def test_upload_rejects_oversize():
    with pytest.raises(ValueError):
        validate_upload("x.pdf", 20*1024*1024, 10)
def test_upload_ok():
    validate_upload("resume.pdf", 1000, 10)
```
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement using `socket.getaddrinfo` + `ipaddress.ip_address(...).is_private/is_loopback/is_link_local/is_reserved/is_multicast`. Resolve ALL returned addresses; reject if any is non-global.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `feat: SSRF guard and upload validation`.

### Task 1.4: Ephemeral file store with TTL cleanup (TDD)
**Files:**
- Create: `backend/app/store.py`, `backend/tests/test_store.py`

**Interfaces:**
- Produces: `FileStore(ttl_seconds, base_dir)` with `register(path) -> str` (uuid id), `get(id) -> Path | None` (None if missing/expired), `sweep() -> int` (deletes expired files + entries, returns count), `start_background_sweeper()/stop()`. Used as a singleton via `get_store()`.

- [ ] **Step 1:** Test register→get round trips; expired entry returns None and file removed; `sweep()` count correct (inject a `now` callable for determinism).
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement with a lock-guarded dict of `{id: (path, created_at)}`; sweeper via `asyncio` task started in lifespan.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit: `feat: TTL-based ephemeral file store`.

---

# PHASE 2 — Multi-Provider LLM Abstraction (TDD)

> Before writing provider code, consult the claude-api reference for current Anthropic model IDs/params, and verify current free-tier model IDs for Gemini (`gemini-*`), Groq (Llama models), and OpenAI.

### Task 2.1: LLM base contract
**Files:**
- Create: `backend/app/llm/__init__.py`, `backend/app/llm/base.py`, `backend/tests/test_llm_base.py`

**Interfaces:**
- Produces:
```python
@dataclass
class LLMResponse: text: str; model: str; provider: str; usage: dict | None = None
class LLMError(Exception):
    def __init__(self, message, *, provider, kind):  # kind in {"auth","rate_limit","timeout","bad_request","server","unknown"}
        ...
class LLMProvider(Protocol):
    name: str
    def complete(self, *, prompt: str, system: str | None = None,
                 max_tokens: int = 2000, temperature: float = 0.2,
                 model: str | None = None) -> LLMResponse: ...
```
- [ ] Define dataclasses/protocol + `LLMError`. Test that `LLMError` carries `provider`/`kind`.
- [ ] Commit: `feat: LLM provider contract`.

### Task 2.2: Provider registry (catalog)
**Files:**
- Create: `backend/app/llm/registry.py`, test `test_registry.py`

**Interfaces:**
- Produces: `PROVIDERS: dict[str, ProviderInfo]` where `ProviderInfo` has `label`, `env_key_name`, `models: list[ModelInfo]`, default model. `ModelInfo`: `id`, `label`, `free: bool`. `list_providers() -> list[dict]` for the `/providers` endpoint. Mark Gemini + Groq models `free=True`.
- [ ] Implement catalog (verify IDs first). Test that every provider has ≥1 model and a default.
- [ ] Commit: `feat: provider/model registry with free-tier flags`.

### Task 2.3: Factory + per-provider adapters
**Files:**
- Create: `backend/app/llm/factory.py`, `anthropic_provider.py`, `openai_provider.py`, `gemini_provider.py`, `groq_provider.py`, test `test_llm_factory.py`

**Interfaces:**
- Produces: `get_provider(provider: str, *, api_key: str | None, model: str | None) -> LLMProvider`. Resolves key from arg → settings env fallback; raises `LLMError(kind="auth")` if none. Each adapter maps SDK exceptions → `LLMError(kind=...)`, sets `timeout` and `max_retries` from settings.
- [ ] **Step 1:** Test factory routing + auth error with mocks (monkeypatch each SDK client). No real network in tests.
```python
def test_factory_unknown_provider():
    with pytest.raises(LLMError):
        get_provider("nope", api_key="x", model=None)
def test_factory_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMError):
        get_provider("anthropic", api_key=None, model=None)
```
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement factory + 4 adapters. Anthropic via `messages.create`; OpenAI via `chat.completions`; Gemini via `google-genai` `generate_content`; Groq via OpenAI-compatible `chat.completions`. Each returns `LLMResponse`.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit: `feat: multi-provider LLM factory (Anthropic/OpenAI/Gemini/Groq)`.

### Task 2.4: Migrate services to the LLM abstraction
**Files:**
- Modify: every file in `backend/app/services/` that currently calls `client.messages.create` / hardcodes `claude-opus-4-5`.

**Interfaces:**
- Consumes: services now take an `llm: LLMProvider` argument instead of `client: anthropic.Anthropic`. Replace `resp = client.messages.create(model="claude-opus-4-5", ...)` + manual text extraction with `llm.complete(prompt=..., system=..., max_tokens=...).text`.
- [ ] Replace call sites file-by-file; add typed error handling (`except LLMError`) that surfaces a useful message instead of silently swallowing. Remove the now-redundant text-block extraction loops.
- [ ] Fix the specific service bugs found in audit while here (only these, no scope creep):
  - `scorer.py`: delete dead `score_card_html` (unreachable block).
  - `jd_parser.py`: `lstrip("www.")` → `removeprefix("www.")`; wrap the JD extraction LLM call.
  - `cover_letter.py`: guard the two unguarded LLM calls; `p['name']` → `p.get('name','')`.
  - `project_matcher.py`: skip refs without `index` instead of defaulting to 0; stop padding bullets by duplication (pad with empty/skip); reduce `stars*2` weight (cap star contribution).
  - `resume_builder.py`/`cover_letter.py`: remove `docx2pdf` usage (replaced in Phase 3); `bare except:` → `except OSError:`.
- [ ] Run existing import smoke + any service unit tests.
- [ ] Commit per service: `refactor(<service>): use LLM abstraction + fix audit bugs`.

---

# PHASE 3 — LibreOffice PDF Rendering (TDD-ish)

### Task 3.1: PDF service via LibreOffice headless
**Files:**
- Create: `backend/app/services/pdf.py`, `backend/tests/test_pdf.py`

**Interfaces:**
- Produces: `docx_to_pdf(docx_path: str, out_dir: str | None = None) -> str` (returns pdf path; raises `RuntimeError` if soffice missing/fails); `soffice_available() -> bool`; `count_pdf_pages(pdf_path) -> int` (PyMuPDF).
- [ ] Implement using `subprocess.run(["soffice","--headless","--convert-to","pdf","--outdir",out,docx], timeout=120, check=True)` with a per-process user profile dir to avoid lock contention, args passed as a list (no shell, no `-c` interpolation).
- [ ] **Test:** `test_pdf.py` builds a tiny docx with python-docx, converts, asserts the pdf exists and `count_pdf_pages == 1`. Skip with `pytest.mark.skipif(not soffice_available())` so CI without LibreOffice still passes (CI image installs it).
- [ ] Commit: `feat: LibreOffice headless PDF rendering (Linux-safe)`.

### Task 3.2: Wire PDF service into resume_builder + cover_letter
**Files:**
- Modify: `resume_builder.py` (`_count_pages_pdf`, `build_resume`), `cover_letter.py` (`build_cover_letter_docx`)
- [ ] Replace all `docx2pdf` imports/calls with `app.services.pdf.docx_to_pdf` / `count_pdf_pages`. Remove the subprocess `-c` string and the `time.sleep(1.0)` COM band-aid.
- [ ] Remove `docx2pdf` from dependencies.
- [ ] Commit: `refactor: render PDFs via LibreOffice in builder + cover letter`.

---

# PHASE 4 — API Routers, App Factory, Observability

### Task 4.1: App factory + lifespan + meta router
**Files:**
- Create: `backend/app/main.py`, `backend/app/routers/__init__.py`, `backend/app/routers/meta.py`
- Modify: delete `backend/app/_legacy_api.py` after all routers exist

**Interfaces:**
- Produces: `create_app() -> FastAPI`; `app = create_app()`. Lifespan starts/stops the file-store sweeper, calls `configure_logging`, validates settings (fail loud). CORS from `settings.allowed_origins`. Mounts routers. `meta.py`: `GET /api/health`, `GET /api/providers` (from registry), `GET /api/metrics` (in-proc counters: request count, error count, p50/p95 latency, LLM call count).
- [ ] Implement; smoke test `GET /api/health` → 200 and `GET /api/providers` returns the 4 providers.
- [ ] Commit: `feat: app factory, lifespan, health/providers/metrics`.

### Task 4.2: Migrate the 6 functional endpoints into routers
**Files:**
- Create: `routers/analyse.py`, `projects.py`, `generate.py`, `cover_letter.py`, `files.py`
- [ ] Port each endpoint from `_legacy_api.py`, swapping: `_get_client` → `get_provider(provider, api_key, model)`; add `provider`/`model` form fields; apply `assert_public_http_url` in analyse (JD URL); apply `validate_upload` on the resume upload; use `get_store()` for file registration/serving; replace the polled `log_queue` SSE hack with a clean `asyncio.Queue`-based streamer helper in `app/sse.py`.
- [ ] Add a shared `app/sse.py` `stream(run_coroutine)` helper so the threaded-queue pattern lives in one place.
- [ ] Delete `_legacy_api.py`.
- [ ] Smoke test each route with mocked providers (`test_api_smoke.py`): analyse/generate return expected JSON keys; files 404 on unknown id.
- [ ] Commit per router: `feat(api): <route> router with provider selection + validation`.

---

# PHASE 5 — Frontend Rebuild (Vite + React + Design System)

> Use the frontend-design skill for visual direction. Goal: a distinctive, non-template UI that "pops" — intentional typography, motion, and color, not default shadcn-gray.

### Task 5.1: Scaffold Vite app, remove Next.js
**Files:**
- Delete: all Next.js-specific files (`next.config.ts`, `app/`, `eslint.config.mjs` Next preset, `.next/`)
- Create: `frontend/index.html`, `vite.config.ts`, `package.json` (Vite/React/TS/Tailwind v4/Framer Motion/TanStack Query), `tsconfig.json`, `.env.example` (`VITE_API_URL`), `src/main.tsx`, `src/App.tsx`
- [ ] Scaffold; `npm run build` succeeds; app renders a placeholder.
- [ ] Commit: `feat(frontend): scaffold Vite + React + Tailwind v4`.

### Task 5.2: Design system + primitives
**Files:**
- Create: `src/design/tokens.css` (color/space/type scales), `src/design/theme.ts`, `src/components/{Button,Card,Input,Textarea,Select,Badge,Spinner}.tsx`, motion presets in `src/design/motion.ts`
- [ ] Build the primitives with a cohesive custom aesthetic + Framer Motion presets. No `dangerouslySetInnerHTML`.
- [ ] Commit: `feat(frontend): design system + motion primitives`.

### Task 5.3: API client + typed SSE
**Files:**
- Create: `src/lib/types.ts`, `src/lib/api.ts`, `src/lib/sse.ts`
- [ ] Port `api.ts`/`types.ts` from old frontend; base URL strictly from `import.meta.env.VITE_API_URL`; add `provider`/`model` to request payloads; downloads use the same base (no localhost proxy). Add zod (or hand-written guards) to validate responses at runtime. Add `AbortController` wiring used by a real cancel button.
- [ ] Commit: `feat(frontend): typed API client + SSE + runtime validation`.

### Task 5.4: Provider/model selector + key entry
**Files:**
- Create: `src/features/ProviderPicker.tsx`
- [ ] Fetch `/api/providers`; show provider dropdown + model dropdown + masked key field; mark free providers with a "Free" badge; persist selection in memory only (not key).
- [ ] Commit: `feat(frontend): LLM provider + model selector`.

### Task 5.5: Step features + state
**Files:**
- Create: `src/features/{Analyse,Projects,Generate,Editor,CoverLetter}.tsx`, `src/features/store.ts` (Zustand or `useReducer` context — replaces the 30-`useState` god component), `src/components/{ProgressLog,ScoreCard,DownloadButtons,ErrorBoundary}.tsx`
- [ ] Rebuild the flow as focused components driven by a single store. Add an error boundary, loading/error states, a cancel button, and aria-labels on icon buttons.
- [ ] `npm run build` + manual smoke against local backend.
- [ ] Commit per feature: `feat(frontend): <step> feature`.

---

# PHASE 6 — Containerization, CI/CD, Docs, Deploy

### Task 6.1: Backend Dockerfile (multi-stage, non-root, LibreOffice)
**Files:**
- Create: `backend/Dockerfile`, `backend/.dockerignore`
- [ ] Base `python:3.11-slim`; `apt-get install --no-install-recommends libreoffice-writer fonts-dejavu`; create non-root user; install pinned deps; `CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]`. Verify `soffice` present in image.
- [ ] Build locally; run; hit `/api/health`.
- [ ] Commit: `feat: backend Dockerfile with LibreOffice, non-root`.

### Task 6.2: docker-compose for local prod-like run
**Files:**
- Create: `docker-compose.yml` (backend service; env from `.env`; healthcheck on `/api/health`)
- [ ] `docker compose up` → backend healthy.
- [ ] Commit: `feat: docker-compose for local prod-like run`.

### Task 6.3: CI pipeline
**Files:**
- Create: `.github/workflows/ci.yml`
- [ ] Jobs: **backend** (ruff lint, pytest + coverage; install LibreOffice for the PDF test), **frontend** (npm ci, tsc --noEmit, eslint, vite build). Trigger on PR + push. Upload coverage as artifact.
- [ ] Commit: `ci: lint + test + build for backend and frontend`.

### Task 6.4: README + ADRs + OpenAPI note
**Files:**
- Create: root `README.md`, `docs/adr/0001..0004`
- [ ] README: what it does (with screenshot/gif placeholder), architecture diagram, local run (docker + manual), env vars, deploy steps (Render + Cloudflare/Vercel), provider/free-tier notes, link to `/docs` OpenAPI. ADRs document the 4 key decisions (SPA+FastAPI split, multi-provider abstraction, LibreOffice PDF, ephemeral TTL store).
- [ ] Commit: `docs: README + architecture decision records`.

### Task 6.5: Deploy (free tier)
**Files:**
- Create: `render.yaml` (backend, Docker env), frontend deploy config (Cloudflare Pages / Vercel)
- [ ] Backend → Render (Docker) with env vars + health check path `/api/health`; note free-tier cold-start. Frontend → Cloudflare Pages/Vercel with `VITE_API_URL` pointing at the Render URL. Update backend `ALLOWED_ORIGINS` to the deployed frontend origin.
- [ ] Verify end-to-end on the live URLs (analyse → generate → download DOCX **and** PDF).
- [ ] Commit: `chore: deployment config (Render + static frontend)`.

---

# PHASE 7 — Optional Stretch (RAG/Retrieval signal)

### Task 7.1: Embedding-based project↔JD semantic matching
- [ ] Add an embeddings step (free provider, e.g. Gemini embeddings) to pre-rank GitHub projects against the JD by cosine similarity before the LLM re-ranks — gives a genuine retrieval/grounding story. Document as ADR 0005. Gate behind a flag; only if Phases 0–6 are solid.

---

## Self-Review Notes
- **Spec coverage:** every audit Critical (C1 docx2pdf→Phase 3; C2 SSRF→1.3; C3 unguarded LLM→2.4; C4 frontend localhost→5.3; C5 file store→1.4; C6 tests/CI/Docker→Phases 1-6; C7 XSS→5.2) and Important item maps to a task. ✅
- **Provider IDs** must be verified against live references before Phase 2 (flagged in Global Constraints + Phase 2 header).
- **Runnable-after-each-task** maintained by keeping `_legacy_api.py` until routers exist (Phase 4).
```
