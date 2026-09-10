"""Version-bound human approval and durable, account-bound CRM reconciliation."""
import copy
import json
import re
from datetime import timedelta
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import urlparse
from uuid import uuid4

import yaml
from psycopg.types.json import Jsonb

from abr_engine.config import ROOT
from abr_engine.control.service import DomainError, digest, json_safe
from abr_engine.db import transaction

MAPPED_FIELDS = {"abn", "signal", "score", "tier", "industry", "entity_class", "state", "website", "positioning_notes", "basis_summary"}


def load_field_mapping(path: Path | None = None) -> dict:
    """Validate the actual fixture adapter mapping; live IDs require separate G5 certification."""
    mapping = yaml.safe_load((path or ROOT / "integrations/crm_fields.yaml").read_text(encoding="utf-8"))
    if not isinstance(mapping, dict) or mapping.get("schema_version") != 1 or mapping.get("mode") != "fixture" or mapping.get("live_enabled") is not False:
        raise DomainError("CRM_MAPPING_NOT_CERTIFIED", 409)
    fields = mapping.get("fields")
    identity = mapping.get("identity", {})
    tags = mapping.get("tags", {})
    if (not isinstance(fields, dict) or set(fields) != MAPPED_FIELDS or not mapping.get("mapping_version")
            or identity.get("key") != "group_id" or identity.get("type") != "uuid"
            or identity.get("prohibit_endpoint_only_merge") is not True
            or tags.get("owned_prefix") != "maintain-media:" or tags.get("replace_all") is not False
            or set(tags.get("operations", [])) != {"add", "remove"} or mapping.get("campaign_enrolment") is not False):
        raise DomainError("CRM_MAPPING_INVALID", 409)
    ids = [identity.get("custom_field_id")]
    for field in fields.values():
        if not isinstance(field, dict) or field.get("type") not in {"string", "number"} or type(field.get("nullable")) is not bool:
            raise DomainError("CRM_MAPPING_INVALID", 409)
        ids.append(field.get("custom_field_id"))
    if any(not isinstance(field_id, str) or not field_id.startswith("fixture_") for field_id in ids) or len(ids) != len(set(ids)):
        raise DomainError("CRM_MAPPING_IDS_INVALID", 409)
    if not tags.get("allowed") or any(not isinstance(tag, str) or not tag.startswith("maintain-media:") for tag in tags["allowed"]):
        raise DomainError("CRM_MAPPING_TAGS_INVALID", 409)
    return mapping


def mapped_fields(values: dict, mapping: dict) -> list[dict]:
    if set(values) != MAPPED_FIELDS:
        raise DomainError("CRM_FIELDS_INCOMPLETE", 409)
    custom = []
    for name in sorted(mapping["fields"]):
        spec = mapping["fields"][name]
        value = values[name]
        if value is None:
            if not spec["nullable"]:
                raise DomainError("CRM_REQUIRED_FIELD_MISSING", 409)
        elif spec["type"] == "number":
            if type(value) is not int or value < spec.get("minimum", value) or value > spec.get("maximum", value):
                raise DomainError("CRM_FIELD_TYPE_OR_RANGE", 409)
        elif not isinstance(value, str):
            raise DomainError("CRM_FIELD_TYPE_OR_RANGE", 409)
        elif (("enum" in spec and value not in spec["enum"])
                or ("max_length" in spec and len(value) > spec["max_length"])
                or ("pattern" in spec and re.fullmatch(spec["pattern"], value) is None)):
            raise DomainError("CRM_FIELD_VALUE_INVALID", 409)
        if value is not None and spec.get("format") == "uri":
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise DomainError("CRM_WEBSITE_INVALID", 409)
        custom.append({"id": spec["custom_field_id"], "value": value})
    return custom


def validate_projection_mapping(payload: dict, mapping: dict) -> None:
    if payload.get("custom_field_map_version") != mapping["mapping_version"]:
        raise DomainError("CRM_MAPPING_REVISION_CHANGED", 409)
    custom = mapped_fields({key: payload.get(key) for key in MAPPED_FIELDS}, mapping)
    custom.append({"id": mapping["identity"]["custom_field_id"], "value": payload["group_id"]})
    if payload.get("custom_fields") != custom or not set(payload.get("tags", [])).issubset(mapping["tags"]["allowed"]):
        raise DomainError("CRM_PROJECTION_MAPPING_MISMATCH", 409)


