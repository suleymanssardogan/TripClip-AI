FROM python:3.11-slim

# Runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Set credentials
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/tripclip-ai.json

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]