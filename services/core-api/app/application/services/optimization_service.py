"""
Application katmanı — Trip Optimizer iş mantığı.

Repository ve strateji DI ile enjekte edilir (repository test'te mock'lanabilir,
strateji registry üzerinden isimle çözülür) — bkz. trip_service.py/
sharing_service.py ile aynı desen.
"""
from datetime import date
from typing import Any, Dict, List

from app.domain.repositories.optimization_repository import AbstractOptimizationRepository
from app.domain.optimization.models import OptimizationConstraints
from app.application.dto.optimization_dto import (
    OptimizeTripRequest,
    OptimizeTripResponse,
    ItineraryListResponse,
    ItinerarySummaryResponse,
    ApplyItineraryResponse,
)
from app.infrastructure.optimization.strategy_registry import get_strategy, available_strategies
from app.core.exceptions import (
    TripNotFoundException,
    PermissionDeniedException,
    InvalidOptimizationRequestException,
    ItineraryNotFoundException,
)


def _to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _validate_hhmm(raw: str, field: str) -> None:
    try:
        h, m = raw.split(":")
        if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            raise ValueError
    except (ValueError, AttributeError):
        raise InvalidOptimizationRequestException(f"Geçersiz {field} biçimi: '{raw}'. 'HH:MM' olmalı.")


class OptimizationService:

    def __init__(self, repo: AbstractOptimizationRepository):
        self._repo = repo

    @staticmethod
    def _dedupe(place_ids: List[int]) -> tuple[List[int], int]:
        """Sırayı koruyarak tekilleştirir, kaç tanesinin kaldırıldığını döner
        (bkz. spesifikasyonun 'duplicate location removed' uyarı örneği)."""
        seen: set[int] = set()
        deduped: List[int] = []
        removed = 0
        for pid in place_ids:
            if pid in seen:
                removed += 1
                continue
            seen.add(pid)
            deduped.append(pid)
        return deduped, removed

    def optimize_trip(self, trip_id: int, user_id: int, request: OptimizeTripRequest) -> OptimizeTripResponse:
        access = self._repo.resolve_access(trip_id, user_id)
        if access is None:
            raise TripNotFoundException(trip_id)
        if access not in ("owner", "editor"):
            raise PermissionDeniedException(
                "Bu geziyi optimize etme yetkiniz yok — yalnızca sahibi ve editörler çalıştırabilir."
            )

        if not request.selected_place_ids:
            raise InvalidOptimizationRequestException("En az bir mekan seçmelisiniz.")

        deduped_ids, duplicates_removed = self._dedupe(request.selected_place_ids)

        if request.duration_days is not None and request.duration_days < 1:
            raise InvalidOptimizationRequestException("duration_days en az 1 olmalı.")

        _validate_hhmm(request.preferred_start_time, "preferred_start_time")
        _validate_hhmm(request.preferred_end_time, "preferred_end_time")
        if _to_minutes(request.preferred_end_time) <= _to_minutes(request.preferred_start_time):
            raise InvalidOptimizationRequestException(
                "preferred_end_time, preferred_start_time'dan sonra olmalı."
            )

        if request.start_date is not None:
            try:
                date.fromisoformat(request.start_date)
            except ValueError:
                raise InvalidOptimizationRequestException(
                    f"Geçersiz start_date biçimi: '{request.start_date}'. 'YYYY-MM-DD' olmalı."
                )

        try:
            strategy = get_strategy(request.strategy)
        except KeyError:
            raise InvalidOptimizationRequestException(
                f"Bilinmeyen strateji: '{request.strategy}'. "
                f"Geçerli seçenekler: {', '.join(available_strategies())}."
            )

        places = self._repo.get_owned_places(trip_id, deduped_ids)
        if places is None:
            raise InvalidOptimizationRequestException(
                "Seçilen mekanlardan biri veya birden fazlası kütüphanenizde bulunamadı."
            )

        constraints = OptimizationConstraints(
            start_date=request.start_date,
            duration_days=request.duration_days,
            preferred_start_time=request.preferred_start_time,
            preferred_end_time=request.preferred_end_time,
        )
        result = strategy.optimize(places, constraints)

        # Not: bu uyarı stratejinin optimization_score hesabından SONRA eklenir,
        # skora yansımaz — bkz. docs/trip-optimizer.md "Limitations". İstek
        # hijyeni (tekrar temizleme) ile rota kalitesi kasıtlı olarak ayrı
        # kaygılar; skor yalnızca ikincisini ölçer.
        if duplicates_removed:
            result.warnings.append(f"{duplicates_removed} tekrarlı mekan seçimi kaldırıldı.")

        params: Dict[str, Any] = request.model_dump()
        itinerary_id = self._repo.save_itinerary(trip_id, strategy.name, params, result)

        saved = self._repo.get_itinerary(itinerary_id, user_id)
        return OptimizeTripResponse(**saved)

    def list_itineraries(self, trip_id: int, user_id: int) -> ItineraryListResponse:
        rows = self._repo.list_itineraries(trip_id, user_id)
        if rows is None:
            raise TripNotFoundException(trip_id)
        return ItineraryListResponse(itineraries=[ItinerarySummaryResponse(**r) for r in rows])

    def get_itinerary(self, itinerary_id: int, user_id: int) -> OptimizeTripResponse:
        data = self._repo.get_itinerary(itinerary_id, user_id)
        if data is None:
            raise ItineraryNotFoundException(itinerary_id)
        return OptimizeTripResponse(**data)

    def apply_itinerary(self, itinerary_id: int, user_id: int) -> ApplyItineraryResponse:
        """bkz. docs/trip-optimizer.md 'Apply semantics' — REPLACE, atomik,
        TripItinerary/TripItineraryStop hiçbir zaman değişmez."""
        result = self._repo.apply_itinerary(itinerary_id, user_id)
        status = result["status"]

        if status == "not_found":
            raise ItineraryNotFoundException(itinerary_id)
        if status == "forbidden":
            raise PermissionDeniedException(
                "Bu geziyi düzenleme yetkiniz yok — yalnızca sahibi ve editörler itinerary uygulayabilir."
            )
        if status == "empty":
            raise InvalidOptimizationRequestException("Bu itinerary hiçbir durak içermiyor, uygulanamaz.")
        if status == "invalid_places":
            raise InvalidOptimizationRequestException(
                "Bu itinerary artık var olmayan (silinmiş) mekanlar içeriyor, uygulanamaz."
            )
        if status == "duplicate_places":
            raise InvalidOptimizationRequestException("Bu itinerary tekrarlı mekanlar içeriyor, uygulanamaz.")

        # Pydantic, list[TripStopDTO] alanı için ham dict listesini otomatik
        # coerce eder — get_itinerary'nin **data ile days'i inşa etmesiyle
        # aynı desen, tek tek TripStopDTO(...) sarmalamaya gerek yok. Alanlar
        # tek tek geçiriliyor (result["status"] burada bilerek dışarıda
        # bırakılıyor — ApplyItineraryResponse'ta karşılığı yok).
        return ApplyItineraryResponse(
            trip_id=result["trip_id"],
            itinerary_id=result["itinerary_id"],
            stops=result["stops"],
            stops_count=result["stops_count"],
            applied_at=result["applied_at"],
        )
