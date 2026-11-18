import json
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


def _frequency_value(value: str | None) -> str | None:
    """Retire un éventuel « MHz » ; une fréquence vide reste vide (affichée « Aucune »)."""
    if value is None:
        return None
    return re.sub(r"\s*MHz\s*$", "", value, flags=re.IGNORECASE).strip() or None


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
    "ALTER TABLE grades ADD COLUMN is_trial BOOLEAN DEFAULT FALSE NOT NULL",
    "ALTER TABLE grades ADD COLUMN is_training BOOLEAN DEFAULT FALSE NOT NULL",
]

_VEHICLE_ALTER_STATEMENTS = [
    "ALTER TABLE vehicles ADD COLUMN model VARCHAR(64)",
]

_MORGUE_ALTER_STATEMENTS = [
    "ALTER TABLE morgue_entries ADD COLUMN coffined_at TIMESTAMP WITH TIME ZONE",
]

_GROUP_ALTER_STATEMENTS = [
    "ALTER TABLE affiliation_groups ADD COLUMN color VARCHAR(7)",
]

_TRAINING_ALTER_STATEMENTS = [
    "ALTER TABLE trainings ADD COLUMN permissions TEXT DEFAULT '[]' NOT NULL",
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
    await _clean_role_pages(conn)
    await _move_user_role_to_user_roles(conn)


async def _move_user_role_to_user_roles(conn) -> None:
    """Reprend l'ancien rôle unique (`users.role_id`) dans `user_roles`, puis le vide
    pour que la reprise ne se refasse pas après un retrait de rôle."""
    try:
        async with conn.begin_nested():
            await conn.execute(
                text(
                    """
                    INSERT INTO user_roles (user_id, role_id)
                    SELECT u.id, u.role_id FROM users u
                    WHERE u.role_id IS NOT NULL
                      AND EXISTS (SELECT 1 FROM roles r WHERE r.id = u.role_id)
                      AND NOT EXISTS (
                          SELECT 1 FROM user_roles ur
                          WHERE ur.user_id = u.id AND ur.role_id = u.role_id
                      )
                    """
                )
            )
            await conn.execute(text("UPDATE users SET role_id = NULL WHERE role_id IS NOT NULL"))
    except Exception:
        pass  # base créée sans la colonne users.role_id


async def _clean_role_pages(conn) -> None:
    """Ne garde dans les rôles que les pages encore à cocher : les pages ouvertes
    à tout compte validé, ou supprimées, feraient refuser l'enregistrement du rôle."""
    from deps import PAGE_KEYS

    rows = (await conn.execute(text("SELECT id, pages FROM roles"))).all()
    for role_id, raw_pages in rows:
        try:
            pages = json.loads(raw_pages)
        except (TypeError, ValueError):
            pages = []
        if not isinstance(pages, list):
            pages = []
        kept = [page for page in pages if page in PAGE_KEYS]
        if kept != pages:
            await conn.execute(
                text("UPDATE roles SET pages = :pages WHERE id = :id"),
                {"pages": json.dumps(kept), "id": role_id},
            )


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


async def _run_morgue_migrations(conn) -> None:
    for stmt in _MORGUE_ALTER_STATEMENTS:
        try:
            async with conn.begin_nested():
                await conn.execute(text(stmt))
        except Exception:
            pass


async def _run_group_migrations(conn) -> None:
    for stmt in _GROUP_ALTER_STATEMENTS:
        try:
            async with conn.begin_nested():
                await conn.execute(text(stmt))
        except Exception:
            pass


async def _run_training_migrations(conn) -> None:
    for stmt in _TRAINING_ALTER_STATEMENTS:
        try:
            async with conn.begin_nested():
                await conn.execute(text(stmt))
        except Exception:
            pass


_DISPATCH_STATE_RENAMES = [
    ("freq_147", "freq_bces"),
    ("freq_570", "freq_shared"),
]

# Chaque instruction échoue sans effet si elle a déjà été appliquée, si la base
# est neuve (create_all crée directement le bon schéma) ou si le moteur ne la
# connaît pas (SQLite n'a pas d'ALTER COLUMN).
_DISPATCH_FREQUENCY_STATEMENTS = [
    # Fréquences actuelles : aucune valeur par défaut, vides tant qu'elles ne sont pas réglées.
    *(f"ALTER TABLE dispatch_state RENAME COLUMN {old} TO {new}" for old, new in _DISPATCH_STATE_RENAMES),
    *(
        f"ALTER TABLE dispatch_state ALTER COLUMN {column} {change}"
        for column in ("freq_bces", "freq_shared")
        for change in ("DROP DEFAULT", "DROP NOT NULL")
    ),
    # La table des radios ne contient que la liste des radios, sans fréquence.
    "ALTER TABLE dispatch_radios DROP COLUMN frequency",
    "ALTER TABLE dispatch_radios DROP COLUMN common_frequency",
]


async def _run_dispatch_migrations(conn) -> None:
    for stmt in _DISPATCH_FREQUENCY_STATEMENTS:
        try:
            async with conn.begin_nested():
                await conn.execute(text(stmt))
        except Exception:
            pass

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


async def _seed_intervention_statuses(conn) -> None:
    """Injecte les statuts d'intervention par défaut quand la table est vide.

    Une base où la colonne `kind` vient d'être ajoutée range ses lieux d'origine
    (BCES, Zombie, salles de l'hôpital…) dans les lieux, une seule fois."""
    from intervention_status_defaults import DEFAULT_INTERVENTION_STATUSES, DEFAULT_PLACES, PLACE_KIND

    try:
        async with conn.begin_nested():
            await conn.execute(
                text("ALTER TABLE intervention_statuses ADD COLUMN kind VARCHAR(16) DEFAULT 'status' NOT NULL")
            )
        kind_added = True
    except Exception:
        kind_added = False
    if kind_added:
        for order, (key, _label, _emoji) in enumerate(DEFAULT_PLACES):
            await conn.execute(
                text('UPDATE intervention_statuses SET kind = :kind, "order" = :order WHERE key = :key'),
                {"kind": PLACE_KIND, "order": order, "key": key},
            )

    if await conn.scalar(text("SELECT COUNT(*) FROM intervention_statuses")):
        return
    orders: dict[str, int] = {}
    rows = []
    for key, label, emoji, is_primo, kind in DEFAULT_INTERVENTION_STATUSES:
        orders[kind] = orders.get(kind, -1) + 1
        rows.append(
            {
                "key": key,
                "label": label,
                "emoji": emoji,
                "is_primo": is_primo,
                "kind": kind,
                "order": orders[kind],
                "created_at": datetime.now(timezone.utc),
            }
        )
    await conn.execute(
        text(
            'INSERT INTO intervention_statuses (key, label, emoji, color, is_primo, kind, "order", created_at) '
            "VALUES (:key, :label, :emoji, NULL, :is_primo, :kind, :order, :created_at)"
        ),
        rows,
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
        await _run_morgue_migrations(conn)
        await _run_group_migrations(conn)
        await _run_training_migrations(conn)
        await _run_access_migrations(conn)
        await _run_dispatch_migrations(conn)
        await _seed_intervention_statuses(conn)

    await _backfill_employees()

    # Ensure default dispatch state singleton exists
    from sqlalchemy import select

    async with SessionLocal() as session:
        existing = await session.get(DispatchState, 1)
        if not existing:
            session.add(DispatchState(id=1))
            await session.flush()

        state = await session.get(DispatchState, 1)
        if state:
            state.freq_bces = _frequency_value(state.freq_bces)
            state.freq_shared = _frequency_value(state.freq_shared)

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
