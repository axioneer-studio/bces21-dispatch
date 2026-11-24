"""Page Formation : une fiche par employé en formation, de la période d'essai
(grades « Période d'essai ») à la période de formation (grades « En
formation »), comme la feuille de suivi du BCES.

- Commun : arrivée (la date de la fiche RH, corrigeable ici), jours depuis
  l'arrivée, mentors (des formateurs), notes.
- Période d'essai : modules par type (basiques, outils, interventions,
  blessures) notés de 0 à 3 (Non observé, Observé, Pratiqué avec aide,
  Pratiqué en autonomie), questionnaire (bonnes réponses ramenées sur 20) et
  simulation validante (cinq critères de 1 à 5), statut de progression.
- Période de formation : formations obligatoires et facultatives notées de 0 à
  2 (Non observé, Pratiqué, Validé) et simulation validante (six critères).

La progression d'un type est la somme des niveaux sur les points possibles. Un
module peut avoir un emoji : il rejoint les compétences de l'employé au niveau
le plus haut, tant que l'employé est à l'étape du module.

Passages, avec leur annulation :
- passage au grade « En formation » juste au-dessus, depuis la période
  d'essai. Les emojis des modules de période d'essai quittent les compétences ;
- fin de formation, passage au grade juste au-dessus, depuis la période de
  formation. Les emojis des modules de période de formation quittent les
  compétences.

Un passage demande les modules obligatoires de l'étape au plus haut, chaque
barre de progression de l'étape à son seuil et la note de l'étape (moyenne
questionnaire + simulation, puis simulation de la période de formation) donnée
et à son seuil (services/formation_thresholds.py). Il se force (Direction et
Responsable du pôle qui donne le droit Formateur) : seuls les modules
obligatoires restent alors exigés.

Droits (vérifiés par les routes, routes/formation.py) : toutes les routes
demandent le droit « Formateur ». Les modules, le questionnaire et les seuils
se gèrent par la Direction, « Gérer l'hôpital » et le Responsable du pôle qui
donne le droit Formateur (`user_manages_formation`). Le forçage d'un passage se
vérifie ici (`user_can_force_passage`).
"""

import math

import json
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dispatch import push_employees_changed
from app.controllers.trainings import (
    active_employees,
    add_emoji,
    get_active_employee,
    remove_emoji,
    remove_emoji_everywhere,
    replace_emoji_everywhere,
)
from app.models import (
    Employee,
    Grade,
    InternAnswer,
    InternMentor,
    InternModule,
    InternModuleLevel,
    InternQuestion,
    InternRecord,
    Training,
    TrainingMember,
    User,
)
from app.schemas import (
    InternAnswerRequest,
    InternPassageRequest,
    InternLevelRequest,
    InternModuleOut,
    InternModuleRequest,
    InternPersonOut,
    InternProgressOut,
    InternQuestionOut,
    InternQuestionRequest,
    InternRecordOut,
    InternRecordUpdate,
    InternsPageOut,
    InternStatusOut,
    InternThresholdsOut,
    InternThresholdsUpdate,
    MessageResponse,
    SimulationCriterionOut,
    TrainingGradeOut,
)
from app.services.formation_stages import (
    TRAINING,
    TRAINING_CATEGORIES,
    TRIAL,
    TRIAL_CATEGORIES,
    employee_stage,
    module_stage,
)
from app.services.formation_thresholds import read_thresholds, write_thresholds
from app.services.hospital_access import is_direction, linked_employee, user_can_manage_hospital
from app.services.training_rights import (
    TRAINER_PERMISSION,
    emoji_key,
    employees_with_training_permission,
    parse_training_permissions,
)

# Niveau le plus haut : Pratiqué en autonomie (période d'essai), Validé (période de formation).
MAX_LEVELS = {TRIAL: 3, TRAINING: 2}
# Barres de progression de chaque étape, qui ont un seuil de passage.
PROGRESS_BARS = {
    TRIAL: (
        ("basics", "Validations basiques"),
        ("tools", "Gestion des outils"),
        ("interventions", "Type d’intervention"),
        ("injuries", "Blessures"),
        ("overall", "Progression totale"),
    ),
    TRAINING: (
        ("mandatory", "Formations obligatoires"),
        ("optional", "Formations facultatives"),
    ),
}
CRITERIA = {
    TRIAL: [
        ("on_site", "Prise en charge sur place"),
        ("diagnosis", "Diagnostic"),
        ("operation", "Opération"),
        ("record", "Dossier"),
        ("confidence", "Niveau de confiance"),
    ],
    TRAINING: [
        ("on_site", "Prise en charge sur place"),
        ("diagnosis", "Diagnostic"),
        ("operation", "Opération"),
        ("malus", "Gestion Malus"),
        ("record", "Dossier"),
        ("confidence", "Niveau de confiance"),
    ],
}


