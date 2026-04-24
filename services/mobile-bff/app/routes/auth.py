"""
Mobile BFF — Auth route handler'ları.
Tüm Core API hataları mobile_error_wrapper aracılığıyla iOS dostu mesajlara çevrilir.
"""
from fastapi import APIRouter
from pydantic import BaseModel
import httpx
import os
import uuid

from app.core.error_wrapper import mobile_error_wrapper, raise_from_response

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


async def _forward(path: str, body: dict, rid: str) -> dict:
    async with mobile_error_wrapper(request_id=rid):
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{CORE_API_URL}{path}", json=body)
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.post("/register")
async def register(body: RegisterRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/register", body.model_dump(), rid)


@router.post("/login")
async def login(body: LoginRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/login", body.model_dump(), rid)


@router.post("/apple")
async def apple_sign_in(body: AppleSignInRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/apple", body.model_dump(), rid)
