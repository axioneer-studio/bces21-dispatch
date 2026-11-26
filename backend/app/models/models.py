from datetime import UTC, date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    case,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


# Rôles applicatifs d'un compte : il cumule les pages et permissions de chacun.
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


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

    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False, index=True)
    competencies: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Interrupteur du super-admin lui-même (bouton « Superadmin ») : désactivé,
    # il garde son statut mais n'a plus que les accès de ses rôles et de son grade.
    super_admin_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    roles: Mapped[list["Role"]] = relationship(
        secondary=user_roles, back_populates="users", lazy="selectin", order_by="Role.name"
    )

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

    @property
    def has_super_admin_rights(self) -> bool:
        """Super-admin dont les droits sont actifs : à utiliser pour tout contrôle d'accès."""
        return self.is_super_admin and self.super_admin_enabled
    last_login_at: Mapped[datetime | None] = mapped_column(
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
    users: Mapped[list["User"]] = relationship(secondary=user_roles, back_populates="roles")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    arrival_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    competencies: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    account_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    account_user: Mapped[Optional["User"]] = relationship(lazy="selectin")
    grade_id: Mapped[int | None] = mapped_column(
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
    # Les employés de ce grade peuvent recevoir une radio Direction.
    is_direction: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Grades en formation initiale (période d'essai : CDD, Interne) ou en formation
    # complémentaire (CDI, Résident) : leurs employés sont suivis dans les tableaux
    # de la page Formation.
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_training: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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
    title: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    location: Mapped[str | None] = mapped_column(String(64), nullable=True)
    type_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
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
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    is_on: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_loading: Mapped[bool] = mapped_column(default=False, nullable=False)
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
    # Fréquences actuelles : BCES et commune (partagée avec les autres services).
    # Vides tant qu'elles n'ont pas été réglées (Paramètres) ou tirées (Dispatch).
    freq_bces: Mapped[str | None] = mapped_column(String(16), nullable=True)
    freq_shared: Mapped[str | None] = mapped_column(String(16), nullable=True)
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
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(16), default="#46996d", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Vehicle(Base):
    """Véhicule de la flotte, géré dans Administration."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    plate: Mapped[str | None] = mapped_column(String(16), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ParkingSpot(Base):
    """Emplacement de stationnement proposé dans la flotte (liste non exhaustive)."""

    __tablename__ = "parking_spots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class FleetEntry(Base):
    """Ligne de l'encart « Flotte de véhicules » du Dispatch.

    L'emplacement est du texte libre : il peut reprendre un emplacement de
    stationnement ou toute autre valeur saisie par le dispatcheur.
    """

    __tablename__ = "dispatch_fleet_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    location: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    note: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class HospitalRoom(Base):
    """Chambre de l'hôpital, qui contient des lits."""

    __tablename__ = "hospital_rooms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    beds: Mapped[list["HospitalBed"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        order_by="HospitalBed.id",
        lazy="selectin",
    )


class HospitalBed(Base):
    """Lit d'une chambre. Créé vide ; les champs du patient sont remplis à l'affectation."""

    __tablename__ = "hospital_beds"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(
        ForeignKey("hospital_rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room: Mapped["HospitalRoom"] = relationship(back_populates="beds")
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    patient_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    accident: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    arrival_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    care_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Forces de l'ordre : « none » (non concernées), « to_notify » (à prévenir), « notified » (prévenues).
    police_status: Mapped[str] = mapped_column(String(16), default="none", nullable=False)
    reason: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class HospitalBedReason(Base):
    """Raison proposée pour la présence d'un patient dans un lit (liste non exhaustive)."""

    __tablename__ = "hospital_bed_reasons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MorgueEntry(Base):
    """Un défunt pris en charge par la morgue : corps en cellule réfrigérée, puis
    urne s'il est incinéré, ou cercueil s'il y est mis. Les deux sont réservés aux
    médecins légistes, après l'autopsie, et s'excluent l'un l'autre."""

    __tablename__ = "morgue_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    death_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    identity: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    affiliation: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    info_shareable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    autopsy_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    examiner_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    examiner: Mapped[Optional["Employee"]] = relationship(lazy="selectin")
    emergency_contacts: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    recoverable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    incinerated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    coffined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class InterventionStatus(Base):
    """Statut proposé pour une intervention du Dispatch, géré dans Administration.

    `key` est la valeur enregistrée dans `dispatch_slots.status` : elle ne change
    pas quand on renomme le statut. `is_primo` marque les statuts « Primo Inter »,
    liés à la page Crise."""

    __tablename__ = "intervention_statuses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    emoji: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    # Couleur « #rrggbb » de l'intervention ; aucune par défaut.
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    is_primo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # « status » (Patrouille, Inter…) ou « place » (BCES, Zombie…) : les statuts
    # sont toujours proposés avant les lieux ; `order` range chaque type.
    kind: Mapped[str] = mapped_column(String(16), default="status", nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


def intervention_status_order():
    """Tri des statuts d'intervention : les statuts, puis les lieux, chacun dans son ordre."""
    return (
        case((InterventionStatus.kind == "place", 1), else_=0),
        InterventionStatus.order,
        InterventionStatus.id,
    )


class AffiliationGroup(Base):
    """Groupe proposé pour l'appartenance d'un blessé (Crise) ou d'un défunt
    (Morgue). La liste n'est pas exhaustive : on peut saisir un autre groupe."""

    __tablename__ = "affiliation_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # Couleur « #rrggbb » de l'appartenance dans la Crise et la Morgue, ou aucune.
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CrisisState(Base):
    """Ligne unique `id = 1` : code postal de la crise et intervention « Primo » du
    Dispatch où le Primo Intervenant est affecté."""

    __tablename__ = "crisis_state"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    zip_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("dispatch_slots.id", ondelete="SET NULL"), nullable=True
    )


class CrisisMember(Base):
    """Équipe de la crise en cours : le Primo Intervenant et les agents qui l'assistent."""

    __tablename__ = "crisis_members"

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True
    )
    employee: Mapped["Employee"] = relationship(lazy="selectin")
    # Un seul membre est le Primo Intervenant ; les autres l'assistent.
    is_primo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CrisisVictim(Base):
    """Blessé de la crise en cours, renseigné par l'équipe sur place puis suivi
    jusqu'à l'hôpital. La « Tempête » vide la liste."""

    __tablename__ = "crisis_victims"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    affiliation: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    coma: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    severe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unconscious: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    injuries: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    repatriating_doctor: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    treating_doctor: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    # Arrivée à l'hôpital : l'heure est prise au moment où on coche la case.
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    care_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Cases de la Centrale : blessé ajouté au canal radio, et lit où il est installé.
    channel_added: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bed_id: Mapped[int | None] = mapped_column(
        ForeignKey("hospital_beds.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Training(Base):
    """Formation de Pôles & Spé. La valider pour un employé ajoute son emoji aux
    compétences de l'employé : l'emoji est la trace de la validation. L'emoji est
    facultatif : sans emoji, la validation est une ligne « validated » de
    TrainingMember.

    `kind` : « general » (formation de Pôles & Spé, ex. Pilote Medicopter). Les
    périodes d'essai et de formation ont leurs modules (InternModule).
    """

    __tablename__ = "trainings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default="general", nullable=False)
    # Formation générale : « pole » (ex. Pilote Medicopter, Stock, Formateur) ou
    # « specialty » (ex. Médecin légiste). Sans effet sur les autres types.
    category: Mapped[str] = mapped_column(String(16), default="pole", nullable=False)
    # Droits donnés à ceux qui l'ont validée (formation générale), en JSON : voir
    # training_rights.
    permissions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TrainingMember(Base):
    """Rôle d'un employé dans une formation générale, quand ce n'est pas un simple
    « Validé » (qui ne tient qu'à l'emoji dans ses compétences) : « lead »
    (Responsable) et « second » (Second) ont l'emoji, « in_progress » (En cours)
    ne l'a pas encore. Dans une formation sans emoji, un Validé a sa ligne
    « validated »."""

    __tablename__ = "training_members"

    training_id: Mapped[int] = mapped_column(ForeignKey("trainings.id", ondelete="CASCADE"), primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# --- Fiches des Internes (page Formation) ---


class InternModule(Base):
    """Module de la page Formation, rangé par type.

    Période d'essai : « basics » (Validations basiques), « tools » (Gestion des
    outils), « interventions » (Type d'intervention), « injuries » (Blessures),
    notés de 0 à 3. En formation : « mandatory » (formations obligatoires) et
    « optional » (facultatives), notés de 0 à 2. Son emoji, facultatif, rejoint
    les compétences de l'employé au niveau le plus haut. Obligatoire
    (`is_required`) : à valider au plus haut pour le passage, même forcé."""

    __tablename__ = "intern_modules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class InternQuestion(Base):
    """Question du questionnaire de passage Résident, avec la réponse attendue."""

    __tablename__ = "intern_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class InternRecord(Base):
    """Fiche de formation d'un employé, de la période d'essai à la période de
    formation : notes, simulations validantes et passage de grade.

    `simulation` (période d'essai) et `resident_simulation` (en formation) :
    notes de 1 à 5 par critère, en JSON. `resident_at` : passage au grade « En
    formation » depuis la fiche ; `previous_grade_id` : grade d'avant, pour
    pouvoir l'annuler. `completed_at` : fin de formation (passage au grade
    au-dessus) ; `completed_from_grade_id` : grade « En formation » d'avant."""

    __tablename__ = "intern_records"

    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    simulation: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    resident_simulation: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    resident_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    previous_grade_id: Mapped[int | None] = mapped_column(
        ForeignKey("grades.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_from_grade_id: Mapped[int | None] = mapped_column(
        ForeignKey("grades.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class InternMentor(Base):
    """Mentor (un formateur) d'un Interne."""

    __tablename__ = "intern_mentors"

    intern_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)


class InternModuleLevel(Base):
    """Niveau d'un employé sur un module. Période d'essai : 1 Observé,
    2 Pratiqué avec aide, 3 Pratiqué en autonomie. En formation : 1 Pratiqué,
    2 Validé. Sans ligne : Non observé."""

    __tablename__ = "intern_module_levels"

    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("intern_modules.id", ondelete="CASCADE"), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)


class InternAnswer(Base):
    """Bonne réponse d'un Interne à une question (sans ligne : pas la bonne réponse)."""

    __tablename__ = "intern_answers"

    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("intern_questions.id", ondelete="CASCADE"), primary_key=True)