def max_level(module: InternModule) -> int:
    return MAX_LEVELS[module_stage(module)]


def _grade_out(grade: Grade) -> TrainingGradeOut:
    return TrainingGradeOut(id=grade.id, name=grade.name, level=grade.level)


# --- Droits ---


async def _leads_trainer_pole(db: AsyncSession, employee: Employee | None) -> bool:
    """L'employé est Responsable d'un pôle qui donne le droit Formateur."""
    if employee is None:
        return False
    led = (
        await db.execute(
            select(Training)
            .join(TrainingMember, TrainingMember.training_id == Training.id)
            .where(TrainingMember.employee_id == employee.id, TrainingMember.status == "lead")
        )
    ).scalars().all()
    return any(TRAINER_PERMISSION in parse_training_permissions(training.permissions) for training in led)


async def user_manages_formation(db: AsyncSession, user: User) -> bool:
    """Direction, « Gérer l'hôpital » (super-admins compris) et Responsable d'un
    pôle qui donne le droit Formateur."""
    if await user_can_manage_hospital(db, user):
        return True
    return await _leads_trainer_pole(db, await linked_employee(db, user))


async def user_can_force_passage(db: AsyncSession, user: User) -> bool:
    """Forcer un passage de grade : Direction (super-admins compris) et
    Responsable d'un pôle qui donne le droit Formateur, pas « Gérer l'hôpital »."""
    if user.has_super_admin_rights:
        return True
    employee = await linked_employee(db, user)
    return is_direction(employee) or await _leads_trainer_pole(db, employee)


# --- Grades des passages ---


async def _grade_above(db: AsyncSession, grade: Grade | None, *, training_only: bool) -> Grade | None:
    """Grade juste au-dessus (niveau plus petit). Pour le passage de la période
    d'essai : un grade « En formation », à défaut le plus bas d'entre eux."""
    query = select(Grade).order_by(Grade.level.desc())
    if training_only:
        query = query.where(Grade.is_training.is_(True))
    grades = list((await db.execute(query)).scalars().all())
    if grade is not None:
        above = [item for item in grades if item.level < grade.level]
        if above:
            return above[0]
        if not training_only:
            return None
    return grades[0] if training_only and grades else None


# --- Calculs de la fiche ---


def _ratio(levels: dict[int, int], modules: list[InternModule]) -> float:
    """Progression d'un ensemble de modules ; complète s'il n'y a rien à valider."""
    possible = sum(max_level(module) for module in modules)
    if not possible:
        return 1.0
    return sum(min(levels.get(module.id, 0), max_level(module)) for module in modules) / possible


def _progress(levels: dict[int, int], modules: list[InternModule]) -> InternProgressOut:
    of = {category: [module for module in modules if module.category == category] for category in (*TRIAL_CATEGORIES, *TRAINING_CATEGORIES)}
    return InternProgressOut(
        **{category: _ratio(levels, items) for category, items in of.items()},
        overall=_ratio(levels, [module for module in modules if module_stage(module) == TRIAL]),
    )


def _simulation(value: str | None, stage: str) -> dict[str, int]:
    try:
        scores = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    if not isinstance(scores, dict):
        return {}
    keys = {key for key, _label in CRITERIA[stage]}
    return {key: score for key, score in scores.items() if key in keys and isinstance(score, int) and 1 <= score <= 5}


def _simulation_score(scores: dict[str, int], stage: str) -> float | None:
    """Chaque critère vaut de 0 (1, pas réalisé) à 4 points (5, très bien), le
    total est ramené sur 20 ; il faut tous les critères notés."""
    criteria = CRITERIA[stage]
    if len(scores) != len(criteria):
        return None
    return round(sum(score - 1 for score in scores.values()) / (4 * len(criteria)) * 20, 1)