class CRMProvider(Protocol):
    """Adapters enforce bounded I/O deadlines. No method runs under a database lock.

    fetch returns the remote group identity and current field projection. Production adapters
    must implement engine-owned field/tag add/remove operations, never replace unrelated tags.
    """
    def find_group(self, group_id: str) -> list[str]: ...
    def fetch(self, remote_id: str) -> dict: ...
    def create(self, group_id: str, payload: dict, request_id: str) -> str: ...
    def update(self, remote_id: str, payload: dict, request_id: str) -> None: ...


class MockCRM:
    def __init__(self):
        self.records: dict[str, dict] = {}
        self.timeout_after_create = False
        self.calls = 0

    def find_group(self, group_id):
        return [key for key, value in self.records.items() if value["group_id"] == group_id]

    def fetch(self, remote_id):
        return copy.deepcopy(self.records[remote_id])

    def create(self, group_id, payload, request_id):
        self.calls += 1
        remote_id = "fixture-" + request_id
        self.records[remote_id] = {"group_id": group_id, "payload": copy.deepcopy(payload)}
        if self.timeout_after_create:
            self.timeout_after_create = False
            raise TimeoutError("Synthetic uncertain create")
        return remote_id

    def update(self, remote_id, payload, request_id):
        self.calls += 1
        old = self.records[remote_id]["payload"]
        unrelated = [tag for tag in old.get("tags", []) if not tag.startswith("maintain-media:")]
        old.update(copy.deepcopy(payload))
        old["tags"] = sorted(set(unrelated + payload.get("tags", [])))


def projection(conn, service, row) -> tuple[dict, dict]:
    from abr_engine.export.live_contract import selected_mapping
    mapping = selected_mapping(conn, service)
    lead = service.lead(conn, row["lead_id"])
    group_id = service.canonical_group(conn, lead["group_id"])
    family = service.group_family(conn, group_id)
    contacts = conn.execute("SELECT contact_id FROM contact_record WHERE lead_id=%s ORDER BY channel,contact_id", (lead["lead_id"],)).fetchall()
    for item in contacts:
        gate = service.gate(conn, item["contact_id"])
        if gate["allowed"]:
            contact = service.contact(conn, item["contact_id"])
            aliases = conn.execute("SELECT encrypted_identifier FROM lead_source_link WHERE group_id=ANY(%s) AND source_type='abn'", (family,)).fetchall()
            abns = {service.keys.decrypt(alias["encrypted_identifier"]) for alias in aliases}
            if len(abns) > 1:
                raise DomainError("CRM_ABN_IDENTITY_AMBIGUOUS", 409)
            basis = conn.execute("SELECT basis_type FROM contact_basis WHERE contact_id=%s ORDER BY assessment_seq DESC LIMIT 1", (contact["contact_id"],)).fetchone()
            fields = {"abn": next(iter(abns), None), "signal": row["selected_signal"], "score": lead["score"],
                      "tier": row["selected_tier"], "industry": lead["fields"].get("industry"),
                      "entity_class": lead["fields"].get("entity_class"), "state": lead["state"],
                      "website": lead["fields"].get("website"), "positioning_notes": lead["fields"].get("positioning_notes"),
                      "basis_summary": f"Current {basis['basis_type']} basis; action-time checks required" if basis else None}
            payload = {"group_id": str(group_id), "business_name": lead["display_name"],
                       "contact_id": str(contact["contact_id"]), "endpoint": service.keys.decrypt(contact["encrypted_value"]),
                       "channel": gate["channel"], **fields, "tags": ["maintain-media:candidate"],
                       "custom_field_map_version": mapping["mapping_version"],
                       "custom_fields": mapped_fields(fields, mapping) + [
                           {"id": mapping["identity"]["custom_field_id"], "value": str(group_id)}]}
            validate_projection_mapping(payload, mapping)
            return payload, gate["versions"]
    raise DomainError("NO_ELIGIBLE_CONTACT", 409)


