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
    def get_by_id(self, user_id: int):
        """ID ile kullanıcı getir."""
        ...

    @abstractmethod
    def create(self, email: str, username: str, hashed_password: Optional[str] = None, apple_id: Optional[str] = None):
        """Yeni kullanıcı oluştur. Oluşturulan User nesnesini döner."""
        ...

    @abstractmethod
    def update_apple_id(self, user_id: int, apple_id: str) -> None:
        """Kullanıcının Apple ID'sini güncelle."""
        ...
