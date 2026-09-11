"""Interrupted real-file namespaces, isolated PostgreSQL; no publisher/provider I/O."""
# ruff: noqa: F811 -- imported pytest fixtures.
import hashlib
import os
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from psycopg.types.json import Jsonb
from test_live_abr_runtime import prepared, run  # noqa: F401
from test_qbcc_review_stage import live as source_live  # noqa: F401

from abr_engine.compliance.retention import artifact_retention
from abr_engine.control.service import Service
from abr_engine.db import transaction
from abr_engine.live import abr_cleanup as cleanup
from abr_engine.ops.promotion import declare_artifact, source_lock_key
from abr_engine.pipeline import process_lock, safe_root


@pytest.fixture
def subject(settings, prepared, monkeypatch):
    runtime, _, calls, keys = prepared
    original = cleanup._session_lock
    monkeypatch.setattr(cleanup, '_session_lock', lambda ignored, key: original(settings, key))
    return runtime, calls, Service(runtime.settings, keys)


def reserve(runtime):
    job = runtime.submit_run({'source': 'abr', 'request_id': str(uuid4())}, 'synthetic-operator')
    path = cleanup.reserve_attempt(runtime.settings, UUID(job['job_id']), safe_root(runtime.settings))
    return job, path


def age(settings, job, paths=(), *, state='held', days=8):
    with transaction(settings) as conn:
        start = Service.now(conn) - timedelta(days=days)
        record = conn.execute('SELECT manifest FROM pipeline_run WHERE run_id=%s', (job['job_id'],)).fetchone()
        entries = [{**entry, 'created_at': (start + timedelta(seconds=1)).isoformat()}
                   for entry in record['manifest']['attempt_namespaces']]
        conn.execute('UPDATE pipeline_run SET state=%s,started_at=%s,manifest=manifest||%s WHERE run_id=%s',
            (state, start, Jsonb({'attempt_namespaces': entries}), job['job_id']))
    for path in paths:
        os.utime(path, ((start + timedelta(seconds=2)).timestamp(),) * 2)
    return start


def reconcile(runtime, job, **kwargs):
    return cleanup.reconcile_attempts(runtime.settings, job_id=job['job_id'], execute=True, **kwargs)


def test_reservation_is_committed_and_empty_before_inode_seal(settings, subject, monkeypatch):
    runtime, calls, _ = subject
    real_sync = cleanup._sync_directory
    checked = []
    def inspect(path):
        with transaction(settings) as conn:
            row = conn.execute("SELECT manifest FROM pipeline_run WHERE manifest ? 'attempt_namespaces'").fetchone()
            assert row['manifest']['attempt_namespaces'][-1]['state'] == 'reserved'
        assert not list(path.iterdir()) if path.name.count('-') == 4 and path.parent.name.count('-') == 4 else True
        checked.append(path)
        real_sync(path)
    monkeypatch.setattr(cleanup, '_sync_directory', inspect)
    job, directory = reserve(runtime)
    with transaction(settings) as conn:
        entry = conn.execute('SELECT manifest FROM pipeline_run WHERE run_id=%s', (job['job_id'],)).fetchone()['manifest']['attempt_namespaces'][0]
    assert entry['state'] == 'owned' and entry['inode'] == directory.stat().st_ino
    assert checked == [directory, directory.parent] and calls == []


def test_unknown_spill_part_and_partial_are_registered_with_original_age_then_expire(settings, subject):
    runtime, calls, service = subject
    job, directory = reserve(runtime)
    paths = [directory / 'spill' / 'duckdb_temp_storage-0.tmp', directory / 'events' / 'part-0001.parquet', directory / 'resource-0.zip.partial']
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'private synthetic working bytes')
    start = age(settings, job, paths)
    result = reconcile(runtime, job)
    assert result['status'] == 'complete' and result['runs'][0]['registered'] == 3, result
    with transaction(settings) as conn:
        rows = conn.execute('SELECT * FROM artifact_manifest ORDER BY local_path').fetchall()
        assert len(rows) == 3
        assert all(row['state'] == 'orphan' and row['created_at'] == start + timedelta(seconds=2) for row in rows)
        assert all(row['content_digest'] == hashlib.sha256(paths[0].read_bytes()).hexdigest() for row in rows)
        deleted = artifact_retention(conn, service, now=Service.now(conn), execute=True)
    assert len(deleted) == 3 and all(row['state'] == 'deleted' for row in deleted), deleted
    assert all(not path.exists() for path in paths) and calls == []


