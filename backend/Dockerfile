# ResumeForge backend (API) image.
# NOTE: LibreOffice is intentionally NOT installed here — it spikes ~300 MB and
# OOM-kills Render's 512 MB free instance. DOCX->PDF conversion is delegated to
# a separate converter service (PDF_SERVICE_URL); see pdf-service/ and
# app/services/pdf.py. Without it, the app still delivers DOCX.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Render (and most PaaS) inject $PORT; default to 8000 locally. Shell form so the
# variable is expanded.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
