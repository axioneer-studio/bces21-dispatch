"""Tempête automatique : chaque nuit à 3 h, heure de Paris (`APP_TIMEZONE`,
heure d'été comprise), le Dispatch est réinitialisé comme avec le bouton
« Tempête », sans supprimer les interventions."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.controllers.dispatch import reset_dispatch
from app.database import SessionLocal

logger = logging.getLogger("bces.storm")

STORM_HOUR = 3
# L'attente est découpée pour que la Tempête suive l'horloge, même recalée.
MAX_WAIT_SECONDS = 300


def next_storm(now: datetime) -> datetime:
    """Prochaine Tempête strictement après `now`, dans le fuseau de `now`."""
    target = now.replace(hour=STORM_HOUR, minute=0, second=0, microsecond=0)
    if target <= now:
        target = (now + timedelta(days=1)).replace(hour=STORM_HOUR, minute=0, second=0, microsecond=0)
    return target


async def run_storm() -> None:
    async with SessionLocal() as db:
        await reset_dispatch(db)
    logger.info("Tempête automatique : Dispatch réinitialisé.")


async def storm_loop(stop_event: asyncio.Event) -> None:
    zone = ZoneInfo(get_settings().app_timezone)
    storm_at = next_storm(datetime.now(zone))
    logger.info("Tempête automatique programmée le %s.", storm_at.isoformat())
    while not stop_event.is_set():
        # Écart calculé en UTC : entre deux heures d'un même fuseau, Python
        # soustrait les heures affichées et oublie le changement d'heure.
        remaining = (storm_at - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            try:
                await run_storm()
            except Exception:
                logger.exception("Échec de la Tempête automatique.")
            storm_at = next_storm(datetime.now(zone))
            logger.info("Prochaine Tempête automatique le %s.", storm_at.isoformat())
            continue
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=min(remaining, MAX_WAIT_SECONDS))
        except TimeoutError:
            continue
