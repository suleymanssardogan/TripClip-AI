"""
Web BFF — Trip sharing (davet) route handler'ları.

Web'in rolü yalnızca davet ALAN taraf: önizleme (anonim) + kabul/reddet
(giriş gerektirir). Davet OLUŞTURMA/collaborator yönetimi iOS'ta — web
"görüntüleme/paylaşım" katmanı, "yazma/yönetim" değil (bkz. CLAUDE.md
"Web upload deprecated" kararıyla aynı ilke).
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
import os
import uuid
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.internal_client import internal_client
from app.core.auth import get_current_user_id
from app.core.error_wrapper import web_error_wrapper, raise_from_response

limiter      = Limiter(key_func=get_remote_address)
router       = APIRouter(prefix="/shares", tags=["trip_sharing"])
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")


class TokenRequest(BaseModel):
    token: str


@router.get("/{token}/preview")
@limiter.limit("30/minute")
async def preview_share(
    request: Request,
    token: str,
):
    """Kimlik doğrulama gerekmez — /invite/[token] sayfası kabul etmeden
    önce neyin kabul edileceğini gösterir."""
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(10.0) as client:
            resp = await client.get(f"{CORE_API_URL}/internal/shares/{token}/preview")
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.post("/accept")
@limiter.limit("20/minute")
async def accept_share(
    request: Request,
    body: TokenRequest,
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/shares/accept",
                json={"token": body.token},
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


@router.post("/decline")
@limiter.limit("20/minute")
async def decline_share(
    request: Request,
    body: TokenRequest,
    user_id: int = Depends(get_current_user_id),
):
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.post(
                f"{CORE_API_URL}/internal/shares/decline",
                json={"token": body.token},
                headers={"x-user-id": str(user_id)},
            )
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return {"success": True}
