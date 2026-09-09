"""Closed configuration and offline boundary; fixture credentials are never live secrets."""
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["fixture", "pilot", "production"] = "fixture"
    database_url: str = "postgresql://abr_fixture:abr_fixture@127.0.0.1:55432/abr_fixture"
    output_dir: Path = Path("var")
    schema_name: str = Field(default="public", pattern=r"^(public|abr_test_[a-f0-9]{32})$")
    monthly_cap_micro_aud: int = Field(default=150_000_000, ge=0, le=150_000_000)
    issuer: str = "maintain-media-fixture"
    audience: str = "abr-engine-fixture"
    live_credentials: dict[str, str] = Field(default_factory=dict, repr=False)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    key_file: Path | None = None

    @model_validator(mode="after")
    def enforce_boundary(self):
        db = urlparse(self.database_url)
        if self.mode == "fixture":
            if (db.scheme != "postgresql" or db.hostname not in {"127.0.0.1", "::1"}
                    or db.path != "/abr_fixture" or db.username != "abr_fixture"
                    or db.password != "abr_fixture" or db.query or self.live_credentials
                    or any(self.capabilities.values())):
                raise ValueError("Fixture mode requires the isolated fixture database and no live capabilities")
        elif self.key_file is None or not self.key_file.is_absolute():
            raise ValueError("Live modes require a separately managed absolute key-store path")
        return self


def load_settings(path: Path | None = None, mode: str | None = None) -> Settings:
    from abr_engine.qualify.policy import load_policy

    load_policy()
    data = yaml.safe_load((path or ROOT / "config/fixture.yaml").read_text())
    if mode is not None:
        data["mode"] = mode
    return Settings.model_validate(data)
