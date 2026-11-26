"""Contrôleur de Pôles & Spé : formations générales du service, rangées en pôles
(ex. Pilote Medicopter, Stock, Formateur) et en spécialités (ex. Médecin légiste).

Valider une formation pour un employé ajoute l'emoji de la formation à ses
compétences (la ligne « Compétences » des Ressources humaines) ; l'emoji est la
seule trace de la validation, si bien qu'un emoji ajouté à la main dans les
Ressources humaines compte aussi comme une validation. L'emoji est facultatif :
sans emoji, un Validé a sa ligne « validated » dans l'équipe (TrainingMember).
Les fonctions qui donnent, remplacent ou retirent l'emoji servent aussi à la
page Formation (controllers/formation.py).

Deux pôles ou spécialités n'ont jamais le même emoji, mais un module de la page
Formation peut avoir celui d'un pôle : chez un employé à l'étape du module,
l'emoji vient du module et ne vaut pas validation du pôle
(services/formation_stages.py).

Une formation générale a une équipe (Responsable, Second, Validé, En cours) et
peut donner des droits (Formateur, Médecin légiste, Ressources humaines, Stock)
à ceux qui l'ont validée : voir services/training_rights.

Droits (vérifiés par les routes, routes/trainings.py) : la page est ouverte à
tout compte validé ; créer, modifier et supprimer une formation est réservé à
ceux qui gèrent l'hôpital (rôle « Gérer l'hôpital » ou grade de la Direction).
L'équipe d'une formation se gère par la Direction, son Responsable et ses
Seconds (vérifié ici) ; seule la Direction nomme ou retire un Responsable. Les
super-admins ont tous les droits.
"""

import json
from collections.abc import Callable

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dispatch import push_employees_changed
from app.models import Employee, Grade, Training, TrainingMember, User
from app.schemas import (
    MessageResponse,
    TrainingEmployeeOut,
    TrainingMemberOut,
    TrainingMemberRequest,
    TrainingOut,
    TrainingPageOut,
    TrainingPermissionOption,
    TrainingRequest,
)
from app.services.formation_stages import module_emojis_by_stage
from app.services.hospital_access import (
    is_direction,
    linked_employee,
    user_can_manage_hospital,
)
from app.services.training_rights import (
    TRAINING_PERMISSION_CATALOG,
    emoji_key,
    employee_competencies,
    from_stage_module,
    parse_training_permissions,
    pole_competencies,
)

# Même limite que la fiche employé des Ressources humaines.
MAX_COMPETENCIES = 20


# --- Emoji d'une formation dans les compétences des employés ---


def _set_competencies(employee: Employee, competencies: list[str]) -> None:
    employee.competencies = json.dumps(list(dict.fromkeys(competencies)), ensure_ascii=False)


def has_emoji(employee: Employee, emoji: str) -> bool:
    return any(emoji_key(item) == emoji_key(emoji) for item in employee_competencies(employee))


def add_emoji(employee: Employee, emoji: str) -> bool:
    """Ajoute l'emoji aux compétences ; `True` s'il n'y était pas."""
    if has_emoji(employee, emoji):
        return False
    competencies = employee_competencies(employee)
    if len(competencies) >= MAX_COMPETENCIES:
        raise HTTPException(
            status_code=409,
            detail=f"Cet employé a déjà {MAX_COMPETENCIES} compétences : retirez-en une dans les Ressources humaines.",
        )
    _set_competencies(employee, [*competencies, emoji])
    return True


def remove_emoji(employee: Employee, emoji: str) -> bool:
    """Retire l'emoji des compétences ; `True` s'il y était."""
    if not has_emoji(employee, emoji):
        return False
    _set_competencies(
        employee, [item for item in employee_competencies(employee) if emoji_key(item) != emoji_key(emoji)]
    )
    return True


async def replace_emoji_everywhere(
    db: AsyncSession, old: str, new: str, only: Callable[[Employee], bool] | None = None
) -> bool:
    """Un nouvel emoji remplace l'ancien chez les employés qui l'avaient
    (`only` : parmi ceux qu'il retient)."""
    if emoji_key(old) == emoji_key(new):
        return False
    changed = False
    for employee in await _all_employees(db):
        if only is not None and not only(employee):
            continue
        competencies = employee_competencies(employee)
        if any(emoji_key(item) == emoji_key(old) for item in competencies):
            _set_competencies(employee, [new if emoji_key(item) == emoji_key(old) else item for item in competencies])
            changed = True
    return changed


