import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from pydantic import ValidationError

from abr_engine.export.metrics import (
    Activity,
    CohortEntry,
    Outcome,
    cash_and_time_metrics,
    cohort_metrics,
    union_work_seconds,
)
from abr_engine.export.report import CSV_FIELDS, ReportContext, ReportRow, render_report, safe_rows
from abr_engine.ops.alarms import AlarmInputs, Flag, evaluate_alarms, make_alarm
from abr_engine.ops.capacity import GIB, CapacityPlan, estimate_upper_bytes, measure_callable

NOW = datetime(2026, 9, 8, 1, tzinfo=UTC)


def row(**changes):
    data = {'row_id': uuid4(), 'worklist_id': uuid4(), 'lead_id': uuid4(), 'group_id': uuid4(),
                'row_version': 1, 'business_name': '<script>alert("x")</script>', 'source': "qbcc",
                'source_published_at': NOW - timedelta(days=37), 'signal': "qbcc_backlog", 'tier': "A", 'score': 85,
                'channel': "email", 'candidate_endpoint': "fixture@example.test", 'export_allowed': True,
                'gate_checked_at': NOW - timedelta(seconds=1), 'gate_expires_at': NOW + timedelta(hours=1),
                'policy_version': "fixture-v1"}
    data.update(changes)
    return ReportRow(**data)


def context(rows, **changes):
    return ReportContext(run_id=uuid4(), generated_at=NOW, authorised_operator=True, rows=rows, **changes)


def test_private_report_positive_path_and_escaped_artifacts(tmp_path):
    paths = render_report(context([row()]), tmp_path)
    html = paths["html"].read_text(encoding="utf-8")
    md = paths["markdown"].read_text(encoding="utf-8")
    csv = paths["csv"].read_text(encoding="utf-8-sig")
    assert '<script>alert' not in html and '&lt;script&gt;' in html
    assert '<script>' not in md
    assert "fixture@example.test" in html and "fixture@example.test" in csv
    assert "Email: needs send-time checks" in html
    assert "37 days old" in html and "not actual revenue" in html
    assert 'name="viewport"' in html and 'href="worklist.csv" download' in html
    assert "default-src 'none'" in html and 'noindex' in html
    assert 'minmax(min(100%,260px)' in html


@pytest.mark.parametrize("changes", [
    {"export_allowed": False}, {"policy_version": None}, {"gate_checked_at": None},
    {"gate_expires_at": None}, {"gate_expires_at": NOW},
    {"gate_checked_at": NOW + timedelta(seconds=1)}, {"channel": None},
])
def test_missing_and_expired_gate_masks_every_artifact(tmp_path, changes):
    paths = render_report(context([row(**changes)]), tmp_path)
    for path in paths.values():
        assert "fixture@example.test" not in path.read_text(encoding="utf-8-sig")
    assert "Do not contact" in paths["html"].read_text(encoding="utf-8")


def test_unauthorised_reader_mask_and_no_overwrite(tmp_path):
    ctx = ReportContext(run_id=uuid4(), generated_at=NOW, rows=[row()])
    assert "@" not in safe_rows(ctx)[0]["contact"]
    render_report(ctx, tmp_path)
    with pytest.raises(FileExistsError):
        render_report(ctx, tmp_path)


def test_csv_formula_and_markdown_link_injection(tmp_path):
    paths = render_report(context([row(business_name="  =HYPERLINK(\"https://evil.test\") [run](javascript:evil)")]), tmp_path)
    assert "'  =HYPERLINK" in paths["csv"].read_text(encoding="utf-8-sig")
    assert "\\[run\\]" in paths["markdown"].read_text(encoding="utf-8")


def test_duplicate_groups_rejected():
    first = row()
    with pytest.raises(ValidationError, match="duplicate group_id"):
        context([first, row(group_id=first.group_id)])


def activity(actor, left, right, **changes):
    return Activity(activity_id=uuid4(), actor_id=actor, category="calling",
                    started_at=NOW + timedelta(minutes=left), ended_at=NOW + timedelta(minutes=right), **changes)


def test_time_unions_overlap_by_actor_clips_window_and_applies_corrections():
    actor, second_actor = uuid4(), uuid4()
    original = activity(actor, 0, 60)
    corrected = activity(actor, 0, 20, correction_of=original.activity_id)
    activities = [original, corrected, activity(actor, 10, 30), activity(actor, 40, 60),
                  activity(second_actor, 0, 20)]
    assert union_work_seconds(activities, NOW + timedelta(minutes=5), NOW + timedelta(minutes=50)) == 50 * 60
    assert union_work_seconds([original, original], NOW, NOW + timedelta(hours=2)) == 3600
    with pytest.raises(ValueError, match="correction"):
        union_work_seconds([original, activity(second_actor, 0, 20, correction_of=original.activity_id)], NOW, NOW + timedelta(hours=2))


def test_cohort_distinct_denominators_fixed_tier_and_actual_dates():
    cohort, first, second = uuid4(), uuid4(), uuid4()
    entries = [CohortEntry(cohort_id=cohort, group_id=group, tier="A", originating_signal="qbcc_backlog", selected_at=NOW) for group in (first, second)]
    events = [Outcome(event_id=uuid4(), cohort_id=cohort, group_id=first, occurred_at=NOW, kind="attempt", attempts=2),
              Outcome(event_id=uuid4(), cohort_id=cohort, group_id=first, occurred_at=NOW, kind="contacted"),
              Outcome(event_id=uuid4(), cohort_id=cohort, group_id=first, occurred_at=NOW, kind="meeting_booked"),
              Outcome(event_id=uuid4(), cohort_id=cohort, group_id=first, occurred_at=NOW, kind="meeting_booked"),
              Outcome(event_id=uuid4(), cohort_id=cohort, group_id=second, occurred_at=NOW + timedelta(days=8), kind="meeting_held")]
    result = cohort_metrics(entries, events + [events[0]], NOW, NOW + timedelta(days=7))[0]
    assert (result["attempts"], result["contacted_groups"], result["booked_groups"], result["held_groups"]) == (2, 1, 1, 0)
    assert result["booking_rate"] == 1
    assert cohort_metrics(entries, [], NOW, NOW + timedelta(days=7))[0]["booking_rate"] is None
    with pytest.raises(ValueError, match="fixed cohort"):
        cohort_metrics(entries + [entries[0].model_copy(update={"tier": "B"})], [], NOW, NOW + timedelta(days=7))


def test_missing_costs_are_unknown_and_cash_authority_is_zero():
    values = cash_and_time_metrics({"enrichment": 5_000_000}, 3600, 30_000_000)
    assert values["fully_loaded_micro_aud"] is None and values["operator_micro_aud"] == 30_000_000
    assert values["automatic_procurement_cap_micro_aud"] == 0


def codes(**changes):
    return {alarm.code for alarm in evaluate_alarms(AlarmInputs(run_id=uuid4(), source="abr", **changes))}


@pytest.mark.parametrize("flag", Flag.__args__)
def test_every_explicit_alarm_flag_is_safe_and_deduplicated(flag):
    inputs = AlarmInputs(run_id=uuid4(), source="abr", flags={flag})
    first, second = evaluate_alarms(inputs)[0], evaluate_alarms(inputs)[0]
    assert first.dedupe_key == second.dedupe_key
    assert len(first.dedupe_key) == 64 and first.code == flag
    assert first.owner and first.runbook.startswith("ops/runbook.md#")
    assert "@" not in first.model_dump_json()
    assert make_alarm(uuid4(), flag).dedupe_key != first.dedupe_key


def test_alarm_exact_boundaries_and_baseline_exceptions():
    assert not codes(source_age_days=10, mismatch_hours=48, field_fill_delta_pp=2,
                     classification_delta_pp=3, rss_bytes=2 * GIB, suppression_commit_seconds=5,
                     suppression_propagation_seconds=60, current_volume=150, comparable_volumes=[100] * 4)
    assert codes(source_age_days=10.01, mismatch_hours=49) == {"source_stale", "source_mismatch"}
    assert codes(mismatch_hours=168) == {"source_mismatch_escalation"}
    assert codes(baseline=True, classification_delta_pp=20, current_volume=1000,
                 comparable_volumes=[10] * 4, flags={"integrity_failure"}) == {"integrity_failure"}
    assert codes(no_op=True, classification_delta_pp=20, rss_bytes=2 * GIB + 1) == {"memory_limit"}


def test_statistical_alarms_use_explicit_baselines():
    assert codes(current_volume=1, comparable_volumes=[0] * 4) == {"volume_zero_threshold_missing"}
    assert not codes(current_volume=1, comparable_volumes=[0] * 4, zero_median_absolute_threshold=1)
    assert codes(current_volume=2, comparable_volumes=[0] * 4, zero_median_absolute_threshold=1) == {"volume_deviation"}
    assert not codes(hit_rate=.1, hit_rate_sample_size=100)
    assert codes(hit_rate=.1, hit_rate_sample_size=100, approved_hit_rate_baseline=.5,
                 approved_hit_rate_drop_pp=10, minimum_hit_rate_sample_size=30) == {"hit_rate_deterioration"}


