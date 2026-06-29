"""Lightweight in-process per-IP rate limiter for expensive endpoints.

Single-worker friendly (a sliding window in memory; not distributed). Its job is
to stop an anonymous visitor from draining the owner's server-side API-key quota
on the LLM/crawl endpoints. Disabled when `rate_limit_max <= 0`.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from starlette.requests import Request

from app.config import get_settings

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate(ip: str) -> bool:
    """Record a hit for `ip`; return False if it has exceeded the window limit."""
    settings = get_settings()
    limit, window = settings.rate_limit_max, settings.rate_limit_window_s
    if limit <= 0:
        return True
    now = time.monotonic()
    with _lock:
        if len(_hits) > 10000:  # crude unbounded-growth guard
            _hits.clear()
        dq = _hits[ip]
        while dq and dq[0] <= now - window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True
