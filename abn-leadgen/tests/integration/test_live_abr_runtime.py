"""Actual isolated PostgreSQL and real public parser; tiny synthetic publisher bytes."""
# ruff: noqa: F811 -- pytest fixture import.
import hashlib
import io
import json
import zipfile
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from psycopg.types.json import Jsonb
from test_qbcc_review_stage import live as source_live  # noqa: F401

from abr_engine.compliance.policy import REQUIRED_GATES
from abr_engine.control.service import DomainError, Service
from abr_engine.db import transaction
from abr_engine.ingest.catalogue import CATALOGUES
from abr_engine.live import abr, abr_cleanup, sources
from abr_engine.ops import abr_analysis

RESOURCE_ID = "0ae4d427-6fa8-4d40-8e76-c6909b5a071b"
URL = f"https://data.gov.au/data/dataset/{CATALOGUES['abr'].dataset_id}/resource/{RESOURCE_ID}/download/public_split_1_1.zip"


def archive_bytes(*, gst="", status="ACT", name="Synthetic Construction", date="20260909"):
    body = (f'<ABR recordLastUpdatedDate="{date}" replaced="N"><ABN status="{status}" ABNStatusFromDate="20180131">51824753556</ABN>'
        '<EntityType><EntityTypeInd>PRV</EntityTypeInd><EntityTypeText>Australian Private Company</EntityTypeText></EntityType>'
        f'<MainEntity><NonIndividualName type="MN"><NonIndividualNameText>{name}</NonIndividualNameText></NonIndividualName>'
        '<BusinessAddress><AddressDetails><State>QLD</State><Postcode>4000</Postcode></AddressDetails></BusinessAddress></MainEntity>'
        + gst + '</ABR>')
    extracted = f"{date[:4]}-{date[4:6]}-{date[6:]}T12:20:57"
    xml = ('<Transfer error="none" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:noNamespaceSchemaLocation="BulkExtract.xsd"><TransferInfo><FileSequenceNumber>1</FileSequenceNumber>'
        f'<RecordCount>1</RecordCount><ExtractTime>{extracted}</ExtractTime></TransferInfo>{body}</Transfer>')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{date}_Public01.xml", xml)
    return output.getvalue()


@pytest.fixture
def prepared(settings, source_live, monkeypatch, tmp_path):
    config, _, keys = source_live
    config_path = tmp_path / "synthetic-abr-configuration.json"
    config = config.model_copy(update={"capabilities": {"abr": True, "retention": True}, "abr_config_file": config_path})
    for module in (abr, abr_cleanup, sources):
        monkeypatch.setattr(module, "transaction", lambda ignored: transaction(settings))
    original = abr._session_lock
    monkeypatch.setattr(abr, "_session_lock", lambda ignored, key: original(settings, key))
    monkeypatch.setattr(abr.shutil, "disk_usage", lambda ignored: SimpleNamespace(free=200 * abr.GIB))
    with transaction(settings) as conn:
        now = Service.now(conn)
        for scope in ("abr", "retention"):
            for gate in REQUIRED_GATES[scope]:
                conn.execute("INSERT INTO release_gate VALUES(%s,'pilot',%s,1,'synthetic-reviewed-scope',%s,'test-owner',%s,%s)",
                             (gate, scope, 'b' * 64, now - timedelta(minutes=1), now + timedelta(hours=2)))
        config_path.write_text(abr.ABRLiveConfig(operation="observe_only", source_scope_evidence_sha256='b'*64,
            mapping_evidence_sha256='b'*64, expires_at=now+timedelta(hours=1)).model_dump_json())
        conn.execute("INSERT INTO policy VALUES('synthetic-abr-observation','approved','pilot','synthetic-only',"
                     "'test-owner',%s,%s,%s)", (now - timedelta(minutes=1), now + timedelta(hours=2), Jsonb({
            "abr": {"approved": True, "operation": "observe_only", "classification_enabled": False,
                    "evidence_sha256": 'b'*64, "expires_at": (now + timedelta(hours=1)).isoformat()},
            "retention": {"approved": True, "schedule_version": "abr-v4-defaults", "retain_selected_evidence": False,
                          "evidence_sha256": 'b'*64},
        })))
    publisher = {"bytes": archive_bytes(), "etag": '"synthetic-one"', "hook": lambda request: None}
    calls = []
    def response(request):
        calls.append((request.method, str(request.url)))
        publisher["hook"](request)
        if str(request.url) == CATALOGUES['abr'].endpoint:
            return httpx.Response(200, json={"success": True, "result": {"id": CATALOGUES['abr'].dataset_id,
                "license_id": "cc-by", "resources": [{"id": RESOURCE_ID, "format": "ZIP", "url": URL,
                                                         "size": len(publisher['bytes'])}]}})
        assert str(request.url) == URL
        headers = {"etag": publisher['etag'], "last-modified": "Wed, 09 Sep 2026 12:20:57 GMT",
                   "content-length": str(len(publisher['bytes']))}
        return httpx.Response(200, headers=headers, stream=httpx.ByteStream(publisher['bytes'] if request.method == 'GET' else b''))
    runtime = abr.ABRRuntime(config, transport=httpx.MockTransport(response), sleep=lambda ignored: None)
    return runtime, publisher, calls, keys


