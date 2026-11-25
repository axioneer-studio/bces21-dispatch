"""Contrôleur des agents (utilisateurs disponibles pour le Dispatch)."""

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas import AgentListResponse, AgentSummary


async def list_users(db: AsyncSession) -> AgentListResponse:
    rows = (
        await db.execute(
            select(User)
            .where(or_(User.status == "active", User.status.is_(None)))
            .order_by(User.prenom_rp.asc().nulls_last(), User.nom_rp.asc().nulls_last())
        )
    ).scalars().all()
    agents = [AgentSummary.model_validate(u) for u in rows]
    return AgentListResponse(
        agents=agents,
        count=len(agents),
        generated_at=datetime.now(UTC),
    )
