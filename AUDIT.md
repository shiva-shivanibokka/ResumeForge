# Repo Audit Report — ResumeForge

**Date:** 2026-06-29
**Stack detected:** Python 3.11 / FastAPI (backend) · TypeScript / React 19 / Vite / Zustand (frontend) · Docker · LibreOffice PDF microservice
**Scope:** `backend/app/**`, `frontend/src/**`, `pdf-service/`, Docker/compose/render config. Excluded: generated `dist/`, `node_modules`, `__pycache__`, `docs/`.

## Summary

- Total findings: 25
- Auto-fixed (trivial-safe): 6
- Needs review (see `PLAN.md`): 19
- Critical: 4 | Major: 8 | Minor: 7 | Notes: 6

## Production-readiness scorecard

Status columns: **Found** = at audit time · **After** = after the fixes in `PLAN.md` were applied (2026-06-29).

| Category | Found | After | Notes |
|---|---|---|---|
| Correctness | ❌ | ✅ | Floor bug fixed (header ≤ body); analyse() resets downstream state |
| Silent failures | ❌ | ✅ | Cover-letter build failure now raises; GitHub auth/rate-limit surfaced distinctly with logging |
| Security | ❌ | ⚠️ | SSRF redirect re-validated; rate limiter added; CORS credentials off. Remaining: key rotation (operational, done by user) |
| Concurrency | ❌ | ✅ | Blocking handlers moved off the loop (sync `def` / `run_in_threadpool`); SSE queue bounded |
| Performance | ❌ | ✅ | GitHub fan-out capped at 30; DB connection pool added; upload streamed with early size cap |
| Architecture | ⚠️ | ⚠️ | Notes only (unchanged by design): process-local file store, mixed db/rag access, one god-closure |
| Production-readiness | ❌ | ✅ | GitHub module logs failures; rate-limit/auth distinguishable in logs |
| Test coverage | ⚠️ | ✅ | 65 tests pass; added regression tests for floor bug, rate limiter, SSRF redirect |

(✅ none · ⚠️ minor/notes only · ❌ ≥1 major/critical)

## Auto-fixed (trivial-safe)

1. **`backend/app/services/resume_builder.py`** — deleted dead `_count_pages_pdf()` + its `_count_pages` alias (zero call sites; live code uses `pdf.count_pdf_pages`). The alias comment falsely claimed "used by external code."
2. **`backend/app/services/resume_builder.py`** (`_fits_fast` docstring) — corrected the documented page threshold from `0.95` to the actual `0.92`, and noted the real-PDF verify loop backstops it.
3. **`frontend/src/components/ui.tsx`** — removed unused `Eyebrow` export (SectionTitle inlines its own eyebrow).
4. **`frontend/src/components/ui.tsx`** — removed unused `Badge` export (no render sites since the provider picker stopped using it).
5. **`frontend/src/lib/types.ts`** — removed dead `gap_markdown` field, the unused `FetchProjectsDone` interface, and the write-only `scores_md` field.
6. **`frontend/src/store.ts`** — removed the write-only `scoresMd` state field + its two assignments, plus the dead `export type { KeywordItem, Project }` re-export and the now-unused `KeywordItem` import.

Verified after fixes: `pytest` 60 pass, `ruff` clean, `tsc`+`vite build` clean.

## Findings requiring review

Severity-ordered; full task detail (proposed code + verification) in `PLAN.md` (task numbers referenced).

### Security (pass 8)
- **`backend/.env:1-2` · Critical · PLAN Task 1** — Live `ANTHROPIC_API_KEY` and a GitHub PAT sit in the working tree (gitignored, not in git history, but exposed on disk). *Production:* any folder share/backup/`git add -f` leaks the owner's paid billing + GitHub scope. **Rotate both keys now**; this is an operational action, not a code change.
- **`backend/app/services/jd_parser.py:128` (guard at `analyse.py:34`) · Critical · PLAN Task 4** — SSRF: `assert_public_http_url` validates the original host once, then `requests.get` follows redirects (`allow_redirects=True` default). A public URL that 302-redirects to `169.254.169.254` / internal hosts bypasses the guard; DNS rebinding does too. *Production:* cloud metadata / internal-service exfiltration from the server.
- **`backend/app/main.py:82-90` + `llm/factory.py:15-26` · Major · PLAN Task 6** — No rate limiting on `/api/generate|fetch-projects|analyse|cover-letter`, and the LLM factory falls back to the **server** key when none is supplied. *Production:* an anonymous visitor drains the owner's Anthropic/OpenAI/GitHub quota (cost-DoS).
- **`backend/app/config.py:35-37` · Minor · PLAN Task 13** — CORS `allowed_origin_regex` trusts every `*.vercel.app` with `allow_credentials=True`. App uses no cookies, so credentials should be off and the origin tightened to the real domain.

### Concurrency / async (pass 9)
- **`analyse.py:18`, `generate.py:217` (edit_resume), `cover_letter.py:33,70`, `projects.py:28` (projects_cache) · Critical · PLAN Tasks 2-3** — These `async def` handlers call blocking LLM / PDF-subprocess / `psycopg` / `requests` work directly on the event loop. On the single-worker free tier, one request freezes the whole server (health check included) for seconds–minutes. SSE endpoints already do this correctly via `stream_work` (threaded) — the fix is to mirror that (make handlers `def`, or `run_in_threadpool`).
- **`generate.py:277` (rebuild_resume) · Major · PLAN Task 3** — same blocking issue: `build_resume` runs a DOCX render + PDF conversion (≤120s) on the loop.
- **`sse.py:45,60` · Minor · PLAN Task 14** — the SSE worker thread isn't cancellable (client disconnect still runs the full GitHub crawl / LLM spend) and the progress queue is unbounded.

