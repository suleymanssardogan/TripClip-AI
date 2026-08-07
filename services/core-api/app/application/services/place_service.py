"""
Application katmanı — Place (kütüphane) iş mantığı.
"""
from typing import Optional

from app.domain.repositories.place_repository import AbstractPlaceRepository
from app.application.dto.place_dto import LibraryResponse, PlaceSummary


class PlaceService:

    def __init__(self, place_repo: AbstractPlaceRepository):
        self._repo = place_repo

    def get_library(
        self,
        user_id: int,
        city: Optional[str] = None,
        q: Optional[str] = None,
        category: Optional[str] = None,
        semantic: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> LibraryResponse:
        data = self._repo.get_library(
            user_id, city=city, q=q, category=category, semantic=semantic, limit=limit, offset=offset
        )
        places = [PlaceSummary(**p) for p in data["places"]]
        return LibraryResponse(places=places, total=data["total"])
