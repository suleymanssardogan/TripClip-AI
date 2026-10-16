"""
BFF ↔ core-api arası paylaşılan sır (shared secret) doğrulaması.

Docker network izolasyonu (core-api'nin prod'da dışa açık port'u yok) BFF
dışından erişimi zaten engelliyor, ama bu tek katman: bir network yanlış
yapılandırılırsa core-api'ye doğrudan istek atılıp `x-user-id` header'ı
sahtelenerek herhangi bir kullanıcı taklit edilebilir. Bu dependency
savunmanın ikinci katmanı — BFF'lerin gönderdiği X-Internal-Secret'ı doğrular.

INTERNAL_API_SECRET tanımlı değilse (local geliştirme/test) doğrulama
atlanır — mevcut davranış bozulmaz. Ancak APP_ENV=production iken secret
tanımsız bırakılırsa bu ikinci savunma katmanı sessizce devre dışı kalırdı;
bu yüzden prod'da secret eksikse başlangıçta hata fırlatılır (fail-closed).
"""
import secrets
import logging
import os

from fastapi import Header, HTTPException, Depends
from app.core.database import get_db

INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

if len(INTERNAL_API_SECRET) < 32 and os.getenv("APP_ENV") == "production":
    logging.getLogger("tripclip.internal_auth").error(
        "INTERNAL_API_SECRET must contain at least 32 characters in production."
    )
    raise RuntimeError(
        "INTERNAL_API_SECRET must contain at least 32 characters in production. "
        "Set a secure random value via the INTERNAL_API_SECRET environment variable."
    )


async def verify_internal_secret(
    x_internal_secret: str = Header(default=""),
) -> None:
    if not INTERNAL_API_SECRET:
        return  # dev/test ortamı — secret hiç ayarlanmamışsa doğrulama yapılmaz
    if not secrets.compare_digest(x_internal_secret.encode(), INTERNAL_API_SECRET.encode()):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Geçersiz internal secret."},
        )


def verify_active_internal_user(
    x_user_id: int | None = Header(default=None),
    db=Depends(get_db),
) -> None:
    """Reject still-valid JWT subjects whose account was deleted or disabled."""
    if x_user_id is None:
        return
    from app.models.user import User
    user = db.get(User, x_user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, detail={"code": "AUTH_ERROR", "message": "Oturum geçersiz. Tekrar giriş yapın."})
