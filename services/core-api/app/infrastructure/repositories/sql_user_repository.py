"""
Infrastructure katmanı — AbstractUserRepository'nin SQLAlchemy implementasyonu.
Tüm DB sorgular burada toplanır; üst katmanlar DB'yi doğrudan görmez.
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.domain.repositories.user_repository import AbstractUserRepository
from app.models.user import User


class SqlUserRepository(AbstractUserRepository):

    def __init__(self, db: Session):
        self._db = db

    def get_by_email(self, email: str) -> Optional[User]:
        return self._db.query(User).filter(User.email == email).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return self._db.query(User).filter(User.username == username).first()

    def get_by_apple_id(self, apple_id: str) -> Optional[User]:
        return self._db.query(User).filter(User.apple_id == apple_id).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self._db.query(User).filter(User.id == user_id).first()

    def create(
        self,
        email: str,
        username: str,
        hashed_password: Optional[str] = None,
        apple_id: Optional[str] = None,
    ) -> User:
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            apple_id=apple_id,
        )
        try:
            self._db.add(user)
            self._db.commit()
            self._db.refresh(user)
        except Exception:
            self._db.rollback()
            raise
        return user

    def update_apple_id(self, user_id: int, apple_id: str) -> None:
        user = self.get_by_id(user_id)
        if user:
            user.apple_id = apple_id
            self._db.commit()
