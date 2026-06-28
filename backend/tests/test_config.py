from app.config import Settings, get_settings

# Tests pass _env_file=None so they never read the developer's local .env.


def test_defaults(monkeypatch):
    for var in ["ALLOWED_ORIGINS", "FILE_TTL_SECONDS", "MAX_UPLOAD_MB", "ENVIRONMENT"]:
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.file_ttl_seconds == 1800
    assert s.max_upload_mb == 10
    assert s.request_timeout_s == 60
    assert s.llm_max_retries == 2
    assert s.environment == "dev"
    assert s.allowed_origins == ["http://localhost:5173"]


def test_origins_parsed_from_csv(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://a.com, http://b.com")
    s = Settings(_env_file=None)
    assert s.allowed_origins == ["http://a.com", "http://b.com"]


def test_origins_single_value(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://x.com")
    s = Settings(_env_file=None)
    assert s.allowed_origins == ["http://x.com"]


def test_server_keys_optional(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = Settings(_env_file=None)
    assert s.anthropic_api_key is None


def test_get_settings_is_cached():
    get_settings.cache_clear()
    assert get_settings() is get_settings()
