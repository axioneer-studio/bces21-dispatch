import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dispatch import push_employees_changed
from deps import PAGE_KEYS, require_admin, require_super_admin, user_has_page_access
from app_permissions import APP_PERMISSION_CATALOG
from models import ApplicationSetting, Employee, Role, User
from schemas import (
    AdminUserOut,
    AdminUserRoleUpdateRequest,
    AdminUserStatusUpdateRequest,
    ApplicationSettingsOut,
    ApplicationSettingsUpdateRequest,
    MessageResponse,
    RoleCreateRequest,
    RoleOut,
    RoleUpdateRequest,
    SuperAdminUpdateRequest,
)

router = APIRouter(prefix="/api/admin", tags=["administration"])


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
        role_id=user.role_id,
        role_name=user.role.name if user.role else None,
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


@router.patch("/users/{user_id}/role", response_model=MessageResponse)
async def update_user_role(
    user_id: int,
    payload: AdminUserRoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if payload.role_id is not None and await db.get(Role, payload.role_id) is None:
        raise HTTPException(status_code=404, detail="Rôle introuvable.")

    next_role = await db.get(Role, payload.role_id) if payload.role_id is not None else None
    removes_admin_access = _is_app_admin(target) and not (
        target.is_super_admin
        or (
            next_role is not None
            and "administration" in _parse_pages(next_role.pages)
        )
    )
    if removes_admin_access:
        await _ensure_another_admin_remains(db, target)

    target.role_id = payload.role_id
    await db.commit()
    return MessageResponse(message="Rôle applicatif mis à jour.")


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
    output = []
    for role in roles:
        count = await db.scalar(select(func.count(User.id)).where(User.role_id == role.id))
        output.append(_role_out(role, count or 0))
    return output


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
            users = (
                await db.execute(select(User).where(User.role_id == role_id))
            ).scalars().all()
            active_super_admin = any(
                user.is_super_admin and (user.status or "active") == "active"
                for user in users
            )
            external_admin = any(
                user.role_id != role_id
                and _is_app_admin(user)
                and (user.status or "active") == "active"
                for user in (
                    await db.execute(select(User))
                ).scalars().all()
            )
            if users and not active_super_admin and not external_admin:
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
    count = await db.scalar(select(func.count(User.id)).where(User.role_id == role_id))
    return _role_out(role, count or 0)


@router.delete("/roles/{role_id}", response_model=MessageResponse)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    role = await db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Rôle introuvable.")
    count = await db.scalar(select(func.count(User.id)).where(User.role_id == role_id))
    if count:
        raise HTTPException(
            status_code=409,
            detail="Réattribuez d’abord ce rôle aux utilisateurs concernés.",
        )
    await db.delete(role)
    await db.commit()
    return MessageResponse(message="Rôle supprimé.")


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
