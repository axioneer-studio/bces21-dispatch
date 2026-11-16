"""Groupes d'appartenance, gérés dans Administration.

Ils sont proposés pour l'appartenance d'un blessé (Crise) et d'un défunt
(Morgue). La liste n'est pas exhaustive : ces fiches gardent leur appartenance en
texte libre, si bien que renommer ou supprimer un groupe ne les modifie pas.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import require_admin
from models import AffiliationGroup, User
from schemas import AffiliationGroupOut, AffiliationGroupRequest, MessageResponse

router = APIRouter(prefix="/api/admin/groups", tags=["administration"], dependencies=[Depends(require_admin)])


async def group_names(db: AsyncSession) -> list[str]:
    """Noms des groupes, triés, pour les listes de la Crise et de la Morgue."""
    return list(
        (await db.execute(select(AffiliationGroup.name).order_by(func.lower(AffiliationGroup.name)))).scalars()
    )


async def _ensure_name_available(db: AsyncSession, name: str, group_id: int | None = None) -> None:
    filters = [func.lower(AffiliationGroup.name) == name.lower()]
    if group_id is not None:
        filters.append(AffiliationGroup.id != group_id)
    if await db.scalar(select(AffiliationGroup.id).where(*filters).limit(1)) is not None:
        raise HTTPException(status_code=409, detail="Ce groupe existe déjà.")


async def _get_group(db: AsyncSession, group_id: int) -> AffiliationGroup:
    group = await db.get(AffiliationGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Groupe introuvable.")
    return group


@router.get("", response_model=list[AffiliationGroupOut])
async def list_groups(db: AsyncSession = Depends(get_db)):
    groups = (
        await db.execute(select(AffiliationGroup).order_by(func.lower(AffiliationGroup.name)))
    ).scalars().all()
    return [AffiliationGroupOut.model_validate(group) for group in groups]


@router.post("", response_model=AffiliationGroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(payload: AffiliationGroupRequest, db: AsyncSession = Depends(get_db)):
    await _ensure_name_available(db, payload.name)
    group = AffiliationGroup(name=payload.name)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return AffiliationGroupOut.model_validate(group)


@router.patch("/{group_id}", response_model=AffiliationGroupOut)
async def rename_group(
    group_id: int,
    payload: AffiliationGroupRequest,
    db: AsyncSession = Depends(get_db),
):
    group = await _get_group(db, group_id)
    await _ensure_name_available(db, payload.name, group.id)
    group.name = payload.name
    await db.commit()
    await db.refresh(group)
    return AffiliationGroupOut.model_validate(group)


@router.delete("/{group_id}", response_model=MessageResponse)
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db)):
    group = await _get_group(db, group_id)
    await db.delete(group)
    await db.commit()
    return {"message": "Groupe supprimé."}
