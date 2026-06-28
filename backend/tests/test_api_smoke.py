import io

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_providers_lists_all_four(client):
    r = client.get("/api/providers")
    assert r.status_code == 200
    keys = {p["key"] for p in r.json()["providers"]}
    assert {"anthropic", "openai", "gemini", "groq"} <= keys


def test_metrics_shape(client):
    r = client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "request_count" in body and "latency_ms" in body


def test_download_unknown_id_404(client):
    r = client.get("/api/download/does-not-exist")
    assert r.status_code == 404


def test_analyse_missing_jd_returns_400(client, monkeypatch):
    # Stub the provider so no real key/network is needed; the request should still
    # 400 because neither a JD URL nor JD text is supplied.
    from app.llm.base import LLMResponse

    class StubProvider:
        name = "stub"

        def complete(self, **kwargs):
            return LLMResponse(text="{}", model="stub", provider="stub")

    monkeypatch.setattr("app.deps.get_provider", lambda *a, **k: StubProvider())

    files = {"resume_file": ("resume.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")}
    data = {"provider": "anthropic", "jd_url": "", "jd_text": ""}
    r = client.post("/api/analyse", data=data, files=files)
    assert r.status_code == 400


def test_analyse_bad_provider_returns_400(client):
    files = {"resume_file": ("resume.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")}
    data = {"provider": "nope", "jd_text": "Some JD"}
    r = client.post("/api/analyse", data=data, files=files)
    assert r.status_code == 400


def test_analyse_rejects_bad_upload_type(client, monkeypatch):
    from app.llm.base import LLMResponse

    class StubProvider:
        name = "stub"

        def complete(self, **kwargs):
            return LLMResponse(text="{}", model="stub", provider="stub")

    monkeypatch.setattr("app.deps.get_provider", lambda *a, **k: StubProvider())
    files = {"resume_file": ("resume.exe", io.BytesIO(b"MZ"), "application/octet-stream")}
    data = {"provider": "anthropic", "jd_text": "Some JD text here"}
    r = client.post("/api/analyse", data=data, files=files)
    assert r.status_code == 400