def test_declared_writing_partial_keeps_ledger_age_and_can_expire(settings, subject):
    runtime, _, service = subject
    job, directory = reserve(runtime)
    path = directory / 'resource-0.zip.partial'
    path.write_bytes(b'incomplete raw transfer')
    start = age(settings, job, [path])
    with transaction(settings) as conn:
        owned = declare_artifact(conn, UUID(job['job_id']), 'abr', path, artifact_class='raw')
        conn.execute('UPDATE artifact_manifest SET created_at=%s WHERE artifact_id=%s', (start + timedelta(seconds=1), owned['artifact_id']))
    assert reconcile(runtime, job)['runs'][0]['registered'] == 1
    with transaction(settings) as conn:
        row = conn.execute('SELECT * FROM artifact_manifest').fetchone()
        assert row['byte_count'] == path.stat().st_size and row['created_at'] == start + timedelta(seconds=1)
        assert artifact_retention(conn, service, now=Service.now(conn), execute=True)[0]['state'] == 'deleted'


@pytest.mark.parametrize('kind', ['foreign_namespace', 'hardlink', 'symlink', 'unsealed_payload'])
def test_foreign_and_linked_payloads_are_never_adopted(settings, subject, tmp_path, kind):
    runtime, _, _ = subject
    job, directory = reserve(runtime)
    outside = tmp_path / 'foreign-private.txt'
    outside.write_bytes(b'must remain untouched')
    if kind == 'foreign_namespace':
        with transaction(settings) as conn:
            row = conn.execute('SELECT manifest FROM pipeline_run WHERE run_id=%s', (job['job_id'],)).fetchone()
            entry = {**row['manifest']['attempt_namespaces'][0], 'relative_directory': '../foreign-private.txt'}
            conn.execute('UPDATE pipeline_run SET manifest=manifest||%s WHERE run_id=%s', (Jsonb({'attempt_namespaces': [entry]}), job['job_id']))
    elif kind == 'unsealed_payload':
        (directory / 'unexpected.bin').write_bytes(b'unowned')
        with transaction(settings) as conn:
            row = conn.execute('SELECT manifest FROM pipeline_run WHERE run_id=%s', (job['job_id'],)).fetchone()
            entry = {**row['manifest']['attempt_namespaces'][0], 'state': 'reserved'}
            conn.execute('UPDATE pipeline_run SET manifest=manifest||%s WHERE run_id=%s', (Jsonb({'attempt_namespaces': [entry]}), job['job_id']))
    elif kind == 'hardlink':
        os.link(outside, directory / 'linked.txt')
    else:
        try:
            (directory / 'linked.txt').symlink_to(outside)
        except OSError:
            pytest.skip('Host does not grant symlink creation')
    age(settings, job)
    receipt = reconcile(runtime, job)
    assert receipt['status'] == 'complete_with_holds' and receipt['runs'][0]['state'] == 'held', receipt
    with transaction(settings) as conn:
        assert conn.execute('SELECT count(*) n FROM artifact_manifest').fetchone()['n'] == 0
    assert outside.read_bytes() == b'must remain untouched'


def test_current_retention_survives_source_withdrawal_but_not_retention_withdrawal(settings, subject):
    runtime, _, _ = subject
    job, directory = reserve(runtime)
    path = directory / 'spill.tmp'
    path.write_bytes(b'synthetic')
    age(settings, job, [path])
    runtime.settings = runtime.settings.model_copy(update={'capabilities': {'retention': True}, 'abr_config_file': None})
    with transaction(settings) as conn:
        conn.execute("DELETE FROM release_gate WHERE scope='abr'")
    assert reconcile(runtime, job)['runs'][0]['registered'] == 1
    second = directory / 'spill2.tmp'
    second.write_bytes(b'synthetic2')
    with transaction(settings) as conn:
        conn.execute("INSERT INTO release_gate SELECT gate_name,environment,scope,2,evidence_ref,evidence_sha256,actor_id,"
                     "clock_timestamp()-interval '2 days',clock_timestamp()-interval '1 day' FROM release_gate WHERE scope='retention' AND gate_name='G1'")
    result = reconcile(runtime, job)
    assert result['status'] == 'held' and result['reason_codes'] == ['GATE_G1_CLOSED']
    with transaction(settings) as conn:
        assert conn.execute('SELECT count(*) n FROM artifact_manifest').fetchone()['n'] == 1


