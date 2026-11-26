"""Routes de Pôles & Spé (couche transport mince).

La page est ouverte à tout compte validé. Créer, modifier et supprimer une
formation demandent « Gérer l'hôpital » (rôle) ou un grade de la Direction ;
l'équipe d'une formation se vérifie dans le contrôleur (Direction, Responsable,
Second).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import trainings as ct
from app.deps import get_current_user, get_db, require_page_access
from app.models import User
from app.schemas import (
    MessageResponse,
    TrainingEmployeeOut,
    TrainingMemberRequest,
    TrainingOut,
    TrainingPageOut,
    TrainingRequest,
)
from app.services.hospital_access import require_hospital_manage

router = APIRouter(
    prefix="/api/trainings",
    tags=["trainings"],
    dependencies=[Depends(require_page_access("training"))],
)


@router.get("", response_model=TrainingPageOut)
async def training_page(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> TrainingPageOut:
    return await ct.training_page(user, db)


@router.post(
    "",
    response_model=TrainingOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_hospital_manage)],
)
async def create_training(
    payload: TrainingRequest, db: AsyncSession = Depends(get_db)
) -> TrainingOut:
    return await ct.create_training(payload, db)


@router.patch(
    "/{training_id}",
    response_model=TrainingOut,
    dependencies=[Depends(require_hospital_manage)],
)
async def update_training(
    training_id: int, payload: TrainingRequest, db: AsyncSession = Depends(get_db)
) -> TrainingOut:
    return await ct.update_training(training_id, payload, db)


@router.delete(
    "/{training_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_hospital_manage)],
)
async def delete_training(
    training_id: int, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    return await ct.delete_training(training_id, db)


@router.put(
    "/{training_id}/employees/{employee_id}", response_model=TrainingEmployeeOut
)
async def validate_training(
    training_id: int,
    employee_id: int,
    payload: TrainingMemberRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrainingEmployeeOut:
    return await ct.validate_training(training_id, employee_id, payload, user, db)


@router.delete(
    "/{training_id}/employees/{employee_id}", response_model=TrainingEmployeeOut
)
async def unvalidate_training(
    training_id: int,
    employee_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrainingEmployeeOut:
    return await ct.unvalidate_training(training_id, employee_id, user, db)
