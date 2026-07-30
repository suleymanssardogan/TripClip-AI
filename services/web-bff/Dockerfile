# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache /wheels/* && rm -rf /wheels

COPY . .

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# --proxy-headers: nginx'in gönderdiği X-Forwarded-For/X-Real-IP header'larından
# gerçek istemci IP'sini request.client.host'a yazar (aksi halde her istek nginx'in
# container IP'si gibi görünür ve rate-limit tüm kullanıcılar arasında paylaşılır).
# forwarded-allow-ips=* güvenli: bu container'a app-network dışından hiçbir port
# açılmıyor (docker-compose.prod.yml), yani bu header'ı yalnızca nginx ayarlayabilir.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--proxy-headers", "--forwarded-allow-ips=*"]