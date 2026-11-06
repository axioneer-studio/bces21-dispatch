from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role_id: Mapped[Optional[int]] = mapped_column(ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    role: Mapped[Optional["Role"]] = relationship(back_populates="users", lazy="selectin")

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


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    pages: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    permissions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    users: Mapped[list["User"]] = relationship(back_populates="role")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    arrival_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    competencies: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    account_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    account_user: Mapped[Optional["User"]] = relationship(lazy="selectin")
    grade_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("grades.id", ondelete="SET NULL"), nullable=True, index=True
    )
    grade: Mapped[Optional["Grade"]] = relationship(back_populates="employees", lazy="selectin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    assignments: Mapped[list["DispatchAssignment"]] = relationship(back_populates="employee")


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(7), default="#46996d", nullable=False)
    permissions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    employees: Mapped[list["Employee"]] = relationship(back_populates="grade")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class ApplicationSetting(Base):
    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
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
    __tablename__ = "dispatch_employee_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("dispatch_slots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("employee_id", name="uq_dispatch_employee_assignments_employee"),
    )

    slot: Mapped["DispatchSlot"] = relationship("DispatchSlot", back_populates="assignments")
    employee: Mapped["Employee"] = relationship("Employee", back_populates="assignments")


class DispatchRadio(Base):
    __tablename__ = "dispatch_radios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    serial: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    doctor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    employee_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
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


class DispatchNote(Base):
    __tablename__ = "dispatch_notes"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class AgendaEvent(Base):
    """Shared calendar item, deliberately independent from dispatch slots."""

    __tablename__ = "agenda_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(16), default="#46996d", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
