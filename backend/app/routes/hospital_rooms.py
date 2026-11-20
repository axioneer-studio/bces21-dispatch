"""Routes des chambres et lits de l'hôpital (couche transport mince)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import hospital_rooms as chr
from app.deps import get_current_user, get_db, require_page_access
from app.models import User
from app.schemas import (
    HospitalBedFlagsRequest,
    HospitalBedOut,
    HospitalBedReasonOut,
    HospitalBedReasonRequest,
    HospitalBedRenameRequest,
    HospitalPatientRequest,
    HospitalRoomOut,
    HospitalRoomRequest,
    HospitalRoomsOut,
    MessageResponse,
)
from app.services.app_permissions import require_app_permission
from app.services.hospital_access import require_hospital_manage

router = APIRouter(
    prefix="/api/hospital",
    tags=["hospital"],
    dependencies=[Depends(require_page_access("hospital"))],
)


@router.get("/rooms", response_model=HospitalRoomsOut)
async def get_rooms(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HospitalRoomsOut:
    return await chr.get_rooms(db, user)


@router.post(
    "/rooms",
    response_model=HospitalRoomOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_hospital_manage)],
)
async def create_room(
    payload: HospitalRoomRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("hospital")),
) -> HospitalRoomOut:
    return await chr.create_room(payload, db)


@router.patch("/rooms/{room_id}", response_model=HospitalRoomOut)
async def rename_room(
    room_id: int,
    payload: HospitalRoomRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("hospital")),
) -> HospitalRoomOut:
    return await chr.rename_room(room_id, payload, db)


@router.delete("/rooms/{room_id}", response_model=MessageResponse)
async def delete_room(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("hospital")),
) -> MessageResponse:
    return await chr.delete_room(room_id, db)


@router.post(
    "/rooms/{room_id}/beds",
    response_model=HospitalBedOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_hospital_manage)],
)
async def create_bed(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("hospital")),
) -> HospitalBedOut:
    return await chr.create_bed(room_id, db)


@router.patch("/beds/{bed_id}", response_model=HospitalBedOut)
async def rename_bed(
    bed_id: int,
    payload: HospitalBedRenameRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("hospital")),
) -> HospitalBedOut:
    return await chr.rename_bed(bed_id, payload, db)


@router.delete("/beds/{bed_id}", response_model=MessageResponse)
async def delete_bed(
    bed_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("hospital")),
) -> MessageResponse:
    return await chr.delete_bed(bed_id, db)


@router.put("/beds/{bed_id}/patient", response_model=HospitalBedOut)
async def set_patient(
    bed_id: int,
    payload: HospitalPatientRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HospitalBedOut:
    return await chr.set_patient(bed_id, payload, db)


@router.patch("/beds/{bed_id}/flags", response_model=HospitalBedOut)
async def set_bed_flags(
    bed_id: int,
    payload: HospitalBedFlagsRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HospitalBedOut:
    return await chr.set_bed_flags(bed_id, payload, db)


@router.delete("/beds/{bed_id}/patient", response_model=HospitalBedOut)
async def release_bed(
    bed_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HospitalBedOut:
    return await chr.release_bed(bed_id, db)


@router.post(
    "/bed-reasons",
    response_model=HospitalBedReasonOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_hospital_manage)],
)
async def create_reason(
    payload: HospitalBedReasonRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("hospital")),
) -> HospitalBedReasonOut:
    return await chr.create_reason(payload, db)


@router.delete("/bed-reasons/{reason_id}", response_model=MessageResponse)
async def delete_reason(
    reason_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("hospital")),
) -> MessageResponse:
    return await chr.delete_reason(reason_id, db)
