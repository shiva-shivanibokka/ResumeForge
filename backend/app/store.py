"""Ephemeral file store with TTL-based cleanup.

Generated resumes/cover letters are written to a temp dir and handed to the client
via an opaque id. The previous implementation kept an unbounded in-memory dict and
never deleted the temp files — a memory + disk leak. This store expires entries
after `ttl_seconds` and a background sweeper deletes the underlying files.

A `now` callable is injectable so tests can control time deterministically.
"""

from __future__ import annotations

import asyncio
import threading
import time as _time
import uuid
from pathlib import Path
from typing import Callable


class FileStore:
    def __init__(
        self,
        ttl_seconds: int = 1800,
        *,
        now: Callable[[], float] = _time.time,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self._now = now
        self._entries: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._sweeper_task: asyncio.Task | None = None

    def register(self, path: str) -> str:
        file_id = str(uuid.uuid4())
        with self._lock:
            self._entries[file_id] = (path, self._now())
        return file_id

    def get(self, file_id: str) -> Path | None:
        with self._lock:
            entry = self._entries.get(file_id)
            if entry is None:
                return None
            path, created = entry
            if self._now() - created > self.ttl_seconds:
                self._entries.pop(file_id, None)
                self._remove_file(path)
                return None
        p = Path(path)
        return p if p.exists() else None

    def sweep(self) -> int:
        """Delete expired entries and their files. Returns the number removed."""
        cutoff = self._now() - self.ttl_seconds
        removed = 0
        with self._lock:
            expired = [fid for fid, (_, created) in self._entries.items() if created < cutoff]
            for fid in expired:
                path, _ = self._entries.pop(fid)
                self._remove_file(path)
                removed += 1
        return removed

    @staticmethod
    def _remove_file(path: str) -> None:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass

    async def _sweep_loop(self, interval: int) -> None:
        while True:
            await asyncio.sleep(interval)
            self.sweep()

    def start_background_sweeper(self, interval: int = 300) -> None:
        if self._sweeper_task is None:
            self._sweeper_task = asyncio.create_task(self._sweep_loop(interval))

    def stop(self) -> None:
        if self._sweeper_task is not None:
            self._sweeper_task.cancel()
            self._sweeper_task = None


_store: FileStore | None = None


def get_store() -> FileStore:
    global _store
    if _store is None:
        from app.config import get_settings

        _store = FileStore(ttl_seconds=get_settings().file_ttl_seconds)
    return _store
