"""Contrôleur Direction : grades, radios et fréquences."""

import json

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dispatch import push_employees_changed, push_snapshot, sorted_radios
from app.models import DispatchRadio, DispatchState, Employee, Grade, User
from app.schemas import (
    DirectionRadioCreateRequest,
    DirectionRadioOut,
    DirectionRadioUpdateRequest,
    FrequencyKind,
    FrequencySettingOut,
    FrequencySettingUpdateRequest,
    GradeCreateRequest,
    GradeOut,
    GradeUpdateRequest,
    MessageResponse,
)
from app.services.frequency_settings import (
    FREQUENCY_KINDS,
    LABELS,
    current_frequency,
    read_bounds,
    set_current_frequency,
    write_bounds,
)
from app.services.grade_permissions import GRADE_PERMISSION_CATALOG


def _validated_permissions(permissions: list[str] | None) -> list[str]:
    if permissions is None:
        return []
    unknown = set(permissions) - GRADE_PERMISSION_CATALOG.keys()
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Permissions inconnues : {', '.join(sorted(unknown))}.",
        )
    return list(dict.fromkeys(permissions))


async def _grade_out(db: AsyncSession, grade: Grade) -> GradeOut:
    try:
        permissions = json.loads(grade.permissions or "[]")
    except (TypeError, ValueError):
        permissions = []
    count = await db.scalar(
        select(func.count(Employee.id)).where(Employee.grade_id == grade.id)
    )
    return GradeOut(
        id=grade.id,
        name=grade.name,
        level=grade.level,
        color=grade.color,
        permissions=_validated_permissions(permissions if isinstance(permissions, list) else []),
        is_direction=grade.is_direction,
        employees_count=count or 0,
    )


async def list_grade_permissions() -> list[dict]:
    return [
        {"key": key, "label": label}
        for key, label in GRADE_PERMISSION_CATALOG.items()
    ]


async def list_grades(db: AsyncSession) -> list[GradeOut]:
    grades = (
        await db.execute(select(Grade).order_by(Grade.level.asc(), Grade.name.asc()))
    ).scalars().all()
    return [await _grade_out(db, grade) for grade in grades]


