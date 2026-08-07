from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.core.database import Base
from datetime import datetime


class ShareToken(Base):
    """
    Bir TripShare'in gizli, yüksek entropili değeri — 1:1. RefreshToken ile
    aynı ilke (bkz. app/core/auth.py generate_secure_token/hash_token):
    ham token asla DB'ye yazılmaz, yalnızca SHA-256 hash'i. Ham değer
    yalnızca oluşturma anındaki API yanıtında bir kez görünür.

    `share_id` üzerinden trip_id'ye ulaşılır ama token'ın KENDİSİ hiçbir
    trip/ID bilgisi taşımaz — bir token'ı görmek/tahmin etmeye çalışmak
    tek başına hangi trip'e ait olduğunu söylemez (bkz. spesifikasyonun
    "tokens should not expose trip IDs").
    """
    __tablename__ = "share_tokens"

    id         = Column(Integer, primary_key=True, index=True)
    share_id   = Column(Integer, ForeignKey("trip_shares.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=True)
    # None = sınırsız kullanım. Kabul + reddetme birer "kullanım" sayılır —
    # bkz. SqlSharingRepository._consume_token.
    max_uses   = Column(Integer, nullable=True)
    use_count  = Column(Integer, nullable=False, default=0)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
