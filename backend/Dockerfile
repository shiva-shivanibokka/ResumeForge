# ResumeForge backend image.
# LibreOffice is installed so DOCX->PDF conversion works in the container
# (docx2pdf / MS Word can't run here — see app/services/pdf.py).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System deps: LibreOffice Writer for PDF export + fonts for clean rendering.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-writer \
        fonts-dejavu \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

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
