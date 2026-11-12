import re
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import get_settings


class Base(DeclarativeBase):
    pass


def _frequency_value(value: str) -> str:
    return re.sub(r"\s*MHz\s*$", "", value, flags=re.IGNORECASE).strip()


_settings = get_settings()

# SQLAlchemy uses ``postgresql`` as the dialect name.  Accept the legacy
# ``postgres://`` scheme used by some hosted PostgreSQL providers, then select
# the async driver explicitly for this async application.
_database_url = _settings.database_url
if _database_url.startswith("postgres://"):
    _database_url = "postgresql+asyncpg://" + _database_url.removeprefix("postgres://")
elif _database_url.startswith("postgresql://"):
    _database_url = "postgresql+asyncpg://" + _database_url.removeprefix("postgresql://")

engine = create_async_engine(
    _database_url,
    echo=_settings.debug,
    future=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


# Migration statements for columns that may need to be added to existing tables.
# create_all() only creates new tables — for existing tables, we ALTER.
_USER_ALTER_STATEMENTS = [
    "ALTER TABLE users ADD COLUMN phone VARCHAR(20)",
    "ALTER TABLE users ADD COLUMN status VARCHAR(16) DEFAULT 'active' NOT NULL",
    "ALTER TABLE users ADD COLUMN competencies TEXT DEFAULT '[]' NOT NULL",
    "ALTER TABLE users ADD COLUMN is_super_admin BOOLEAN DEFAULT FALSE NOT NULL",
    "ALTER TABLE users ADD COLUMN role_id INTEGER REFERENCES roles(id) ON DELETE SET NULL",
    "ALTER TABLE users ADD COLUMN super_admin_enabled BOOLEAN DEFAULT TRUE NOT NULL",
]

_ROLE_ALTER_STATEMENTS = [
    "ALTER TABLE roles ADD COLUMN permissions TEXT DEFAULT '[]' NOT NULL",
]

_EMPLOYEE_ALTER_STATEMENTS = [
    "ALTER TABLE employees ADD COLUMN grade_id INTEGER REFERENCES grades(id) ON DELETE SET NULL",
    "ALTER TABLE employees ADD COLUMN email VARCHAR(254)",
    "ALTER TABLE employees ADD COLUMN arrival_date DATE",
]

_GRADE_ALTER_STATEMENTS = [
    "ALTER TABLE grades ADD COLUMN color VARCHAR(7) DEFAULT '#46996d' NOT NULL",
    "ALTER TABLE grades ADD COLUMN is_direction BOOLEAN DEFAULT FALSE NOT NULL",
]

_VEHICLE_ALTER_STATEMENTS = [
    "ALTER TABLE vehicles ADD COLUMN model VARCHAR(64)",
]


async def _run_user_migrations(conn) -> None:
    for stmt in _USER_ALTER_STATEMENTS:
        try:
            # A duplicate-column error aborts the surrounding PostgreSQL
            # transaction.  A savepoint lets this migration remain idempotent
            # without poisoning the rest of application startup.
            async with conn.begin_nested():
                await conn.execute(text(stmt))
        except Exception:
            pass  # column already exists

    # Backfill : les lignes existantes ont pu être créées avec NULL sur les
    # colonnes ajoutées après coup (ALTER TABLE + DEFAULT ne s'applique pas).
    for stmt in (
        "UPDATE users SET status = 'active' WHERE status IS NULL OR status = ''",
        "UPDATE users SET competencies = '[]' WHERE competencies IS NULL OR competencies = ''",
        "UPDATE users SET phone = '' WHERE phone IS NULL",
    ):
        try:
            await conn.execute(text(stmt))
        except Exception:
            pass


async def _run_role_migrations(conn) -> None:
    for stmt in _ROLE_ALTER_STATEMENTS:
        try:
            async with conn.begin_nested():
                await conn.execute(text(stmt))
        except Exception:
            pass


async def _run_employee_migrations(conn) -> None:
    for stmt in _EMPLOYEE_ALTER_STATEMENTS:
        try:
            async with conn.begin_nested():
                await conn.execute(text(stmt))
        except Exception:
            pass


async def _run_grade_migrations(conn) -> None:
    for stmt in _GRADE_ALTER_STATEMENTS:
        try:
            async with conn.begin_nested():
                await conn.execute(text(stmt))
        except Exception:
            pass


async def _run_vehicle_migrations(conn) -> None:
    for stmt in _VEHICLE_ALTER_STATEMENTS:
        try:
            async with conn.begin_nested():
                await conn.execute(text(stmt))
        except Exception:
            pass


async def _run_dispatch_migrations(conn) -> None:
    try:
        async with conn.begin_nested():
            await conn.execute(
                text(
                    "ALTER TABLE dispatch_radios ADD COLUMN employee_id INTEGER "
                    "REFERENCES employees(id) ON DELETE SET NULL"
                )
            )
    except Exception:
        pass

    await conn.execute(
        text(
            """
            UPDATE dispatch_slots
            SET status = NULL
            WHERE lower(trim(status)) IN (
                'a_prendre',
                'a prendre'
            )
            OR upper(trim(status)) LIKE '%A PRENDRE%'
            """
        )
    )


async def _run_access_migrations(conn) -> None:
    await conn.execute(
        text(
            """
            UPDATE users
            SET is_super_admin = TRUE
            WHERE id = (
                SELECT id FROM users ORDER BY created_at ASC, id ASC LIMIT 1
            )
            AND NOT EXISTS (SELECT 1 FROM users WHERE is_super_admin = TRUE)
            """
        )
    )


async def _backfill_employees() -> None:
    from models import DispatchAssignment, DispatchRadio, Employee

    async with engine.connect() as conn:
        has_legacy_assignments = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table("dispatch_assignments")
        )

    async with SessionLocal() as session:
        employees = (
            await session.execute(select(Employee).where(Employee.account_user_id.is_not(None)))
        ).scalars().all()
        by_user = {employee.account_user_id: employee for employee in employees}

        if has_legacy_assignments:
            legacy_rows = (
                await session.execute(
                    text(
                        'SELECT slot_id, user_id, "order", created_at '
                        "FROM dispatch_assignments ORDER BY id"
                    )
                )
            ).mappings().all()
            existing = (
                await session.execute(select(DispatchAssignment.employee_id))
            ).scalars().all()
            assigned_employee_ids = set(existing)
            for row in legacy_rows:
                employee = by_user.get(row["user_id"])
                if employee and employee.id not in assigned_employee_ids:
                    created_at = row["created_at"]
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(
                            created_at.replace("Z", "+00:00")
                        )
                    if created_at is None:
                        created_at = datetime.now(timezone.utc)
                    session.add(
                        DispatchAssignment(
                            slot_id=row["slot_id"],
                            employee_id=employee.id,
                            order=row["order"],
                            created_at=created_at,
                        )
                    )
                    assigned_employee_ids.add(employee.id)

        for radio in (await session.execute(select(DispatchRadio))).scalars():
            if radio.employee_id is None and radio.doctor_id in by_user:
                radio.employee_id = by_user[radio.doctor_id].id
        await session.commit()


async def init_db() -> None:
    from models import (
        DispatchAssignment,
        AgendaEvent,
        DispatchRadio,
        DispatchSlot,
        DispatchState,
        DispatchNote,
        Employee,
        Grade,
        ApplicationSetting,
        Role,
        User,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_user_migrations(conn)
        await _run_role_migrations(conn)
        await _run_employee_migrations(conn)
        await _run_grade_migrations(conn)
        await _run_vehicle_migrations(conn)
        await _run_access_migrations(conn)
        await _run_dispatch_migrations(conn)

    await _backfill_employees()

    # Ensure default dispatch state singleton exists
    from sqlalchemy import select

    async with SessionLocal() as session:
        existing = await session.get(DispatchState, 1)
        if not existing:
            session.add(DispatchState(id=1))
            await session.flush()

        for radio in (await session.execute(select(DispatchRadio))).scalars():
            radio.frequency = _frequency_value(radio.frequency)
            radio.common_frequency = _frequency_value(radio.common_frequency)

        state = await session.get(DispatchState, 1)
        if state:
            state.freq_147 = _frequency_value(state.freq_147)
            state.freq_570 = _frequency_value(state.freq_570)

        if await session.get(DispatchNote, 1) is None:
            session.add(DispatchNote(id=1, content=""))

        # Ensure default dispatch slots exist (idempotent bootstrap).
        # Layout mirrors the legacy Google Sheets dispatch.
        default_slots = [
            ("centrale", "Centrale", -100),
            ("hopital", "Hôpital", -90),
            ("astreinte", "Astreinte", -80),
            ("conges", "Congés", -70),
            ("ipt", "IPT", -60),
            ("astreinte-fin", "Astreinte fin de service", -50),
            ("pause", "Pause", -40),
        ]
        for kind, title, order in default_slots:
            found = (
                await session.execute(
                    select(DispatchSlot).where(DispatchSlot.kind == kind)
                )
            ).scalar_one_or_none()
            if not found:
                session.add(
                    DispatchSlot(kind=kind, title=title, order=order)
                )
            else:
                # Normalise l'ordre des lignes créées avant l'introduction
                # de cette table (les anciens ordre -600/-200 … se chevauchent).
                found.order = order
        await session.commit()
