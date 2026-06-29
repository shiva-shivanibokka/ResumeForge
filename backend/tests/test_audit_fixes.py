"""Regression tests for the repo-bug-audit fixes."""

from app.config import Settings


def _settings(**kw):
    return Settings(_env_file=None, **kw)


# Task 5 — entry-header font must never exceed body size on dense resumes.
def test_fit_entry_size_never_exceeds_body():
    from app.services.resume_builder import _fit_entry_size

    long_left = "Deenbandhu Chhotu Ram University of Science and Technology"
    # At a small body size the shrink result must not jump back up to the 8.5 floor.
    assert _fit_entry_size(long_left, "May 2011 - May 2016", 7.0) <= 7.0
    assert _fit_entry_size("Short Co", "2024", 7.5) <= 7.5
    # Short text that fits keeps the body size unchanged.
    assert _fit_entry_size("Acme", "2024", 11.0) == 11.0


# Task 6 — per-IP rate limiter blocks after the configured max.
def test_rate_limit_blocks_after_max(monkeypatch):
    import app.ratelimit as rl

    monkeypatch.setattr(rl, "get_settings", lambda: _settings(rate_limit_max=2, rate_limit_window_s=3600))
    ip = "203.0.113.77"  # unique to this test to avoid shared-state bleed
    assert rl.check_rate(ip) is True
    assert rl.check_rate(ip) is True
    assert rl.check_rate(ip) is False  # third hit over the limit of 2


def test_rate_limit_disabled_when_max_zero(monkeypatch):
    import app.ratelimit as rl

    monkeypatch.setattr(rl, "get_settings", lambda: _settings(rate_limit_max=0))
    ip = "203.0.113.78"
    assert all(rl.check_rate(ip) for _ in range(50))


# Task 4 — SSRF: a redirect to a private/link-local address must be blocked.
def test_jd_fetch_blocks_redirect_to_metadata(monkeypatch):
    from app.services import jd_parser

    class FakeResp:
        is_redirect = True
        is_permanent_redirect = False
        status_code = 302
        headers = {"Location": "http://169.254.169.254/latest/meta-data/"}

    monkeypatch.setattr(jd_parser.requests, "get", lambda *a, **k: FakeResp())
    result = jd_parser.fetch_jd_text("http://example.com/jobs/123")
    assert result["success"] is False
    assert "redirect" in (result["error"] or "").lower()
