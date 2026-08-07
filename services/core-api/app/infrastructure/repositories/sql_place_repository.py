"""
Infrastructure katmanı — AbstractPlaceRepository'nin SQLAlchemy implementasyonu.
"""
import math
from typing import Optional, List, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.repositories.place_repository import AbstractPlaceRepository
from app.models.place import Place
from app.models.place_save import PlaceSave
from app.ml.location_deduplicator import normalize_place_name


class SqlPlaceRepository(AbstractPlaceRepository):

    # İki mekan bu yarıçapın içindeyse ve normalize edilmiş adları aynıysa
    # aynı Place sayılır. location_deduplicator'ın tek-video-içi eşiğinden
    # (5km) kasıtlı olarak daha dar: videolar arası birleştirmede yanlışlıkla
    # farklı iki mekanı tek Place'e toplamanın maliyeti (kullanıcının
    # kütüphanesinde bir yerin sessizce kaybolması) çok daha yüksek.
    MERGE_RADIUS_KM = 1.0
    # Kütüphane sayfalama üst sınırı — public feed ile aynı gerekçe
    # (sql_video_repository._MAX_PUBLIC_PAGE_SIZE): istemci limit=999999
    # gönderse bile amplification'ı önler.
    _MAX_PAGE_SIZE = 50

    def __init__(self, db: Session):
        self._db = db

    @staticmethod
    def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        R = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lng2 - lng1)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Nominatim address hierarchy: city > town > province > state — aynı
    # öncelik sırası video_processor._extract_city_hint'te de kullanılıyor
    # (oradaki çoğunluk-oyu / bölge ipucu için). Burada tek bir lokasyonun
    # kendi city'sini çıkarmak için aynı sıra tekrarlanıyor; iki yer de küçük
    # ve bağımsız kaldığı için ortak bir yardımcıya çıkarmak bu aşamada
    # gereksiz bir bağımlılık ekler (ML pipeline ↔ repository katmanı).
    _CITY_ADDRESS_KEYS = ("city", "town", "province", "state")

    @classmethod
    def _extract_city(cls, place_data: Dict[str, Any]) -> Optional[str]:
        addr = place_data.get("address_details") or {}
        for key in cls._CITY_ADDRESS_KEYS:
            if name := addr.get(key):
                return name
        return None

    def _find_or_create_place(
        self,
        name: str,
        lat: float,
        lng: float,
        city: Optional[str],
        address: Optional[str],
        first_seen_video_id: Optional[int],
    ) -> Place:
        name_key = normalize_place_name(name)

        # Aynı ada sahip adaylar arasından yarıçap içinde olanı ara. Aday
        # sayısı bir kullanıcının/şehrin aynı isimli mekan sayısıyla sınırlı
        # olduğundan (genelde tek haneli) Python'da mesafe hesaplamak burada
        # sorun değil — location_deduplicator da aynı yaklaşımı kullanıyor.
        candidates = self._db.query(Place).filter(Place.name_key == name_key).all()
        for candidate in candidates:
            if self._haversine_km(lat, lng, candidate.lat, candidate.lng) <= self.MERGE_RADIUS_KM:
                # Daha önce city çözülememiş bir kayıt, şimdi elimizdeki
                # bilgiyle zenginleşebilir — backfill'i tekrar çalıştırmak
                # eski kayıtları da bu şekilde tamamlıyor.
                if not candidate.city and city:
                    candidate.city = city
                return candidate

        place = Place(
            name=name,
            name_key=name_key,
            lat=lat,
            lng=lng,
            city=city,
            address=address,
            first_seen_video_id=first_seen_video_id,
            save_count=0,
        )
        self._db.add(place)
        self._db.flush()  # id lazım (PlaceSave FK'ı için), henüz commit etme
        return place

    def _save_for_user(self, user_id: int, place: Place, video_id: Optional[int]) -> None:
        existing = (
            self._db.query(PlaceSave)
            .filter(PlaceSave.user_id == user_id, PlaceSave.place_id == place.id)
            .first()
        )
        if existing:
            # Kullanıcı bu mekanı zaten kaydetmiş (başka bir videodan) —
            # tekrar saymıyoruz, save_count kullanıcı başına en fazla 1 artar.
            return

        self._db.add(PlaceSave(user_id=user_id, place_id=place.id, video_id=video_id))
        place.save_count = (place.save_count or 0) + 1

    def sync_from_video(self, video) -> None:
        if not video.user_id:
            return

        locations = video.deduplicated_locations or []
        for loc in locations:
            place_data = loc.get("place_data") or {}
            coords = place_data.get("location") or {}
            lat, lng = coords.get("lat"), coords.get("lng")
            name = loc.get("original_name") or place_data.get("name")

            if not name or lat is None or lng is None:
                continue

            place = self._find_or_create_place(
                name=name,
                lat=float(lat),
                lng=float(lng),
                city=self._extract_city(place_data),
                address=place_data.get("address"),
                first_seen_video_id=video.id,
            )
            self._save_for_user(user_id=video.user_id, place=place, video_id=video.id)

        self._db.commit()

    @staticmethod
    def _to_summary(place: Place, saved_at) -> Dict[str, Any]:
        return {
            "id": place.id,
            "name": place.name,
            "lat": place.lat,
            "lng": place.lng,
            "city": place.city,
            "address": place.address,
            "category": place.category,
            "save_count": place.save_count,
            "saved_at": saved_at.isoformat() if saved_at else None,
        }

    def get_library(
        self,
        user_id: int,
        city: Optional[str] = None,
        q: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        limit = max(1, min(limit, self._MAX_PAGE_SIZE))
        offset = max(0, offset)

        query = (
            self._db.query(Place, PlaceSave.saved_at)
            .join(PlaceSave, PlaceSave.place_id == Place.id)
            .filter(PlaceSave.user_id == user_id)
        )
        if city:
            query = query.filter(Place.city.ilike(f"%{city}%"))
        if q:
            query = query.filter(Place.name.ilike(f"%{q}%"))

        total = query.with_entities(func.count(Place.id)).scalar()
        rows = (
            query.order_by(PlaceSave.saved_at.desc())
            .offset(offset).limit(limit)
            .all()
        )
        return {
            "places": [self._to_summary(place, saved_at) for place, saved_at in rows],
            "total": total,
        }
