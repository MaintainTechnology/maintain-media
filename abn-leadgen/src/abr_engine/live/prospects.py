"""Durable manual research, never a qualification or permission-to-contact ledger."""

import json
import re
from datetime import date, timedelta
from time import monotonic
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from abr_engine.compliance.policy import gate_reasons
from abr_engine.control.service import DomainError, json_safe
from abr_engine.db import transaction
from abr_engine.enrich.endpoints import normalize_email, normalize_phone

Presence = Literal["unknown", "present", "absent"]
ContactStage = Literal["not_contacted", "contacted", "interested", "follow_up", "not_interested"]


class ProspectSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    abn: str = Field(pattern=r"^[0-9]{11}$")
    expected_revision: int = Field(ge=0, strict=True)
    source: Literal["abr", "qbcc"]
    run_id: str = "latest"
    snapshot_id: UUID
    business_name: str = Field(default="", max_length=500)
    website_presence: Presence = "unknown"
    email_presence: Presence = "unknown"
    social_presence: Presence = "unknown"
    website_url: str = Field(default="", max_length=2000)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=40)
    social_url: str = Field(default="", max_length=2000)
    evidence_ref: str = Field(default="", max_length=2000)
    research_note: str = Field(default="", max_length=5000)
    contact_stage: ContactStage = "not_contacted"
    follow_up_on: date | None = None
    registration_date: date | None = None
    registration_evidence_ref: str = Field(default="", max_length=2000)

    @field_validator("*", mode="before")
    @classmethod
    def trim(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
                raise ValueError("Invalid control character")
        return value

    @field_validator("website_url", "social_url")
    @classmethod
    def safe_url(cls, value):
        if value:
            parsed = urlsplit(value)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username or parsed.password or any(char.isspace() for char in value)):
                raise ValueError("A public http or https URL is required")
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        return normalize_email(value) if value else value

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value):
        return normalize_phone(value) if value else value

    @field_validator("run_id")
    @classmethod
    def valid_run(cls, value):
        if value != "latest":
            UUID(value)
        return value

    @field_validator("registration_date", "follow_up_on", mode="before")
    @classmethod
    def iso_dates(cls, value):
        if (value is not None and not isinstance(value, date)
                and (not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value))):
            raise ValueError("ISO calendar date required")
        return value

    @model_validator(mode="after")
    def evidence_required(self):
        for channel, endpoint in (("website", self.website_url), ("email", self.email), ("social", self.social_url)):
            if endpoint and getattr(self, channel + "_presence") != "present":
                raise ValueError("A supplied endpoint requires presence to be present")
        if ((any(value != "unknown" for value in (self.website_presence, self.email_presence, self.social_presence))
             or self.phone or self.contact_stage != "not_contacted") and not self.evidence_ref):
            raise ValueError("Presence and contact findings require an evidence reference")
        if bool(self.registration_date) != bool(self.registration_evidence_ref):
            raise ValueError("Original registration date and its evidence must be recorded together")
        if self.contact_stage == "follow_up" and not self.follow_up_on:
            raise ValueError("A follow-up date is required")
        return self


class ProspectFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str | None = Field(default=None, max_length=200)
    website_presence: Presence | None = None
    email_presence: Presence | None = None
    social_presence: Presence | None = None
    contact_stage: ContactStage | None = None
    registration_date_from: date | None = None
    registration_date_to: date | None = None
    follow_up_due: date | None = None

    @field_validator("registration_date_from", "registration_date_to", "follow_up_due", mode="before")
    @classmethod
    def iso_dates(cls, value):
        if (value is not None and not isinstance(value, date)
                and (not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value))):
            raise ValueError("ISO calendar date required")
        return value

    @model_validator(mode="after")
    def dates_ordered(self):
        if (self.registration_date_from and self.registration_date_to
                and self.registration_date_from > self.registration_date_to):
            raise ValueError("Registration date range is reversed")
        return self


class ProspectQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offset: int = Field(default=0, ge=0, le=100_000, strict=True)
    filters: ProspectFilters = Field(default_factory=ProspectFilters)
    abns: list[str] | None = Field(default=None, min_length=1, max_length=50)

    @field_validator("abns")
    @classmethod
    def valid_batch(cls, value):
        if value is not None and (len(set(value)) != len(value)
                                  or any(not re.fullmatch(r"[0-9]{11}", abn) for abn in value)):
            raise ValueError("Provide 1 to 50 unique 11-digit ABNs")
        return value


def _rows_for_abn(conn, service, abn):
    if not re.fullmatch(r"[0-9]{11}", abn):
        raise DomainError("INVALID_INPUT", 422)
    rows = []
    for version, token in service.keys.matches("abn", abn):
        row = conn.execute("SELECT * FROM prospect_research WHERE alias_token=%s AND key_version=%s",
                           (token, version)).fetchone()
        if row:
            rows.append(row)
    if len(rows) > 1:
        raise DomainError("IDENTITY_MERGE_REVIEW_REQUIRED", 409)
    return rows[0] if rows else None


def _restricted(conn, service, row):
    return bool(service.restricted(conn, row["group_id"]))


def _record(service, row):
    return json_safe({**json.loads(service.keys.decrypt(row["payload_encrypted"])),
                      **{key: row[key] for key in ("prospect_id", "source", "snapshot_id", "revision",
                         "website_presence", "email_presence", "social_presence", "contact_stage",
                         "registration_date", "follow_up_on", "saved_at", "expires_at")},
                      "contact_permission": "not_assessed"})


def get_prospect(conn, service, abn, actor):
    service.personal_data_access(conn)
    row = _rows_for_abn(conn, service, abn)
    if row and _restricted(conn, service, row):
        raise DomainError("SUPPRESSED_SOURCE_IDENTITY", 409)
    if row and row["expires_at"] <= service.now(conn):
        raise DomainError("PROSPECT_RESEARCH_EXPIRED", 410)
    if row:
        service.audit(conn, actor, "prospect_research_read", row["prospect_id"])
    return {"prospect": _record(service, row) if row else None}


def query_prospects(conn, service, query, actor):
    service.personal_data_access(conn)
    params = [service.now(conn)]
    clauses = ["expires_at>%s"]
    values = query.filters.model_dump(exclude_none=True)
    search = (values.pop("query", "") or "").strip().casefold()
    identifier = re.sub(r"[\s-]", "", search)
    abn_search = identifier if re.fullmatch(r"[0-9]{11}", identifier) else None
    requested_abns = set(query.abns) if query.abns is not None else None
    lookup_abns = query.abns if query.abns is not None else ([abn_search] if abn_search else None)
    if lookup_abns is not None:
        token_clauses = []
        for abn in lookup_abns:
            for version, token in service.keys.matches("abn", abn):
                token_clauses.append("(alias_token=%s AND key_version=%s)")
                params.extend((token, version))
        clauses.append("(" + " OR ".join(token_clauses) + ")")
    for key, value in values.items():
        if key in {"registration_date_from", "registration_date_to"}:
            clauses.append("registration_date" + (">=%s" if key.endswith("from") else "<=%s"))
        elif key == "follow_up_due":
            clauses.append("follow_up_on<=%s AND contact_stage='follow_up'")
        else:
            clauses.append(key + "=%s")
        params.append(value)
    # Prospect research is a small reviewed work queue, not a full ABR-table scan.
    # Search stays over encrypted payloads; no plaintext name/contact search index.
    total, records, scanned, started = 0, [], 0, monotonic()
    seen_abns = set()
    with conn.cursor(name="prospect_query_" + uuid4().hex) as cursor:
        cursor.itersize = 100
        cursor.execute("SELECT * FROM prospect_research WHERE " + " AND ".join(clauses)
                       + " ORDER BY saved_at DESC,prospect_id", params)
        for row in cursor:
            scanned += 1
            if scanned > 10_000 or monotonic() - started > 5:
                raise DomainError("PROSPECT_QUERY_TOO_BROAD", 422,
                                  {"hint": "Narrow the presence, registration date or follow-up filters"})
            if _restricted(conn, service, row):
                continue
            record = _record(service, row)
            if requested_abns is not None:
                if record["abn"] not in requested_abns:
                    continue
                if record["abn"] in seen_abns:
                    raise DomainError("IDENTITY_MERGE_REVIEW_REQUIRED", 409)
                seen_abns.add(record["abn"])
            if abn_search:
                if record["abn"] != abn_search:
                    continue
            elif search and search not in (record["business_name"] + " " + record["abn"]).casefold():
                continue
            if query.offset <= total < query.offset + 50:
                records.append(record)
            total += 1
    service.audit(conn, actor, "prospect_research_list_read", "prospects", {"offset": query.offset, "count": len(records)})
    return {"records": records, "total": total, "offset": query.offset, "limit": 50,
            "next_offset": query.offset + 50 if query.offset + 50 < total else None}