def _status(days: int | None, progress: InternProgressOut, grade_name: str | None) -> InternStatusOut:
    """Statut de la feuille de suivi, règle par règle, la première qui s'applique."""
    days = days or 0
    basics_done = progress.basics >= 1
    overall = progress.overall
    if overall >= 1:
        return InternStatusOut(label=f"🎉 Formation {grade_name or 'en période d’essai'} terminée !", tone="done")
    if basics_done and overall >= 0.85:
        return InternStatusOut(label="✅ À valider : questionnaire et simulation", tone="ready")
    if days < 15:
        return InternStatusOut(label="👍 Progression normale", tone="normal")
    if days > 15 and not basics_done:
        return InternStatusOut(label="⚠️ Il faut valider les basiques rapidement", tone="warning")
    if days <= 30 and basics_done:
        return InternStatusOut(label="👍 Progression normale", tone="normal")
    if days <= 45 and basics_done and overall < 0.5:
        return InternStatusOut(label="⚠️ Il faut accélérer la formation", tone="warning")
    if days <= 45 and basics_done:
        return InternStatusOut(label="👍 Progression normale", tone="normal")
    if days >= 60 and basics_done:
        return InternStatusOut(label="⚠️ Urgence : formation à finir", tone="urgent")
    if days > 45 and basics_done and overall < 0.75:
        return InternStatusOut(label="⚠️ Formation à accélérer nettement", tone="warning")
    return InternStatusOut(label="👍 Progression normale", tone="normal")


def _percent(value: float) -> int:
    """Pourcentage entier, arrondi vers le bas comme sur la fiche : 99,6 % reste
    sous un seuil de 100 %."""
    return math.floor(value * 100 + 1e-9)


def _note(value: float) -> str:
    return f"{value:g} / 20"


def _missing_required(levels: dict[int, int], modules: list[InternModule], stage: str) -> list[str]:
    """Modules obligatoires de l'étape pas encore au plus haut."""
    return [
        module.name
        for module in modules
        if module.is_required and module_stage(module) == stage and levels.get(module.id, 0) < max_level(module)
    ]


def _blockers(
    stage: str,
    progress: InternProgressOut,
    note: float | None,
    thresholds: InternThresholdsOut,
    missing_required: list[str],
    next_grade: Grade | None,
) -> list[str]:
    """Ce qui manque pour passer sans forcer, dans l'ordre de la fiche. `note` :
    moyenne (période d'essai) ou simulation (période de formation). Un seuil à
    0 n'exige rien, pas même une note donnée."""
    blockers: list[str] = []
    if missing_required:
        blockers.append(f"Modules obligatoires à valider : {', '.join(missing_required)}")
    for key, label in PROGRESS_BARS[stage]:
        required = getattr(thresholds, key)
        value = _percent(getattr(progress, key))
        if value < required:
            blockers.append(f"{label} : {value} % ({required} % requis)")
    if stage == TRIAL:
        required_note, label, unscored = thresholds.average, "Moyenne", "Questionnaire et simulation à noter"
    else:
        required_note, label, unscored = thresholds.resident_simulation, "Simulation", "Simulation à noter"
    if required_note > 0 and note is None:
        blockers.append(unscored)
    elif required_note > 0 and note < required_note:
        blockers.append(f"{label} {_note(note)} ({_note(required_note)} requis)")
    if next_grade is None:
        blockers.append("Aucun grade au-dessus dans Direction")
    return blockers


def _person(employee: Employee) -> InternPersonOut:
    return InternPersonOut(id=employee.id, name=" ".join(filter(None, [employee.first_name, employee.last_name])))


class _PageData:
    """Tout ce qu'il faut pour calculer les fiches, chargé en une fois."""

    def __init__(self, modules, questions, records, mentors, levels, answers, people, thresholds):
        self.modules: list[InternModule] = modules
        self.questions: list[InternQuestion] = questions
        self.records: dict[int, InternRecord] = records
        self.mentors: dict[int, list[int]] = mentors
        self.levels: dict[int, dict[int, int]] = levels
        self.answers: dict[int, set[int]] = answers
        self.people: dict[int, Employee] = people
        self.thresholds: InternThresholdsOut = thresholds


