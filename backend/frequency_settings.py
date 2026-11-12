"""Fréquences radio : bornes réglées dans Administration → Paramètres.

Les bornes sont des paramètres de l'application (table `application_settings`),
sans valeur par défaut : tant qu'elles ne sont pas réglées, elles valent `None`.
La fréquence actuelle reste dans l'état du Dispatch, affiché en direct.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from models import ApplicationSetting, DispatchState
from schemas import FrequencyBounds, FrequencyKind

FREQUENCY_KINDS: tuple[FrequencyKind, ...] = ("radio", "shared")

# Colonne de l'état du Dispatch qui contient la fréquence actuelle.
STATE_COLUMNS: dict[FrequencyKind, str] = {"radio": "freq_147", "shared": "freq_570"}

LABELS: dict[FrequencyKind, str] = {
    "radio": "Fréquence Radio BCES",
    "shared": "Fréquence Radio Commune",
}


def _setting_key(kind: FrequencyKind, bound: str) -> str:
    return f"{kind}_frequency_{bound}"


def _parse_int(setting: ApplicationSetting | None) -> int | None:
    if setting is None:
        return None
    try:
        return int(setting.value)
    except (TypeError, ValueError):
        return None


async def read_bounds(db: AsyncSession, kind: FrequencyKind) -> FrequencyBounds:
    return FrequencyBounds(
        min=_parse_int(await db.get(ApplicationSetting, _setting_key(kind, "min"))),
        max=_parse_int(await db.get(ApplicationSetting, _setting_key(kind, "max"))),
    )


async def read_all_bounds(db: AsyncSession) -> dict[FrequencyKind, FrequencyBounds]:
    return {kind: await read_bounds(db, kind) for kind in FREQUENCY_KINDS}


async def write_bounds(db: AsyncSession, kind: FrequencyKind, low: int, high: int) -> None:
    for bound, value in (("min", low), ("max", high)):
        key = _setting_key(kind, bound)
        setting = await db.get(ApplicationSetting, key)
        if setting is None:
            db.add(ApplicationSetting(key=key, value=str(value)))
        else:
            setting.value = str(value)


def current_frequency(state: DispatchState, kind: FrequencyKind) -> str:
    return getattr(state, STATE_COLUMNS[kind])


def set_current_frequency(state: DispatchState, kind: FrequencyKind, value: int) -> None:
    setattr(state, STATE_COLUMNS[kind], str(value))
