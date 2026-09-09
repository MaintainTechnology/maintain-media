"""Closed redacted observations and durable fixture alarm delivery. Never sends notifications."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, Field, model_validator

from abr_engine.control.service import DomainError
from abr_engine.db import transaction
from abr_engine.ops.alarms import AlarmInputs, evaluate_alarms, make_alarm


class Observation(AlarmInputs):
    """Only numeric/status facts, UUID references and dates may cross this boundary."""
    observed_at: AwareDatetime
    evidence_id: UUID | None = None
    snapshot_id: UUID | None = None
    source_contract_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    source_rows: int | None = Field(default=None, ge=0)
    field_fill_weighted: dict[Literal["abn", "status", "status_date", "entity_type", "main_name", "state", "postcode"], Annotated[float, Field(ge=0, le=1)]] = Field(default_factory=dict)
    member_count: int | None = Field(default=None, ge=0)
    enrichment_completed: int | None = Field(default=None, ge=0)
    enrichment_with_contact: int | None = Field(default=None, ge=0)
    suppression_request_to_commit_seconds: float | None = Field(default=None, ge=0)
    backup_status: Literal["unknown", "passed", "failed"] = "unknown"
    restore_status: Literal["unknown", "passed", "failed"] = "unknown"
    timer_last_success_at: AwareDatetime | None = None
    timer_max_interval_seconds: int | None = Field(default=None, ge=1, le=604800)

    @model_validator(mode="after")
    def inventory_authority(self):
        if ((self.backup_status != "unknown" or self.restore_status != "unknown"
             or self.timer_last_success_at is not None) and self.evidence_id is None):
            raise ValueError("Inventory status requires an evidence UUID")
        if (self.timer_last_success_at is None) != (self.timer_max_interval_seconds is None):
            raise ValueError("Timer timestamp and expected interval must be supplied together")
        if self.timer_last_success_at and self.timer_last_success_at > self.observed_at:
            raise ValueError("Future timer heartbeat")
        return self


ERROR_FLAGS = {
    "REVISION_CONFLICT": "writeback_conflict", "IDEMPOTENCY_CONFLICT": "writeback_conflict",
    "INVALID_RECEIPT": "invalid_receipt", "RECEIPT_MISMATCH": "invalid_receipt",
    "WASH_RECEIPT_INVALID": "invalid_receipt", "SUPPRESSION_UNCONFIRMED": "suppression_unconfirmed",
    "RECEIPT_FORMAT_UNAPPROVED": "invalid_receipt", "BATCH_MISMATCH": "invalid_receipt",
    "INVALID_WASH_OBSERVATION": "invalid_receipt", "DUPLICATE_WASH_ROW": "invalid_receipt",
    "BATCH_MEMBERSHIP_MISMATCH": "invalid_receipt", "RECEIPT_CONTENT_MISMATCH": "invalid_receipt",
    "BUDGET_STOP": "budget_stop", "QUOTA_STOP": "quota_stop",
}


def persist_observation(conn, observation: Observation):
    value = observation.model_dump(mode="json")
    # Set order is not meaningful; make the content digest stable across process hash seeds.
    value["flags"] = sorted(value["flags"])
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    conn.execute("INSERT INTO ops_observation(observation_id,run_id,source,observed_at,digest,payload) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(run_id,source,digest) DO NOTHING",
                 (uuid4(), observation.run_id, observation.source, observation.observed_at, digest, Jsonb(value)))
    inputs = {name: getattr(observation, name) for name in AlarmInputs.model_fields}
    inputs["flags"] = set(inputs["flags"])
    if observation.backup_status == "failed":
        inputs["flags"].add("backup_failed")
    if observation.restore_status == "failed":
        inputs["flags"].add("restore_failed")
    if (observation.timer_last_success_at and observation.timer_max_interval_seconds is not None and
            (observation.observed_at-observation.timer_last_success_at).total_seconds() > observation.timer_max_interval_seconds):
        inputs["flags"].add("timer_heartbeat_missed")
    alarms = evaluate_alarms(AlarmInputs.model_validate(inputs))
    for alarm in alarms:
        conn.execute("INSERT INTO alarm_outbox(alarm_id,run_id,code,subject_key,payload) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(run_id,code,subject_key) DO NOTHING",
                     (uuid4(), alarm.run_id, alarm.code, alarm.subject_key, Jsonb(alarm.model_dump(mode="json"))))
    unknown = [name for name in ("source_age_days", "mismatch_hours", "field_fill_delta_pp",
                "classification_delta_pp", "approved_hit_rate_baseline", "required_free_disk_bytes",
                "suppression_commit_seconds", "timer_last_success_at") if getattr(observation, name) is None]
    unknown += [name for name in ("backup_status", "restore_status") if getattr(observation, name) == "unknown"]
    if len(observation.comparable_volumes) < 4:
        unknown.append("four_comparable_publications")
    return {"source": observation.source, "observation_digest": digest,
            "alarms": [alarm.code for alarm in alarms], "unknown_inputs": unknown}


def _source_failure(code):
    """Map actual pipeline failure codes to the closed alarm inventory; discard error text."""
    code = str(code).upper()
    if "SCHEMA" in code:
        return "schema_failure"
    if "COUNT" in code:
        return "count_failure"
    if "DUPLICATE" in code:
        return "duplicate_failure"
    if "FIELD_FILL" in code:
        return "field_fill_breach"
    if "SPILL" in code:
        return "spill_exhausted"
    return "integrity_failure"


def monitor_run(conn, service, run_id, result: dict | None = None):
    """Project available actual DB/run facts, preserving unknown external inventory/baselines."""
    service.authority(conn)
    run = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (run_id,)).fetchone()
    if not run:
        raise DomainError("RUN_NOT_FOUND", 404)
    now = service.now(conn)
    result = result if result is not None else (run["manifest"] or {}).get("result", {})
    flags = set()
    policy = service.current_policy(conn)
    if not policy or policy["state"] != "approved" or not policy["approved_at"] <= now < policy["expires_at"]:
        flags.add("policy_expired")
    month = now.astimezone(ZoneInfo("Australia/Brisbane")).strftime("%Y-%m")
    if conn.execute("SELECT 1 FROM budget_month WHERE month=%s AND (frozen OR reserved+settled>=cap)", (month,)).fetchone():
        flags.add("budget_stop")
    if conn.execute("SELECT 1 FROM crm_outbox WHERE state='uncertain' OR (state IN ('blocked','inflight') AND operation_kind IN ('create','update') AND (lease_until IS NULL OR lease_until<%s)) LIMIT 1", (now,)).fetchone():
        flags.add("crm_reconciliation_pending")
    if conn.execute("SELECT 1 FROM enrichment_attempt WHERE state='blocked' AND reason LIKE '%%QUOTA%%' LIMIT 1").fetchone():
        flags.add("quota_stop")
    if conn.execute("SELECT 1 FROM pipeline_run WHERE state='running' AND heartbeat_at<%s LIMIT 1", (now-timedelta(minutes=5),)).fetchone():
        flags.add("timer_heartbeat_missed")
    delayed = conn.execute("SELECT extract(epoch FROM (%s-min(created_at))) AS seconds FROM propagation_outbox WHERE completed_at IS NULL", (now,)).fetchone()["seconds"]
    # Client event time is not server receipt/ack timing. Preserve its separate meaning;
    # actual server commit-ack latency stays unknown without a measured observation.
    duration = conn.execute("SELECT max(extract(epoch FROM (committed_at-requested_at))) AS seconds FROM suppression_event WHERE committed_at>=%s AND committed_at<=%s", (run["started_at"], now)).fetchone()["seconds"]
    resources = result.get("resource_sample", {})
    backup = conn.execute("SELECT run_id,state FROM pipeline_run WHERE code_version='native-backup-drill' ORDER BY started_at DESC LIMIT 1").fetchone()
    restore = conn.execute("SELECT restore_id,state FROM restore_receipt ORDER BY restored_at DESC LIMIT 1").fetchone()
    output = []
    for source in ("abr", "qbcc"):
        current = result.get("sources", {}).get(source, {})
        latest = conn.execute("SELECT s.snapshot_id,s.manifest FROM source_cursor c JOIN source_snapshot s USING(snapshot_id) WHERE c.source=%s", (source,)).fetchone()
        snapshot = current.get("snapshot_id") or (latest["snapshot_id"] if latest else None)
        promotion = conn.execute("SELECT from_snapshot_id FROM source_promotion WHERE run_id=%s AND source=%s", (run_id, source)).fetchone()
        baseline = bool(promotion and promotion["from_snapshot_id"] is None)
        baseline = baseline or bool((run["manifest"] or {}).get("request", {}).get("rebaseline"))
        observed = {"run_id": run_id, "source": source, "observed_at": now, "snapshot_id": snapshot,
                    "baseline": baseline, "no_op": bool(current.get("noop", False)), "flags": set(flags),
                    "current_volume": current.get("candidates"),
                    "member_count": current.get("validation", {}).get("members"),
                    "source_rows": current.get("validation", {}).get("source_rows"),
                    "field_fill_weighted": current.get("validation", {}).get("field_fill_weighted", {}),
                    "rss_bytes": resources.get("sampled_peak_rss_bytes"), "free_disk_bytes": resources.get("disk_free_bytes"),
                    "required_free_disk_bytes": resources.get("required_free_disk_bytes"),
                    "suppression_propagation_seconds": max(0, float(delayed)) if delayed is not None else None,
                    "suppression_request_to_commit_seconds": max(0, float(duration)) if duration is not None else None}
        if backup and backup["state"] in {"complete", "failed"}:
            observed["backup_status"] = "passed" if backup["state"] == "complete" else "failed"
            observed["evidence_id"] = backup["run_id"]
        if restore and restore["state"] == "reconciled":
            observed["restore_status"] = "passed"
            observed["evidence_id"] = restore["restore_id"]
        stamp = latest["manifest"].get("publisher_timestamp") if latest else None
        if stamp:
            publication = datetime.fromisoformat(stamp)
            if publication.tzinfo and publication <= now:
                observed["source_age_days"] = (now-publication).total_seconds()/86400
        history = conn.execute("SELECT payload FROM ops_observation WHERE source=%s AND run_id<>%s ORDER BY observed_at DESC", (source, run_id)).fetchall()
        if latest and latest["manifest"].get("parser_version") and latest["manifest"].get("schema_version"):
            contract = {name: latest["manifest"][name] for name in ("parser_version", "schema_version")}
            observed["source_contract_digest"] = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
        if observed["field_fill_weighted"] and observed.get("source_contract_digest"):
            comparison = next((r["payload"] for r in history
                               if str(r["payload"].get("snapshot_id")) != str(snapshot)
                               and r["payload"].get("source_contract_digest") == observed["source_contract_digest"]
                               and set(r["payload"].get("field_fill_weighted", {})) == set(observed["field_fill_weighted"])), None)
            if comparison:
                observed["field_fill_delta_pp"] = round(100 * max(abs(value-comparison["field_fill_weighted"][key])
                                                           for key, value in observed["field_fill_weighted"].items()), 10)
        if observed["member_count"] is not None:
            previous_members = next((r["payload"].get("member_count") for r in history
                                     if r["payload"].get("member_count") is not None
                                     and str(r["payload"].get("snapshot_id")) != str(snapshot)), None)
            if previous_members is not None and previous_members != observed["member_count"]:
                observed["flags"].add("member_count_changed")
        attempts = [UUID(item["attempt_id"]) for item in result.get("enrichment", [])
                    if item.get("attempt_id") and item.get("status") in {"complete", "exhausted"}]
        if attempts:
            sample = conn.execute("SELECT count(*) AS completed,count(*) FILTER(WHERE EXISTS(SELECT 1 FROM contact_record c WHERE c.lead_id=a.lead_id)) AS contacts FROM enrichment_attempt a JOIN lead_entity l USING(lead_id) WHERE a.attempt_id=ANY(%s) AND l.source=%s AND a.state IN ('complete','exhausted')", (attempts, source)).fetchone()
            observed["enrichment_completed"] = sample["completed"]
            observed["enrichment_with_contact"] = sample["contacts"]
            observed["hit_rate_sample_size"] = sample["completed"]
            observed["hit_rate"] = sample["contacts"]/sample["completed"] if sample["completed"] else None
        seen, volumes = set(), []
        for prior in history:
            payload = prior["payload"]
            sid = payload.get("snapshot_id")
            if sid and str(sid) != str(snapshot) and sid not in seen and not payload.get("baseline") and not payload.get("no_op") and payload.get("current_volume") is not None:
                seen.add(sid)
                volumes.append(payload["current_volume"])
                if len(volumes) == 4:
                    break
        observed["comparable_volumes"] = list(reversed(volumes))
        if current.get("event_counts", {}).get("abn_disappeared"):
            observed["flags"].add("unexpected_disappearance")
        if current.get("status") == "held":
            failure = _source_failure(current.get("code"))
            if failure == "field_fill_breach":
                alarm = make_alarm(run_id, failure, "critical")
                conn.execute("INSERT INTO alarm_outbox(alarm_id,run_id,code,subject_key,payload) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                             (uuid4(), run_id, failure, alarm.subject_key, Jsonb(alarm.model_dump(mode="json"))))
            else:
                observed["flags"].add(failure)
        output.append(persist_observation(conn, Observation.model_validate(observed)))
    return {"status": "observed", "sources": output, "notifications_sent": 0,
            "active_run_heartbeat_threshold_seconds": 300, "inventory": "Unknown external baselines and backup/timer receipts require explicit evidence observations"}


def record_control_failure(settings, code):
    """Separate transaction after failed request rollback; never stores request or exception text."""
    flag = ERROR_FLAGS.get(code)
    if flag is None:
        return False
    with transaction(settings) as conn:
        run = conn.execute("SELECT run_id FROM pipeline_run ORDER BY started_at DESC LIMIT 1").fetchone()
        if not run:
            return False
        alarm = make_alarm(run["run_id"], flag, "critical")
        conn.execute("INSERT INTO alarm_outbox(alarm_id,run_id,code,subject_key,payload) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                     (uuid4(), alarm.run_id, alarm.code, alarm.subject_key, Jsonb(alarm.model_dump(mode="json"))))
    return True


def drain_mock(settings, service, *, limit=60, fail=False):
    """Bounded leases, idempotent mock receipts, exponential retry; no external transport."""
    if settings.mode != "fixture":
        raise DomainError("LIVE_ALARM_DELIVERY_DISABLED", 403)
    if not 1 <= limit <= 60:
        raise ValueError("limit must be 1..60")
    owner = uuid4()
    with transaction(settings) as conn:
        now = service.now(conn)
        conn.execute("UPDATE alarm_outbox SET state='dead_letter',lease_owner=NULL,lease_until=NULL,last_error_code='LEASE_EXHAUSTED' WHERE state='inflight' AND attempts>=5 AND lease_until<=%s", (now,))
        rows = conn.execute("SELECT alarm_id,code,run_id,attempts FROM alarm_outbox WHERE ((state IN ('pending','retry') AND (next_attempt_at IS NULL OR next_attempt_at<=%s)) OR (state='inflight' AND lease_until<=%s)) AND attempts<5 ORDER BY alarm_id FOR UPDATE SKIP LOCKED LIMIT %s", (now, now, limit)).fetchall()
        for row in rows:
            conn.execute("UPDATE alarm_outbox SET state='inflight',lease_owner=%s,lease_until=%s,attempts=attempts+1 WHERE alarm_id=%s", (owner, now+timedelta(seconds=60), row["alarm_id"]))
    delivered = retried = dead = 0
    for row in rows:
        # This boundary is intentionally a DB mock receipt, never a notification send.
        with transaction(settings) as conn:
            current = conn.execute("SELECT * FROM alarm_outbox WHERE alarm_id=%s FOR UPDATE", (row["alarm_id"],)).fetchone()
            assert current is not None
            if current["lease_owner"] != owner or current["state"] != "inflight":
                continue
            now = service.now(conn)
            if fail:
                state = "dead_letter" if current["attempts"] >= 5 else "retry"
                conn.execute("UPDATE alarm_outbox SET state=%s,lease_owner=NULL,lease_until=NULL,next_attempt_at=%s,last_error_code='MOCK_FAILURE' WHERE alarm_id=%s", (state, now+timedelta(seconds=min(3600, 2**current["attempts"])), row["alarm_id"]))
                dead += state == "dead_letter"
                retried += state == "retry"
            else:
                # Rebuild safe payload; legacy arbitrary source messages are never copied.
                try:
                    safe_code = make_alarm(row["run_id"], row["code"]).code
                except ValueError:
                    safe_code = _source_failure(row["code"])
                safe = {"alarm_id": str(row["alarm_id"]), "run_id": str(row["run_id"]),
                        "code": safe_code,
                        "transport": "fixture_db_receipt", "notifications_sent": 0}
                conn.execute("INSERT INTO ops_mock_delivery VALUES(%s,%s,%s) ON CONFLICT(alarm_id) DO NOTHING", (row["alarm_id"], now, Jsonb(safe)))
                conn.execute("UPDATE alarm_outbox SET state='succeeded',delivered_at=%s,lease_owner=NULL,lease_until=NULL,next_attempt_at=NULL,last_error_code=NULL WHERE alarm_id=%s", (now, row["alarm_id"]))
                delivered += 1
    return {"claimed": len(rows), "delivered_mock": delivered, "retry": retried, "dead_letter": dead, "notifications_sent": 0}
