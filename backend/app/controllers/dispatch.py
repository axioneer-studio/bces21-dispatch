"""Contrôleur Dispatch : état, slots, affectations, radios, snapshot et WebSocket."""

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import (
    DispatchAssignment,
    DispatchNote,
    DispatchRadio,
    DispatchSlot,
    DispatchState,
    Employee,
    FleetEntry,
    InterventionStatus,
    ParkingSpot,
    User,
    Vehicle,
    intervention_status_order,
    utcnow,
)
from app.schemas import (
    AssignRequest,
    DispatchNoteUpdateRequest,
    DispatchResetRequest,
    DispatchSnapshot,
    FleetEntryOut,
    InterventionStatusOut,
    MessageResponse,
    ParkingSpotOut,
    RadioOut,
    RadioUpdateRequest,
    SlotCreateRequest,
    SlotOut,
    SlotUpdateRequest,
    StateOut,
    StateUpdateRequest,
    VehicleOut,
    mask_serial,
)
from app.services import crisis_link as cl
from app.services.frequency_settings import read_all_bounds
from app.services.google_sheets_service import (
    GoogleSheetsError,
    GoogleSheetsService,
    load_settings_from_db,
)
from app.services.grade_permissions import (
    user_has_grade_permission,
)

logger = logging.getLogger("bces.dispatch")


# --- Traduction des statuts pour l'affichage sur Google Sheets ---

_HOSPITAL_STATUS_LABELS = {
    "ouvert": "Ouvert",
    "ferme": "Fermé",
    "nuit": "Mode nuit",
}


def _hospital_status_label(value: str | None) -> str:
    """Retourne le libellé d'affichage du statut hôpital pour Google Sheets."""
    if not value:
        return ""
    return _HOSPITAL_STATUS_LABELS.get(value.strip().lower(), value)


# --- Verrou pour éviter les synchronisations simultanées ---

_sheets_sync_lock = asyncio.Lock()


async def _sync_employee_to_google_sheets() -> None:
    """Écrit le nom et le téléphone du premier employé affecté vers Google Sheets."""
    async with _sheets_sync_lock:
        async with SessionLocal() as db:
            settings = await load_settings_from_db(db)

            first_employee_name = ""
            first_employee_phone = ""
            result = await db.execute(
                select(Employee.first_name, Employee.last_name, Employee.phone)
                .join(DispatchAssignment, DispatchAssignment.employee_id == Employee.id)
                .join(DispatchSlot, DispatchSlot.id == DispatchAssignment.slot_id)
                .where(DispatchSlot.kind == "centrale")
                .order_by(DispatchAssignment.order.asc(), DispatchAssignment.created_at.asc())
                .limit(1)
            )
            row = result.first()
            if row:
                first_employee_name = f"{row.first_name} {row.last_name}".strip()
                first_employee_phone = row.phone or ""

        if not bool(settings["enabled"]):
            logger.debug("Synchronisation Google Sheets désactivée.")
            return

        spreadsheet_id = str(settings["spreadsheet_id"])
        sheet_name = str(settings["sheet_name"])
        if not spreadsheet_id or not sheet_name:
            logger.debug("Google Sheets non configuré, synchronisation ignorée.")
            return

        service = GoogleSheetsService(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            timeout_seconds=int(settings["timeout_seconds"]),
            s3_key=str(settings["s3_key"]),
        )
        if not service.configured:
            logger.debug("Google Sheets non configuré (credentials absents), synchronisation ignorée.")
            return

        try:
            name_cell = str(settings.get("write_name_cell") or "A1")
            phone_cell = str(settings.get("write_phone_cell") or "B1")
            await service.write_values_batch(
                ranges=[
                    (name_cell, [[first_employee_name]]),
                    (phone_cell, [[first_employee_phone]]),
                ],
                value_input_option="USER_ENTERED",
            )
            logger.debug(
                "Employé synchronisé vers Google Sheets : name=%s, phone=%s",
                first_employee_name,
                first_employee_phone,
            )
        except GoogleSheetsError as exc:
            logger.warning(
                "Échec de la synchronisation employé Google Sheets (non bloquant) : %s", exc
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "Erreur inattendue lors de la synchronisation employé Google Sheets : %s", exc
            )


