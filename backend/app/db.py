"""Postgres + pgvector store for cached GitHub-project embeddings.

Disabled (and inert) when DATABASE_URL is unset, so local dev and the existing
flow work with no database. One idempotent table; cosine search via pgvector's
`<=>` operator. Connections are short-lived (Neon pools server-side).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from app.config import get_settings
from app.embeddings import EMBED_DIM, EMBED_MODEL
from app.logging import get_logger

log = get_logger("db")

_CREATE = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS project_embeddings (
    id            bigserial PRIMARY KEY,
    github_user   text NOT NULL,
    name          text NOT NULL,
    data          jsonb NOT NULL,
    embedding     vector({EMBED_DIM}) NOT NULL,
    embedding_model text NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (github_user, name)
);
CREATE INDEX IF NOT EXISTS project_embeddings_user_idx
    ON project_embeddings (github_user);
"""


def is_enabled() -> bool:
    return bool((get_settings().database_url or "").strip())


@contextmanager
def _conn() -> Iterator:
    import psycopg
    from pgvector.psycopg import register_vector

    conn = psycopg.connect(get_settings().database_url, autocommit=True)
    try:
        register_vector(conn)
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create the extension + table. Called once at startup when enabled."""
    if not is_enabled():
        return
    with _conn() as conn:
        conn.execute(_CREATE)
    log.info("db_ready", model=EMBED_MODEL, dim=EMBED_DIM)


def cache_status(github_user: str) -> dict:
    """Return {cached, count, embedded_at} for a user."""
    if not is_enabled():
        return {"cached": False, "count": 0, "embedded_at": None}
    with _conn() as conn:
        row = conn.execute(
            "SELECT count(*), max(updated_at) FROM project_embeddings WHERE github_user = %s",
            (github_user,),
        ).fetchone()
    count = row[0] if row else 0
    embedded_at: datetime | None = row[1] if row else None
    return {
        "cached": count > 0,
        "count": count,
        "embedded_at": embedded_at.isoformat() if embedded_at else None,
    }


def replace_user_projects(
    github_user: str, items: list[tuple[str, dict, list[float]]]
) -> None:
    """Atomically replace all cached rows for a user with fresh (name, data, vec)."""
    if not is_enabled():
        return
    with _conn() as conn:
        with conn.transaction():
            conn.execute(
                "DELETE FROM project_embeddings WHERE github_user = %s", (github_user,)
            )
            for name, data, vec in items:
                conn.execute(
                    """INSERT INTO project_embeddings
                       (github_user, name, data, embedding, embedding_model)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (github_user, name, json.dumps(data), vec, EMBED_MODEL),
                )


def rank_by_vector(github_user: str, jd_vec: list[float], top_n: int = 10) -> list[dict]:
    """Cosine-rank cached projects against the JD vector; attach match_score (0-100)."""
    if not is_enabled():
        return []
    with _conn() as conn:
        rows = conn.execute(
            """SELECT data, 1 - (embedding <=> %s) AS score
               FROM project_embeddings
               WHERE github_user = %s
               ORDER BY embedding <=> %s
               LIMIT %s""",
            (jd_vec, github_user, jd_vec, top_n),
        ).fetchall()
    results = []
    for data, score in rows:
        proj = dict(data)
        proj["match_score"] = round(max(0.0, min(1.0, float(score))) * 100, 1)
        results.append(proj)
    return results
