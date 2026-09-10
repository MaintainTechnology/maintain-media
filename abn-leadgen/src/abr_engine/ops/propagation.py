"""Downstream stop projection with durable claims and verified update receipts."""
from __future__ import annotations

import copy
from datetime import timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb

from abr_engine.control.service import DomainError, digest
from abr_engine.db import transaction
from abr_engine.export.crm import MAPPED_FIELDS, load_field_mapping
from abr_engine.export.mock_provider import PersistentMockCRM


def blocked_projection(remote, mapping=None):
    """Remove only engine-owned marketing values; keep remote identity/unrelated metadata."""
    mapping = mapping or load_field_mapping()
    stop_tag = "maintain-media:suppressed"
    if stop_tag not in mapping["tags"]["allowed"]:
        raise DomainError("PROPAGATION_TAG_NOT_CERTIFIED")
    desired = copy.deepcopy(remote["payload"])
    for key in MAPPED_FIELDS | {"business_name", "contact_id", "endpoint", "channel"}:
        desired[key] = None
    owned_ids = {field["custom_field_id"] for field in mapping["fields"].values()}
    desired["custom_fields"] = [dict(field, value=None) if field.get("id") in owned_ids else field
                                 for field in desired.get("custom_fields", [])]
    desired["tags"] = sorted({tag for tag in desired.get("tags", []) if not tag.startswith("maintain-media:")}
                             | {stop_tag})
    desired["outreach_blocked"] = True
    return desired


def _projection_matches(remote, desired):
    if "provider_dnd" in remote and remote["provider_dnd"] is not True:
        return False
    actual = copy.deepcopy(remote.get("payload", {}))
    actual["tags"] = sorted(actual.get("tags", []))
    expected = copy.deepcopy(desired)
    expected["tags"] = sorted(expected.get("tags", []))
    return digest(actual) == digest(expected)


def _claim(settings, service, limit):
    owner = uuid4()
    with transaction(settings) as conn:
        service.authority(conn)
        now = service.now(conn)
        conn.execute("UPDATE propagation_outbox SET state='dead_letter',lease_owner=NULL,lease_until=NULL,last_error_code='LEASE_EXHAUSTED' WHERE state='inflight' AND attempts>=5 AND lease_until<=%s", (now,))
        rows = conn.execute("SELECT * FROM propagation_outbox WHERE completed_at IS NULL AND attempts<5 AND ((state IN ('pending','retry') AND (next_attempt_at IS NULL OR next_attempt_at<=%s)) OR (state='inflight' AND lease_until<=%s)) ORDER BY created_at,outbox_id FOR UPDATE SKIP LOCKED LIMIT %s", (now, now, limit)).fetchall()
        for row in rows:
            conn.execute("UPDATE propagation_outbox SET state='inflight',lease_owner=%s,lease_until=%s,attempts=attempts+1 WHERE outbox_id=%s", (owner, now+timedelta(seconds=120), row["outbox_id"]))
            row["owner"] = owner
    return rows


def _authority(settings, service, claim):
    with transaction(settings) as conn:
        service.personal_data_access(conn)
        row = conn.execute("SELECT * FROM propagation_outbox WHERE outbox_id=%s FOR UPDATE", (claim["outbox_id"],)).fetchone()
        if not row or row["lease_owner"] != claim["owner"] or row["state"] != "inflight" or row["lease_until"] <= service.now(conn):
            raise DomainError("PROPAGATION_LEASE_LOST")
        if not row["group_id"]:
            raise DomainError("PROPAGATION_IDENTITY_UNKNOWN")
        family = service.group_family(conn, row["group_id"])
        mappings = conn.execute("SELECT * FROM crm_identity WHERE group_id=ANY(%s)", (family,)).fetchall()
        location = "fixture"
        if settings.mode != "fixture":
            from abr_engine.export.live_contract import live_contract
            location = live_contract(conn, service, removal_only=True)[0].location_id
        if any(mapping["location_id"] != location for mapping in mappings):
            raise DomainError("PROPAGATION_LOCATION_MISMATCH")
        pending = conn.execute("SELECT 1 FROM crm_outbox o JOIN lead_entity l USING(lead_id) WHERE l.group_id=ANY(%s) AND o.dispatched_at IS NOT NULL AND o.operation_kind IN ('create','update') AND o.state IN ('inflight','uncertain','blocked','dead_letter') LIMIT 1", (family,)).fetchone() is not None
        # Read actual restrictions/current contact decisions under authority. This worker only
        # removes the stale projection; it never reverses a stop when new evidence appears.
        restricted = bool(service.restricted(conn, row["group_id"]))
        contacts = conn.execute("SELECT c.contact_id FROM contact_record c JOIN lead_entity l USING(lead_id) WHERE l.group_id=ANY(%s)", (family,)).fetchall()
        denied = sum(not service.gate(conn, contact["contact_id"])["allowed"] for contact in contacts)
        return family, mappings, pending, {"entity_restricted": restricted, "denied_contacts": denied}


