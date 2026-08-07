"""
Qdrant — Place kütüphanesi için anlamsal (semantic) arama.

Videolar-arası, tekilleştirilmiş `Place` tablosu tek doğru kaynak olduğu için
embedding de Place seviyesinde tutulur (bkz. SqlPlaceRepository): her Place
tam olarak bir Qdrant point'i, point id place_id — bu yüzden bir Place'in
adı/şehri/kategorisi zenginleştiğinde yeniden upsert etmek doğal biçimde
idempotent'tir, eski kayıt sessizce üzerine yazılır.

Tamamen opsiyonel altyapı: Qdrant'a erişilemezse (bağlantı hatası, servis
ayakta değil) tüm metodlar sessizce boş/None döner — arayan taraf
(SqlPlaceRepository) normal substring aramasına düşer. Aynı "yalnızca
mevcutsa aktif" felsefesi SENTRY_DSN ve APNs istemcisiyle paylaşılıyor.
"""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchAny
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class QdrantService:
    """Place embedding'leri için Qdrant vektör veritabanı istemcisi."""

    def __init__(self):
        self.client = None
        self.model = None
        self.collection_name = "places"
        self.vector_size = 384  # all-MiniLM-L6-v2 çıktı boyutu
        self._collection_ready = False
        logger.info("QdrantService initialized (lazy loading)")

    def _load(self):
        """Qdrant istemcisini ve embedding modelini tembel yükler."""
        if self.client is None:
            logger.info("Connecting to Qdrant...")
            self.client = QdrantClient(host="qdrant", port=6333)
            logger.info("✅ Qdrant connected")

        if self.model is None:
            logger.info("Loading sentence transformer model...")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("✅ Sentence transformer loaded")

    def _ensure_collection(self):
        """Koleksiyonun var olduğundan emin olur — süreç başına en fazla bir kez kontrol eder."""
        if self._collection_ready:
            return

        collections = self.client.get_collections().collections
        names = [c.name for c in collections]

        if self.collection_name not in names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
            logger.info(f"✅ Collection '{self.collection_name}' created")

        self._collection_ready = True

    @staticmethod
    def _embedding_text(name: str, city: Optional[str], category: Optional[str]) -> str:
        return ", ".join(part for part in (name, city, category) if part)

    def upsert_place(
        self,
        place_id: int,
        name: str,
        city: Optional[str] = None,
        category: Optional[str] = None,
    ) -> None:
        """
        Bir Place'i embed edip Qdrant'a yazar. Hata durumunda (Qdrant erişilemez
        vb.) sessizce loglar ve döner — çağıran tarafın (Place senkronizasyonu)
        bu adıma bağımlı olmaması gerekir, tıpkı push bildirimi gibi best-effort.
        """
        try:
            self._load()
            self._ensure_collection()

            text = self._embedding_text(name, city, category)
            vector = self.model.encode(text).tolist()

            point = PointStruct(
                id=place_id,
                vector=vector,
                payload={"place_id": place_id, "name": name, "city": city, "category": category},
            )
            self.client.upsert(collection_name=self.collection_name, points=[point])
        except Exception as exc:
            logger.warning("Qdrant place embed başarısız | place_id=%s | %s", place_id, exc)

    def search_place_ids(self, query: str, place_ids: List[int], limit: int = 20) -> List[int]:
        """
        `place_ids` kümesiyle sınırlı anlamsal arama — kullanıcının kendi
        kütüphanesi dışına asla sızmaz (Qdrant tarafında filtrelenir, sonradan
        Python'da değil). Sonuç: benzerlik sırasına göre place_id listesi.

        Qdrant yapılandırılmamışsa/erişilemezse ya da `place_ids` boşsa boş
        liste döner — çağıran taraf bunu "substring aramasına düş" sinyali
        olarak kullanır.
        """
        if not place_ids:
            return []

        try:
            self._load()
            self._ensure_collection()

            vector = self.model.encode(query).tolist()
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=Filter(
                    must=[FieldCondition(key="place_id", match=MatchAny(any=place_ids))]
                ),
                limit=limit,
            )
            return [r.payload["place_id"] for r in results]
        except Exception as exc:
            logger.warning("Qdrant anlamsal arama başarısız: %s", exc)
            return []
