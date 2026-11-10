import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.session import decode_token, get_session_cookie_name
from config import get_settings
from database import SessionLocal, get_db
from deps import require_page_access, user_has_page_access
from grade_permissions import require_grade_permission, user_has_grade_permission
from models import (
    DispatchAssignment,
    Employee,
    DispatchRadio,
    DispatchSlot,
    DispatchState,
    DispatchNote,
    User,
)
from schemas import (
    AssignRequest,
    DispatchNoteUpdateRequest,
    DispatchResetRequest,
    DispatchSnapshot,
    MessageResponse,
    RadioOut,
    RadioUpdateRequest,
    SlotCreateRequest,
    SlotOut,
    SlotUpdateRequest,
    StateOut,
    StateUpdateRequest,
    mask_serial,
)

logger = logging.getLogger("bces.dispatch")

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

    return {
        "slots": [SlotOut.model_validate(s).model_dump(mode="json") for s in slots],
        "radios": [dispatch_radio_out(r).model_dump(mode="json") for r in radios],
        "state": StateOut.model_validate(state).model_dump(mode="json"),
        "note": note.content if note else "",
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
    # Plus personne n'est en service : les radios ON ou en sablier passent OFF.
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
        assignment = DispatchAssignment(
            employee_id=employee.id,
            order=len(slot.assignments),
        )
        slot.assignments.append(assignment)
    elif assignment.slot_id != slot.id:
        assignment.order = len(slot.assignments)
        slot.assignments.append(assignment)

    await db.commit()
    await db.refresh(slot)
    await push_snapshot(db)
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
        await db.commit()
    result = await db.execute(
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .where(DispatchSlot.id == slot_id)
    )
    slot = result.scalar_one()
    await push_snapshot(db)
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
        if radio.is_direction and not (employee.grade and employee.grade.is_direction):
            raise HTTPException(
                status_code=409,
                detail="Une radio Direction ne s’affecte qu’à un membre de la Direction.",
            )
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
                detail=f"Cet employé a déjà une radio ({other_radio or 'sans numéro'}).",
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
            status_code=422, detail="Une radio ne peut pas être à la fois ON et en sablier."
        )
    # Trois états exclusifs : passer ON retire le sablier, et inversement.
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
    await push_snapshot(db)
    return StateOut.model_validate(state)
