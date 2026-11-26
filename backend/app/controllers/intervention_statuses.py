"""Contrôleur des statuts d'intervention du Dispatch."""

import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dispatch import push_snapshot
from app.models import DispatchSlot, InterventionStatus, intervention_status_order
from app.schemas import (
    InterventionStatusOut,
    InterventionStatusRequest,
    MessageResponse,
)


def _slug(label: str) -> str:
    ascii_label = (
        unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_label.lower()).strip("_")[:28] or "statut"


async def _new_key(db: AsyncSession, label: str) -> str:
    """Clé stable dérivée du libellé, rendue unique (elle ne change plus ensuite)."""
    base = _slug(label)
    taken = set(
        (
            await db.execute(
                select(InterventionStatus.key).where(
                    InterventionStatus.key.like(f"{base}%")
                )
            )
        ).scalars()
    )
    key, number = base, 2
    while key in taken:
        key, number = f"{base}_{number}", number + 1
    return key


async def _get_status(db: AsyncSession, status_id: int) -> InterventionStatus:
    item = await db.get(InterventionStatus, status_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Statut introuvable.")
    return item


async def _ordered(db: AsyncSession) -> list[InterventionStatus]:
    """Les statuts, puis les lieux, chacun dans son ordre."""
    return list(
        (
            await db.execute(
                select(InterventionStatus).order_by(*intervention_status_order())
            )
        ).scalars()
    )


async def _next_order(db: AsyncSession, kind: str) -> int:
    last_order = await db.scalar(
        select(func.max(InterventionStatus.order)).where(
            InterventionStatus.kind == kind
        )
    )
    return (last_order + 1) if last_order is not None else 0


async def list_statuses(db: AsyncSession) -> list[InterventionStatusOut]:
    return [InterventionStatusOut.model_validate(item) for item in await _ordered(db)]


async def create_status(
    payload: InterventionStatusRequest, db: AsyncSession
) -> InterventionStatusOut:
    item = InterventionStatus(
        key=await _new_key(db, payload.label),
        label=payload.label,
        emoji=payload.emoji,
        color=payload.color,
        is_primo=payload.is_primo,
        kind=payload.kind,
        order=await _next_order(db, payload.kind),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    await push_snapshot(db)
    return InterventionStatusOut.model_validate(item)


async def update_status(
    status_id: int, payload: InterventionStatusRequest, db: AsyncSession
) -> InterventionStatusOut:
    """Modifie libellé, emoji, couleur, case « Primo Inter » et type ; la clé ne change
    pas. Un changement de type place l'entrée à la fin de son nouveau type."""
    item = await _get_status(db, status_id)
    if payload.kind != item.kind:
        item.order = await _next_order(db, payload.kind)
        item.kind = payload.kind
    item.label = payload.label
    item.emoji = payload.emoji
    item.color = payload.color
    item.is_primo = payload.is_primo
    await db.commit()
    await db.refresh(item)
    await push_snapshot(db)
    return InterventionStatusOut.model_validate(item)


async def move_status(
    status_id: int, direction: int, db: AsyncSession
) -> list[InterventionStatusOut]:
    """Monte (`direction=-1`) ou descend (`direction=1`) l'entrée dans la liste de son
    type (statuts ou lieux). Renvoie toute la liste, statuts puis lieux."""
    if direction not in (-1, 1):
        raise HTTPException(status_code=422, detail="La direction doit être -1 ou 1.")
    moved = await _get_status(db, status_id)
    items = [item for item in await _ordered(db) if item.kind == moved.kind]
    index = items.index(moved)
    target = index + direction
    if 0 <= target < len(items):
        items[index], items[target] = items[target], items[index]
        for order, item in enumerate(items):
            item.order = order
        await db.commit()
        await push_snapshot(db)
    return [InterventionStatusOut.model_validate(item) for item in await _ordered(db)]


async def delete_status(status_id: int, db: AsyncSession) -> MessageResponse:
    item = await _get_status(db, status_id)
    in_use = await db.scalar(
        select(DispatchSlot.id).where(DispatchSlot.status == item.key).limit(1)
    )
    if in_use is not None:
        raise HTTPException(
            status_code=409,
            detail="Une intervention du Dispatch a ce statut : changez-le avant de supprimer le statut.",
        )
    await db.delete(item)
    await db.commit()
    await push_snapshot(db)
    return MessageResponse(message="Statut supprimé.")
