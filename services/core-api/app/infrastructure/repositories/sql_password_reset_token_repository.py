"""
Infrastructure katmanı — AbstractPasswordResetTokenRepository'nin SQLAlchemy
implementasyonu. `SqlRefreshTokenRepository` ile BİREBİR aynı desen.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.domain.repositories.password_reset_token_repository import AbstractPasswordResetTokenRepository
from app.models.password_reset_token import PasswordResetToken


class SqlPasswordResetTokenRepository(AbstractPasswordResetTokenRepository):

    def __init__(self, db: Session):
        self._db = db

    def create(self, user_id: int, token_hash: str, expires_at: datetime) -> PasswordResetToken:
        row = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        try:
            self._db.add(row)
            self._db.commit()
            self._db.refresh(row)
        except Exception:
            self._db.rollback()
            raise
        return row

    def get_by_hash(self, token_hash: str) -> Optional[PasswordResetToken]:
        return self._db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()

    def mark_used_if_active(self, token_id: int) -> bool:
        rowcount = (
            self._db.query(PasswordResetToken)
            .filter(PasswordResetToken.id == token_id, PasswordResetToken.used_at.is_(None))
            .update({"used_at": datetime.utcnow()}, synchronize_session=False)
        )
        self._db.commit()
        return rowcount > 0

    def invalidate_all_for_user(self, user_id: int) -> None:
        now = datetime.utcnow()
        (
            self._db.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
            .update({"used_at": now}, synchronize_session=False)
        )
        self._db.commit()
