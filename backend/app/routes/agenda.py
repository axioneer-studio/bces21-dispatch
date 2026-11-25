"""Routes de l'agenda (couche transport mince)."""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import agenda as cag
from app.deps import get_current_user, get_db, require_page_access
from app.models import User
from app.schemas import (
    AgendaEventCreate,
    AgendaEventOut,
    AgendaEventUpdate,
    MessageResponse,
)
from app.services.grade_permissions import require_grade_permission

router = APIRouter(
    prefix="/api/agenda",
    tags=["agenda"],
    dependencies=[Depends(require_page_access("agenda"))],
)


@router.get("/events", response_model=list[AgendaEventOut])
async def list_events(
    start: datetime | None = None,
    end: datetime | None = None,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgendaEventOut]:
    return await cag.list_events(start, end, db)


@router.post(
    "/events", response_model=AgendaEventOut, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_grade_permission("agenda.manage_events"))],
)
async def create_event(
    payload: AgendaEventCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("agenda")),
) -> AgendaEventOut:
    return await cag.create_event(payload, db)


@router.patch(
    "/events/{event_id}",
    response_model=AgendaEventOut,
    dependencies=[Depends(require_grade_permission("agenda.manage_events"))],
)
async def update_event(
    event_id: int,
    payload: AgendaEventUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("agenda")),
) -> AgendaEventOut:
    return await cag.update_event(event_id, payload, db)


@router.delete(
    "/events/{event_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_grade_permission("agenda.manage_events"))],
)
async def delete_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("agenda")),
) -> MessageResponse:
    return await cag.delete_event(event_id, db)
