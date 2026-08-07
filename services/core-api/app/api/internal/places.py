"""
Presentation katmanı — Place (kütüphane) route handler'ları.
Sadece: input al → service çağır → response döndür.
"""
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.application.services.place_service import PlaceService
from app.application.dto.place_dto import LibraryResponse
from app.infrastructure.repositories.sql_place_repository import SqlPlaceRepository

router = APIRouter(prefix="/internal/places", tags=["internal"])


def get_place_service(db: Session = Depends(get_db)) -> PlaceService:
    return PlaceService(SqlPlaceRepository(db))


@router.get("", response_model=LibraryResponse)
def get_library(
    city: Optional[str] = None,
    q: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    service: PlaceService = Depends(get_place_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """
    Kullanıcının tüm videolarından birikmiş, tekilleştirilmiş mekan
    kütüphanesi. goal.md Phase 7'deki "Library" ekranının backend'i —
    tek video değil, tüm zamanların kaydedilmiş mekanları.
    """
    if x_user_id is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Kimlik doğrulama gerekli."},
        )
    return service.get_library(x_user_id, city=city, q=q, category=category, limit=limit, offset=offset)
