"""Contrôleur de la morgue : logique métier des défunts (cellule, autopsie, cercueil).

L'autopsie et le légiste ne se renseignent que par un médecin légiste (formation
qui donne le droit « Médecin légiste », voir training_rights) ou par la
Direction (grade `is_direction`) ; le légiste qui déclare l'autopsie devient le
légiste du défunt. Seuls les légistes incinèrent un corps ou le mettent en
cercueil, une fois l'autopsie faite.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import affiliation_groups as cg_affiliation
from app.models import Employee, MorgueEntry, User, utcnow
from app.schemas import (
    MessageResponse,
    MorgueAutopsyRequest,
    MorgueEntryCreate,
    MorgueEntryOut,
    MorgueEntryUpdate,
    MorgueExaminerOut,
    MorgueExaminerRequest,
    MorgueOut,
)
from app.services.hospital_access import is_direction, linked_employee
from app.services.training_rights import (
    FORENSIC_PERMISSION,
    employees_with_training_permission,
    user_has_training_permission,
)


def _employee_name(employee: Employee) -> str:
    return f"{employee.first_name} {employee.last_name}".strip()


def _entry_out(entry: MorgueEntry) -> MorgueEntryOut:
    return MorgueEntryOut.model_validate(entry).model_copy(
        update={"examiner_name": _employee_name(entry.examiner) if entry.examiner else None}
    )


async def _can_manage_autopsy(db: AsyncSession, user: User) -> bool:
    if await user_has_training_permission(db, user, FORENSIC_PERMISSION):
        return True
    return is_direction(await linked_employee(db, user))


async def _require_autopsy_rights(db: AsyncSession, user: User) -> tuple[bool, Employee | None]:
    """Vérifie que le compte est légiste ou Direction ; renvoie s'il est légiste et sa tuile."""
    is_forensic = await user_has_training_permission(db, user, FORENSIC_PERMISSION)
    employee = await linked_employee(db, user)
    if not is_forensic and not is_direction(employee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les médecins légistes et la Direction peuvent renseigner l’autopsie et le légiste.",
        )
    return is_forensic, employee


async def _examiners(db: AsyncSession) -> list[Employee]:
    """Employés actifs, liés à un compte, qui ont validé une formation de médecin légiste."""
    return [
        employee
        for employee in await employees_with_training_permission(db, FORENSIC_PERMISSION)
        if employee.account_user_id is not None
    ]


async def _get_entry(db: AsyncSession, entry_id: int) -> MorgueEntry:
    entry = await db.get(MorgueEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Défunt introuvable.")
    return entry


def _ensure_in_cell(entry: MorgueEntry) -> None:
    """Refuse toute action réservée à un corps encore en cellule réfrigérée."""
    if entry.incinerated_at is not None:
        raise HTTPException(status_code=409, detail="Ce défunt a déjà été incinéré.")
    if entry.coffined_at is not None:
        raise HTTPException(status_code=409, detail="Ce défunt a déjà été mis en cercueil.")


def _ensure_autopsy_done(entry: MorgueEntry) -> None:
    if not entry.autopsy_done:
        raise HTTPException(status_code=409, detail="L’autopsie doit être faite avant.")


# --- Handlers appelés par les routes ---


async def get_morgue(user: User, db: AsyncSession) -> MorgueOut:
    entries = (
        await db.execute(select(MorgueEntry).order_by(MorgueEntry.death_date, MorgueEntry.id))
    ).scalars().all()
    can_manage_autopsy = await _can_manage_autopsy(db, user)
    return MorgueOut(
        entries=[_entry_out(entry) for entry in entries],
        examiners=[
            MorgueExaminerOut(id=employee.id, name=_employee_name(employee))
            for employee in (await _examiners(db) if can_manage_autopsy else [])
        ],
        can_manage_autopsy=can_manage_autopsy,
        is_forensic=await user_has_training_permission(db, user, FORENSIC_PERMISSION),
        groups=await cg_affiliation.group_choices(db),
    )


async def create_entry(payload: MorgueEntryCreate, db: AsyncSession) -> MorgueEntryOut:
    entry = MorgueEntry(**payload.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return _entry_out(entry)


async def update_entry(
    entry_id: int, payload: MorgueEntryUpdate, db: AsyncSession
) -> MorgueEntryOut:
    entry = await _get_entry(db, entry_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    await db.commit()
    await db.refresh(entry)
    return _entry_out(entry)


async def set_autopsy(
    entry_id: int,
    payload: MorgueAutopsyRequest,
    user: User,
    db: AsyncSession,
) -> MorgueEntryOut:
    """Déclare l'autopsie faite ou non. Le légiste qui la déclare devient le légiste
    du défunt ; la Direction peut la déclarer sans en devenir le légiste."""
    is_forensic, employee = await _require_autopsy_rights(db, user)
    entry = await _get_entry(db, entry_id)
    _ensure_in_cell(entry)
    entry.autopsy_done = payload.done
    if not payload.done:
        entry.examiner_id = None
    elif is_forensic and employee is not None:
        entry.examiner_id = employee.id
    await db.commit()
    await db.refresh(entry)
    return _entry_out(entry)


async def set_examiner(
    entry_id: int,
    payload: MorgueExaminerRequest,
    user: User,
    db: AsyncSession,
) -> MorgueEntryOut:
    """Change le légiste du défunt, parmi les employés au rôle de légiste."""
    await _require_autopsy_rights(db, user)
    entry = await _get_entry(db, entry_id)
    _ensure_in_cell(entry)
    if payload.examiner_id is not None and payload.examiner_id != entry.examiner_id:
        if payload.examiner_id not in {employee.id for employee in await _examiners(db)}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Le médecin choisi n’a pas le rôle de légiste.",
            )
    entry.examiner_id = payload.examiner_id
    await db.commit()
    await db.refresh(entry)
    return _entry_out(entry)


async def incinerate_entry(entry_id: int, db: AsyncSession) -> MorgueEntryOut:
    entry = await _get_entry(db, entry_id)
    _ensure_in_cell(entry)
    _ensure_autopsy_done(entry)
    entry.incinerated_at = utcnow()
    await db.commit()
    await db.refresh(entry)
    return _entry_out(entry)


async def coffin_entry(entry_id: int, db: AsyncSession) -> MorgueEntryOut:
    entry = await _get_entry(db, entry_id)
    _ensure_in_cell(entry)
    _ensure_autopsy_done(entry)
    entry.coffined_at = utcnow()
    await db.commit()
    await db.refresh(entry)
    return _entry_out(entry)


async def delete_entry(entry_id: int, db: AsyncSession) -> MessageResponse:
    entry = await _get_entry(db, entry_id)
    await db.delete(entry)
    await db.commit()
    return {"message": "Défunt retiré de la morgue."}
