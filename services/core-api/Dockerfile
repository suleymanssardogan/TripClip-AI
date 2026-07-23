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

# ── ML model ağırlıklarını BUILD zamanında indirip image'a göm ────────────────
# Önceden bu modeller ilk kullanımda (runtime'da) indiriliyordu: her container
# restart/redeploy'unda ~/.cache silinir (volume değil), bu yüzden ilk video
# her seferinde yüzlerce MB'lık bir indirme bekliyor ve (yavaş/kesik ağda) NER
# timeout'una (45s) takılıp sessizce fallback'e düşebiliyordu. Build'e taşımak
# runtime network bağımlılığını tamamen ortadan kaldırır.
#
# Bilerek COPY . .'dan ÖNCE: bu layer yalnızca requirements.txt veya
# WHISPER_MODEL değişince invalidate olur — her kod değişikliğinde (COPY . .)
# modelleri yeniden indirmez. WHISPER_MODEL, docker-compose(.prod).yml'deki
# runtime env değeriyle AYNI olmalı — build-arg olarak compose'dan otomatik
# geçirilir (bkz. docker-compose.prod.yml `build.args`).
ENV HOME=/app
ARG WHISPER_MODEL=small
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" \
 && python -c "import whisper; whisper.load_model('${WHISPER_MODEL}')" \
 && python -c "from transformers import pipeline; pipeline('ner', model='savasy/bert-base-turkish-ner-cased', aggregation_strategy='simple')" \
 && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

# uploads/ alt dizinleri burada, chown'dan ÖNCE oluşturulmalı — aksi halde
# Docker bunları sadece named volume mount edildiğinde (runtime'da) root
# sahipliğiyle yaratır ve non-root appuser mkdir/write yapamaz. Aynı chown,
# yukarıda root olarak indirilen model cache'inin (/app/.cache, /app/yolov8n.pt)
# sahipliğini de appuser'a çevirir.
RUN mkdir -p /app/uploads/videos /app/uploads/frames \
 && useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# GOOGLE_APPLICATION_CREDENTIALS is intentionally NOT set here.
# Provide it at runtime via Docker volume mount and environment variable:
#   docker run -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp.json \
#              -v /host/path/gcp.json:/run/secrets/gcp.json:ro ...
# Only needed when USE_GOOGLE_VISION=true.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
