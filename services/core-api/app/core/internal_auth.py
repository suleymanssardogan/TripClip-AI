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
import logging
import os

from fastapi import Header, HTTPException

INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

if not INTERNAL_API_SECRET and os.getenv("APP_ENV") == "production":
    logging.getLogger("tripclip.internal_auth").error(
        "❌ INTERNAL_API_SECRET tanımsız ama APP_ENV=production."
    )
    raise RuntimeError(
        "INTERNAL_API_SECRET must be set in production. "
        "Set a secure random value via the INTERNAL_API_SECRET environment variable."
    )


async def verify_internal_secret(
    x_internal_secret: str = Header(default=""),
) -> None:
    if not INTERNAL_API_SECRET:
        return  # dev/test ortamı — secret hiç ayarlanmamışsa doğrulama yapılmaz
    if x_internal_secret != INTERNAL_API_SECRET:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Geçersiz internal secret."},
        )
