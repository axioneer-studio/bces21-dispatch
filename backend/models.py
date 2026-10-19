from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    discord_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    discord_username: Mapped[str] = mapped_column(String(64), nullable=False)
    discord_avatar: Mapped[str | None] = mapped_column(String(128), nullable=True)

    prenom_rp: Mapped[str | None] = mapped_column(String(32), nullable=True)
    nom_rp: Mapped[str | None] = mapped_column(String(32), nullable=True)

    rp_name_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_users_rp_deadline", "rp_name_deadline"),
    )