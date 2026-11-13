"""Chambres de l'hôpital et leurs lits.

Tout compte connecté affecte un patient à un lit, met à jour sa fiche et libère
le lit. Seuls les rôles ayant la permission `hospital.manage` (« Gérer
l'hôpital ») ajoutent, renomment et suppriment les chambres et les lits, ainsi
que la liste des raisons proposées.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app_permissions import require_app_permission, user_has_app_permission
from database import get_db
from deps import get_current_user
from models import HospitalBed, HospitalBedReason, HospitalRoom, User
from schemas import (
    HospitalBedFlagsRequest,
    HospitalBedOut,
    HospitalBedReasonOut,
    HospitalBedReasonRequest,
    HospitalPatientRequest,
    HospitalRoomOut,
    HospitalRoomRequest,
    HospitalRoomsOut,
    MessageResponse,
)

MANAGE_PERMISSION = "hospital.manage"
_BED_LABEL = re.compile(r"^Lit (\d+)$")

router = APIRouter(prefix="/api/hospital", tags=["hospital"])
require_manage = require_app_permission(MANAGE_PERMISSION)


async def _get_room(db: AsyncSession, room_id: int) -> HospitalRoom:
    room = await db.get(HospitalRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Chambre introuvable.")
    return room


async def _get_bed(db: AsyncSession, bed_id: int) -> HospitalBed:
    bed = await db.get(HospitalBed, bed_id)
    if not bed:
        raise HTTPException(status_code=404, detail="Lit introuvable.")
    return bed


async def _ensure_room_name_available(db: AsyncSession, name: str, room_id: int | None = None) -> None:
    filters = [func.lower(HospitalRoom.name) == name.lower()]
    if room_id is not None:
        filters.append(HospitalRoom.id != room_id)
    if await db.scalar(select(HospitalRoom.id).where(*filters).limit(1)) is not None:
        raise HTTPException(status_code=409, detail="Une chambre porte déjà ce nom.")


def _next_bed_label(room: HospitalRoom) -> str:
    used = {int(match.group(1)) for bed in room.beds if (match := _BED_LABEL.match(bed.label))}
    number = 1
    while number in used:
        number += 1
    return f"Lit {number}"


def _clear_patient(bed: HospitalBed) -> None:
    bed.patient_name = None
    bed.accident = ""
    bed.arrival_date = None
    bed.care_done = False
    bed.police_status = "none"
    bed.reason = ""


# --- Consultation ---


@router.get("/rooms", response_model=HospitalRoomsOut)
async def get_rooms(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rooms = (
        await db.execute(select(HospitalRoom).order_by(HospitalRoom.order, HospitalRoom.id))
    ).scalars().all()
    reasons = (
        await db.execute(select(HospitalBedReason).order_by(HospitalBedReason.name))
    ).scalars().all()
    return HospitalRoomsOut(
        rooms=[HospitalRoomOut.model_validate(room) for room in rooms],
        reasons=[HospitalBedReasonOut.model_validate(reason) for reason in reasons],
        can_manage=user_has_app_permission(user, MANAGE_PERMISSION),
    )


# --- Chambres et lits (Gérer l'hôpital) ---


@router.post("/rooms", response_model=HospitalRoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(
    payload: HospitalRoomRequest,
    _: User = Depends(require_manage),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_room_name_available(db, payload.name)
    last_order = await db.scalar(select(func.max(HospitalRoom.order)))
    room = HospitalRoom(name=payload.name, order=(last_order or 0) + 1)
    db.add(room)
    await db.commit()
    await db.refresh(room, ["beds"])
    return HospitalRoomOut.model_validate(room)


@router.patch("/rooms/{room_id}", response_model=HospitalRoomOut)
async def rename_room(
    room_id: int,
    payload: HospitalRoomRequest,
    _: User = Depends(require_manage),
    db: AsyncSession = Depends(get_db),
):
    room = await _get_room(db, room_id)
    await _ensure_room_name_available(db, payload.name, room.id)
    room.name = payload.name
    await db.commit()
    await db.refresh(room, ["beds"])
    return HospitalRoomOut.model_validate(room)


@router.delete("/rooms/{room_id}", response_model=MessageResponse)
async def delete_room(
    room_id: int,
    _: User = Depends(require_manage),
    db: AsyncSession = Depends(get_db),
):
    room = await _get_room(db, room_id)
    if any(bed.patient_name for bed in room.beds):
        raise HTTPException(
            status_code=409,
            detail="Libérez les lits occupés avant de supprimer la chambre.",
        )
    await db.delete(room)
    await db.commit()
    return {"message": "Chambre supprimée."}


@router.post("/rooms/{room_id}/beds", response_model=HospitalBedOut, status_code=status.HTTP_201_CREATED)
async def create_bed(
    room_id: int,
    _: User = Depends(require_manage),
    db: AsyncSession = Depends(get_db),
):
    room = await _get_room(db, room_id)
    bed = HospitalBed(room_id=room.id, label=_next_bed_label(room))
    db.add(bed)
    await db.commit()
    await db.refresh(bed)
    return HospitalBedOut.model_validate(bed)


@router.delete("/beds/{bed_id}", response_model=MessageResponse)
async def delete_bed(
    bed_id: int,
    _: User = Depends(require_manage),
    db: AsyncSession = Depends(get_db),
):
    bed = await _get_bed(db, bed_id)
    if bed.patient_name:
        raise HTTPException(status_code=409, detail="Libérez ce lit avant de le supprimer.")
    await db.delete(bed)
    await db.commit()
    return {"message": "Lit supprimé."}


# --- Patients (tout compte connecté) ---


@router.put("/beds/{bed_id}/patient", response_model=HospitalBedOut)
async def set_patient(
    bed_id: int,
    payload: HospitalPatientRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Affecte un patient au lit, ou met à jour sa fiche s'il y est déjà."""
    bed = await _get_bed(db, bed_id)
    for key, value in payload.model_dump().items():
        setattr(bed, key, value)
    await db.commit()
    await db.refresh(bed)
    return HospitalBedOut.model_validate(bed)