async def _load(db: AsyncSession, employee_ids: list[int]) -> _PageData:
    modules = list((await db.execute(select(InternModule).order_by(InternModule.id))).scalars().all())
    questions = list((await db.execute(select(InternQuestion).order_by(InternQuestion.id))).scalars().all())
    records = {
        record.employee_id: record
        for record in (
            await db.execute(select(InternRecord).where(InternRecord.employee_id.in_(employee_ids)))
        ).scalars().all()
    }
    mentors: dict[int, list[int]] = {}
    for row in (await db.execute(select(InternMentor).where(InternMentor.intern_id.in_(employee_ids)))).scalars().all():
        mentors.setdefault(row.intern_id, []).append(row.mentor_id)
    levels: dict[int, dict[int, int]] = {}
    for row in (
        await db.execute(select(InternModuleLevel).where(InternModuleLevel.employee_id.in_(employee_ids)))
    ).scalars().all():
        levels.setdefault(row.employee_id, {})[row.module_id] = row.level
    answers: dict[int, set[int]] = {}
    for row in (await db.execute(select(InternAnswer).where(InternAnswer.employee_id.in_(employee_ids)))).scalars().all():
        answers.setdefault(row.employee_id, set()).add(row.question_id)
    mentor_ids = {mentor_id for ids in mentors.values() for mentor_id in ids}
    people = {
        employee.id: employee
        for employee in (await db.execute(select(Employee).where(Employee.id.in_(mentor_ids)))).scalars().all()
    }
    return _PageData(modules, questions, records, mentors, levels, answers, people, await read_thresholds(db))


def _record_out(employee: Employee, data: _PageData, stage: str, next_grade: Grade | None) -> InternRecordOut:
    """`stage` : étape affichée (celle du grade, ou la dernière pour une
    formation terminée) ; `next_grade` : grade donné par le prochain passage."""
    record = data.records.get(employee.id)
    module_ids = {module.id for module in data.modules}
    levels = {module_id: level for module_id, level in data.levels.get(employee.id, {}).items() if module_id in module_ids}
    question_ids = {question.id for question in data.questions}
    answers = sorted(data.answers.get(employee.id, set()) & question_ids)
    simulation = _simulation(record.simulation if record else None, TRIAL)
    resident_simulation = _simulation(record.resident_simulation if record else None, TRAINING)
    progress = _progress(levels, data.modules)
    days = (date.today() - employee.arrival_date).days if employee.arrival_date else None

    questionnaire = round(len(answers) / len(question_ids) * 20, 1) if question_ids else None
    simulation_score = _simulation_score(simulation, TRIAL)
    resident_simulation_score = _simulation_score(resident_simulation, TRAINING)
    average = (
        round((questionnaire + simulation_score) / 2, 1)
        if questionnaire is not None and simulation_score is not None
        else None
    )
    in_grade_stage = employee_stage(employee) == stage
    missing_required = _missing_required(levels, data.modules, stage) if in_grade_stage else []
    blockers = (
        _blockers(
            stage,
            progress,
            average if stage == TRIAL else resident_simulation_score,
            data.thresholds,
            missing_required,
            next_grade,
        )
        if in_grade_stage
        else []
    )
    return InternRecordOut(
        employee_id=employee.id,
        name=_person(employee).name,
        stage=stage,
        grade_name=employee.grade.name if employee.grade else None,
        grade_color=employee.grade.color if employee.grade else None,
        arrival_date=employee.arrival_date,
        days=days,
        mentors=[_person(data.people[mentor_id]) for mentor_id in data.mentors.get(employee.id, []) if mentor_id in data.people],
        levels=levels,
        answers=answers,
        simulation=simulation,
        resident_simulation=resident_simulation,
        notes=record.notes if record else "",
        progress=progress,
        questionnaire_score=questionnaire,
        simulation_score=simulation_score,
        average=average,
        resident_simulation_score=resident_simulation_score,
        status=_status(days, progress, employee.grade.name if employee.grade else None) if stage == TRIAL else None,
        blockers=blockers,
        missing_required=missing_required,
        can_pass_resident=in_grade_stage and stage == TRIAL and not blockers,
        resident_at=record.resident_at if record else None,
        can_complete=in_grade_stage and stage == TRAINING and not blockers,
        next_grade_name=next_grade.name if next_grade and in_grade_stage else None,
        completed_at=record.completed_at if record else None,
    )


async def _next_grade(db: AsyncSession, employee: Employee) -> Grade | None:
    stage = employee_stage(employee)
    if stage == TRIAL:
        return await _grade_above(db, employee.grade, training_only=True)
    if stage == TRAINING:
        return await _grade_above(db, employee.grade, training_only=False)
    return None


async def _fiche(db: AsyncSession, employee: Employee) -> InternRecordOut:
    await db.refresh(employee)
    stage = employee_stage(employee) or TRAINING
    return _record_out(employee, await _load(db, [employee.id]), stage, await _next_grade(db, employee))


