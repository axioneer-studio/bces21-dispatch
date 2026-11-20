"""Routes des ressources humaines (couche transport mince)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import human_resources as chr_
from app.deps import (
    get_db,
    require_any_page_access,
    require_page_access,
)
from app.models import User
from app.schemas import (
    EmployeeAccountLinkRequest,
    EmployeeCreateRequest,
    EmployeeOut,
    EmployeeUpdateRequest,
    GradeOption,
    MessageResponse,
)
from app.services.app_permissions import require_app_permission
from app.services.grade_permissions import require_grade_permission

router = APIRouter(prefix="/api", tags=["human resources"])


@router.get(
    "/employees",
    response_model=list[EmployeeOut],
)
async def list_employees(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_any_page_access("dispatch", "human-resources")
    ),
) -> list[EmployeeOut]:
    return await chr_.list_employees(db, current_user)


@router.get(
    "/employee-accounts",
    dependencies=[
        Depends(require_page_access("human-resources")),
        Depends(require_app_permission("human_resources.link_accounts")),
    ],
)
async def list_employee_accounts(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await chr_.list_employee_accounts(db)


@router.get(
    "/employee-grades",
    response_model=list[GradeOption],
    dependencies=[Depends(require_page_access("human-resources"))],
)
async def list_employee_grade_options(db: AsyncSession = Depends(get_db)) -> list[GradeOption]:
    return await chr_.list_employee_grade_options(db)


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
) -> EmployeeOut:
    return await chr_.create_employee(payload, db)


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
) -> EmployeeOut:
    return await chr_.update_employee(employee_id, payload, db)


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
) -> EmployeeOut:
    return await chr_.link_employee_account(employee_id, payload, db)


@router.delete(
    "/employees/{employee_id}",
    response_model=MessageResponse,
    dependencies=[
        Depends(require_page_access("human-resources")),
        Depends(require_grade_permission("human_resources.manage_employees")),
    ],
)
async def delete_employee(
    employee_id: int, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    return await chr_.delete_employee(employee_id, db)
