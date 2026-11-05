from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import require_page_access
from grade_permissions import require_grade_permission
from models import AgendaEvent, User
from schemas import AgendaEventCreate, AgendaEventOut, AgendaEventUpdate, MessageResponse

router = APIRouter(prefix="/api/agenda", tags=["agenda"])


@router.get("/events", response_model=list[AgendaEventOut])
async def list_events(
    start: datetime | None = None,
    end: datetime | None = None,
    _: User = Depends(require_page_access("agenda")),
    db: AsyncSession = Depends(get_db),
):
    query = select(AgendaEvent).order_by(AgendaEvent.starts_at)
    if start:
        query = query.where(AgendaEvent.starts_at >= start)
    if end:
        query = query.where(AgendaEvent.starts_at < end)
    return (await db.execute(query)).scalars().all()


@router.post("/events", response_model=AgendaEventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: AgendaEventCreate,
    _: User = Depends(require_page_access("agenda")),
    __: User = Depends(require_grade_permission("agenda.manage_events")),
    db: AsyncSession = Depends(get_db),
):
    if payload.ends_at and payload.ends_at < payload.starts_at:
        raise HTTPException(status_code=422, detail="La fin doit être après le début.")
    event = AgendaEvent(**payload.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.patch("/events/{event_id}", response_model=AgendaEventOut)
async def update_event(
    event_id: int,
    payload: AgendaEventUpdate,
    _: User = Depends(require_page_access("agenda")),
    __: User = Depends(require_grade_permission("agenda.manage_events")),
    db: AsyncSession = Depends(get_db),
):
    event = await db.get(AgendaEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    if event.ends_at and event.ends_at < event.starts_at:
        raise HTTPException(status_code=422, detail="La fin doit être après le début.")
    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/events/{event_id}", response_model=MessageResponse)
async def delete_event(
    event_id: int,
    _: User = Depends(require_page_access("agenda")),
    __: User = Depends(require_grade_permission("agenda.manage_events")),
    db: AsyncSession = Depends(get_db),
):
    event = await db.get(AgendaEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable.")
    await db.delete(event)
    await db.commit()
    return {"message": "Événement supprimé."}
