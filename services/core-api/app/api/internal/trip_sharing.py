"""
Presentation katmanı — Trip sharing (davet/collaborator) route handler'ları.
Sadece: input al → service çağır → response döndür.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.application.services.sharing_service import TripSharingService
from app.application.dto.sharing_dto import (
    CreateShareRequest,
    ShareResponse,
    ShareListResponse,
    SharePreviewResponse,
    AcceptShareRequest,
    AcceptShareResponse,
    DeclineShareRequest,
    CollaboratorListResponse,
)
from app.infrastructure.repositories.sql_sharing_repository import SqlSharingRepository

router = APIRouter(tags=["internal"])


def get_sharing_service(db: Session = Depends(get_db)) -> TripSharingService:
    return TripSharingService(SqlSharingRepository(db))


def _require_user(x_user_id: Optional[int]) -> int:
    if x_user_id is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Kimlik doğrulama gerekli."},
        )
    return x_user_id


# ── Owner: davet oluşturma / listeleme / iptal ────────────────────────────────

@router.post("/internal/trips/{trip_id}/shares", response_model=ShareResponse)
def create_share(
    trip_id: int,
    body: CreateShareRequest,
    service: TripSharingService = Depends(get_sharing_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """Yeni bir davet linki oluşturur. Yalnızca gezinin sahibi çağırabilir."""
    user_id = _require_user(x_user_id)
    return service.create_share(trip_id, user_id, body.role, body.expires_at, body.max_uses)


@router.get("/internal/trips/{trip_id}/shares", response_model=ShareListResponse)
def list_shares(
    trip_id: int,
    service: TripSharingService = Depends(get_sharing_service),
    x_user_id: Optional[int] = Header(default=None),
):
    user_id = _require_user(x_user_id)
    return service.list_shares(trip_id, user_id)


@router.post("/internal/trips/{trip_id}/shares/{share_id}/revoke")
def revoke_share(
    trip_id: int,
    share_id: int,
    service: TripSharingService = Depends(get_sharing_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """Daveti kalıcı olarak iptal eder — linki elinde bulunduran biri artık
    kabul/reddedemez, bu hemen etkili olur (bkz. spesifikasyonun
    "revoked links must stop working immediately" gereksinimi)."""
    user_id = _require_user(x_user_id)
    service.revoke_share(trip_id, share_id, user_id)
    return {"success": True}


# ── Davet alan taraf: önizleme / kabul / reddet (token ile, kimlik doğrulama
# önizlemede gerekmez, kabul/reddette gerekir) ────────────────────────────────

@router.get("/internal/shares/{token}/preview", response_model=SharePreviewResponse)
def preview_share(
    token: str,
    service: TripSharingService = Depends(get_sharing_service),
):
    """
    Kimlik doğrulama GEREKTİRMEZ — davet linkini açan biri kabul etmeden önce
    neyi kabul edeceğini (gezi başlığı, durak sayısı, verilecek rol) görebilir.
    """
    return service.preview_share(token)


@router.post("/internal/shares/accept", response_model=AcceptShareResponse)
def accept_share(
    body: AcceptShareRequest,
    service: TripSharingService = Depends(get_sharing_service),
    x_user_id: Optional[int] = Header(default=None),
):
    user_id = _require_user(x_user_id)
    return service.accept_share(body.token, user_id)


@router.post("/internal/shares/decline")
def decline_share(
    body: DeclineShareRequest,
    service: TripSharingService = Depends(get_sharing_service),
    x_user_id: Optional[int] = Header(default=None),
):
    user_id = _require_user(x_user_id)
    service.decline_share(body.token, user_id)
    return {"success": True}


# ── Collaborator yönetimi ─────────────────────────────────────────────────────

@router.get("/internal/trips/{trip_id}/collaborators", response_model=CollaboratorListResponse)
def list_collaborators(
    trip_id: int,
    service: TripSharingService = Depends(get_sharing_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """Owner VEYA herhangi bir collaborator kimin erişimi olduğunu görebilir."""
    user_id = _require_user(x_user_id)
    return service.list_collaborators(trip_id, user_id)


@router.delete("/internal/trips/{trip_id}/collaborators/{target_user_id}")
def remove_collaborator(
    trip_id: int,
    target_user_id: int,
    service: TripSharingService = Depends(get_sharing_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """Yalnızca gezinin sahibi bir collaborator'ı çıkarabilir."""
    user_id = _require_user(x_user_id)
    service.remove_collaborator(trip_id, target_user_id, user_id)
    return {"success": True}
