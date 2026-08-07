"""
Infrastructure katmanı — AbstractSharingRepository'nin SQLAlchemy implementasyonu.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy.orm import Session

from app.domain.repositories.sharing_repository import AbstractSharingRepository
from app.models.trip import Trip
from app.models.trip_stop import TripStop
from app.models.trip_share import TripShare
from app.models.trip_share_enums import ShareStatus, CollaboratorRole
from app.models.share_token import ShareToken
from app.models.trip_collaborator import TripCollaborator
from app.core.auth import generate_secure_token, hash_token
from app.core.analytics_events import AnalyticsEvent
from app.application.services.analytics_service import AnalyticsService, get_analytics_service

logger = logging.getLogger(__name__)


class SqlSharingRepository(AbstractSharingRepository):

    def __init__(self, db: Session, analytics: Optional[AnalyticsService] = None):
        self._db = db
        self._analytics = analytics or get_analytics_service()

    # ── Erişim yardımcıları ──────────────────────────────────────────────────

    def _is_owner(self, trip_id: int, user_id: int) -> Optional[Trip]:
        """Trip'i, yalnızca user_id sahibiyse döner; aksi halde (trip yok ya
        da sahibi değil) None — çağıran taraf bunu 'not_found'/'forbidden'
        ayrımı yapmak için trip'in var olup olmadığını AYRICA kontrol eder."""
        trip = self._db.query(Trip).filter(Trip.id == trip_id).first()
        if trip is None or trip.user_id != user_id:
            return None
        return trip

    def _has_any_access(self, trip_id: int, user_id: int) -> bool:
        trip = self._db.query(Trip).filter(Trip.id == trip_id).first()
        if trip is None:
            return False
        if trip.user_id == user_id:
            return True
        return (
            self._db.query(TripCollaborator)
            .filter(TripCollaborator.trip_id == trip_id, TripCollaborator.user_id == user_id)
            .first()
            is not None
        )

    # ── Davet oluşturma / listeleme / iptal ──────────────────────────────────

    def create_share(
        self,
        trip_id: int,
        created_by: int,
        role: str,
        expires_at: Optional[datetime] = None,
        max_uses: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        trip = self._db.query(Trip).filter(Trip.id == trip_id).first()
        if trip is None or trip.user_id != created_by:
            return None

        share = TripShare(trip_id=trip_id, created_by=created_by, role=CollaboratorRole(role))
        self._db.add(share)
        self._db.flush()  # share.id lazım

        raw_token = generate_secure_token()
        token_row = ShareToken(
            share_id=share.id,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
            max_uses=max_uses,
        )
        self._db.add(token_row)
        self._db.commit()

        # Best-effort — davet oluşturma başarısız olsa bile (analytics) davet
        # zaten oluşturulmuş durumda, kullanıcıya hata dönmemeli.
        self._analytics.track(
            event=AnalyticsEvent.SHARED_TRIP_INVITE_SENT,
            trip_id=trip_id,
            platform="server",
            user_id=created_by,
            source="share_link_created",
            kind="trip",
        )

        return self._share_summary(share, token_row, raw_token=raw_token)

    @staticmethod
    def _share_summary(share: TripShare, token: ShareToken, raw_token: Optional[str] = None) -> Dict[str, Any]:
        summary = {
            "share_id":    share.id,
            "trip_id":     share.trip_id,
            "role":        share.role.value,
            "status":      share.status.value,
            "created_at":  share.created_at.isoformat() if share.created_at else None,
            "responded_at": share.responded_at.isoformat() if share.responded_at else None,
            "expires_at":  token.expires_at.isoformat() if token.expires_at else None,
            "max_uses":    token.max_uses,
            "use_count":   token.use_count,
            "revoked":     token.revoked_at is not None,
        }
        if raw_token is not None:
            summary["token"] = raw_token
        return summary

    def list_shares(self, trip_id: int, user_id: int) -> Optional[List[Dict[str, Any]]]:
        if self._is_owner(trip_id, user_id) is None:
            return None

        rows: List[Tuple[TripShare, ShareToken]] = (
            self._db.query(TripShare, ShareToken)
            .join(ShareToken, ShareToken.share_id == TripShare.id)
            .filter(TripShare.trip_id == trip_id)
            .order_by(TripShare.created_at.desc())
            .all()
        )
        result = []
        for share, token in rows:
            self._maybe_expire(share, token)
            result.append(self._share_summary(share, token))
        return result

    def revoke_share(self, trip_id: int, share_id: int, user_id: int) -> str:
        if self._db.query(Trip).filter(Trip.id == trip_id).first() is None:
            return "not_found"
        if self._is_owner(trip_id, user_id) is None:
            return "forbidden"

        share = (
            self._db.query(TripShare)
            .filter(TripShare.id == share_id, TripShare.trip_id == trip_id)
            .first()
        )
        if share is None:
            return "not_found"

        token = self._db.query(ShareToken).filter(ShareToken.share_id == share.id).first()
        now = datetime.utcnow()
        if token is not None:
            token.revoked_at = now
        if share.status == ShareStatus.PENDING:
            share.status = ShareStatus.REVOKED
            share.responded_at = now
        self._db.commit()
        return "ok"

    # ── Token doğrulama (kabul/reddet/önizleme için ortak) ──────────────────

    def _resolve_token(self, raw_token: str) -> Optional[Tuple[TripShare, ShareToken]]:
        token = self._db.query(ShareToken).filter(ShareToken.token_hash == hash_token(raw_token)).first()
        if token is None:
            return None
        share = self._db.query(TripShare).filter(TripShare.id == token.share_id).first()
        if share is None:
            return None
        return share, token

    def _maybe_expire(self, share: TripShare, token: ShareToken) -> None:
        """
        PENDING bir davet, süresi geçmişse EXPIRED'a geçer — bu, "expired"
        durumunun gözlemlendiği TEK an (arka planda bir cron YOK, bkz.
        docs/trip-sharing.md "Security decisions"). Geçiş gerçekten olduysa
        (ilk gözlem) analytics event'i tetiklenir, tekrar tekrar değil.
        """
        if share.status != ShareStatus.PENDING or token.expires_at is None:
            return
        if datetime.utcnow() <= token.expires_at:
            return

        share.status = ShareStatus.EXPIRED
        share.responded_at = datetime.utcnow()
        self._db.commit()

        self._analytics.track(
            event=AnalyticsEvent.SHARED_TRIP_EXPIRED,
            trip_id=share.trip_id,
            platform="server",
            user_id=share.created_by,
            source="lazy_expiry_check",
            kind="trip",
        )

    def _is_usable(self, share: TripShare, token: ShareToken) -> bool:
        """
        Revoked/expired/already-responded kontrolleri — accept/decline/preview
        ORTAK. max_uses BİLEREK burada değil: yalnızca preview_by_token'ın
        kendi limitini uyguluyor (bkz. orada), aksi halde bir önizlemenin
        tükettiği kota, aynı token'ı meşru biçimde kabul etmeye çalışan
        kişiyi de bloklardı — "önce önizle, sonra kabul et" normal akıştır.
        """
        if token.revoked_at is not None:
            return False
        self._maybe_expire(share, token)
        return share.status == ShareStatus.PENDING

    def preview_by_token(self, raw_token: str) -> Optional[Dict[str, Any]]:
        """
        Kimlik doğrulama gerekmez — tokenin en çok maruz kaldığı yüzey. Bu
        yüzden `max_uses` burada tüketilir: bir share'in status'u accept/
        decline'da tek bir terminal duruma geçtiği için (bkz.
        docs/trip-sharing.md "max_uses semantics") max_uses'ın asıl anlamlı
        koruması BURADA — otomatik token tarama/deneme saldırılarına karşı
        bir önizlemenin kaç kez çözülebileceğini sınırlamak.
        """
        resolved = self._resolve_token(raw_token)
        if resolved is None:
            return None
        share, token = resolved
        if not self._is_usable(share, token):
            return None
        if token.max_uses is not None and token.use_count >= token.max_uses:
            return None

        trip = self._db.query(Trip).filter(Trip.id == share.trip_id).first()
        if trip is None:
            return None
        stops_count = self._db.query(TripStop).filter(TripStop.trip_id == trip.id).count()

        token.use_count += 1
        self._db.commit()

        return {
            "trip_title": trip.title,
            "stops_count": stops_count,
            "role": share.role.value,
        }

    def accept_by_token(self, raw_token: str, user_id: int) -> Dict[str, Any]:
        resolved = self._resolve_token(raw_token)
        if resolved is None:
            return {"status": "invalid", "trip_id": None}
        share, token = resolved
        if not self._is_usable(share, token):
            return {"status": "invalid", "trip_id": None}

        trip = self._db.query(Trip).filter(Trip.id == share.trip_id).first()
        if trip is None:
            return {"status": "invalid", "trip_id": None}
        if trip.user_id == user_id:
            # Owner kendi trip'ine "katılamaz" — zaten tam erişimi var, bir
            # collaborator satırı oluşturmak yalnızca kafa karışıklığı yaratır.
            return {"status": "self_invite", "trip_id": trip.id}

        existing = (
            self._db.query(TripCollaborator)
            .filter(TripCollaborator.trip_id == trip.id, TripCollaborator.user_id == user_id)
            .first()
        )
        if existing is not None:
            # Zaten collaborator — rolü bu davetin rolüyle güncelle (ör. viewer
            # olarak eklenmiş biri editor daveti kabul ederse yükseltilir).
            existing.role = share.role
            existing.share_id = share.id
        else:
            self._db.add(TripCollaborator(
                trip_id=trip.id, user_id=user_id, role=share.role, share_id=share.id,
            ))

        # use_count'a dokunmuyoruz — accept/decline zaten status state
        # machine'i ile tek seferlik (PENDING'ten terminale geçiş bir daha
        # tekrarlanamaz). use_count yalnızca preview_by_token'ın anti-tarama
        # sınırı, accept burada onu bir daha tüketirse max_uses=1 ile normal
        # "önce önizle, sonra kabul et" akışını kırardı.
        share.status = ShareStatus.ACCEPTED
        share.accepted_by = user_id
        share.responded_at = datetime.utcnow()
        self._db.commit()

        return {"status": "ok", "trip_id": trip.id}

    def decline_by_token(self, raw_token: str, user_id: int) -> str:
        resolved = self._resolve_token(raw_token)
        if resolved is None:
            return "invalid"
        share, token = resolved
        if not self._is_usable(share, token):
            return "invalid"

        now = datetime.utcnow()
        share.status = ShareStatus.DECLINED
        share.responded_at = now
        self._db.commit()

        self._analytics.track(
            event=AnalyticsEvent.SHARED_TRIP_DECLINED,
            trip_id=share.trip_id,
            platform="server",
            user_id=user_id,
            source="invite_response",
            kind="trip",
        )
        return "ok"

    # ── Collaborator yönetimi ────────────────────────────────────────────────

    def list_collaborators(self, trip_id: int, user_id: int) -> Optional[List[Dict[str, Any]]]:
        if not self._has_any_access(trip_id, user_id):
            return None

        rows = (
            self._db.query(TripCollaborator)
            .filter(TripCollaborator.trip_id == trip_id)
            .order_by(TripCollaborator.joined_at.asc())
            .all()
        )
        return [
            {
                "user_id": c.user_id,
                "role": c.role.value,
                "joined_at": c.joined_at.isoformat() if c.joined_at else None,
            }
            for c in rows
        ]

    def remove_collaborator(self, trip_id: int, target_user_id: int, requesting_user_id: int) -> str:
        if self._db.query(Trip).filter(Trip.id == trip_id).first() is None:
            return "not_found"
        if self._is_owner(trip_id, requesting_user_id) is None:
            return "forbidden"

        collab = (
            self._db.query(TripCollaborator)
            .filter(TripCollaborator.trip_id == trip_id, TripCollaborator.user_id == target_user_id)
            .first()
        )
        if collab is None:
            return "not_found"

        self._db.delete(collab)
        self._db.commit()
        return "ok"
