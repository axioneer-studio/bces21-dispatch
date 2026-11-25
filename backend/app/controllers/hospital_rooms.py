"""Contrôleur des chambres et lits de l'hôpital."""

import re

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CrisisVictim, HospitalBed, HospitalBedReason, HospitalRoom
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
from app.services.hospital_access import (
    user_can_manage_hospital,
)

_BED_LABEL = re.compile(r"^lit (\d+)$", re.IGNORECASE)


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


async def _ensure_room_name_available(
    db: AsyncSession, name: str, room_id: int | None = None
) -> None:
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


def clear_patient(bed: HospitalBed) -> None:
    bed.patient_name = None
    bed.accident = ""
    bed.arrival_date = None
    bed.care_done = False
    bed.police_status = "none"
    bed.reason = ""


async def get_rooms(db: AsyncSession, user) -> HospitalRoomsOut:
    rooms = (
        await db.execute(select(HospitalRoom).order_by(HospitalRoom.order, HospitalRoom.id))
    ).scalars().all()
    reasons = (
        await db.execute(select(HospitalBedReason).order_by(HospitalBedReason.name))
    ).scalars().all()
    return HospitalRoomsOut(
        rooms=[HospitalRoomOut.model_validate(room) for room in rooms],
        reasons=[HospitalBedReasonOut.model_validate(reason) for reason in reasons],
        can_manage=await user_can_manage_hospital(db, user),
    )


async def create_room(
    payload: HospitalRoomRequest, db: AsyncSession
) -> HospitalRoomOut:
    await _ensure_room_name_available(db, payload.name)
    last_order = await db.scalar(select(func.max(HospitalRoom.order)))
    room = HospitalRoom(name=payload.name, order=(last_order or 0) + 1)
    db.add(room)
    await db.commit()
    await db.refresh(room, ["beds"])
    return HospitalRoomOut.model_validate(room)


async def rename_room(
    room_id: int, payload: HospitalRoomRequest, db: AsyncSession
) -> HospitalRoomOut:
    room = await _get_room(db, room_id)
    await _ensure_room_name_available(db, payload.name, room.id)
    room.name = payload.name
    await db.commit()
    await db.refresh(room, ["beds"])
    return HospitalRoomOut.model_validate(room)


async def delete_room(room_id: int, db: AsyncSession) -> MessageResponse:
    room = await _get_room(db, room_id)
    if any(bed.patient_name for bed in room.beds):
        raise HTTPException(
            status_code=409,
            detail="Libérez les lits occupés avant de supprimer la chambre.",
        )
    await db.delete(room)
    await db.commit()
    return {"message": "Chambre supprimée."}


async def create_bed(room_id: int, db: AsyncSession) -> HospitalBedOut:
    room = await _get_room(db, room_id)
    bed = HospitalBed(room_id=room.id, label=_next_bed_label(room))
    db.add(bed)
    await db.commit()
    await db.refresh(bed)
    return HospitalBedOut.model_validate(bed)


async def rename_bed(
    bed_id: int, payload: HospitalBedRenameRequest, db: AsyncSession
) -> HospitalBedOut:
    """Renomme le lit, sans changer sa place : les lits restent dans l'ordre de création."""
    bed = await _get_bed(db, bed_id)
    duplicate = await db.scalar(
        select(HospitalBed.id)
        .where(
            HospitalBed.room_id == bed.room_id,
            HospitalBed.id != bed.id,
            func.lower(HospitalBed.label) == payload.label.lower(),
        )
        .limit(1)
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Un lit de cette chambre porte déjà ce nom.")
    bed.label = payload.label
    await db.commit()
    await db.refresh(bed)
    return HospitalBedOut.model_validate(bed)


async def delete_bed(bed_id: int, db: AsyncSession) -> MessageResponse:
    bed = await _get_bed(db, bed_id)
    if bed.patient_name:
        raise HTTPException(status_code=409, detail="Libérez ce lit avant de le supprimer.")
    await db.delete(bed)
    await db.commit()
    return {"message": "Lit supprimé."}


async def set_patient(
    bed_id: int, payload: HospitalPatientRequest, db: AsyncSession
) -> HospitalBedOut:
    """Affecte un patient au lit, ou met à jour sa fiche s'il y est déjà."""
    bed = await _get_bed(db, bed_id)
    for key, value in payload.model_dump().items():
        setattr(bed, key, value)
    await db.commit()
    await db.refresh(bed)
    return HospitalBedOut.model_validate(bed)


async def set_bed_flags(
    bed_id: int, payload: HospitalBedFlagsRequest, db: AsyncSession
) -> HospitalBedOut:
    bed = await _get_bed(db, bed_id)
    if not bed.patient_name:
        raise HTTPException(status_code=409, detail="Ce lit est libre.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(bed, key, value)
    await db.commit()
    await db.refresh(bed)
    return HospitalBedOut.model_validate(bed)


async def release_bed(bed_id: int, db: AsyncSession) -> HospitalBedOut:
    bed = await _get_bed(db, bed_id)
    clear_patient(bed)
    await db.execute(
        update(CrisisVictim).where(CrisisVictim.bed_id == bed.id).values(bed_id=None)
    )
    await db.commit()
    await db.refresh(bed)
    return HospitalBedOut.model_validate(bed)


async def create_reason(
    payload: HospitalBedReasonRequest, db: AsyncSession
) -> HospitalBedReasonOut:
    existing = await db.scalar(
        select(HospitalBedReason.id).where(
            func.lower(HospitalBedReason.name) == payload.name.lower()
        ).limit(1)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Cette raison existe déjà.")
    reason = HospitalBedReason(name=payload.name)
    db.add(reason)
    await db.commit()
    await db.refresh(reason)
    return HospitalBedReasonOut.model_validate(reason)


async def delete_reason(reason_id: int, db: AsyncSession) -> MessageResponse:
    reason = await db.get(HospitalBedReason, reason_id)
    if not reason:
        raise HTTPException(status_code=404, detail="Raison introuvable.")
    await db.delete(reason)
    await db.commit()
    return {"message": "Raison supprimée."}
