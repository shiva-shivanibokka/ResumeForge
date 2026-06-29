from app import db
from app.embeddings import EMBED_MODELS, resolve_embedder
from app.services import rag


def _settings(**kw):
    from app.config import Settings

    return Settings(_env_file=None, **kw)


def test_resolve_embedder_openai(monkeypatch):
    monkeypatch.setattr("app.embeddings.get_settings", lambda: _settings())
    assert resolve_embedder("openai", "sk-x") == ("openai", EMBED_MODELS["openai"][0], "sk-x")


def test_resolve_embedder_gemini(monkeypatch):
    monkeypatch.setattr("app.embeddings.get_settings", lambda: _settings())
    assert resolve_embedder("gemini", "g-x") == ("gemini", EMBED_MODELS["gemini"][0], "g-x")


def test_resolve_embedder_server_fallback(monkeypatch):
    # Groq has no embeddings API → fall back to a server-side key.
    monkeypatch.setattr("app.embeddings.get_settings", lambda: _settings(openai_api_key="srv-oai"))
    assert resolve_embedder("groq", "groq-key") == ("openai", EMBED_MODELS["openai"][0], "srv-oai")


def test_resolve_embedder_none(monkeypatch):
    monkeypatch.setattr("app.embeddings.get_settings", lambda: _settings())
    assert resolve_embedder("groq", "groq-key") is None


def test_vec_literal_format():
    assert db._vec([0.5, 1, 2.25]) == "[0.5,1.0,2.25]"


def test_db_disabled_without_url(monkeypatch):
    monkeypatch.setattr("app.db.get_settings", lambda: _settings())
    assert db.is_enabled() is False
    assert db.rank_by_vector("user", [0.0, 0.1]) == []
    assert db.cache_status("user") == {"cached": False, "count": 0, "embedded_at": None}
    assert db.cached_model("user") is None


def test_project_and_jd_text_build_nonempty():
    proj = {"name": "rf", "one_line": "resume tool", "tech_stack": ["python"], "keywords": ["fastapi"]}
    assert "rf" in rag._project_text(proj) and "python" in rag._project_text(proj)
    jd = {"job_title": "MLE", "required_skills": ["pytorch"]}
    assert "MLE" in rag._jd_text(jd) and "pytorch" in rag._jd_text(jd)


def test_embed_and_store_persists_with_model(monkeypatch):
    captured = {}
    monkeypatch.setattr(rag, "embed_texts", lambda texts, emb: [[float(i)] * 3 for i in range(len(texts))])
    monkeypatch.setattr(
        rag.db,
        "replace_user_projects",
        lambda user, items, model: captured.update(user=user, items=items, model=model),
    )
    count = rag.embed_and_store("octocat", [{"name": "a"}, {"name": "b"}], ("openai", "text-embedding-3-small", "k"))
    assert count == 2
    assert captured["user"] == "octocat"
    assert captured["model"] == "text-embedding-3-small"
    assert [name for name, _d, _v in captured["items"]] == ["a", "b"]


def test_rank_embeds_jd_and_queries_db(monkeypatch):
    monkeypatch.setattr(rag, "embed_one", lambda text, emb: [0.1] * 3)
    monkeypatch.setattr(rag.db, "rank_by_vector", lambda user, vec, top_n: [{"name": "a", "match_score": 91.0}])
    out = rag.rank("octocat", {"job_title": "MLE"}, ("gemini", "text-embedding-004", "k"), top_n=5)
    assert out == [{"name": "a", "match_score": 91.0}]
