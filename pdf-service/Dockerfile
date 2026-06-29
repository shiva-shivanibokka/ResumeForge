# ResumeForge PDF converter — minimal FastAPI + LibreOffice.
# Only this container carries LibreOffice, so its ~300 MB spike has the full
# 512 MB to itself; the main API image stays light.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-writer \
        fonts-dejavu \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY app.py ./

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
