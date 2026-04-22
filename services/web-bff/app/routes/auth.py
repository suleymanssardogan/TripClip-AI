from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import os

router = APIRouter(prefix="/auth", tags=["auth"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    username: str | None = None


async def _forward(path: str, body: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{CORE_API_URL}{path}", json=body)
        
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", "İşlem başarısız")
            except:
                detail = f"Backend Hatası: {resp.status_code}"
            raise HTTPException(status_code=resp.status_code, detail=detail)
        
        return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Core API hizmetine erişilemiyor")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
async def login(body: LoginRequest):
    return await _forward("/internal/auth/login", body.model_dump())


@router.post("/register")
async def register(body: RegisterRequest):
    return await _forward("/internal/auth/register", body.model_dump())