def run(runtime):
    receipt = runtime.submit_run({"source": "abr", "request_id": str(uuid4())}, "synthetic-operator")
    assert receipt['state'] == 'queued', receipt
    return runtime.execute_job(receipt['job_id'])


def test_full_public_baseline_commits_zero_events_and_replays(settings, prepared):
    runtime, _, calls, _ = prepared
    receipt = run(runtime)
    assert receipt['state'] == 'complete', receipt
    assert receipt['result']['baseline'] is True and receipt['result']['record_count'] == 1
    assert receipt['result']['events'] == receipt['result']['candidates'] == 0
    assert receipt['result']['classification'] == 'disabled'
    assert receipt['result']['source_published_at'] is None
    assert receipt['result']['publisher_extract_time'] == '2026-09-09T12:20:57'
    assert len(calls) == 4
    assert runtime.execute_job(receipt['job_id']) == receipt and len(calls) == 4
    with transaction(settings) as conn:
        assert conn.execute("SELECT version FROM source_cursor WHERE source='abr'").fetchone()['version'] == 1
        for table in ('abr_event', 'lead_entity', 'candidate_queue', 'worklist_row', 'crm_outbox'):
            assert conn.execute(f"SELECT count(*) n FROM {table}").fetchone()['n'] == 0
        artifacts = conn.execute("SELECT * FROM artifact_manifest WHERE state='referenced'").fetchall()
        assert len(artifacts) == 4
        assert all(row['content_digest'] and row['byte_count'] for row in artifacts)


def test_next_complete_gst_diff_never_qualifies_a_candidate(settings, prepared):
    runtime, publisher, _, _ = prepared
    assert run(runtime)['state'] == 'complete'
    publisher['bytes'] = archive_bytes(gst='<GST status="ACT" GSTStatusFromDate="20260910"/>', date='20260910')
    publisher['etag'] = '"synthetic-two"'
    result = run(runtime)
    assert result['state'] == 'complete', result
    assert result['result']['baseline'] is False and result['result']['events'] == 1
    assert result['result']['candidates'] == 0
    with transaction(settings) as conn:
        assert conn.execute("SELECT event_type FROM abr_event").fetchone()['event_type'] == 'gst_registered'
        assert conn.execute("SELECT count(*) n FROM candidate_queue").fetchone()['n'] == 0


@pytest.mark.parametrize('gate', ['G1', 'G2', 'G3', 'G6', 'G7', 'retention', 'capability', 'policy'])
def test_closed_scope_never_requests_or_loads_keys(settings, prepared, monkeypatch, gate):
    runtime, _, calls, _ = prepared
    with transaction(settings) as conn:
        if gate == 'capability':
            runtime.settings = runtime.settings.model_copy(update={'capabilities': {'collection': True}})
        elif gate == 'policy':
            conn.execute("UPDATE policy SET settings='{}'")
        elif gate == 'retention':
            conn.execute("DELETE FROM release_gate WHERE scope='retention'")
        else:
            conn.execute("DELETE FROM release_gate WHERE scope='abr' AND gate_name=%s", (gate,))
    monkeypatch.setattr(abr, 'load_keys', lambda ignored: pytest.fail('keys before authority'))
    receipt = runtime.submit_run({'source': 'abr'}, 'synthetic-operator')
    assert receipt['state'] == 'held' and receipt['result'] is None and calls == []


