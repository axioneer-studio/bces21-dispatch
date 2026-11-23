"""Routes des agents (couche transport mince)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import agents as ca
from app.deps import get_db, require_page_access
from app.models import User

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/users", response_model=ca.AgentListResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
) -> ca.AgentListResponse:
    return await ca.list_users(db)
