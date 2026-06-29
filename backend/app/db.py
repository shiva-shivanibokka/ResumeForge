"""Postgres + pgvector store for cached GitHub-project embeddings.

Disabled (and inert) when DATABASE_URL is unset, so local dev and the existing
flow work with no database. The embedding column is dimension-agnostic (`vector`
with no fixed size) so vectors from different models can coexist — Gemini (768)
and OpenAI (1536). Each row records its `embedding_model`; ranking only ever
compares vectors of the same model (all of a user's rows share one model, since
they're replaced atomically). Cosine search via pgvector's `<=>` operator.
Read paths degrade to "empty" on any error so the API never 500s on a DB hiccup.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from app.config import get_settings
from app.logging import get_logger

log = get_logger("db")

_CREATE = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS project_embeddings (
    id            bigserial PRIMARY KEY,
    github_user   text NOT NULL,
    name          text NOT NULL,
    data          jsonb NOT NULL,
    embedding     vector NOT NULL,
    embedding_model text NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (github_user, name)
);
CREATE INDEX IF NOT EXISTS project_embeddings_user_idx
    ON project_embeddings (github_user);
"""

# Migrate an older fixed-dimension column (vector(768)) to dimension-agnostic.
_ALTER = "ALTER TABLE project_embeddings ALTER COLUMN embedding TYPE vector;"


def is_enabled() -> bool:
    return bool((get_settings().database_url or "").strip())


@contextmanager
def _conn() -> Iterator:
    import psycopg

    conn = psycopg.connect(get_settings().database_url, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


def _vec(values: list[float]) -> str:
    """Format a vector as a pgvector text literal for `%s::vector`."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def init_db() -> None:
    """Create the extension + table (and migrate the column type) when enabled."""
    if not is_enabled():
        return
    with _conn() as conn:
        conn.execute(_CREATE)
        try:
            conn.execute(_ALTER)
        except Exception as e:  # noqa: BLE001 - already dimension-agnostic / nothing to do
            log.info("db_alter_skipped", detail=str(e)[:120])
    log.info("db_ready")


def cache_status(github_user: str) -> dict:
    """Return {cached, count, embedded_at}; degrades to not-cached on error."""
    if not is_enabled():
        return {"cached": False, "count": 0, "embedded_at": None}
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT count(*), max(updated_at) FROM project_embeddings WHERE github_user = %s",
                (github_user,),
            ).fetchone()
    except Exception as e:  # noqa: BLE001
        log.error("cache_status_failed", error=str(e))
        return {"cached": False, "count": 0, "embedded_at": None}
    count = row[0] if row else 0
    embedded_at: datetime | None = row[1] if row else None
    return {
        "cached": count > 0,
        "count": count,
        "embedded_at": embedded_at.isoformat() if embedded_at else None,
    }


def cached_model(github_user: str) -> str | None:
    """The embedding model a user's cached projects were embedded with (or None)."""
    if not is_enabled():
        return None
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT embedding_model FROM project_embeddings WHERE github_user = %s LIMIT 1",
                (github_user,),
            ).fetchone()
        return row[0] if row else None
    except Exception as e:  # noqa: BLE001
        log.error("cached_model_failed", error=str(e))
        return None


def replace_user_projects(
    github_user: str, items: list[tuple[str, dict, list[float]]], embedding_model: str
) -> None:
    """Atomically replace all cached rows for a user with fresh (name, data, vec)."""
    if not is_enabled():
        return
    with _conn() as conn, conn.transaction():
        conn.execute(
            "DELETE FROM project_embeddings WHERE github_user = %s", (github_user,)
        )
        for name, data, vec in items:
            conn.execute(
                """INSERT INTO project_embeddings
                   (github_user, name, data, embedding, embedding_model)
                   VALUES (%s, %s, %s, %s::vector, %s)""",
                (github_user, name, json.dumps(data), _vec(vec), embedding_model),
            )


def rank_by_vector(github_user: str, jd_vec: list[float], top_n: int = 10) -> list[dict]:
    """Cosine-rank cached projects against the JD vector; degrades to [] on error."""
    if not is_enabled():
        return []
    lit = _vec(jd_vec)
    try:
        with _conn() as conn:
            rows = conn.execute(
                """SELECT data, 1 - (embedding <=> %s::vector) AS score
                   FROM project_embeddings
                   WHERE github_user = %s
                   ORDER BY embedding <=> %s::vector
                   LIMIT %s""",
                (lit, github_user, lit, top_n),
            ).fetchall()
    except Exception as e:  # noqa: BLE001
        log.error("rank_by_vector_failed", error=str(e))
        return []
    results = []
    for data, score in rows:
        proj = dict(data)
        proj["match_score"] = round(max(0.0, min(1.0, float(score))) * 100, 1)
        results.append(proj)
    return results