def approve(conn, service, data, actor):
    service.authority(conn)
    row = conn.execute("SELECT * FROM worklist_row WHERE row_id=%s FOR UPDATE", (data["row_id"],)).fetchone()
    if not row:
        raise DomainError("NOT_FOUND", 404)
    if row["version"] != data["expected_version"]:
        raise DomainError("REVISION_CONFLICT", 409)
    if data["decision"] == "reject":
        conn.execute("UPDATE worklist_row SET approval_state='rejected' WHERE row_id=%s", (row["row_id"],))
        return {"state": "rejected"}
    if row["selected_tier"] != "A":
        raise DomainError("ONLY_SELECTED_TIER_A", 409)
    payload, versions = projection(conn, service, row)
    from abr_engine.export.live_contract import selected_mapping
    mapping = selected_mapping(conn, service)
    location = "fixture" if service.settings.mode == "fixture" else mapping["location_id"]
    outbox_id = uuid4()
    outbox = conn.execute("INSERT INTO crm_outbox(outbox_id,row_id,location_id,lead_id,approved_version,actor_id,payload_digest,versions,state,desired_payload_encrypted) "
                          "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s) "
                          "ON CONFLICT(location_id,row_id,approved_version) DO UPDATE SET actor_id=crm_outbox.actor_id RETURNING *",
                          (outbox_id, row["row_id"], location, row["lead_id"], row["version"], actor, digest(payload), Jsonb(json_safe(versions)),
                           service.keys.encrypt(json.dumps(payload, sort_keys=True)))).fetchone()
    conn.execute("UPDATE worklist_row SET approval_state='approved' WHERE row_id=%s", (row["row_id"],))
    service.audit(conn, actor, "crm_approved", outbox["outbox_id"])
    return {"approval_id": outbox["outbox_id"], "outbox_id": outbox["outbox_id"], "state": outbox["state"]}


def _current(conn, service, row, desired) -> bool:
    from abr_engine.export.live_contract import selected_mapping
    try:
        mapping = selected_mapping(conn, service)
    except DomainError:
        return False
    if row["location_id"] != ("fixture" if service.settings.mode == "fixture" else mapping["location_id"]):
        return False
    work = conn.execute("SELECT * FROM worklist_row WHERE row_id=%s", (row["row_id"],)).fetchone()
    if not work or work["approval_state"] != "approved" or work["version"] != row["approved_version"]:
        return False
    try:
        payload, versions = projection(conn, service, work)
    except DomainError:
        return False
    return digest(payload) == digest(desired) == row["payload_digest"] and json_safe(versions) == row["versions"]


def _remote_matches(remote, desired) -> bool:
    if remote.get("group_id") != desired["group_id"]:
        raise DomainError("CRM_REMOTE_IDENTITY_CONFLICT", 409)
    if "provider_dnd" in remote and remote["provider_dnd"] is not True:
        return False
    fields = remote.get("payload", {})
    for key, value in desired.items():
        if key == "tags":
            owned = sorted(tag for tag in fields.get("tags", []) if tag.startswith("maintain-media:"))
            if owned != sorted(value):
                return False
        elif fields.get(key) != value:
            return False
    return True


