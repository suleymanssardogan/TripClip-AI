"""Apple credentials stay server-side; provider payloads/tokens are never logged."""
import os
from datetime import datetime, timedelta, timezone
import httpx
import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException


def cipher():
    try:
        return Fernet(os.environ["APPLE_TOKEN_ENCRYPTION_KEY"].encode())
    except Exception:
        raise HTTPException(503, "Apple sign-in configuration unavailable") from None


def client_credentials():
    try:
        required = ["APPLE_CLIENT_ID", "APPLE_TEAM_ID", "APPLE_KEY_ID", "APPLE_PRIVATE_KEY"]
        if any(not os.environ.get(key, "").strip() for key in required):
            raise ValueError("Missing Apple credentials")
        client_id = os.environ["APPLE_CLIENT_ID"]
        now = datetime.now(timezone.utc)
        secret = jwt.encode(
            {"iss": os.environ["APPLE_TEAM_ID"], "iat": now,
             "exp": now + timedelta(minutes=5), "aud": "https://appleid.apple.com", "sub": client_id},
            os.environ["APPLE_PRIVATE_KEY"].replace("\\n", "\n"), algorithm="ES256",
            headers={"kid": os.environ["APPLE_KEY_ID"]},
        )
        return {"client_id": client_id, "client_secret": secret}
    except Exception:
        raise HTTPException(503, "Apple sign-in configuration unavailable") from None


def exchange(code, expected_subject, verify):
    encryption = cipher()  # Validate persistence configuration before consuming the code.
    credentials = client_credentials()
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post("https://appleid.apple.com/auth/token", data={
                **credentials, "grant_type": "authorization_code", "code": code})
        if response.status_code >= 500:
            raise HTTPException(503, "Apple sign-in temporarily unavailable")
        if response.status_code != 200:
            raise HTTPException(401, "Invalid Apple authorization code")
        payload = response.json()
        subject, _ = verify(payload["id_token"])
        if subject != expected_subject:
            raise HTTPException(401, "Apple credential mismatch")
        return encryption.encrypt(payload["refresh_token"].encode()).decode()
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, "Apple sign-in temporarily unavailable") from None


def revoke(encrypted_token):
    token = cipher().decrypt(encrypted_token.encode()).decode()
    with httpx.Client(timeout=10) as client:
        response = client.post("https://appleid.apple.com/auth/revoke", data={
            **client_credentials(), "token": token, "token_type_hint": "refresh_token"})
    if response.status_code != 200:
        raise RuntimeError("Apple revocation not acknowledged")


def dispatch_revocations():
    from app.core.database import SessionLocal
    from app.models.apple_revocation import AppleRevocation
    # Claim under row lock; bounded batch. Revocation is idempotent if commit is interrupted.
    with SessionLocal() as db:
        rows = db.query(AppleRevocation).filter(
            AppleRevocation.available_at <= datetime.utcnow()).order_by(AppleRevocation.id).with_for_update(
                skip_locked=True).limit(5).all()
        for row in rows:
            try:
                revoke(row.encrypted_token)
            except Exception:
                import logging
                logging.getLogger(__name__).warning("Apple revocation retry required | job_id=%s", row.id)
                row.attempts += 1
                row.available_at = datetime.utcnow() + timedelta(seconds=min(3600, 30 * 2 ** min(row.attempts, 7)))
            else:
                db.delete(row)  # No token retained after acknowledgement.
        db.commit()
