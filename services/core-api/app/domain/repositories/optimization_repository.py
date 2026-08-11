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

    @abstractmethod
    def apply_itinerary(self, itinerary_id: int, user_id: int) -> Dict[str, Any]:
        """
        Kayıtlı bir itinerary'i Trip'in kanonik TripStop listesine uygular
        (REPLACE semantiği — bkz. docs/trip-optimizer.md "Apply semantics").
        TripItinerary/TripItineraryStop'a ASLA yazmaz, yalnızca okur — aynı
        itinerary güvenle tekrar tekrar uygulanabilir.

        Döner: {"status": "ok", ...} ya da
        {"status": "not_found" | "forbidden" | "empty" | "invalid_places" | "duplicate_places"}.
        """
        ...

    @abstractmethod
    def delete_itinerary(self, itinerary_id: int, user_id: int) -> str:
        """
        Bir itinerary'i VE onun TripItineraryStop çocuklarını kalıcı olarak
        siler — TripStop'a (Trip'in kanonik durak listesi) ve Place'e HİÇ
        dokunmaz, aynı trip'in başka itinerary'lerini de etkilemez (bkz.
        docs/trip-optimizer.md "Delete Saved Itinerary"). Bu itinerary
        Trip.applied_itinerary_id tarafından referanslanıyorsa o referans
        güvenle temizlenir (dangling FK bırakılmaz).

        Döner: "ok" | "not_found" | "forbidden" — apply_itinerary ile AYNI
        durum sözlüğü (kasıtlı tutarlılık), ama çağıran servis (bkz.
        OptimizationService.delete_itinerary) "forbidden"ı apply'ın aksine
        403'e DEĞİL 404'e çevirir — silme, anti-enumeration açısından
        okumadan/uygulamadan daha sıkı: bir itinerary'nin var olup olmadığı,
        ona owner/editor erişimi olmayan hiç kimseye (viewer dahil)
        sızdırılmaz.
        """
        ...

    @abstractmethod
    def list_apply_history(self, trip_id: int, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        Bu trip'in TÜM apply/undo geçmişi, en yeniden eskiye — bkz.
        docs/trip-optimizer.md "Apply History & Undo". `list_itineraries`
        ile AYNI erişim semantiği: trip yoksa ya da hiç erişim yoksa (viewer
        dahil ERİŞİMİ olan HERKES okuyabilir — bu bir OKUMA, mutasyon değil)
        None; aksi halde liste (boş olabilir).
        """
        ...

    @abstractmethod
    def undo_apply_history(self, trip_id: int, history_id: int, user_id: int) -> Dict[str, Any]:
        """
        Belirtilen apply-history kaydının `previous_stops`/`previous_itinerary_id`
        anlık görüntüsünü TripStop'a geri yükler — yalnızca bu trip'in EN SON
        apply-history kaydıysa (bkz. docs/trip-optimizer.md "Apply History &
        Undo → Latest-only safety rule"). Kendi başarılı sonucu için YENİ bir
        apply-history kaydı (`is_undo=True`) oluşturur — geri alma işleminin
        kendisi de (yalnızca en sonuncuysa) geri alınabilir.

        Kaydedilmiş TripItinerary'e ASLA yazmaz.

        Döner: {"status": "ok", ...} ya da
        {"status": "trip_not_found" | "forbidden" | "history_not_found" | "stale" | "invalid_places"}.
        "forbidden" apply_itinerary'nin kendi konvansiyonunu izler (403) —
        delete_itinerary'nin ekstra-sıkı anti-enumeration'ı BURAYA
        uygulanmadı, çünkü undo kavramsal olarak apply'ın bir varyantı
        (aynı owner/editor mutasyon yetkisi).
        """
        ...