def _claim(settings, service, outbox_id):
    with transaction(settings) as conn:
        service.authority(conn)
        row = conn.execute("SELECT * FROM crm_outbox WHERE outbox_id=%s FOR UPDATE", (outbox_id,)).fetchone()
        if not row:
            raise DomainError("NOT_FOUND", 404)
        now = service.now(conn)
        prior_write = row["operation_kind"] in {"create", "update"}
        if row["state"] in {"succeeded", "dead_letter"} or (row["state"] == "blocked" and not prior_write):
            return None, row["state"]
        if row["lease_owner"] and row["lease_until"] > now:
            return None, "inflight"
        if row["next_attempt_at"] and row["next_attempt_at"] > now:
            return None, row["state"]
        if row["attempts"] >= 5:
            conn.execute("UPDATE crm_outbox SET state='dead_letter',lease_owner=NULL,lease_until=NULL WHERE outbox_id=%s", (outbox_id,))
            service.audit(conn, "crm-worker", "crm_dead_letter", outbox_id)
            return None, "dead_letter"
        desired = json.loads(service.keys.decrypt(row["desired_payload_encrypted"])) if row["desired_payload_encrypted"] else None
        current = desired is not None and row["state"] != "blocked" and _current(conn, service, row, desired)
        if desired is None or (not current and not prior_write):
            conn.execute("UPDATE crm_outbox SET state='blocked' WHERE outbox_id=%s", (outbox_id,))
            return None, "blocked"
        owner = uuid4()
        conn.execute("UPDATE crm_outbox SET state='inflight',attempts=attempts+1,operation_kind=COALESCE(operation_kind,'lookup'),lease_owner=%s,lease_until=%s WHERE outbox_id=%s",
                     (owner, now + timedelta(seconds=120), outbox_id))
        return {**row, "owner": owner, "desired": desired, "reconcile_only": not current}, "inflight"


def _dispatch(settings, service, claim, operation, remote_id):
    """Persist exact pending operation and recheck authority immediately before external write."""
    with transaction(settings) as conn:
        from abr_engine.export.live_contract import selected_mapping
        validate_projection_mapping(claim["desired"], selected_mapping(conn, service))
        service.authority(conn)
        row = conn.execute("SELECT * FROM crm_outbox WHERE outbox_id=%s FOR UPDATE", (claim["outbox_id"],)).fetchone()
        if row is None:
            return False
        now = service.now(conn)
        if row["lease_owner"] != claim["owner"] or not row["lease_until"] or row["lease_until"] <= now:
            return False
        if row["state"] != "inflight" or not _current(conn, service, row, claim["desired"]):
            conn.execute("UPDATE crm_outbox SET state='blocked',lease_owner=NULL,lease_until=NULL WHERE outbox_id=%s", (row["outbox_id"],))
            return False
        if remote_id:
            conflict = conn.execute("SELECT group_id FROM crm_identity WHERE location_id=%s AND remote_id=%s", (row["location_id"], remote_id)).fetchone()
            if conflict and str(conflict["group_id"]) != claim["desired"]["group_id"]:
                raise DomainError("CRM_REMOTE_IDENTITY_CONFLICT", 409)
        conn.execute("UPDATE crm_outbox SET operation_kind=%s,remote_id=%s,dispatched_at=%s WHERE outbox_id=%s",
                     (operation, remote_id, now, row["outbox_id"]))
    return True


def _finish(settings, service, claim, state, remote_id=None, *, dispatched=False, retry_after=0):
    with transaction(settings) as conn:
        service.authority(conn)
        row = conn.execute("SELECT * FROM crm_outbox WHERE outbox_id=%s FOR UPDATE", (claim["outbox_id"],)).fetchone()
        if row is None:
            return {"outbox_id": claim["outbox_id"], "state": "blocked", "reason": "outbox_missing"}
        now = service.now(conn)
        current = row["state"] != "blocked" and _current(conn, service, row, claim["desired"])
        # A write may already be in flight when suppression/revocation commits. Add a NEW
        # follow-up even if an earlier propagation job finished before the remote write.
        if not current and dispatched:
            conn.execute("INSERT INTO propagation_outbox(outbox_id,group_id,reason) VALUES(%s,%s,'crm_inflight_authority_changed')",
                         (uuid4(), claim["desired"]["group_id"]))
            service.audit(conn, "crm-worker", "crm_inflight_authority_changed", row["outbox_id"])
        if row["lease_owner"] != claim["owner"] or not row["lease_until"] or row["lease_until"] <= now:
            return {"outbox_id": row["outbox_id"], "state": row["state"], "lease_lost": True}
        if not current:
            state = "blocked"
        elif state in {"retry", "uncertain"} and row["attempts"] >= 5:
            state = "dead_letter"
        if state == "succeeded":
            conflict = conn.execute("SELECT group_id FROM crm_identity WHERE location_id=%s AND remote_id=%s", (row["location_id"], remote_id)).fetchone()
            if conflict and str(conflict["group_id"]) != claim["desired"]["group_id"]:
                state = "blocked"
            else:
                conn.execute("INSERT INTO crm_identity(location_id,group_id,remote_id) VALUES(%s,%s,%s) "
                             "ON CONFLICT(location_id,group_id) DO UPDATE SET remote_id=EXCLUDED.remote_id,verified_at=now()",
                             (row["location_id"], claim["desired"]["group_id"], remote_id))
        conn.execute("UPDATE crm_outbox SET state=%s,remote_id=COALESCE(%s,remote_id),next_attempt_at=%s,lease_owner=NULL,lease_until=NULL WHERE outbox_id=%s",
                     (state, remote_id, now + timedelta(seconds=max(min(86_400, retry_after), min(300, 2 ** row["attempts"]))) if state in {"retry", "uncertain"} else None, row["outbox_id"]))
        service.audit(conn, "crm-worker", "crm_" + state, row["outbox_id"])
        return {"outbox_id": row["outbox_id"], "state": state}


