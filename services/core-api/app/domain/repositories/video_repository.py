"""
Domain katmanı — Video repository abstract interface.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class AbstractVideoRepository(ABC):

    @abstractmethod
    def create(self, filename: str, file_path: str, user_id: int):
        """Yeni video kaydı oluştur. Video nesnesini döner."""
        ...

    @abstractmethod
    def get_by_id(self, video_id: int):
        """ID ile video getir. Bulunamazsa None döner."""
        ...

    @abstractmethod
    def get_by_user(self, user_id: int) -> List:
        """Kullanıcıya ait tüm videoları getir."""
        ...

    @abstractmethod
    def get_completed(self, city: Optional[str] = None, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Tamamlanan videoları listele (public feed). {"plans": [...], "total": N} döner."""
        ...

    @abstractmethod
    def get_stats(self) -> Dict[str, int]:
        """Platform istatistiklerini döner."""
        ...

    @abstractmethod
    def mark_processing(self, video_id: int) -> None:
        """Video durumunu PROCESSING olarak güncelle."""
        ...

    @abstractmethod
    def save_results(self, video_id: int, results: Dict[str, Any]) -> None:
        """ML pipeline sonuçlarını kaydet, durumu COMPLETED yap."""
        ...

    @abstractmethod
    def mark_failed(self, video_id: int) -> None:
        """Video durumunu FAILED olarak güncelle."""
        ...
