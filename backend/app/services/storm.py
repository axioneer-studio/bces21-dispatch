"""Tempête automatique : chaque jour à l'heure réglée dans Administration
(Paramètres généraux, 3 h par défaut), dans le fuseau `APP_TIMEZONE` (heure
d'été comprise), le Dispatch est réinitialisé comme avec le bouton « Tempête »,
sans supprimer les interventions. Elle peut y être désactivée.

Réglages dans `application_settings` : `storm_enabled` et `storm_time` (HH:MM).
Une heure qui n'existe pas la nuit du passage à l'heure d'été (entre 2 h et
3 h) tombe une heure plus tard ce jour-là."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.controllers.dispatch import reset_dispatch
from app.database import SessionLocal
from app.models import ApplicationSetting

logger = logging.getLogger("bces.storm")

ENABLED_KEY = "storm_enabled"
TIME_KEY = "storm_time"
DEFAULT_TIME = time(3, 0)
# L'attente est découpée pour que la Tempête suive l'horloge, même recalée.
MAX_WAIT_SECONDS = 300

# Réveille la tâche quand les réglages changent.
_settings_changed = asyncio.Event()


@dataclass(frozen=True)
class StormSchedule:
    enabled: bool
    at: time


def storm_zone() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


async def read_schedule(db: AsyncSession) -> StormSchedule:
    enabled = await db.get(ApplicationSetting, ENABLED_KEY)
    stored_time = await db.get(ApplicationSetting, TIME_KEY)
    try:
        at = time.fromisoformat(stored_time.value) if stored_time else DEFAULT_TIME
    except ValueError:
        at = DEFAULT_TIME
    return StormSchedule(enabled=enabled is None or enabled.value == "true", at=at)


async def write_schedule(db: AsyncSession, schedule: StormSchedule) -> None:
    values = {
        ENABLED_KEY: "true" if schedule.enabled else "false",
        TIME_KEY: schedule.at.strftime("%H:%M"),
    }
    for key, value in values.items():
        setting = await db.get(ApplicationSetting, key)
        if setting is None:
            db.add(ApplicationSetting(key=key, value=value))
        else:
            setting.value = value
    await db.commit()
    _settings_changed.set()


def next_storm(now: datetime, at: time) -> datetime:
    """Prochaine Tempête strictement après `now`, dans le fuseau de `now`."""
    target = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    if target <= now:
        target = (now + timedelta(days=1)).replace(
            hour=at.hour, minute=at.minute, second=0, microsecond=0
        )
    return target


async def run_storm() -> None:
    async with SessionLocal() as db:
        await reset_dispatch(db)
    logger.info("Tempête automatique : Dispatch réinitialisé.")


async def _wait(stop_event: asyncio.Event, timeout: float | None) -> None:
    """Attend l'arrêt de l'API, un changement de réglages ou la fin du délai."""
    waiters = [
        asyncio.ensure_future(stop_event.wait()),
        asyncio.ensure_future(_settings_changed.wait()),
    ]
    try:
        await asyncio.wait(
            waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        for waiter in waiters:
            waiter.cancel()


async def storm_loop(stop_event: asyncio.Event) -> None:
    zone = storm_zone()
    while not stop_event.is_set():
        _settings_changed.clear()
        try:
            async with SessionLocal() as db:
                schedule = await read_schedule(db)
        except Exception:
            logger.exception(
                "Lecture des réglages de la Tempête automatique impossible."
            )
            await _wait(stop_event, MAX_WAIT_SECONDS)
            continue
        if not schedule.enabled:
            logger.info("Tempête automatique désactivée.")
            await _wait(stop_event, None)
            continue
        storm_at = next_storm(datetime.now(zone), schedule.at)
        logger.info("Tempête automatique programmée le %s.", storm_at.isoformat())
        while not stop_event.is_set() and not _settings_changed.is_set():
            # Écart calculé en UTC : entre deux heures d'un même fuseau, Python
            # soustrait les heures affichées et oublie le changement d'heure.
            remaining = (storm_at - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                try:
                    await run_storm()
                except Exception:
                    logger.exception("Échec de la Tempête automatique.")
                break
            await _wait(stop_event, min(remaining, MAX_WAIT_SECONDS))
