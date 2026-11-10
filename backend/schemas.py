import re
from datetime import date, datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


_NAME_PATTERN = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' \-]+$")
_PHONE_PATTERN = re.compile(r"^[\d\-\+\(\) ]{6,20}$")


class HealthResponse(BaseModel):
    status: str
    version: str
    timezone: str


class ProfileUpdateRequest(BaseModel):
    prenomRP: str = Field(min_length=2, max_length=120)
    nomRP: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=20)

    @field_validator("prenomRP", "nomRP")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not _NAME_PATTERN.match(trimmed):
            raise ValueError(
                "Caractères autorisés : lettres, espaces, tirets, apostrophes."
            )
        return trimmed

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            return ""
        if not _PHONE_PATTERN.match(trimmed):
            raise ValueError("Numéro de téléphone invalide.")
        return trimmed


class UserResponse(BaseModel):
    id: int
    discord_id: str
    discord_username: str
    discord_avatar: Optional[str]
    prenom_rp: Optional[str]
    nom_rp: Optional[str]
    phone: Optional[str]
    status: Optional[str] = "active"
    competencies: list[str]
    rp_name_deadline: Optional[datetime]
    created_at: datetime
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    is_super_admin: bool = False
    page_access: list[str] = Field(default_factory=list)
    app_permissions: list[str] = Field(default_factory=list)
    grade_permissions: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @field_validator("status", mode="before")
    @classmethod
    def _default_status(cls, value):
        return value or "active"

    @field_validator("rp_name_deadline", "created_at", mode="before")
    @classmethod
    def _ensure_utc(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @field_validator("competencies", mode="before")
    @classmethod
    def _parse_competencies(cls, value):
        if isinstance(value, str):
            import json

            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        if isinstance(value, list):
            return value
        return []


class AgentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    discord_id: str
    discord_username: str
    discord_avatar: Optional[str]
    prenom_rp: Optional[str]
    nom_rp: Optional[str]
    phone: Optional[str]
    status: Optional[str] = "active"
    competencies: list[str]

    @field_validator("status", mode="before")
    @classmethod
    def _default_status(cls, value):
        return value or "active"

    @field_validator("competencies", mode="before")
    @classmethod
    def _parse_competencies(cls, value):
        if isinstance(value, str):
            import json

            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        return value if isinstance(value, list) else []


class AgentListResponse(BaseModel):
    agents: list[AgentSummary]
    count: int
    generated_at: datetime


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    phone: Optional[str]
    email: Optional[str] = None
    arrival_date: Optional[date] = None
    competencies: list[str]
    is_active: bool
    account_user_id: Optional[int]
    account_username: Optional[str] = None
    grade_id: Optional[int] = None
    grade_name: Optional[str] = None
    grade_level: Optional[int] = None
    grade_color: Optional[str] = None
    grade_is_direction: bool = False
    grade_permissions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("competencies", mode="before")
    @classmethod
    def _parse_employee_competencies(cls, value):
        if isinstance(value, str):
            import json

            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except (TypeError, ValueError):
                return []
        return value if isinstance(value, list) else []


class EmployeeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=64)
    last_name: str = Field(default="", max_length=64)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=254)
    arrival_date: Optional[date] = None
    competencies: list[str] = Field(default_factory=list, max_length=20)
    grade_id: Optional[int] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _trim_employee_name(cls, value: str, info: ValidationInfo) -> str:
        trimmed = value.strip()
        if not trimmed and info.field_name == "first_name":
            raise ValueError("Le prénom est obligatoire.")
        return trimmed

    @field_validator("competencies")
    @classmethod
    def _clean_competencies(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if any(len(item) > 40 for item in cleaned):
            raise ValueError("Chaque compétence doit faire 40 caractères maximum.")
        return list(dict.fromkeys(cleaned))

    @field_validator("phone")
    @classmethod
    def _validate_employee_phone(cls, value: str | None) -> str | None:
        trimmed = value.strip() if value else ""
        if trimmed and not _PHONE_PATTERN.match(trimmed):
            raise ValueError("Numéro de téléphone invalide.")
        return trimmed or None

    @field_validator("email")
    @classmethod
    def _validate_employee_email(cls, value: str | None) -> str | None:
        trimmed = value.strip() if value else ""
        if not trimmed:
            return None
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", trimmed):
            raise ValueError("Adresse e-mail invalide.")
        return trimmed


class EmployeeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    last_name: Optional[str] = Field(default=None, max_length=64)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=254)
    arrival_date: Optional[date] = None
    competencies: Optional[list[str]] = Field(default=None, max_length=20)
    is_active: Optional[bool] = None
    grade_id: Optional[int] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _trim_updated_employee_name(
        cls, value: str | None, info: ValidationInfo
    ) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed and info.field_name == "first_name":
            raise ValueError("Le prénom ne peut pas être vide.")
        return trimmed

    @field_validator("competencies")
    @classmethod
    def _clean_updated_competencies(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [item.strip() for item in value if item.strip()]
        if any(len(item) > 40 for item in cleaned):
            raise ValueError("Chaque compétence doit faire 40 caractères maximum.")
        return list(dict.fromkeys(cleaned))

    @field_validator("phone")
    @classmethod
    def _validate_updated_employee_phone(cls, value: str | None) -> str | None:
        trimmed = value.strip() if value else ""
        if trimmed and not _PHONE_PATTERN.match(trimmed):
            raise ValueError("Numéro de téléphone invalide.")
        return trimmed or None

    @field_validator("email")
    @classmethod
    def _validate_updated_employee_email(cls, value: str | None) -> str | None:
        trimmed = value.strip() if value else ""
        if not trimmed:
            return None
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", trimmed):
            raise ValueError("Adresse e-mail invalide.")
        return trimmed


class EmployeeAccountLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_user_id: Optional[int]


class RoleOut(BaseModel):
    id: int
    name: str
    pages: list[str]
    permissions: list[str]
    users_count: int


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    pages: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _trim_role_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Le nom du rôle est obligatoire.")
        return trimmed


class RoleUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    pages: Optional[list[str]] = None
    permissions: Optional[list[str]] = None

    @field_validator("name")
    @classmethod
    def _trim_updated_role_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Le nom du rôle est obligatoire.")
        return trimmed


class GradeOut(BaseModel):
    id: int
    name: str
    level: int
    color: str
    permissions: list[str]
    is_direction: bool
    employees_count: int


class GradeOption(BaseModel):
    id: int
    name: str
    level: int
    color: str


class GradeCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    level: int = Field(ge=1)
    color: str = Field(default="#46996d", pattern=r"^#[0-9A-Fa-f]{6}$")
    permissions: list[str] = Field(default_factory=list, max_length=32)
    is_direction: bool = False

    @field_validator("name")
    @classmethod
    def _trim_grade_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Le nom du grade est obligatoire.")
        return trimmed


class GradeUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    level: Optional[int] = Field(default=None, ge=1)
    color: str = Field(default="#46996d", pattern=r"^#[0-9A-Fa-f]{6}$")
    permissions: Optional[list[str]] = Field(default=None, max_length=32)
    is_direction: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def _trim_updated_grade_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Le nom du grade est obligatoire.")
        return trimmed


class UserRoleUpdateRequest(BaseModel):
    role_id: Optional[int] = None


class SuperAdminUpdateRequest(BaseModel):
    is_super_admin: bool


class AdminUserOut(BaseModel):
    id: int
    discord_username: str
    first_name: Optional[str]
    last_name: Optional[str]
    status: str
    role_id: Optional[int]
    role_name: Optional[str]
    is_super_admin: bool
    created_at: datetime


class AdminUserRoleUpdateRequest(BaseModel):
    role_id: Optional[int] = None


class AdminUserStatusUpdateRequest(BaseModel):
    is_active: bool


class ApplicationSettingsOut(BaseModel):
    registration_open: bool


class ApplicationSettingsUpdateRequest(BaseModel):
    registration_open: bool


class PendingUserItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    discord_id: str
    discord_username: str
    discord_avatar: Optional[str]
    prenom_rp: Optional[str]
    nom_rp: Optional[str]
    phone: Optional[str]
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def _ensure_utc(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class PendingListResponse(BaseModel):
    users: list[PendingUserItem]
    count: int


# --- Dispatch schemas ---

class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slot_id: int
    employee_id: int
    order: int
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def _ensure_utc(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: Optional[str]
    status: Optional[str]
    zip_code: Optional[str]
    location: Optional[str]
    type_label: Optional[str]
    order: int
    assignments: list[AssignmentOut] = []
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _ensure_utc(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class SlotCreateRequest(BaseModel):
    kind: str = Field(pattern=r"^(intervention|consultation)$")


class SlotUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=64)
    status: Optional[str] = Field(default=None, max_length=32)
    zip_code: Optional[str] = Field(default=None, max_length=16)
    location: Optional[str] = Field(default=None, max_length=64)
    type_label: Optional[str] = Field(default=None, max_length=32)


class AssignRequest(BaseModel):
    employee_id: int


class RadioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    serial: str
    employee_id: Optional[int]
    is_on: bool
    is_loading: bool
    frequency: str
    common_frequency: str
    is_direction: bool
    order: int
    updated_at: datetime

    @field_validator("updated_at", mode="before")
    @classmethod
    def _ensure_utc(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


def _clean_serial(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("Le numéro de série est obligatoire.")
    return value


def mask_serial(serial: str) -> str:
    """Numéro affiché sur le Dispatch : les 2 premiers caractères, le reste en X."""
    return serial[:2] + "X" * max(len(serial) - 2, 0)


class RadioUpdateRequest(BaseModel):
    """Modifications possibles depuis le Dispatch : porteur et état.

    États : ON (`is_on`), Indisponible (`is_loading` : en service mais
    indisponible à la radio) ou OFF (ni l'un ni l'autre).
    """

    employee_id: Optional[int] = None
    is_on: Optional[bool] = None
    is_loading: Optional[bool] = None


class DirectionRadioOut(BaseModel):
    id: int
    serial: str
    employee_id: Optional[int]
    employee_name: Optional[str]
    is_on: bool
    is_loading: bool
    # Porteur membre de la Direction (selon son grade) : radio Direction.
    is_direction: bool


class DirectionRadioCreateRequest(BaseModel):
    serial: str = Field(min_length=1, max_length=16)

    @field_validator("serial")
    @classmethod
    def _serial(cls, value: str) -> str:
        return _clean_serial(value)


class DirectionRadioUpdateRequest(BaseModel):
    serial: Optional[str] = Field(default=None, max_length=16)

    @field_validator("serial")
    @classmethod
    def _serial(cls, value: Optional[str]) -> Optional[str]:
        return _clean_serial(value)


class StateOut(BaseModel):
    hospital_status: str
    lses_status: str
    safd_status: str
    freq_147: str
    freq_570: str
    radio_codes: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("updated_at", mode="before")
    @classmethod
    def _ensure_utc(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class StateUpdateRequest(BaseModel):
    hospital_status: Optional[str] = Field(default=None, pattern=r"^(ouvert|ferme|nuit)$")
    # lses_status / safd_status : pilotés par le Google Sheet (status_sync.py)
    radio_codes: Optional[str] = Field(default=None, max_length=2000)


class DispatchNoteUpdateRequest(BaseModel):
    content: str = Field(max_length=10000)


# --- Flotte de véhicules ---

def _clean_required(value: Optional[str], label: str) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError(f"{label} est obligatoire.")
    return value


def _clean_plate(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip().upper()
    return value or None


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip() or None


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    plate: Optional[str]
    model: Optional[str] = None


class VehicleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    plate: Optional[str] = Field(default=None, max_length=16)
    model: Optional[str] = Field(default=None, max_length=64)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _clean_required(value, "Le nom du véhicule")

    @field_validator("plate")
    @classmethod
    def _plate(cls, value: Optional[str]) -> Optional[str]:
        return _clean_plate(value)

    @field_validator("model")
    @classmethod
    def _model(cls, value: Optional[str]) -> Optional[str]:
        return _clean_optional(value)


class VehicleUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    plate: Optional[str] = Field(default=None, max_length=16)
    model: Optional[str] = Field(default=None, max_length=64)

    @field_validator("name")
    @classmethod
    def _name(cls, value: Optional[str]) -> Optional[str]:
        return _clean_required(value, "Le nom du véhicule")

    @field_validator("plate")
    @classmethod
    def _plate(cls, value: Optional[str]) -> Optional[str]:
        return _clean_plate(value)

    @field_validator("model")
    @classmethod
    def _model(cls, value: Optional[str]) -> Optional[str]:
        return _clean_optional(value)


class VehicleImportRequest(BaseModel):
    """Liste complète du garage : le catalogue devient exactement cette liste."""

    vehicles: list[VehicleCreateRequest] = Field(max_length=500)


class VehicleImportResult(BaseModel):
    created: int
    updated: int
    deleted: int
    vehicles: list[VehicleOut]


class ParkingSpotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ParkingSpotRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _clean_required(value, "Le nom de l’emplacement")


class FleetEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: Optional[int]
    location: str
    note: str
    order: int


class FleetEntryUpdateRequest(BaseModel):
    vehicle_id: Optional[int] = None
    location: Optional[str] = Field(default=None, max_length=64)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("location", "note")
    @classmethod
    def _strip(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value is not None else None


class DispatchSnapshot(BaseModel):
    slots: list[SlotOut]
    radios: list[RadioOut]
    state: StateOut
    note: str = ""
    fleet: list[FleetEntryOut] = Field(default_factory=list)
    vehicles: list[VehicleOut] = Field(default_factory=list)
    parking_spots: list[ParkingSpotOut] = Field(default_factory=list)


class DispatchResetRequest(BaseModel):
    delete_interventions: bool = False


class MessageResponse(BaseModel):
    message: str


class AgendaEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    starts_at: datetime
    ends_at: Optional[datetime] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    color: str = Field(default="#46996d", pattern=r"^#[0-9A-Fa-f]{6}$")


class AgendaEventUpdate(AgendaEventCreate):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    starts_at: Optional[datetime] = None
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class AgendaEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    starts_at: datetime
    ends_at: Optional[datetime]
    description: Optional[str]
    color: str
    created_at: datetime
    updated_at: datetime
