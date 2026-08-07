"""
Mobile BFF — Trip sharing (davet/collaborator) route handler'ları.
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional
import os
import uuid
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.internal_client import internal_client
from app.core.auth import get_current_user_id
from app.core.error_wrapper import mobile_error_wrapper, raise_from_response

limiter      = Limiter(key_func=get_remote_address)
router       = APIRouter(tags=["trip_sharing"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


class CreateShareRequest(BaseModel):
    role: str
    expires_at: Optional[str] = None
    max_uses: Optional[int] = None


class TokenRequest(BaseModel):
    token: str


# ── Owner: davet oluşturma / listeleme / iptal ────────────────────────────────

@router.post("/trips/{trip_id}/shares")
async def create_share(
    trip_id: int,
    body: CreateShareRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Yeni bir davet linki oluşturur. Yalnızca gezinin sahibi çağırabilir."""
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/trips/{trip_id}/shares",
                json={"role": body.role, "expires_at": body.expires_at, "max_uses": body.max_uses},
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.get("/trips/{trip_id}/shares")
async def list_shares(
    trip_id: int,
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(
                f"{CORE_API_URL}/internal/trips/{trip_id}/shares",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.post("/trips/{trip_id}/shares/{share_id}/revoke")
async def revoke_share(
    trip_id: int,
    share_id: int,
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/trips/{trip_id}/shares/{share_id}/revoke",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return {"success": True}


# ── Davet alan taraf: önizleme / kabul / reddet ──────────────────────────────
#
# Rate limit: bu üçü token'ı kimlik doğrulama olmadan (preview) ya da düşük
# sürtünmeli bir kimlikle (accept/decline) doğrudan alıyor — token tahmin
# etmeye çalışan bir otomasyona karşı ek bir savunma katmanı (256 bit
# entropi zaten pratikte kaba kuvveti imkansız kılıyor, ama ucuz bir önlem).

@router.get("/shares/{token}/preview")
@limiter.limit("30/minute")
async def preview_share(
    request: Request,
    token: str,
):
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(10.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/shares/{token}/preview")
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.post("/shares/accept")
@limiter.limit("20/minute")
async def accept_share(
    request: Request,
    body: TokenRequest,
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/shares/accept",
                json={"token": body.token},
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.post("/shares/decline")
@limiter.limit("20/minute")
async def decline_share(
    request: Request,
    body: TokenRequest,
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/shares/decline",
                json={"token": body.token},
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return {"success": True}


# ── Collaborator yönetimi ─────────────────────────────────────────────────────

@router.get("/trips/{trip_id}/collaborators")
async def list_collaborators(
    trip_id: int,
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.get(
                f"{CORE_API_URL}/internal/trips/{trip_id}/collaborators",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.delete("/trips/{trip_id}/collaborators/{target_user_id}")
async def remove_collaborator(
    trip_id: int,
    target_user_id: int,
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with mobile_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.delete(
                f"{CORE_API_URL}/internal/trips/{trip_id}/collaborators/{target_user_id}",
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return {"success": True}
