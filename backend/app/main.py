"""FastAPI application factory.

Wires logging, settings validation (fail loud at startup), CORS, the request
middleware (timing + metrics), the file-store background sweeper, and all routers.
Run locally: `uvicorn app.main:app --reload --port 8000`.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings
from app.logging import configure_logging, get_logger
from app.metrics import METRICS
from app.ratelimit import check_rate, client_ip
from app.routers import analyse, cover_letter, files, generate, meta, projects
from app.store import get_store

# Expensive LLM/crawl endpoints protected by the per-IP rate limiter. Cheap/polled
# routes (/projects/cache) and frequent layout tweaks (/rebuild-resume) are excluded.
_RATE_LIMITED_PATHS = {
    "/api/analyse",
    "/api/generate",
    "/api/fetch-projects",
    "/api/cover-letter",
    "/api/edit-cover-letter",
    "/api/edit-resume",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """429 a client that exceeds the per-IP window on expensive endpoints."""

    async def dispatch(self, request, call_next):
        if request.method == "POST" and request.url.path in _RATE_LIMITED_PATHS:
            if not check_rate(client_ip(request)):
                return JSONResponse(
                    {"detail": "Rate limit reached. Please slow down, or use your own API key."},
                    status_code=429,
                )
        return await call_next(request)


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """Assign a request_id, time the request, log it, and record metrics."""

    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        log = get_logger("request")
        start = time.perf_counter()
        status = 500
        response = None
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            METRICS.record_request(duration_ms, status >= 500)
            log.info(
                "request",
                method=request.method,
                path=request.url.path,
                status_code=status,
                duration_ms=duration_ms,
            )
            if response is not None:
                response.headers["X-Request-ID"] = request_id
            structlog.contextvars.clear_contextvars()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()  # raises immediately if config is invalid
    configure_logging(settings.log_level)
    get_logger("startup").info(
        "starting", environment=settings.environment, origins=settings.allowed_origins
    )
    from app import db

    if db.is_enabled():
        try:
            db.init_db()
        except Exception as e:  # noqa: BLE001 - never let DB issues block startup
            get_logger("startup").error("db_init_failed", error=str(e))

    store = get_store()
    store.start_background_sweeper()
    try:
        yield
    finally:
        store.stop()
        db.close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ResumeForge API", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_origin_regex=(settings.allowed_origin_regex or None),
        # No cookies/session auth (BYOK) — credentials must stay off so a hostile
        # *.vercel.app origin can't make credentialed cross-origin requests.
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestObservabilityMiddleware)
    app.add_middleware(RateLimitMiddleware)

    app.include_router(meta.router)
    app.include_router(analyse.router)
    app.include_router(projects.router)
    app.include_router(generate.router)
    app.include_router(cover_letter.router)
    app.include_router(files.router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
