"""Chef de service : l'employé du grade le plus élevé, celui en tête de
Direction › Grades (plus petit niveau, puis nom), quel que soit le nom du grade
(« Directeur »). Ce grade ne se donne qu'à un seul employé actif.

Le compte lié à la tuile du chef a les droits super-admin tant qu'il a ce
grade, même sans le statut super-admin du compte (`users.is_super_admin`) :
s'il change de grade, il ne les garde que si son compte a ce statut. Avec les
super-admins, il donne et retire ce statut aux autres comptes (page Direction,
onglet Super-admins), jamais le sien.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee, Grade, User


async def chief_grade(db: AsyncSession) -> Grade | None:
    return await db.scalar(select(Grade).order_by(Grade.level.asc(), Grade.name.asc()).limit(1))


async def chief_employees(db: AsyncSession, grade: Grade | None) -> list[Employee]:
    """Employés actifs du grade de chef : un seul, sauf données d'avant la règle."""
    if grade is None:
        return []
    return list(
        (
            await db.execute(
                select(Employee)
                .where(Employee.grade_id == grade.id, Employee.is_active.is_(True))
                .order_by(Employee.id)
            )
        ).scalars().all()
    )


async def is_service_chief(db: AsyncSession, user: User) -> bool:
    grade = await chief_grade(db)
    if grade is None:
        return False
    employee_id = await db.scalar(
        select(Employee.id)
        .where(
            Employee.account_user_id == user.id,
            Employee.grade_id == grade.id,
            Employee.is_active.is_(True),
        )
        .limit(1)
    )
    return employee_id is not None


def _employee_name(employee: Employee) -> str:
    return " ".join(filter(None, [employee.first_name, employee.last_name]))


async def ensure_chief_grade_free(db: AsyncSession, grade_id: int | None, employee_id: int | None = None) -> None:
    """Avant de donner ce grade à un employé actif (`employee_id` : lui-même,
    s'il existe déjà) : 409 s'il s'agit du grade du chef de service et qu'un
    autre employé actif l'a déjà."""
    if grade_id is None:
        return
    grade = await chief_grade(db)
    if grade is None or grade.id != grade_id:
        return
    filters = [Employee.grade_id == grade.id, Employee.is_active.is_(True)]
    if employee_id is not None:
        filters.append(Employee.id != employee_id)
    holder = await db.scalar(select(Employee).where(*filters).order_by(Employee.id).limit(1))
    if holder is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"« {grade.name} » est le grade du chef de service, qui ne se donne qu’à une personne : "
                f"{_employee_name(holder)} l’a déjà. Changez d’abord son grade."
            ),
        )


async def ensure_single_chief(db: AsyncSession, previous_chief_grade_id: int | None) -> None:
    """Après un changement dans les grades (niveau, nom, suppression), avant le
    commit : 409 si un autre grade passe en tête alors que plusieurs employés
    actifs l'ont."""
    grade = await chief_grade(db)
    if grade is None or grade.id == previous_chief_grade_id:
        return
    count = await db.scalar(
        select(func.count(Employee.id)).where(Employee.grade_id == grade.id, Employee.is_active.is_(True))
    )
    if count and count > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"« {grade.name} » passerait en tête des grades et deviendrait celui du chef de service, "
                f"qui ne se donne qu’à une personne : {count} employés l’ont."
            ),
        )
