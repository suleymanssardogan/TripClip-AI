"""
Infrastructure katmanı — AbstractUserRepository'nin SQLAlchemy implementasyonu.
Tüm DB sorgular burada toplanır; üst katmanlar DB'yi doğrudan görmez.
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.domain.repositories.user_repository import AbstractUserRepository
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.password_reset_token import PasswordResetToken
from app.models.place_save import PlaceSave
from app.models.plan import Plan
from app.models.video import Video
from app.models.trip import Trip
from app.models.trip_stop import TripStop
from app.models.trip_itinerary import TripItinerary
from app.models.trip_itinerary_stop import TripItineraryStop
from app.models.trip_itinerary_apply_history import TripItineraryApplyHistory
from app.models.trip_collaborator import TripCollaborator
from app.models.trip_share import TripShare


class SqlUserRepository(AbstractUserRepository):

    def __init__(self, db: Session):
        self._db = db

    def get_by_email(self, email: str) -> Optional[User]:
        return self._db.query(User).filter(User.email == email).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return self._db.query(User).filter(User.username == username).first()

    def get_by_apple_id(self, apple_id: str) -> Optional[User]:
        return self._db.query(User).filter(User.apple_id == apple_id).first()

    def get_by_google_id(self, google_id: str) -> Optional[User]:
        return self._db.query(User).filter(User.google_id == google_id).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self._db.query(User).filter(User.id == user_id).first()

    def create(
        self,
        email: str,
        username: str,
        hashed_password: Optional[str] = None,
        apple_id: Optional[str] = None,
        google_id: Optional[str] = None,
    ) -> User:
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            apple_id=apple_id,
            google_id=google_id,
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

    def update_google_id(self, user_id: int, google_id: str) -> None:
        user = self.get_by_id(user_id)
        if user:
            user.google_id = google_id
            self._db.commit()

    def update_password(self, user_id: int, hashed_password: str) -> None:
        user = self.get_by_id(user_id)
        if user:
            user.hashed_password = hashed_password
            self._db.commit()

    def update_apns_token(self, user_id: int, token: str) -> None:
        user = self.get_by_id(user_id)
        if user:
            user.apns_token = token
            self._db.commit()

    def clear_apns_token(self, user_id: int) -> None:
        user = self.get_by_id(user_id)
        if user:
            user.apns_token = None
            self._db.commit()

    def delete_account(self, user_id: int) -> list[str]:
        user = self.get_by_id(user_id)
        if not user:
            return []
        video_rows = self._db.query(Video.id, Video.file_path).filter(Video.user_id == user_id).all()
        video_ids = [row.id for row in video_rows]
        trip_ids = [row.id for row in self._db.query(Trip.id).filter(Trip.user_id == user_id).all()]
        try:
            self._db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete(synchronize_session=False)
            self._db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_id).delete(synchronize_session=False)
            self._db.query(PlaceSave).filter(PlaceSave.user_id == user_id).delete(synchronize_session=False)
            created_share_ids = [r.id for r in self._db.query(TripShare.id).filter(TripShare.created_by == user_id).all()]
            collaborator_filter = (
                (TripCollaborator.user_id == user_id) | (TripCollaborator.trip_id.in_(trip_ids) if trip_ids else False)
            )
            if created_share_ids:
                collaborator_filter = collaborator_filter | TripCollaborator.share_id.in_(created_share_ids)
            self._db.query(TripCollaborator).filter(collaborator_filter).delete(synchronize_session=False)
            self._db.query(TripShare).filter(
                (TripShare.created_by == user_id) | (TripShare.trip_id.in_(trip_ids) if trip_ids else False)
            ).delete(synchronize_session=False)
            self._db.query(TripShare).filter(TripShare.accepted_by == user_id).update({TripShare.accepted_by: None}, synchronize_session=False)
            if trip_ids:
                self._db.query(TripItineraryApplyHistory).filter(TripItineraryApplyHistory.trip_id.in_(trip_ids)).delete(synchronize_session=False)
                itinerary_ids = [r.id for r in self._db.query(TripItinerary.id).filter(TripItinerary.trip_id.in_(trip_ids)).all()]
                if itinerary_ids:
                    self._db.query(TripItineraryStop).filter(TripItineraryStop.itinerary_id.in_(itinerary_ids)).delete(synchronize_session=False)
                self._db.query(TripItinerary).filter(TripItinerary.trip_id.in_(trip_ids)).delete(synchronize_session=False)
                self._db.query(TripStop).filter(TripStop.trip_id.in_(trip_ids)).delete(synchronize_session=False)
                self._db.query(Trip).filter(Trip.id.in_(trip_ids)).delete(synchronize_session=False)
            plan_filter = Plan.user_id == user_id
            if video_ids:
                plan_filter = plan_filter | Plan.video_id.in_(video_ids)
            self._db.query(Plan).filter(plan_filter).delete(synchronize_session=False)
            if video_ids:
                self._db.query(Video).filter(Video.id.in_(video_ids)).delete(synchronize_session=False)
            from app.models.privacy_erasure_record import PendingFileErasure, PrivacyErasureRecord
            for row in video_rows:
                if row.file_path:
                    self._db.add(PendingFileErasure(file_path=row.file_path))
            self._db.add(PrivacyErasureRecord(action="delete", category="account_sql_records", count=1))
            self._db.delete(user)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return [row.file_path for row in video_rows if row.file_path]
