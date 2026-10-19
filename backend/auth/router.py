import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.discord import (
    DiscordAPIError,
    build_authorize_url,
    exchange_code,
    fetch_me,
)
from auth.session import (
    get_session_cookie_name,
    issue_token,
)
from config import get_settings
from database import get_db
from deps import get_current_user
from models import User
from schemas import ProfileUpdateRequest, UserResponse

logger = logging.getLogger("bces.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])

_PENDING_STATES: dict[str, datetime] = {}
_PENDING_TTL_SECONDS = 60 * 10


def _register_state(state_value: str) -> None:
    _PENDING_STATES[state_value] = datetime.now(timezone.utc) + timedelta(
        seconds=_PENDING_TTL_SECONDS
    )


def _consume_state(state_value: str) -> bool:
    expiry = _PENDING_STATES.pop(state_value, None)
    if expiry is None:
        return False
    return datetime.now(timezone.utc) <= expiry


def _frontend_redirect(path: str, **params: str | None) -> str:
    base = get_settings().frontend_base_url.rstrip("/")
    query = urlencode({k: v for k, v in params.items() if v is not None})
    return f"{base}{path}?{query}" if query else f"{base}{path}"


def _set_session_cookie(response: Response, token: str, expires: datetime) -> None:
    settings = get_settings()
    response.set_cookie(
        key=get_session_cookie_name(),
        value=token,
        expires=expires,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        domain=settings.session_cookie_domain,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=get_session_cookie_name(),
        path="/",
    )


@router.get("/discord/start")
async def discord_start() -> RedirectResponse:
    settings = get_settings()
    if not settings.discord_client_id:
        return RedirectResponse(
            _frontend_redirect(
                "/",
                error="discord_misconfigured",
                error_description="Identifiants Discord manquants côté serveur.",
            ),
            status_code=302,
        )

    state = secrets.token_urlsafe(24)
    _register_state(state)
    authorize_url = build_authorize_url(state)
    return RedirectResponse(authorize_url, status_code=302)


async def _handle_callback(
    code: str,
    state_value: str,
    db: AsyncSession,
) -> RedirectResponse:
    if not _consume_state(state_value):
        return RedirectResponse(
            _frontend_redirect(
                "/", error="invalid_state", error_description="Session OAuth expirée ou invalide."
            ),
            status_code=302,
        )

    try:
        token_payload = await exchange_code(code)
        me = await fetch_me(token_payload["access_token"])
    except DiscordAPIError as exc:
        logger.warning("Discord OAuth error: %s", exc)
        return RedirectResponse(
            _frontend_redirect("/", error="discord_failed", error_description="Connexion Discord refusée."),
            status_code=302,
        )

    discord_id = str(me.get("id") or "")
    if not discord_id:
        return RedirectResponse(
            _frontend_redirect("/", error="discord_profile_unavailable"),
            status_code=302,
        )

    existing = await db.execute(
        select(User).where(User.discord_id == discord_id)
    )
    user = existing.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if user is None:
        deadline = now + timedelta(
            seconds=get_settings().profile_deadline_seconds
        )
        user = User(
            discord_id=discord_id,
            discord_username=me.get("username") or "Discord",
            discord_avatar=me.get("avatar"),
            rp_name_deadline=deadline,
        )
        db.add(user)

    user.discord_username = me.get("username") or user.discord_username
    avatar = me.get("avatar")
    if avatar:
        user.discord_avatar = avatar
    user.last_login_at = now

    await db.commit()
    await db.refresh(user)

    token, expires = issue_token(user.id)
    response = RedirectResponse(_status_redirect_target(user), status_code=302)
    _set_session_cookie(response, token, expires)
    return response


def _status_redirect_target(user: User) -> str:
    if user.prenom_rp and user.nom_rp:
        return _frontend_redirect("/dashboard")
    deadline_iso = (
        user.rp_name_deadline.isoformat()
        if user.rp_name_deadline
        else None
    )
    return _frontend_redirect("/complete-profile", deadline=deadline_iso)


@router.get("/discord/callback")
async def discord_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if error:
        return RedirectResponse(
            _frontend_redirect("/", error=error, error_description=error_description),
            status_code=302,
        )

    if not code or not state:
        return RedirectResponse(
            _frontend_redirect("/", error="missing_code"),
            status_code=302,
        )

    return await _handle_callback(code, state, db)


@router.post("/profile", response_model=UserResponse)
async def complete_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    user.prenom_rp = payload.prenomRP
    user.nom_rp = payload.nomRP
    user.rp_name_deadline = None
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/logout")
async def logout(response: Response) -> dict:
    _clear_session_cookie(response)
    return {"message": "Déconnecté."}