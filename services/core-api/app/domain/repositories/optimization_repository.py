"""
Domain katmanı — Trip Optimizer persistence arayüzü.

SqlTripRepository/SqlSharingRepository ile aynı desen: erişim kontrolü
(`resolve_access`) ile veri okuma/yazma ayrı metodlara bölünmüş, DI ile
OptimizationService'e enjekte edilir.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from app.domain.optimization.models import PlaceInput, OptimizationResult


class AbstractOptimizationRepository(ABC):

    @abstractmethod
    def resolve_access(self, trip_id: int, user_id: int) -> Optional[str]:
        """'owner' | 'editor' | 'viewer' | None — SqlTripRepository.resolve_access ile
        aynı semantik (bilinçli küçük kod tekrarı: iki repository birbirine
        bağımlı olmasın diye, bkz. docs/trip-optimizer.md "Architecture")."""
        ...

    @abstractmethod
    def get_owned_places(self, trip_id: int, place_ids: List[int]) -> Optional[List[PlaceInput]]:
        """
        Trip sahibinin Library'sindeki (PlaceSave ile) Place'lerden, verilen
        id'lere karşılık gelenleri `place_ids` sırasıyla döner. `place_ids`
        içindeki herhangi bir id sahibinin kütüphanesinde yoksa (ya da Place
        hiç yoksa) None döner — SqlTripRepository._owned_places ile aynı
        "hepsi ya da hiçbiri" davranışı.
        """
        ...

    @abstractmethod
    def save_itinerary(
        self,
        trip_id: int,
        strategy_name: str,
        params: Dict[str, Any],
        result: OptimizationResult,
    ) -> int:
        """Üretilen itinerary'i kalıcı hale getirir, yeni itinerary_id döner."""
        ...

    @abstractmethod
    def get_itinerary(self, itinerary_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Itinerary yoksa ya da kullanıcının bağlı olduğu trip'e hiç erişimi yoksa None."""
        ...

    @abstractmethod
    def list_itineraries(self, trip_id: int, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """Trip yoksa ya da erişim yoksa None; aksi halde en yeniden eskiye özet liste."""
        ...