def verify_source(settings, service, data, actor):
    """Exact ABN membership in the accepted snapshot, before the write transaction."""
    from abr_engine.live.source_records import list_source_records

    result = list_source_records(settings, service, source=data.source, requested_run=data.run_id,
                                 offset=0, actor=actor, filters={"query": data.abn})
    matches = [row for row in result["records"] if row.get("abn") == data.abn]
    if result["snapshot_id"] != str(data.snapshot_id) or not matches:
        raise DomainError("PROSPECT_SOURCE_MISMATCH", 409)
    row = matches[0]
    return {"run_id": result["run_id"] or data.run_id,
            "business_name": row["main_name" if data.source == "abr" else "licensee_name"],
            "state": row.get("state"), "postcode": row.get("postcode")}


def save_prospect(conn, service, data, actor, source_identity=None):
    service.personal_data_access(conn)
    now = service.now(conn)
    reasons = gate_reasons(conn, service.settings, "abr" if data.source == "abr" else "collection", now)
    if reasons:
        raise DomainError(reasons[0], 403, {"reason_codes": reasons})
    if data.registration_date and data.registration_date > now.astimezone(ZoneInfo("Australia/Brisbane")).date():
        raise DomainError("REGISTRATION_DATE_IN_FUTURE", 422)
    prior = _rows_for_abn(conn, service, data.abn)
    if data.expected_revision != (prior["revision"] if prior else 0):
        raise DomainError("REVISION_CONFLICT", 409)
    if prior:
        if _restricted(conn, service, prior):
            raise DomainError("SUPPRESSED_SOURCE_IDENTITY", 409)
        if prior["expires_at"] <= now:
            raise DomainError("PROSPECT_RESEARCH_EXPIRED", 410)
        if prior["source"] != data.source or prior["snapshot_id"] != data.snapshot_id:
            raise DomainError("PROSPECT_SOURCE_MISMATCH", 409)
        prior_record = _record(service, prior)
        source_identity = {key: prior_record[key] for key in ("run_id", "business_name", "state", "postcode")}
        group_id, prospect_id = prior["group_id"], prior["prospect_id"]
    else:
        if not source_identity:
            raise DomainError("PROSPECT_SOURCE_MISMATCH", 409)
        snapshot = conn.execute("SELECT state FROM source_snapshot WHERE snapshot_id=%s AND source=%s",
                                (data.snapshot_id, data.source)).fetchone()
        if not snapshot or snapshot["state"] != "committed":
            raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
        if conn.execute("SELECT 1 FROM artifact_manifest WHERE snapshot_id=%s AND state IN ('deleting','deleted')",
                        (data.snapshot_id,)).fetchone():
            raise DomainError("SOURCE_RECORDS_UNAVAILABLE", 409)
        groups = set()
        for version, token in service.keys.matches("abn", data.abn):
            matched = conn.execute("SELECT group_id FROM suppression_alias WHERE alias_type='abn' AND key_version=%s AND alias_token=%s",
                                   (version, token)).fetchone()
            if matched:
                groups.add(service.canonical_group(conn, matched["group_id"]))
        if len(groups) > 1:
            raise DomainError("IDENTITY_MERGE_REVIEW_REQUIRED", 409)
        group_id, prospect_id = next(iter(groups), uuid4()), uuid4()
        if service.restricted(conn, group_id):
            raise DomainError("SUPPRESSED_SOURCE_IDENTITY", 409)
        conn.execute("INSERT INTO business_group(group_id) VALUES(%s) ON CONFLICT DO NOTHING", (group_id,))
        conn.execute("INSERT INTO suppression_alias(alias_type,key_version,alias_token,group_id) VALUES('abn',%s,%s,%s) ON CONFLICT DO NOTHING",
                     (service.keys.active_version, service.keys.token("abn", data.abn), group_id))
    payload = data.model_dump(mode="json", exclude={"request_id", "expected_revision"})
    payload.update(source_identity)
    encrypted = service.keys.encrypt(json.dumps(payload, sort_keys=True))
    expires = now + timedelta(days=180)
    fields = (encrypted, data.website_presence, data.email_presence, data.social_presence, data.contact_stage,
              data.registration_date, data.follow_up_on, now, expires, actor)
    if prior:
        conn.execute("UPDATE prospect_research SET payload_encrypted=%s,website_presence=%s,email_presence=%s,social_presence=%s,"
                     "contact_stage=%s,registration_date=%s,follow_up_on=%s,saved_at=%s,expires_at=%s,actor_id=%s,revision=revision+1 "
                     "WHERE prospect_id=%s", (*fields, prospect_id))
    else:
        conn.execute("INSERT INTO prospect_research(payload_encrypted,website_presence,email_presence,social_presence,contact_stage,"
                     "registration_date,follow_up_on,saved_at,expires_at,actor_id,prospect_id,group_id,alias_token,key_version,source,snapshot_id,created_at) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                     (*fields, prospect_id, group_id, service.keys.token("abn", data.abn), service.keys.active_version,
                      data.source, data.snapshot_id, now))
    service.audit(conn, actor, "prospect_research_saved", prospect_id, {"revision": data.expected_revision + 1})
    return {"prospect_id": prospect_id, "revision": data.expected_revision + 1, "saved_at": now, "expires_at": expires}