### Correctness (pass 1/3)
- **`resume_builder.py:_fit_entry_size` (floor `8.5`) · Major · PLAN Task 5** — On dense resumes the auto-fit body drops below 8.5pt (search floor 7.0, verify floor 6.5), but this helper returns `max(8.5, …)`, so entry headers render *larger* than body text — inflating height and defeating the one-page guarantee the verify loop exists to enforce.
- **`frontend/src/store.ts:analyse()` (179-211) · Major · PLAN Task 7** — re-running analyse for a new job doesn't reset `ranked/selectedProjects/matchedPayload/resume/scores/beforeScores/letterText/cover/generateLog`, and keeps `reached.forge/letter`. *User:* paste Job B → Forge/Temper still show Job A's resume/scores/cover, and a forge runs against Job A's stale project selections — silent cross-job data mixing.

### Silent failures (pass 2)
- **`cover_letter.py` router (64-67, 89-92) · Major · PLAN Task 8** — `build_cover_letter_docx` swallows all build errors into `result["error"]`; the router never checks it, returning HTTP 200 with `docx_id/pdf_id = null` and no message (generate.py does check). *User:* download buttons silently do nothing; root cause discarded.
- **`github_parser.py:35-43,253` · Major · PLAN Task 10** — `_get` and `summarize_repo_with_claude` swallow every exception with zero logging; a 401 (bad token) or rate-limit is indistinguishable from "user has no repos." *Production:* unfixable-from-logs; users misdirected.

### Performance (pass 10)
- **`github_parser.py` (via `projects.py:59` `max_repos=100`) · Major · PLAN Task 11** — N+1 fan-out: per repo ~3–16 GitHub calls + 1 LLM call. 100 repos ⇒ hundreds–1600 GitHub calls + 100 LLM calls per `/fetch-projects`. Exhausts GitHub limits instantly; large LLM cost/latency.
- **`db.py:48-56` · Major · PLAN Task 12** — no connection pool; every `cache_status/cached_model/replace_user_projects/rank_by_vector` opens a fresh `psycopg.connect` (3–4 per fetch). Not a leak (closed in `finally`), but slow + exhausts Neon connection caps under concurrency.
- **`deps.py:39-43` · Major · PLAN Task 9** — upload is fully `await file.read()` into RAM *before* the 10MB check; concurrent oversized uploads can OOM the 512MB instance before the guard fires.

### Missing validation / consistency (pass 5/7)
- **`analyse.py:70,74` + `scorer.py:114,122` · Minor · PLAN Task 15** — `item["keyword"]` hard-subscripts LLM output (siblings use `.get`). A malformed item ⇒ `KeyError` ⇒ 500 instead of graceful degrade.
- **`resume_parser.py:43,107,272` · Minor · PLAN Task 16** — extraction failures are signaled by a string starting with `"["` and detected via `startswith("[")`; a résumé whose text legitimately starts with `[` is misclassified as failed.
- **`projects.py:88` · Note · PLAN Task 17** — cache-hit path returns `all_projects: []` while crawl/LLM paths return the full list (currently unused by the UI; latent).
- **`frontend/src/store.ts:reformatResume` · Note · PLAN Task 18** — ignores the now-returned `matched_payload` (insertKeywords captures it). Harmless today; inconsistent contract.
- **`frontend/src/features/Projects.tsx:35-49` · Minor · PLAN Task 19** — combined required+preferred keyword chips keyed by `k.keyword`; an LLM emitting the same string in both lists yields duplicate React keys (toggle glitch).

### Observability (pass 12)
- **`main.py:29-52` · Minor** — `RequestObservabilityMiddleware` logs `duration_ms` at `call_next` return, which for SSE `StreamingResponse` is time-to-first-byte, not the 30–120s work duration — the expensive endpoints' latency is under-reported. (Folded into PLAN Task 14.)

## Architecture notes (pass 11 — not bugs, no action required)

- **`store.py` `FileStore`** — process-local in-memory dict + temp files + TTL sweeper. Correct for single-worker; a hard ceiling if you ever scale to multiple workers/instances (download IDs and the sweeper are per-process). Documented tradeoff.
- **`projects.py`** calls `app.db` directly while other DB access goes through `services/rag.py` — mixed layering.
- **`generate.py` `work()`** is a ~65-line closure doing matching + skill merge + build + before/after scoring; harder to unit-test in isolation.

## Clean areas (no findings)

`routers/files.py`, `routers/meta.py`, `routers/generate.py` (logic), `services/pdf.py` (list-arg subprocess, no shell injection), `services/project_matcher.py`, `services/rag.py`, `services/scorer.py` (except the keyword subscript), `sse.py` core design, `store.py` TTL logic, `deps.py` (except upload buffering), `embeddings.py`, `db.py` (graceful-degrade excepts are intentional; signatures match callers). Frontend: `App.tsx`, `main.tsx`, `lib/api.ts`, `lib/providers.ts`, `ErrorBoundary.tsx`, `ProviderPicker.tsx`, `ScoreGauge.tsx`, `DownloadBar.tsx`, `ProgressLog.tsx`, `Stepper.tsx`, `Materials.tsx`, `CoverLetter.tsx`. Docker: non-root users, healthchecks present, `.env` gitignored with clean history, no hardcoded secrets in source.
