"""Server-Sent Events helper for long-running streamed endpoints.

The business work (GitHub crawl, resume build) is blocking sync code that reports
progress via a callback. `stream_work` runs it in a thread and bridges progress
messages onto an async SSE generator without blocking the event loop, then emits
a final `done` (with the result dict) or `error` event. This replaces the
per-endpoint polled-list pattern that was duplicated across routes.
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from collections.abc import AsyncIterator, Callable

SSE_HEADERS = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}


def sse_line(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def stream_work(work: Callable[[Callable[[str], None]], dict]) -> AsyncIterator[str]:
    """Run `work(progress)` in a thread; yield progress then done/error SSE lines.

    `work` receives a `progress(msg: str)` callback and returns the final result
    dict (merged into the `done` event). Any exception becomes an `error` event.
    """
    # Bounded so a fast producer can't grow memory without limit; progress()
    # applies light backpressure if the client is slow to drain.
    q: queue.Queue[str] = queue.Queue(maxsize=2000)
    state: dict = {}

    def progress(msg: str) -> None:
        q.put(msg)

    def runner() -> None:
        try:
            state["result"] = work(progress)
        except Exception as e:  # noqa: BLE001 - surfaced as an SSE error event
            state["error"] = str(e)
        finally:
            state["done"] = True

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()

    while True:
        drained = False
        while True:
            try:
                msg = q.get_nowait()
            except queue.Empty:
                break
            drained = True
            yield sse_line({"type": "progress", "message": msg})
        if state.get("done") and q.empty():
            break
        if not drained:
            await asyncio.sleep(0.05)

    if "error" in state:
        yield sse_line({"type": "error", "message": state["error"]})
    else:
        yield sse_line({"type": "done", **(state.get("result") or {})})
