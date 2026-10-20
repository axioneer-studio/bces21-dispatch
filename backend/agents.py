import logging

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import get_current_user
from models import User
from schemas import AgentListResponse, AgentSummary

logger = logging.getLogger("bces.agents")

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/users", response_model=AgentListResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AgentListResponse:
    rows = (
        await db.execute(
            select(User)
            .where(or_(User.status == "active", User.status.is_(None)))
            .order_by(User.prenom_rp.asc().nulls_last(), User.nom_rp.asc().nulls_last())
        )
    ).scalars().all()
    agents = [AgentSummary.model_validate(u) for u in rows]
    from datetime import datetime, timezone
    return AgentListResponse(
        agents=agents,
        count=len(agents),
        generated_at=datetime.now(timezone.utc),
    )