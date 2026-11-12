"""Fréquences radio : réglage dans Administration et tirage aléatoire depuis le Dispatch.

Chaque modification rediffuse le snapshot du Dispatch, qui affiche les
fréquences actuelles en direct.
"""

import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import require_admin, require_page_access
from dispatch import push_snapshot
from frequency_settings import (
    FREQUENCY_KINDS,
    LABELS,
    current_frequency,
    read_bounds,
    set_current_frequency,
    write_bounds,
)
from grade_permissions import require_grade_permission
from models import DispatchState, User
from schemas import FrequencyKind, FrequencySettingOut, FrequencySettingUpdateRequest

router = APIRouter(tags=["frequencies"])


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


@router.get("/api/admin/frequencies", response_model=list[FrequencySettingOut])
async def list_frequencies(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    state = await _state(db)
    await db.commit()
    return [await _setting_out(db, state, kind) for kind in FREQUENCY_KINDS]


@router.put("/api/admin/frequencies/{kind}", response_model=FrequencySettingOut)
async def update_frequency(
    kind: FrequencyKind,
    payload: FrequencySettingUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    state = await _state(db)
    await write_bounds(db, kind, payload.min, payload.max)
    set_current_frequency(state, kind, payload.current)
    await db.commit()
    await push_snapshot(db)
    return await _setting_out(db, state, kind)


@router.post("/api/dispatch/frequencies/{kind}/random", response_model=FrequencySettingOut)
async def randomize_frequency(
    kind: FrequencyKind,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
    __: User = Depends(require_grade_permission("dispatch.manage_state")),
):
    bounds = await read_bounds(db, kind)
    if bounds.min is None or bounds.max is None:
        raise HTTPException(
            status_code=409,
            detail=f"Réglez d’abord les bornes de la « {LABELS[kind]} » dans Administration → Paramètres.",
        )
    state = await _state(db)
    set_current_frequency(
        state, kind, _random_frequency(bounds.min, bounds.max, current_frequency(state, kind))
    )
    await db.commit()
    await push_snapshot(db)
    return await _setting_out(db, state, kind)
