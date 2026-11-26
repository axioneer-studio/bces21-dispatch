"""Routes de la page Formation (couche transport mince).

Toutes les routes demandent le droit « Formateur » (formation de Pôles & Spé qui
le donne ; les super-admins l'ont). Les modules, le questionnaire et les seuils
de passage se gèrent par la Direction, « Gérer l'hôpital » et le Responsable du
pôle qui donne le droit Formateur. Le forçage d'un passage se vérifie dans le
contrôleur.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import formation as cf
from app.deps import get_current_user, get_db
from app.models import User
from app.schemas import (
    InternAnswerRequest,
    InternLevelRequest,
    InternModuleOut,
    InternModuleRequest,
    InternPassageRequest,
    InternQuestionOut,
    InternQuestionRequest,
    InternRecordOut,
    InternRecordUpdate,
    InternsPageOut,
    InternThresholdsOut,
    InternThresholdsUpdate,
    MessageResponse,
)
from app.services.training_rights import TRAINER_PERMISSION, require_training_permission


async def require_formation_manager(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if await cf.user_manages_formation(db, user):
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Seuls la Direction, « Gérer l’hôpital » et le Responsable du pôle "
            "Formation modifient les modules, le questionnaire et les seuils."
        ),
    )


router = APIRouter(
    prefix="/api/formation",
    tags=["formation"],
    dependencies=[Depends(require_training_permission(TRAINER_PERMISSION))],
)


@router.get("", response_model=InternsPageOut)
async def formation_page(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> InternsPageOut:
    return await cf.formation_page(user, db)


# --- Modules et questionnaire ---


@router.post(
    "/modules",
    response_model=InternModuleOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_formation_manager)],
)
async def create_module(
    payload: InternModuleRequest, db: AsyncSession = Depends(get_db)
) -> InternModuleOut:
    return await cf.create_module(payload, db)


@router.patch(
    "/modules/{module_id}",
    response_model=InternModuleOut,
    dependencies=[Depends(require_formation_manager)],
)
async def update_module(
    module_id: int, payload: InternModuleRequest, db: AsyncSession = Depends(get_db)
) -> InternModuleOut:
    return await cf.update_module(module_id, payload, db)


@router.delete(
    "/modules/{module_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_formation_manager)],
)
async def delete_module(
    module_id: int, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    return await cf.delete_module(module_id, db)


@router.post(
    "/questions",
    response_model=InternQuestionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_formation_manager)],
)
async def create_question(
    payload: InternQuestionRequest, db: AsyncSession = Depends(get_db)
) -> InternQuestionOut:
    return await cf.create_question(payload, db)


@router.patch(
    "/questions/{question_id}",
    response_model=InternQuestionOut,
    dependencies=[Depends(require_formation_manager)],
)
async def update_question(
    question_id: int, payload: InternQuestionRequest, db: AsyncSession = Depends(get_db)
) -> InternQuestionOut:
    return await cf.update_question(question_id, payload, db)


@router.delete(
    "/questions/{question_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_formation_manager)],
)
async def delete_question(
    question_id: int, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    return await cf.delete_question(question_id, db)


@router.put(
    "/thresholds",
    response_model=InternThresholdsOut,
    dependencies=[Depends(require_formation_manager)],
)
async def update_thresholds(
    payload: InternThresholdsUpdate, db: AsyncSession = Depends(get_db)
) -> InternThresholdsOut:
    return await cf.update_thresholds(payload, db)


# --- Fiche ---


@router.patch("/{employee_id}", response_model=InternRecordOut)
async def update_record(
    employee_id: int, payload: InternRecordUpdate, db: AsyncSession = Depends(get_db)
) -> InternRecordOut:
    return await cf.update_record(employee_id, payload, db)


@router.put("/{employee_id}/modules/{module_id}", response_model=InternRecordOut)
async def set_module_level(
    employee_id: int,
    module_id: int,
    payload: InternLevelRequest,
    db: AsyncSession = Depends(get_db),
) -> InternRecordOut:
    return await cf.set_module_level(employee_id, module_id, payload, db)


@router.put("/{employee_id}/questions/{question_id}", response_model=InternRecordOut)
async def set_answer(
    employee_id: int,
    question_id: int,
    payload: InternAnswerRequest,
    db: AsyncSession = Depends(get_db),
) -> InternRecordOut:
    return await cf.set_answer(employee_id, question_id, payload, db)


# --- Passages de grade ---


@router.post("/{employee_id}/resident", response_model=InternRecordOut)
async def pass_training_grade(
    employee_id: int,
    payload: InternPassageRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InternRecordOut:
    return await cf.pass_training_grade(employee_id, payload, user, db)


@router.delete("/{employee_id}/resident", response_model=InternRecordOut)
async def cancel_training_grade(
    employee_id: int, db: AsyncSession = Depends(get_db)
) -> InternRecordOut:
    return await cf.cancel_training_grade(employee_id, db)


@router.post("/{employee_id}/complete", response_model=InternRecordOut)
async def complete_formation(
    employee_id: int,
    payload: InternPassageRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InternRecordOut:
    return await cf.complete_formation(employee_id, payload, user, db)


@router.delete("/{employee_id}/complete", response_model=InternRecordOut)
async def cancel_completion(
    employee_id: int, db: AsyncSession = Depends(get_db)
) -> InternRecordOut:
    return await cf.cancel_completion(employee_id, db)
