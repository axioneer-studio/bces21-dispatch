"""Routes des fréquences (couche transport mince)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import frequencies as cfreq
from app.deps import get_db, require_page_access
from app.models import User
from app.schemas import FrequencyKind
from app.services.grade_permissions import require_grade_permission

router = APIRouter(tags=["frequencies"])


@router.post(
    "/api/dispatch/frequencies/{kind}/random",
    response_model=cfreq.FrequencySettingOut,
)
async def randomize_frequency(
    kind: FrequencyKind,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
    __: User = Depends(require_grade_permission("dispatch.manage_state")),
) -> cfreq.FrequencySettingOut:
    return await cfreq.randomize_frequency(kind, db)