async def _in_formation(db: AsyncSession, employee_id: int) -> tuple[Employee, str]:
    """Employé actif d'un grade « Période d'essai » ou « En formation »."""
    employee = await get_active_employee(db, employee_id)
    stage = employee_stage(employee)
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cet employé n’est ni en période d’essai ni en formation.",
        )
    return employee, stage


async def _record(db: AsyncSession, employee_id: int) -> InternRecord:
    record = await db.get(InternRecord, employee_id)
    if record is None:
        record = InternRecord(employee_id=employee_id)
        db.add(record)
    return record


async def _stage_emojis(db: AsyncSession, employee: Employee, stage: str, present: bool) -> bool:
    """Donne (`present`) les emojis des modules de l'étape au niveau le plus
    haut, ou retire tous ceux de l'étape (passage à l'étape suivante)."""
    modules = (
        await db.execute(select(InternModule).where(InternModule.emoji.is_not(None)))
    ).scalars().all()
    levels = {
        row.module_id: row.level
        for row in (
            await db.execute(select(InternModuleLevel).where(InternModuleLevel.employee_id == employee.id))
        ).scalars().all()
    }
    changed = False
    for module in modules:
        if module_stage(module) != stage:
            continue
        if present and levels.get(module.id) == max_level(module):
            changed = add_emoji(employee, module.emoji) or changed
        elif not present:
            changed = remove_emoji(employee, module.emoji) or changed
    return changed


async def _employees_at_level_max(db: AsyncSession, module: InternModule) -> list[Employee]:
    """Employés encore à l'étape du module, au niveau le plus haut."""
    employees = (
        await db.execute(
            select(Employee)
            .join(InternModuleLevel, InternModuleLevel.employee_id == Employee.id)
            .where(InternModuleLevel.module_id == module.id, InternModuleLevel.level == max_level(module))
        )
    ).scalars().all()
    return [employee for employee in employees if employee_stage(employee) == module_stage(module)]


# --- Handlers appelés par les routes : page ---


async def formation_page(user: User, db: AsyncSession) -> InternsPageOut:
    interns =await active_employees(db, Grade.is_trial.is_(True))
    residents = await active_employees(db, Grade.is_training.is_(True))
    completed_ids = (
        await db.execute(select(InternRecord.employee_id).where(InternRecord.completed_at.is_not(None)))
    ).scalars().all()
    completed = [
        employee
        for employee in await active_employees(db, Employee.id.in_(list(completed_ids)))
        if employee_stage(employee) is None
    ]
    data = await _load(db, [employee.id for employee in [*interns, *residents, *completed]])
    grades = (await db.execute(select(Grade).order_by(Grade.level.asc(), Grade.name.asc()))).scalars().all()
    return InternsPageOut(
        modules=[InternModuleOut.model_validate(module) for module in data.modules],
        questions=[InternQuestionOut.model_validate(question) for question in data.questions],
        criteria=[SimulationCriterionOut(key=key, label=label) for key, label in CRITERIA[TRIAL]],
        resident_criteria=[SimulationCriterionOut(key=key, label=label) for key, label in CRITERIA[TRAINING]],
        interns=[_record_out(employee, data, TRIAL, await _next_grade(db, employee)) for employee in interns],
        residents=[_record_out(employee, data, TRAINING, await _next_grade(db, employee)) for employee in residents],
        completed=[_record_out(employee, data, TRAINING, None) for employee in completed],
        trainers=[_person(employee) for employee in await employees_with_training_permission(db, TRAINER_PERMISSION)],
        trial_grades=[_grade_out(grade) for grade in grades if grade.is_trial],
        training_grades=[_grade_out(grade) for grade in grades if grade.is_training],
        thresholds=data.thresholds,
        can_manage=await user_manages_formation(db, user),
        can_force=await user_can_force_passage(db, user),
    )


# --- Modules et questionnaire ---


async def _ensure_module_emoji_available(db: AsyncSession, emoji: str, module_id: int | None = None) -> None:
    """L'emoji est unique parmi les modules ; un pôle ou une spécialité peut avoir
    le même (services/formation_stages.py)."""
    modules = (await db.execute(select(InternModule).where(InternModule.emoji.is_not(None)))).scalars().all()
    for module in modules:
        if module.id != module_id and emoji_key(module.emoji) == emoji_key(emoji):
            raise HTTPException(
                status_code=409,
                detail=f"L’emoji {emoji} est déjà celui du module « {module.name} ».",
            )


def _at_stage_of(module: InternModule):
    """Employés à l'étape du module : les seuls chez qui son emoji vient de lui."""
    return lambda employee: employee_stage(employee) == module_stage(module)