def test_withdrawal_after_download_stops_before_more_http_or_cursor(settings, prepared):
    runtime, publisher, calls, _ = prepared
    def withdraw(request):
        if str(request.url) == URL and request.method == 'GET':
            with transaction(settings) as conn:
                conn.execute("INSERT INTO release_gate SELECT gate_name,environment,scope,2,evidence_ref,evidence_sha256,"
                    "actor_id,clock_timestamp()-interval '2 days',clock_timestamp()-interval '1 day' "
                    "FROM release_gate WHERE scope='abr' AND gate_name='G1'")
    publisher['hook'] = withdraw
    receipt = run(runtime)
    assert receipt['state'] == 'held' and receipt['reason_codes'] == ['GATE_G1_CLOSED']
    assert len(calls) == 2
    with transaction(settings) as conn:
        assert conn.execute('SELECT count(*) n FROM source_cursor').fetchone()['n'] == 0


def test_insufficient_capacity_is_held_before_first_http(prepared, monkeypatch):
    runtime, _, calls, _ = prepared
    monkeypatch.setattr(abr.shutil, 'disk_usage', lambda ignored: SimpleNamespace(free=72*abr.GIB))
    result = run(runtime)
    assert result['reason_codes'] == ['ABR_CAPACITY_HEADROOM_REQUIRED'] and calls == []


def test_facade_admits_without_inline_abr_work(prepared, monkeypatch):
    runtime, _, calls, _ = prepared
    facade = sources.SourceRuntime(runtime.settings, transport=runtime.transport)
    monkeypatch.setattr(abr.ABRRuntime, 'execute_job', lambda *args: pytest.fail('ABR in web process'))
    receipt = facade.submit_run({'source': 'abr'}, 'synthetic-operator')
    assert facade.kick_job(receipt['job_id'])['state'] == 'queued' and calls == []
    with pytest.raises(DomainError, match='EXACT_LIVE_SOURCE_REQUIRED'):
        facade.submit_run({'source': 'all'}, 'synthetic-operator')


def test_mapping_and_policy_expiry_are_rechecked_for_admitted_job(settings, prepared):
    runtime, _, calls, _ = prepared
    receipt = runtime.submit_run({'source': 'abr'}, 'synthetic-operator')
    with transaction(settings) as conn:
        conn.execute("INSERT INTO release_gate SELECT gate_name,environment,scope,2,evidence_ref,%s,actor_id,approved_at,expires_at "
                     "FROM release_gate WHERE scope='abr' AND gate_name='G2'", ('c'*64,))
    result = runtime.execute_job(receipt['job_id'])
    assert result['reason_codes'] == ['ABR_EVIDENCE_BINDING_CHANGED'] and calls == []


def test_duplicate_request_is_not_a_second_job(prepared):
    runtime, _, calls, _ = prepared
    payload = {'source': 'abr', 'request_id': str(uuid4())}
    first = runtime.submit_run(payload, 'synthetic-operator')
    assert runtime.submit_run(payload, 'synthetic-operator') == first and calls == []
    with pytest.raises(DomainError, match='IDEMPOTENCY_CONFLICT'):
        runtime.submit_run(payload, 'another-operator')


def test_baseline_cancelled_existing_qbcc_identity_is_restricted_without_profile_refresh(settings, prepared):
    runtime, publisher, _, keys = prepared
    with transaction(settings) as conn:
        service = Service(runtime.settings, keys)
        lead = service.create_lead(conn, name='Existing reviewed QBCC business', source='qbcc', alias='SYNTHETIC-ONLY', abn='51824753556')
        old = conn.execute('SELECT * FROM lead_entity').fetchone()
    publisher['bytes'] = archive_bytes(status='CAN')
    result = run(runtime)
    assert result['state'] == 'complete', result
    assert result['result']['events'] == result['result']['candidates'] == 0
    with transaction(settings) as conn:
        assert service.restricted(conn, lead['group_id']) == ['SUPPRESSED_CANCELLATION']
        current = conn.execute('SELECT * FROM lead_entity').fetchone()
        assert current['display_name'] == old['display_name'] and current['fields'] == old['fields']
        assert conn.execute("SELECT count(*) n FROM lead_entity WHERE source='abr'").fetchone()['n'] == 0


