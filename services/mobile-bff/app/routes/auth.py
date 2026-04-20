from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import os

router = APIRouter(prefix="/auth", tags=["auth"])

CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


class RegisterRequest(BaseModel):
    email: str
    password: str
    username: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AppleSignInRequest(BaseModel):
    identity_token: str
    full_name: str | None = None


async def _forward(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{CORE_API_URL}{path}", json=body)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail"))
    return resp.json()


@router.post("/register")
async def register(body: RegisterRequest):
    return await _forward("/internal/auth/register", body.model_dump())


@router.post("/login")
async def login(body: LoginRequest):
    return await _forward("/internal/auth/login", body.model_dump())


@router.post("/apple")
async def apple_sign_in(body: AppleSignInRequest):
    return await _forward("/internal/auth/apple", body.model_dump())
