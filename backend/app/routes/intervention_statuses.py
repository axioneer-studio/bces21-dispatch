"""Routes des statuts d'intervention (couche transport mince)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import intervention_statuses as cis
from app.deps import get_db, require_admin

router = APIRouter(
    prefix="/api/admin/intervention-statuses",
    tags=["administration"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[cis.InterventionStatusOut])
async def list_statuses(db: AsyncSession = Depends(get_db)) -> list[cis.InterventionStatusOut]:
    return await cis.list_statuses(db)


@router.post(
    "", response_model=cis.InterventionStatusOut, status_code=status.HTTP_201_CREATED
)
async def create_status(
    payload: cis.InterventionStatusRequest, db: AsyncSession = Depends(get_db)
) -> cis.InterventionStatusOut:
    return await cis.create_status(payload, db)


@router.patch("/{status_id}", response_model=cis.InterventionStatusOut)
async def update_status(
    status_id: int,
    payload: cis.InterventionStatusRequest,
    db: AsyncSession = Depends(get_db),
) -> cis.InterventionStatusOut:
    return await cis.update_status(status_id, payload, db)


@router.post("/{status_id}/move", response_model=list[cis.InterventionStatusOut])
async def move_status(
    status_id: int, direction: int, db: AsyncSession = Depends(get_db)
) -> list[cis.InterventionStatusOut]:
    return await cis.move_status(status_id, direction, db)


@router.delete("/{status_id}", response_model=cis.MessageResponse)
async def delete_status(status_id: int, db: AsyncSession = Depends(get_db)) -> cis.MessageResponse:
    return await cis.delete_status(status_id, db)
