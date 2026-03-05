from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="TripClip AI - Web BFF",
    description="Backend for Frontend - Web",
    version="0.1.0"
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
        "service": "Web BFF",
        "platform": "Web",
        "status": "running",
        "message":"Merhab WEB BFF bu kod Süleyman Tarafından yazıldı"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "web-bff"}
