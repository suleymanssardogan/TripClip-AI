FROM python:3.11-slim

# System dependencies + FFmpeg
RUN apt-get update && apt-get install -y \
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

# Credentials klasörünü kopyala (Google Vision API için)
COPY credentials /app/credentials

# Environment variable
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/tripclip-ai.json

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]