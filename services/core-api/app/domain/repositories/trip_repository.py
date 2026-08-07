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
    def resolve_access(self, trip_id: int, user_id: int) -> Optional[str]:
        """
        Kullanıcının bu trip'teki erişim seviyesini döner: 'owner' | 'editor' |
        'viewer' | None (trip yok ya da hiçbir ilişkisi yok). Her erişim
        kontrolünün tek doğru kaynağı — get_trip/update_stop_order/delete_trip
        hepsi bunun üzerine kurulu.
        """
        ...

    @abstractmethod
    def get_trip(self, trip_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Trip yoksa veya hiçbir erişimi (owner/editor/viewer) yoksa None döner."""
        ...

    @abstractmethod
    def list_trips(self, user_id: int) -> List[Dict[str, Any]]:
        """Kullanıcının sahip olduğu VE collaborator olarak eklendiği tüm trip'ler."""
        ...

    @abstractmethod
    def update_stop_order(self, trip_id: int, user_id: int, order: List[List[int]]) -> str:
        """
        `order`: gün başına place_id listesi. Döner: 'ok' | 'not_found' | 'forbidden'
        ('forbidden' = trip var ve görebiliyor ama owner/editor değil, yalnızca viewer).
        """
        ...

    @abstractmethod
    def delete_trip(self, trip_id: int, user_id: int) -> str:
        """Yalnızca owner silebilir. Döner: 'ok' | 'not_found' | 'forbidden'."""
        ...
