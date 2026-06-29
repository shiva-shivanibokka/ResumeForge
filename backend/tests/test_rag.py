from app import db
from app.embeddings import resolve_embed_key
from app.services import rag


def test_resolve_embed_key_uses_user_key_when_gemini(monkeypatch):
    from app.config import Settings

    monkeypatch.setattr("app.embeddings.get_settings", lambda: Settings(_env_file=None))
    assert resolve_embed_key("gemini", "user-key") == "user-key"


def test_resolve_embed_key_falls_back_to_server_key(monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(
        "app.embeddings.get_settings",
        lambda: Settings(_env_file=None, google_api_key="server-key"),
    )
    # Non-Gemini engine → use the server-side Google key for embeddings.
    assert resolve_embed_key("groq", "groq-key") == "server-key"


def test_resolve_embed_key_none_when_unavailable(monkeypatch):
    from app.config import Settings

    monkeypatch.setattr("app.embeddings.get_settings", lambda: Settings(_env_file=None))
    assert resolve_embed_key("groq", "groq-key") is None


def test_vec_literal_format():
    assert db._vec([0.5, 1, 2.25]) == "[0.5,1.0,2.25]"


def test_db_disabled_without_url(monkeypatch):
    from app.config import Settings

    monkeypatch.setattr("app.db.get_settings", lambda: Settings(_env_file=None))
    assert db.is_enabled() is False
    # Disabled store returns empty/zero, never raises.
    assert db.rank_by_vector("user", [0.0] * 768) == []
    assert db.cache_status("user") == {"cached": False, "count": 0, "embedded_at": None}


def test_available_requires_db_and_key(monkeypatch):
    monkeypatch.setattr("app.services.rag.db", db)
    monkeypatch.setattr(db, "is_enabled", lambda: True)
    assert rag.available("key") is True
    assert rag.available("") is False
    monkeypatch.setattr(db, "is_enabled", lambda: False)
    assert rag.available("key") is False


def test_project_and_jd_text_build_nonempty():
    proj = {"name": "rf", "one_line": "resume tool", "tech_stack": ["python"], "keywords": ["fastapi"]}
    assert "rf" in rag._project_text(proj) and "python" in rag._project_text(proj)
    jd = {"job_title": "MLE", "required_skills": ["pytorch"]}
    assert "MLE" in rag._jd_text(jd) and "pytorch" in rag._jd_text(jd)


def test_embed_and_store_embeds_and_persists(monkeypatch):
    captured = {}
    monkeypatch.setattr(rag, "embed_texts", lambda texts, key: [[float(i)] * 3 for i in range(len(texts))])
    monkeypatch.setattr(rag.db, "replace_user_projects", lambda user, items: captured.update(user=user, items=items))
    projects = [{"name": "a"}, {"name": "b"}]
    count = rag.embed_and_store("octocat", projects, "key")
    assert count == 2
    assert captured["user"] == "octocat"
    assert [name for name, _data, _vec in captured["items"]] == ["a", "b"]


def test_rank_embeds_jd_and_queries_db(monkeypatch):
    monkeypatch.setattr(rag, "embed_one", lambda text, key: [0.1] * 3)
    monkeypatch.setattr(rag.db, "rank_by_vector", lambda user, vec, top_n: [{"name": "a", "match_score": 91.0}])
    out = rag.rank("octocat", {"job_title": "MLE"}, "key", top_n=5)
    assert out == [{"name": "a", "match_score": 91.0}]
