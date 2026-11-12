import json

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import get_current_user
from models import Employee, Grade, User

GRADE_PERMISSION_CATALOG = {
    "dispatch.manage_slots": "Créer, modifier et supprimer les postes Dispatch",
    "dispatch.manage_assignments": "Affecter et retirer des employés des postes",
    "dispatch.manage_radios": "Modifier les radios et leurs affectations",
    "dispatch.manage_state": "Modifier l’état et les fréquences du service",
    "agenda.manage_events": "Créer, modifier et supprimer les événements de l’agenda",
    "human_resources.manage_employees": "Gérer les fiches et les tuiles des employés",
}


def parse_grade_permissions(value: str | None) -> list[str]:
    try:
        permissions = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(permissions, list):
        return []
    return [permission for permission in permissions if permission in GRADE_PERMISSION_CATALOG]


async def user_has_grade_permission(
    user: User, db: AsyncSession, permission: str
) -> bool:
    if user.has_super_admin_rights:
        return True
    permissions = await db.scalar(
        select(Grade.permissions)
        .join(Employee, Employee.grade_id == Grade.id)
        .where(Employee.account_user_id == user.id)
    )
    return permission in parse_grade_permissions(permissions)


def require_grade_permission(permission: str):
    if permission not in GRADE_PERMISSION_CATALOG:
        raise ValueError(f"Unknown grade permission: {permission}")

    async def dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if await user_has_grade_permission(user, db, permission):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre grade ne vous autorise pas à effectuer cette action.",
        )

    return dependency
