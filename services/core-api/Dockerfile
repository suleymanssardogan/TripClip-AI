FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# uploads/ alt dizinleri burada, chown'dan ÖNCE oluşturulmalı — aksi halde
# Docker bunları sadece named volume mount edildiğinde (runtime'da) root
# sahipliğiyle yaratır ve non-root appuser mkdir/write yapamaz.
RUN mkdir -p /app/uploads/videos /app/uploads/frames \
 && useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# GOOGLE_APPLICATION_CREDENTIALS is intentionally NOT set here.
# Provide it at runtime via Docker volume mount and environment variable:
#   docker run -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp.json \
#              -v /host/path/gcp.json:/run/secrets/gcp.json:ro ...
# Only needed when USE_GOOGLE_VISION=true.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