async def _sync_all_to_google_sheets(state: DispatchState) -> None:
    """Synchronise employé (centrale) + état (hôpital/info) en UNE seule requête batch."""
    async with _sheets_sync_lock:
        async with SessionLocal() as db:
            settings = await load_settings_from_db(db)

            first_employee_name = ""
            first_employee_phone = ""
            result = await db.execute(
                select(Employee.first_name, Employee.last_name, Employee.phone)
                .join(DispatchAssignment, DispatchAssignment.employee_id == Employee.id)
                .join(DispatchSlot, DispatchSlot.id == DispatchAssignment.slot_id)
                .where(DispatchSlot.kind == "centrale")
                .order_by(DispatchAssignment.order.asc(), DispatchAssignment.created_at.asc())
                .limit(1)
            )
            row = result.first()
            if row:
                first_employee_name = f"{row.first_name} {row.last_name}".strip()
                first_employee_phone = row.phone or ""

        if not bool(settings["enabled"]):
            logger.debug("Synchronisation Google Sheets désactivée.")
            return

        spreadsheet_id = str(settings["spreadsheet_id"])
        sheet_name = str(settings["sheet_name"])
        if not spreadsheet_id or not sheet_name:
            logger.debug("Google Sheets non configuré, synchronisation ignorée.")
            return

        service = GoogleSheetsService(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            timeout_seconds=int(settings["timeout_seconds"]),
            s3_key=str(settings["s3_key"]),
        )
        if not service.configured:
            logger.debug("Google Sheets non configuré (credentials absents), synchronisation ignorée.")
            return

        try:
            name_cell = str(settings.get("write_name_cell") or "A1")
            phone_cell = str(settings.get("write_phone_cell") or "B1")
            hospital_cell = str(settings.get("write_hospital_cell") or "C1")
            info_cell = str(settings.get("write_info_cell") or "D1")
            await service.write_values_batch(
                ranges=[
                    (name_cell, [[first_employee_name]]),
                    (phone_cell, [[first_employee_phone]]),
                    (hospital_cell, [[_hospital_status_label(state.hospital_status)]]),
                    (info_cell, [[""]]),
                ],
                value_input_option="USER_ENTERED",
            )
            logger.debug(
                "Dispatch synchronisé vers Google Sheets (batch) : hospital=%s, name=%s, phone=%s",
                state.hospital_status,
                first_employee_name,
                first_employee_phone,
            )
        except GoogleSheetsError as exc:
            logger.warning(
                "Échec de la synchronisation Google Sheets (non bloquant) : %s", exc
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "Erreur inattendue lors de la synchronisation Google Sheets : %s", exc
            )


async def _sync_state_to_google_sheets(state: DispatchState) -> None:
    """Synchronise l'état du Dispatch vers Google Sheets (non-bloquant)."""
    async with _sheets_sync_lock:
        async with SessionLocal() as db:
            settings = await load_settings_from_db(db)

        if not bool(settings["enabled"]):
            logger.debug("Synchronisation Google Sheets désactivée.")
            return

        spreadsheet_id = str(settings["spreadsheet_id"])
        sheet_name = str(settings["sheet_name"])
        if not spreadsheet_id or not sheet_name:
            logger.debug("Google Sheets non configuré, synchronisation ignorée.")
            return

        service = GoogleSheetsService(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            timeout_seconds=int(settings["timeout_seconds"]),
            s3_key=str(settings["s3_key"]),
        )
        if not service.configured:
            logger.debug("Google Sheets non configuré (credentials absents), synchronisation ignorée.")
            return

        try:
            hospital_cell = str(settings.get("write_hospital_cell") or "C1")
            info_cell = str(settings.get("write_info_cell") or "D1")
            await service.write_values_batch(
                ranges=[
                    (hospital_cell, [[_hospital_status_label(state.hospital_status)]]),
                    (info_cell, [[""]]),
                ],
                value_input_option="USER_ENTERED",
            )
            logger.debug(
                "État Dispatch synchronisé vers Google Sheets : hospital=%s",
                state.hospital_status,
            )
        except GoogleSheetsError as exc:
            logger.warning(
                "Échec de la synchronisation Google Sheets (non bloquant) : %s", exc
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "Erreur inattendue lors de la synchronisation Google Sheets : %s", exc
            )


# --- WebSocket connection manager ---


