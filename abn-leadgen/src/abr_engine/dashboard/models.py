"""Closed, deliberately small dashboard configuration and run requests."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Source = Literal["all", "abr", "qbcc"]


class DashboardSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    default_source: Source = "all"
    monthly_cap_micro_aud: int = Field(default=150_000_000, ge=0, le=150_000_000, strict=True)
    mode: Literal["fixture"] = "fixture"


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_source: Source | None = None
    monthly_cap_micro_aud: int | None = Field(default=None, ge=0, le=150_000_000, strict=True)


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    source: Source | None = None
