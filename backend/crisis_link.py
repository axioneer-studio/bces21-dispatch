"""Lien entre la Crise et son intervention « Primo » du Dispatch.

La crise a au plus une intervention « Primo » (`CrisisState.slot_id`) :
- désigner un Primo dans la Crise l'affecte à cette intervention (créée au besoin) ;
- passer une intervention au statut « Primo » sur le Dispatch en fait celle de la
  crise, si la crise n'en a pas encore ;
- l'équipe de crise suit les membres de cette intervention : le premier arrivé
  est Primo, les suivants en assistance ; qui quitte l'intervention quitte
  l'équipe, et si c'était le Primo, le suivant prend sa place.
Le code postal est celui de l'intervention : il se modifie d'un côté ou de l'autre.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    CrisisMember,
    CrisisState,
    DispatchAssignment,
    DispatchSlot,
    InterventionStatus,
    intervention_status_order,
)


async def primo_status_keys(db: AsyncSession) -> list[str]:
    """Clés des statuts cochés « Primo Inter » dans Administration, dans l'ordre de la liste."""
    return list(
        (
            await db.execute(
                select(InterventionStatus.key)
                .where(InterventionStatus.is_primo.is_(True))
                .order_by(*intervention_status_order())
            )
        ).scalars()
    )


async def crisis_state(db: AsyncSession) -> CrisisState:
    state = await db.get(CrisisState, 1)
    if state is None:
        state = CrisisState(id=1)
        db.add(state)
    return state


async def primo_slot(db: AsyncSession, state: CrisisState | None) -> DispatchSlot | None:
    """Intervention « Primo » de la crise, si elle existe encore sur le Dispatch."""
    if state is None or state.slot_id is None:
        return None
    return await db.get(DispatchSlot, state.slot_id)


async def _slot_employee_ids(db: AsyncSession, slot_id: int) -> list[int]:
    """Personnes de l'intervention, dans leur ordre d'arrivée."""
    return list(
        (
            await db.execute(
                select(DispatchAssignment.employee_id)
                .where(DispatchAssignment.slot_id == slot_id)
                .order_by(DispatchAssignment.created_at, DispatchAssignment.id)
            )
        ).scalars()
    )


async def _add_member(db: AsyncSession, employee_id: int) -> None:
    """Ajoute à l'équipe : Primo s'il n'y en a pas, sinon agent en assistance."""
    await db.flush()
    if await db.get(CrisisMember, employee_id) is not None:
        return
    has_primo = await db.scalar(select(CrisisMember.employee_id).where(CrisisMember.is_primo.is_(True)))
    db.add(CrisisMember(employee_id=employee_id, is_primo=has_primo is None))


async def linked_slot_id(db: AsyncSession) -> int | None:
    slot = await primo_slot(db, await db.get(CrisisState, 1))
    return slot.id if slot else None


async def sync_crisis_from_slot(db: AsyncSession, slot: DispatchSlot, joined_id: int | None = None) -> None:
    """À appeler quand une intervention change de statut ou reçoit quelqu'un (`joined_id`).

    Une intervention « Primo » devient celle de la crise si la crise n'en a pas
    (son code postal devient celui de la crise) : ses membres rejoignent alors
    l'équipe, le premier arrivé comme Primo s'il n'y en a pas. Ensuite, chaque
    nouvelle personne affectée rejoint l'équipe, comme Primo s'il n'y en a pas,
    sinon en assistance.
    """
    state = await crisis_state(db)
    linked = await primo_slot(db, state)
    newly_linked = linked is None and slot.status is not None and slot.status in await primo_status_keys(db)
    if newly_linked:
        state.slot_id = slot.id
        if slot.zip_code:
            state.zip_code = slot.zip_code
        linked = slot
    if linked is None or linked.id != slot.id:
        return
    await db.flush()
    if newly_linked:
        for employee_id in await _slot_employee_ids(db, slot.id):
            await _add_member(db, employee_id)
    elif joined_id is not None:
        await _add_member(db, joined_id)


async def employee_left_slot(db: AsyncSession, slot_id: int | None, employee_id: int) -> None:
    """À appeler quand quelqu'un quitte une intervention (retiré ou déplacé).

    S'il quitte l'intervention « Primo » de la crise, il quitte aussi l'équipe ;
    si c'était le Primo, la personne suivante de l'intervention (par ordre
    d'arrivée) devient Primo.
    """
    if slot_id is None or slot_id != await linked_slot_id(db):
        return
    member = await db.get(CrisisMember, employee_id)
    if member is None:
        return
    was_primo = member.is_primo
    await db.delete(member)
    await db.flush()
    if not was_primo:
        return
    remaining = [other for other in await _slot_employee_ids(db, slot_id) if other != employee_id]
    if not remaining:
        return
    successor = await db.get(CrisisMember, remaining[0])
    if successor is None:
        db.add(CrisisMember(employee_id=remaining[0], is_primo=True))
    else:
        successor.is_primo = True


async def slot_emptied(db: AsyncSession, slot_id: int) -> None:
    """À appeler avant de vider ou de supprimer une intervention : si c'est celle de
    la crise, ses membres quittent l'équipe."""
    if slot_id != await linked_slot_id(db):
        return
    employee_ids = await _slot_employee_ids(db, slot_id)
    if employee_ids:
        await db.execute(delete(CrisisMember).where(CrisisMember.employee_id.in_(employee_ids)))
