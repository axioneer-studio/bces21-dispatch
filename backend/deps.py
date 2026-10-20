from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.session import current_user_id
from database import get_db
from models import User


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
    if (user.status or "active") == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte en attente de validation.",
        )
    return user