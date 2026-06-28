import pytest

from app.llm.base import LLMError, LLMResponse
from app.llm.factory import get_provider
from app.llm.registry import PROVIDERS, list_providers


def test_registry_every_provider_has_models_and_default():
    for key, info in PROVIDERS.items():
        assert info.models, f"{key} has no models"
        ids = {m.id for m in info.models}
        assert info.default_model in ids, f"{key} default not in its model list"


def test_list_providers_shape():
    providers = list_providers()
    keys = {p["key"] for p in providers}
    assert {"anthropic", "openai", "gemini", "groq"} <= keys
    gemini = next(p for p in providers if p["key"] == "gemini")
    assert gemini["free_tier"] is True
    assert any(m["free"] for m in gemini["models"])


def test_anthropic_and_openai_are_paid():
    for p in list_providers():
        if p["key"] in ("anthropic", "openai"):
            assert p["free_tier"] is False


def test_factory_unknown_provider_raises_bad_request():
    with pytest.raises(LLMError) as exc:
        get_provider("does-not-exist", api_key="x", model=None)
    assert exc.value.kind == "bad_request"


def test_factory_missing_key_raises_auth(monkeypatch):
    # Build settings without reading the dev .env, and without any provider key
    # in the environment, so key resolution finds nothing.
    for var in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"]:
        monkeypatch.delenv(var, raising=False)
    from app.config import Settings

    monkeypatch.setattr("app.llm.factory.get_settings", lambda: Settings(_env_file=None))
    with pytest.raises(LLMError) as exc:
        get_provider("anthropic", api_key=None, model=None)
    assert exc.value.kind == "auth"


def test_factory_routes_with_explicit_key():
    # A non-empty explicit key skips env resolution; construction should succeed
    # (no network call happens until .complete()).
    provider = get_provider("groq", api_key="test-key-123", model=None)
    assert provider.name == "groq"


def test_llm_response_dataclass():
    r = LLMResponse(text="hi", model="m", provider="p")
    assert r.usage is None and r.text == "hi"
