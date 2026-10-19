from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, HTTPException, status

from config import get_settings


def issue_token(user_id: int) -> tuple[str, datetime]:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(
        seconds=settings.session_ttl_seconds
    )
    payload = {
        "sub": str(user_id),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expires.timestamp()),
        "type": "session",
    }
    token = jwt.encode(
        payload, settings.session_secret, algorithm="HS256"
    )
    return token, expires


def decode_token(token: str) -> int:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.session_secret,
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide.",
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide.",
        )
    try:
        return int(sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide.",
        ) from exc


def get_session_cookie_name() -> str:
    return get_settings().session_cookie_name


async def current_user_id(
    bces_session: str | None = Cookie(default=None),
) -> int:
    if not bces_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié.",
        )
    return decode_token(bces_session)