import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    user_id: int
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
    user_id: int


class RadioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    serial: str
    doctor_id: Optional[int]
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


class RadioUpdateRequest(BaseModel):
    serial: Optional[str] = Field(default=None, max_length=16)
    doctor_id: Optional[int] = None
    is_on: Optional[bool] = None
    is_loading: Optional[bool] = None


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
    lses_status: Optional[str] = Field(default=None, max_length=16)
    safd_status: Optional[str] = Field(default=None, max_length=16)
    radio_codes: Optional[str] = Field(default=None, max_length=2000)


class DispatchSnapshot(BaseModel):
    slots: list[SlotOut]
    radios: list[RadioOut]
    state: StateOut


class MessageResponse(BaseModel):
    message: str