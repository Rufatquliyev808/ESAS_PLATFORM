import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field


SESSION_SECONDS = 8 * 60 * 60
_bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    user_code: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=200)


def _credential(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    return value


def _encode(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(value: str) -> dict[str, object]:
    padding = "=" * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode(value + padding))


def create_session(login: LoginRequest) -> dict[str, object]:
    expected_code = _credential("ESAS_USER_CODE")
    expected_password = _credential("ESAS_USER_PASSWORD")

    if not (
        secrets.compare_digest(login.user_code, expected_code)
        and secrets.compare_digest(login.password, expected_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    expires_at = int(time.time()) + SESSION_SECONDS
    payload = _encode({"sub": expected_code, "exp": expires_at})
    signature = hmac.new(
        _credential("ESAS_SESSION_SECRET").encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        "access_token": f"{payload}.{signature}",
        "token_type": "bearer",
        "expires_in": SESSION_SECONDS,
    }


def require_dashboard_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        payload, signature = credentials.credentials.rsplit(".", 1)
        expected_signature = hmac.new(
            _credential("ESAS_SESSION_SECRET").encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not secrets.compare_digest(signature, expected_signature):
            raise ValueError("Invalid signature")

        decoded = _decode(payload)
        if int(decoded["exp"]) < int(time.time()):
            raise ValueError("Expired token")
        return str(decoded["sub"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        ) from None
