"""
Presentation katmanı — Trip Assistant route handler (M26). Sadece: input al
→ service çağır → response döndür (bkz. trip_optimization.py'nin AYNI ilkesi).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.application.dto.assistant_dto import AssistantRequestDTO, AssistantResponseDTO
from app.application.services.optimization_service import OptimizationService
from app.application.services.trip_assistant_service import TripAssistantService
from app.core.database import get_db
from app.infrastructure.repositories.sql_optimization_repository import SqlOptimizationRepository
from app.infrastructure.repositories.sql_trip_repository import SqlTripRepository
from app.ml.ai_provider import get_ai_provider

router = APIRouter(tags=["internal"])


def get_trip_assistant_service(db: Session = Depends(get_db)) -> TripAssistantService:
    return TripAssistantService(
        trip_repo=SqlTripRepository(db),
        optimization_service=OptimizationService(SqlOptimizationRepository(db)),
        provider=get_ai_provider(),
    )


def _require_user(x_user_id: Optional[int]) -> int:
    if x_user_id is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Kimlik doğrulama gerekli."},
        )
    return x_user_id


@router.post("/internal/trips/{trip_id}/assistant", response_model=AssistantResponseDTO)
def ask_trip_assistant(
    trip_id: int,
    body: AssistantRequestDTO,
    service: TripAssistantService = Depends(get_trip_assistant_service),
    x_user_id: Optional[int] = Header(default=None),
):
    """Trip'in gerçek durak/itinerary verisine GROUNDED, salt-okunur bir
    soru-cevap. Hiçbir trip/itinerary state'ini DEĞİŞTİRMEZ."""
    user_id = _require_user(x_user_id)
    return service.ask(trip_id, user_id, body.message, body.history)