async def create_module(payload: InternModuleRequest, db: AsyncSession) -> InternModuleOut:
    if payload.emoji:
        await _ensure_module_emoji_available(db, payload.emoji)
    module = InternModule(
        category=payload.category, name=payload.name, emoji=payload.emoji, is_required=payload.is_required
    )
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return InternModuleOut.model_validate(module)


async def update_module(module_id: int, payload: InternModuleRequest, db: AsyncSession) -> InternModuleOut:
    """Chez les employés à l'étape du module, un nouvel emoji remplace l'ancien
    et un emoji retiré quitte leurs compétences ; un emoji ajouté va à ceux qui
    ont déjà le module au plus haut. Les autres gardent le leur (un pôle peut
    avoir le même). Le module reste à son étape (période d'essai ou de
    formation)."""
    module = await db.get(InternModule, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Module introuvable.")
    if (payload.category in TRIAL_CATEGORIES) != (module.category in TRIAL_CATEGORIES):
        raise HTTPException(status_code=422, detail="Un module ne change pas d’étape : créez-le dans l’autre.")
    if payload.emoji:
        await _ensure_module_emoji_available(db, payload.emoji, module_id=module.id)
    changed = False
    if module.emoji and payload.emoji:
        changed = await replace_emoji_everywhere(db, module.emoji, payload.emoji, only=_at_stage_of(module))
    elif module.emoji:
        changed = await remove_emoji_everywhere(db, module.emoji, only=_at_stage_of(module))
    elif payload.emoji:
        for employee in await _employees_at_level_max(db, module):
            changed = add_emoji(employee, payload.emoji) or changed
    module.category = payload.category
    module.name = payload.name
    module.emoji = payload.emoji
    module.is_required = payload.is_required
    await db.commit()
    await db.refresh(module)
    if changed:
        await push_employees_changed()
    return InternModuleOut.model_validate(module)


async def delete_module(module_id: int, db: AsyncSession) -> MessageResponse:
    """Supprime le module, les niveaux des employés et son emoji des compétences
    des employés à son étape."""
    module = await db.get(InternModule, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Module introuvable.")
    changed = (
        await remove_emoji_everywhere(db, module.emoji, only=_at_stage_of(module)) if module.emoji else False
    )
    await db.execute(delete(InternModuleLevel).where(InternModuleLevel.module_id == module.id))
    await db.delete(module)
    await db.commit()
    if changed:
        await push_employees_changed()
    return MessageResponse(message="Module supprimé.")


async def create_question(payload: InternQuestionRequest, db: AsyncSession) -> InternQuestionOut:
    question = InternQuestion(question=payload.question, answer=payload.answer)
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return InternQuestionOut.model_validate(question)


async def update_question(question_id: int, payload: InternQuestionRequest, db: AsyncSession) -> InternQuestionOut:
    question = await db.get(InternQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question introuvable.")
    question.question = payload.question
    question.answer = payload.answer
    await db.commit()
    await db.refresh(question)
    return InternQuestionOut.model_validate(question)


async def delete_question(question_id: int, db: AsyncSession) -> MessageResponse:
    question = await db.get(InternQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question introuvable.")
    await db.execute(delete(InternAnswer).where(InternAnswer.question_id == question.id))
    await db.delete(question)
    await db.commit()
    return MessageResponse(message="Question supprimée.")


async def update_thresholds(payload: InternThresholdsUpdate, db: AsyncSession) -> InternThresholdsOut:
    """Seuils du passage sans forçage, communs à toutes les fiches."""
    await write_thresholds(db, payload)
    await db.commit()
    return await read_thresholds(db)


# --- Fiche ---


def _checked_scores(scores: dict[str, int], stage: str) -> str:
    keys = {key for key, _label in CRITERIA[stage]}
    if set(scores) - keys or any(not 1 <= score <= 5 for score in scores.values()):
        raise HTTPException(status_code=422, detail="La simulation se note de 1 à 5 sur chacun de ses critères.")
    return json.dumps(scores)


async def update_record(employee_id: int, payload: InternRecordUpdate, db: AsyncSession) -> InternRecordOut:
    """Arrivée (celle de la fiche RH), notes, mentors (des formateurs) et
    simulation validante de l'étape de l'employé (de 1 à 5 par critère ; un
    critère absent n'est pas encore noté)."""
    employee, stage = await _in_formation(db, employee_id)
    data = payload.model_dump(exclude_unset=True)
    record = await _record(db, employee.id)
    employees_changed = False
    if "arrival_date" in data:
        employee.arrival_date = data["arrival_date"]
        employees_changed = True
    if data.get("notes") is not None:
        record.notes = data["notes"].strip()
    if data.get("mentor_ids") is not None:
        trainer_ids = {trainer.id for trainer in await employees_with_training_permission(db, TRAINER_PERMISSION)}
        mentor_ids = list(dict.fromkeys(data["mentor_ids"]))
        if set(mentor_ids) - trainer_ids:
            raise HTTPException(status_code=422, detail="Un mentor doit être un formateur.")
        if employee.id in mentor_ids:
            raise HTTPException(status_code=422, detail="Un employé ne peut pas être son propre mentor.")
        await db.execute(delete(InternMentor).where(InternMentor.intern_id == employee.id))
        db.add_all(InternMentor(intern_id=employee.id, mentor_id=mentor_id) for mentor_id in mentor_ids)
    for key, key_stage in (("simulation", TRIAL), ("resident_simulation", TRAINING)):
        if data.get(key) is None:
            continue
        if stage != key_stage:
            raise HTTPException(status_code=409, detail="Cette simulation n’est pas celle de l’étape de l’employé.")
        setattr(record, key, _checked_scores(data[key], key_stage))
    await db.commit()
    if employees_changed:
        await push_employees_changed()
    return await _fiche(db, employee)


async def set_module_level(
    employee_id: int, module_id: int, payload: InternLevelRequest, db: AsyncSession
) -> InternRecordOut:
    """Niveau de l'employé sur un module de son étape ; au niveau le plus haut,
    l'emoji du module rejoint ses compétences, en dessous il les quitte."""
    employee, stage = await _in_formation(db, employee_id)
    module = await db.get(InternModule, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Module introuvable.")
    if module_stage(module) != stage:
        raise HTTPException(status_code=409, detail="Ce module n’est pas de l’étape de l’employé.")
    if payload.level > max_level(module):
        raise HTTPException(status_code=422, detail=f"Ce module se note de 0 à {max_level(module)}.")
    await _record(db, employee.id)
    row = await db.get(InternModuleLevel, (employee.id, module.id))
    if payload.level == 0:
        if row is not None:
            await db.delete(row)
    elif row is None:
        db.add(InternModuleLevel(employee_id=employee.id, module_id=module.id, level=payload.level))
    else:
        row.level = payload.level
    changed = False
    if module.emoji:
        changed = (
            add_emoji(employee, module.emoji)
            if payload.level == max_level(module)
            else remove_emoji(employee, module.emoji)
        )
    await db.commit()
    if changed:
        await push_employees_changed()
    return await _fiche(db, employee)


async def set_answer(
    employee_id: int, question_id: int, payload: InternAnswerRequest, db: AsyncSession
) -> InternRecordOut:
    employee, stage = await _in_formation(db, employee_id)
    if stage != TRIAL:
        raise HTTPException(status_code=409, detail="Le questionnaire se remplit pendant la période d’essai.")
    if await db.get(InternQuestion, question_id) is None:
        raise HTTPException(status_code=404, detail="Question introuvable.")
    await _record(db, employee.id)
    row = await db.get(InternAnswer, (employee.id, question_id))
    if payload.correct and row is None:
        db.add(InternAnswer(employee_id=employee.id, question_id=question_id))
    elif not payload.correct and row is not None:
        await db.delete(row)
    await db.commit()
    return await _fiche(db, employee)


# --- Passages de grade ---


async def _change_grade(db: AsyncSession, employee: Employee, grade: Grade, leaving: str, entering: str | None) -> None:
    """Change le grade : les emojis de l'étape quittée partent, ceux de l'étape
    retrouvée reviennent selon les niveaux gardés."""
    await _stage_emojis(db, employee, leaving, present=False)
    employee.grade = grade
    if entering is not None:
        await _stage_emojis(db, employee, entering, present=True)
    await db.commit()
    await push_employees_changed()


async def _ensure_can_pass(
    db: AsyncSession, user: User, fiche: InternRecordOut, payload: InternPassageRequest | None
) -> None:
    """Passage normal si rien ne manque ; sinon forcé, par la Direction ou le
    Responsable du pôle Formation, et seulement avec les modules obligatoires
    validés."""
    if not fiche.blockers:
        return
    if not (payload and payload.force):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Passage impossible : {' ; '.join(fiche.blockers)}."
        )
    if not await user_can_force_passage(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls la Direction et le Responsable du pôle Formation forcent un passage.",
        )
    if fiche.missing_required:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Même forcé, il faut valider les modules obligatoires : {', '.join(fiche.missing_required)}.",
        )
    if fiche.next_grade_name is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Aucun grade au-dessus : vérifiez Direction.")


async def pass_training_grade(
    employee_id: int, payload: InternPassageRequest | None, user: User, db: AsyncSession
) -> InternRecordOut:
    """Fin de période d'essai (conditions : `_ensure_can_pass`). L'employé
    prend le grade « En formation » juste au-dessus."""
    employee, stage = await _in_formation(db, employee_id)
    if stage != TRIAL:
        raise HTTPException(status_code=409, detail="Cet employé n’est pas en période d’essai.")
    await _ensure_can_pass(db, user, await _fiche(db, employee), payload)
    target = await _next_grade(db, employee)
    record = await _record(db, employee.id)
    record.previous_grade_id = employee.grade_id
    record.resident_at = datetime.now(timezone.utc)
    await _change_grade(db, employee, target, leaving=TRIAL, entering=TRAINING)
    return await _fiche(db, employee)


async def cancel_training_grade(employee_id: int, db: AsyncSession) -> InternRecordOut:
    """Annule le passage : l'employé reprend son grade de période d'essai, celui
    d'avant le passage, ou à défaut (passé « En formation » hors de la page) le
    grade « Période d'essai » juste en dessous du sien."""
    employee, stage = await _in_formation(db, employee_id)
    if stage != TRAINING:
        raise HTTPException(status_code=409, detail="Cet employé n’est pas en formation.")
    record = await _record(db, employee.id)
    previous = await db.get(Grade, record.previous_grade_id) if record.previous_grade_id else None
    if previous is None or not previous.is_trial:
        trial_grades = list(
            (await db.execute(select(Grade).where(Grade.is_trial.is_(True)).order_by(Grade.level.asc()))).scalars().all()
        )
        below = [grade for grade in trial_grades if grade.level > employee.grade.level]
        previous = below[0] if below else (trial_grades[-1] if trial_grades else None)
    if previous is None:
        raise HTTPException(status_code=409, detail="Aucun grade « Période d’essai » : cochez-le dans Direction.")
    record.resident_at = None
    record.previous_grade_id = None
    await _change_grade(db, employee, previous, leaving=TRAINING, entering=TRIAL)
    return await _fiche(db, employee)


async def complete_formation(
    employee_id: int, payload: InternPassageRequest | None, user: User, db: AsyncSession
) -> InternRecordOut:
    """Fin de formation (conditions : `_ensure_can_pass`). L'employé prend le
    grade juste au-dessus."""
    employee, stage = await _in_formation(db, employee_id)
    if stage != TRAINING:
        raise HTTPException(status_code=409, detail="Cet employé n’est pas en formation.")
    await _ensure_can_pass(db, user, await _fiche(db, employee), payload)
    target = await _next_grade(db, employee)
    record = await _record(db, employee.id)
    record.completed_from_grade_id = employee.grade_id
    record.completed_at = datetime.now(timezone.utc)
    await _change_grade(db, employee, target, leaving=TRAINING, entering=None)
    await db.refresh(employee)
    return _record_out(employee, await _load(db, [employee.id]), TRAINING, None)


async def cancel_completion(employee_id: int, db: AsyncSession) -> InternRecordOut:
    """Annule la fin de formation : l'employé reprend son grade « En formation »."""
    employee = await get_active_employee(db, employee_id)
    record = await db.get(InternRecord, employee.id)
    if record is None or record.completed_at is None or employee_stage(employee) is not None:
        raise HTTPException(status_code=409, detail="Cette fin de formation n’a pas été validée depuis la page Formation.")
    previous = await db.get(Grade, record.completed_from_grade_id) if record.completed_from_grade_id else None
    if previous is None or not previous.is_training:
        previous = (
            await db.execute(select(Grade).where(Grade.is_training.is_(True)).order_by(Grade.level.asc()))
        ).scalars().first()
    if previous is None:
        raise HTTPException(status_code=409, detail="Aucun grade « En formation » : cochez-le dans Direction.")
    record.completed_at = None
    record.completed_from_grade_id = None
    employee.grade = previous
    await _stage_emojis(db, employee, TRAINING, present=True)
    await db.commit()
    await push_employees_changed()
    return await _fiche(db, employee)