def test_full_analysis_does_not_hold_staff_control_lock(settings, prepared, monkeypatch):
    runtime, _, _, _ = prepared
    original = abr_analysis.parquet_fill
    checks = []
    def quality(*args, **kwargs):
        value = int.from_bytes(hashlib.sha256((settings.schema_name + ':control-authority').encode()).digest()[:8], 'big', signed=True)
        with transaction(settings) as conn:
            checks.append(conn.execute('SELECT pg_try_advisory_xact_lock(%s) acquired', (value,)).fetchone()['acquired'])
        return original(*args, **kwargs)
    monkeypatch.setattr(abr_analysis, 'parquet_fill', quality)
    result = run(runtime)
    assert result['state'] == 'complete', result
    assert checks and all(checks)


def test_event_limit_rejects_before_any_cursor_or_event_change(settings, prepared):
    runtime, publisher, _, _ = prepared
    assert run(runtime)['state'] == 'complete'
    values = json.loads(runtime.settings.abr_config_file.read_text())
    values['max_events'] = 0
    runtime.settings.abr_config_file.write_text(json.dumps(values))
    publisher['bytes'] = archive_bytes(name='Changed synthetic name', date='20260910')
    result = run(runtime)
    assert result['state'] == 'held' and result['reason_codes'] == ['ABR_EVENT_COUNT_LIMIT'], result
    with transaction(settings) as conn:
        assert conn.execute("SELECT version FROM source_cursor WHERE source='abr'").fetchone()['version'] == 1
        assert conn.execute('SELECT count(*) n FROM abr_event').fetchone()['n'] == 0


@pytest.mark.parametrize('stage', ['before_commit', 'after_commit'])
def test_process_death_replays_prepared_or_committed_without_another_download(settings, prepared, monkeypatch, stage):
    runtime, _, calls, _ = prepared
    original = runtime._commit
    class ProcessDeath(BaseException):
        pass
    def interrupted(*args, **kwargs):
        if stage == 'before_commit':
            raise ProcessDeath()
        original(*args, **kwargs)
        raise ProcessDeath()
    monkeypatch.setattr(runtime, '_commit', interrupted)
    receipt = runtime.submit_run({'source': 'abr'}, 'synthetic-operator')
    with pytest.raises(ProcessDeath):
        runtime.execute_job(receipt['job_id'])
    assert len(calls) == 4
    monkeypatch.setattr(runtime, '_commit', original)
    if stage == 'after_commit':
        with transaction(settings) as conn:
            conn.execute("DELETE FROM release_gate WHERE scope='abr'")
    result = runtime.execute_job(receipt['job_id'])
    assert result['state'] == 'complete' and result['result']['baseline'] is True and len(calls) == 4
    with transaction(settings) as conn:
        assert conn.execute("SELECT version FROM source_cursor WHERE source='abr'").fetchone()['version'] == 1


def test_file_changed_after_analysis_never_commits(settings, prepared, monkeypatch):
    runtime, _, _, _ = prepared
    original = abr_analysis.prepare_analysis
    def changed(*args, **kwargs):
        analysis = original(*args, **kwargs)
        from pathlib import Path
        with Path(analysis.paths[0]).open('ab') as stream:
            stream.write(b'changed-after-verified-analysis')
        return analysis
    monkeypatch.setattr(abr_analysis, 'prepare_analysis', changed)
    result = run(runtime)
    assert result['state'] == 'held' and result['reason_codes'] == ['ANALYSED_ARTIFACT_CHANGED']
    with transaction(settings) as conn:
        assert conn.execute('SELECT count(*) n FROM source_snapshot').fetchone()['n'] == 0


def test_config_replacement_after_analysis_is_rechecked_at_commit(settings, prepared, monkeypatch):
    runtime, _, _, _ = prepared
    original = abr_analysis.prepare_analysis
    def changed(*args, **kwargs):
        analysis = original(*args, **kwargs)
        values = json.loads(runtime.settings.abr_config_file.read_text())
        values['max_events'] -= 1
        runtime.settings.abr_config_file.write_text(json.dumps(values))
        return analysis
    monkeypatch.setattr(abr_analysis, 'prepare_analysis', changed)
    result = run(runtime)
    assert result['state'] == 'held' and result['reason_codes'] == ['ABR_LIVE_CONFIGURATION_CHANGED']
    with transaction(settings) as conn:
        assert conn.execute('SELECT count(*) n FROM source_cursor').fetchone()['n'] == 0


