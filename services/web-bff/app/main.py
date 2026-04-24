from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, plans
from app.routes import videos as videos_router
import os

# Web BFF: yalnızca Next.js web uygulamasından istek gelir.
# ALLOWED_ORIGINS env ile production domain eklenebilir.
_raw = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = (
    [o.strip() for o in _raw.split(",") if o.strip()]
    if _raw
    else [
        "http://localhost:3001",    # local Next.js dev
        "http://127.0.0.1:3001",
    ]
)

app = FastAPI(
    title="TripClip AI - Web BFF",
    description="Backend for Frontend - Web",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router,          prefix="/api/web")
app.include_router(plans.router,         prefix="/api/web")
app.include_router(videos_router.router, prefix="/api/web")


@app.get("/")
async def root():
    return {"service": "Web BFF", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "web-bff"}
