import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import router as auth_router
from app.config import get_settings
from app.database import get_db, init_db
from app.deps import get_current_user, user_role_pages
from app.models import Employee, Grade, User
from app.routes.administration import router as administration_router
from app.routes.affiliation_groups import router as affiliation_groups_router
from app.routes.agenda import router as agenda_router
from app.routes.agents import router as agents_router
from app.routes.crisis import router as crisis_router
from app.routes.direction import router as direction_router
from app.routes.dispatch import router as dispatch_router
from app.routes.fleet import router as fleet_router
from app.routes.formation import router as formation_router
from app.routes.frequencies import router as frequencies_router
from app.routes.hospital_rooms import router as hospital_rooms_router
from app.routes.human_resources import router as human_resources_router
from app.routes.intervention_statuses import router as intervention_statuses_router
from app.routes.morgue import router as morgue_router
from app.routes.trainings import router as trainings_router
from app.schemas import HealthResponse, SuperAdminToggleRequest, UserResponse
from app.services.app_permissions import user_role_permissions
from app.services.cleanup import cleanup_loop
from app.services.grade_permissions import parse_grade_permissions
from app.services.status_sync import status_sync_loop
from app.services.storm import storm_loop
from app.services.training_rights import user_has_hr_access, user_training_permissions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("bces")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Initialisation de la base de données…")
    await init_db()

    stop_event = asyncio.Event()
    tasks = [
        asyncio.create_task(cleanup_loop(stop_event), name="cleanup"),
        asyncio.create_task(status_sync_loop(stop_event), name="status-sync"),
        asyncio.create_task(storm_loop(stop_event), name="storm"),
    ]
    logger.info(
        "Démarrage de l'API %s v%s (debug=%s)",
        settings.app_name,
        settings.app_version,
        settings.debug,
    )

    try:
        yield
    finally:
        stop_event.set()
        for task in tasks:
            try:
                await asyncio.wait_for(task, timeout=5)
            except TimeoutError:
                task.cancel()


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=dict)
def read_root() -> dict:
    return {"message": settings.app_name, "version": settings.app_version}


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(
        status="ok", version=settings.app_version, timezone=settings.app_timezone
    )


@app.get("/api/me", response_model=UserResponse)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await _me_response(db, user)


@app.patch("/api/me/super-admin", response_model=UserResponse)
async def toggle_own_super_admin(
    payload: SuperAdminToggleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    # Statut réel, pas les droits actifs : un super-admin désactivé doit
    # toujours pouvoir se réactiver.
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Réservé aux super-admins.")
    user.super_admin_enabled = payload.enabled
    await db.commit()
    await db.refresh(user)
    return await _me_response(db, user)


async def _me_response(db: AsyncSession, user: User) -> UserResponse:
    response = UserResponse.model_validate(user)
    grade_permissions = await db.scalar(
        select(Grade.permissions)
        .join(Employee, Employee.grade_id == Grade.id)
        .where(Employee.account_user_id == user.id)
    )
    # Ressources humaines ne se coche pas dans un rôle : elle suit les droits RH.
    page_access = [page for page in user_role_pages(user) if page != "human-resources"]
    if await user_has_hr_access(db, user):
        page_access.append("human-resources")
    return response.model_copy(
        update={
            "role_names": [role.name for role in user.roles],
            "is_super_admin": user.has_super_admin_rights,
            "super_admin_available": user.is_super_admin,
            "super_admin_enabled": user.super_admin_enabled,
            "page_access": page_access,
            "app_permissions": user_role_permissions(user),
            "grade_permissions": parse_grade_permissions(grade_permissions),
            "training_permissions": await user_training_permissions(db, user),
        }
    )


app.include_router(auth_router)
app.include_router(administration_router)
app.include_router(direction_router)
app.include_router(agents_router)
app.include_router(agenda_router)
app.include_router(dispatch_router)
app.include_router(fleet_router)
app.include_router(frequencies_router)
app.include_router(human_resources_router)
app.include_router(hospital_rooms_router)
app.include_router(morgue_router)
app.include_router(crisis_router)
app.include_router(affiliation_groups_router)
app.include_router(intervention_statuses_router)
app.include_router(trainings_router)
app.include_router(formation_router)
