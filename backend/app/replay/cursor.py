import base64
import binascii
import hashlib
import hmac
import json
import os
import time


CURSOR_SECONDS = 60 * 60
CURSOR_RESOURCE = "replay_sessions"


class InvalidReplayCursorError(ValueError):
    pass


def _secret() -> bytes:
    value = os.getenv("ESAS_SESSION_SECRET", "").strip()
    if len(value) < 32:
        raise RuntimeError("cursor signing is not configured securely")
    return value.encode()


def _encode_json(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def encode_replay_session_cursor(
    *,
    created_at: str,
    session_id: str,
    subject: str,
) -> str:
    encoded = _encode_json(
        {
            "v": 1,
            "resource": CURSOR_RESOURCE,
            "sub": subject,
            "created_at": created_at,
            "session_id": session_id,
            "exp": int(time.time()) + CURSOR_SECONDS,
        }
    )
    signature = hmac.new(_secret(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def decode_replay_session_cursor(
    cursor: str,
    *,
    subject: str,
) -> tuple[str, str]:
    try:
        encoded, signature = cursor.rsplit(".", 1)
        expected = hmac.new(
            _secret(), encoded.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        if payload["v"] != 1 or payload["resource"] != CURSOR_RESOURCE:
            raise ValueError("invalid cursor context")
        if payload["sub"] != subject:
            raise ValueError("invalid cursor subject")
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired cursor")
        created_at = str(payload["created_at"]).strip()
        session_id = str(payload["session_id"]).strip()
        if not created_at or not session_id:
            raise ValueError("incomplete cursor")
        return created_at, session_id
    except (
        KeyError,
        binascii.Error,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise InvalidReplayCursorError("invalid replay cursor") from error
