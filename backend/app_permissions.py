import json

from fastapi import Depends, HTTPException, status

from deps import get_current_user
from models import User

APP_PERMISSION_CATALOG = {
    "human_resources.link_accounts": "Lier ou délier un compte utilisateur à une tuile employé",
    "hospital.forensic": "Médecin Légiste",
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
        permission
        for permission in permissions
        if permission in APP_PERMISSION_CATALOG
    ]


def user_has_app_permission(user: User, permission: str) -> bool:
    if user.has_super_admin_rights:
        return True
    return bool(
        user.role
        and permission in parse_app_permissions(user.role.permissions)
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
