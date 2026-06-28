# ADR 0004 — Ephemeral file store with TTL cleanup

**Status:** Accepted (2026-06-28)

## Context

Generated resumes/cover letters are handed to the client via an opaque id and
served back on download. The original implementation kept an unbounded
module-level `dict` mapping id → path, and the underlying temp files were never
deleted. That is two leaks: the dict grows for the life of the process, and temp
files accumulate on disk. The dict is also wiped on restart, so links silently
die — fine functionally, but the leaks are not.

## Decision

A `FileStore` (`app/store.py`) with a TTL: `register(path) -> id`, `get(id)`
returns the path only if it exists and hasn't expired (deleting it if it has),
and a background sweeper periodically removes expired entries and their files.
The store is a singleton wired into the app lifespan (sweeper started on startup,
cancelled on shutdown). `now` is injectable so the behavior is unit-tested
deterministically.

## Consequences

- **Bounded memory and disk:** entries and files expire (default 30 min,
  `FILE_TTL_SECONDS`).
- **Good fit for free-tier single-instance hosting:** no external dependency.
- **Trade-off:** state is per-process and in-memory, so it does not survive a
  restart and does not work across multiple instances. If ResumeForge ever scales
  horizontally, swap the implementation for object storage (e.g. S3 with lifecycle
  rules) behind the same `register`/`get` interface — the call sites won't change.