def test_capacity_exact_formula_unknown_bounds_and_no_existing_double_count():
    with pytest.raises(ValueError, match="unknown"):
        CapacityPlan().admit(10**15)
    plan = CapacityPlan(remaining_downloads=1, staged_parquet_upper_bound=2, prior_snapshot_bytes=3,
                        new_snapshot_upper_bound=4, configured_spill_limit=5, projected_db_growth=6,
                        projected_wal_growth=7, temporary_backup_bytes=8, existing_allocations={"already_on_disk": 10**12})
    required = 25 * GIB + 36
    assert plan.required_free_bytes() == required
    assert plan.admit(required) and not plan.admit(required - 1)
    assert estimate_upper_bytes(100, 10, 1000) == 20_000
    with pytest.raises(ValueError):
        estimate_upper_bytes(100, 10, 1000, 1.9)


def test_resource_sample_materialises_output_without_full_scale_claim(tmp_path):
    path = tmp_path / "sample.bin"
    result, measurement = measure_callable(lambda: path.write_bytes(b"12345"), output_paths=[path],
                                           rows=1, runtime_version="fixture")
    assert result == 5 and measurement["output_bytes"] == 5
    assert measurement["sampled_peak_rss_bytes"] > 0
    assert measurement["full_scale_certified"] is False and measurement["db_wal_measured"] is False


def test_crm_field_map_is_typed_fixture_only():
    root = Path(__file__).resolve().parents[2]
    mapping = yaml.safe_load((root / "integrations/crm_fields.yaml").read_text())
    assert mapping["mode"] == "fixture" and mapping["live_enabled"] is False
    assert mapping["location_id"] is None and mapping["sandbox_receipt"] is None
    assert mapping["identity"]["key"] == "group_id"
    assert set(mapping["fields"]) == {"abn", "signal", "score", "tier", "industry", "entity_class", "state", "website", "positioning_notes", "basis_summary"}
    assert all(value["type"] in {"number", "string"} and value["custom_field_id"].startswith("fixture_") for value in mapping["fields"].values())
    assert mapping["tags"]["replace_all"] is False and mapping["campaign_enrolment"] is False