def _finish_blocked_reconcile(settings, service, claim, remote_id):
    """Recover remote identity for removal only; never revive an obsolete approval."""
    with transaction(settings) as conn:
        service.authority(conn)
        row = conn.execute("SELECT * FROM crm_outbox WHERE outbox_id=%s FOR UPDATE", (claim["outbox_id"],)).fetchone()
        now = service.now(conn)
        if row is None or row["lease_owner"] != claim["owner"] or not row["lease_until"] or row["lease_until"] <= now:
            return {"outbox_id": claim["outbox_id"], "state": "blocked", "lease_lost": True}
        if remote_id:
            conflict = conn.execute("SELECT group_id FROM crm_identity WHERE location_id=%s AND remote_id=%s", (row["location_id"], remote_id)).fetchone()
            if conflict and str(conflict["group_id"]) != claim["desired"]["group_id"]:
                raise DomainError("CRM_REMOTE_IDENTITY_CONFLICT", 409)
            conn.execute("INSERT INTO crm_identity(location_id,group_id,remote_id) VALUES(%s,%s,%s) "
                         "ON CONFLICT(location_id,group_id) DO UPDATE SET remote_id=EXCLUDED.remote_id,verified_at=now()",
                         (row["location_id"], claim["desired"]["group_id"], remote_id))
            conn.execute("INSERT INTO propagation_outbox(outbox_id,group_id,reason) VALUES(%s,%s,'crm_inflight_reconciled')",
                         (uuid4(), claim["desired"]["group_id"]))
        state = "dead_letter" if not remote_id and row["attempts"] >= 5 else "blocked"
        conn.execute("UPDATE crm_outbox SET state=%s,operation_kind=%s,remote_id=COALESCE(%s,remote_id),next_attempt_at=%s,lease_owner=NULL,lease_until=NULL WHERE outbox_id=%s",
                     (state, "lookup" if remote_id else row["operation_kind"], remote_id,
                      None if remote_id else now + timedelta(seconds=min(300, 2 ** row["attempts"])), row["outbox_id"]))
        service.audit(conn, "crm-worker", "crm_restricted_reconciled" if remote_id else "crm_reconciliation_pending", row["outbox_id"])
        return {"outbox_id": row["outbox_id"], "state": state, "reconciliation_pending": not bool(remote_id)}


