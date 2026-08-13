"""
Infrastructure katmanı — `PlaceKnowledgeRetriever`'ın SQLAlchemy + Qdrant
implementasyonu (M30, Trip Assistant RAG).

`SqlPlaceRepository`'nin AYNI deseni: bir SQLAlchemy `Session` VE bir
`QdrantService` enjekte edilir (test'te ikisi de sahte/mock'lanabilir).
VAR OLAN Qdrant koleksiyonunu ("places", all-MiniLM-L6-v2, `search_places` —
bkz. app/ml/qdrant_service.py M30 eklentisi) kullanır — YENİ bir koleksiyon,
istemci ya da embedding modeli İCAT EDİLMEZ (bkz. milestone Req 4).
"""
import logging
from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.domain.assistant.context_builder import TripContext
from app.domain.assistant.place_knowledge import PlaceKnowledgeRetriever, RetrievedPlaceKnowledge
from app.ml.qdrant_service import QdrantService
from app.models.place import Place

logger = logging.getLogger(__name__)


class SqlPlaceKnowledgeRetriever(PlaceKnowledgeRetriever):

    # Milestone Req 7 "explicit bounded limits" — `MAX_HISTORY_TURNS`/
    # `MAX_HISTORY_MESSAGE_LENGTH`'in (trip_assistant_service.py, M27) AYNI
    # deseni: iki bağımsız sınırın ÇARPIMI toplam boyutu zaten sınırlar,
    # ayrı bir "toplam karakter" sayacı GEREKMEZ.
    MAX_CONTENT_LENGTH = 300
    # Aday havuzu — trip'in KENDİ duraklarının ÖTESİNDE, aynı şehirdeki
    # diğer Place'leri ne kadar genişçe tarayacağımızın üst sınırı (bkz.
    # SqlPlaceRepository._MAX_PAGE_SIZE'ın AYNI "amplification'ı önle"
    # gerekçesi) — Qdrant'a giden filtre listesinin BOYUTU, sonuç sayısı
    # DEĞİL (o zaten `limit` ile ayrıca sınırlı).
    CANDIDATE_POOL_LIMIT = 100

    def __init__(self, db: Session, qdrant: Optional[QdrantService] = None):
        self._db = db
        self._qdrant = qdrant or QdrantService()

    def retrieve(
        self, query: str, trip_context: Optional[TripContext] = None, limit: int = 4,
    ) -> List[RetrievedPlaceKnowledge]:
        candidate_ids = self._candidate_place_ids(trip_context)
        if not candidate_ids:
            return []

        search_text = self._build_search_text(query, trip_context)

        try:
            hits = self._qdrant.search_places(search_text, candidate_ids, limit=limit)
        except Exception as exc:
            # QdrantService._search zaten kendi içinde try/except'li (best-
            # effort) — bu ikinci katman yalnızca beklenmedik bir Python
            # hatasına (ör. SQL tarafı) karşı savunma, "RAG yok" davranışı
            # ASSISTANT_UNAVAILABLE'a asla dönüşmemeli (bkz. milestone Req 13).
            logger.warning("Place knowledge retrieval başarısız (arama): %s", type(exc).__name__)
            return []

        if not hits:
            return []

        place_ids = [h["place_id"] for h in hits]
        places_by_id = {p.id: p for p in self._db.query(Place).filter(Place.id.in_(place_ids)).all()}

        results: List[RetrievedPlaceKnowledge] = []
        for hit in hits:
            place = places_by_id.get(hit["place_id"])
            if place is None:
                # Qdrant point'i var ama Postgres kaydı silinmiş/tutarsız —
                # sessizce atla, halüsinasyon üretme (bkz. context_builder'ın
                # AYNI "silinmiş mekan" ilkesi).
                continue
            results.append(RetrievedPlaceKnowledge(
                place_id=place.id,
                title=place.name,
                content=self._bounded_content(place),
                score=hit["score"],
                metadata={"city": place.city, "category": place.category, "opening_hours": place.opening_hours},
            ))
        return results

    def _candidate_place_ids(self, trip_context: Optional[TripContext]) -> List[int]:
        """Qdrant'a verilecek `place_ids` filtresi — iki kaynağın BİRLEŞİMİ:
        (1) trip'in kendi durakları (ör. "Zeugma Müzesi hakkında..." — Zeugma
        zaten trip'te), (2) aynı şehir(ler)deki DİĞER Place'ler (ör. "yakın
        başka tarihi yerler" — trip'te OLMAYAN bir mekan). Trip'in TAMAMI
        Qdrant'a kopyalanmaz (bkz. milestone Req 6) — bu yalnızca çalışma
        zamanında, bir SQL sorgusuyla kurulan geçici bir aday listesi."""
        if trip_context is None:
            return []

        candidate_ids = set(trip_context.all_stop_place_ids)

        cities = trip_context.all_cities
        if cities:
            city_filters = [Place.city.ilike(f"%{c}%") for c in cities]
            rows = (
                self._db.query(Place.id)
                .filter(or_(*city_filters))
                .limit(self.CANDIDATE_POOL_LIMIT)
                .all()
            )
            candidate_ids.update(r[0] for r in rows)

        return list(candidate_ids)

    @staticmethod
    def _build_search_text(query: str, trip_context: Optional[TripContext]) -> str:
        """Trip-aware retrieval (milestone Req 6): trip'in durak adlarını
        arama metnine EKLER, böylece "Bunlardan hangisi Roma tarihi
        açısından önemli?" gibi zamir içeren sorular da anlamsal olarak
        gezinin gerçek mekanlarına ÇAPALANIR — kullanıcının HAM mesajı tek
        başına bu bağlamı taşımaz."""
        if trip_context is None:
            return query
        names = [s.name for d in trip_context.days for s in d.stops]
        if not names:
            return query
        return f"{query} ({', '.join(names)})"

    @classmethod
    def _bounded_content(cls, place: Place) -> str:
        """Place'in GERÇEKTEN sahip olduğu alanlardan (bkz.
        RetrievedPlaceKnowledge'ın kendi doc yorumu — anlatı/açıklama alanı
        YOK) kısa, sınırlı bir metin üretir.

        M31: `opening_hours` de eklendi — Place'in ZATEN VAR OLAN (ve
        optimizer tarafından ZATEN okunan, bkz. greedy_distance_strategy.py/
        ortools_strategy.py) bir kolonu, ama M30'a kadar asistana hiç
        SIZMIYORDU. Bugün prod'da neredeyse her zaman `None` (hiçbir
        pipeline doldurmuyor — bkz. RetrievedPlaceKnowledge'ın doc yorumu),
        bu yüzden pratik etkisi bugün SIFIR, ama bir pipeline bunu
        doldurmaya başladığında BEDAVA çalışmaya başlar — yeni bir sorgu,
        yeni bir alan, yeni bir milestone GEREKMEZ."""
        parts = [p for p in (place.category, place.city, place.address) if p]
        if place.opening_hours:
            parts.append(f"açılış saatleri: {place.opening_hours}")
        content = ", ".join(parts) if parts else "Bu mekan için ek bilgi mevcut değil."
        if len(content) <= cls.MAX_CONTENT_LENGTH:
            return content
        return content[:cls.MAX_CONTENT_LENGTH] + "…"
