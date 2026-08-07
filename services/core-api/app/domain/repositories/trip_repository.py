"""
Domain katmanı — Trip repository abstract interface.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class AbstractTripRepository(ABC):

    @abstractmethod
    def create_trip(self, user_id: int, title: str, place_ids: List[int]) -> Optional[Dict[str, Any]]:
        """
        Verilen Place id'lerinden (kullanıcının kendi kütüphanesine ait olmalı)
        TSP ile rotalanmış yeni bir Trip oluşturur. Herhangi bir id kullanıcıya
        ait değilse None döner.
        """
        ...

    @abstractmethod
    def get_trip(self, trip_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Trip yoksa veya sahibi değilse None döner."""
        ...

    @abstractmethod
    def list_trips(self, user_id: int) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def update_stop_order(self, trip_id: int, user_id: int, order: List[List[int]]) -> bool:
        """
        `order`: gün başına place_id listesi. Trip yoksa/sahibi değilse False.
        """
        ...

    @abstractmethod
    def delete_trip(self, trip_id: int, user_id: int) -> bool:
        ...
