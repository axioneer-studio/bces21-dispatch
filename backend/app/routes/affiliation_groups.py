"""Routes des groupes d'appartenance (couche transport mince)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import affiliation_groups as cg
from app.deps import get_db, require_admin

router = APIRouter(
    prefix="/api/admin/groups",
    tags=["administration"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[cg.AffiliationGroupOut])
async def list_groups(db: AsyncSession = Depends(get_db)) -> list[cg.AffiliationGroupOut]:
    return await cg.list_groups(db)


@router.post(
    "", response_model=cg.AffiliationGroupOut, status_code=status.HTTP_201_CREATED
)
async def create_group(
    payload: cg.AffiliationGroupRequest, db: AsyncSession = Depends(get_db)
) -> cg.AffiliationGroupOut:
    return await cg.create_group(payload, db)


@router.patch("/{group_id}", response_model=cg.AffiliationGroupOut)
async def update_group(
    group_id: int,
    payload: cg.AffiliationGroupRequest,
    db: AsyncSession = Depends(get_db),
) -> cg.AffiliationGroupOut:
    return await cg.update_group(group_id, payload, db)


@router.delete("/{group_id}", response_model=cg.MessageResponse)
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db)) -> cg.MessageResponse:
    return await cg.delete_group(group_id, db)
