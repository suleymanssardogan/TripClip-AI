"""
Infrastructure katmanı — AbstractRefreshTokenRepository'nin SQLAlchemy implementasyonu.
Tüm DB sorgular burada toplanır; üst katmanlar DB'yi doğrudan görmez.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.domain.repositories.refresh_token_repository import AbstractRefreshTokenRepository
from app.models.refresh_token import RefreshToken


class SqlRefreshTokenRepository(AbstractRefreshTokenRepository):

    def __init__(self, db: Session):
        self._db = db

    def create(self, user_id: int, token_hash: str, expires_at: datetime) -> RefreshToken:
        row = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        try:
            self._db.add(row)
            self._db.commit()
            self._db.refresh(row)
        except Exception:
            self._db.rollback()
            raise
        return row

    def get_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        return self._db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    def revoke(self, token_id: int, replaced_by_id: Optional[int] = None) -> None:
        row = self._db.query(RefreshToken).filter(RefreshToken.id == token_id).first()
        if row:
            # revoked_at zaten set edilmiş olabilir (revoke_if_active ile atomic
            # claim edilmiş) — bu durumda sadece replaced_by_id linkini ekleriz,
            # revoked_at'a tekrar dokunmayız.
            if row.revoked_at is None:
                row.revoked_at = datetime.utcnow()
            if replaced_by_id is not None:
                row.replaced_by_id = replaced_by_id
            self._db.commit()

    def revoke_if_active(self, token_id: int) -> bool:
        """Sadece hâlâ aktifse (revoked_at IS NULL) atomic olarak iptal eder.

        Tek bir UPDATE...WHERE ile — read-then-write yerine — race-safe:
        iki eşzamanlı çağrıdan sadece biri rowcount>0 alır.
        """
        rowcount = (
            self._db.query(RefreshToken)
            .filter(RefreshToken.id == token_id, RefreshToken.revoked_at.is_(None))
            .update({"revoked_at": datetime.utcnow()}, synchronize_session=False)
        )
        self._db.commit()
        return rowcount > 0

    def revoke_all_for_user(self, user_id: int) -> None:
        now = datetime.utcnow()
        (
            self._db.query(RefreshToken)
            .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .update({"revoked_at": now}, synchronize_session=False)
        )
        self._db.commit()
