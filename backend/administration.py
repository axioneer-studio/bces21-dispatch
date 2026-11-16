import asyncio
import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from dispatch import push_employees_changed
from deps import PAGE_KEYS, require_admin, require_super_admin, user_has_page_access
from app_permissions import APP_PERMISSION_CATALOG
from google_sheets_service import (
    GoogleSheetsError,
    GoogleSheetsService,
    build_from_db,
    load_settings_from_db,
)
from models import ApplicationSetting, Employee, Role, User, user_roles
from s3_service import S3ServiceError, s3_service
from schemas import (
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
    SuperAdminUpdateRequest,
)

router = APIRouter(prefix="/api/admin", tags=["administration"])

logger = logging.getLogger("bces.admin")


def _role_out(role: Role, users_count: int) -> RoleOut:
    try:
        pages = json.loads(role.pages)
    except (TypeError, ValueError):
        pages = []
    return RoleOut(
        id=role.id,
        name=role.name,
        pages=pages if isinstance(pages, list) else [],
        permissions=_parse_app_permissions(role.permissions),
        users_count=users_count,
    )


def _parse_app_permissions(value: str | None) -> list[str]:
    try:
        permissions = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(permissions, list):
        return []
    return [permission for permission in permissions if permission in APP_PERMISSION_CATALOG]


def _admin_user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        discord_username=user.discord_username,
        first_name=user.prenom_rp,
        last_name=user.nom_rp,
        status=user.status or "active",
        role_ids=[role.id for role in user.roles],
        role_names=[role.name for role in user.roles],
        is_super_admin=user.is_super_admin,
        super_admin_enabled=user.super_admin_enabled,
        created_at=user.created_at,
    )


def _validate_pages(pages: list[str] | None) -> list[str]:
    if pages is None:
        return []
    unknown = set(pages) - PAGE_KEYS
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Pages inconnues : {', '.join(sorted(unknown))}.",
        )
    return list(dict.fromkeys(pages))


def _validate_app_permissions(permissions: list[str] | None) -> list[str]:
    if permissions is None:
        return []
    unknown = set(permissions) - APP_PERMISSION_CATALOG.keys()
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Permissions inconnues : {', '.join(sorted(unknown))}.",
        )
    return list(dict.fromkeys(permissions))


def _is_app_admin(user: User) -> bool:
    return user.is_super_admin or user_has_page_access(user, "administration")


async def _ensure_another_admin_remains(db: AsyncSession, target: User) -> None:
    if not _is_app_admin(target):
        return
    users = (await db.execute(select(User).where(User.id != target.id))).scalars().all()
    if any(
        _is_app_admin(user)
        and (user.status or "active") == "active"
        for user in users
    ):
        return
    raise HTTPException(
        status_code=409,
        detail="Impossible de retirer le dernier administrateur actif.",
    )


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    users = (
        await db.execute(select(User).order_by(User.created_at.desc(), User.id.desc()))
    ).scalars().all()
    return [_admin_user_out(user) for user in users]


