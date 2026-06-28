# ADR 0001 — Single-page app + FastAPI, not Next.js

**Status:** Accepted (2026-06-28)

## Context

The project started with two parallel implementations: a Gradio monolith and a
Next.js (App Router) frontend over a FastAPI backend. ResumeForge is an
interactive, authenticated-by-key tool: every screen is dynamic, there is no
public content to index, and SEO/SSR provide no value. Maintaining two apps —
and the duplicated, already-diverged service modules behind them — was pure
overhead.

## Decision

Keep **one** architecture: a **FastAPI** backend exposing REST + SSE, and a
**Vite + React single-page app** as a pure client. Delete the Gradio app and the
duplicated root modules; consolidate all backend logic into one `app/` package.

## Consequences

- **Simpler mental model and deploy:** a static SPA (any CDN) + one container API.
  No SSR server to run, no hydration concerns.
- **Clear contract:** the API is the only integration surface, documented via
  FastAPI's auto-generated OpenAPI (`/docs`).
- **Trade-off:** no server-side rendering. Acceptable — there is no crawlable
  content and first paint of an app shell is fast enough.
- **Trade-off:** the SPA must be configured with the API's URL at build time
  (`VITE_API_URL`); handled in [ADR 0004]'s sibling config and the deploy docs.
