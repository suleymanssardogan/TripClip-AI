from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import videos

app = FastAPI(
    title="TripClip AI - Mobile BFF",
    description="Backend for Frontend - iOS",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
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
