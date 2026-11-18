"""Page Formation : formations du service et leur validation par employé.

Valider une formation pour un employé ajoute l'emoji de la formation à ses
compétences (la ligne « Compétences » des Ressources humaines) ; l'emoji est la
seule trace de la validation, si bien qu'un emoji ajouté à la main dans les
Ressources humaines compte aussi comme une validation.

Trois types de formation :
- « trial » : période d'essai (CDD, Interne), pour passer Résident ; suivie pour
  les employés des grades « Période d'essai » (formation initiale) ;
- « training » : période de formation (CDI, Résident), pour passer Médecin ;
  suivie pour les employés des grades « En formation » (formation complémentaire) ;
- « general » : formation générale (ex. Pilote Medicopter).

Une formation générale peut donner des droits (Formateur, Médecin légiste) à ceux
qui l'ont validée : voir training_rights.

La page est ouverte à tout compte validé. Créer, modifier et supprimer une
formation est réservé à ceux qui gèrent l'hôpital (rôle « Gérer l'hôpital » ou
grade de la Direction). Seuls les formateurs valident les formations de période
d'essai et de période de formation. L'équipe d'une formation générale se gère
par la Direction et par son Responsable ; seule la Direction nomme ou retire un
Responsable. Les super-admins ont tous les droits.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from deps import get_current_user, require_page_access
from dispatch import push_employees_changed
from hospital_access import is_direction, linked_employee, require_hospital_manage, user_can_manage_hospital
from models import Employee, Grade, Training, TrainingMember, User
from schemas import (
    MessageResponse,
    TrainingEmployeeOut,
    TrainingGradeOut,
    TrainingMemberOut,
    TrainingMemberRequest,
    TrainingOut,
    TrainingPageOut,
    TrainingPermissionOption,
    TrainingRequest,
)
from training_rights import (
    TRAINER_PERMISSION,
    TRAINING_PERMISSION_CATALOG,
    emoji_key as _emoji_key,
    employee_competencies as _competencies,
    parse_training_permissions,
    user_has_training_permission,
)

# Même limite que la fiche employé des Ressources humaines.
MAX_COMPETENCIES = 20
_KIND_ORDER = {"trial": 0, "training": 1, "general": 2}
# Formations que les formateurs valident.
_TRAINER_KINDS = {"trial", "training"}

router = APIRouter(
    prefix="/api/trainings",
    tags=["trainings"],
    dependencies=[Depends(require_page_access("training"))],
)


async def user_is_trainer(db: AsyncSession, user: User) -> bool:
    return await user_has_training_permission(db, user, TRAINER_PERMISSION)


async def _is_direction_user(db: AsyncSession, user: User) -> bool:
    return user.has_super_admin_rights or is_direction(await linked_employee(db, user))


async def _leads(db: AsyncSession, user: User, training: Training) -> bool:
    """Le compte est lié à l'employé Responsable de cette formation."""
    employee = await linked_employee(db, user)
    if employee is None:
        return False
    member = await db.get(TrainingMember, (training.id, employee.id))
    return member is not None and member.status == "lead"


async def _ensure_can_validate(
    db: AsyncSession,
    user: User,
    training: Training,
    employee_id: int,
    new_status: str | None,
) -> None:
    """Formations de période d'essai et de période de formation : seuls les
    formateurs (droit donné par une formation) les valident.

    Formations générales : la Direction et le Responsable de la formation gèrent
    l'équipe (Second, Validé, En cours) ; seule la Direction nomme ou retire un
    Responsable. `new_status` est le rôle donné, `None` pour un retrait.

    Les super-admins ont tous les droits."""
    if training.kind in _TRAINER_KINDS:
        if await user_is_trainer(db, user):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les formateurs peuvent valider cette formation.",
        )

    if await _is_direction_user(db, user):
        return
    if not await _leads(db, user, training):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls le Responsable de la formation et la Direction gèrent son équipe.",
        )
    current = await db.get(TrainingMember, (training.id, employee_id))
    if new_status == "lead" or (current is not None and current.status == "lead"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seule la Direction nomme ou retire le Responsable d’une formation.",
        )


def _granted_permissions(payload: TrainingRequest) -> list[str]:
    """Droits donnés par la formation : seule une formation générale en donne."""
    if payload.kind != "general":
        return []
    unknown = set(payload.permissions) - TRAINING_PERMISSION_CATALOG.keys()
    if unknown:
        raise HTTPException(status_code=422, detail=f"Droits inconnus : {', '.join(sorted(unknown))}.")
    return list(dict.fromkeys(payload.permissions))


def _training_out(training: Training) -> TrainingOut:
    return TrainingOut(
        id=training.id,
        name=training.name,
        emoji=training.emoji,
        kind=training.kind,
        permissions=parse_training_permissions(training.permissions),
    )


