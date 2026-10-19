import re
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


_NAME_PATTERN = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' \-]+$")


class HealthResponse(BaseModel):
    status: str
    version: str
    timezone: str


class ProfileUpdateRequest(BaseModel):
    prenomRP: str = Field(min_length=2, max_length=120)
    nomRP: str = Field(min_length=2, max_length=120)

    @field_validator("prenomRP", "nomRP")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not _NAME_PATTERN.match(trimmed):
            raise ValueError(
                "Caractères autorisés : lettres, espaces, tirets, apostrophes."
            )
        return trimmed


class UserResponse(BaseModel):
    id: int
    discord_id: str
    discord_username: str
    discord_avatar: str | None
    prenom_rp: str | None
    nom_rp: str | None
    rp_name_deadline: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("rp_name_deadline", "created_at", mode="before")
    @classmethod
    def _ensure_utc(cls, value: object) -> object:
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class AgentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    discord_id: str
    discord_username: str
    discord_avatar: str | None
    prenom_rp: str | None
    nom_rp: str | None

    @property
    def display_name(self) -> str:
        if self.prenom_rp and self.nom_rp:
            return f"{self.prenom_rp} {self.nom_rp}"
        return self.discord_username

    @property
    def series(self) -> str:
        return f"SSS-{self.id:04d}"


class AgentListResponse(BaseModel):
    agents: list[AgentSummary]
    count: int
    generated_at: datetime


class MessageResponse(BaseModel):
    message: str