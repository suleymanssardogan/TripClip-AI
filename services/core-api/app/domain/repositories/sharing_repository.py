"""
Domain katmanı — Trip sharing (davet/collaborator) repository arayüzü.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any


class AbstractSharingRepository(ABC):

    @abstractmethod
    def create_share(
        self,
        trip_id: int,
        created_by: int,
        role: str,
        expires_at: Optional[datetime] = None,
        max_uses: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Yeni bir davet + gizli token oluşturur. `created_by` trip'in owner'ı
        değilse (ya da trip yoksa) None döner. Dönen dict'teki `token` ham
        değer — yalnızca burada görünür, DB'ye hash'lenmiş hali yazılır.
        """
        ...

    @abstractmethod
    def list_shares(self, trip_id: int, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """Owner-only. Owner değilse/trip yoksa None döner."""
        ...

    @abstractmethod
    def revoke_share(self, trip_id: int, share_id: int, user_id: int) -> str:
        """Döner: 'ok' | 'not_found' | 'forbidden' (owner-only)."""
        ...

    @abstractmethod
    def preview_by_token(self, raw_token: str) -> Optional[Dict[str, Any]]:
        """
        Kimlik doğrulama GEREKTİRMEZ — davet linkini açan biri kabul etmeden
        önce neyi kabul edeceğini görebilmeli. Token geçersiz/süresi
        dolmuş/iptal edilmiş/zaten yanıtlanmışsa None döner.
        """
        ...

    @abstractmethod
    def accept_by_token(self, raw_token: str, user_id: int) -> Dict[str, Any]:
        """
        Döner: {"status": "ok"|"invalid"|"self_invite", "trip_id": int|None}.
        'ok' ise TripCollaborator satırı oluşturulmuş/güncellenmiştir.
        """
        ...

    @abstractmethod
    def decline_by_token(self, raw_token: str, user_id: int) -> str:
        """Döner: 'ok' | 'invalid'."""
        ...

    @abstractmethod
    def list_collaborators(self, trip_id: int, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """Owner VEYA herhangi bir collaborator görebilir. Erişimi yoksa None."""
        ...

    @abstractmethod
    def remove_collaborator(self, trip_id: int, target_user_id: int, requesting_user_id: int) -> str:
        """Döner: 'ok' | 'not_found' | 'forbidden' (owner-only)."""
        ...
