"""Routes Direction (couche transport mince)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import direction as cd
from app.deps import get_db, require_page_access, require_super_admin_manager
from app.models import User
from app.schemas import FrequencyKind

router = APIRouter(prefix="/api/direction", tags=["direction"])


# --- Grades ---


@router.get("/permissions")
async def list_grade_permissions(
    _: User = Depends(require_page_access("direction")),
):
    return await cd.list_grade_permissions()


@router.get("/grades", response_model=list[cd.GradeOut])
async def list_grades(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
) -> list[cd.GradeOut]:
    return await cd.list_grades(db)


@router.post("/grades", response_model=cd.GradeOut, status_code=status.HTTP_201_CREATED)
async def create_grade(
    payload: cd.GradeCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
) -> cd.GradeOut:
    return await cd.create_grade(payload, db)


@router.patch("/grades/{grade_id}", response_model=cd.GradeOut)
async def update_grade(
    grade_id: int,
    payload: cd.GradeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
) -> cd.GradeOut:
    return await cd.update_grade(grade_id, payload, db)


@router.delete("/grades/{grade_id}", response_model=cd.MessageResponse)
async def delete_grade(
    grade_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
) -> cd.MessageResponse:
    return await cd.delete_grade(grade_id, db)


# --- Radios ---


@router.get("/radios", response_model=list[cd.DirectionRadioOut])
async def list_radios(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
) -> list[cd.DirectionRadioOut]:
    return await cd.list_radios(db)


@router.post(
    "/radios", response_model=cd.DirectionRadioOut, status_code=status.HTTP_201_CREATED
)
async def create_radio(
    payload: cd.DirectionRadioCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
) -> cd.DirectionRadioOut:
    return await cd.create_radio(payload, db)


@router.patch("/radios/{radio_id}", response_model=cd.DirectionRadioOut)
async def update_radio(
    radio_id: int,
    payload: cd.DirectionRadioUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
) -> cd.DirectionRadioOut:
    return await cd.update_radio(radio_id, payload, db)


@router.delete("/radios/{radio_id}", response_model=cd.MessageResponse)
async def delete_radio(
    radio_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
) -> cd.MessageResponse:
    return await cd.delete_radio(radio_id, db)


# --- Fréquences ---


@router.get("/frequencies", response_model=list[cd.FrequencySettingOut])
async def list_frequencies(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
) -> list[cd.FrequencySettingOut]:
    return await cd.list_frequencies(db)


@router.put("/frequencies/{kind}", response_model=cd.FrequencySettingOut)
async def update_frequency(
    kind: FrequencyKind,
    payload: cd.FrequencySettingUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("direction")),
) -> cd.FrequencySettingOut:
    return await cd.update_frequency(kind, payload, db)


# --- Super-admins : chef de service et super-admins ---


@router.get("/super-admins", response_model=cd.DirectionSuperAdminsOut)
async def list_super_admins(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_super_admin_manager),
) -> cd.DirectionSuperAdminsOut:
    return await cd.list_super_admins(user, db)


@router.put("/super-admins/{user_id}", response_model=cd.DirectionSuperAdminsOut)
async def update_super_admin_status(
    user_id: int,
    payload: cd.SuperAdminUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_super_admin_manager),
) -> cd.DirectionSuperAdminsOut:
    return await cd.update_super_admin_status(user_id, payload, user, db)
