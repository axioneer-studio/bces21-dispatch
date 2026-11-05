import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import require_page_access
from grade_permissions import GRADE_PERMISSION_CATALOG
from models import Employee, Grade, User
from schemas import GradeCreateRequest, GradeOut, GradeUpdateRequest, MessageResponse

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
