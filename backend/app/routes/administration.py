"""Routes Administration (couche transport mince)."""

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import administration as cad
from app.deps import get_db, require_admin, require_super_admin
from app.models import User
from app.schemas import (
    AdminUserOut,
    AdminUserRolesUpdateRequest,
    AdminUserStatusUpdateRequest,
    ApplicationSettingsOut,
    ApplicationSettingsUpdateRequest,
    GoogleSheetsConfigOut,
    GoogleSheetsConfigUpdateRequest,
    GoogleSheetsTestResponse,
    MessageResponse,
    RoleCreateRequest,
    RoleOut,
    RoleUpdateRequest,
    StormSettingsOut,
    StormSettingsUpdateRequest,
    SuperAdminUpdateRequest,
)

router = APIRouter(prefix="/api/admin", tags=["administration"])


# --- Utilisateurs ---


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AdminUserOut]:
    return await cad.list_users(db)


@router.put("/users/{user_id}/roles", response_model=AdminUserOut)
async def update_user_roles(
    user_id: int,
    payload: AdminUserRolesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> AdminUserOut:
    return await cad.update_user_roles(user_id, payload, db)


@router.patch("/users/{user_id}/super-admin", response_model=MessageResponse)
async def update_super_admin(
    user_id: int,
    payload: SuperAdminUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin),
) -> MessageResponse:
    return await cad.update_super_admin(user_id, payload, db)


@router.patch("/users/{user_id}/activation", response_model=MessageResponse)
async def set_user_activation(
    user_id: int,
    payload: AdminUserStatusUpdateRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    return await cad.set_user_activation(user_id, payload, current_user, db)


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    return await cad.delete_user(user_id, current_user, db)


# --- Rôles ---


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[RoleOut]:
    return await cad.list_roles(db)


@router.get("/permissions")
async def list_app_permissions(_: User = Depends(require_admin)):
    return await cad.list_app_permissions()


@router.post(
    "/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED
)
async def create_role(
    payload: RoleCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> RoleOut:
    return await cad.create_role(payload, db)


@router.patch("/roles/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    payload: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> RoleOut:
    return await cad.update_role(role_id, payload, db)


@router.delete("/roles/{role_id}", response_model=MessageResponse)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageResponse:
    return await cad.delete_role(role_id, db)


# --- Paramètres ---


@router.get("/settings", response_model=ApplicationSettingsOut)
async def get_application_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> ApplicationSettingsOut:
    return await cad.get_application_settings(db)


@router.put("/settings", response_model=ApplicationSettingsOut)
async def update_application_settings(
    payload: ApplicationSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> ApplicationSettingsOut:
    return await cad.update_application_settings(payload, db)


@router.get("/settings/storm", response_model=StormSettingsOut)
async def get_storm_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> StormSettingsOut:
    return await cad.get_storm_settings(db)


@router.put("/settings/storm", response_model=StormSettingsOut)
async def update_storm_settings(
    payload: StormSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> StormSettingsOut:
    return await cad.update_storm_settings(payload, db)


# --- Google Sheets ---


@router.get("/settings/google-sheets", response_model=GoogleSheetsConfigOut)
async def get_google_sheets_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> GoogleSheetsConfigOut:
    return await cad.get_google_sheets_config(db)


@router.put("/settings/google-sheets", response_model=GoogleSheetsConfigOut)
async def update_google_sheets_config(
    payload: GoogleSheetsConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> GoogleSheetsConfigOut:
    return await cad.update_google_sheets_config(payload, db)


@router.post(
    "/settings/google-sheets/service-account", response_model=MessageResponse
)
async def upload_google_service_account(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageResponse:
    return await cad.upload_google_service_account(file, db)


@router.delete(
    "/settings/google-sheets/service-account", response_model=MessageResponse
)
async def delete_google_service_account(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageResponse:
    return await cad.delete_google_service_account(db)


@router.post(
    "/settings/google-sheets/test", response_model=GoogleSheetsTestResponse
)
async def test_google_sheets_connection(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> GoogleSheetsTestResponse:
    return await cad.test_google_sheets_connection(db)


@router.get(
    "/settings/google-sheets/status", response_model=GoogleSheetsConfigOut
)
async def get_google_sheets_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> GoogleSheetsConfigOut:
    return await cad.get_google_sheets_status(db)


# --- Inscriptions ---


@router.post("/registrations/{user_id}/approve", response_model=MessageResponse)
async def approve_registration(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageResponse:
    return await cad.approve_registration(user_id, db)


@router.post("/registrations/{user_id}/reject", response_model=MessageResponse)
async def reject_registration(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageResponse:
    return await cad.reject_registration(user_id, db)
