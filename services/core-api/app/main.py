from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

import sentry_sdk
sentry_sdk.init(
    dsn="https://1538a657aa1234c66d5af8f3101f6142@o4511132818407424.ingest.de.sentry.io/4511132827648080",
    send_default_pii=True,
    traces_sample_rate=1.0,
    profile_session_sample_rate=1.0,
    profile_lifecycle="trace",
)

app = FastAPI(
    title="TripClip AI - Core API",
    description="Business logic and AI services",
    version="0.1.0"
)
# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # ← Docker log'a yaz!
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "service": "Core API",
        "message": "Business logic layer",
        "status": "running"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "core-api"}

# Import routers AFTER app creation
from app.api.internal import videos, auth
app.include_router(videos.router)
app.include_router(auth.router)
