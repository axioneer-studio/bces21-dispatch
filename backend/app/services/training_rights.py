"""Droits donnés par les formations générales.

Une formation générale peut donner des droits (Formateur, Médecin légiste, RH)
à ceux qui l'ont validée, c'est-à-dire aux employés qui ont son emoji dans leurs
compétences (`pole_competencies` : sans les emojis des modules de leur étape de
formation, qu'un pôle peut partager). Le compte lié à la tuile de l'employé
reçoit ces droits. La Direction (grade `is_direction`) a le droit RH par
défaut. Les super-admins ont tous les droits.
"""

import json

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import Employee, Training, User
from app.services.formation_stages import employee_stage, module_emojis_by_stage

TRAINER_PERMISSION = "training.validate"
FORENSIC_PERMISSION = "hospital.forensic"
# Droit RH : ouvre la page Ressources humaines, où il permet de gérer les fiches
# et les tuiles des employés et de lier un compte à une tuile.
HR_PERMISSION = "human_resources.manage"
# Droit Stock : gestion des stocks du BCES (page Stock).
STOCK_PERMISSION = "stock.manage"

# Droits qu'une formation générale peut donner.
TRAINING_PERMISSION_CATALOG = {
    TRAINER_PERMISSION: "Formateur",
    FORENSIC_PERMISSION: "Médecin légiste",
    HR_PERMISSION: "Ressources humaines",
    STOCK_PERMISSION: "Stock",
}


def emoji_key(value: str) -> str:
    """Un même emoji peut s'écrire avec ou sans sélecteur de variante (U+FE0F)."""
    return value.replace("️", "").strip()


def employee_competencies(employee: Employee) -> list[str]:
    try:
        value = json.loads(employee.competencies or "[]")
    except (TypeError, ValueError):
        return []
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def from_stage_module(employee: Employee, emoji: str, module_emojis: dict[str, list[str]]) -> bool:
    """L'emoji est celui d'un module de l'étape de l'employé : chez lui, il vient
    de sa fiche de formation, pas d'un pôle ou d'une spécialité."""
    stage = employee_stage(employee)
    return stage is not None and any(emoji_key(item) == emoji_key(emoji) for item in module_emojis[stage])


def pole_competencies(employee: Employee, module_emojis: dict[str, list[str]]) -> list[str]:
    """Compétences qui comptent pour les pôles et spécialités (`module_emojis` :
    `formation_stages.module_emojis_by_stage`)."""
    return [item for item in employee_competencies(employee) if not from_stage_module(employee, item, module_emojis)]


def parse_training_permissions(value: str | None) -> list[str]:
    try:
        permissions = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(permissions, list):
        return []
    return [permission for permission in permissions if permission in TRAINING_PERMISSION_CATALOG]


async def _granting_trainings(db: AsyncSession) -> list[Training]:
    trainings = (await db.execute(select(Training).where(Training.kind == "general"))).scalars().all()
    return [training for training in trainings if parse_training_permissions(training.permissions)]


def _permissions_of(employee: Employee, trainings: list[Training], module_emojis: dict[str, list[str]]) -> set[str]:
    owned = {emoji_key(item) for item in pole_competencies(employee, module_emojis)}
    return {
        permission
        for training in trainings
        if emoji_key(training.emoji) in owned
        for permission in parse_training_permissions(training.permissions)
    }


async def employees_with_training_permission(db: AsyncSession, permission: str) -> list[Employee]:
    """Employés actifs qui ont validé une formation donnant ce droit."""
    trainings = await _granting_trainings(db)
    if not trainings:
        return []
    employees = (
        await db.execute(
            select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.first_name, Employee.last_name)
        )
    ).scalars().all()
    module_emojis = await module_emojis_by_stage(db)
    return [employee for employee in employees if permission in _permissions_of(employee, trainings, module_emojis)]


async def user_training_permissions(db: AsyncSession, user: User) -> list[str]:
    """Droits du compte : ceux que les formations de sa tuile lui donnent, plus
    les droits RH si sa tuile est de la Direction. Un super-admin les a tous."""
    if user.has_super_admin_rights:
        return list(TRAINING_PERMISSION_CATALOG)
    employee = await db.scalar(select(Employee).where(Employee.account_user_id == user.id))
    if employee is None or not employee.is_active:
        return []
    permissions = _permissions_of(employee, await _granting_trainings(db), await module_emojis_by_stage(db))
    if employee.grade and employee.grade.is_direction:
        permissions.add(HR_PERMISSION)
    return [permission for permission in TRAINING_PERMISSION_CATALOG if permission in permissions]


async def user_has_training_permission(db: AsyncSession, user: User, permission: str) -> bool:
    return permission in await user_training_permissions(db, user)


async def user_has_hr_access(db: AsyncSession, user: User) -> bool:
    """Page Ressources humaines : réservée au droit RH (formation ou Direction)."""
    return await user_has_training_permission(db, user, HR_PERMISSION)


async def require_hr_access(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if await user_has_hr_access(db, user):
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès à cette page non autorisé.")


def require_training_permission(permission: str):
    if permission not in TRAINING_PERMISSION_CATALOG:
        raise ValueError(f"Unknown training permission: {permission}")

    async def dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if await user_has_training_permission(db, user, permission):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Réservé à ceux qui ont validé une formation « {TRAINING_PERMISSION_CATALOG[permission]} ».",
        )

    return dependency
