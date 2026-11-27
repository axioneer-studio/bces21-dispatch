import json

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import current_user_id
from app.database import get_db
from app.models import User
from app.services.service_chief import is_service_chief

# Pages ouvertes à tout compte validé par un admin, même sans rôle.
OPEN_PAGES = frozenset(
    {"dispatch", "crisis", "hospital", "agenda", "stock", "training"}
)
# Pages à cocher dans un rôle (« Pages accessibles »). Ressources humaines n'en
# fait pas partie : elle est réservée aux droits RH et à la Direction (voir
# training_rights).
PAGE_KEYS = frozenset({"direction", "administration"})


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
    user.is_service_chief = await is_service_chief(db, user)
    return user


def require_page_access(page: str):
    if page not in PAGE_KEYS | OPEN_PAGES:
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
    if page in OPEN_PAGES:
        return (user.status or "active") == "active"
    return page in user_role_pages(user)


def parse_role_pages(value: str | None) -> list[str]:
    try:
        pages = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return (
        [page for page in pages if isinstance(page, str)]
        if isinstance(pages, list)
        else []
    )


def user_role_pages(user: User) -> list[str]:
    """Pages cochées dans l'ensemble des rôles du compte, sans doublon."""
    return list(
        dict.fromkeys(
            page for role in user.roles for page in parse_role_pages(role.pages)
        )
    )


def require_any_page_access(*pages: str):
    if not pages or not set(pages).issubset(PAGE_KEYS | OPEN_PAGES):
        raise ValueError("At least one valid page permission is required.")

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if any(user_has_page_access(user, page) for page in pages):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès à cette page non autorisé.",
        )

    return dependency


async def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if not user.has_super_admin_rights:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits super-admin requis.",
        )
    return user


async def require_super_admin_manager(user: User = Depends(get_current_user)) -> User:
    """Donner et retirer le statut super-admin (page Direction) : le chef de
    service, même s'il a désactivé ses droits super-admin, et les super-admins."""
    if user.is_service_chief or user.has_super_admin_rights:
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Réservé au chef de service et aux super-admins.",
    )


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user_has_page_access(user, "administration"):
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Droits d’administration requis.",
    )
