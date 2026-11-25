"""Contrôleur des fréquences radio : tirage aléatoire depuis le Dispatch."""

import random

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dispatch import push_snapshot
from app.models import DispatchState
from app.schemas import FrequencyKind, FrequencySettingOut
from app.services.frequency_settings import (
    LABELS,
    current_frequency,
    read_bounds,
    set_current_frequency,
)


async def _state(db: AsyncSession) -> DispatchState:
    state = await db.get(DispatchState, 1)
    if state is None:
        state = DispatchState(id=1)
        db.add(state)
        await db.flush()
    return state


async def _setting_out(db: AsyncSession, state: DispatchState, kind: FrequencyKind) -> FrequencySettingOut:
    bounds = await read_bounds(db, kind)
    return FrequencySettingOut(
        kind=kind, current=current_frequency(state, kind), min=bounds.min, max=bounds.max
    )


def _random_frequency(low: int, high: int, current: str | None) -> int:
    """Nombre entre les bornes (incluses), différent de l'actuel s'il y a le choix."""
    try:
        current_value = int(current) if current is not None else None
    except ValueError:
        current_value = None
    if high == low or current_value is None or not low <= current_value <= high:
        return random.randint(low, high)
    value = random.randint(low, high - 1)
    return value + 1 if value >= current_value else value


async def randomize_frequency(
    kind: FrequencyKind, db: AsyncSession
) -> FrequencySettingOut:
    bounds = await read_bounds(db, kind)
    if bounds.min is None or bounds.max is None:
        raise HTTPException(
            status_code=409,
            detail=f"Réglez d’abord les bornes de la « {LABELS[kind]} » dans Direction → Fréquences.",
        )
    state = await _state(db)
    set_current_frequency(
        state, kind, _random_frequency(bounds.min, bounds.max, current_frequency(state, kind))
    )
    await db.commit()
    await push_snapshot(db)
    return await _setting_out(db, state, kind)
