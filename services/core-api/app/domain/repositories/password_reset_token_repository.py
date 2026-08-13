"""
Domain katmanı — PasswordResetToken repository abstract interface.
Bağımlılık yönü: Infrastructure → Domain (içe doğru bağımlılık).
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class AbstractPasswordResetTokenRepository(ABC):

    @abstractmethod
    def create(self, user_id: int, token_hash: str, expires_at: datetime):
        """Yeni şifre sıfırlama token'ı oluştur. Oluşturulan satırı döner."""
        ...

    @abstractmethod
    def get_by_hash(self, token_hash: str):
        """Hash ile token kaydını getir. Bulunamazsa None döner."""
        ...

    @abstractmethod
    def mark_used_if_active(self, token_id: int) -> bool:
        """Sadece hâlâ kullanılmamışsa (used_at IS NULL) atomic olarak
        'kullanıldı' işaretler.

        Read-then-write yerine tek bir UPDATE...WHERE — bkz.
        RefreshTokenRepository.revoke_if_active'ın AYNI race-safety ilkesi:
        aynı token'ı aynı anda iki kez kullanmaya çalışan iki istekten
        sadece biri True alır.
        """
        ...

    @abstractmethod
    def invalidate_all_for_user(self, user_id: int) -> None:
        """Kullanıcının TÜM hâlâ aktif (kullanılmamış) sıfırlama token'larını
        geçersiz kılar — yeni bir sıfırlama isteği geldiğinde önceki e-posta
        linklerinin hâlâ geçerli kalmaması için (bkz. AuthService.request_password_reset)."""
        ...
