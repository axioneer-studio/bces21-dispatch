"""Gestion de crise : équipe sur place et liste des blessés.

La page est ouverte à tout compte validé. En pratique, la Centrale du Dispatch
désigne le Primo Intervenant et les agents qui l'assistent, coche l'ajout au canal
et le lit d'arrivée ; l'équipe renseigne les blessés. La « Tempête » vide tout.

Choisir un lit installe le blessé dans ce lit de l'onglet Chambres, avec la raison
« En attente d'opération » ; seuls les lits libres sont proposés. Une fois le blessé soigné (ou
retiré de la liste), il quitte le lit, qui redevient libre.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from affiliation_groups import group_names
from config import get_settings
from database import get_db
from deps import get_current_user, require_page_access
from hospital_access import linked_employee
from hospital_rooms import clear_patient
from models import CrisisMember, CrisisVictim, Employee, HospitalBed, HospitalBedReason, HospitalRoom, User, utcnow
from schemas import (
    CrisisBedOut,
    CrisisEmployeeOut,
    CrisisOut,
    CrisisTeamRequest,
    CrisisVictimCreate,
    CrisisVictimOut,
    CrisisVictimUpdate,
    MessageResponse,
)

router = APIRouter(prefix="/api/crisis", tags=["crisis"], dependencies=[Depends(require_page_access("crisis"))])


def _employee_out(employee: Employee) -> CrisisEmployeeOut:
    return CrisisEmployeeOut(id=employee.id, name=f"{employee.first_name} {employee.last_name}".strip())


async def _user_display_name(db: AsyncSession, user: User) -> str:
    """Nom de la tuile employé liée au compte, sinon son nom RP, sinon son pseudo Discord."""
    employee = await linked_employee(db, user)
    if employee:
        return _employee_out(employee).name
    rp_name = f"{user.prenom_rp or ''} {user.nom_rp or ''}".strip()
    return (rp_name or user.discord_username)[:120]


SURGERY_REASON = "En attente d’opération"


def _bed_patient_name(victim: CrisisVictim) -> str:
    return victim.full_name or "Blessé de la crise"


async def _release_bed(db: AsyncSession, victim: CrisisVictim) -> None:
    """Retire le blessé de son lit dans l'onglet Chambres : le lit redevient libre."""
    if victim.bed_id is None:
        return
    bed = await db.get(HospitalBed, victim.bed_id)
    if bed is not None:
        clear_patient(bed)
    victim.bed_id = None


async def _install_in_bed(db: AsyncSession, victim: CrisisVictim, bed_id: int) -> None:
    """Installe le blessé dans un lit libre de l'onglet Chambres, avec la raison
    « En attente d'opération », ajoutée à la liste des raisons si elle n'y est pas."""
    bed = await db.get(HospitalBed, bed_id)
    if bed is None:
        raise HTTPException(status_code=404, detail="Lit introuvable.")
    if bed.patient_name:
        raise HTTPException(status_code=409, detail="Ce lit est déjà occupé.")
    reason = await db.scalar(
        select(HospitalBedReason)
        .where(func.lower(HospitalBedReason.name).in_({SURGERY_REASON.lower(), SURGERY_REASON.lower().replace("’", "'")}))
        .limit(1)
    )
    if reason is None:
        reason = HospitalBedReason(name=SURGERY_REASON)
        db.add(reason)
    clear_patient(bed)
    bed.patient_name = _bed_patient_name(victim)
    bed.accident = (f"Crise : {victim.injuries}" if victim.injuries else "Crise")[:200]
    bed.arrival_date = datetime.now(ZoneInfo(get_settings().app_timezone)).date()
    bed.reason = reason.name
    victim.bed_id = bed.id


async def _get_victim(db: AsyncSession, victim_id: int) -> CrisisVictim:
    victim = await db.get(CrisisVictim, victim_id)
    if not victim:
        raise HTTPException(status_code=404, detail="Blessé introuvable.")
    return victim


