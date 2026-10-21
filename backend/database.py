import re
from collections.abc import AsyncIterator

from sqlalchemy import text
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

engine = create_async_engine(
    _settings.database_url,
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
]


async def _run_user_migrations(conn) -> None:
    for stmt in _USER_ALTER_STATEMENTS:
        try:
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


async def _run_dispatch_migrations(conn) -> None:
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


async def init_db() -> None:
    from models import (
        DispatchAssignment,
        DispatchRadio,
        DispatchSlot,
        DispatchState,
        User,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_user_migrations(conn)
        await _run_dispatch_migrations(conn)

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