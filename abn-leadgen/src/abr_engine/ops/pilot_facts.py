"""Minimal fixed cohort facts survive marketing erasure for a finite measurement purpose."""
from uuid import NAMESPACE_URL, uuid5

from psycopg import sql

from abr_engine.control.service import DomainError


def _insert_immutable(conn, table, values):
    key = next(iter(values))
    existing = conn.execute(sql.SQL("SELECT * FROM {} WHERE {}=%s").format(sql.Identifier(table), sql.Identifier(key)), (values[key],)).fetchone()
    if existing:
        if existing != values:
            raise DomainError("RETAINED_METRIC_CONFLICT", 409)
        return
    conn.execute(sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(sql.Identifier(table),
        sql.SQL(",").join(map(sql.Identifier, values)), sql.SQL(",").join(sql.Placeholder() for _ in values)), tuple(values.values()))


def retain_profile_metrics(conn, service, lead_id, *, now):
    from abr_engine.compliance.retention import retention_deadline
    group = service.lead(conn, lead_id)["group_id"]
    rows = conn.execute("SELECT r.row_id,r.worklist_id,r.selected_tier,r.selected_signal,w.generated_at FROM worklist_row r JOIN worklist w USING(worklist_id) WHERE r.lead_id=%s ORDER BY w.generated_at,r.row_id", (lead_id,)).fetchall()
    activities = conn.execute("SELECT * FROM operator_activity WHERE lead_id=%s ORDER BY recorded_seq", (lead_id,)).fetchall()
    holds = {(r["object_type"], r["object_id"]) for r in conn.execute("SELECT object_type,object_id FROM retention_hold").fetchall()}
    for row in rows:
        events = conn.execute("SELECT event_id,status,attempts,occurred_at,recorded_seq FROM outcome_event WHERE row_id=%s ORDER BY recorded_seq", (row["row_id"],)).fetchall()
        relevant = [row["generated_at"], *(r["occurred_at"] for r in events if r["occurred_at"]>=row["generated_at"]), *(a["ended_at"] for a in activities if a["worklist_id"] == row["worklist_id"])]
        deadline = retention_deadline("metric", max(relevant))
        row_held = ("cohort", str(row["worklist_id"])) in holds or ("cohort_metric", str(row["row_id"])) in holds
        child_held = any(("outcome_metric", str(e["event_id"])) in holds for e in events)
        if deadline <= now and not row_held and not child_held:
            continue
        _insert_immutable(conn, "retained_cohort_fact", {**row, "group_id": group, "retained_until": deadline})
        attempted = 0
        for event in events:
            delta = 0
            if event["occurred_at"] >= row["generated_at"]:
                delta = max(0, event["attempts"]-attempted)
                attempted = max(attempted, event["attempts"])
            expiry = retention_deadline("metric", event["occurred_at"])
            if expiry <= now and not row_held and ("outcome_metric", str(event["event_id"])) not in holds:
                continue
            status = event["status"]
            kind = status if status in {"meeting_booked", "meeting_held"} else "contacted" if status.startswith("contacted_") else "other"
            _insert_immutable(conn, "retained_outcome_fact", {"event_id": event["event_id"], "row_id": row["row_id"],
                "status": kind, "attempts": event["attempts"], "attempt_increment": delta,
                "occurred_at": event["occurred_at"], "recorded_seq": event["recorded_seq"], "retained_until": expiry})
    for activity in activities:
        expiry = retention_deadline("metric", activity["ended_at"])
        activity_held = ("activity_metric", str(activity["activity_id"])) in holds or ("cohort", str(activity["worklist_id"])) in holds
        if expiry > now or activity_held or conn.execute("SELECT 1 FROM operator_activity WHERE correction_of=%s", (activity["activity_id"],)).fetchone():
            _insert_immutable(conn, "retained_activity_fact", {"activity_id": activity["activity_id"], "worklist_id": activity["worklist_id"],
                "group_id": group, "actor_key": uuid5(NAMESPACE_URL, activity["actor_id"]), "category": activity["category"],
                "started_at": activity["started_at"], "ended_at": activity["ended_at"], "correction_of": activity["correction_of"],
                "recorded_seq": activity["recorded_seq"], "retained_until": expiry})
    conn.execute("UPDATE operator_activity SET metrics_archived_at=%s WHERE lead_id=%s AND metrics_archived_at IS NULL", (now, lead_id))