def test_sheets_bridge_signed_reordered_row_and_immediate_optout(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node required for isolated Apps Script contract fixture")
    bridge = Path(__file__).resolve().parents[2] / "integrations/sheets_bridge.gs"
    artifacts = render_report(context([row()]), tmp_path)
    with artifacts["csv"].open(encoding="utf-8-sig", newline="") as stream:
        generated_csv = list(csv.reader(stream))
    csv_fixture = tmp_path / "generated-sheet.json"
    csv_fixture.write_text(json.dumps(generated_csv), encoding="utf-8")
    harness = r'''
const vm = require('vm'), fs = require('fs'), crypto = require('crypto'), assert = require('assert');
const headers = ['row_id','worklist_id','lead_id','group_id','row_version','save_state','status','attempts','invitation_state','invitation_evidence_ref','notes','occurred_at'];
const target='10000000-0000-4000-8000-000000000001', other='10000000-0000-4000-8000-000000000002';
const rows=[headers,[other,'w','l','g',7,'','','','','','',''],[target,'w','l','g',1,'','','','','','','']];
const sheet={getSheetId:()=>8,getLastColumn:()=>headers.length,getLastRow:()=>rows.length,getParent:()=>({getId:()=> 'private'}),
  getRange:(r,c,n=1,m=1)=>({getRow:()=>r,getColumn:()=>c,getSheet:()=>sheet,getNumRows:()=>n,getNumColumns:()=>m,
    getValues:()=>rows.slice(r-1,r-1+n).map(row=>row.slice(c-1,c-1+m)),setValue:value=>{rows[r-1][c-1]=value;}})};
let calls=[], failSuppression=false;
const props={ENABLED:'true',API_BASE_URL:'https://fixture.test',SERVICE_TOKEN:'fixture-token',BRIDGE_SECRET:'fixture-secret'};
const properties={getProperty:key=>props[key],getProperties:()=>props,setProperty:(key,value)=>{props[key]=value;},deleteProperty:key=>{delete props[key];}};
const context={PropertiesService:{getScriptProperties:()=>properties},
  SpreadsheetApp:{openById:()=>({getSheets:()=>[sheet]})},
  Utilities:{getUuid:()=>crypto.randomUUID(),Charset:{UTF_8:'utf8'},computeHmacSha256Signature:(body,secret)=>Array.from(crypto.createHmac('sha256',secret).update(body).digest())},
  UrlFetchApp:{fetch:(url,options)=>{calls.push({url,options});const suppress=url.endsWith('/suppressions');return {getResponseCode:()=>suppress&&failSuppression?503:200,getContentText:()=>JSON.stringify(suppress?{receipt_id:'receipt',committed_at:'2026-09-08T01:00:00Z'}:{row_id:target,version:2})};}},console};
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const generatedSheet=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const generatedHeaders=context.headers_({getLastColumn:()=>generatedSheet[0].length,getRange:()=>({getValues:()=>[generatedSheet[0]]})});
assert(generatedHeaders.row_id && generatedHeaders.status && generatedHeaders.occurred_at && generatedHeaders.save_state);
const pending={eventId:crypto.randomUUID(),suppressionKey:crypto.randomUUID(),actor:'operator@fixture.test',spreadsheetId:'private',sheetId:8,rowId:target,leadId:crypto.randomUUID(),createdAt:'2026-09-08T01:00:00Z',attempts:0,body:{expected_version:1,status:'do_not_contact_requested',attempts:0,invitation_state:'unknown',occurred_at:'2026-09-08T01:00:00Z'}};
context.submit_(pending);
assert(calls[0].url.endsWith('/v1/suppressions'));
assert(calls[1].url.endsWith('/v1/worklist-rows/'+target));
assert.strictEqual(rows[1][4],7);assert.strictEqual(rows[2][4],2);
const call=calls[0], h=call.options.headers;
const canonical=['POST','/v1/suppressions',h['X-Bridge-Timestamp'],pending.actor,pending.suppressionKey,call.options.payload].join('\n'.replace('\\n','\n'));
// Construct with actual newlines independently of bridge implementation.
const expected=crypto.createHmac('sha256','fixture-secret').update(['POST','/v1/suppressions',h['X-Bridge-Timestamp'],pending.actor,pending.suppressionKey,call.options.payload].join(String.fromCharCode(10))).digest('hex');
assert.strictEqual(h['X-Bridge-Signature'],expected);
assert.strictEqual(h.Authorization,'Bearer fixture-token');
calls=[];failSuppression=true;
assert.throws(()=>context.submit_(pending));assert.strictEqual(calls.length,1);
assert(props['pending:'+pending.eventId]);assert(rows[2][5].startsWith('Do not contact;'));
calls=[];props.ENABLED='false';assert.throws(()=>context.submit_(pending));assert.strictEqual(calls.length,0);
calls=[];props.ENABLED='true';failSuppression=false;
rows[2]=[target,crypto.randomUUID(),crypto.randomUUID(),crypto.randomUUID(),1,'','do_not_contact_requested',-1,'invalid',null,'x'.repeat(3000),'invalid date'];
context.onWorklistEdit({range:sheet.getRange(3,7),user:{getEmail:()=> 'operator@fixture.test'}});
assert(calls[0].url.endsWith('/v1/suppressions'));
const patch=JSON.parse(calls[1].options.payload);
assert.strictEqual(patch.notes,'');assert.strictEqual(patch.invitation_state,'unknown');assert.strictEqual(patch.attempts,0);
console.log('bridge fixture passed');
'''
    result = subprocess.run([node, "-e", harness, str(bridge), str(csv_fixture)], capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert "bridge fixture passed" in result.stdout


def test_generated_worklist_preserves_outcomes_and_matches_closed_schema(tmp_path):
    current = row(status="meeting_booked", attempts=3, invitation_state="invited",
                  invitation_evidence_ref="fixture-invitation-evidence", notes="Reviewed current outcome",
                  occurred_at=NOW - timedelta(hours=2), row_version=7)
    artifacts = render_report(context([current]), tmp_path)
    with artifacts["csv"].open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        exported = next(reader)
        assert tuple(reader.fieldnames) == CSV_FIELDS
    schema = json.loads((Path(__file__).resolve().parents[2] / "templates/worklist_schema.json").read_text())
    assert set(exported) == set(schema["properties"]) == set(schema["required"])
    assert exported["status"] == "meeting_booked" and exported["attempts"] == "3"
    assert exported["row_version"] == "7" and exported["notes"] == "Reviewed current outcome"
    assert exported["occurred_at"] == current.occurred_at.isoformat()
    assert exported["invitation_state"] == "invited" and exported["signal"] == "qbcc_backlog"
    assert "not actual revenue" in exported["signal_description"]
    assert exported["safe_contact_view"] == current.candidate_endpoint


def test_empty_worklist_still_has_complete_bridge_headers(tmp_path):
    artifacts = render_report(context([]), tmp_path)
    with artifacts["csv"].open(encoding="utf-8-sig", newline="") as stream:
        assert next(csv.reader(stream)) == list(CSV_FIELDS)
import csv
import json
