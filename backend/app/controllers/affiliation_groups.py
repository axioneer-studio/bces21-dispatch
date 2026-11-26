"""Contrôleur des groupes d'appartenance (Administration, Crise, Morgue)."""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AffiliationGroup
from app.schemas import AffiliationGroupOut, AffiliationGroupRequest, MessageResponse


async def group_choices(db: AsyncSession) -> list[AffiliationGroupOut]:
    """Groupes triés par nom, avec leur couleur, pour les listes de la Crise et de la Morgue."""
    groups = (
        (
            await db.execute(
                select(AffiliationGroup).order_by(func.lower(AffiliationGroup.name))
            )
        )
        .scalars()
        .all()
    )
    return [AffiliationGroupOut.model_validate(group) for group in groups]


async def _ensure_name_available(
    db: AsyncSession, name: str, group_id: int | None = None
) -> None:
    filters = [func.lower(AffiliationGroup.name) == name.lower()]
    if group_id is not None:
        filters.append(AffiliationGroup.id != group_id)
    if (
        await db.scalar(select(AffiliationGroup.id).where(*filters).limit(1))
        is not None
    ):
        raise HTTPException(status_code=409, detail="Ce groupe existe déjà.")


async def _get_group(db: AsyncSession, group_id: int) -> AffiliationGroup:
    group = await db.get(AffiliationGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Groupe introuvable.")
    return group


async def list_groups(db: AsyncSession) -> list[AffiliationGroupOut]:
    return await group_choices(db)


async def create_group(
    payload: AffiliationGroupRequest, db: AsyncSession
) -> AffiliationGroupOut:
    await _ensure_name_available(db, payload.name)
    group = AffiliationGroup(name=payload.name, color=payload.color)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return AffiliationGroupOut.model_validate(group)


async def update_group(
    group_id: int, payload: AffiliationGroupRequest, db: AsyncSession
) -> AffiliationGroupOut:
    """Renomme le groupe et change sa couleur."""
    group = await _get_group(db, group_id)
    await _ensure_name_available(db, payload.name, group.id)
    group.name = payload.name
    group.color = payload.color
    await db.commit()
    await db.refresh(group)
    return AffiliationGroupOut.model_validate(group)


async def delete_group(group_id: int, db: AsyncSession) -> MessageResponse:
    group = await _get_group(db, group_id)
    await db.delete(group)
    await db.commit()
    return MessageResponse(message="Groupe supprimé.")
