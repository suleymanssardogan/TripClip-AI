"""
Web BFF — Auth route handler'ları.
Tüm Core API hataları web_error_wrapper aracılığıyla web dostu mesajlara çevrilir.
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
import httpx
from app.core.internal_client import internal_client
import os
import uuid

from app.core.error_wrapper import web_error_wrapper, raise_from_response

router  = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    username: str | None = None


class AppleSignInRequest(BaseModel):
    identity_token: str
    full_name: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


async def _forward(path: str, body: dict, rid: str) -> dict:
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.post(f"{CORE_API_URL}{path}", json=body)
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.post("/login")
async def login(body: LoginRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/login", body.model_dump(), rid)


@router.post("/register")
async def register(body: RegisterRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/register", body.model_dump(), rid)


@router.post("/apple")
async def apple_sign_in(body: AppleSignInRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/apple", body.model_dump(), rid)


@router.post("/refresh")
@limiter.limit("20/minute")
async def refresh(request: Request, body: RefreshRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/refresh", body.model_dump(), rid)


@router.post("/logout")
@limiter.limit("20/minute")
async def logout(request: Request, body: RefreshRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/logout", body.model_dump(), rid)
