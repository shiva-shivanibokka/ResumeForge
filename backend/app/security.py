"""Input-security helpers: SSRF guard for outbound URL fetches and upload validation.

The JD-fetch feature retrieves a *user-supplied* URL server-side. Without a guard
that is a classic SSRF vector (e.g. hitting the cloud metadata endpoint at
169.254.169.254 to steal credentials, or probing internal services). We resolve
the host and reject any address that is not globally routable.
"""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx"}

Resolver = Callable[[str], list]


def _default_resolver(host: str) -> list:
    # Returns getaddrinfo tuples; we only use the resolved IP (index 4[0]).
    return socket.getaddrinfo(host, None)


def _is_global(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_public_http_url(url: str, *, resolver: Resolver = _default_resolver) -> str:
    """Validate that `url` is an http(s) URL whose host resolves only to public IPs.

    Returns the normalized URL on success; raises ValueError otherwise.
    """
    url = (url or "").strip()
    if not url:
        raise ValueError("Empty URL.")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http(s) URLs are allowed, got scheme '{parsed.scheme}'.")
    host = parsed.hostname
    if not host:
        raise ValueError("URL has no host.")

    try:
        infos = resolver(host)
    except (socket.gaierror, OSError) as exc:
        raise ValueError(f"Could not resolve host '{host}'.") from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise ValueError(f"Host '{host}' did not resolve to any address.")

    for addr in addresses:
        if not _is_global(addr):
            raise ValueError(
                f"Refusing to fetch '{host}' — resolves to non-public address {addr}."
            )
    return url


def validate_upload(filename: str, size: int, max_mb: int) -> None:
    """Raise ValueError if the upload has a disallowed extension or exceeds the size cap."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise ValueError(f"Unsupported file type '{ext or '(none)'}'. Allowed: {allowed}.")
    if size > max_mb * 1024 * 1024:
        raise ValueError(f"File too large ({size} bytes). Max is {max_mb} MB.")
