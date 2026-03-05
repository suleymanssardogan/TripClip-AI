
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import videos



app = FastAPI(
    title="TripClip AI API",
    description="AI-powered travel planning from Instagram videos",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router)

@app.get("/")
async def root():
    return {
        "message": "🚀 TripClip AI API",
        "version": "0.1.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
