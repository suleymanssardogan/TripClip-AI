"""
Domain katmanı — User repository abstract interface.
Bağımlılık yönü: Infrastructure → Domain (içe doğru bağımlılık).
"""
from abc import ABC, abstractmethod
from typing import Optional


class AbstractUserRepository(ABC):

    @abstractmethod
    def get_by_email(self, email: str):
        """E-posta ile kullanıcı getir. Bulunamazsa None döner."""
        ...

    @abstractmethod
    def get_by_username(self, username: str):
        """Kullanıcı adı ile kullanıcı getir."""
        ...

    @abstractmethod
    def get_by_apple_id(self, apple_id: str):
        """Apple ID ile kullanıcı getir."""
        ...

    @abstractmethod
    def get_by_google_id(self, google_id: str):
        """Google ID (sub claim) ile kullanıcı getir (M34)."""
        ...

    @abstractmethod
    def get_by_id(self, user_id: int):
        """ID ile kullanıcı getir."""
        ...

    @abstractmethod
    def create(
        self, email: str, username: str, hashed_password: Optional[str] = None,
        apple_id: Optional[str] = None, google_id: Optional[str] = None,
    ):
        """Yeni kullanıcı oluştur. Oluşturulan User nesnesini döner."""
        ...

    @abstractmethod
    def update_apple_id(self, user_id: int, apple_id: str) -> None:
        """Kullanıcının Apple ID'sini güncelle."""
        ...

    @abstractmethod
    def update_google_id(self, user_id: int, google_id: str) -> None:
        """Kullanıcının Google ID'sini günceller — mevcut e-posta/şifre
        hesabını doğrulanmış bir Google kimliğiyle BAĞLAR (M34)."""
        ...

    @abstractmethod
    def update_password(self, user_id: int, hashed_password: str) -> None:
        """Kullanıcının şifre hash'ini günceller (M34, şifre sıfırlama)."""
        ...

    @abstractmethod
    def update_apns_token(self, user_id: int, token: str) -> None:
        """Kullanıcının APNs push bildirim device token'ını güncelle."""
        ...

    @abstractmethod
    def clear_apns_token(self, user_id: int) -> None:
        """APNs'in geçersiz/kayıt-dışı dediği bir token'ı temizle — aksi
        halde her push denemesi aynı ölü token'a boşuna gönderilmeye devam eder."""
        ...