async def create_grade(
    payload: GradeCreateRequest, db: AsyncSession
) -> GradeOut:
    name = payload.name.strip()
    existing = await db.scalar(
        select(Grade.id).where(func.lower(Grade.name) == name.lower())
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Ce grade existe déjà.")
    grade = Grade(
        name=name,
        level=payload.level,
        color=payload.color,
        permissions=json.dumps(_validated_permissions(payload.permissions)),
        is_direction=payload.is_direction,
    )
    db.add(grade)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Ce grade existe déjà.") from exc
    await db.refresh(grade)
    return await _grade_out(db, grade)


async def update_grade(
    grade_id: int, payload: GradeUpdateRequest, db: AsyncSession
) -> GradeOut:
    grade = await db.get(Grade, grade_id)
    if grade is None:
        raise HTTPException(status_code=404, detail="Grade introuvable.")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
        existing = await db.scalar(
            select(Grade.id).where(
                func.lower(Grade.name) == data["name"].lower(),
                Grade.id != grade_id,
            )
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="Ce grade existe déjà.")
    if "permissions" in data:
        data["permissions"] = json.dumps(_validated_permissions(data["permissions"]))
    for key, value in data.items():
        setattr(grade, key, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Ce grade existe déjà.") from exc
    await db.refresh(grade)
    await push_employees_changed()
    return await _grade_out(db, grade)


async def delete_grade(grade_id: int, db: AsyncSession) -> MessageResponse:
    grade = await db.get(Grade, grade_id)
    if grade is None:
        raise HTTPException(status_code=404, detail="Grade introuvable.")
    count = await db.scalar(
        select(func.count(Employee.id)).where(Employee.grade_id == grade_id)
    )
    if count:
        raise HTTPException(
            status_code=409,
            detail="Réattribuez d’abord ce grade aux employés concernés.",
        )
    await db.delete(grade)
    await db.commit()
    return MessageResponse(message="Grade supprimé.")


async def _radio_out(db: AsyncSession, radio: DispatchRadio) -> DirectionRadioOut:
    employee = await db.get(Employee, radio.employee_id) if radio.employee_id else None
    return DirectionRadioOut(
        id=radio.id,
        serial=radio.serial,
        employee_id=radio.employee_id,
        employee_name=" ".join(filter(None, [employee.first_name, employee.last_name]))
        if employee
        else None,
        is_on=radio.is_on,
        is_loading=radio.is_loading,
        is_direction=bool(employee and employee.grade and employee.grade.is_direction),
    )


async def _ensure_serial_available(
    db: AsyncSession, serial: str, radio_id: int | None = None
) -> None:
    filters = [DispatchRadio.serial == serial]
    if radio_id is not None:
        filters.append(DispatchRadio.id != radio_id)
    if await db.scalar(select(DispatchRadio.id).where(*filters).limit(1)) is not None:
        raise HTTPException(
            status_code=409, detail="Une radio porte déjà ce numéro de série."
        )


async def list_radios(db: AsyncSession) -> list[DirectionRadioOut]:
    radios = sorted_radios((await db.execute(select(DispatchRadio))).scalars().all())
    out = [await _radio_out(db, radio) for radio in radios]
    return sorted(
        out,
        key=lambda radio: 0 if radio.is_direction else 1 if radio.employee_id is not None else 2,
    )


async def create_radio(
    payload: DirectionRadioCreateRequest, db: AsyncSession
) -> DirectionRadioOut:
    await _ensure_serial_available(db, payload.serial)
    radio = DispatchRadio(
        serial=payload.serial,
        employee_id=None,
        is_on=False,
        is_loading=False,
    )
    db.add(radio)
    await db.commit()
    await db.refresh(radio)
    await push_snapshot(db)
    return await _radio_out(db, radio)


async def update_radio(
    radio_id: int, payload: DirectionRadioUpdateRequest, db: AsyncSession
) -> DirectionRadioOut:
    radio = await db.get(DispatchRadio, radio_id)
    if radio is None:
        raise HTTPException(status_code=404, detail="Radio introuvable.")
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "serial" in data:
        await _ensure_serial_available(db, data["serial"], radio.id)
    for key, value in data.items():
        setattr(radio, key, value)
    await db.commit()
    await db.refresh(radio)
    await push_snapshot(db)
    return await _radio_out(db, radio)


async def delete_radio(radio_id: int, db: AsyncSession) -> MessageResponse:
    radio = await db.get(DispatchRadio, radio_id)
    if radio is None:
        raise HTTPException(status_code=404, detail="Radio introuvable.")
    await db.delete(radio)
    await db.commit()
    await push_snapshot(db)
    return MessageResponse(message="Radio supprimée.")


async def _direction_state(db: AsyncSession) -> DispatchState:
    state = await db.get(DispatchState, 1)
    if state is None:
        state = DispatchState(id=1)
        db.add(state)
        await db.flush()
    return state


async def _frequency_setting_out(
    db: AsyncSession, state: DispatchState, kind: FrequencyKind
) -> FrequencySettingOut:
    bounds = await read_bounds(db, kind)
    return FrequencySettingOut(
        kind=kind,
        current=current_frequency(state, kind),
        min=bounds.min,
        max=bounds.max,
    )


async def list_frequencies(db: AsyncSession) -> list[FrequencySettingOut]:
    state = await _direction_state(db)
    await db.commit()
    return [await _frequency_setting_out(db, state, kind) for kind in FREQUENCY_KINDS]


async def update_frequency(
    kind: FrequencyKind,
    payload: FrequencySettingUpdateRequest,
    db: AsyncSession,
) -> FrequencySettingOut:
    state = await _direction_state(db)
    if payload.min is not None or payload.max is not None:
        current_bounds = await read_bounds(db, kind)
        await write_bounds(
            db,
            kind,
            payload.min if payload.min is not None else current_bounds.min,
            payload.max if payload.max is not None else current_bounds.max,
        )
    set_current_frequency(state, kind, payload.current)
    await db.commit()
    await push_snapshot(db)
    return await _frequency_setting_out(db, state, kind)