def _set_competencies(employee: Employee, competencies: list[str]) -> None:
    employee.competencies = json.dumps(list(dict.fromkeys(competencies)), ensure_ascii=False)


def _has_emoji(employee: Employee, emoji: str) -> bool:
    return any(_emoji_key(item) == _emoji_key(emoji) for item in _competencies(employee))


def _without_emoji(competencies: list[str], emoji: str) -> list[str]:
    return [item for item in competencies if _emoji_key(item) != _emoji_key(emoji)]


def _employee_out(employee: Employee) -> TrainingEmployeeOut:
    return TrainingEmployeeOut(
        id=employee.id,
        name=" ".join(filter(None, [employee.first_name, employee.last_name])),
        phone=employee.phone,
        grade_id=employee.grade_id,
        grade_name=employee.grade.name if employee.grade else None,
        grade_level=employee.grade.level if employee.grade else None,
        grade_color=employee.grade.color if employee.grade else None,
        competencies=_competencies(employee),
    )


def _grade_out(grade: Grade) -> TrainingGradeOut:
    return TrainingGradeOut(id=grade.id, name=grade.name, level=grade.level)


async def _get_training(db: AsyncSession, training_id: int) -> Training:
    training = await db.get(Training, training_id)
    if training is None:
        raise HTTPException(status_code=404, detail="Formation introuvable.")
    return training


async def _get_active_employee(db: AsyncSession, employee_id: int) -> Employee:
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employé introuvable.")
    if not employee.is_active:
        raise HTTPException(status_code=409, detail="Cet employé est désactivé.")
    return employee


async def _ensure_emoji_available(db: AsyncSession, emoji: str, training_id: int | None = None) -> None:
    trainings = (await db.execute(select(Training))).scalars().all()
    for training in trainings:
        if training.id != training_id and _emoji_key(training.emoji) == _emoji_key(emoji):
            raise HTTPException(
                status_code=409,
                detail=f"L’emoji {emoji} est déjà celui de la formation « {training.name} ».",
            )


async def _all_employees(db: AsyncSession) -> list[Employee]:
    return list((await db.execute(select(Employee))).scalars().all())


def _sorted_trainings(trainings: list[Training]) -> list[Training]:
    return sorted(trainings, key=lambda item: (_KIND_ORDER.get(item.kind, 3), item.name.lower(), item.id))


@router.get("", response_model=TrainingPageOut)
async def training_page(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trainings = (await db.execute(select(Training))).scalars().all()
    employees = (
        await db.execute(
            select(Employee)
            .outerjoin(Grade, Employee.grade_id == Grade.id)
            .where(Employee.is_active.is_(True))
            .order_by(Grade.level.is_(None), Grade.level.asc(), func.lower(Employee.first_name), Employee.id)
        )
    ).scalars().all()
    grades = (await db.execute(select(Grade).order_by(Grade.level.asc(), Grade.name.asc()))).scalars().all()
    members = (await db.execute(select(TrainingMember).order_by(TrainingMember.created_at))).scalars().all()
    can_manage = await user_can_manage_hospital(db, user)
    own_employee = await linked_employee(db, user)
    return TrainingPageOut(
        trainings=[_training_out(item) for item in _sorted_trainings(list(trainings))],
        employees=[_employee_out(employee) for employee in employees],
        members=[TrainingMemberOut.model_validate(member) for member in members],
        grades=[_grade_out(grade) for grade in grades],
        trial_grades=[_grade_out(grade) for grade in grades if grade.is_trial],
        training_grades=[_grade_out(grade) for grade in grades if grade.is_training],
        permission_options=[
            TrainingPermissionOption(key=key, label=label) for key, label in TRAINING_PERMISSION_CATALOG.items()
        ],
        can_manage=can_manage,
        can_validate=await user_is_trainer(db, user),
        can_assign_lead=await _is_direction_user(db, user),
        employee_id=own_employee.id if own_employee else None,
    )


@router.post(
    "",
    response_model=TrainingOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_hospital_manage)],
)
async def create_training(payload: TrainingRequest, db: AsyncSession = Depends(get_db)):
    await _ensure_emoji_available(db, payload.emoji)
    training = Training(
        name=payload.name,
        emoji=payload.emoji,
        kind=payload.kind,
        permissions=json.dumps(_granted_permissions(payload)),
    )
    db.add(training)
    await db.commit()
    await db.refresh(training)
    return _training_out(training)