@router.get("", response_model=CrisisOut)
async def get_crisis(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    members = (
        await db.execute(select(CrisisMember).order_by(CrisisMember.created_at))
    ).scalars().all()
    primo = next((member.employee for member in members if member.is_primo), None)
    victims = (
        await db.execute(select(CrisisVictim).order_by(CrisisVictim.created_at, CrisisVictim.id))
    ).scalars().all()
    employees = (
        await db.execute(
            select(Employee)
            .where(Employee.is_active.is_(True))
            .order_by(Employee.first_name, Employee.last_name)
        )
    ).scalars().all()
    beds = (
        await db.execute(
            select(HospitalBed, HospitalRoom.name)
            .join(HospitalRoom, HospitalRoom.id == HospitalBed.room_id)
            .order_by(HospitalRoom.order, HospitalRoom.id, HospitalBed.id)
        )
    ).all()
    return CrisisOut(
        primo=_employee_out(primo) if primo else None,
        helpers=[_employee_out(member.employee) for member in members if not member.is_primo],
        victims=[CrisisVictimOut.model_validate(victim) for victim in victims],
        employees=[_employee_out(employee) for employee in employees],
        beds=[
            CrisisBedOut(id=bed.id, label=f"{room_name} · {bed.label}", patient_name=bed.patient_name)
            for bed, room_name in beds
        ],
        groups=await group_names(db),
    )


@router.put("/team", response_model=MessageResponse)
async def set_team(
    payload: CrisisTeamRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remplace l'équipe. Le Primo n'est pas compté parmi les agents qui l'assistent."""
    helper_ids = [
        employee_id for employee_id in dict.fromkeys(payload.helper_ids) if employee_id != payload.primo_id
    ]
    wanted = helper_ids + ([payload.primo_id] if payload.primo_id is not None else [])
    if wanted:
        found = set(
            (
                await db.execute(
                    select(Employee.id).where(Employee.id.in_(wanted), Employee.is_active.is_(True))
                )
            ).scalars()
        )
        if found != set(wanted):
            raise HTTPException(status_code=404, detail="Employé introuvable ou inactif.")
    await db.execute(delete(CrisisMember))
    if payload.primo_id is not None:
        db.add(CrisisMember(employee_id=payload.primo_id, is_primo=True))
    for employee_id in helper_ids:
        db.add(CrisisMember(employee_id=employee_id, is_primo=False))
    await db.commit()
    return {"message": "Équipe de crise mise à jour."}


@router.post("/victims", response_model=CrisisVictimOut, status_code=status.HTTP_201_CREATED)
async def create_victim(
    payload: CrisisVictimCreate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    victim = CrisisVictim(**payload.model_dump())
    db.add(victim)
    await db.commit()
    await db.refresh(victim)
    return CrisisVictimOut.model_validate(victim)


@router.patch("/victims/{victim_id}", response_model=CrisisVictimOut)
async def update_victim(
    victim_id: int,
    payload: CrisisVictimUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Celui qui coche « Arrivé » devient le médecin qui rapatrie, et celui qui coche
    « Soigné » le médecin soignant, si ces champs sont vides. « Canal » ne se coche
    qu'une fois le blessé soigné ; décocher « Soigné » décoche donc aussi « Canal »."""
    victim = await _get_victim(db, victim_id)
    data = payload.model_dump(exclude_unset=True)
    bed_requested = "bed_id" in data
    next_bed_id = data.pop("bed_id", None)

    arrived = data.pop("arrived", None)
    newly_arrived = arrived is True and victim.arrived_at is None
    newly_cared = data.get("care_done") is True and not victim.care_done
    for key, value in data.items():
        setattr(victim, key, value)
    if arrived is False:
        victim.arrived_at = None
    elif newly_arrived:
        victim.arrived_at = utcnow()
    if not victim.care_done:
        if data.get("channel_added"):
            raise HTTPException(status_code=409, detail="Cochez « Soigné » avant « Canal ».")
        victim.channel_added = False

    if (newly_arrived and not victim.repatriating_doctor) or (newly_cared and not victim.treating_doctor):
        name = await _user_display_name(db, user)
        if newly_arrived and not victim.repatriating_doctor:
            victim.repatriating_doctor = name
        if newly_cared and not victim.treating_doctor:
            victim.treating_doctor = name

    if bed_requested and next_bed_id != victim.bed_id:
        if next_bed_id is not None and victim.care_done:
            raise HTTPException(status_code=409, detail="Ce blessé est déjà soigné : il n’a plus besoin de lit.")
        await _release_bed(db, victim)
        if next_bed_id is not None:
            await _install_in_bed(db, victim, next_bed_id)
    elif victim.care_done:
        await _release_bed(db, victim)
    elif "full_name" in data and victim.bed_id is not None:
        bed = await db.get(HospitalBed, victim.bed_id)
        if bed is not None:
            bed.patient_name = _bed_patient_name(victim)
    await db.commit()
    await db.refresh(victim)
    return CrisisVictimOut.model_validate(victim)


@router.delete("/victims/{victim_id}", response_model=MessageResponse)
async def delete_victim(
    victim_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    victim = await _get_victim(db, victim_id)
    await _release_bed(db, victim)
    await db.delete(victim)
    await db.commit()
    return {"message": "Blessé retiré de la liste."}


@router.post("/reset", response_model=MessageResponse)
async def reset_crisis(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tempête : vide la liste des blessés et l'équipe de crise, et libère les lits
    où des blessés de la crise étaient installés."""
    for victim in (await db.execute(select(CrisisVictim).where(CrisisVictim.bed_id.is_not(None)))).scalars():
        await _release_bed(db, victim)
    await db.execute(delete(CrisisVictim))
    await db.execute(delete(CrisisMember))
    await db.commit()
    return {"message": "Crise réinitialisée."}
