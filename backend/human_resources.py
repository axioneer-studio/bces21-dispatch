import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dispatch import push_employees_changed
from app_permissions import require_app_permission
from deps import (
    require_any_page_access,
    require_page_access,
    user_has_page_access,
)
from grade_permissions import parse_grade_permissions, require_grade_permission
from models import DispatchAssignment, DispatchRadio, DispatchSlot, Employee, Grade, User
from schemas import (
    EmployeeAccountLinkRequest,
    EmployeeCreateRequest,
    EmployeeOut,
    EmployeeUpdateRequest,
    GradeOption,
    MessageResponse,
)

router = APIRouter(prefix="/api", tags=["human resources"])


def _employee_out(employee: Employee, *, include_hr_details: bool = False) -> EmployeeOut:
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
        # Date d'arrivée visible du Dispatch : elle sert à l'ancienneté
        # (tri de la réserve et des radios Direction).
        arrival_date=employee.arrival_date,
        competencies=competencies if isinstance(competencies, list) else [],
        is_active=employee.is_active,
        account_user_id=employee.account_user_id,
        account_username=employee.account_user.discord_username if employee.account_user else None,
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
        raise HTTPException(status_code=409, detail="Ce compte est déjà lié à un employé.")
    return user


@router.get(
    "/employees",
    response_model=list[EmployeeOut],
)
async def list_employees(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_any_page_access("dispatch", "human-resources")
    ),
):
    employees_query = select(Employee).order_by(
        Employee.is_active.desc(), Employee.first_name.asc(), Employee.last_name.asc()
    )
    if not user_has_page_access(current_user, "human-resources"):
        employees_query = employees_query.where(Employee.is_active.is_(True))
    employees = (await db.execute(employees_query)).scalars().all()
    include_hr_details = user_has_page_access(current_user, "human-resources")
    return [
        _employee_out(employee, include_hr_details=include_hr_details)
        for employee in employees
    ]


@router.get(
    "/employee-accounts",
    dependencies=[
        Depends(require_page_access("human-resources")),
        Depends(require_app_permission("human_resources.link_accounts")),
    ],
)
async def list_employee_accounts(db: AsyncSession = Depends(get_db)):
    users = (
        await db.execute(
            select(User)
            .where(User.status == "active")
            .order_by(User.prenom_rp.asc().nulls_last(), User.discord_username.asc())
        )
    ).scalars().all()
    return [
        {
            "id": user.id,
            "name": f"{user.prenom_rp or ''} {user.nom_rp or ''}".strip()
            or user.discord_username,
            "discord_username": user.discord_username,
        }
        for user in users
    ]


@router.get(
    "/employee-grades",
    response_model=list[GradeOption],
    dependencies=[Depends(require_page_access("human-resources"))],
)
async def list_employee_grade_options(db: AsyncSession = Depends(get_db)):
    grades = (
        await db.execute(select(Grade).order_by(Grade.level.asc(), Grade.name.asc()))
    ).scalars().all()
    return [
        GradeOption(id=grade.id, name=grade.name, level=grade.level, color=grade.color)
        for grade in grades
    ]


@router.get(
    "/dashboard/summary",
    dependencies=[Depends(require_page_access("dashboard"))],
)
async def dashboard_summary(db: AsyncSession = Depends(get_db)):
    active_employees = await db.scalar(
        select(func.count(Employee.id)).where(Employee.is_active.is_(True))
    )
    assigned_employees = await db.scalar(
        select(func.count(func.distinct(DispatchAssignment.employee_id)))
    )
    intervention_count = await db.scalar(
        select(func.count(DispatchSlot.id)).where(
            DispatchSlot.kind.in_(("intervention", "consultation"))
        )
    )
    online_radios = await db.scalar(
        select(func.count(DispatchRadio.id)).where(DispatchRadio.is_on.is_(True))
    )
    return {
        "assigned_employees": assigned_employees or 0,
        "available_employees": max(0, (active_employees or 0) - (assigned_employees or 0)),
        "interventions": intervention_count or 0,
        "online_radios": online_radios or 0,
    }


@router.post(
    "/employees",
    response_model=EmployeeOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_page_access("human-resources")),
        Depends(require_grade_permission("human_resources.manage_employees")),
    ],
)
async def create_employee(
    payload: EmployeeCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    grade = await db.get(Grade, payload.grade_id) if payload.grade_id is not None else None
    if payload.grade_id is not None and grade is None:
        raise HTTPException(status_code=404, detail="Grade introuvable.")
    employee = Employee(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        email=payload.email,
        arrival_date=payload.arrival_date,
        competencies=json.dumps(payload.competencies, ensure_ascii=False),
        grade_id=payload.grade_id,
        grade=grade,
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    await push_employees_changed()
    return _employee_out(employee, include_hr_details=True)


@router.patch(
    "/employees/{employee_id}",
    response_model=EmployeeOut,
    dependencies=[
        Depends(require_page_access("human-resources")),
        Depends(require_grade_permission("human_resources.manage_employees")),
    ],
)
async def update_employee(
    employee_id: int,
    payload: EmployeeUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employé introuvable.")

    data = payload.model_dump(exclude_unset=True)
    if "grade_id" in data:
        target_grade = (
            await db.get(Grade, data["grade_id"])
            if data["grade_id"] is not None
            else None
        )
        if data["grade_id"] is not None and target_grade is None:
            raise HTTPException(status_code=404, detail="Grade introuvable.")
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
            select(DispatchAssignment.id).where(DispatchAssignment.employee_id == employee_id)
        )
        radio = await db.execute(
            select(DispatchRadio.id).where(DispatchRadio.employee_id == employee_id)
        )
        if assignment.scalar_one_or_none() is not None or radio.scalar_one_or_none() is not None:
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


@router.patch(
    "/employees/{employee_id}/account",
    response_model=EmployeeOut,
    dependencies=[
        Depends(require_page_access("human-resources")),
        Depends(require_app_permission("human_resources.link_accounts")),
    ],
)
async def link_employee_account(
    employee_id: int,
    payload: EmployeeAccountLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employé introuvable.")
    account = await _validate_account_link(
        db, payload.account_user_id, employee_id
    )
    employee.account_user = account
    await db.commit()
    await db.refresh(employee)
    await push_employees_changed()
    return _employee_out(employee, include_hr_details=True)


@router.delete(
    "/employees/{employee_id}",
    response_model=MessageResponse,
    dependencies=[
        Depends(require_page_access("human-resources")),
        Depends(require_grade_permission("human_resources.manage_employees")),
    ],
)
async def delete_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employé introuvable.")
    if employee.account_user_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Déliez le compte utilisateur avant de supprimer cet employé.",
        )
    assignment = await db.execute(
        select(DispatchAssignment.id).where(DispatchAssignment.employee_id == employee_id)
    )
    radio = await db.execute(
        select(DispatchRadio.id).where(DispatchRadio.employee_id == employee_id)
    )
    if assignment.scalar_one_or_none() is not None or radio.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="Retirez d’abord cet employé des postes et des radios.",
        )
    await db.delete(employee)
    await db.commit()
    await push_employees_changed()
    return MessageResponse(message="Employé supprimé.")
