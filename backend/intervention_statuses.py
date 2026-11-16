"""Statuts d'intervention du Dispatch, gérés dans Administration.

Chaque entrée est un statut (Patrouille, Inter…) ou un lieu (BCES, Zombie…), avec
un libellé, un emoji, une couleur facultative et une case « Primo Inter » : une
intervention à un statut « Primo Inter » est liée à la page Crise (voir
crisis_link). Les statuts sont toujours proposés avant les lieux. Les changements
sont poussés en direct au Dispatch.
"""

import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import require_admin
from dispatch import push_snapshot
from models import DispatchSlot, InterventionStatus, intervention_status_order
from schemas import InterventionStatusOut, InterventionStatusRequest, MessageResponse

router = APIRouter(
    prefix="/api/admin/intervention-statuses",
    tags=["administration"],
    dependencies=[Depends(require_admin)],
)


def _slug(label: str) -> str:
    ascii_label = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_label.lower()).strip("_")[:28] or "statut"


async def _new_key(db: AsyncSession, label: str) -> str:
    """Clé stable dérivée du libellé, rendue unique (elle ne change plus ensuite)."""
    base = _slug(label)
    taken = set(
        (await db.execute(select(InterventionStatus.key).where(InterventionStatus.key.like(f"{base}%")))).scalars()
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
    return list((await db.execute(select(InterventionStatus).order_by(*intervention_status_order()))).scalars())


async def _next_order(db: AsyncSession, kind: str) -> int:
    last_order = await db.scalar(select(func.max(InterventionStatus.order)).where(InterventionStatus.kind == kind))
    return (last_order + 1) if last_order is not None else 0


@router.get("", response_model=list[InterventionStatusOut])
async def list_statuses(db: AsyncSession = Depends(get_db)):
    return [InterventionStatusOut.model_validate(item) for item in await _ordered(db)]


@router.post("", response_model=InterventionStatusOut, status_code=status.HTTP_201_CREATED)
async def create_status(payload: InterventionStatusRequest, db: AsyncSession = Depends(get_db)):
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


@router.patch("/{status_id}", response_model=InterventionStatusOut)
async def update_status(
    status_id: int,
    payload: InterventionStatusRequest,
    db: AsyncSession = Depends(get_db),
):
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


@router.post("/{status_id}/move", response_model=list[InterventionStatusOut])
async def move_status(status_id: int, direction: int, db: AsyncSession = Depends(get_db)):
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


@router.delete("/{status_id}", response_model=MessageResponse)
async def delete_status(status_id: int, db: AsyncSession = Depends(get_db)):
    item = await _get_status(db, status_id)
    in_use = await db.scalar(select(DispatchSlot.id).where(DispatchSlot.status == item.key).limit(1))
    if in_use is not None:
        raise HTTPException(
            status_code=409,
            detail="Une intervention du Dispatch a ce statut : changez-le avant de supprimer le statut.",
        )
    await db.delete(item)
    await db.commit()
    await push_snapshot(db)
    return {"message": "Statut supprimé."}
