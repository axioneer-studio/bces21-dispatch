"""Contrôleur des ressources humaines : employés, grades, comptes."""

import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dispatch import push_employees_changed
from app.models import DispatchAssignment, DispatchRadio, Employee, Grade, User
from app.schemas import (
    EmployeeAccountLinkRequest,
    EmployeeCreateRequest,
    EmployeeOut,
    EmployeeUpdateRequest,
    GradeOption,
    MessageResponse,
)
from app.services.grade_permissions import parse_grade_permissions
from app.services.service_chief import ensure_chief_grade_free
from app.services.training_rights import user_has_hr_access


def _employee_out(
    employee: Employee, *, include_hr_details: bool = False
) -> EmployeeOut:
    try:
        competencies = json.loads(employee.competencies or "[]")
    except (TypeError, ValueError):
        competencies = []
    return EmployeeOut(
        id=employee.id,
        first_name=employee.first_name,
        last_name=employee.last_name,
        phone=employee.phone,
        email=employee.email if include_hr_details else None,
        arrival_date=employee.arrival_date,
        gender=employee.gender if include_hr_details else None,
        birth_date=employee.birth_date if include_hr_details else None,
        diploma=employee.diploma if include_hr_details else False,
        boat_license=employee.boat_license if include_hr_details else False,
        boat_license_date=employee.boat_license_date if include_hr_details else None,
        helicopter_license=employee.helicopter_license if include_hr_details else False,
        helicopter_license_date=(
            employee.helicopter_license_date if include_hr_details else None
        ),
        competencies=competencies if isinstance(competencies, list) else [],
        is_active=employee.is_active,
        account_user_id=employee.account_user_id,
        account_username=(
            employee.account_user.discord_username if employee.account_user else None
        ),
        grade_id=employee.grade_id,
        grade_name=employee.grade.name if employee.grade else None,
        grade_level=employee.grade.level if employee.grade else None,
        grade_color=employee.grade.color if employee.grade else None,
        grade_is_direction=bool(employee.grade and employee.grade.is_direction),
        grade_permissions=parse_grade_permissions(
            employee.grade.permissions if employee.grade else None
        ),
        created_at=employee.created_at,
        updated_at=employee.updated_at,
    )


async def _validate_account_link(
    db: AsyncSession, account_user_id: int | None, employee_id: int | None = None
) -> User | None:
    if account_user_id is None:
        return None
    user = await db.get(User, account_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Compte utilisateur introuvable.")
    if user.status != "active":
        raise HTTPException(status_code=409, detail="Ce compte n’est pas actif.")
    filters = [Employee.account_user_id == account_user_id]
    if employee_id is not None:
        filters.append(Employee.id != employee_id)
    existing = await db.execute(select(Employee.id).where(*filters))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail="Ce compte est déjà lié à un employé."
        )
    return user


async def list_employees(db: AsyncSession, current_user: User) -> list[EmployeeOut]:
    employees_query = select(Employee).order_by(
        Employee.is_active.desc(), Employee.first_name.asc(), Employee.last_name.asc()
    )
    # Tout le monde voit la liste des employés (Dispatch) ; les employés
    # désactivés et les détails RH sont réservés au droit RH (formation ou Direction).
    include_hr_details = await user_has_hr_access(db, current_user)
    if not include_hr_details:
        employees_query = employees_query.where(Employee.is_active.is_(True))
    employees = (await db.execute(employees_query)).scalars().all()
    return [
        _employee_out(employee, include_hr_details=include_hr_details)
        for employee in employees
    ]


