"""Database-backed redacted operations/cohort projection; no fabricated pilot observations."""
from datetime import datetime
from uuid import UUID, uuid4, uuid5
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from abr_engine.control.service import json_safe
from abr_engine.export.metrics import Activity, CohortEntry, Outcome, cohort_metrics, union_work_seconds
from abr_engine.ops.alarms import AlarmInputs, Flag, evaluate_alarms
from abr_engine.ops.costs import cost_projection
from abr_engine.ops.pilot_facts import effective_activity_pairs, measurement_rows


def operational_summary(conn, service, run_id, start, end):
    service.authority(conn)
    entries, outcomes, memberships = [], [], {}
    rows, outcome_rows, activity_rows = measurement_rows(conn)
    row_groups = {}
    for row in rows:
        group = service.canonical_group(conn, row["group_id"])
        key = (row["worklist_id"], group)
        row_groups[row["row_id"]] = key
        if key not in memberships:
            entry = CohortEntry(cohort_id=key[0], group_id=key[1], tier=row["selected_tier"], originating_signal=row["selected_signal"], selected_at=row["generated_at"])
            memberships[key] = entry
            entries.append(entry)
    # Sheet attempts are cumulative per immutable row. Count positive increases once.
    counters: dict[UUID, int] = {}
    anomalies = 0
    for row in outcome_rows:
        event_key = row_groups.get(row["row_id"])
        if not event_key or row["occurred_at"] < memberships[event_key].selected_at:
            anomalies += 1
            continue
        prior = counters.get(row["row_id"], 0)
        increase = row["attempt_increment"] if row["attempt_increment"] is not None else max(0, row["attempts"] - prior)
        counters[row["row_id"]] = max(prior, row["attempts"])
        base = {"cohort_id": event_key[0], "group_id": event_key[1], "occurred_at": row["occurred_at"]}
        if increase:
            outcomes.append(Outcome(event_id=uuid5(row["event_id"], "attempt"), kind="attempt", attempts=increase, **base))
        status = row["status"]
        if status in {"contacted", "meeting_booked", "meeting_held"} or status.startswith("contacted_"):
            outcomes.append(Outcome(event_id=row["event_id"], kind=status if status.startswith("meeting_") else "contacted", **base))
    activities = [Activity(activity_id=r["activity_id"], actor_id=r["actor_key"], category=r["category"], started_at=r["started_at"], ended_at=r["ended_at"], correction_of=r["correction_of"]) for r in activity_rows]
    effective = effective_activity_pairs(activities, activity_rows)
    costs = cost_projection(conn, service, start, end, activities)
    cohorts = cohort_metrics(entries, outcomes, start, end)
    cohort_costs = []
    seen_cost_cohorts = set()
    for cohort in cohorts:
        if (cohort["cohort_id"], cohort["tier"]) in seen_cost_cohorts:
            continue
        seen_cost_cohorts.add((cohort["cohort_id"], cohort["tier"]))
        eligible_groups = {entry.group_id for entry in memberships.values() if str(entry.cohort_id) == cohort["cohort_id"] and entry.tier == cohort["tier"]}
        tier_count = len({entry.tier for entry in memberships.values() if str(entry.cohort_id) == cohort["cohort_id"]})
        relevant = [activity for activity, r in effective
                    if str(r["worklist_id"]) == cohort["cohort_id"] and (r["group_id"] is not None and service.canonical_group(conn, r["group_id"]) in eligible_groups or r["group_id"] is None and tier_count == 1)]
        cohort_costs.append({"cohort_id": cohort["cohort_id"], "tier": cohort["tier"], **cost_projection(conn, service, start, end, relevant, cohort_id=cohort["cohort_id"], tier=cohort["tier"])})
    month = end.astimezone(ZoneInfo("Australia/Brisbane")).strftime("%Y-%m")
    spend = conn.execute("SELECT coalesce(sum(reserved),0) reserved,coalesce(sum(settled),0) settled FROM budget_month WHERE month=%s", (month,)).fetchone()
    alarms = []
    flags: set[Flag] = set()
    if conn.execute("SELECT 1 FROM crm_outbox WHERE state='uncertain' LIMIT 1").fetchone():
        flags.add("crm_reconciliation_pending")
    policy = service.current_policy(conn)
    if not policy or policy["state"] != "approved" or not policy["approved_at"] <= end < policy["expires_at"]:
        flags.add("policy_expired")
    if conn.execute("SELECT 1 FROM budget_month WHERE month=%s AND (frozen OR reserved+settled>=cap) LIMIT 1", (month,)).fetchone():
        flags.add("budget_stop")
    delayed = conn.execute("SELECT extract(epoch FROM (%s-min(created_at))) age FROM propagation_outbox WHERE completed_at IS NULL AND created_at<=%s", (end, end)).fetchone()["age"]
    for source in ("abr", "qbcc"):
        latest = conn.execute("SELECT s.manifest FROM source_cursor c JOIN source_snapshot s USING(snapshot_id) WHERE c.source=%s", (source,)).fetchone()
        stamp = latest["manifest"].get("publisher_timestamp") if latest else None
        age = None
        if stamp:
            published = datetime.fromisoformat(stamp)
            age = max(0, (end-published).total_seconds()/86400) if published.tzinfo else None
        for alarm in evaluate_alarms(AlarmInputs(run_id=run_id, source=source, source_age_days=age, flags=flags,
                                               suppression_propagation_seconds=float(delayed) if delayed is not None else None)):
            conn.execute("INSERT INTO alarm_outbox(alarm_id,run_id,code,subject_key,payload) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(run_id,code,subject_key) DO NOTHING",
                         (uuid4(), run_id, alarm.code, alarm.subject_key, Jsonb(json_safe(alarm.model_dump()))))
            alarms.append(alarm.code)
    return {"window_start": start.isoformat(), "window_end_exclusive": end.isoformat(),
            "cohorts": cohorts, "cohort_costs": cohort_costs, "worked_seconds": union_work_seconds(activities, start, end),
            "activity_records": len(activities), "undated_or_preselection_outcomes_excluded": anomalies,
            "usage_micro_aud": {"brisbane_calendar_month": month, "reserved": int(spend["reserved"]), "settled": int(spend["settled"])}, **costs,
            "alarms": sorted(set(alarms)), "pilot_observation": "synthetic_only" if service.settings.mode == "fixture" else "unreviewed",
            "attribution": "Fixed first selected tier/signal per worklist and canonical group; cumulative attempt increases; dated events; per-actor interval unions."}
