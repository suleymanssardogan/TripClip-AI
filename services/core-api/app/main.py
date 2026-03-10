from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

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

# Import router AFTER app creation
from app.api.internal import videos
app.include_router(videos.router)
