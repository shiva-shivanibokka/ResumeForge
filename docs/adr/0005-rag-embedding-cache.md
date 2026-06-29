# ADR 0005 — RAG project matching with a pgvector embedding cache

**Status:** Accepted (2026-06-29)

## Context

Ranking GitHub projects for a job description re-crawled the user's repos,
LLM-summarized every repo, and LLM-ranked them on **every** run — slow, costly,
and repetitive when the repos rarely change. We wanted retrieval-based matching
(a genuine RAG signal) and a cache so unchanged repos aren't reprocessed, with an
explicit refresh when the user pushes new projects.

## Decision

Crawl + summarize + **embed each project once**, store the vectors in Postgres
(Neon) with the **pgvector** extension, and rank future JDs by cosine similarity
(`embedding <=> jd_vector`). A `force_reembed` flag refreshes the cache.

- **Embedding model is fixed** to Gemini `text-embedding-004` (768-dim, free).
  Project vectors and the JD query vector must come from the same model, so the
  embedder cannot vary with the user's chat-engine choice. The embedding key is
  the user's key when they're on Gemini, else a server-side `GOOGLE_API_KEY`.
- **Storage** is one table, `project_embeddings (github_user, name, data jsonb,
  embedding vector(768), embedding_model, updated_at)`, created idempotently at
  startup (no migration framework — YAGNI).
- **Graceful degradation:** if `DATABASE_URL` is unset *or* no embedding key is
  available, the feature is off and ranking falls back to the previous LLM path.
  The DB layer is inert without `DATABASE_URL`, so local dev needs no database.

## Consequences

- **Faster, cheaper repeat runs:** after the first embed, ranking a new JD is a
  single short embedding call + an indexed vector search — no crawl, no per-repo
  LLM. The UI shows "✓ N projects embedded {date}" and a **Re-embed** button.
- **Real portfolio signals:** retrieval-augmented matching, a vector database,
  and SQL — the data/retrieval gaps flagged in the market analysis.
- **Per-project match %** (cosine score) replaces the old LLM "why it fits"
  blurb — cheaper and honest.
- **Trade-offs:** the cache is keyed only by GitHub username (no per-commit
  invalidation — hence the manual Re-embed). Cosine match loses the natural-language
  rationale; acceptable. Requires provisioning a free managed Postgres and a
  Google key. If the embedding model is ever changed, stored `embedding_model`
  lets us detect and re-embed stale rows.
