import json
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents import router as agents_router
from agenda import router as agenda_router
from administration import router as administration_router
from app_permissions import parse_app_permissions
from auth.router import router as auth_router
from cleanup import cleanup_loop
from config import get_settings
from database import get_db, init_db
from deps import get_current_user
from dispatch import router as dispatch_router
from direction import router as direction_router
from fleet import router as fleet_router
from frequencies import router as frequencies_router
from human_resources import router as human_resources_router
from grade_permissions import parse_grade_permissions
from models import Employee, Grade, User
from schemas import HealthResponse, UserResponse
from status_sync import status_sync_loop

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
    cleanup_task = asyncio.create_task(cleanup_loop(stop_event), name="cleanup")
    sync_task = asyncio.create_task(status_sync_loop(stop_event), name="status-sync")
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
        try:
            await asyncio.wait_for(cleanup_task, timeout=5)
        except asyncio.TimeoutError:
            cleanup_task.cancel()
        try:
            await asyncio.wait_for(sync_task, timeout=5)
        except asyncio.TimeoutError:
            sync_task.cancel()


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
    response = UserResponse.model_validate(user)
    try:
        pages = json.loads(user.role.pages) if user.role else []
    except (TypeError, ValueError):
        pages = []
    grade_permissions = await db.scalar(
        select(Grade.permissions)
        .join(Employee, Employee.grade_id == Grade.id)
        .where(Employee.account_user_id == user.id)
    )
    return response.model_copy(
        update={
            "role_name": user.role.name if user.role else None,
            "is_super_admin": user.is_super_admin,
            "page_access": pages if isinstance(pages, list) else [],
            "app_permissions": parse_app_permissions(
                user.role.permissions if user.role else None
            ),
            "grade_permissions": parse_grade_permissions(grade_permissions),
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
