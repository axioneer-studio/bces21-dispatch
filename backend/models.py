from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    discord_avatar: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    prenom_rp: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    nom_rp: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False, index=True)
    competencies: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    rp_name_deadline: Mapped[Optional[datetime]] = mapped_column(
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
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_users_rp_deadline", "rp_name_deadline"),
    )


class DispatchSlot(Base):
    __tablename__ = "dispatch_slots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    zip_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    type_label: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    assignments: Mapped[list["DispatchAssignment"]] = relationship(
        "DispatchAssignment",
        cascade="all, delete-orphan",
        order_by="DispatchAssignment.order",
        lazy="selectin",
    )


class DispatchAssignment(Base):
    __tablename__ = "dispatch_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("dispatch_slots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    slot: Mapped["DispatchSlot"] = relationship("DispatchSlot", back_populates="assignments")


class DispatchRadio(Base):
    __tablename__ = "dispatch_radios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    serial: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    doctor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_on: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_loading: Mapped[bool] = mapped_column(default=False, nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), default="147", nullable=False)
    common_frequency: Mapped[str] = mapped_column(
        String(16), default="570", nullable=False
    )
    is_direction: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class DispatchState(Base):
    __tablename__ = "dispatch_state"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    hospital_status: Mapped[str] = mapped_column(
        String(16), default="ouvert", nullable=False
    )
    lses_status: Mapped[str] = mapped_column(
        String(16), default="ferme", nullable=False
    )
    safd_status: Mapped[str] = mapped_column(
        String(16), default="disponible", nullable=False
    )
    freq_147: Mapped[str] = mapped_column(
        String(16), default="147", nullable=False
    )
    freq_570: Mapped[str] = mapped_column(
        String(16), default="570", nullable=False
    )
    radio_codes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )