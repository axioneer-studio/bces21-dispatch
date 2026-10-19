import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete

from config import get_settings
from database import SessionLocal
from models import User

logger = logging.getLogger("bces.cleanup")


async def purge_uncompleted_accounts() -> int:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        result = await session.execute(
            delete(User).where(
                User.prenom_rp.is_(None),
                User.nom_rp.is_(None),
                User.rp_name_deadline.is_not(None),
                User.rp_name_deadline <= now,
            )
        )
        await session.commit()
        count = result.rowcount or 0
    if count:
        logger.info("Purged %s uncompleted account(s).", count)
    return count


async def cleanup_loop(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    interval = max(30, settings.cleanup_interval_seconds)
    logger.info(
        "Background cleanup started (interval=%ss, deadline=%ss).",
        interval,
        settings.profile_deadline_seconds,
    )
    while not stop_event.is_set():
        try:
            await purge_uncompleted_accounts()
        except Exception:
            logger.exception("Cleanup iteration failed.")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue