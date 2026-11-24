"""Seuils du passage de grade de la page Formation, réglés sur les fiches.

Chaque barre de progression (en %) et la note de l'étape (sur 20) ont un seuil
à atteindre pour passer sans forcer. Ce sont des paramètres de l'application
(table `application_settings`). Tant qu'un seuil n'est pas réglé, il garde sa
valeur par défaut, qui reprend la feuille de suivi :
- période d'essai : tous les modules en autonomie et une moyenne de 14 ;
- période de formation : toutes les formations obligatoires validées et une
  simulation de 14.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApplicationSetting
from app.schemas import InternThresholdsOut, InternThresholdsUpdate

DEFAULT_THRESHOLDS = InternThresholdsOut(
    basics=0,
    tools=0,
    interventions=0,
    injuries=0,
    overall=100,
    average=14,
    mandatory=100,
    optional=0,
    resident_simulation=14,
)

_PREFIX = "formation_threshold_"


async def read_thresholds(db: AsyncSession) -> InternThresholdsOut:
    values = DEFAULT_THRESHOLDS.model_dump()
    settings = (
        await db.execute(select(ApplicationSetting).where(ApplicationSetting.key.startswith(_PREFIX)))
    ).scalars().all()
    for setting in settings:
        key = setting.key.removeprefix(_PREFIX)
        if key not in values:
            continue
        try:
            values[key] = type(values[key])(float(setting.value))
        except ValueError:
            continue
    return InternThresholdsOut(**values)


async def write_thresholds(db: AsyncSession, payload: InternThresholdsUpdate) -> None:
    for key, value in payload.model_dump(exclude_none=True).items():
        setting = await db.get(ApplicationSetting, _PREFIX + key)
        if setting is None:
            db.add(ApplicationSetting(key=_PREFIX + key, value=str(value)))
        else:
            setting.value = str(value)
