import pytest

from app.security import assert_public_http_url, validate_upload


def _resolver_for(ip: str):
    # Mimic socket.getaddrinfo's tuple shape: (family, type, proto, canonname, sockaddr)
    return lambda host: [(2, 1, 6, "", (ip, 0))]


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/x",
        "file:///etc/passwd",
        "http://127.0.0.1/x",
        "http://localhost/x",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/x",
        "http://192.168.1.1/x",
        "http://[::1]/x",
        "http://172.16.0.1/x",
    ],
)
def test_blocks_ssrf(url):
    # Literal IPs/loopback resolve to themselves; only the scheme/host checks matter.
    with pytest.raises(ValueError):
        assert_public_http_url(url, resolver=_resolver_for("127.0.0.1"))


def test_blocks_public_host_resolving_to_private():
    # A public-looking domain that secretly resolves to an internal IP is still blocked.
    with pytest.raises(ValueError):
        assert_public_http_url("https://evil.example.com/x", resolver=_resolver_for("10.1.2.3"))


def test_allows_public():
    url = assert_public_http_url("https://jobs.example.com/posting/1", resolver=_resolver_for("93.184.216.34"))
    assert url.startswith("https://")


def test_empty_url():
    with pytest.raises(ValueError):
        assert_public_http_url("")


def test_upload_rejects_exe():
    with pytest.raises(ValueError):
        validate_upload("malware.exe", 1000, 10)


def test_upload_rejects_oversize():
    with pytest.raises(ValueError):
        validate_upload("resume.pdf", 20 * 1024 * 1024, 10)


def test_upload_ok_pdf_and_docx():
    validate_upload("resume.pdf", 1000, 10)
    validate_upload("resume.docx", 1000, 10)
