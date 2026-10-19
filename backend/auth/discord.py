from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from config import get_settings

DISCORD_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_ME_URL = "https://discord.com/api/users/@me"


class DiscordAPIError(Exception):
    pass


def build_authorize_url(state: str) -> str:
    settings = get_settings()
    if not settings.discord_client_id:
        raise HTTPException(
            status_code=500,
            detail="DISCORD_CLIENT_ID non configuré côté serveur.",
        )

    params = {
        "client_id": settings.discord_client_id,
        "redirect_uri": settings.discord_redirect_uri,
        "response_type": "code",
        "scope": " ".join(settings.discord_scope_list),
        "state": state,
        "prompt": "consent",
    }
    return f"{DISCORD_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    settings = get_settings()
    data = {
        "client_id": settings.discord_client_id,
        "client_secret": settings.discord_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.discord_redirect_uri,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            DISCORD_TOKEN_URL, data=data, headers=headers
        )

    if response.status_code != 200:
        raise DiscordAPIError(
            f"Échange du code OAuth échoué ({response.status_code}): {response.text}"
        )

    payload = response.json()
    if "access_token" not in payload:
        raise DiscordAPIError("Réponse OAuth Discord invalide (pas d'access_token).")
    return payload


async def fetch_me(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(DISCORD_ME_URL, headers=headers)

    if response.status_code != 200:
        raise DiscordAPIError(
            f"Récupération du profil Discord échouée ({response.status_code}): {response.text}"
        )

    return response.json()