"""
Application katmanı — Trip iş mantığı.
Repository DI ile enjekte edilir → test ortamında kolayca mock'lanır.
"""
from typing import List

from app.domain.repositories.trip_repository import AbstractTripRepository
from app.application.dto.trip_dto import (
    TripDetailResponse,
    TripSummaryResponse,
    TripListResponse,
)
from app.core.exceptions import (
    TripNotFoundException,
    InvalidTripPlacesException,
    InvalidTripStopOrderException,
    PermissionDeniedException,
)


class TripService:

    def __init__(self, trip_repo: AbstractTripRepository):
        self._repo = trip_repo

    def create_trip(self, user_id: int, title: str, place_ids: List[int]) -> TripDetailResponse:
        if not place_ids:
            raise InvalidTripPlacesException("En az bir mekan seçmelisiniz.")
        if len(place_ids) != len(set(place_ids)):
            raise InvalidTripPlacesException("Aynı mekan birden fazla kez seçilemez.")

        trip = self._repo.create_trip(user_id, title.strip() or "Yeni Gezi", place_ids)
        if trip is None:
            raise InvalidTripPlacesException(
                "Seçilen mekanlardan biri veya birden fazlası kütüphanenizde bulunamadı."
            )
        return TripDetailResponse(**trip)

    def get_trip(self, trip_id: int, user_id: int) -> TripDetailResponse:
        trip = self._repo.get_trip(trip_id, user_id)
        if trip is None:
            raise TripNotFoundException(trip_id)
        return TripDetailResponse(**trip)

    def list_trips(self, user_id: int) -> TripListResponse:
        trips = self._repo.list_trips(user_id)
        return TripListResponse(trips=[TripSummaryResponse(**t) for t in trips])

    def update_stop_order(self, trip_id: int, user_id: int, order: List[List[int]]) -> None:
        """
        `order` hem sıralamayı hem hangi durakların kalacağını belirler — Video'nun
        stop_order doğrulamasıyla aynı gerekçe (bkz. VideoService.update_stop_order).
        """
        current = self._repo.get_trip(trip_id, user_id)
        if current is None:
            raise TripNotFoundException(trip_id)

        valid_ids = {stop["place_id"] for day in current["days"] for stop in day}
        flat = [place_id for day in order for place_id in day]

        unknown = sorted(set(flat) - valid_ids)
        if unknown:
            raise InvalidTripStopOrderException(f"Geçersiz mekan id'si: {unknown}.")
        if len(flat) != len(set(flat)):
            raise InvalidTripStopOrderException("Aynı mekan birden fazla kez sıralanamaz.")

        result = self._repo.update_stop_order(trip_id, user_id, order)
        if result == "forbidden":
            raise PermissionDeniedException("Bu geziyi düzenleme yetkiniz yok — yalnızca sahibi ve editörler düzenleyebilir.")
        # 'not_found' burada pratikte olmaz: current = get_trip zaten yukarıda
        # None kontrolü yaptı, ama savunmacı olarak yine de kontrol ediyoruz.
        if result == "not_found":
            raise TripNotFoundException(trip_id)

    def delete_trip(self, trip_id: int, user_id: int) -> None:
        result = self._repo.delete_trip(trip_id, user_id)
        if result == "not_found":
            raise TripNotFoundException(trip_id)
        if result == "forbidden":
            raise PermissionDeniedException("Bu geziyi yalnızca sahibi silebilir.")
