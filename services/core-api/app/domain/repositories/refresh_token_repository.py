"""
Domain katmanı — RefreshToken repository abstract interface.
Bağımlılık yönü: Infrastructure → Domain (içe doğru bağımlılık).
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class AbstractRefreshTokenRepository(ABC):

    @abstractmethod
    def create(self, user_id: int, token_hash: str, expires_at: datetime):
        """Yeni refresh token kaydı oluştur. Oluşturulan satırı döner."""
        ...

    @abstractmethod
    def get_by_hash(self, token_hash: str):
        """Hash ile refresh token kaydını getir. Bulunamazsa None döner."""
        ...

    @abstractmethod
    def revoke(self, token_id: int, replaced_by_id: Optional[int] = None) -> None:
        """Refresh token'ı iptal et (rotation sırasında replaced_by_id verilir)."""
        ...

    @abstractmethod
    def revoke_if_active(self, token_id: int) -> bool:
        """Sadece hâlâ aktifse (revoked_at IS NULL) atomic olarak iptal eder.

        Read-then-write yerine tek bir UPDATE...WHERE — iki eşzamanlı refresh
        isteği aynı token'ı aynı anda kullanmaya çalışırsa sadece biri True
        döner, diğeri False alıp güvenli şekilde durur (yeni token üretmez).
        """
        ...

    @abstractmethod
    def revoke_all_for_user(self, user_id: int) -> None:
        """Kullanıcının TÜM aktif refresh token'larını iptal et (reuse detection sonrası)."""
        ...