def test_restart_cannot_reset_total_job_deadline(settings, prepared):
    runtime, _, calls, _ = prepared
    receipt = runtime.submit_run({'source':'abr'}, 'synthetic-operator')
    with transaction(settings) as conn:
        conn.execute("UPDATE pipeline_run SET started_at=clock_timestamp()-interval '7 hours' WHERE run_id=%s", (receipt['job_id'],))
    result = runtime.execute_job(receipt['job_id'])
    assert result['state'] == 'held' and result['reason_codes'] == ['ABR_RUN_DEADLINE'] and calls == []


@pytest.mark.parametrize('failure', ['aggregate_limit', 'foreign_namespace'])
def test_restart_storage_counts_all_owned_attempts_and_refuses_foreign_scope(settings, prepared, monkeypatch, failure):
    runtime, _, calls, _ = prepared
    job = runtime.submit_run({'source': 'abr'}, 'synthetic-operator')
    for _ in range(2):
        directory = abr_cleanup.reserve_attempt(runtime.settings, UUID(job['job_id']), abr.safe_root(runtime.settings))
        (directory / 'retained-part.tmp').write_bytes(b'x' * 30)
    if failure == 'aggregate_limit':
        # Lower the synthetic in-memory threshold; never allocate48GiB in tests.
        config = abr.load_config(runtime.settings).model_copy(update={'max_working_bytes': 50})
        monkeypatch.setattr(abr, 'load_config', lambda ignored: config)
    else:
        with transaction(settings) as conn:
            record = conn.execute('SELECT manifest FROM pipeline_run WHERE run_id=%s', (job['job_id'],)).fetchone()
            entries = record['manifest']['attempt_namespaces']
            entries[0]['relative_directory'] = '../unowned'
            conn.execute('UPDATE pipeline_run SET manifest=manifest||%s WHERE run_id=%s',
                         (Jsonb({'attempt_namespaces': entries}), job['job_id']))
    result = runtime.execute_job(job['job_id'])
    expected = 'ABR_WORKING_STORAGE_LIMIT' if failure == 'aggregate_limit' else 'ABR_NAMESPACE_INVALID'
    assert result['state'] == 'held' and result['reason_codes'] == [expected] and calls == [], result
    with transaction(settings) as conn:
        assert conn.execute('SELECT count(*) n FROM source_cursor').fetchone()['n'] == 0


def test_restart_below_aggregate_storage_limit_still_accepts_real_parsed_baseline(settings, prepared, monkeypatch):
    runtime, _, calls, _ = prepared
    job = runtime.submit_run({'source': 'abr'}, 'synthetic-operator')
    earlier = abr_cleanup.reserve_attempt(runtime.settings, UUID(job['job_id']), abr.safe_root(runtime.settings))
    (earlier / 'retained-part.tmp').write_bytes(b'x' * 30)
    config = abr.load_config(runtime.settings).model_copy(update={'max_working_bytes': 1024**2})
    monkeypatch.setattr(abr, 'load_config', lambda ignored: config)
    result = runtime.execute_job(job['job_id'])
    assert result['state'] == 'complete' and result['result']['baseline'] is True, result
    assert result['result']['events'] == result['result']['candidates'] == 0 and len(calls) == 4


def test_transient_http_failure_uses_existing_bounded_retry(prepared):
    runtime, publisher, calls, _ = prepared
    failed = False
    def transient(request):
        nonlocal failed
        if str(request.url) == URL and request.method == 'GET' and not failed:
            failed = True
            raise httpx.ReadTimeout('synthetic-only timeout')
    publisher['hook'] = transient
    result = run(runtime)
    assert result['state'] == 'complete' and len(calls) == 5


@pytest.mark.parametrize('phase', ['discovering','downloading','validating','parsing','diffing','promoting'])
def test_inflight_receipt_preserves_phase_and_normalises_running(prepared, phase):
    runtime, _, _, _ = prepared
    job = runtime.submit_run({'source':'abr'},'synthetic-operator')
    runtime._record(job['job_id'], phase=phase)
    receipt = runtime.get_job(job['job_id'])
    assert receipt['state'] == 'running' and receipt['phase'] == phase and receipt['result'] is None
