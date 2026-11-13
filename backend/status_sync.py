"""Synchronisation des statuts LSES / SAFD depuis le Google Sheet
« Disponibilités LSES/BCES/SAFD » (configuration de lecture).

Logique calquée sur les formules du Sheet :
  B3 (LSES) = SI(B2="🎙️";"Ouvert";SI(B2="Off - 🎙️";"Fermé";SI(B2="🌙";"Mode nuit";"C'est bugué")))
  D3 (SAFD) = SI(D2>0;"Disponibles";"Indisponibles")

La configuration de lecture (spreadsheet, onglet, activation) est lue depuis la
base de données (ApplicationSetting) et les valeurs sont récupérées via l'API
Google Sheets (GoogleSheetsService), jamais depuis une URL CSV en dur.
"""

import asyncio
import logging

from database import SessionLocal
from google_sheets_service import (
    DEFAULT_S3_KEY,
    GoogleSheetsError,
    GoogleSheetsService,
    load_settings_from_db,
)
from models import DispatchState

logger = logging.getLogger("bces.status_sync")

STATUS_SYNC_INTERVAL_SECONDS = 10

LSES_MIC = "\U0001F399"  # 🎙
LSES_MOON = "\U0001F319"  # 🌙


def map_lses(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return "bug"
    lower = value.lower()
    if lower.startswith("off") or lower == "fermé" or lower == "ferme":
        return "ferme"
    if "nuit" in lower:
        return "nuit"
    if lower == "ouvert":
        return "ouvert"
    if LSES_MIC in value:
        return "ouvert"
    if LSES_MOON in value:
        return "nuit"
    return "bug"


def map_safd(raw: str) -> str:
    value = (raw or "").strip()
    lower = value.lower()
    if lower in ("disponibles", "disponible", "oui", "yes", "true", "1"):
        return "disponible"
    if lower in ("indisponibles", "indisponible", "non", "no", "false", "0"):
        return "indisponible"
    if not value:
        return "bug"
    try:
        return "disponible" if float(value.replace(",", ".")) > 0 else "indisponible"
    except ValueError:
        return "bug"


async def _load_read_settings() -> dict:
    """Charge la configuration de lecture Google Sheets depuis la base de données."""
    async with SessionLocal() as db:
        return await load_settings_from_db(db)


async def fetch_statuses() -> tuple[tuple[str, str] | None, float]:
    """Récupère (lses, safd) depuis les cellules configurées du Google Sheet de lecture.

    Retourne (statuts, délai_conseillé).
    """
    settings = await _load_read_settings()

    if not bool(settings.get("read_enabled")):
        return None, float(STATUS_SYNC_INTERVAL_SECONDS)

    spreadsheet_id = str(settings.get("read_spreadsheet_id") or "")
    sheet_name = str(settings.get("read_sheet_name") or "")
    if not spreadsheet_id or not sheet_name:
        logger.debug("Google Sheets lecture non configuré, synchronisation ignorée.")
        return None, float(STATUS_SYNC_INTERVAL_SECONDS)

    service = GoogleSheetsService(
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        timeout_seconds=int(settings.get("timeout_seconds", 15)),
        s3_key=str(settings.get("s3_key", DEFAULT_S3_KEY)),
    )
    if not service.configured:
        logger.debug(
            "Google Sheets lecture non configuré (credentials absents), synchronisation ignorée."
        )
        return None, float(STATUS_SYNC_INTERVAL_SECONDS)

    lses_cell = str(settings.get("read_lses_cell") or "B3")
    safd_cell = str(settings.get("read_safd_cell") or "D3")

    try:
        lses_raw = await service.read_cell(lses_cell)
        safd_raw = await service.read_cell(safd_cell)
    except GoogleSheetsError as exc:
        logger.warning("Échec de la lecture Google Sheets (statuts) : %s", exc)
        return None, 60.0

    return (map_lses(lses_raw), map_safd(safd_raw)), float(STATUS_SYNC_INTERVAL_SECONDS)


async def sync_statuses() -> tuple[bool, float]:
    """Met à jour lses_status / safd_status si le Sheet a changé.

    Retourne (modifié, délai_avant_prochain_appel).
    """
    from dispatch import push_snapshot  # import local pour éviter une référence circulaire

    statuses, delay = await fetch_statuses()
    if not statuses:
        return False, delay
    lses, safd = statuses

    async with SessionLocal() as db:
        state = await db.get(DispatchState, 1)
        if not state:
            state = DispatchState(id=1)
            db.add(state)
        changed = state.lses_status != lses or state.safd_status != safd
        if changed:
            state.lses_status = lses
            state.safd_status = safd
            await db.commit()
            await push_snapshot(db)
            logger.debug(
                "Statuts synchronisés depuis le Sheet : LSES=%s SAFD=%s", lses, safd
            )
    return changed, delay


async def status_sync_loop(stop_event: asyncio.Event) -> None:
    interval = max(15, STATUS_SYNC_INTERVAL_SECONDS)
    logger.info("Synchronisation Google Sheet démarrée (interval=%ss).", interval)
    while not stop_event.is_set():
        delay = float(interval)
        try:
            _, advised = await sync_statuses()
            if advised > 0:
                delay = advised
        except Exception:
            logger.exception("Échec de l'itération de synchronisation.")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            continue
