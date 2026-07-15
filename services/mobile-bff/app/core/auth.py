from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends
from jose import JWTError, jwt
import os

_DEFAULT_SECRET = "tripclip-secret-change-in-production"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", _DEFAULT_SECRET)
ALGORITHM = "HS256"

if SECRET_KEY == _DEFAULT_SECRET:
    import logging as _logging
    _logging.getLogger("mobile-bff.auth").warning(
        "⚠️  JWT_SECRET_KEY is using the insecure default value. "
        "Set JWT_SECRET_KEY in your environment before deploying."
    )
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError(
            "JWT_SECRET_KEY must not be the default value in production."
        )

bearer_scheme = HTTPBearer()


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> int:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
