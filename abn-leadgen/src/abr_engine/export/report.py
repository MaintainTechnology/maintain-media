"""Private static review artifacts. Inputs must be server-gated projections, never raw DB dumps."""

from __future__ import annotations

import csv
import html
import io
from pathlib import Path
from typing import Literal
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class ReportRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    row_id: UUID
    worklist_id: UUID
    lead_id: UUID
    group_id: UUID
    row_version: int = Field(ge=1)
    business_name: str
    source: Literal["abr", "qbcc"]
    source_published_at: AwareDatetime | None = None
    signal: Literal["abn_new", "gst_registered", "qbcc_backlog", "qbcc_new", "qbcc_category_changed"]
    tier: Literal["A", "B", "C"]
    score: int = Field(ge=0, le=100)
    channel: Literal["email", "phone"] | None = None
    candidate_endpoint: str | None = None
    export_allowed: bool = False
    gate_checked_at: AwareDatetime | None = None
    gate_expires_at: AwareDatetime | None = None
    policy_version: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    next_action: str = "Review current identity and contact restrictions"
    status: Literal["not_started", "no_usable_contact", "attempted_no_answer", "contacted_not_interested",
                    "contacted_nurture", "meeting_booked", "meeting_held", "disqualified", "do_not_contact_requested"] = "not_started"
    attempts: int = Field(default=0, ge=0, le=100000)
    invitation_state: Literal["invited", "uninvited", "unknown"] = "unknown"
    invitation_evidence_ref: str | None = None
    notes: str = Field(default="", max_length=2000)
    occurred_at: AwareDatetime | None = None
    opener: str = "Review current permission and business evidence before preparing an opener."

    @model_validator(mode="after")
    def invitation_evidence(self):
        if self.invitation_state == "invited" and not self.invitation_evidence_ref:
            raise ValueError("Invited state needs recorded evidence")
        return self


class ReportContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: UUID
    generated_at: AwareDatetime
    mode: Literal["fixture", "pilot", "production"] = "fixture"
    authorised_operator: bool = False
    rows: list[ReportRow] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def unique_rows(self):
        for name in ("row_id", "group_id"):
            values = [getattr(row, name) for row in self.rows]
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {name}")
        return self


SIGNALS = {
    "abn_new": "Active ABN first observed between accepted snapshots; business creation date is unknown.",
    "gst_registered": "GST registration first observed between accepted snapshots; actual turnover is unknown.",
    "qbcc_backlog": "QBCC discovery backlog; licence category describes permitted capacity, not actual revenue.",
    "qbcc_new": "First observed in the QBCC source; licence issue date and current demand are unknown.",
    "qbcc_category_changed": "QBCC category change first observed; permitted capacity is not actual revenue.",
}

CSV_FIELDS = (
    "row_id", "worklist_id", "lead_id", "group_id", "row_version", "generated_at", "signal", "tier", "score",
    "business_name", "safe_contact_view", "gate_label", "gate_checked_at", "next_action", "opener", "status",
    "attempts", "invitation_state", "invitation_evidence_ref", "notes", "occurred_at", "save_state",
    "source", "source_age", "source_published_at", "signal_description", "reasons", "gate_expires_at", "policy_version",
)