def register_prospect_routes(app, settings, service, actor_for, mutate):
    @app.post("/api/prospects/query")
    def query(body: ProspectQuery, request: Request):
        actor = actor_for(request, ("admin", "reviewer", "compliance"))
        with transaction(settings) as conn:
            return query_prospects(conn, service, body, actor.actor_id)

    @app.get("/api/prospects/{abn}")
    def read(abn: str, request: Request):
        actor = actor_for(request, ("admin", "reviewer", "compliance"))
        with transaction(settings) as conn:
            return get_prospect(conn, service, abn, actor.actor_id)

    @app.post("/v1/prospects")
    def save(body: ProspectSave, request: Request):
        actor = actor_for(request, ("admin", "reviewer"))
        if str(body.request_id) != request.headers.get("idempotency-key"):
            raise DomainError("REQUEST_IDENTIFIERS_REQUIRED", 422)
        identity = None
        with transaction(settings) as conn:
            service.personal_data_access(conn)
            already_saved = _rows_for_abn(conn, service, body.abn)
        if body.expected_revision == 0 and not already_saved:
            identity = verify_source(settings, service, body, actor.actor_id)
        return mutate(request, body.model_dump(), ("admin", "reviewer"),
                      lambda conn, data, actor, key: save_prospect(conn, service, body, actor.actor_id, identity))
