"""Tiny in-process metrics.

Not a Prometheus replacement — just enough to answer "is it up, how fast, how
often does it error" from the `/api/metrics` endpoint and structured logs. Most
student projects have zero observability, so even this is a differentiator.
"""

from __future__ import annotations

import threading
from collections import deque


class Metrics:
    def __init__(self, window: int = 500):
        self._lock = threading.Lock()
        self.request_count = 0
        self.error_count = 0
        self._latencies: deque[float] = deque(maxlen=window)

    def record_request(self, duration_ms: float, is_error: bool) -> None:
        with self._lock:
            self.request_count += 1
            if is_error:
                self.error_count += 1
            self._latencies.append(duration_ms)

    def snapshot(self) -> dict:
        with self._lock:
            lat = sorted(self._latencies)
            count = self.request_count
            errors = self.error_count
        return {
            "request_count": count,
            "error_count": errors,
            "error_rate": round(errors / count, 4) if count else 0.0,
            "latency_ms": {
                "p50": _percentile(lat, 50),
                "p95": _percentile(lat, 95),
                "p99": _percentile(lat, 99),
                "samples": len(lat),
            },
        }


def _percentile(sorted_values: list[float], pct: int) -> float | None:
    if not sorted_values:
        return None
    k = max(0, min(len(sorted_values) - 1, round((pct / 100) * len(sorted_values)) - 1))
    return round(sorted_values[k], 2)


METRICS = Metrics()
