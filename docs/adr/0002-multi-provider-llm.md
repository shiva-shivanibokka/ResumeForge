# ADR 0002 — Multi-provider LLM abstraction

**Status:** Accepted (2026-06-28)

## Context

The original code constructed an `anthropic.Anthropic` client directly in every
service and hardcoded a model string (`claude-opus-4-5`) at ~10 call sites.
Changing models meant editing every file; supporting another provider was
impossible without a rewrite; and a stale model string lingered everywhere.
For a portfolio piece, provider-agnostic LLM integration is also a stronger,
more legible signal than a single-vendor wrapper.

## Decision

Introduce an `app/llm` package with a single `LLMProvider` protocol
(`complete(prompt, system, max_tokens, ...) -> LLMResponse`) and concrete
adapters for **Anthropic, OpenAI, Google Gemini, and Groq**. A `factory.get_provider`
resolves the key (per-request "bring your own key" → server-side env fallback)
and returns a ready provider. A `registry` lists providers/models (with free-tier
flags) and powers the `/api/providers` endpoint and the UI picker. Services
depend only on the protocol.

## Consequences

- **Provider + model are a runtime choice**, surfaced in the UI. Gemini and Groq
  free tiers let the hosted demo run at no cost to the owner.
- **Errors are normalized** (`LLMError(kind=...)`) so routes can map them to
  sensible HTTP statuses without importing each SDK's exception tree.
- **SDK imports are lazy** (inside each adapter), so a missing optional SDK only
  fails if that provider is actually selected.
- **Model IDs live in one file** (`registry.py`) — the only place to update when
  they drift.
- **Trade-off:** the lowest-common-denominator `complete()` interface doesn't
  expose provider-specific features (tools, thinking modes). Fine for this app's
  structured-extraction calls; revisit if richer features are needed.