def test_hashing_releases_staff_lock_and_withdrawal_prevents_ledger_write(settings, subject, monkeypatch):
    runtime, _, _ = subject
    job, directory = reserve(runtime)
    path = directory / 'spill.tmp'
    path.write_bytes(b'synthetic')
    age(settings, job, [path])
    original = cleanup.digest_file
    checked = []
    def withdraw(path, **kwargs):
        with transaction(settings) as conn:
            lock_key = int.from_bytes(hashlib.sha256((settings.schema_name + ':control-authority').encode()).digest()[:8], 'big', signed=True)
            assert conn.execute('SELECT pg_try_advisory_xact_lock(%s) ok', (lock_key,)).fetchone()['ok']
            conn.execute("INSERT INTO release_gate SELECT gate_name,environment,scope,2,evidence_ref,evidence_sha256,actor_id,"
                "clock_timestamp()-interval '2 days',clock_timestamp()-interval '1 day' FROM release_gate WHERE scope='retention' AND gate_name='G1'")
        checked.append(True)
        return original(path, **kwargs)
    monkeypatch.setattr(cleanup, 'digest_file', withdraw)
    result = reconcile(runtime, job)
    assert result['runs'][0]['reason_codes'] == ['GATE_G1_CLOSED'] and checked == [True], result
    with transaction(settings) as conn:
        assert conn.execute('SELECT count(*) n FROM artifact_manifest').fetchone()['n'] == 0


def test_fresh_or_locked_worker_cannot_be_reconciled(settings, subject):
    runtime, _, _ = subject
    job, directory = reserve(runtime)
    (directory / 'spill.tmp').write_bytes(b'in flight')
    assert reconcile(runtime, job)['runs'][0]['state'] == 'active'
    with process_lock(safe_root(runtime.settings) / 'abr-live-worker.lock'):
        result = reconcile(runtime, job)
        assert result['reason_codes'] == ['PROCESS_STAGE_LOCK_BUSY']
    with cleanup._session_lock(runtime.settings, source_lock_key('abr-live-worker', runtime.settings.schema_name)):
        result = reconcile(runtime, job)
        assert result['reason_codes'] == ['SOURCE_STAGE_LOCK_BUSY']
    with transaction(settings) as conn:
        assert conn.execute('SELECT count(*) n FROM artifact_manifest').fetchone()['n'] == 0


def test_new_artifact_hold_during_hash_preserves_unverified_ledger(settings, subject, monkeypatch):
    runtime, _, _ = subject
    job, directory = reserve(runtime)
    path = directory / 'resource-0.zip.partial'
    path.write_bytes(b'interrupted raw transfer')
    age(settings, job, [path])
    with transaction(settings) as conn:
        before = declare_artifact(conn, UUID(job['job_id']), 'abr', path, artifact_class='raw')
    original = cleanup.digest_file
    def insert_hold(path, **kwargs):
        with transaction(settings) as conn:
            conn.execute("INSERT INTO retention_hold VALUES(%s,'artifact',%s,'synthetic-owner','synthetic hold',clock_timestamp()+interval '1 day')",
                         (uuid4(), str(before['artifact_id'])))
        return original(path, **kwargs)
    monkeypatch.setattr(cleanup, 'digest_file', insert_hold)
    result = reconcile(runtime, job)
    assert result['runs'][0]['reason_codes'] == ['ARTIFACT_ACTIVE_OR_HELD'], result
    with transaction(settings) as conn:
        assert conn.execute('SELECT * FROM artifact_manifest').fetchone() == before
    assert path.read_bytes() == b'interrupted raw transfer'


