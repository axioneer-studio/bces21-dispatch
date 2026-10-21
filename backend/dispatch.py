import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.session import decode_token, get_session_cookie_name
from config import get_settings
from database import SessionLocal, get_db
from deps import get_current_user
from models import (
    DispatchAssignment,
    DispatchRadio,
    DispatchSlot,
    DispatchState,
    User,
)
from schemas import (
    AssignRequest,
    DispatchSnapshot,
    MessageResponse,
    RadioOut,
    RadioUpdateRequest,
    SlotCreateRequest,
    SlotOut,
    SlotUpdateRequest,
    StateOut,
    StateUpdateRequest,
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


async def build_snapshot(db: AsyncSession) -> dict[str, Any]:
    slots_q = (
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .order_by(DispatchSlot.order.asc(), DispatchSlot.id.asc())
    )
    slots = (await db.execute(slots_q)).scalars().all()

    radios_q = (
        select(DispatchRadio)
        .order_by(DispatchRadio.is_direction.asc(), DispatchRadio.order.asc(), DispatchRadio.id.asc())
    )
    radios = (await db.execute(radios_q)).scalars().all()

    state = await db.get(DispatchState, 1)
    if not state:
        state = DispatchState(id=1)
        db.add(state)
        await db.commit()

    return {
        "slots": [SlotOut.model_validate(s).model_dump(mode="json") for s in slots],
        "radios": [RadioOut.model_validate(r).model_dump(mode="json") for r in radios],
        "state": StateOut.model_validate(state).model_dump(mode="json"),
    }


async def push_snapshot(db: AsyncSession) -> None:
    snap = await build_snapshot(db)
    await manager.broadcast({"type": "snapshot", "data": snap})


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
        if not user or (user.status or "active") == "pending":
            await ws.close(code=1008, reason="Compte non autorisé")
            return

    await manager.connect(ws)
    try:
        # Snapshot initial
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
    _: User = Depends(get_current_user),
):
    return await build_snapshot(db)


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
    _: User = Depends(get_current_user),
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
    _: User = Depends(get_current_user),
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
    _: User = Depends(get_current_user),
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
    _: User = Depends(get_current_user),
):
    slot_q = await db.execute(
        select(DispatchSlot)
        .options(selectinload(DispatchSlot.assignments))
        .where(DispatchSlot.id == slot_id)
    )
    slot = slot_q.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Slot introuvable")

    user = await db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    # A user can only occupy one dispatch slot at a time.
    result = await db.execute(
        select(DispatchAssignment).where(DispatchAssignment.user_id == user.id)
    )
    for assignment in result.scalars().all():
        if assignment.slot_id == slot.id:
            slot.assignments.remove(assignment)
        await db.delete(assignment)

    assignment = DispatchAssignment(
        slot_id=slot_id,
        user_id=user.id,
        order=len(slot.assignments),
    )
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


@router.delete("/api/dispatch/slots/{slot_id}/assign/{user_id}", response_model=SlotOut)
async def unassign_user(
    slot_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DispatchAssignment)
        .where(
            DispatchAssignment.slot_id == slot_id,
            DispatchAssignment.user_id == user_id,
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
    _: User = Depends(get_current_user),
):
    radio = await db.get(DispatchRadio, radio_id)
    if not radio:
        raise HTTPException(status_code=404, detail="Radio introuvable")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(radio, k, v)
    await db.commit()
    await db.refresh(radio)
    await push_snapshot(db)
    return RadioOut.model_validate(radio)


@router.patch("/api/dispatch/state", response_model=StateOut)
async def update_state(
    payload: StateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
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