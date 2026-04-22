from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, plans

app = FastAPI(
    title="TripClip AI - Web BFF",
    description="Backend for Frontend - Web",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/web")
app.include_router(plans.router, prefix="/api/web")


@app.get("/")
async def root():
    return {"service": "Web BFF", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "web-bff"}