async def list_employee_accounts(db: AsyncSession) -> list[dict]:
    users = (
        (
            await db.execute(
                select(User)
                .where(User.status == "active")
                .order_by(
                    User.prenom_rp.asc().nulls_last(), User.discord_username.asc()
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": user.id,
            "name": f"{user.prenom_rp or ''} {user.nom_rp or ''}".strip()
            or user.discord_username,
            "discord_username": user.discord_username,
        }
        for user in users
    ]


async def list_employee_grade_options(db: AsyncSession) -> list[GradeOption]:
    grades = (
        (await db.execute(select(Grade).order_by(Grade.level.asc(), Grade.name.asc())))
        .scalars()
        .all()
    )
    return [
        GradeOption(id=grade.id, name=grade.name, level=grade.level, color=grade.color)
        for grade in grades
    ]


async def create_employee(
    payload: EmployeeCreateRequest, db: AsyncSession
) -> EmployeeOut:
    grade = (
        await db.get(Grade, payload.grade_id) if payload.grade_id is not None else None
    )
    if payload.grade_id is not None and grade is None:
        raise HTTPException(status_code=404, detail="Grade introuvable.")
    await ensure_chief_grade_free(db, payload.grade_id)
    if payload.account_user_id is not None:
        await _validate_account_link(db, payload.account_user_id)

    employee = Employee(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        email=payload.email,
        arrival_date=payload.arrival_date,
        gender=payload.gender,
        birth_date=payload.birth_date,
        diploma=payload.diploma,
        boat_license=payload.boat_license,
        boat_license_date=payload.boat_license_date if payload.boat_license else None,
        helicopter_license=payload.helicopter_license,
        helicopter_license_date=(
            payload.helicopter_license_date if payload.helicopter_license else None
        ),
        competencies=json.dumps(payload.competencies, ensure_ascii=False),
        grade_id=payload.grade_id,
        grade=grade,
        account_user_id=payload.account_user_id,
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    await push_employees_changed()
    return _employee_out(employee, include_hr_details=True)


async def update_employee(
    employee_id: int, payload: EmployeeUpdateRequest, db: AsyncSession
) -> EmployeeOut:
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employé introuvable.")

    data = payload.model_dump(exclude_unset=True)
    if data.get("boat_license") is False:
        data["boat_license_date"] = None
    if data.get("helicopter_license") is False:
        data["helicopter_license_date"] = None
    if "account_user_id" in data and data["account_user_id"] is not None:
        await _validate_account_link(db, data["account_user_id"], employee_id)
    if "grade_id" in data:
        target_grade = (
            await db.get(Grade, data["grade_id"])
            if data["grade_id"] is not None
            else None
        )
        if data["grade_id"] is not None and target_grade is None:
            raise HTTPException(status_code=404, detail="Grade introuvable.")
    # Le grade du chef de service ne va qu'à un seul employé actif.
    if data.get("is_active", employee.is_active) and ("grade_id" in data or data.get("is_active") is True):
        await ensure_chief_grade_free(db, data["grade_id"] if "grade_id" in data else employee.grade_id, employee.id)
    if "grade_id" in data:
        employee.grade = target_grade
    target_account_id = employee.account_user_id
    if data.get("is_active") is True and target_account_id is not None:
        linked_user = await db.get(User, target_account_id)
        if linked_user is not None and linked_user.status == "pending":
            raise HTTPException(
                status_code=409,
                detail="Le compte lié est en attente de validation.",
            )
    if data.get("is_active") is False:
        assignment = await db.execute(
            select(DispatchAssignment.id).where(
                DispatchAssignment.employee_id == employee_id
            )
        )
        radio = await db.execute(
            select(DispatchRadio.id).where(DispatchRadio.employee_id == employee_id)
        )
        if (
            assignment.scalar_one_or_none() is not None
            or radio.scalar_one_or_none() is not None
        ):
            raise HTTPException(
                status_code=409,
                detail="Retirez cet employé des postes et des radios avant de le désactiver.",
            )
    for key, value in data.items():
        if key == "competencies":
            value = json.dumps(value, ensure_ascii=False)
        elif key in {"first_name", "last_name"} and value is not None:
            value = value.strip()
        elif key == "phone" and value is not None:
            value = value.strip() or None
        setattr(employee, key, value)
    await db.commit()
    await db.refresh(employee)
    await push_employees_changed()
    return _employee_out(employee, include_hr_details=True)


async def link_employee_account(
    employee_id: int, payload: EmployeeAccountLinkRequest, db: AsyncSession
) -> EmployeeOut:
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employé introuvable.")
    account = await _validate_account_link(db, payload.account_user_id, employee_id)
    employee.account_user = account
    await db.commit()
    await db.refresh(employee)
    await push_employees_changed()
    return _employee_out(employee, include_hr_details=True)


async def delete_employee(employee_id: int, db: AsyncSession) -> MessageResponse:
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employé introuvable.")
    if employee.account_user_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Déliez le compte utilisateur avant de supprimer cet employé.",
        )
    assignment = await db.execute(
        select(DispatchAssignment.id).where(
            DispatchAssignment.employee_id == employee_id
        )
    )
    radio = await db.execute(
        select(DispatchRadio.id).where(DispatchRadio.employee_id == employee_id)
    )
    if (
        assignment.scalar_one_or_none() is not None
        or radio.scalar_one_or_none() is not None
    ):
        raise HTTPException(
            status_code=409,
            detail="Retirez d’abord cet employé des postes et des radios.",
        )
    await db.delete(employee)
    await db.commit()
    await push_employees_changed()
    return MessageResponse(message="Employé supprimé.")