async def remove_emoji_everywhere(
    db: AsyncSession, emoji: str, only: Callable[[Employee], bool] | None = None
) -> bool:
    """Retire l'emoji des compétences des employés (`only` : parmi ceux qu'il retient)."""
    changed = False
    for employee in await _all_employees(db):
        if only is None or only(employee):
            changed = remove_emoji(employee, emoji) or changed
    return changed


async def ensure_training_emoji_available(db: AsyncSession, emoji: str, training_id: int | None = None) -> None:
    """L'emoji est unique parmi les pôles et spécialités : c'est lui qui fait la
    validation. Un module de la page Formation peut avoir le même."""
    trainings = (await db.execute(select(Training).where(Training.emoji.is_not(None)))).scalars().all()
    for training in trainings:
        if training.id != training_id and emoji_key(training.emoji) == emoji_key(emoji):
            raise HTTPException(
                status_code=409,
                detail=f"L’emoji {emoji} est déjà celui de la formation « {training.name} ».",
            )


async def _pole_holders(db: AsyncSession, emoji: str) -> Callable[[Employee], bool]:
    """Employés chez qui l'emoji vaut validation du pôle : pas ceux chez qui il
    vient d'un module de leur étape de formation."""
    module_emojis = await module_emojis_by_stage(db)
    return lambda employee: not from_stage_module(employee, emoji, module_emojis)


async def _all_employees(db: AsyncSession) -> list[Employee]:
    return list((await db.execute(select(Employee))).scalars().all())


async def _change_training_emoji(db: AsyncSession, training: Training, new: str | None) -> bool:
    """Garde les validations quand l'emoji de la formation change ; `True` si
    des compétences ont changé.
    - Nouvel emoji : il remplace l'ancien chez ceux qui l'avaient validée.
    - Emoji retiré : il quitte leurs compétences et les Validés passent dans
      l'équipe (ligne « validated »).
    - Emoji ajouté : il rejoint les compétences des Responsables, Seconds et
      Validés, dont la ligne « validated » n'a plus lieu d'être.
    Jamais chez ceux qui ont l'emoji d'un module de leur étape de formation."""
    old = training.emoji
    if old and new:
        return await replace_emoji_everywhere(db, old, new, only=await _pole_holders(db, old))
    members = list(
        (await db.execute(select(TrainingMember).where(TrainingMember.training_id == training.id))).scalars().all()
    )
    changed = False
    if old:
        holders = await _pole_holders(db, old)
        in_roster = {member.employee_id for member in members}
        for employee in await _all_employees(db):
            if holders(employee) and remove_emoji(employee, old):
                changed = True
                if employee.id not in in_roster:
                    db.add(TrainingMember(training_id=training.id, employee_id=employee.id, status="validated"))
    elif new:
        for member in members:
            if member.status == "in_progress":
                continue
            employee = await db.get(Employee, member.employee_id)
            if employee is not None:
                changed = add_emoji(employee, new) or changed
            if member.status == "validated":
                await db.delete(member)
    return changed


# --- Lectures partagées ---


def training_out(training: Training) -> TrainingOut:
    return TrainingOut(
        id=training.id,
        name=training.name,
        emoji=training.emoji,
        kind=training.kind,
        category=training.category,
        permissions=parse_training_permissions(training.permissions),
    )


def in_formation(employee: Employee) -> bool:
    """Grade « Période d'essai » ou « En formation » : pas de pôle ni de spécialité."""
    return bool(employee.grade and (employee.grade.is_trial or employee.grade.is_training))


def employee_out(employee: Employee, module_emojis: dict[str, list[str]]) -> TrainingEmployeeOut:
    """`module_emojis` : `formation_stages.module_emojis_by_stage`, pour ne garder
    que les compétences qui comptent pour les pôles et spécialités."""
    return TrainingEmployeeOut(
        id=employee.id,
        name=" ".join(filter(None, [employee.first_name, employee.last_name])),
        phone=employee.phone,
        grade_id=employee.grade_id,
        grade_name=employee.grade.name if employee.grade else None,
        grade_level=employee.grade.level if employee.grade else None,
        grade_color=employee.grade.color if employee.grade else None,
        in_formation=in_formation(employee),
        competencies=pole_competencies(employee, module_emojis),
    )


