"""Operational endpoints: health, provider catalog, metrics."""

from __future__ import annotations

from fastapi import APIRouter

from app.llm import list_providers
from app.metrics import METRICS

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ResumeForge API"}


@router.get("/providers")
async def providers() -> dict:
    """LLM provider + model catalog for the frontend's picker."""
    return {"providers": list_providers()}


@router.get("/metrics")
async def metrics() -> dict:
    return METRICS.snapshot()
