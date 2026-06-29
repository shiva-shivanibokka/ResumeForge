# Fix Plan — ResumeForge

Generated from repo-bug-audit on 2026-06-29. 19 tasks, ordered by severity (Critical first).

> **STATUS — all tasks applied 2026-06-29.** Tasks 2–19 were implemented and
> verified (65 tests pass, ruff + tsc clean). **Task 1 is operational** (key
> rotation) — the user removed `backend/.env`; the keys were inactive and never in
> git history, so no scrub is needed. Task 14 was applied as a bounded SSE queue;
> true mid-LLM cancellation is left as a documented limitation (needs `work()`
> cooperation). The 6 trivial-safe items were auto-fixed earlier (see `AUDIT.md`).

---

## Task 1: Rotate the live secrets exposed in `backend/.env`

- **File:** `backend/.env` (operational — not committed; gitignored, not in history)
- **Category:** Security (pass 8)
- **Severity:** Critical
- **Finding:** A working `ANTHROPIC_API_KEY` (`sk-ant-…`) and a GitHub PAT (`github_pat_…`) are stored in plaintext in the working tree.
- **Why it matters:** Disk backup, folder share, or an accidental `git add -f` leaks paid Anthropic billing and GitHub account scope.
- **Proposed change:** Revoke + reissue both keys (Anthropic console; GitHub → Settings → Developer settings → PATs). Update local `.env` and the HF Space secrets with the new values. Confirm `.env` stays in `.gitignore`.
- **Verification:** `git check-ignore backend/.env` prints the path; `git log -p -- backend/.env` is empty.
- **Depends on:** none.

---

## Task 2: Stop blocking the event loop in `analyse`, `edit_resume`, `cover_letter` handlers

