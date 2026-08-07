from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from app.core.database import Base
from datetime import datetime


class Place(Base):
    """
    Videolar-arası, tekilleştirilmiş mekan kaydı.

    `Video.deduplicated_locations` bir videonun İÇİNDEKİ tekrarları temizler;
    Place videolar ARASINDAKİ tekrarları temizler — aynı mekan iki farklı
    Reel'den çıkarılırsa tek Place satırına toplanır (bkz. SqlPlaceRepository.
    sync_from_video). Bu tablo olmadan "kütüphane" ekranı aynı mekanı N kez
    listeler; goal.md Phase 12'deki temel yapısal boşluk buydu.
    """
    __tablename__ = "places"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # normalize_place_name() çıktısı — videolar arası eşleştirme anahtarı.
    # Ayrı bir DB unique constraint YOK: aynı isim farklı şehirlerde geçerli
    # olabilir, eşleşme name_key + mesafe birlikte kontrol edilir (bkz. repo).
    name_key = Column(String, nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    city = Column(String, nullable=True, index=True)
    address = Column(String, nullable=True)
    # Henüz otomatik doldurulmuyor — goal.md Phase 18 Week 9-10 (kategori/tag
    # sınıflandırma) kapsamında pipeline tarafından set edilecek. Şimdiden
    # kolonu açmak, o iş geldiğinde ikinci bir migration'ı gereksiz kılıyor.
    category = Column(String, nullable=True, index=True)
    # ondelete=SET NULL: video silinebilir bir kullanıcı özelliği (bkz.
    # VideoService.delete_video) — kaynak video gittiğinde Place'in kendisi
    # (ve ona bağlı PlaceSave'ler) geçerliliğini korumalı, sadece köken bilgisi kaybolur.
    first_seen_video_id = Column(Integer, ForeignKey("videos.id", ondelete="SET NULL"), nullable=True)
    # Kaç PlaceSave satırının bu Place'e işaret ettiğinin denormalize sayacı —
    # her sorguda COUNT yapmadan popülerlik/sıralama sinyali vermek için.
    save_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # Kütüphane ekranının "şehre göre ara" sorgusu için.
        Index("ix_places_city_name_key", "city", "name_key"),
    )
