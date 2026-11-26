import json

from fastapi import Depends, HTTPException, status

from app.deps import get_current_user
from app.models import User

APP_PERMISSION_CATALOG = {
    "hospital.manage": "Gérer l’hôpital",
}


def parse_app_permissions(value: str | None) -> list[str]:
    try:
        permissions = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(permissions, list):
        return []
    return [
        permission for permission in permissions if permission in APP_PERMISSION_CATALOG
    ]


def user_has_app_permission(user: User, permission: str) -> bool:
    if user.has_super_admin_rights:
        return True
    return permission in user_role_permissions(user)


def user_role_permissions(user: User) -> list[str]:
    """Permissions de l'ensemble des rôles du compte, sans doublon."""
    return list(
        dict.fromkeys(
            permission
            for role in user.roles
            for permission in parse_app_permissions(role.permissions)
        )
    )


def require_app_permission(permission: str):
    if permission not in APP_PERMISSION_CATALOG:
        raise ValueError(f"Unknown application permission: {permission}")

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user_has_app_permission(user, permission):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre rôle applicatif ne vous autorise pas à effectuer cette action.",
        )

    return dependency
