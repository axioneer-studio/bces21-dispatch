"""Routes de gestion de crise (couche transport mince)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import crisis as cc
from app.deps import get_current_user, get_db, require_page_access
from app.models import User
from app.schemas import (
    CrisisTeamRequest,
    CrisisVictimCreate,
    CrisisVictimOut,
    CrisisVictimUpdate,
    CrisisZipRequest,
    MessageResponse,
)

router = APIRouter(
    prefix="/api/crisis",
    tags=["crisis"],
    dependencies=[Depends(require_page_access("crisis"))],
)


@router.get("", response_model=cc.CrisisOut)
async def get_crisis(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> cc.CrisisOut:
    return await cc.get_crisis(db, _)


@router.put("/team", response_model=MessageResponse)
async def set_team(
    payload: CrisisTeamRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    return await cc.set_team(payload, _, db)


@router.put("/zip", response_model=MessageResponse)
async def set_zip(
    payload: CrisisZipRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    return await cc.set_zip(payload, db)


@router.post(
    "/victims",
    response_model=CrisisVictimOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_victim(
    payload: CrisisVictimCreate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CrisisVictimOut:
    return await cc.create_victim(payload, db)


@router.patch("/victims/{victim_id}", response_model=CrisisVictimOut)
async def update_victim(
    victim_id: int,
    payload: CrisisVictimUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CrisisVictimOut:
    return await cc.update_victim(victim_id, payload, user, db)


@router.delete("/victims/{victim_id}", response_model=MessageResponse)
async def delete_victim(
    victim_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    return await cc.delete_victim(victim_id, db)


@router.post("/reset", response_model=MessageResponse)
async def reset_crisis(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    return await cc.reset_crisis(db)
