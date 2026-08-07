"""
Application katmanı — Trip sharing (davet/collaborator) iş mantığı.
Repository DI ile enjekte edilir → test ortamında kolayca mock'lanır.
"""
import os
from datetime import datetime
from typing import Optional

from app.domain.repositories.sharing_repository import AbstractSharingRepository
from app.application.dto.sharing_dto import (
    ShareResponse,
    ShareListResponse,
    SharePreviewResponse,
    AcceptShareResponse,
    CollaboratorResponse,
    CollaboratorListResponse,
)
from app.core.exceptions import (
    TripNotFoundException,
    PermissionDeniedException,
    InvalidShareRequestException,
    ShareTokenInvalidException,
    CannotJoinOwnTripException,
)
from app.models.trip_share_enums import CollaboratorRole

_VALID_ROLES = {r.value for r in CollaboratorRole}


class TripSharingService:

    def __init__(self, repo: AbstractSharingRepository):
        self._repo = repo

    @staticmethod
    def _share_base_url() -> str:
        return os.getenv("WEB_APP_BASE_URL", "http://localhost:3000").rstrip("/")

    @staticmethod
    def _parse_expires_at(raw: Optional[str]) -> Optional[datetime]:
        if raw is None:
            return None
        try:
            # "Z" desteği: fromisoformat 3.11'den önce "Z" son ekini kabul etmiyor.
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=None)  # DB naive UTC saklıyor (bkz. diğer modeller)
        except ValueError:
            raise InvalidShareRequestException(f"Geçersiz expires_at biçimi: '{raw}'.")

    def create_share(
        self,
        trip_id: int,
        user_id: int,
        role: str,
        expires_at_raw: Optional[str],
        max_uses: Optional[int],
    ) -> ShareResponse:
        if role not in _VALID_ROLES:
            raise InvalidShareRequestException(f"Geçersiz rol: '{role}'. 'viewer' ya da 'editor' olmalı.")
        if max_uses is not None and max_uses < 1:
            raise InvalidShareRequestException("max_uses en az 1 olmalı.")

        expires_at = self._parse_expires_at(expires_at_raw)
        if expires_at is not None and expires_at <= datetime.utcnow():
            raise InvalidShareRequestException("expires_at geçmişte bir tarih olamaz.")

        share = self._repo.create_share(trip_id, user_id, role, expires_at=expires_at, max_uses=max_uses)
        if share is None:
            raise TripNotFoundException(trip_id)

        token = share.get("token")
        share["share_url"] = f"{self._share_base_url()}/invite/{token}" if token else None
        return ShareResponse(**share)

    def list_shares(self, trip_id: int, user_id: int) -> ShareListResponse:
        shares = self._repo.list_shares(trip_id, user_id)
        if shares is None:
            raise TripNotFoundException(trip_id)
        return ShareListResponse(shares=[ShareResponse(**s) for s in shares])

    def revoke_share(self, trip_id: int, share_id: int, user_id: int) -> None:
        result = self._repo.revoke_share(trip_id, share_id, user_id)
        if result == "not_found":
            raise TripNotFoundException(trip_id)
        if result == "forbidden":
            raise PermissionDeniedException("Bu daveti yalnızca gezinin sahibi iptal edebilir.")

    def preview_share(self, token: str) -> SharePreviewResponse:
        preview = self._repo.preview_by_token(token)
        if preview is None:
            raise ShareTokenInvalidException()
        return SharePreviewResponse(**preview)

    def accept_share(self, token: str, user_id: int) -> AcceptShareResponse:
        result = self._repo.accept_by_token(token, user_id)
        if result["status"] == "self_invite":
            raise CannotJoinOwnTripException()
        if result["status"] != "ok":
            raise ShareTokenInvalidException()
        return AcceptShareResponse(trip_id=result["trip_id"])

    def decline_share(self, token: str, user_id: int) -> None:
        result = self._repo.decline_by_token(token, user_id)
        if result != "ok":
            raise ShareTokenInvalidException()

    def list_collaborators(self, trip_id: int, user_id: int) -> CollaboratorListResponse:
        collaborators = self._repo.list_collaborators(trip_id, user_id)
        if collaborators is None:
            raise TripNotFoundException(trip_id)
        return CollaboratorListResponse(collaborators=[CollaboratorResponse(**c) for c in collaborators])

    def remove_collaborator(self, trip_id: int, target_user_id: int, requesting_user_id: int) -> None:
        result = self._repo.remove_collaborator(trip_id, target_user_id, requesting_user_id)
        if result == "not_found":
            raise TripNotFoundException(trip_id)
        if result == "forbidden":
            raise PermissionDeniedException("Collaborator'ı yalnızca gezinin sahibi çıkarabilir.")
