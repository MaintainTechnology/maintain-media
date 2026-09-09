"""Closed v1 API inputs; callers cannot inject approval or actor flags."""
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Suppression(Input):
    lead_id: UUID | None = None
    endpoint: str | None = Field(default=None, max_length=254)
    channel: Literal["email", "phone", "mobile", "landline"] | None = None
    reason: Literal["unsubscribe", "complaint", "no_unsolicited_notice", "cancellation", "manual"]
    source: str = Field(min_length=1, max_length=100)
    requested_at: AwareDatetime
    operator_note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def target(self):
        if not self.lead_id and not self.endpoint or self.endpoint and not self.channel:
            raise ValueError("Target and channel required")
        return self


class Identity(Input):
    lead_id: UUID
    registrable_domain: str = Field(min_length=3, max_length=253)
    expected_revision: int = Field(ge=1)
    assessment: Literal["approved", "rejected", "ambiguous"]
    method: Literal["exact_identifier", "reviewed_attributes"]
    evidence_refs: dict
    reason: str = Field(min_length=1, max_length=2000)


class Merge(Input):
    source_lead_id: UUID
    target_lead_id: UUID
    source_revision: int = Field(ge=1)
    target_revision: int = Field(ge=1)
    evidence_refs: list[str] = Field(min_length=2, max_length=10)
    reason: str = Field(min_length=1, max_length=2000)


class Licence(Input):
    lead_id: UUID
    licence_number: str = Field(min_length=1, max_length=40)
    status: Literal["active", "suspended", "cancelled", "unknown"]
    identity_match: bool
    evidence_ref: str = Field(min_length=1, max_length=500)
    reviewed_at: AwareDatetime


class Basis(Input):
    contact_id: UUID
    channel: Literal["email"]
    expected_revision: int = Field(ge=1)
    basis_type: Literal["inferred", "express", "none"]
    assessment_state: Literal["pass", "fail", "unknown", "withdrawn"]
    limbs: dict[str, Literal["pass", "fail", "unknown"]] | None = None
    express_scope: str | None = Field(default=None, max_length=2000)
    express_evidence: dict | None = None
    evidence_provenance_id: UUID
    reason: str = Field(min_length=1, max_length=2000)


class Relevance(Input):
    contact_id: UUID
    channel: Literal["email"]
    campaign_id: str = Field(min_length=1, max_length=100)
    template_id: str = Field(min_length=1, max_length=100)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_version: str = Field(min_length=1, max_length=100)
    state: Literal["pass", "fail", "unknown"]
    role_evidence_id: UUID
    reason: str = Field(min_length=1, max_length=2000)
    expected_contact_revision: int = Field(ge=1)


class Action(Input):
    lead_id: UUID
    contact_id: UUID
    channel: Literal["email", "phone"]
    campaign_id: str = Field(min_length=1, max_length=100)
    template_id: str = Field(min_length=1, max_length=100)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    relevance_assessment_id: UUID | None = None
    script_policy_version: str | None = Field(default=None, max_length=100)
    expected_contact_revision: int = Field(ge=1)
    recipient_timezone: str | None = Field(default=None, max_length=100)


class Consume(Input):
    dispatch_id: UUID
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Outcome(Input):
    expected_version: int = Field(ge=1)
    status: Literal["not_started", "no_usable_contact", "attempted_no_answer", "contacted_not_interested",
                    "contacted_nurture", "meeting_booked", "meeting_held", "disqualified", "do_not_contact_requested"]
    attempts: int = Field(ge=0, le=100000)
    invitation_state: Literal["invited", "uninvited", "unknown"]
    invitation_evidence_ref: str | None = Field(default=None, max_length=500)
    notes: str = Field(default="", max_length=2000)
    occurred_at: AwareDatetime

    @model_validator(mode="after")
    def evidence(self):
        if self.invitation_state == "invited" and not self.invitation_evidence_ref:
            raise ValueError("Invitation evidence required")
        return self


class Approval(Input):
    row_id: UUID
    expected_version: int = Field(ge=1)
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=1, max_length=2000)


class Activity(Input):
    activity_id: UUID
    worklist_id: UUID
    lead_id: UUID | None = None
    category: Literal["calling", "research", "wash", "review", "admin"]
    started_at: AwareDatetime
    ended_at: AwareDatetime
    correction_of: UUID | None = None

    @model_validator(mode="after")
    def duration(self):
        seconds = (self.ended_at - self.started_at).total_seconds()
        if not 0 <= seconds <= 86400:
            raise ValueError("Invalid work interval")
        return self


class ActionResult(Input):
    decision_id: UUID
    dispatch_id: UUID
    state: Literal["sent", "failed", "cancelled", "uncertain"]
    provider_ref: str | None = Field(default=None, max_length=200)
    occurred_at: AwareDatetime


class Deletion(Input):
    lead_id: UUID
    reason: str = Field(min_length=1, max_length=1000)
    requested_at: AwareDatetime
    retain_suppression: Literal[True]


class Resolution(Input):
    lead_id: UUID
    cancellation_event_id: UUID
    positive_reactivation_evidence_ref: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=2000)
