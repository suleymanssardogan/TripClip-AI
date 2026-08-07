"""
Domain katmanı — Place repository abstract interface.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class AbstractPlaceRepository(ABC):

    @abstractmethod
    def sync_from_video(self, video) -> None:
        """
        Bir video COMPLETED olduğunda, `deduplicated_locations` içindeki her
        mekanı videolar-arası Place kütüphanesine işler (bul-ya-da-oluştur +
        kullanıcı için PlaceSave). video.user_id yoksa hiçbir şey yapmaz.
        """
        ...

    @abstractmethod
    def get_library(
        self,
        user_id: int,
        city: Optional[str] = None,
        q: Optional[str] = None,
        category: Optional[str] = None,
        semantic: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Kullanıcının kaydettiği tüm mekanları döner (tüm videolarından
        birikmiş) — {"places": [...], "total": N}.
        """
        ...