class ConnectionManager:
    def __init__(self) -> None:
        self.active: set = set()
        self._lock = asyncio.Lock()
        self._send_locks: dict[Any, asyncio.Lock] = {}

    async def connect(self, ws) -> None:
        await ws.accept()
        async with self._lock:
            self.active.add(ws)
            self._send_locks[ws] = asyncio.Lock()

    async def disconnect(self, ws) -> None:
        async with self._lock:
            self.active.discard(ws)
            self._send_locks.pop(ws, None)

    async def send(self, ws, message: dict[str, Any]) -> None:
        async with self._lock:
            send_lock = self._send_locks.get(ws)
        if send_lock is None:
            return

        try:
            async with send_lock:
                await ws.send_json(message)
        except Exception:
            await self.disconnect(ws)
            try:
                await ws.close(code=1011, reason="Envoi WebSocket impossible")
            except Exception:
                pass
            raise

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self.active)
        for ws in clients:
            try:
                await self.send(ws, message)
            except Exception:
                pass


manager = ConnectionManager()
snapshot_lock = asyncio.Lock()


def sorted_radios(radios: Sequence) -> list:
    """Ordre par numéro de série, sans tenir compte de la casse."""
    return sorted(radios, key=lambda r: (r.serial.casefold(), r.serial, r.id))


def dispatch_radio_out(radio) -> RadioOut:
    """Radio telle que la voit le Dispatch : numéro de série masqué."""
    out = RadioOut.model_validate(radio)
    out.serial = mask_serial(radio.serial)
    return out


async def build_snapshot(db: AsyncSession) -> dict[str, Any]:
    slots_q = (
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .order_by(DispatchSlot.order.asc(), DispatchSlot.id.asc())
        # Mutation handlers may already have loaded these slots before commit.
        # With expire_on_commit=False, refresh their relationships so the
        # first broadcast reflects the committed assignments immediately.
        .execution_options(populate_existing=True)
    )
    slots = (await db.execute(slots_q)).scalars().all()

    radios = sorted_radios((await db.execute(select(DispatchRadio))).scalars().all())

    state = await db.get(DispatchState, 1)
    if not state:
        state = DispatchState(id=1)
        db.add(state)
        await db.commit()
    note = await db.get(DispatchNote, 1)

    fleet = (
        await db.execute(select(FleetEntry).order_by(FleetEntry.order.asc(), FleetEntry.id.asc()))
    ).scalars().all()
    vehicles = (
        await db.execute(select(Vehicle).order_by(Vehicle.name.asc(), Vehicle.plate.asc(), Vehicle.id.asc()))
    ).scalars().all()
    parking_spots = (
        await db.execute(select(ParkingSpot).order_by(ParkingSpot.name.asc()))
    ).scalars().all()
    statuses = (
        await db.execute(select(InterventionStatus).order_by(*intervention_status_order()))
    ).scalars().all()

    return {
        "slots": [SlotOut.model_validate(s).model_dump(mode="json") for s in slots],
        "radios": [dispatch_radio_out(r).model_dump(mode="json") for r in radios],
        "state": StateOut.model_validate(state).model_dump(mode="json"),
        "note": note.content if note else "",
        "fleet": [FleetEntryOut.model_validate(f).model_dump(mode="json") for f in fleet],
        "vehicles": [VehicleOut.model_validate(v).model_dump(mode="json") for v in vehicles],
        "parking_spots": [ParkingSpotOut.model_validate(p).model_dump(mode="json") for p in parking_spots],
        "statuses": [InterventionStatusOut.model_validate(s).model_dump(mode="json") for s in statuses],
        "frequency_bounds": {
            kind: bounds.model_dump(mode="json") for kind, bounds in (await read_all_bounds(db)).items()
        },
    }


async def push_snapshot(db: AsyncSession) -> None:
    async with snapshot_lock:
        snap = await build_snapshot(db)
        await manager.broadcast({"type": "snapshot", "data": snap})


async def push_employees_changed() -> None:
    await manager.broadcast({"type": "employees_changed"})


# --- Handlers REST ---


async def get_snapshot(db: AsyncSession) -> DispatchSnapshot:
    return await build_snapshot(db)


async def update_dispatch_note(
    payload: DispatchNoteUpdateRequest, db: AsyncSession
) -> DispatchSnapshot:
    note = await db.get(DispatchNote, 1)
    if note is None:
        note = DispatchNote(id=1, content=payload.content)
        db.add(note)
    else:
        note.content = payload.content
    await db.commit()
    snapshot = await build_snapshot(db)
    await manager.broadcast({"type": "snapshot", "data": snapshot})
    return snapshot


