"""
Web BFF — Auth route handler'ları.
Tüm Core API hataları web_error_wrapper aracılığıyla web dostu mesajlara çevrilir.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.internal_client import internal_client
import os
import time
import uuid
from jose import jwt

from app.core.error_wrapper import web_error_wrapper, raise_from_response
from app.core.auth import ACCESS_COOKIE, REFRESH_COOKIE, ALGORITHM, SECRET_KEY, get_access_claims, get_current_user_id

router  = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)
CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api:8000")
COOKIE_SECURE = os.getenv("APP_ENV") == "production"
REFRESH_MAX_AGE = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")) * 86400


def _clear_cookies(response: JSONResponse) -> JSONResponse:
    response.delete_cookie(ACCESS_COOKIE, path="/", secure=COOKIE_SECURE, httponly=True, samesite="lax")
    response.delete_cookie(REFRESH_COOKIE, path="/api/web/auth", secure=COOKIE_SECURE, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return response


def _session_response(data: dict) -> JSONResponse:
    """Only session metadata reaches JavaScript; raw tokens remain HttpOnly."""
    claims = jwt.decode(data["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    response = JSONResponse({"user_id": data["user_id"], "email": data["email"]})
    response.set_cookie(ACCESS_COOKIE, data["access_token"], max_age=max(1, int(claims["exp"] - time.time())),
                        path="/", secure=COOKIE_SECURE, httponly=True, samesite="lax")
    response.set_cookie(REFRESH_COOKIE, data["refresh_token"], max_age=REFRESH_MAX_AGE,
                        path="/api/web/auth", secure=COOKIE_SECURE, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return response


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    username: str | None = None


class AppleSignInRequest(BaseModel):
    identity_token: str
    full_name: str | None = None


class GoogleSignInRequest(BaseModel):
    code: str
    redirect_uri: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


async def _forward(path: str, body: dict, rid: str, client_ip: str | None = None) -> dict:
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            headers = {"x-forwarded-for": client_ip} if client_ip else {}
            resp = await client.post(f"{CORE_API_URL}{path}", json=body, headers=headers)
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
        return resp.json()


# NOT: get_remote_address, uvicorn --proxy-headers ile nginx'in ilettiği
# X-Forwarded-For/X-Real-IP'yi request.client.host olarak çözer (bkz. Dockerfile
# CMD) — bu yüzden burada gerçek son kullanıcı IP'sini yansıtır, BFF container
# adresini değil. Bu IP hem burada rate-limit anahtarı olarak, hem de core-api'ye
# iletilerek core-api'nin kendi login rate-limit'inin tüm kullanıcılar arasında
# paylaşılan tek bir kotaya düşmesini önlemek için kullanılır.
@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    rid = str(uuid.uuid4())[:8]
    return _session_response(await _forward("/internal/auth/login", body.model_dump(), rid, get_remote_address(request)))


@router.post("/register")
@limiter.limit("10/minute")
async def register(request: Request, body: RegisterRequest):
    rid = str(uuid.uuid4())[:8]
    return _session_response(await _forward("/internal/auth/register", body.model_dump(), rid, get_remote_address(request)))


@router.post("/apple")
@limiter.limit("5/minute")
async def apple_sign_in(request: Request, body: AppleSignInRequest):
    rid = str(uuid.uuid4())[:8]
    return _session_response(await _forward("/internal/auth/apple", body.model_dump(), rid, get_remote_address(request)))


@router.post("/google")
@limiter.limit("5/minute")
async def google_sign_in(request: Request, body: GoogleSignInRequest):
    rid = str(uuid.uuid4())[:8]
    return _session_response(await _forward("/internal/auth/google", body.model_dump(), rid, get_remote_address(request)))


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/forgot-password", body.model_dump(), rid, get_remote_address(request))


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, body: ResetPasswordRequest):
    rid = str(uuid.uuid4())[:8]
    return await _forward("/internal/auth/reset-password", body.model_dump(), rid, get_remote_address(request))


@router.get("/session")
async def session(request: Request):
    try:
        claims = get_access_claims(request)
    except HTTPException:
        code = "SESSION_EXPIRED" if request.cookies.get(REFRESH_COOKIE) else "NO_SESSION"
        response = JSONResponse(status_code=401, content={"code": code})
        response.headers["Cache-Control"] = "no-store"
        return response
    response = JSONResponse({"user_id": int(claims["sub"]), "email": claims.get("email", "")})
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/refresh")
@limiter.limit("20/minute")
async def refresh(request: Request):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Oturum sona erdi")
    rid = str(uuid.uuid4())[:8]
    return _session_response(await _forward("/internal/auth/refresh", {"refresh_token": token}, rid))


@router.post("/logout")
@limiter.limit("20/minute")
async def logout(request: Request):
    rid = str(uuid.uuid4())[:8]
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        try:
            await _forward("/internal/auth/logout", {"refresh_token": token}, rid)
        except Exception:
            pass  # Local session still must end if the upstream is unavailable.
    return _clear_cookies(JSONResponse({"status": "ok"}))


@router.delete("/account")
async def delete_account(request: Request, user_id: int = Depends(get_current_user_id)):
    rid = str(uuid.uuid4())[:8]
    async with web_error_wrapper(request_id=rid):
        async with internal_client(15.0) as client:
            resp = await client.delete(f"{CORE_API_URL}/internal/auth/account", headers={"x-user-id": str(user_id)})
        if resp.status_code >= 400:
            raise_from_response(resp, request_id=rid)
    return _clear_cookies(JSONResponse(resp.json()))