@router.patch(
    "/{training_id}",
    response_model=TrainingOut,
    dependencies=[Depends(require_hospital_manage)],
)
async def update_training(training_id: int, payload: TrainingRequest, db: AsyncSession = Depends(get_db)):
    """Modifie la formation. Un nouvel emoji remplace l'ancien chez les employés
    qui l'avaient validée."""
    training = await _get_training(db, training_id)
    await _ensure_emoji_available(db, payload.emoji, training.id)
    emoji_changed = _emoji_key(payload.emoji) != _emoji_key(training.emoji)
    if emoji_changed:
        for employee in await _all_employees(db):
            competencies = _competencies(employee)
            if not any(_emoji_key(item) == _emoji_key(training.emoji) for item in competencies):
                continue
            _set_competencies(
                employee,
                [payload.emoji if _emoji_key(item) == _emoji_key(training.emoji) else item for item in competencies],
            )
    if payload.kind != "general":
        # Responsable, Second et En cours n'existent que dans les formations générales.
        await db.execute(delete(TrainingMember).where(TrainingMember.training_id == training.id))
    training.name = payload.name
    training.emoji = payload.emoji
    training.kind = payload.kind
    training.permissions = json.dumps(_granted_permissions(payload))
    await db.commit()
    await db.refresh(training)
    if emoji_changed:
        await push_employees_changed()
    return _training_out(training)


@router.delete(
    "/{training_id}",
    response_model=MessageResponse,
    dependencies=[Depends(require_hospital_manage)],
)
async def delete_training(training_id: int, db: AsyncSession = Depends(get_db)):
    """Supprime la formation et retire son emoji des compétences des employés."""
    training = await _get_training(db, training_id)
    changed = False
    for employee in await _all_employees(db):
        if _has_emoji(employee, training.emoji):
            _set_competencies(employee, _without_emoji(_competencies(employee), training.emoji))
            changed = True
    await db.execute(delete(TrainingMember).where(TrainingMember.training_id == training.id))
    await db.delete(training)
    await db.commit()
    if changed:
        await push_employees_changed()
    return {"message": "Formation supprimée."}


@router.put(
    "/{training_id}/employees/{employee_id}",
    response_model=TrainingEmployeeOut,
)
async def validate_training(
    training_id: int,
    employee_id: int,
    payload: TrainingMemberRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Valide la formation pour l'employé : son emoji rejoint ses compétences, avec
    les droits que la formation donne.

    Dans une formation générale, `status` donne aussi son rôle : Responsable
    (« lead ») et Second (« second ») ont l'emoji, En cours (« in_progress »)
    ne l'a pas encore."""
    member_status = payload.status if payload else "validated"
    training = await _get_training(db, training_id)
    await _ensure_can_validate(db, user, training, employee_id, member_status)
    employee = await _get_active_employee(db, employee_id)
    if member_status != "validated" and training.kind != "general":
        raise HTTPException(
            status_code=422,
            detail="Responsable, Second et En cours ne concernent que les formations générales.",
        )

    member = await db.get(TrainingMember, (training.id, employee.id))
    if member_status == "validated":
        if member is not None:
            await db.delete(member)
    elif member is None:
        db.add(TrainingMember(training_id=training.id, employee_id=employee.id, status=member_status))
    else:
        member.status = member_status

    competencies_changed = False
    if member_status == "in_progress":
        if _has_emoji(employee, training.emoji):
            _set_competencies(employee, _without_emoji(_competencies(employee), training.emoji))
            competencies_changed = True
    elif not _has_emoji(employee, training.emoji):
        competencies = _competencies(employee)
        if len(competencies) >= MAX_COMPETENCIES:
            raise HTTPException(
                status_code=409,
                detail=f"Cet employé a déjà {MAX_COMPETENCIES} compétences : retirez-en une dans les Ressources humaines.",
            )
        _set_competencies(employee, [*competencies, training.emoji])
        competencies_changed = True

    await db.commit()
    await db.refresh(employee)
    if competencies_changed:
        await push_employees_changed()
    return _employee_out(employee)


@router.delete(
    "/{training_id}/employees/{employee_id}",
    response_model=TrainingEmployeeOut,
)
async def unvalidate_training(
    training_id: int,
    employee_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retire l'employé de la formation : l'emoji quitte ses compétences et il perd
    son rôle (Responsable, Second, En cours) et les droits de la formation."""
    training = await _get_training(db, training_id)
    await _ensure_can_validate(db, user, training, employee_id, None)
    employee = await _get_active_employee(db, employee_id)
    await db.execute(
        delete(TrainingMember).where(
            TrainingMember.training_id == training.id, TrainingMember.employee_id == employee.id
        )
    )
    had_emoji = _has_emoji(employee, training.emoji)
    if had_emoji:
        _set_competencies(employee, _without_emoji(_competencies(employee), training.emoji))
    await db.commit()
    await db.refresh(employee)
    if had_emoji:
        await push_employees_changed()
    return _employee_out(employee)