async def active_employees(db: AsyncSession, *filters) -> list[Employee]:
    """Employés actifs, du plus haut grade au plus bas."""
    return list(
        (
            await db.execute(
                select(Employee)
                .outerjoin(Grade, Employee.grade_id == Grade.id)
                .where(Employee.is_active.is_(True), *filters)
                .order_by(Grade.level.is_(None), Grade.level.asc(), func.lower(Employee.first_name), Employee.id)
            )
        ).scalars().all()
    )


async def get_active_employee(db: AsyncSession, employee_id: int) -> Employee:
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employé introuvable.")
    if not employee.is_active:
        raise HTTPException(status_code=409, detail="Cet employé est désactivé.")
    return employee


async def get_training_of_kind(db: AsyncSession, training_id: int, kinds: set[str]) -> Training:
    """Chaque page ne voit que ses formations : les autres sont introuvables."""
    training = await db.get(Training, training_id)
    if training is None or training.kind not in kinds:
        raise HTTPException(status_code=404, detail="Formation introuvable.")
    return training


# --- Pôles & Spé ---

_GENERAL = {"general"}


async def _is_direction_user(db: AsyncSession, user: User) -> bool:
    return user.has_super_admin_rights or is_direction(await linked_employee(db, user))


async def _own_status(db: AsyncSession, user: User, training: Training) -> str | None:
    """Rôle, dans cette formation, de l'employé lié au compte (Responsable,
    Second, En cours) ; `None` s'il n'en a pas ou n'est qu'un « Validé »."""
    employee = await linked_employee(db, user)
    if employee is None:
        return None
    member = await db.get(TrainingMember, (training.id, employee.id))
    return member.status if member else None


# Rôles que chacun peut donner ou retirer dans l'équipe d'une formation.
_RESPONSIBLE_STATUSES = {"second", "validated", "in_progress"}
_SECOND_STATUSES = {"validated", "in_progress"}


async def _ensure_can_edit_roster(
    db: AsyncSession,
    user: User,
    training: Training,
    employee_id: int,
    new_status: str | None,
) -> None:
    """Qui gère l'équipe d'une formation :
    - la Direction : tout, et elle seule nomme ou retire un Responsable ;
    - le Responsable : Second, Validé et En cours ;
    - le Second : Validé et En cours, sans toucher aux Seconds ni au Responsable.
    `new_status` est le rôle donné, `None` pour un retrait.

    Les super-admins ont tous les droits."""
    if await _is_direction_user(db, user):
        return
    own = await _own_status(db, user, training)
    if own == "lead":
        allowed = _RESPONSIBLE_STATUSES
    elif own == "second":
        allowed = _SECOND_STATUSES
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls le Responsable, le Second de la formation et la Direction gèrent son équipe.",
        )
    member = await db.get(TrainingMember, (training.id, employee_id))
    current = member.status if member else "validated"
    if current not in allowed or (new_status is not None and new_status not in allowed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Seule la Direction nomme ou retire le Responsable d’une formation."
                if own == "lead"
                else "Le Second ajoute des Validés et des En cours, pas de Second ni de Responsable."
            ),
        )


def _granted_permissions(payload: TrainingRequest) -> list[str]:
    unknown = set(payload.permissions) - TRAINING_PERMISSION_CATALOG.keys()
    if unknown:
        raise HTTPException(status_code=422, detail=f"Droits inconnus : {', '.join(sorted(unknown))}.")
    return list(dict.fromkeys(payload.permissions))


# --- Handlers appelés par les routes ---


async def training_page(user: User, db: AsyncSession) -> TrainingPageOut:
    trainings = (
        await db.execute(select(Training).where(Training.kind == "general"))
    ).scalars().all()
    members = (await db.execute(select(TrainingMember).order_by(TrainingMember.created_at))).scalars().all()
    own_employee = await linked_employee(db, user)
    module_emojis = await module_emojis_by_stage(db)
    return TrainingPageOut(
        trainings=[training_out(item) for item in sorted(trainings, key=lambda item: (item.name.lower(), item.id))],
        employees=[employee_out(employee, module_emojis) for employee in await active_employees(db)],
        members=[TrainingMemberOut.model_validate(member) for member in members],
        permission_options=[
            TrainingPermissionOption(key=key, label=label) for key, label in TRAINING_PERMISSION_CATALOG.items()
        ],
        can_manage=await user_can_manage_hospital(db, user),
        can_assign_lead=await _is_direction_user(db, user),
        employee_id=own_employee.id if own_employee else None,
    )


