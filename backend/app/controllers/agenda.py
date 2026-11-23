"""Contrôleur de l'agenda : événements."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgendaEvent
from app.schemas import AgendaEventCreate, AgendaEventOut, AgendaEventUpdate, MessageResponse
from app.services.grade_permissions import require_grade_permission


async def list_events(
    start: object | None,
    end: object | None,
    db: AsyncSession,
) -> list[AgendaEventOut]:
    query = select(AgendaEvent).order_by(AgendaEvent.starts_at)
    if start:
        query = query.where(AgendaEvent.starts_at >= start)
    if end:
        query = query.where(AgendaEvent.starts_at < end)
    return (await db.execute(query)).scalars().all()


async def create_event(
    payload: AgendaEventCreate, db: AsyncSession
) -> AgendaEventOut:
    if payload.ends_at and payload.ends_at < payload.starts_at:
        raise HTTPException(status_code=422, detail="La fin doit être après le début.")
    event = AgendaEvent(**payload.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def update_event(
    event_id: int, payload: AgendaEventUpdate, db: AsyncSession
) -> AgendaEventOut:
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


async def delete_event(event_id: int, db: AsyncSession) -> MessageResponse:
    event = await db.get(AgendaEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable.")
    await db.delete(event)
    await db.commit()
    return {"message": "Événement supprimé."}