def _finish(settings, service, claim, receipt=None, error=None, retry_after=0):
    with transaction(settings) as conn:
        service.authority(conn)
        row = conn.execute("SELECT * FROM propagation_outbox WHERE outbox_id=%s FOR UPDATE", (claim["outbox_id"],)).fetchone()
        now = service.now(conn)
        if not row or row["lease_owner"] != claim["owner"] or row["state"] != "inflight" or row["lease_until"] <= now:
            return {"outbox_id": str(claim["outbox_id"]), "state": "lease_lost"}
        state = "succeeded" if receipt is not None else "dead_letter" if row["attempts"] >= 5 else "retry"
        if receipt is not None:
            receipt["verified_at"] = now.isoformat()
        conn.execute("UPDATE propagation_outbox SET state=%s,completed_at=%s,receipt=%s,last_error_code=%s,next_attempt_at=%s,lease_owner=NULL,lease_until=NULL WHERE outbox_id=%s",
                     (state, now if receipt is not None else None, Jsonb(receipt) if receipt is not None else None,
                      error, None if receipt is not None else now+timedelta(seconds=max(min(86_400, retry_after), min(300, 2**row["attempts"]))), row["outbox_id"]))
        return {"outbox_id": str(row["outbox_id"]), "state": state,
                "elapsed_since_enqueue_seconds": (now-row["created_at"]).total_seconds(),
                "verified_remote_records": receipt["verified_remote_records"] if receipt else 0}


def drain_propagation(settings, service, *, limit=60, provider=None, transport=None, environ=None):
    if settings.mode != service.settings.mode:
        raise DomainError("PROPAGATION_ENVIRONMENT_MISMATCH", 409)
    live = settings.mode != "fixture"
    from abr_engine.export.gohighlevel import GoHighLevel
    if not live and isinstance(provider, GoHighLevel):
        raise DomainError("FIXTURE_LIVE_PROVIDER_FORBIDDEN", 409)
    if live and provider is not None:
        raise DomainError("LIVE_PROPAGATION_INJECTED_PROVIDER_FORBIDDEN", 409)
    if not 1 <= limit <= 60:
        raise ValueError("limit must be 1..60")
    if live:
        from abr_engine.export.live_contract import live_contract
        with transaction(settings) as conn:
            live_contract(conn, service, removal_only=True)
    else:
        provider = provider or PersistentMockCRM(settings, service.keys)
    results = []
    for claim in _claim(settings, service, limit):
        active_provider = provider
        try:
            mapping = load_field_mapping()
            if live:
                with transaction(settings) as conn:
                    config, mapping, _ = live_contract(conn, service, removal_only=True)
                def live_authority(claim=claim, config=config):
                    _authority(settings, service, claim)
                    with transaction(settings) as conn:
                        current, _, _ = live_contract(conn, service, removal_only=True)
                        if current != config:
                            raise DomainError("CRM_PROVIDER_CONFIG_CHANGED", 409)
                active_provider = GoHighLevel.from_environment(config, transport=transport, environ=environ,
                    read_guard=live_authority, write_guard=live_authority)
            if active_provider is None:
                raise DomainError("PROPAGATION_PROVIDER_MISSING", 409)
            family, mappings, pending, controls = _authority(settings, service, claim)
            identities = {row["remote_id"]: str(row["group_id"]) for row in mappings}
            # Lookup is outside all database/global locks, including when mapping is absent.
            for group in family:
                matches = active_provider.find_group(str(group))
                if len(matches) > 1:
                    raise DomainError("PROPAGATION_IDENTITY_AMBIGUOUS")
                for remote_id in matches:
                    if remote_id in identities and identities[remote_id] != str(group):
                        raise DomainError("PROPAGATION_IDENTITY_CONFLICT")
                    identities[remote_id] = str(group)
            verified = []
            for remote_id, group_id in identities.items():
                remote = active_provider.fetch(remote_id)
                if not remote or remote.get("group_id") != group_id or remote.get("payload", {}).get("group_id") != group_id:
                    raise DomainError("PROPAGATION_IDENTITY_CONFLICT")
                desired = blocked_projection(remote, mapping)
                _authority(settings, service, claim)
                if not _projection_matches(remote, desired):
                    active_provider.update(remote_id, desired, str(claim["outbox_id"]))
                after = active_provider.fetch(remote_id)
                if not after or after.get("group_id") != group_id or not _projection_matches(after, desired):
                    raise DomainError("PROPAGATION_UPDATE_UNCONFIRMED")
                verified.append(digest({"group_id": group_id, "remote_id": remote_id, "projection": desired}))
            _, _, pending_after, _ = _authority(settings, service, claim)
            if pending or pending_after:
                raise DomainError("PROPAGATION_CRM_RECONCILIATION_PENDING")
            results.append(_finish(settings, service, claim, receipt={"mode": settings.mode, "verified_remote_records": len(verified),
                "projection_digests": verified, "no_remote_records_confirmed": not identities, "controls": controls,
                "notifications_sent": 0}))
        except (OSError, TimeoutError, ValueError, DomainError) as exc:
            # No provider exception strings or remote identifiers enter the public receipt.
            code = exc.code if isinstance(exc, DomainError) else "PROPAGATION_PROVIDER_UNCERTAIN"
            results.append(_finish(settings, service, claim, error=code, retry_after=getattr(exc, "retry_after", 0)))
        finally:
            if live and active_provider is not None:
                active_provider.close()
    return {"mode": settings.mode, "notifications_sent": 0, "results": results}