async def create_training(payload: TrainingRequest, db: AsyncSession) -> TrainingOut:
    if payload.emoji:
        await ensure_training_emoji_available(db, payload.emoji)
    training = Training(
        name=payload.name,
        emoji=payload.emoji,
        kind="general",
        category=payload.category,
        permissions=json.dumps(_granted_permissions(payload)),
    )
    db.add(training)
    await db.commit()
    await db.refresh(training)
    return training_out(training)


async def update_training(training_id: int, payload: TrainingRequest, db: AsyncSession) -> TrainingOut:
    """Modifie la formation. Ceux qui l'avaient validée la gardent, même si son
    emoji change, est retiré ou ajouté : voir `_change_training_emoji`."""
    training = await get_training_of_kind(db, training_id, _GENERAL)
    if payload.emoji:
        await ensure_training_emoji_available(db, payload.emoji, training.id)
    emoji_changed = await _change_training_emoji(db, training, payload.emoji)
    training.name = payload.name
    training.emoji = payload.emoji
    training.category = payload.category
    training.permissions = json.dumps(_granted_permissions(payload))
    await db.commit()
    await db.refresh(training)
    if emoji_changed:
        await push_employees_changed()
    return training_out(training)


async def delete_training(training_id: int, db: AsyncSession) -> MessageResponse:
    """Supprime la formation et retire son emoji des compétences des employés
    (pas de ceux qui l'ont d'un module de leur étape)."""
    training = await get_training_of_kind(db, training_id, _GENERAL)
    changed = bool(training.emoji) and await remove_emoji_everywhere(
        db, training.emoji, only=await _pole_holders(db, training.emoji)
    )
    await db.execute(delete(TrainingMember).where(TrainingMember.training_id == training.id))
    await db.delete(training)
    await db.commit()
    if changed:
        await push_employees_changed()
    return MessageResponse(message="Formation supprimée.")


async def validate_training(
    training_id: int,
    employee_id: int,
    payload: TrainingMemberRequest | None,
    user: User,
    db: AsyncSession,
) -> TrainingEmployeeOut:
    """Donne à l'employé son rôle dans la formation : Responsable (« lead »),
    Second (« second ») et Validé (« validated ») ont l'emoji dans leurs
    compétences, avec les droits que la formation donne ; En cours
    (« in_progress ») ne l'a pas encore. Sans emoji, seul le rôle est gardé, et
    le Validé a sa ligne comme les autres."""
    member_status = payload.status if payload else "validated"
    training = await get_training_of_kind(db, training_id, _GENERAL)
    await _ensure_can_edit_roster(db, user, training, employee_id, member_status)
    employee = await get_active_employee(db, employee_id)
    if in_formation(employee):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{employee.grade.name} : un employé en période d’essai ou en formation ne rejoint ni pôle ni spécialité.",
        )

    member = await db.get(TrainingMember, (training.id, employee.id))
    if member_status == "validated" and training.emoji:
        if member is not None:
            await db.delete(member)
    elif member is None:
        db.add(TrainingMember(training_id=training.id, employee_id=employee.id, status=member_status))
    else:
        member.status = member_status

    if not training.emoji:
        competencies_changed = False
    elif member_status == "in_progress":
        competencies_changed = remove_emoji(employee, training.emoji)
    else:
        competencies_changed = add_emoji(employee, training.emoji)

    await db.commit()
    await db.refresh(employee)
    if competencies_changed:
        await push_employees_changed()
    return employee_out(employee, await module_emojis_by_stage(db))


async def unvalidate_training(
    training_id: int, employee_id: int, user: User, db: AsyncSession
) -> TrainingEmployeeOut:
    """Retire l'employé de la formation : l'emoji quitte ses compétences (sauf
    s'il vient d'un module de son étape) et il perd son rôle (Responsable,
    Second, En cours) et les droits de la formation."""
    training = await get_training_of_kind(db, training_id, _GENERAL)
    await _ensure_can_edit_roster(db, user, training, employee_id, None)
    employee = await get_active_employee(db, employee_id)
    await db.execute(
        delete(TrainingMember).where(
            TrainingMember.training_id == training.id, TrainingMember.employee_id == employee.id
        )
    )
    module_emojis = await module_emojis_by_stage(db)
    had_emoji = (
        bool(training.emoji)
        and not from_stage_module(employee, training.emoji, module_emojis)
        and remove_emoji(employee, training.emoji)
    )
    await db.commit()
    await db.refresh(employee)
    if had_emoji:
        await push_employees_changed()
    return employee_out(employee, module_emojis)