def test_reappearing_deleted_artifact_cannot_rewrite_deletion_history(settings, subject):
    runtime, _, _ = subject
    job, directory = reserve(runtime)
    path = directory / 'reappeared.tmp'
    path.write_bytes(b'reappearing private bytes')
    age(settings, job, [path])
    with transaction(settings) as conn:
        row = declare_artifact(conn, UUID(job['job_id']), 'abr', path, artifact_class='manifest')
        before = conn.execute("UPDATE artifact_manifest SET state='deleted',deletion_reason='finite_retention' WHERE artifact_id=%s RETURNING *",
                              (row['artifact_id'],)).fetchone()
    result = reconcile(runtime, job)
    assert result['runs'][0]['reason_codes'] == ['ARTIFACT_PREVIOUSLY_DELETED'], result
    with transaction(settings) as conn:
        assert conn.execute('SELECT * FROM artifact_manifest').fetchone() == before
    assert path.read_bytes() == b'reappearing private bytes'


def test_stale_running_job_has_finite_cleanup_and_preview_does_not_mutate(settings, subject):
    runtime, _, _ = subject
    job, directory = reserve(runtime)
    path = directory / 'sqlite-index.sqlite-journal'
    path.write_bytes(b'interrupted journal')
    age(settings, job, [path], state='running')
    preview = cleanup.reconcile_attempts(runtime.settings, execute=False, job_id=job['job_id'])
    assert preview['runs'][0]['state'] == 'preview_interruption'
    with transaction(settings) as conn:
        assert conn.execute('SELECT state FROM pipeline_run WHERE run_id=%s', (job['job_id'],)).fetchone()['state'] == 'running'
    result = reconcile(runtime, job)
    assert result['runs'][0]['registered'] == 1
    assert runtime.get_job(job['job_id'])['reason_codes'] == ['ABR_RUN_DEADLINE']


def test_accepted_artifacts_remain_referenced_and_unchanged(settings, subject):
    runtime, _, _ = subject
    result = run(runtime)
    assert result['state'] == 'complete', result
    with transaction(settings) as conn:
        before = conn.execute('SELECT * FROM artifact_manifest ORDER BY artifact_id').fetchall()
    reconciled = reconcile(runtime, result)
    assert reconciled['runs'][0]['registered'] == 0, reconciled
    with transaction(settings) as conn:
        after = conn.execute('SELECT * FROM artifact_manifest ORDER BY artifact_id').fetchall()
    assert before == after and all(Path(row['local_path']).exists() for row in after if row['state'] == 'referenced')


def test_unsealed_empty_crash_namespace_is_safe_and_bounded(settings, subject, monkeypatch):
    runtime, _, _ = subject
    job = runtime.submit_run({'source': 'abr'}, 'synthetic-operator')
    monkeypatch.setattr(cleanup, '_sync_directory', lambda path: (_ for _ in ()).throw(RuntimeError('synthetic crash')))
    with pytest.raises(RuntimeError, match='synthetic crash'):
        cleanup.reserve_attempt(runtime.settings, UUID(job['job_id']), safe_root(runtime.settings))
    age(settings, job)
    result = reconcile(runtime, job)
    assert result['runs'][0]['state'] == 'reconciled' and result['runs'][0]['registered'] == 0, result


@pytest.mark.parametrize('held', [False, True])
def test_scheduled_maintenance_reconciles_then_expires_large_spill_or_preserves_hold(settings, subject, monkeypatch, held):
    from abr_engine.live import artifact_retention as artifacts
    from abr_engine.live import schedule
    runtime, calls, _ = subject
    for module in (artifacts, schedule):
        monkeypatch.setattr(module, 'transaction', lambda ignored: transaction(settings))
    job, directory = reserve(runtime)
    path = directory / 'large-spill.tmp'
    with path.open('wb') as stream:
        for _ in range(17):
            stream.write(b'x' * 1024**2)
    age(settings, job, [path])
    if held:
        with transaction(settings) as conn:
            conn.execute("INSERT INTO retention_hold VALUES(%s,'pipeline_run',%s,'synthetic-owner','synthetic hold',clock_timestamp()+interval '1 day')",
                         (uuid4(), job['job_id']))
    result = schedule.maintenance(runtime.settings, kind='retention', execute=True)
    assert result['status'] == ('held' if held else 'complete'), result
    assert path.exists() is held and calls == []
    if not held:
        assert result['result']['abr_namespaces']['runs'][0]['registered'] == 1
        assert result['result']['artifacts'][0]['state'] == 'deleted'
