import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.session import decode_token, get_session_cookie_name
from database import SessionLocal, get_db
from deps import require_page_access, user_has_page_access
from frequency_settings import read_all_bounds
from grade_permissions import require_grade_permission, user_has_grade_permission
from models import (
    DispatchAssignment,
    Employee,
    DispatchRadio,
    DispatchSlot,
    DispatchState,
    DispatchNote,
    FleetEntry,
    ParkingSpot,
    User,
    Vehicle,
    utcnow,
)
from google_sheets_service import GoogleSheetsError, GoogleSheetsService, load_settings_from_db
from schemas import (
    AssignRequest,
    DispatchNoteUpdateRequest,
    DispatchResetRequest,
    DispatchSnapshot,
    MessageResponse,
    FleetEntryOut,
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
    """Écrit le nom et le téléphone du premier employé affecté vers Google Sheets.

    Appelé à chaque affectation/désaffectation d'employé, indépendamment du
    statut hôpital. Les cellules cibles sont google_sheets_write_name_cell et
    google_sheets_write_phone_cell.
    """
    async with _sheets_sync_lock:
        # Lire la configuration depuis la base de données.
        async with SessionLocal() as db:
            settings = await load_settings_from_db(db)

            # Premier employé affecté sur la case "centrale" (nom et téléphone).
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
            logger.debug(
                "Google Sheets non configuré (credentials absents), synchronisation ignorée."
            )
            return

        try:
            name_cell = str(settings.get("write_name_cell") or "A1")
            phone_cell = str(settings.get("write_phone_cell") or "B1")

            await service.write_values(
                values=[[first_employee_name]],
                range_name=name_cell,
                value_input_option="USER_ENTERED",
            )
            await service.write_values(
                values=[[first_employee_phone]],
                range_name=phone_cell,
                value_input_option="USER_ENTERED",
            )
            logger.info(
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


async def _sync_state_to_google_sheets(state: DispatchState) -> None:
    """Synchronise l'état du Dispatch vers Google Sheets (non-bloquant).

    Ne gère que le statut hôpital et la cellule info. Le nom/téléphone de
    l'employé est géré par _sync_employee_to_google_sheets.
    """
    async with _sheets_sync_lock:
        # Lire la configuration depuis la base de données.
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
            logger.debug(
                "Google Sheets non configuré (credentials absents), synchronisation ignorée."
            )
            return

        try:
            hospital_cell = str(settings.get("write_hospital_cell") or "C1")
            info_cell = str(settings.get("write_info_cell") or "D1")

            # Statut hôpital
            await service.write_values(
                values=[[_hospital_status_label(state.hospital_status)]],
                range_name=hospital_cell,
                value_input_option="USER_ENTERED",
            )
            # Information supplémentaire (LSES/SAFD laissés vides pour le moment)
            await service.write_values(
                values=[[""]],
                range_name=info_cell,
                value_input_option="USER_ENTERED",
            )
            logger.info(
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


router = APIRouter(tags=["dispatch"])


# --- WebSocket connection manager ---

class ConnectionManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.active.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self.active.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self.active)
        for ws in clients:
            try:
                await ws.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()
snapshot_lock = asyncio.Lock()


def sorted_radios(radios: Sequence[DispatchRadio]) -> list[DispatchRadio]:
    """Ordre par numéro de série, sans tenir compte de la casse."""
    return sorted(radios, key=lambda r: (r.serial.casefold(), r.serial, r.id))


def dispatch_radio_out(radio: DispatchRadio) -> RadioOut:
    """Radio telle que la voit le Dispatch : numéro de série masqué."""
    out = RadioOut.model_validate(radio)
    out.serial = mask_serial(radio.serial)
    return out


async def build_snapshot(db: AsyncSession) -> dict[str, Any]:
    slots_q = (
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .order_by(DispatchSlot.order.asc(), DispatchSlot.id.asc())
    )
    slots = (await db.execute(slots_q)).scalars().all()

    # Le Dispatch ne reçoit que le numéro masqué : l'ordre par numéro de série
    # est donc fixé ici, et le front s'en sert pour départager ses tris
    # (section Direction, radios affectées d'abord).
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

    return {
        "slots": [SlotOut.model_validate(s).model_dump(mode="json") for s in slots],
        "radios": [dispatch_radio_out(r).model_dump(mode="json") for r in radios],
        "state": StateOut.model_validate(state).model_dump(mode="json"),
        "note": note.content if note else "",
        "fleet": [FleetEntryOut.model_validate(f).model_dump(mode="json") for f in fleet],
        "vehicles": [VehicleOut.model_validate(v).model_dump(mode="json") for v in vehicles],
        "parking_spots": [ParkingSpotOut.model_validate(p).model_dump(mode="json") for p in parking_spots],
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


# --- WebSocket endpoint ---

@router.websocket("/ws/dispatch")
async def dispatch_ws(ws: WebSocket) -> None:
    # Authentification : le cookie de session doit être présent ET valide.
    # Sans cela on rejette avant l'accept() → 403 chez le client, ce qui
    # déclenche une boucle de reconnexion inutile.
    raw_cookie = ws.cookies.get(get_session_cookie_name())
    if not raw_cookie:
        await ws.close(code=1008, reason="Non authentifié")
        return

    try:
        user_id = decode_token(raw_cookie)
    except HTTPException:
        await ws.close(code=1008, reason="Session invalide")
        return

    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        if not user or (user.status or "active") != "active" or not user_has_page_access(user, "dispatch"):
            await ws.close(code=1008, reason="Compte non autorisé")
            return

    await manager.connect(ws)
    try:
        async with snapshot_lock:
            async with SessionLocal() as db:
                snap = await build_snapshot(db)
            await ws.send_json({"type": "snapshot", "data": snap})
        while True:
            # Keep-alive : le client envoie un ping texte, on l'ignore.
            # Toute modification passe par REST puis est broadcastée ici.
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WS error: %s", exc)
    finally:
        await manager.disconnect(ws)


# --- REST endpoints ---

@router.get("/api/dispatch/snapshot", response_model=DispatchSnapshot)
async def get_snapshot(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
):
    return await build_snapshot(db)


@router.put("/api/dispatch/note", response_model=DispatchSnapshot)
async def update_dispatch_note(
    payload: DispatchNoteUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
):
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


@router.post("/api/dispatch/assignments/reset", response_model=DispatchSnapshot)
async def reset_assignments(
    payload: DispatchResetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_page_access("dispatch")),
):
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

    await db.execute(delete(DispatchAssignment))
    # Plus personne n'est en service : les radios ON ou indisponibles passent OFF.
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
    # Synchronisation employé vers Google Sheets : vide les cellules nom/téléphone
    asyncio.create_task(_sync_employee_to_google_sheets())
    # Synchronisation statut hôpital vers Google Sheets
    asyncio.create_task(_sync_state_to_google_sheets(state))
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


@router.post("/api/dispatch/slots", response_model=SlotOut, status_code=201)
async def create_slot(
    payload: SlotCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
    __: User = Depends(require_grade_permission("dispatch.manage_slots")),
):
    # next order
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
    # Re-fetch with assignments
    result = await db.execute(
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .where(DispatchSlot.id == slot.id)
    )
    slot = result.scalar_one()
    await push_snapshot(db)
    return SlotOut.model_validate(slot)


@router.patch("/api/dispatch/slots/{slot_id}", response_model=SlotOut)
async def update_slot(
    slot_id: int,
    payload: SlotUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
    __: User = Depends(require_grade_permission("dispatch.manage_slots")),
):
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
    await db.commit()
    await db.refresh(slot)
    await push_snapshot(db)
    return SlotOut.model_validate(slot)


@router.delete("/api/dispatch/slots/{slot_id}", response_model=MessageResponse)
async def delete_slot(
    slot_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
    __: User = Depends(require_grade_permission("dispatch.manage_slots")),
):
    slot = await db.get(DispatchSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot introuvable")
    if slot.kind in FIXED_SLOT_KINDS:
        raise HTTPException(status_code=400, detail="Case fixe — non supprimable")
    await db.delete(slot)
    await db.commit()
    await push_snapshot(db)
    return MessageResponse(message="Supprimé")


async def _renumber_slot_orders(db: AsyncSession, slot_id: int) -> None:
    """Renumérote séquentiellement (0, 1, 2…) les orders des affectations d'un slot.

    Triées par created_at (ordre d'arrivée réel), pas par l'ancien order,
    pour que le nouvel arrivant garde toujours la dernière place.
    """
    result = await db.execute(
        select(DispatchAssignment)
        .where(DispatchAssignment.slot_id == slot_id)
        .order_by(DispatchAssignment.created_at.asc(), DispatchAssignment.id.asc())
    )
    for index, assignment in enumerate(result.scalars().all()):
        assignment.order = index


@router.post("/api/dispatch/slots/{slot_id}/assign", response_model=SlotOut)
async def assign_user(
    slot_id: int,
    payload: AssignRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
    __: User = Depends(require_grade_permission("dispatch.manage_assignments")),
):
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
    if assignment is None:
        assignment = DispatchAssignment(employee_id=employee.id, order=0)
        assignment.slot_id = slot.id
        db.add(assignment)
        await db.flush()  # created_at renseigné avant le commit
    elif assignment.slot_id != slot.id:
        assignment.slot_id = slot.id
        assignment.order = 0
        assignment.created_at = utcnow()  # redevient le dernier arrivé

    await db.commit()
    # Renumérotation propre : 0, 1, 2… par ordre d'arrivée (created_at)
    await _renumber_slot_orders(db, slot_id)
    await db.commit()
    await db.refresh(slot)
    await push_snapshot(db)
    # Synchronisation employé vers Google Sheets (nom/téléphone, indépendante du statut hôpital)
    asyncio.create_task(_sync_employee_to_google_sheets())
    # Re-fetch with assignments
    result = await db.execute(
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .where(DispatchSlot.id == slot_id)
    )
    slot = result.scalar_one()
    return SlotOut.model_validate(slot)


@router.delete("/api/dispatch/slots/{slot_id}/assign/{employee_id}", response_model=SlotOut)
async def unassign_user(
    slot_id: int,
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
    __: User = Depends(require_grade_permission("dispatch.manage_assignments")),
):
    slot = await db.get(DispatchSlot, slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Slot introuvable")
    result = await db.execute(
        select(DispatchAssignment)
        .where(
            DispatchAssignment.slot_id == slot_id,
            DispatchAssignment.employee_id == employee_id,
        )
    )
    a = result.scalar_one_or_none()
    if a:
        await db.delete(a)
        # L'employé passe « Hors service BCES » : sa radio s'éteint automatiquement.
        radio = await db.scalar(
            select(DispatchRadio).where(DispatchRadio.employee_id == employee_id).limit(1)
        )
        if radio is not None and (radio.is_on or radio.is_loading):
            radio.is_on = False
            radio.is_loading = False
        await db.commit()

        # Renuméroter les affectations restantes pour fermer les trous
        # (ex: retirer le 01 fait passer le 02 en 01)
        await _renumber_slot_orders(db, slot_id)
        await db.commit()
    result = await db.execute(
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .where(DispatchSlot.id == slot_id)
    )
    slot = result.scalar_one()
    await push_snapshot(db)
    # Synchronisation employé vers Google Sheets (nom/téléphone, indépendante du statut hôpital)
    asyncio.create_task(_sync_employee_to_google_sheets())
    return SlotOut.model_validate(slot)


@router.patch("/api/dispatch/radios/{radio_id}", response_model=RadioOut)
async def update_radio(
    radio_id: int,
    payload: RadioUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
    __: User = Depends(require_grade_permission("dispatch.manage_radios")),
):
    radio = await db.get(DispatchRadio, radio_id)
    if not radio:
        raise HTTPException(status_code=404, detail="Radio introuvable")
    data = payload.model_dump(exclude_unset=True)
    if data.get("employee_id") is not None:
        employee = await db.get(Employee, data["employee_id"])
        if employee is None or not employee.is_active:
            raise HTTPException(status_code=404, detail="Employé actif introuvable.")
        # Une seule radio par employé.
        other_radio = await db.scalar(
            select(DispatchRadio.serial).where(
                DispatchRadio.employee_id == employee.id,
                DispatchRadio.id != radio.id,
            ).limit(1)
        )
        if other_radio is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Cet employé a déjà une radio ({mask_serial(other_radio) or 'sans numéro'}).",
            )
    if "employee_id" in data:
        radio.doctor_id = None

    # Une radio sans affectation ne peut pas être allumée : on refuse une
    # demande explicite et on éteint la radio quand on retire son affectation.
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
    # Trois états exclusifs : passer ON retire « Indisponible », et inversement.
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


@router.patch("/api/dispatch/state", response_model=StateOut)
async def update_state(
    payload: StateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
    __: User = Depends(require_grade_permission("dispatch.manage_state")),
):
    state = await db.get(DispatchState, 1)
    if not state:
        state = DispatchState(id=1)
        db.add(state)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(state, k, v)
    await db.commit()
    await db.refresh(state)
    # Synchronisation asynchrone vers Google Sheets (ne bloque pas l'API)
    asyncio.create_task(_sync_state_to_google_sheets(state))
    await push_snapshot(db)
    return StateOut.model_validate(state)