async def reset_assignments(
    payload: DispatchResetRequest, current_user: User, db: AsyncSession
) -> DispatchSnapshot:
    if not await user_has_grade_permission(current_user, db, "dispatch.manage_assignments"):
        raise HTTPException(
            status_code=403,
            detail="Votre grade ne vous autorise pas à gérer les affectations.",
        )
    if payload.delete_interventions and not await user_has_grade_permission(
        current_user, db, "dispatch.manage_slots"
    ):
        raise HTTPException(
            status_code=403,
            detail="Votre grade ne vous autorise pas à supprimer les interventions.",
        )

    linked_id = await cl.linked_slot_id(db)
    if linked_id is not None:
        await cl.slot_emptied(db, linked_id)
    await db.execute(delete(DispatchAssignment))
    await db.execute(
        update(DispatchRadio)
        .where((DispatchRadio.is_on.is_(True)) | (DispatchRadio.is_loading.is_(True)))
        .values(is_on=False, is_loading=False)
    )
    if payload.delete_interventions:
        await db.execute(
            delete(DispatchSlot).where(
                DispatchSlot.kind.in_(("intervention", "consultation"))
            )
        )
    state = await db.get(DispatchState, 1)
    if state is None:
        state = DispatchState(id=1)
        db.add(state)
    state.hospital_status = "ferme"
    await db.commit()
    snapshot = await build_snapshot(db)
    await manager.broadcast({"type": "assignments_reset", "data": snapshot})
    asyncio.create_task(_sync_all_to_google_sheets(state))
    return snapshot


FIXED_SLOT_KINDS = {
    "centrale",
    "hopital",
    "astreinte",
    "conges",
    "ipt",
    "astreinte-fin",
    "pause",
}