- **File:** `backend/app/routers/analyse.py:18`, `backend/app/routers/generate.py:217`, `backend/app/routers/cover_letter.py:33,70`
- **Category:** Concurrency / async (pass 9)
- **Severity:** Critical
- **Finding:** These `async def` handlers call blocking work (LLM `.complete`, `requests.get`, `build_resume`'s subprocess/HTTP PDF, `psycopg`) directly on the loop.
- **Why it matters:** Single-worker free tier → one in-flight request freezes every other request and `/api/health` for the whole call (seconds to minutes), so the keep-alive cron can mark the service down.
- **Proposed change:** Simplest correct fix — drop `async` so FastAPI runs each in its threadpool. Each handler does only blocking I/O, so this is safe and mechanical:
  ```python
  # analyse.py
  @router.post("/analyse")
  def analyse(  # was: async def
      ...
  ):
      ...

  # generate.py
  @router.post("/edit-resume")
  def edit_resume(  # was: async def
      ...

  # cover_letter.py
  @router.post("/cover-letter")
  def generate_cover_letter(  # was: async def
      ...
  @router.post("/edit-cover-letter")
  def edit_cover_letter(  # was: async def
      ...
  ```
  (Alternative if you keep `async`: wrap each blocking call in `from fastapi.concurrency import run_in_threadpool`.) Verify none of these handlers `await` anything — they don't today.
- **Verification:** `pytest backend/tests/test_api_smoke.py -q`; manual: hit `/api/analyse` with a slow JD while polling `/api/health` — health stays responsive.
- **Depends on:** none.

---

## Task 3: Stop blocking the event loop in `rebuild_resume` and `projects_cache`

- **File:** `backend/app/routers/generate.py:277` (`rebuild_resume`), `backend/app/routers/projects.py:28` (`projects_cache`)
- **Category:** Concurrency / async (pass 9)
- **Severity:** Major
- **Finding:** `rebuild_resume` runs `build_resume` (DOCX + PDF conversion, ≤120s) on the loop; `projects_cache` opens a sync `psycopg` connection on the loop (called on a UI poll, and Neon cold-starts).
- **Why it matters:** A cold PDF service or cold DB stalls the entire worker on what should be a cheap/background path.
- **Proposed change:** Convert both to `def` (threadpool), same as Task 2:
  ```python
  @router.post("/rebuild-resume")
  def rebuild_resume(...):   # was async def

  @router.get("/projects/cache")
  def projects_cache(github_url: str = Query("")):  # was async def
  ```
- **Verification:** `pytest -q`; poll `/api/projects/cache` repeatedly while a generate runs — server stays responsive.
- **Depends on:** none (independent of Task 2 but same pattern).

---

## Task 4: Close the SSRF redirect/rebind bypass in JD fetching

- **File:** `backend/app/services/jd_parser.py:128` (and the guard `backend/app/security.py`)
- **Category:** Security (pass 8)
- **Severity:** Critical
- **Finding:** `assert_public_http_url(url)` validates the submitted host once, then `requests.get(url, timeout=…)` follows redirects by default, so a public URL can 302 to `http://169.254.169.254/…` or an internal host. DNS rebinding similarly defeats the one-time check.
- **Why it matters:** Server-side fetch of internal/metadata endpoints (credential theft on cloud hosts).
- **Proposed change:** Disable auto-redirect and re-validate each hop; cap hops.
  ```python
  # jd_parser.py — replace the single requests.get
  resp = requests.get(url, timeout=15, allow_redirects=False,
                      headers={"User-Agent": "ResumeForge/1.0"})
  hops = 0
  while resp.is_redirect or resp.is_permanent_redirect:
      hops += 1
      if hops > 4:
          raise ValueError("Too many redirects")
      nxt = requests.compat.urljoin(url, resp.headers["Location"])
      assert_public_http_url(nxt)        # re-run guard on the new target
      url = nxt
      resp = requests.get(url, timeout=15, allow_redirects=False,
                          headers={"User-Agent": "ResumeForge/1.0"})
  resp.raise_for_status()
  ```
  Confirm `assert_public_http_url` resolves the hostname and rejects private/loopback/link-local/reserved IPs (and consider pinning the resolved IP for the actual GET to fully close rebinding).
- **Verification:** Add `backend/tests/test_security.py` cases: a URL whose `Location` points to `http://169.254.169.254/` raises; a normal 2-hop public redirect succeeds. `pytest backend/tests/test_security.py -q`.
- **Depends on:** none.

---

## Task 5: Fix `_fit_entry_size` floor so headers never exceed body size

- **File:** `backend/app/services/resume_builder.py` (`_fit_entry_size`, ~line 155; callers 364, 464)
- **Category:** Correctness (pass 1) — regression in the auto-fit path
- **Severity:** Major
- **Finding:** The helper returns `max(floor=8.5, shrunk)`. When auto-fit/verify drives `bs` below 8.5 (down to 7.0/6.5 on dense resumes), entry headers come back at 8.5 — *larger* than body.
- **Why it matters:** On exactly the dense resumes the one-page machinery targets, headers render bigger than body text, adding height the verify loop (which only shrinks `body`) can't recover.
- **Proposed change:** Cap the floor at the current body size, and never enlarge:
  ```python
  def _fit_entry_size(left: str, right: str, bs: float, floor: float = 8.5) -> float:
      floor = min(floor, bs)          # never exceed the body size
      chars = len(left or "") + len(right or "")
      if chars == 0:
          return bs
      factor, gap = 0.7, 12
      need = chars * factor * bs + gap
      if need <= _RIGHT_TAB_PT:
          return bs
      return max(floor, round((_RIGHT_TAB_PT - gap) / (chars * factor), 1))
  ```
- **Verification:** add a test asserting `_fit_entry_size("verylongname"*4, "May 2011 - May 2016", 7.0) <= 7.0`; rebuild the dense sample resume and confirm header size ≤ body in the PDF. `pytest backend/tests/test_skills.py -q` (add the assertion there or a new test module).
- **Depends on:** none.

---

## Task 6: Rate-limit expensive endpoints / gate the server-key fallback

- **File:** `backend/app/main.py:82-90`, `backend/app/llm/factory.py:15-26`
- **Category:** Security (pass 8)
- **Severity:** Major
- **Finding:** No limiter on `/generate|fetch-projects|analyse|cover-letter`; the LLM factory uses the server key when the caller supplies none, so anonymous users spend the owner's quota.
- **Why it matters:** Trivial cost-DoS / quota exhaustion.
- **Proposed change:** Add `slowapi` (or a small in-process token-bucket keyed by client IP) and apply to the four routes; **and/or** require a user key for those routes (return 400 "bring your own key" when the server fallback would be used on a public endpoint). Minimal limiter:
  ```python
  # requirements.txt: slowapi
  from slowapi import Limiter
  from slowapi.util import get_remote_address
  limiter = Limiter(key_func=get_remote_address, default_limits=["20/hour"])
  app.state.limiter = limiter
  # decorate the four POST handlers with @limiter.limit("10/hour")
  ```
- **Verification:** integration test issuing 11 rapid `/api/analyse` calls gets a 429 on the 11th.
- **Depends on:** Task 2/3 (limiter decorators interact with handler signatures — apply after the async→def change).

---

## Task 7: Reset downstream state when `analyse()` re-runs

- **File:** `frontend/src/store.ts` (`analyse`, ~179-211)
- **Category:** Cross-action state consistency
- **Severity:** Major
- **Finding:** Re-running analyse leaves `ranked/selectedProjects/matchedPayload/resume/scores/beforeScores/letterText/cover/generateLog` and `reached.forge/letter` from the previous job.
- **Why it matters:** Analyse Job B → Forge/Temper still show Job A's resume/scores/cover and forge against Job A's stale project picks.
- **Proposed change:** On a successful analyse, clear forward state:
  ```ts
  set({
    analysis: data,
    selectedKeywords: [],
    // reset everything downstream so Job B never shows Job A's results
    ranked: [],
    selectedProjects: [],
    matchedPayload: null,
    resume: { docxId: null, pdfId: null, docxName: null, pdfName: null },
    scores: null,
    beforeScores: null,
    letterText: "",
    cover: { docxId: null, pdfId: null, docxName: null, pdfName: null },
    generateLog: [],
    reached: { materials: true, projects: true, forge: false, letter: false },
    step: "projects",
  });
  ```
  (Match the exact field names/initial shapes in the store.)
- **Verification:** manual — run a full forge for Job A, return to Materials, analyse Job B → Forge/Temper steps are locked again and show no Job A data. Add a store unit test if a test harness is set up.
- **Depends on:** none.

---

## Task 8: Surface cover-letter build failures instead of returning 200 with no file

- **File:** `backend/app/routers/cover_letter.py` (~64-67, 89-92)
- **Category:** Silent failure (pass 2)
- **Severity:** Major
- **Finding:** Router never checks `cl_result.get("error")` / missing `docx_path`; mirrors generate.py which does.
- **Why it matters:** User gets `letter_text` but null file ids and dead download buttons, with the real error discarded.
- **Proposed change:** After the build call in both handlers:
  ```python
  if cl_result.get("error"):
      progress(f"Note: {cl_result['error']}")  # for the SSE path
  if not cl_result.get("docx_path"):
      raise RuntimeError("Cover letter build failed.")
  ```
  (Use the same shape generate.py:180-186 uses; for the non-SSE handler raise `HTTPException(500, …)`.)
- **Verification:** unit test that monkeypatches `build_cover_letter_docx` to return `{"error": "...", "docx_path": None}` and asserts the endpoint raises / streams an error event rather than 200-with-nulls.
- **Depends on:** none.

---

## Task 9: Enforce the upload size limit before buffering the whole file

- **File:** `backend/app/deps.py:39-43`
- **Category:** Performance / memory (pass 10)
- **Severity:** Major
- **Finding:** `await file.read()` loads the entire upload into RAM, then checks the 10MB cap.
- **Why it matters:** Concurrent oversized uploads OOM the 512MB instance before the guard fires.
- **Proposed change:** Reject early via `Content-Length`, and/or read in bounded chunks:
  ```python
  MAX = 10 * 1024 * 1024
  cl = request.headers.get("content-length")
  if cl and int(cl) > MAX:
      raise HTTPException(413, "File too large (max 10MB).")
  data = bytearray()
  while chunk := await file.read(1024 * 1024):
      data.extend(chunk)
      if len(data) > MAX:
          raise HTTPException(413, "File too large (max 10MB).")
  ```
- **Verification:** test posting a >10MB file returns 413 without OOM; a normal file still parses. `pytest backend/tests -q`.
- **Depends on:** none.

---

## Task 10: Add logging + distinguish auth/rate-limit from "no repos" in GitHub parsing

- **File:** `backend/app/services/github_parser.py:35-43` (`_get`), `:253` (`summarize_repo_with_claude`)
- **Category:** Production-readiness / silent failure (pass 12)
- **Severity:** Major
- **Finding:** All exceptions/non-200 swallowed to `None`, no structured logging; a 401/403/rate-limit looks identical to an empty user.
- **Why it matters:** Undiagnosable in production; users told "no repos" when the token is bad.
- **Proposed change:** Have `_get` log the status and raise a typed signal on 401/403/429 so `parse_github_profile` can report "GitHub auth/rate-limit error" vs "no repos":
  ```python
  log = get_logger("github")
  def _get(url, token=None):
      try:
          r = requests.get(url, headers=_headers(token), timeout=15)
      except requests.RequestException as e:
          log.warning("github_get_failed", url=url, error=str(e)); return None
      if r.status_code in (401, 403, 429):
          log.warning("github_auth_or_rate_limit", url=url, status=r.status_code)
          raise GitHubAccessError(r.status_code)   # new lightweight exception
      if r.status_code != 200:
          log.info("github_non_200", url=url, status=r.status_code); return None
      return r.json()
  ```
  Catch `GitHubAccessError` in `parse_github_profile` and set a specific error message.
- **Verification:** unit test with a mocked 401 asserts the error message mentions auth/token, not "no repos."
- **Depends on:** none.

---

## Task 11: Cap GitHub fan-out (N+1) per `/fetch-projects`

- **File:** `backend/app/services/github_parser.py` (`gather_repo_context`), `backend/app/routers/projects.py:59` (`max_repos=100`)
- **Category:** Performance (pass 10)
- **Severity:** Major
- **Finding:** Up to ~3–16 GitHub calls + 1 LLM call per repo × 100 repos.
- **Why it matters:** Exhausts GitHub limits (60/hr unauthenticated) instantly; large LLM cost/latency; this is the path most likely to fail in a live demo.
- **Proposed change:** Lower `max_repos` to a sensible default (e.g., 30), pre-sort repos by stars/recency and only deep-crawl the top N, and reduce per-repo probe calls (single tree fetch instead of sequential filename probes where possible). Make the cap configurable via `Settings`.
- **Verification:** instrument a counter of GitHub calls in a test/staging run; confirm a 30-repo profile stays well under the rate limit. Manual: `/fetch-projects` completes for a large account without a 403.
- **Depends on:** Task 10 (so a rate-limit hit during crawl is now visible).

---

## Task 12: Use a connection pool for Postgres

- **File:** `backend/app/db.py:48-56` (`_conn`)
- **Category:** Performance (pass 10)
- **Severity:** Major
- **Finding:** Every DB op opens/closes a fresh `psycopg.connect`; 3–4 per `/fetch-projects`.
- **Why it matters:** Per-call connect against Neon (connection-capped, cold-starting) is slow and exhausts the pool under concurrency.
- **Proposed change:** Introduce `psycopg_pool.ConnectionPool` created lazily at first use (or in lifespan), and have `_conn()` borrow/return from it:
  ```python
  # requirements.txt: psycopg_pool
  from psycopg_pool import ConnectionPool
  _pool: ConnectionPool | None = None
  def _get_pool():
      global _pool
      if _pool is None:
          _pool = ConnectionPool(get_settings().database_url, min_size=0, max_size=4,
                                 kwargs={"autocommit": True})
      return _pool
  @contextmanager
  def _conn():
      with _get_pool().connection() as conn:
          yield conn
  ```
  Keep the inert behavior when `DATABASE_URL` is unset.
- **Verification:** `pytest backend/tests/test_rag.py -q` (DB-disabled path still passes); manual concurrency check against Neon shows reused connections.
- **Depends on:** none.

---

## Task 13: Tighten CORS

- **File:** `backend/app/config.py:35-37`, `backend/app/main.py:82-89`
- **Category:** Security (pass 8)
- **Severity:** Minor
- **Finding:** `allowed_origin_regex` trusts all `*.vercel.app` with `allow_credentials=True`; app uses no cookies.
- **Proposed change:** Set `allow_credentials=False`, and prefer an explicit `ALLOWED_ORIGINS` list (the exact Vercel domain) over the broad regex in production; keep the regex only for preview deploys behind an env flag.
- **Verification:** preflight from the real domain succeeds; from a random `*.vercel.app` it isn't granted credentialed access.
- **Depends on:** none.

---

## Task 14: Make the SSE worker cancellable + fix SSE latency metric

- **File:** `backend/app/sse.py:45,60`, `backend/app/main.py:29-52`
- **Category:** Concurrency + observability (pass 9/12)
- **Severity:** Minor
- **Finding:** The worker thread runs to completion even after client disconnect (wasted LLM/GitHub spend); the progress queue is unbounded; and `duration_ms` for SSE measures time-to-first-byte.
- **Proposed change:** Pass a `threading.Event` cancel flag the `work()` progress callback checks at each step and abort early when `await request.is_disconnected()`; bound the queue (`maxsize`); and log the real duration from inside `stream_work` when the generator finishes rather than in the middleware.
- **Verification:** disconnect a client mid-generate and confirm (via logs) the worker stops early; check the logged duration matches wall-clock for a generate.
- **Depends on:** none.

---

## Task 15: Guard against missing `keyword` key in gap items

- **File:** `backend/app/routers/analyse.py:70,74`, `backend/app/services/scorer.py:114,122`
- **Category:** Missing validation (pass 5)
- **Severity:** Minor
- **Finding:** `item["keyword"]` hard-subscripts LLM output.
- **Proposed change:** Use `.get("keyword")` and skip items without it:
  ```python
  for item in gap.get("required_missing", []):
      kw = item.get("keyword")
      if not kw:
          continue
      ...
  ```
- **Verification:** unit test passing a gap dict with one `{"explanation": "x"}` (no keyword) returns gracefully (no `KeyError`).
- **Depends on:** none.

---

## Task 16: Replace string-sentinel extraction-error signaling

- **File:** `backend/app/services/resume_parser.py:43,107,272`
- **Category:** Missing/edge-case (pass 5)
- **Severity:** Minor
- **Finding:** Failure is a string starting with `"["`, detected via `startswith("[")`; a résumé whose text starts with `[` is misread as failed.
- **Proposed change:** Return a structured result (e.g., a `(text, error)` tuple or a small dataclass) and check `error is not None` instead of string-sniffing.
- **Verification:** test that a résumé text beginning with `[` parses successfully; a genuine failure is still detected.
- **Depends on:** none (touches callers of `parse_resume`).

---

## Task 17: Make cache-hit return `all_projects` consistently (or drop the field)

- **File:** `backend/app/routers/projects.py:88`
- **Category:** Consistency (pass 7)
- **Severity:** Note
- **Finding:** Cache-hit path returns `all_projects: []` while crawl/LLM paths return the full list.
- **Proposed change:** Either populate `all_projects` from the cache on a hit, or drop the field from the response (frontend no longer types it after the trivial-safe cleanup). Dropping is simplest since nothing consumes it.
- **Verification:** `pytest -q`; confirm no frontend reference to `all_projects` remains.
- **Depends on:** none.

---

## Task 18: Capture `matched_payload` in `reformatResume`

- **File:** `frontend/src/store.ts` (`reformatResume`)
- **Category:** Contract consistency
- **Severity:** Note
- **Finding:** `/api/rebuild-resume` now returns `matched_payload`, but reformat reads only file ids (insertKeywords captures it).
- **Proposed change:** `set({ matchedPayload: d.matched_payload ?? get().matchedPayload, resume: {…} })`.
- **Verification:** `tsc`/build clean; manual reformat then AI-edit uses the latest payload.
- **Depends on:** none.

---

## Task 19: De-duplicate combined keyword keys in Projects

- **File:** `frontend/src/features/Projects.tsx:35-49`
- **Category:** React keys (pass 1)
- **Severity:** Minor
- **Finding:** required+preferred chips keyed by `k.keyword`; an LLM emitting the same string in both lists duplicates keys.
- **Proposed change:** De-dupe before render (e.g. `const keywords = [...new Map([...required, ...preferred].map(k => [k.keyword, k])).values()]`) or key by `` `${list}-${k.keyword}` ``.
- **Verification:** build clean; toggling a keyword that appears in both lists behaves correctly.
- **Depends on:** none.
