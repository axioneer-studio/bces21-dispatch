from collections.abc import AsyncIterator
import json

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.session import current_user_id
from database import get_db
from models import User

PAGE_KEYS = frozenset(
    {"dispatch", "agenda", "human-resources", "direction", "administration"}
)


async def get_current_user(
    user_id: int = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide.",
        )
    if (user.status or "active") != "active":
        detail = (
            "Compte en attente de validation."
            if user.status == "pending"
            else "Compte désactivé ou accès refusé."
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return user


def require_page_access(page: str):
    if page not in PAGE_KEYS:
        raise ValueError(f"Unknown page permission: {page}")

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user_has_page_access(user, page):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès à cette page non autorisé.",
        )

    return dependency


def user_has_page_access(user: User, page: str) -> bool:
    if user.has_super_admin_rights:
        return True
    if user.role is None:
        return False
    try:
        pages = json.loads(user.role.pages)
    except (TypeError, ValueError):
        return False
    return isinstance(pages, list) and page in pages


def require_any_page_access(*pages: str):
    if not pages or not set(pages).issubset(PAGE_KEYS):
        raise ValueError("At least one valid page permission is required.")

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if any(user_has_page_access(user, page) for page in pages):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès à cette page non autorisé.",
        )

    return dependency


async def require_role(user: User = Depends(get_current_user)) -> User:
    """Compte ayant un rôle (ou super-admin) : condition des pages ouvertes à tous."""
    if user.has_super_admin_rights or user.role_id is not None:
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Aucun rôle ne vous donne accès à l’application.",
    )


async def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if not user.has_super_admin_rights:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits super-admin requis.",
        )
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user_has_page_access(user, "administration"):
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Droits d’administration requis.",
    )