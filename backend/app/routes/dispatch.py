"""Routes Dispatch (couche transport mince)."""

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import decode_token, get_session_cookie_name
from app.controllers import dispatch as cd
from app.database import SessionLocal
from app.deps import get_current_user, get_db, require_page_access, user_has_page_access
from app.models import User
from app.schemas import (
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
)
from app.services.grade_permissions import require_grade_permission

router = APIRouter(tags=["dispatch"])


# --- WebSocket ---


@router.websocket("/ws/dispatch")
async def dispatch_ws(
    ws: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    # 1. Essayer le token passé en paramètre de requête (cross-origin fiable)
    raw_cookie = None
    if token:
        raw_cookie = token
    else:
        # 2. Fallback : cookie de session (même origine uniquement)
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
        if (
            not user
            or (user.status or "active") != "active"
            or not user_has_page_access(user, "dispatch")
        ):
            await ws.close(code=1008, reason="Compte non autorisé")
            return

    await cd.manager.connect(ws)
    try:
        async with cd.snapshot_lock:
            async with SessionLocal() as db:
                snap = await cd.build_snapshot(db)
            await ws.send_json({"type": "snapshot", "data": snap})
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pylint: disable=broad-except
        cd.logger.warning("WS error: %s", exc)
    finally:
        await cd.manager.disconnect(ws)


# --- REST ---


@router.get("/api/dispatch/snapshot", response_model=DispatchSnapshot)
async def get_snapshot(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
) -> DispatchSnapshot:
    return await cd.get_snapshot(db)


@router.put("/api/dispatch/note", response_model=DispatchSnapshot)
async def update_dispatch_note(
    payload: DispatchNoteUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
) -> DispatchSnapshot:
    return await cd.update_dispatch_note(payload, db)


@router.post("/api/dispatch/assignments/reset", response_model=DispatchSnapshot)
async def reset_assignments(
    payload: DispatchResetRequest,
    current_user: User = Depends(require_page_access("dispatch")),
    db: AsyncSession = Depends(get_db),
) -> DispatchSnapshot:
    return await cd.reset_assignments(payload, current_user, db)


@router.post(
    "/api/dispatch/slots",
    response_model=SlotOut,
    status_code=201,
    dependencies=[Depends(require_grade_permission("dispatch.manage_slots"))],
)
async def create_slot(
    payload: SlotCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
) -> SlotOut:
    return await cd.create_slot(payload, db)


@router.patch(
    "/api/dispatch/slots/{slot_id}",
    response_model=SlotOut,
    dependencies=[Depends(require_grade_permission("dispatch.manage_slots"))],
)
async def update_slot(
    slot_id: int,
    payload: SlotUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
) -> SlotOut:
    return await cd.update_slot(slot_id, payload, db)


@router.delete(
    "/api/dispatch/slots/{slot_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_grade_permission("dispatch.manage_slots"))],
)
async def delete_slot(
    slot_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
) -> MessageResponse:
    return await cd.delete_slot(slot_id, db)


@router.post(
    "/api/dispatch/slots/{slot_id}/assign",
    response_model=SlotOut,
    dependencies=[Depends(require_grade_permission("dispatch.manage_assignments"))],
)
async def assign_user(
    slot_id: int,
    payload: AssignRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
) -> SlotOut:
    return await cd.assign_user(slot_id, payload, db)


@router.delete(
    "/api/dispatch/slots/{slot_id}/assign/{employee_id}",
    response_model=SlotOut,
    dependencies=[Depends(require_grade_permission("dispatch.manage_assignments"))],
)
async def unassign_user(
    slot_id: int,
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
) -> SlotOut:
    return await cd.unassign_user(slot_id, employee_id, db)


@router.patch(
    "/api/dispatch/radios/{radio_id}",
    response_model=RadioOut,
    dependencies=[Depends(require_grade_permission("dispatch.manage_radios"))],
)
async def update_radio(
    radio_id: int,
    payload: RadioUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
) -> RadioOut:
    return await cd.update_radio(radio_id, payload, db)


@router.patch(
    "/api/dispatch/state",
    response_model=StateOut,
    dependencies=[Depends(require_grade_permission("dispatch.manage_state"))],
)
async def update_state(
    payload: StateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_page_access("dispatch")),
) -> StateOut:
    return await cd.update_state(payload, db)