def measurement_rows(conn):
    selections = conn.execute("""SELECT r.row_id,r.worklist_id,l.group_id,r.selected_tier,r.selected_signal,w.generated_at
      FROM worklist_row r JOIN lead_entity l USING(lead_id) JOIN worklist w USING(worklist_id)
      WHERE NOT EXISTS(SELECT 1 FROM retained_cohort_fact f WHERE f.row_id=r.row_id)
      UNION ALL SELECT row_id,worklist_id,group_id,selected_tier,selected_signal,generated_at FROM retained_cohort_fact
      ORDER BY generated_at,row_id""").fetchall()
    outcomes = conn.execute("""SELECT e.event_id,e.row_id,e.status,e.attempts,e.occurred_at,e.recorded_seq,NULL::integer attempt_increment
      FROM outcome_event e WHERE NOT EXISTS(SELECT 1 FROM retained_outcome_fact f WHERE f.event_id=e.event_id)
      UNION ALL SELECT event_id,row_id,status,attempts,occurred_at,recorded_seq,attempt_increment FROM retained_outcome_fact
      ORDER BY recorded_seq,event_id""").fetchall()
    activities = []
    for row in conn.execute("SELECT a.*,l.group_id FROM operator_activity a LEFT JOIN lead_entity l USING(lead_id) WHERE a.metrics_archived_at IS NULL AND NOT EXISTS(SELECT 1 FROM retained_activity_fact f WHERE f.activity_id=a.activity_id) ORDER BY a.recorded_seq").fetchall():
        activities.append({**row, "actor_key": uuid5(NAMESPACE_URL, row["actor_id"])})
    activities.extend(conn.execute("SELECT * FROM retained_activity_fact").fetchall())
    activities.sort(key=lambda r: (r["recorded_seq"], str(r["activity_id"])))
    return selections, outcomes, activities


def expire_metrics(conn, *, now, execute):
    from abr_engine.compliance.retention import _months
    def purge_original_orphans():
        while conn.execute("DELETE FROM operator_activity a WHERE a.metrics_archived_at IS NOT NULL AND a.ended_at<=%s AND NOT EXISTS(SELECT 1 FROM retained_activity_fact f WHERE f.activity_id=a.activity_id) AND NOT EXISTS(SELECT 1 FROM operator_activity c WHERE c.correction_of=a.activity_id) AND NOT EXISTS(SELECT 1 FROM retention_hold h WHERE (h.object_type='activity_metric' AND h.object_id=a.activity_id::text) OR (h.object_type='cohort' AND h.object_id=a.worklist_id::text))", (_months(now, -24),)).rowcount:
            pass
    if execute:
        purge_original_orphans()
    counts = {}
    for table, kind, key in (("retained_outcome_fact", "outcome_metric", "event_id"),
                             ("retained_activity_fact", "activity_metric", "activity_id"),
                             ("retained_cohort_fact", "cohort_metric", "row_id")):
        extra = ""
        if table == "retained_outcome_fact":
            group_ref = "(SELECT group_id FROM retained_cohort_fact c WHERE c.row_id=f.row_id)"
            work_ref = "(SELECT worklist_id FROM retained_cohort_fact c WHERE c.row_id=f.row_id)"
            extra = " AND NOT EXISTS(SELECT 1 FROM retention_hold h WHERE h.object_type='cohort_metric' AND h.object_id=f.row_id::text)"
        else:
            group_ref, work_ref = "f.group_id", "f.worklist_id"
        if table == "retained_cohort_fact":
            extra = " AND NOT EXISTS(SELECT 1 FROM retained_outcome_fact o WHERE o.row_id=f.row_id)"
        if table == "retained_activity_fact":
            extra = " AND NOT EXISTS(SELECT 1 FROM retained_activity_fact a WHERE a.correction_of=f.activity_id) AND NOT EXISTS(SELECT 1 FROM operator_activity a WHERE a.correction_of=f.activity_id)"
        predicate = f"f.retained_until<=%s AND NOT EXISTS(SELECT 1 FROM retention_hold h WHERE (h.object_type=%s AND h.object_id=f.{key}::text) OR (h.object_type='group' AND h.object_id=({group_ref})::text) OR (h.object_type='cohort' AND h.object_id=({work_ref})::text))" + extra
        args = (now, kind)
        counts[kind] = conn.execute(f"SELECT count(*) n FROM {table} f WHERE " + predicate, args).fetchone()["n"]
        if execute:
            conn.execute("SET LOCAL abr.retention_delete='on'")
            removed = 0
            while True:
                if table == "retained_activity_fact":
                    conn.execute("DELETE FROM operator_activity a WHERE a.metrics_archived_at IS NOT NULL AND a.activity_id IN (SELECT f.activity_id FROM retained_activity_fact f WHERE " + predicate + ")", args)
                batch = conn.execute(f"DELETE FROM {table} f WHERE " + predicate, args).rowcount
                removed += batch
                if table != "retained_activity_fact" or not batch:
                    break
            counts[kind] = removed
            conn.execute("SET LOCAL abr.retention_delete='off'")
    if execute:
        # Marked expired originals lacking any retained fact must not keep identifying actor text.
        purge_original_orphans()
    return counts


def effective_activity_pairs(activities, rows):
    """Resolve correction leaves before splitting work into cohort/tier allocations."""
    replaced = {a.correction_of for a in activities if a.correction_of}
    return [(activity.model_copy(update={"correction_of": None}), row)
            for activity, row in zip(activities, rows, strict=True) if activity.activity_id not in replaced]