async def create_slot(
    payload: SlotCreateRequest, db: AsyncSession
) -> SlotOut:
    result = await db.execute(select(DispatchSlot).order_by(DispatchSlot.order.desc()).limit(1))
    last = result.scalar_one_or_none()
    order = (last.order + 1) if last else 0
    slot = DispatchSlot(
        kind=payload.kind,
        title=payload.kind.capitalize(),
        order=order,
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    result = await db.execute(
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .where(DispatchSlot.id == slot.id)
    )
    slot = result.scalar_one()
    await push_snapshot(db)
    return SlotOut.model_validate(slot)


async def update_slot(
    slot_id: int, payload: SlotUpdateRequest, db: AsyncSession
) -> SlotOut:
    result = await db.execute(
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .where(DispatchSlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot introuvable")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(slot, k, v)
    if "status" in data:
        await cl.sync_crisis_from_slot(db, slot)
    await db.commit()
    await db.refresh(slot)
    await push_snapshot(db)
    return SlotOut.model_validate(slot)


async def delete_slot(slot_id: int, db: AsyncSession) -> MessageResponse:
    slot = await db.get(DispatchSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot introuvable")
    if slot.kind in FIXED_SLOT_KINDS:
        raise HTTPException(status_code=400, detail="Case fixe — non supprimable")
    await cl.slot_emptied(db, slot.id)
    await db.delete(slot)
    await db.commit()
    await push_snapshot(db)
    return MessageResponse(message="Supprimé")


async def _renumber_slot_orders(db: AsyncSession, slot_id: int) -> None:
    """Renumérote séquentiellement (0, 1, 2…) les orders des affectations d'un slot."""
    result = await db.execute(
        select(DispatchAssignment)
        .where(DispatchAssignment.slot_id == slot_id)
        .order_by(DispatchAssignment.created_at.asc(), DispatchAssignment.id.asc())
    )
    for index, assignment in enumerate(result.scalars().all()):
        assignment.order = index


async def assign_user(
    slot_id: int, payload: AssignRequest, db: AsyncSession
) -> SlotOut:
    slot_q = await db.execute(
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .where(DispatchSlot.id == slot_id)
    )
    slot = slot_q.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot introuvable")

    employee = await db.get(Employee, payload.employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employé introuvable")
    if not employee.is_active:
        raise HTTPException(status_code=409, detail="Cet employé est inactif.")

    result = await db.execute(
        select(DispatchAssignment).where(DispatchAssignment.employee_id == employee.id)
    )
    assignment = result.scalar_one_or_none()
    joined = assignment is None or assignment.slot_id != slot.id
    if assignment is not None and joined:
        await cl.employee_left_slot(db, assignment.slot_id, employee.id)
    if assignment is None:
        assignment = DispatchAssignment(employee_id=employee.id, order=0)
        assignment.slot_id = slot.id
        db.add(assignment)
        await db.flush()
    elif assignment.slot_id != slot.id:
        assignment.slot_id = slot.id
        assignment.order = 0
        assignment.created_at = utcnow()

    if joined:
        await cl.sync_crisis_from_slot(db, slot, joined_id=employee.id)
    await db.commit()
    await _renumber_slot_orders(db, slot_id)
    await db.commit()
    await db.refresh(slot)
    await push_snapshot(db)
    asyncio.create_task(_sync_employee_to_google_sheets())
    result = await db.execute(
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .where(DispatchSlot.id == slot_id)
    )
    slot = result.scalar_one()
    return SlotOut.model_validate(slot)


async def unassign_user(
    slot_id: int, employee_id: int, db: AsyncSession
) -> SlotOut:
    slot = await db.get(DispatchSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot introuvable")
    result = await db.execute(
        select(DispatchAssignment).where(
            DispatchAssignment.slot_id == slot_id,
            DispatchAssignment.employee_id == employee_id,
        )
    )
    a = result.scalar_one_or_none()
    if a:
        await db.delete(a)
        radio = await db.scalar(
            select(DispatchRadio).where(DispatchRadio.employee_id == employee_id).limit(1)
        )
        if radio is not None and (radio.is_on or radio.is_loading):
            radio.is_on = False
            radio.is_loading = False
        await db.flush()
        await cl.employee_left_slot(db, slot_id, employee_id)
        await db.commit()
        await _renumber_slot_orders(db, slot_id)
        await db.commit()
    result = await db.execute(
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .where(DispatchSlot.id == slot_id)
    )
    slot = result.scalar_one()
    await push_snapshot(db)
    asyncio.create_task(_sync_employee_to_google_sheets())
    return SlotOut.model_validate(slot)


async def update_radio(
    radio_id: int, payload: RadioUpdateRequest, db: AsyncSession
) -> RadioOut:
    radio = await db.get(DispatchRadio, radio_id)
    if not radio:
        raise HTTPException(status_code=404, detail="Radio introuvable")
    data = payload.model_dump(exclude_unset=True)
    if data.get("employee_id") is not None:
        employee = await db.get(Employee, data["employee_id"])
        if employee is None or not employee.is_active:
            raise HTTPException(status_code=404, detail="Employé actif introuvable.")
        other_radio = await db.scalar(
            select(DispatchRadio.serial).where(
                DispatchRadio.employee_id == employee.id,
                DispatchRadio.id != radio_id,
            ).limit(1)
        )
        if other_radio is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Cet employé a déjà une radio ({mask_serial(other_radio) or 'sans numéro'}).",
            )
    if "employee_id" in data:
        radio.doctor_id = None

    next_employee_id = data.get("employee_id", radio.employee_id)
    if next_employee_id is None:
        if data.get("is_on") or data.get("is_loading"):
            raise HTTPException(
                status_code=409,
                detail="Affectez la radio à un employé avant de l’allumer.",
            )
        data["is_on"] = False
        data["is_loading"] = False
    elif data.get("is_on") and data.get("is_loading"):
        raise HTTPException(
            status_code=422, detail="Une radio ne peut pas être à la fois ON et indisponible."
        )
    elif data.get("is_on"):
        data["is_loading"] = False
    elif data.get("is_loading"):
        data["is_on"] = False

    for k, v in data.items():
        setattr(radio, k, v)
    await db.commit()
    await db.refresh(radio)
    await push_snapshot(db)
    return dispatch_radio_out(radio)


async def update_state(
    payload: StateUpdateRequest, db: AsyncSession
) -> StateOut:
    state = await db.get(DispatchState, 1)
    if not state:
        state = DispatchState(id=1)
        db.add(state)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(state, k, v)
    await db.commit()
    await db.refresh(state)
    asyncio.create_task(_sync_state_to_google_sheets(state))
    await push_snapshot(db)
    return StateOut.model_validate(state)