def drain_one(settings, service, provider: CRMProvider, outbox_id):
    """Claim/lookup/dispatch/finish in separate transactions; provider I/O holds no DB locks.

    The durable operation kind survives worker death. Unknown creates NEVER blindly recreate.
    Existing groups must match the desired projection or receive an idempotent verified update.
    Suppression can commit during any provider call; completion records its follow-up race.
    """
    if settings.mode != service.settings.mode:
        raise DomainError("CRM_ENVIRONMENT_MISMATCH", 409)
    live = settings.mode != "fixture"
    from abr_engine.export.gohighlevel import GoHighLevel
    if not live and isinstance(provider, GoHighLevel):
        raise DomainError("FIXTURE_LIVE_PROVIDER_FORBIDDEN", 409)
    if live:
        from abr_engine.export.live_contract import live_contract
        if type(provider) is not GoHighLevel:
            raise DomainError("LIVE_CRM_PROVIDER_REQUIRED", 409)
        live_provider = cast(GoHighLevel, provider)
        with transaction(settings) as conn:
            config, _, _ = live_contract(conn, service, removal_only=True)
            if live_provider.config != config:
                raise DomainError("CRM_PROVIDER_CONFIG_CHANGED", 409)
    claim, state = _claim(settings, service, outbox_id)
    if claim is None:
        return {"outbox_id": outbox_id, "state": state}
    if live:
        def current_read():
            with transaction(settings) as conn:
                config, _, _ = live_contract(conn, service, removal_only=claim["reconcile_only"])
                if live_provider.config != config or claim["location_id"] != config.location_id:
                    raise DomainError("CRM_PROVIDER_CONFIG_CHANGED", 409)
        def current_write():
            current_read()
            with transaction(settings) as conn:
                service.authority(conn)
                row = conn.execute("SELECT * FROM crm_outbox WHERE outbox_id=%s FOR UPDATE", (outbox_id,)).fetchone()
                if (not row or row["state"] != "inflight" or row["lease_owner"] != claim["owner"]
                        or not row["lease_until"] or row["lease_until"] <= service.now(conn)
                        or not _current(conn, service, row, claim["desired"])):
                    raise DomainError("CRM_WRITE_AUTHORITY_CHANGED", 409)
        live_provider.read_guard, live_provider.write_guard = current_read, current_write
    desired = claim["desired"]
    remote_id = None
    dispatched = False
    retry_after = 0
    try:
        matches = provider.find_group(desired["group_id"])
        if len(matches) > 1:
            raise DomainError("CRM_MATCH_AMBIGUOUS", 409)
        if claim["reconcile_only"]:
            if matches:
                remote_id = matches[0]
                if provider.fetch(remote_id).get("group_id") != desired["group_id"]:
                    raise DomainError("CRM_REMOTE_IDENTITY_CONFLICT", 409)
            return _finish_blocked_reconcile(settings, service, claim, remote_id)
        if matches:
            remote_id = matches[0]
            remote = provider.fetch(remote_id)
            if _remote_matches(remote, desired):
                return _finish(settings, service, claim, "succeeded", remote_id,
                               dispatched=claim["operation_kind"] in {"create", "update"})
            operation = "update"
        else:
            if claim["operation_kind"] == "create":
                return _finish(settings, service, claim, "uncertain", dispatched=True)
            operation = "create"
        if not _dispatch(settings, service, claim, operation, remote_id):
            return _finish(settings, service, claim, "blocked", remote_id)
        dispatched = True
        if operation == "create":
            remote_id = provider.create(desired["group_id"], desired, str(outbox_id))
        else:
            if remote_id is None:
                raise DomainError("CRM_REMOTE_IDENTITY_MISSING", 409)
            provider.update(remote_id, desired, str(outbox_id))
        if not isinstance(remote_id, str) or not remote_id:
            raise DomainError("CRM_REMOTE_IDENTITY_MISSING", 409)
        state = "succeeded" if _remote_matches(provider.fetch(remote_id), desired) else "uncertain"
    except DomainError:
        state = "blocked"
    except OSError as exc:
        state = "uncertain" if dispatched or claim["operation_kind"] in {"create", "update"} else "retry"
        retry_after = getattr(exc, "retry_after", 0)
    finally:
        if live:
            live_provider.read_guard = live_provider.write_guard = None
    return _finish(settings, service, claim, state, remote_id, dispatched=dispatched, retry_after=retry_after)


def drain_live_one(settings, service, outbox_id, *, transport=None, environ=None):
    """No ambient mock fallback. Secrets are injected by the service environment."""
    from abr_engine.export.gohighlevel import GoHighLevel
    from abr_engine.export.live_contract import live_contract
    if settings.mode == "fixture":
        raise DomainError("LIVE_MODE_REQUIRED", 409)
    with transaction(settings) as conn:
        config, _, _ = live_contract(conn, service, removal_only=True)
    with GoHighLevel.from_environment(config, transport=transport, environ=environ) as provider:
        return drain_one(settings, service, provider, outbox_id)
