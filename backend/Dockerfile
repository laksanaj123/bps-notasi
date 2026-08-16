FROM python:3.12-slim

# libreoffice-writer -> soffice binary (backend/app/services/pdf_export.py)
# ffmpeg           -> audio chunking untuk rapat panjang (services/transcription.py)
# build-essential   -> compile deps untuk faster-whisper/bcrypt/ctranslate2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    ffmpeg \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY backend/requirements.txt backend/requirements-local-ai.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -r backend/requirements-local-ai.txt

COPY backend/app backend/app
COPY backend/scripts backend/scripts
COPY frontend frontend

WORKDIR /srv/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/config || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
