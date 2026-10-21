"""Synchronisation des statuts LSES / SAFD depuis le Google Sheet
« Disponibilités LSES/BCES/SAFD ».

Logique calquée sur les formules du Sheet :
  B3 (LSES) = SI(B2="🎙️";"Ouvert";SI(B2="Off - 🎙️";"Fermé";SI(B2="🌙";"Mode nuit";"C'est bugué")))
  D3 (SAFD) = SI(D2>0;"Disponibles";"Indisponibles")
"""

import asyncio
import csv
import io
import logging

import httpx

from config import get_settings
from database import SessionLocal
from models import DispatchState

logger = logging.getLogger("bces.status_sync")

LSES_MIC = "\U0001F399"  # 🎙
LSES_MOON = "\U0001F319"  # 🌙


def map_lses(raw: str) -> str:
    value = (raw or "").strip()
    if value.lower().startswith("off"):
        return "ferme"
    if LSES_MOON in value:
        return "nuit"
    if LSES_MIC in value:
        return "ouvert"
    return "bug"


def map_safd(raw: str) -> str:
    value = (raw or "").strip().replace(",", ".")
    try:
        return "disponible" if float(value) > 0 else "indisponible"
    except ValueError:
        return "indisponible"


def parse_sheet(text: str) -> tuple[str, str] | None:
    """Retourne (lses_status, safd_status) depuis le CSV exporté du Sheet."""
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error:
        return None

    statut_row: list[str] | None = None
    for row in rows:
        if row and row[0].strip().lower() == "statut":
            statut_row = row
            break

    # Colonnes : A=label, B=LSES, C=BCES, D=SAFD
    if not statut_row or len(statut_row) < 4:
        return None
    return map_lses(statut_row[1]), map_safd(statut_row[3])


async def fetch_statuses() -> tuple[tuple[str, str] | None, float]:
    """Récupère (lses, safd) depuis le CSV exporté du Sheet.

    Retourne (statuts, délai_conseillé) : le délai est déduit des en-têtes
    Cache-Control / Retry-After, conformément aux recommandations Google
    (respecter les en-têtes de cache, backoff exponentiel sur 429/5xx).
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(settings.status_sheet_csv_url)

        if resp.status_code in (429, 503):
            retry_after = resp.headers.get("Retry-After")
            try:
                delay = max(30.0, float(retry_after)) if retry_after else 300.0
            except ValueError:
                delay = 300.0
            logger.warning(
                "Google Sheet : HTTP %s, nouvelle tentative dans %.0fs.",
                resp.status_code,
                delay,
            )
            return None, delay

        resp.raise_for_status()

        # Respecter Cache-Control: max-age si présent
        delay = float(settings.status_sync_interval_seconds)
        cache_control = resp.headers.get("Cache-Control", "")
        if "max-age=" in cache_control:
            try:
                max_age = float(cache_control.split("max-age=")[1].split(",")[0].strip())
                if max_age > 0:
                    delay = max(delay, max_age)
            except (ValueError, IndexError):
                pass

        return parse_sheet(resp.text), delay
    except Exception:
        logger.warning("Échec de la récupération du Google Sheet.", exc_info=True)
        return None, 60.0


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
            logger.info(
                "Statuts synchronisés depuis le Sheet : LSES=%s SAFD=%s", lses, safd
            )
    return changed, delay


async def status_sync_loop(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    interval = max(15, settings.status_sync_interval_seconds)
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