def safe_rows(context: ReportContext) -> list[dict]:
    """Mask endpoints on missing/stale decisions, including future-dated checks."""
    result = []
    for row in context.rows:
        valid = bool(
            context.authorised_operator and row.export_allowed and row.candidate_endpoint
            and row.channel and row.policy_version and row.gate_checked_at and row.gate_expires_at
            and row.gate_checked_at <= context.generated_at < row.gate_expires_at
        )
        label = ("Email: needs send-time checks" if row.channel == "email"
                 else "Phone: check before calling") if valid else "Do not contact"
        age = "Unknown source age"
        if row.source_published_at:
            seconds = (context.generated_at - row.source_published_at).total_seconds()
            age = f"{int(seconds // 86400)} days old" if seconds >= 0 else "Future source date: needs review"
        # Do not pass even hidden raw endpoint values to templates.
        result.append({
            "row_id": str(row.row_id), "worklist_id": str(row.worklist_id),
            "lead_id": str(row.lead_id), "group_id": str(row.group_id),
            "row_version": row.row_version, "business_name": row.business_name,
            "source": row.source.upper(), "source_age": age,
            "signal": SIGNALS[row.signal], "tier": row.tier, "score": row.score,
            "contact": row.candidate_endpoint if valid else "Masked — contact blocked",
            "gate_label": label, "reasons": ", ".join(row.reason_codes) or (
                "Candidate only; recheck at the actual attempt" if valid else "Current export authority missing"),
            "gate_checked_at": row.gate_checked_at.isoformat() if row.gate_checked_at else "Unknown",
            "gate_expires_at": row.gate_expires_at.isoformat() if row.gate_expires_at else "Unknown",
            "policy_version": row.policy_version or "Unknown", "next_action": row.next_action,
            "generated_at": context.generated_at.isoformat(), "signal_code": row.signal,
            "source_published_at": row.source_published_at.isoformat() if row.source_published_at else "",
            "status": row.status, "attempts": row.attempts, "invitation_state": row.invitation_state,
            "invitation_evidence_ref": row.invitation_evidence_ref or "", "notes": row.notes,
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else "", "opener": row.opener,
            "save_state": "Current saved outcome" if row.occurred_at else "Not started; record actual activity date before saving",
        })
    return result


def worklist_rows(context: ReportContext) -> list[dict]:
    """Exact Sheets import columns, including current outcome state and immutable IDs.

    Empty occurred_at means no dated activity has been recorded; generation time is not an
    activity date. CSV readers should preserve UUIDs/versions and parse integer/date cells.
    """
    result = []
    for safe in safe_rows(context):
        values = {**safe, "safe_contact_view": safe["contact"], "signal": safe["signal_code"],
                  "signal_description": safe["signal"]}
        result.append({name: values[name] for name in CSV_FIELDS})
    return result


def _markdown(value: object) -> str:
    value = html.escape(str(value), quote=True).replace("\n", " ").replace("\r", " ")
    for char in ("\\", "`", "*", "_", "[", "]", "|", "#", "!"):
        value = value.replace(char, "\\" + char)
    return value


def _csv_cell(value: object) -> str:
    text = str(value)
    # Prevent formula injection even when a malicious name starts with whitespace.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def render_report(context: ReportContext, output_dir: str | Path) -> dict[str, Path]:
    """Write one immutable run bundle; the caller provides access-controlled private storage.

    This renderer enforces projection/expiry, not database eligibility. Obtain export_allowed
    and its revision-bound evidence from the authoritative export gate immediately beforehand.
    """
    output = Path(output_dir) / str(context.run_id)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    templates = Path(__file__).resolve().parents[3] / "templates"
    env = Environment(loader=FileSystemLoader(templates), undefined=StrictUndefined,
                      autoescape=select_autoescape(default=True))
    env.filters["md"] = _markdown
    rows = safe_rows(context)
    data = {"rows": rows, "run_id": str(context.run_id), "mode": context.mode,
            "generated_at": context.generated_at.isoformat()}
    paths = {"html": output / "report.html", "markdown": output / "report.md", "csv": output / "worklist.csv"}
    paths["html"].write_text(env.get_template("report.html.j2").render(**data), encoding="utf-8")
    # Markdown filter already escapes HTML and Markdown syntax; no double HTML escaping.
    md_env = Environment(loader=FileSystemLoader(templates), undefined=StrictUndefined, autoescape=False)
    md_env.filters["md"] = _markdown
    paths["markdown"].write_text(md_env.get_template("report.md.j2").render(**data), encoding="utf-8")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows({key: _csv_cell(value) for key, value in row.items()} for row in worklist_rows(context))
    paths["csv"].write_text(stream.getvalue(), encoding="utf-8-sig", newline="")
    for path in paths.values():
        path.chmod(0o600)
    return paths