@router.patch("/beds/{bed_id}/flags", response_model=HospitalBedOut)
async def set_bed_flags(
    bed_id: int,
    payload: HospitalBedFlagsRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bed = await _get_bed(db, bed_id)
    if not bed.patient_name:
        raise HTTPException(status_code=409, detail="Ce lit est libre.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(bed, key, value)
    await db.commit()
    await db.refresh(bed)
    return HospitalBedOut.model_validate(bed)


@router.delete("/beds/{bed_id}/patient", response_model=HospitalBedOut)
async def release_bed(
    bed_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bed = await _get_bed(db, bed_id)
    _clear_patient(bed)
    await db.commit()
    await db.refresh(bed)
    return HospitalBedOut.model_validate(bed)


# --- Raisons proposées (Gérer l'hôpital) ---


@router.post("/bed-reasons", response_model=HospitalBedReasonOut, status_code=status.HTTP_201_CREATED)
async def create_reason(
    payload: HospitalBedReasonRequest,
    _: User = Depends(require_manage),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(HospitalBedReason.id).where(func.lower(HospitalBedReason.name) == payload.name.lower()).limit(1)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Cette raison existe déjà.")
    reason = HospitalBedReason(name=payload.name)
    db.add(reason)
    await db.commit()
    await db.refresh(reason)
    return HospitalBedReasonOut.model_validate(reason)


@router.delete("/bed-reasons/{reason_id}", response_model=MessageResponse)
async def delete_reason(
    reason_id: int,
    _: User = Depends(require_manage),
    db: AsyncSession = Depends(get_db),
):
    reason = await db.get(HospitalBedReason, reason_id)
    if not reason:
        raise HTTPException(status_code=404, detail="Raison introuvable.")
    await db.delete(reason)
    await db.commit()
    return {"message": "Raison supprimée."}
