"""Contrôleur de l'agenda : événements."""

import calendar
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import AgendaEvent, Employee
from app.schemas import (
    AgendaEventCreate,
    AgendaEventOut,
    AgendaEventUpdate,
    MessageResponse,
)


async def list_events(
    start: datetime | None,
    end: datetime | None,
    db: AsyncSession,
) -> list[AgendaEventOut]:
    query = select(AgendaEvent).order_by(AgendaEvent.starts_at)
    if start:
        query = query.where(AgendaEvent.starts_at >= start)
    if end:
        query = query.where(AgendaEvent.starts_at < end)
    events = (await db.execute(query)).scalars().all()
    result = [AgendaEventOut.model_validate(event) for event in events]

    timezone_info = ZoneInfo(get_settings().app_timezone)
    now = datetime.now(timezone_info)
    start_day = (
        start.astimezone(timezone_info).date()
        if start and start.tzinfo
        else start.date() if start else now.date()
    )
    end_day = (
        end.astimezone(timezone_info).date()
        if end and end.tzinfo
        else end.date() if end else date(now.year + 3, 1, 1)
    )
    employees = (
        (
            await db.execute(
                select(Employee).where(
                    Employee.is_active.is_(True), Employee.birth_date.is_not(None)
                )
            )
        )
        .scalars()
        .all()
    )
    generated_at = datetime.now(timezone.utc)
    for employee in employees:
        birth_date = employee.birth_date
        if birth_date is None:
            continue
        first_year = max(start_day.year, birth_date.year)
        for year in range(first_year, end_day.year + 1):
            month_end = min(
                birth_date.day, calendar.monthrange(year, birth_date.month)[1]
            )
            birthday = date(year, birth_date.month, month_end)
            if birthday < start_day or birthday >= end_day:
                continue
            age = year - birth_date.year
            name = f"{employee.first_name} {employee.last_name}".strip()
            result.append(
                AgendaEventOut(
                    id=-(employee.id * 10000 + year),
                    title=f"Anniversaire de {name}",
                    starts_at=datetime.combine(birthday, time(9), tzinfo=timezone_info),
                    ends_at=None,
                    description=f"Anniversaire de {name} : {age} ans.",
                    color="#d69e38",
                    created_at=generated_at,
                    updated_at=generated_at,
                    is_automatic=True,
                )
            )
    return sorted(result, key=lambda event: (event.starts_at, event.id))


async def create_event(payload: AgendaEventCreate, db: AsyncSession) -> AgendaEventOut:
    if payload.ends_at and payload.ends_at < payload.starts_at:
        raise HTTPException(status_code=422, detail="La fin doit être après le début.")
    event = AgendaEvent(**payload.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return AgendaEventOut.model_validate(event)


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
    return AgendaEventOut.model_validate(event)


async def delete_event(event_id: int, db: AsyncSession) -> MessageResponse:
    event = await db.get(AgendaEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable.")
    await db.delete(event)
    await db.commit()
    return MessageResponse(message="Événement supprimé.")
