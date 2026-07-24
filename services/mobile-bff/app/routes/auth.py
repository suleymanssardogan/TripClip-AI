"""
Mobile BFF — Auth route handler'ları.
Tüm Core API hataları mobile_error_wrapper aracılığıyla iOS dostu mesajlara çevrilir.
"""
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
import httpx
from app.core.internal_client import internal_client
import os
import uuid

from app.core.auth import get_current_user_id
from app.core.error_wrapper import mobile_error_wrapper, raise_from_response

router  = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

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


class RefreshRequest(BaseModel):
    refresh_token: str


class DeviceTokenRequest(BaseModel):
    token: str


async def _forward(path: str, body: dict, rid: str, client_ip: str | None = None) -> dict:
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            headers = {"x-forwarded-for": client_ip} if client_ip else {}
            resp = await client.post(f"{CORE_API_URL}{path}", json=body, headers=headers)
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


# NOT: get_remote_address, uvicorn --proxy-headers ile nginx'in ilettiği
# X-Forwarded-For/X-Real-IP'yi request.client.host olarak çözer (bkz. Dockerfile
# CMD) — bu yüzden burada gerçek son kullanıcı IP'sini yansıtır, BFF container
# adresini değil. Bu IP hem burada rate-limit anahtarı olarak, hem de core-api'ye
# iletilerek core-api'nin kendi login rate-limit'inin tüm kullanıcılar arasında
# paylaşılan tek bir kotaya düşmesini önlemek için kullanılır.
@router.post("/register")
@limiter.limit("10/minute")
async def register(request: Request, body: RegisterRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/register", body.model_dump(), rid, get_remote_address(request))


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/login", body.model_dump(), rid, get_remote_address(request))


@router.post("/apple")
@limiter.limit("5/minute")
async def apple_sign_in(request: Request, body: AppleSignInRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/apple", body.model_dump(), rid, get_remote_address(request))


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


@router.put("/device-token")
async def register_device_token(
    request: Request,
    body: DeviceTokenRequest,
    user_id: int = Depends(get_current_user_id),
):
    """APNs device token'ını kaydeder — push bildirim gönderiminde kullanılacak."""
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(10.0) as client:
            resp = await client.put(
                f"{CORE_API_URL}/internal/auth/device-token",
                json={"token": body.token},
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return {"status": "ok"}
