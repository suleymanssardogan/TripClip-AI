from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Float, JSON, Index
from app.core.database import Base
from datetime import datetime
import enum

class VideoStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Video(Base):
    __tablename__ = "videos"

    # — Primary key —
    id = Column(Integer, primary_key=True, index=True)

    # — Ownership & metadata —
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    filename   = Column(String, nullable=False)
    file_path  = Column(String, nullable=False)
    status     = Column(Enum(VideoStatus), default=VideoStatus.UPLOADED, index=True)
    duration   = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # — Composite indexes for common query patterns —
    __table_args__ = (
        # Kullanıcının videolarını tarihe göre sıralamak için (dashboard feed)
        Index("ix_videos_user_created", "user_id", "created_at"),
        # Public feed: tamamlanan videoları yeniye göre listelemek için
        Index("ix_videos_status_created", "status", "created_at"),
    )

    # AI Results
    processing_time = Column(Float, nullable=True)
    fps_processed = Column(Float , nullable=True)
    detections_count =Column(Integer,nullable=True)
    landmarks_count = Column(Integer,nullable=True)
    top_objects = Column(JSON,nullable=True)
    extracted_texts= Column(JSON,nullable=True)
    vision_landmarks = Column(JSON,nullable=True)
    transcription = Column(JSON,nullable=True)
    extracted_locations = Column(JSON,nullable=True)
    enriched_locations = Column(JSON,nullable=True)
    deduplicated_locations = Column(JSON, nullable=True)   
    location_summary = Column(JSON, nullable=True)
    optimized_route = Column(JSON, nullable=True)
    travel_tips = Column(JSON, nullable=True)
    ocr_pois = Column(JSON, nullable=True)

    # Hangi AI aşamalarının fallback'e düştüğünü kaydeder — pipeline'ın
    # sessizce bozuk sonuç üretip COMPLETED olarak işaretlenmesini önlemek için.
    degradation = Column(JSON, nullable=True)
    # Kullanıcının editor'de belirlediği durak sırası: gün başına ID listesi.
    # Yalnızca sıralamayı değil, HANGİ durakların kaldığını da belirler —
    # bkz. visible_locations().
    stop_order = Column(JSON, nullable=True)


def visible_locations(video: "Video") -> list:
    """
    Kullanıcıya gösterilecek durak listesi.

    `deduplicated_locations` AI'nin ürettiği ham sonuç; kullanıcı durakları
    yeniden sıralayıp silebiliyor ve bu düzenleme `stop_order` içinde 1-tabanlı
    id'lerle saklanıyor. Listede olmayan id silinmiş sayılır.

    Ham veri hiç değiştirilmiyor: düzenleme geri alınabilir olsun ve yeniden
    işlemeye gerek kalmasın diye silme yıkıcı değil.

    Özet (liste kartı) ile detay ekranının aynı sayıyı göstermesi bu tek
    fonksiyona bağlı — iki yerde ayrı ayrı hesaplandığında kart "12 mekan"
    derken detay 11 gösteriyordu.
    """
    locations = video.deduplicated_locations or []
    order = video.stop_order
    if not locations or not order or not isinstance(order, list):
        return locations

    ordered = [
        locations[stop_id - 1]
        for day in order if isinstance(day, list)
        for stop_id in day
        if isinstance(stop_id, int) and 1 <= stop_id <= len(locations)
    ]
    # Eskimiş/bozuk bir sıra yüzünden planı boş göstermeyiz.
    return ordered or locations
    

    

 
