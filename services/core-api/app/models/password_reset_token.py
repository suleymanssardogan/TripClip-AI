from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.core.database import Base
from datetime import datetime


class PasswordResetToken(Base):
    """
    Şifre sıfırlama token'ı — `RefreshToken`/`ShareToken` ile AYNI ilke
    (bkz. app/core/auth.py generate_secure_token/hash_token): ham token
    asla DB'ye yazılmaz, yalnızca SHA-256 hash'i. Ham değer yalnızca
    e-postadaki linkte bir kez görünür, hiçbir API yanıtında/logda YOK.

    `used_at` — `RefreshToken.revoked_at` ile AYNI "tek kullanımlık" deseni:
    NULL = hâlâ kullanılabilir, dolu = zaten tüketilmiş (tekrar kullanılamaz).
    Atomic "claim" (`mark_used_if_active`) RefreshToken'ın `revoke_if_active`'ı
    ile BİREBİR aynı race-safety garantisini verir.
    """
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