@router.put("/users/{user_id}/roles", response_model=AdminUserOut)
async def update_user_roles(
    user_id: int,
    payload: AdminUserRolesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Remplace les rôles du compte : il cumule les pages et permissions de chacun."""
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    role_ids = list(dict.fromkeys(payload.role_ids))
    next_roles = (
        (await db.execute(select(Role).where(Role.id.in_(role_ids)))).scalars().all()
        if role_ids
        else []
    )
    if len(next_roles) != len(role_ids):
        raise HTTPException(status_code=404, detail="Rôle introuvable.")

    removes_admin_access = _is_app_admin(target) and not (
        target.is_super_admin
        or any("administration" in _parse_pages(role.pages) for role in next_roles)
    )
    if removes_admin_access:
        await _ensure_another_admin_remains(db, target)

    target.roles = sorted(next_roles, key=lambda role: role.name.lower())
    await db.commit()
    await db.refresh(target, ["roles"])
    return _admin_user_out(target)


@router.patch("/users/{user_id}/super-admin", response_model=MessageResponse)
async def update_super_admin(
    user_id: int,
    payload: SuperAdminUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if (
        target.is_super_admin
        and not payload.is_super_admin
        and not user_has_page_access(target, "administration")
    ):
        await _ensure_another_admin_remains(db, target)
    if payload.is_super_admin and not target.is_super_admin:
        target.super_admin_enabled = True
    target.is_super_admin = payload.is_super_admin
    await db.commit()
    return MessageResponse(message="Droits super-admin mis à jour.")


@router.patch("/users/{user_id}/activation", response_model=MessageResponse)
async def set_user_activation(
    user_id: int,
    payload: AdminUserStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if target.id == current_user.id and not payload.is_active:
        raise HTTPException(
            status_code=409,
            detail="Vous ne pouvez pas désactiver votre propre compte.",
        )
    if target.status == "pending":
        raise HTTPException(
            status_code=409,
            detail="Validez ou refusez d’abord la demande d’inscription.",
        )
    if not payload.is_active and target.status == "active":
        await _ensure_another_admin_remains(db, target)
    target.status = "active" if payload.is_active else "disabled"
    await db.commit()
    return MessageResponse(
        message="Compte activé." if payload.is_active else "Compte désactivé."
    )


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if target.id == current_user.id:
        raise HTTPException(
            status_code=409,
            detail="Vous ne pouvez pas supprimer votre propre compte.",
        )
    await _ensure_another_admin_remains(db, target)

    employee = (
        await db.execute(select(Employee).where(Employee.account_user_id == target.id))
    ).scalar_one_or_none()
    if employee is not None:
        employee.account_user = None

    await db.delete(target)
    await db.commit()
    if employee is not None:
        await push_employees_changed()
    return MessageResponse(message="Compte utilisateur supprimé.")


def _parse_pages(value: str | None) -> list[str]:
    try:
        pages = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return pages if isinstance(pages, list) else []


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    roles = (await db.execute(select(Role).order_by(Role.name))).scalars().all()
    return [_role_out(role, await _role_users_count(db, role.id)) for role in roles]


async def _role_users_count(db: AsyncSession, role_id: int) -> int:
    count = await db.scalar(
        select(func.count()).select_from(user_roles).where(user_roles.c.role_id == role_id)
    )
    return count or 0


@router.get("/permissions")
async def list_app_permissions(_: User = Depends(require_admin)):
    return [
        {"key": key, "label": label}
        for key, label in APP_PERMISSION_CATALOG.items()
    ]


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    name = payload.name.strip()
    existing = await db.scalar(select(Role.id).where(func.lower(Role.name) == name.lower()))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Ce rôle existe déjà.")
    role = Role(
        name=name,
        pages=json.dumps(_validate_pages(payload.pages)),
        permissions=json.dumps(_validate_app_permissions(payload.permissions)),
    )
    db.add(role)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Ce rôle existe déjà.") from exc
    await db.refresh(role)
    return _role_out(role, 0)


@router.patch("/roles/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    payload: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    role = await db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Rôle introuvable.")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
        existing = await db.scalar(
            select(Role.id).where(
                func.lower(Role.name) == data["name"].lower(), Role.id != role_id
            )
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="Ce rôle existe déjà.")
    if "pages" in data:
        next_pages = _validate_pages(data["pages"])
        if "administration" in _parse_pages(role.pages) and "administration" not in next_pages:
            all_users = (await db.execute(select(User))).scalars().all()
            role_has_users = any(
                any(user_role.id == role_id for user_role in user.roles) for user in all_users
            )
            admin_remains = any(
                (user.status or "active") == "active"
                and (
                    user.is_super_admin
                    or any(
                        user_role.id != role_id and "administration" in _parse_pages(user_role.pages)
                        for user_role in user.roles
                    )
                )
                for user in all_users
            )
            if role_has_users and not admin_remains:
                raise HTTPException(
                    status_code=409,
                    detail="Impossible de retirer le dernier administrateur actif.",
                )
        data["pages"] = json.dumps(next_pages)
    if "permissions" in data:
        data["permissions"] = json.dumps(_validate_app_permissions(data["permissions"]))
    for key, value in data.items():
        setattr(role, key, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Ce rôle existe déjà.") from exc
    await db.refresh(role)
    return _role_out(role, await _role_users_count(db, role_id))


@router.delete("/roles/{role_id}", response_model=MessageResponse)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    role = await db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Rôle introuvable.")

    # Si le rôle donne accès à l’administration, s’assurer qu’un autre
    # administrateur actif restera après son retrait des comptes.
    if "administration" in _parse_pages(role.pages):
        users = (
            await db.execute(select(User).options(selectinload(User.roles)))
        ).scalars().all()
        admin_remains = any(
            (user.status or "active") == "active"
            and (
                user.is_super_admin
                or any(
                    user_role.id != role_id
                    and "administration" in _parse_pages(user_role.pages)
                    for user_role in user.roles
                )
            )
            for user in users
        )
        if not admin_remains:
            raise HTTPException(
                status_code=409,
                detail="Impossible de supprimer le dernier rôle administrateur actif.",
            )

    # Retire le rôle de tous les comptes qui le possèdent avant de le supprimer.
    await db.execute(delete(user_roles).where(user_roles.c.role_id == role_id))
    await db.delete(role)
    await db.commit()
    return MessageResponse(message="Rôle retiré des comptes et supprimé.")


@router.get("/settings", response_model=ApplicationSettingsOut)
async def get_application_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    setting = await db.get(ApplicationSetting, "registration_open")
    return ApplicationSettingsOut(
        registration_open=setting is None or setting.value == "true"
    )


@router.put("/settings", response_model=ApplicationSettingsOut)
async def update_application_settings(
    payload: ApplicationSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    setting = await db.get(ApplicationSetting, "registration_open")
    if setting is None:
        setting = ApplicationSetting(
            key="registration_open",
            value="true" if payload.registration_open else "false",
        )
        db.add(setting)
    else:
        setting.value = "true" if payload.registration_open else "false"
    await db.commit()
    return ApplicationSettingsOut(registration_open=payload.registration_open)


# --- Google Sheets configuration ---

@router.get("/settings/google-sheets", response_model=GoogleSheetsConfigOut)
async def get_google_sheets_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> GoogleSheetsConfigOut:
    """Récupère la configuration Google Sheets (sans données sensibles)."""
    settings = await load_settings_from_db(db)
    service = await build_from_db(db)
    configured = service.configured

    spreadsheet_id = str(settings["spreadsheet_id"])
    sheet_name = str(settings["sheet_name"])
    timeout_seconds = int(settings["timeout_seconds"])
    s3_key = str(settings["s3_key"])

    read_spreadsheet_id = str(settings["read_spreadsheet_id"])
    read_sheet_name = str(settings["read_sheet_name"])
    read_lses_cell = str(settings["read_lses_cell"])
    read_safd_cell = str(settings["read_safd_cell"])
    write_name_cell = str(settings["write_name_cell"])
    write_phone_cell = str(settings["write_phone_cell"])
    write_hospital_cell = str(settings["write_hospital_cell"])
    write_info_cell = str(settings["write_info_cell"])

    try:
        service_account_configured = s3_service.object_exists(s3_key, prefix="credentials/")
    except S3ServiceError:
        service_account_configured = False

    connection_status = "non_configuré"
    connection_error: str | None = None

    if not spreadsheet_id:
        connection_error = "Spreadsheet ID manquant."
    elif not sheet_name:
        connection_error = "Nom d'onglet manquant."
    elif not service_account_configured:
        connection_error = "Credentials du compte de service introuvables sur S3."
    else:
        connection_status = "connecté"
        try:
            test = await asyncio.wait_for(service.test_connection(), timeout=5.0)
            if not test["connected"]:
                connection_status = "erreur"
                connection_error = test.get("error") or "Erreur de connexion inconnue."
        except asyncio.TimeoutError:
            logger.warning("Test de connexion Google Sheets dépassé (timeout 5s).")
            connection_status = "erreur"
            connection_error = "Connexion Google Sheets dépassée (timeout)."
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erreur lors du test de connexion Google Sheets.")
            connection_status = "erreur"
            connection_error = str(exc)

    return GoogleSheetsConfigOut(
        configured=configured,
        enabled=bool(settings["enabled"]),
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        timeout_seconds=timeout_seconds,
        service_account_configured=service_account_configured,
        connection_status=connection_status,
        connection_error=connection_error,
        read_enabled=bool(settings["read_enabled"]),
        read_spreadsheet_id=read_spreadsheet_id,
        read_sheet_name=read_sheet_name,
        read_lses_cell=read_lses_cell,
        read_safd_cell=read_safd_cell,
        write_name_cell=write_name_cell,
        write_phone_cell=write_phone_cell,
        write_hospital_cell=write_hospital_cell,
        write_info_cell=write_info_cell,
    )


@router.put("/settings/google-sheets", response_model=GoogleSheetsConfigOut)
async def update_google_sheets_config(
    payload: GoogleSheetsConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> GoogleSheetsConfigOut:
    """Met à jour la configuration Google Sheets (Spreadsheet ID, nom d'onglet, activation, délai)."""

    logger.info(f"Saving Google Sheets config: spreadsheet_id={payload.spreadsheet_id}, sheet_name={payload.sheet_name}, enabled={payload.enabled}")
    logger.info(f"Payload received: read_spreadsheet_id={payload.read_spreadsheet_id}, read_sheet_name={payload.read_sheet_name}, read_lses_cell={payload.read_lses_cell}, read_safd_cell={payload.read_safd_cell}, read_enabled={payload.read_enabled}")
    logger.info(f"Payload write: write_name_cell={payload.write_name_cell}, write_phone_cell={payload.write_phone_cell}, write_hospital_cell={payload.write_hospital_cell}, write_info_cell={payload.write_info_cell}")

    async def _upsert(key: str, value: str) -> None:
        setting = await db.get(ApplicationSetting, key)
        if setting is None:
            db.add(ApplicationSetting(key=key, value=value))
        else:
            setting.value = value

    await _upsert("google_sheets_spreadsheet_id", payload.spreadsheet_id)
    await _upsert("google_sheets_sheet_name", payload.sheet_name)
    await _upsert("google_sheets_enabled", "true" if payload.enabled else "false")
    await _upsert(
        "google_sheets_timeout_seconds",
        str(max(1, int(payload.timeout_seconds or 15))),
    )
    await _upsert("google_sheets_read_spreadsheet_id", payload.read_spreadsheet_id)
    await _upsert("google_sheets_read_sheet_name", payload.read_sheet_name)
    await _upsert("google_sheets_read_lses_cell", payload.read_lses_cell)
    await _upsert("google_sheets_read_safd_cell", payload.read_safd_cell)
    await _upsert("google_sheets_read_enabled", "true" if payload.read_enabled else "false")
    await _upsert("google_sheets_write_name_cell", payload.write_name_cell)
    await _upsert("google_sheets_write_phone_cell", payload.write_phone_cell)
    await _upsert("google_sheets_write_hospital_cell", payload.write_hospital_cell)
    await _upsert("google_sheets_write_info_cell", payload.write_info_cell)

    await db.commit()
    logger.info("Google Sheets config saved successfully")

    # Recharger la config via l'endpoint GET
    return await get_google_sheets_config(db, _)


@router.post("/settings/google-sheets/service-account", response_model=MessageResponse)
async def upload_google_service_account(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageResponse:
    """Upload le fichier JSON du compte de service Google vers S3.

    Le fichier est stocké sous la clé définie par le réglage
    google_sheets_s3_key (défaut : google-service-account.json).
    Les credentials S3 doivent être configurés dans les variables d'environnement.
    """
    settings = await load_settings_from_db(db)
    s3_key = str(settings["s3_key"])

    # Lire le contenu du fichier
    content = await file.read()
    try:
        # Valider que c'est un JSON valide
        json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Le fichier n'est pas un JSON valide : {exc}",
        ) from exc

    try:
        s3_service.upload_service_account(s3_key, content, prefix="credentials/")
    except S3ServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Échec de l'upload vers S3 : {exc}",
        ) from exc

    logger.info(
        "Compte de service Google uploadé vers S3 (clé=credentials/%s).", s3_key
    )
    return MessageResponse(message="Compte de service Google uploadé vers S3 avec succès.")


@router.delete("/settings/google-sheets/service-account", response_model=MessageResponse)
async def delete_google_service_account(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> MessageResponse:
    """Supprime le fichier JSON du compte de service de S3."""
    settings = await load_settings_from_db(db)
    s3_key = str(settings["s3_key"])

    try:
        s3_service.delete_service_account(s3_key, prefix="credentials/")
    except S3ServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Échec de la suppression depuis S3 : {exc}",
        ) from exc

    logger.info("Compte de service Google supprimé de S3 (clé=credentials/%s).", s3_key)
    return MessageResponse(message="Compte de service Google supprimé de S3 avec succès.")


@router.post("/settings/google-sheets/test", response_model=GoogleSheetsTestResponse)
async def test_google_sheets_connection(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> GoogleSheetsTestResponse:
    """Teste la connexion au Google Sheets configuré."""
    try:
        service = await build_from_db(db)
        test = await service.test_connection()
        return GoogleSheetsTestResponse(
            connected=test["connected"],
            error=test.get("error"),
            spreadsheet_title=test.get("spreadsheet_title"),
            sheet_names=test.get("sheet_names", []),
            target_sheet_found=test.get("target_sheet_found", False),
        )
    except GoogleSheetsError as exc:
        return GoogleSheetsTestResponse(
            connected=False,
            error=str(exc),
            spreadsheet_title=None,
            sheet_names=[],
            target_sheet_found=False,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Erreur inattendue lors du test de connexion.")
        return GoogleSheetsTestResponse(
            connected=False,
            error=f"Erreur inattendue : {type(exc).__name__}",
            spreadsheet_title=None,
            sheet_names=[],
            target_sheet_found=False,
        )


@router.get("/settings/google-sheets/status", response_model=GoogleSheetsConfigOut)
async def get_google_sheets_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> GoogleSheetsConfigOut:
    """Retourne uniquement l'état de connexion Google Sheets."""
    settings = await load_settings_from_db(db)
    service = await build_from_db(db)
    configured = service.configured

    spreadsheet_id = str(settings["spreadsheet_id"])
    sheet_name = str(settings["sheet_name"])
    timeout_seconds = int(settings["timeout_seconds"])
    s3_key = str(settings["s3_key"])

    read_spreadsheet_id = str(settings["read_spreadsheet_id"])
    read_sheet_name = str(settings["read_sheet_name"])
    read_lses_cell = str(settings["read_lses_cell"])
    read_safd_cell = str(settings["read_safd_cell"])
    write_name_cell = str(settings["write_name_cell"])
    write_phone_cell = str(settings["write_phone_cell"])
    write_hospital_cell = str(settings["write_hospital_cell"])
    write_info_cell = str(settings["write_info_cell"])

    try:
        service_account_configured = s3_service.object_exists(s3_key, prefix="credentials/")
    except S3ServiceError:
        service_account_configured = False

    connection_status = "non_configuré"
    connection_error: str | None = None

    if not spreadsheet_id:
        connection_error = "Spreadsheet ID manquant."
    elif not sheet_name:
        connection_error = "Nom d'onglet manquant."
    elif not service_account_configured:
        connection_error = "Credentials du compte de service introuvables sur S3."
    else:
        connection_status = "connecté"

    return GoogleSheetsConfigOut(
        configured=configured,
        enabled=bool(settings["enabled"]),
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        timeout_seconds=timeout_seconds,
        service_account_configured=service_account_configured,
        connection_status=connection_status,
        connection_error=connection_error,
        read_enabled=bool(settings["read_enabled"]),
        read_spreadsheet_id=read_spreadsheet_id,
        read_sheet_name=read_sheet_name,
        read_lses_cell=read_lses_cell,
        read_safd_cell=read_safd_cell,
        write_name_cell=write_name_cell,
        write_phone_cell=write_phone_cell,
        write_hospital_cell=write_hospital_cell,
        write_info_cell=write_info_cell,
    )


@router.post("/registrations/{user_id}/approve", response_model=MessageResponse)
async def approve_registration(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    target = await db.get(User, user_id)
    if target is None or target.status != "pending":
        raise HTTPException(status_code=404, detail="Demande en attente introuvable.")
    target.status = "active"
    employee = (
        await db.execute(select(Employee).where(Employee.account_user_id == target.id))
    ).scalar_one_or_none()
    if employee is not None:
        employee.is_active = True
    await db.commit()
    if employee is not None:
        await push_employees_changed()
    return MessageResponse(message=f"{target.discord_username} validé.")


@router.post("/registrations/{user_id}/reject", response_model=MessageResponse)
async def reject_registration(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    target = await db.get(User, user_id)
    if target is None or target.status != "pending":
        raise HTTPException(status_code=404, detail="Demande en attente introuvable.")
    target.status = "rejected"
    employee = (
        await db.execute(select(Employee).where(Employee.account_user_id == target.id))
    ).scalar_one_or_none()
    if employee is not None:
        employee.is_active = False
    await db.commit()
    if employee is not None:
        await push_employees_changed()
    return MessageResponse(message=f"Demande de {target.discord_username} refusée.")
