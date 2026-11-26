"""Étapes de la page Formation.

Un employé d'un grade « Période d'essai » est à l'étape « trial », d'un grade
« En formation » à l'étape « training » ; les modules sont rangés par étape
selon leur type.

Emojis : deux pôles ou spécialités n'ont jamais le même, deux modules non plus,
mais un pôle ou une spécialité et un module peuvent l'avoir en commun. L'emoji
d'un module ne compte que pour un employé à l'étape du module ; pour les
autres, c'est celui du pôle ou de la spécialité. Les employés en formation ne
rejoignent ni pôle ni spécialité, et les emojis des modules quittent leurs
compétences au passage à l'étape suivante.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee, InternModule
from app.schemas import InternStage

TRIAL: InternStage = "trial"
TRAINING: InternStage = "training"
TRIAL_CATEGORIES = ("basics", "tools", "interventions", "injuries")
TRAINING_CATEGORIES = ("mandatory", "optional")


def module_stage(module: InternModule) -> InternStage:
    return TRIAL if module.category in TRIAL_CATEGORIES else TRAINING


def employee_stage(employee: Employee) -> InternStage | None:
    grade = employee.grade
    if grade is None:
        return None
    if grade.is_trial:
        return TRIAL
    if grade.is_training:
        return TRAINING
    return None


async def module_emojis_by_stage(db: AsyncSession) -> dict[str, list[str]]:
    """Emojis des modules de chaque étape."""
    by_stage: dict[str, list[str]] = {TRIAL: [], TRAINING: []}
    modules = (
        (await db.execute(select(InternModule).where(InternModule.emoji.is_not(None))))
        .scalars()
        .all()
    )
    for module in modules:
        if module.emoji is not None:
            by_stage[module_stage(module)].append(module.emoji)
    return by_stage
