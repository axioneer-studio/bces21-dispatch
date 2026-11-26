"""Routes de la morgue (couche transport mince)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import morgue as cg
from app.deps import get_current_user, get_db, require_page_access
from app.models import User
from app.services.training_rights import (
    FORENSIC_PERMISSION,
    require_training_permission,
)

router = APIRouter(
    prefix="/api/hospital/morgue",
    tags=["hospital"],
    dependencies=[Depends(require_page_access("hospital"))],
)


@router.get("", response_model=cg.MorgueOut)
async def get_morgue(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> cg.MorgueOut:
    return await cg.get_morgue(user, db)


@router.post("", response_model=cg.MorgueEntryOut, status_code=status.HTTP_201_CREATED)
async def create_entry(
    payload: cg.MorgueEntryCreate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> cg.MorgueEntryOut:
    return await cg.create_entry(payload, db)


@router.patch("/{entry_id}", response_model=cg.MorgueEntryOut)
async def update_entry(
    entry_id: int,
    payload: cg.MorgueEntryUpdate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> cg.MorgueEntryOut:
    return await cg.update_entry(entry_id, payload, db)


@router.put("/{entry_id}/autopsy", response_model=cg.MorgueEntryOut)
async def set_autopsy(
    entry_id: int,
    payload: cg.MorgueAutopsyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> cg.MorgueEntryOut:
    return await cg.set_autopsy(entry_id, payload, user, db)


@router.put("/{entry_id}/examiner", response_model=cg.MorgueEntryOut)
async def set_examiner(
    entry_id: int,
    payload: cg.MorgueExaminerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> cg.MorgueEntryOut:
    return await cg.set_examiner(entry_id, payload, user, db)


@router.post("/{entry_id}/incinerate", response_model=cg.MorgueEntryOut)
async def incinerate_entry(
    entry_id: int,
    _: User = Depends(require_training_permission(FORENSIC_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> cg.MorgueEntryOut:
    return await cg.incinerate_entry(entry_id, db)


@router.post("/{entry_id}/coffin", response_model=cg.MorgueEntryOut)
async def coffin_entry(
    entry_id: int,
    _: User = Depends(require_training_permission(FORENSIC_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> cg.MorgueEntryOut:
    return await cg.coffin_entry(entry_id, db)


@router.delete("/{entry_id}", response_model=cg.MessageResponse)
async def delete_entry(
    entry_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> cg.MessageResponse:
    return await cg.delete_entry(entry_id, db)
