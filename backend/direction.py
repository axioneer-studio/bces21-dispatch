import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import require_page_access
from dispatch import push_employees_changed, push_snapshot, sorted_radios
from grade_permissions import GRADE_PERMISSION_CATALOG
from models import DispatchRadio, Employee, Grade, User
from schemas import (
    DirectionRadioCreateRequest,
    DirectionRadioOut,
    DirectionRadioUpdateRequest,
    GradeCreateRequest,
    GradeOut,
    GradeUpdateRequest,
    MessageResponse,
)

router = APIRouter(prefix="/api/direction", tags=["direction"])


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


@router.get("/permissions")
async def list_grade_permissions(
    _: User = Depends(require_page_access("direction")),
):
    return [
        {"key": key, "label": label}
        for key, label in GRADE_PERMISSION_CATALOG.items()
    ]


@router.get("/grades", response_model=list[GradeOut])
async def list_grades(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
):
    grades = (
        await db.execute(select(Grade).order_by(Grade.level.asc(), Grade.name.asc()))
    ).scalars().all()
    return [await _grade_out(db, grade) for grade in grades]


@router.post("/grades", response_model=GradeOut, status_code=status.HTTP_201_CREATED)
async def create_grade(
    payload: GradeCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
):
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


@router.patch("/grades/{grade_id}", response_model=GradeOut)
async def update_grade(
    grade_id: int,
    payload: GradeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
):
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
    # Le Dispatch trie et filtre les employés selon leur grade : il recharge la liste.
    await push_employees_changed()
    return await _grade_out(db, grade)


@router.delete("/grades/{grade_id}", response_model=MessageResponse)
async def delete_grade(
    grade_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
):
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


# --- Radios : seule la Direction voit le numéro de série complet ---


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
    # La casse compte : « 0Va4ZeS » et « 0VA4ZES » sont deux numéros distincts.
    filters = [DispatchRadio.serial == serial]
    if radio_id is not None:
        filters.append(DispatchRadio.id != radio_id)
    if await db.scalar(select(DispatchRadio.id).where(*filters).limit(1)) is not None:
        raise HTTPException(
            status_code=409, detail="Une radio porte déjà ce numéro de série."
        )


@router.get("/radios", response_model=list[DirectionRadioOut])
async def list_radios(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
):
    radios = sorted_radios((await db.execute(select(DispatchRadio))).scalars().all())
    out = [await _radio_out(db, radio) for radio in radios]
    # Direction en haut, puis les radios affectées, puis les libres ; le tri
    # stable garde l'ordre par numéro de série dans chaque groupe.
    return sorted(
        out,
        key=lambda radio: 0 if radio.is_direction else 1 if radio.employee_id is not None else 2,
    )


@router.post("/radios", response_model=DirectionRadioOut, status_code=status.HTTP_201_CREATED)
async def create_radio(
    payload: DirectionRadioCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
):
    await _ensure_serial_available(db, payload.serial)
    # Une radio naît toujours sans affectation, donc OFF.
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


@router.patch("/radios/{radio_id}", response_model=DirectionRadioOut)
async def update_radio(
    radio_id: int,
    payload: DirectionRadioUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
):
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


@router.delete("/radios/{radio_id}", response_model=MessageResponse)
async def delete_radio(
    radio_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
):
    radio = await db.get(DispatchRadio, radio_id)
    if radio is None:
        raise HTTPException(status_code=404, detail="Radio introuvable.")
    await db.delete(radio)
    await db.commit()
    await push_snapshot(db)
    return MessageResponse(message="Radio supprimée.")
