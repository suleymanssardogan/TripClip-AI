from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routes import videos, auth
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="TripClip AI - Mobile BFF",
    description="Backend for Frontend - iOS",
    version="0.1.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mobile BFF: iOS native app CORS göndermez.
# Yalnızca local geliştirme araçları (Swagger, Postman web) için origin kısıtlaması.
import os as _os
_raw = _os.getenv("ALLOWED_ORIGINS", "")
_MOBILE_ORIGINS = (
    [o.strip() for o in _raw.split(",") if o.strip()]
    if _raw
    else [
        "http://localhost:3001",    # Next.js (Swagger erişimi için)
        "http://127.0.0.1:3001",
        "http://localhost:8000",    # core-api Swagger UI
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_MOBILE_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api/mobile")
app.include_router(videos.router, prefix="/api/mobile")

@app.get("/")
async def root():
    return {
        "service": "Mobile BFF",
        "platform": "iOS",
        "status": "running"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "mobile-bff"}