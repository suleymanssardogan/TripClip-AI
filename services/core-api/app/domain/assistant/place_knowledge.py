"""
Domain katmanı — Trip Assistant RAG (M30) için retrieval soyutlaması.

`context_builder.py`'nin AYNI ilkesi: saf dataclass/arayüz, DB/HTTP/Qdrant'a
hiç DOKUNMAZ. Gerçek implementasyon (`SqlPlaceKnowledgeRetriever`) altyapı
katmanında yaşar — bkz. app/infrastructure/repositories/sql_place_knowledge_retriever.py.

Milestone'un kendi örneği `async def retrieve(...)` kullanan bir `Protocol`
öneriyordu ("conceptually") — ama bu repodaki HER şey (FastAPI route'ları,
SQLAlchemy session'ı, AIProvider.answer, mevcut repository arayüzleri) baştan
sona SENKRON. Yeni bir async sınır açmak `TripAssistantService.ask()`'i ve
onu çağıran route'u da async'e çevirmeyi gerektirir — bu milestone'un kapsamı
dışında bir zincirleme değişiklik. Bunun yerine `AbstractTripRepository`/
`AIProvider` ile AYNI konvansiyon (senkron ABC) kullanıldı.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.assistant.context_builder import TripContext


@dataclass
class RetrievedPlaceKnowledge:
    """Qdrant'tan gelen ham `ScoredPoint`'in DIŞARI SIZMAYAN, yapılandırılmış
    karşılığı — bkz. milestone Req 3 "Do not expose Qdrant-specific objects
    outside the retrieval layer."

    `content`, Place tablosunun GERÇEKTEN sahip olduğu alanlardan (category/
    city/address/opening_hours — M31'de eklendi, bkz.
    `SqlPlaceKnowledgeRetriever._bounded_content`) üretilir — bu tabloda
    anlatı biçiminde bir "açıklama"/"tarihçe" alanı YOK (bkz.
    `app/models/place.py`). Yani RAG burada "yapılandırılmış mekan
    gerçeklerini getiriyor", Wikipedia tarzı anlatı metni İCAT ETMİYOR —
    bu dürüstçe `docs/trip-assistant.md`'de belgelenir.

    M31'de tüm repo'da "description/about/summary/content/history" gibi
    alanlar arandı: tek gerçek bulgu `Video.travel_tips[].tips[].tip`
    (Gemini/Ollama'nın video işleme sırasında ürettiği, 1-2 cümlelik
    kısa ipucu metni) idi — ama BİLEREK buraya BAĞLANMADI: (1) bir
    `place_id` FK'ı YOK, yalnızca serbest metin `location` adıyla
    eşleşiyor (yanlış eşleşme riski — aynı isimli farklı bir mekana
    ait ipucu yanlışlıkla eklenebilir), (2) video-işleme aşaması
    best-effort/opsiyonel, güvenilir şekilde dolu DEĞİL, (3) bağlamak
    retrieved place başına EK bir Video sorgusu gerektirir — M30'un
    "tek bağlı retrieval işlemi" performans garantisini BOZAR. Bu üçü
    birlikte, milestone'un kendi "do not invent a new external knowledge
    source/pipeline" kısıtına girer — bu yüzden BİLİNÇLİ OLARAK
    yapılmadı, unutulmadı."""
    place_id: int
    title: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Modele gönderilen (system prompt içindeki) minimal şekil —
        `score`/`metadata` LLM'e ANLAMSIZ/gereksiz olduğu için DIŞARIDA
        bırakılır (bkz. TripAssistantService._build_system_prompt)."""
        return {"place_id": self.place_id, "title": self.title, "content": self.content}


class PlaceKnowledgeRetriever(ABC):
    """Sağlayıcı-agnostik retrieval arayüzü — `AIProvider`'ın AYNI ilkesi:
    `TripAssistantService` Qdrant/embedding/SQL'in VARLIĞINDAN bile haberdar
    değildir, yalnızca bu arayüzü çağırır (bkz. milestone Req 11 "Provider
    Independence")."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        trip_context: Optional["TripContext"] = None,
        limit: int = 4,
    ) -> List[RetrievedPlaceKnowledge]:
        """`query`: kullanıcının sorusu (retrieval'ı TETİKLEYEN metin —
        bkz. `retrieval_heuristic.should_retrieve_place_knowledge`, bu
        kararı VERMEZ, yalnızca çağrıldığında gerçek bir arama yapar).
        `trip_context`: verilirse, gezinin kendi duraklarının
        kimliği/şehri arama kalitesini ve aday havuzunu iyileştirmek için
        kullanılır (bkz. milestone Req 6 "Trip-Aware Retrieval") — ama
        gezinin TAMAMI Qdrant'a KOPYALANMAZ, yalnızca çalışma zamanında
        okunur.

        Başarısızlıkta (Qdrant erişilemez, timeout, sonuç yok) boş liste
        döner, ASLA fırlatmaz — çağıran taraf (`TripAssistantService`)
        bunu "RAG yok, Trip Context'le devam" olarak ele alır, asistanı
        `ASSISTANT_UNAVAILABLE` yapmaz (bkz. milestone Req 13)."""
        ...
