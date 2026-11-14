"""Droits de la page Hôpital.

La Direction (employé lié dont le grade est `is_direction`) a « Gérer l'hôpital »
par défaut, sans que la permission soit cochée sur son rôle. Les super-admins ont
tous les droits.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app_permissions import user_has_app_permission
from database import get_db
from deps import get_current_user
from models import Employee, User

MANAGE_PERMISSION = "hospital.manage"
FORENSIC_PERMISSION = "hospital.forensic"


async def linked_employee(db: AsyncSession, user: User) -> Employee | None:
    return await db.scalar(select(Employee).where(Employee.account_user_id == user.id))


def is_direction(employee: Employee | None) -> bool:
    return bool(employee and employee.grade and employee.grade.is_direction)


async def user_can_manage_hospital(db: AsyncSession, user: User) -> bool:
    if user_has_app_permission(user, MANAGE_PERMISSION):
        return True
    return is_direction(await linked_employee(db, user))


async def require_hospital_manage(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if await user_can_manage_hospital(db, user):
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Seuls la Direction et les rôles « Gérer l’hôpital » peuvent effectuer cette action.",
    )
