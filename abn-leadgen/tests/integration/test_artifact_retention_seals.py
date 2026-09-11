"""Real PG authority with synthetic local files; no live source or provider access."""
# ruff: noqa: F811 -- pytest fixture import.
import hashlib
import os
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from test_qbcc_review_stage import live as source_live  # noqa: F401
from test_retention import artifact

from abr_engine.compliance import retention
from abr_engine.control.service import DomainError, Service
from abr_engine.db import transaction
from abr_engine.live import artifact_retention as seals


@pytest.fixture
def managed(settings, source_live, monkeypatch):
    config, _, keys = source_live
    config = config.model_copy(update={'capabilities': {'retention': True}})
    config.output_dir.mkdir()
    monkeypatch.setattr(seals, 'transaction', lambda ignored: transaction(settings))
    with transaction(settings) as conn:
        now = Service.now(conn)
        for gate in ('G1', 'G3', 'G7'):
            conn.execute("INSERT INTO release_gate VALUES(%s,'pilot','retention',1,'synthetic-retention',%s,"
                "'synthetic-owner',%s,%s)", (gate, 'b'*64, now-timedelta(minutes=1), now+timedelta(hours=2)))
        conn.execute("INSERT INTO policy VALUES('synthetic-retention','approved','pilot','synthetic-retention',"
            "'synthetic-owner',%s,%s,%s)", (now-timedelta(minutes=1), now+timedelta(hours=2), Jsonb({
                'retention': {'approved': True, 'schedule_version': 'abr-v4-defaults',
                              'evidence_sha256': 'b'*64, 'retain_selected_evidence': False}})))
    return Service(config, keys)


def create(settings, service, name='raw.zip', *, size=20, snapshot=False, age=91):
    path = service.settings.output_dir / name
    path.write_bytes(b'x' * size)
    with transaction(settings) as conn:
        identifier = artifact(conn, service, path, 'snapshot' if snapshot else 'raw', snapshot=snapshot, age=age)
        now = Service.now(conn)
    return path, identifier, now


def finish(settings, service, prepared, now):
    with transaction(settings) as conn:
        return retention.artifact_retention(conn, service, now=now, execute=True, prepared=prepared,
                                            artifact_ids=list(prepared.files))


def test_large_hash_does_not_hold_control_authority(settings, managed, monkeypatch):
    path, identifier, now = create(settings, managed, size=17*1024**2)
    real_sha256 = hashlib.sha256
    acquired = []
    class ObservedHash:
        def __init__(self):
            self.value = real_sha256()
        def update(self, data):
            if not acquired:
                key = int.from_bytes(real_sha256((settings.schema_name+':control-authority').encode()).digest()[:8],
                                     'big', signed=True)
                with transaction(settings) as conn:
                    acquired.append(conn.execute('SELECT pg_try_advisory_xact_lock(%s) acquired', (key,)).fetchone()['acquired'])
            self.value.update(data)
        def hexdigest(self):
            return self.value.hexdigest()
    monkeypatch.setattr(seals, 'hashlib', SimpleNamespace(sha256=ObservedHash))
    prepared = seals.prepare_artifact_retention(managed, now=now)
    assert acquired == [True] and str(identifier) in prepared.files and path.exists(), prepared.files
    # The final transaction must use the sealed digest, never read the bytes again.
    monkeypatch.setattr(retention, 'hashlib', SimpleNamespace(sha256=lambda: pytest.fail('hash under authority')))
    assert finish(settings, managed, prepared, now)[0]['state'] == 'deleted'
    assert not path.exists()


@pytest.mark.parametrize('change', ['artifact_hold', 'run_hold', 'pipeline_run_hold', 'snapshot_hold', 'running', 'reference'])
def test_current_holds_runs_and_new_references_override_seal(settings, managed, change):
    path, identifier, now = create(settings, managed, snapshot=change=='snapshot_hold')
    prepared = seals.prepare_artifact_retention(managed, now=now)
    with transaction(settings) as conn:
        row = conn.execute('SELECT * FROM artifact_manifest WHERE artifact_id=%s', (identifier,)).fetchone()
        if change.endswith('_hold'):
            kind = change.removesuffix('_hold')
            target = row[{'artifact': 'artifact_id', 'run': 'run_id', 'pipeline_run': 'run_id', 'snapshot': 'snapshot_id'}[kind]]
            conn.execute("INSERT INTO retention_hold VALUES(%s,%s,%s,'synthetic-owner','new hold',clock_timestamp())",
                         (uuid4(), kind, str(target)))
        elif change == 'running':
            conn.execute("UPDATE pipeline_run SET state='running' WHERE run_id=%s", (row['run_id'],))
        else:
            artifact(conn, managed, path, 'raw', age=1)
    result = finish(settings, managed, prepared, now)
    assert result[0]['state'] == 'held' and path.exists()
    assert result[0]['reason'] in {'ARTIFACT_ACTIVE_OR_HELD', 'ARTIFACT_STILL_REFERENCED'}


@pytest.mark.parametrize('change', ['replacement', 'same_inode', 'ledger', 'hardlink', 'missing_then_created'])
def test_file_or_ledger_change_after_seal_never_deletes(settings, managed, change):
    path, identifier, now = create(settings, managed)
    if change == 'missing_then_created':
        path.unlink()
    prepared = seals.prepare_artifact_retention(managed, now=now)
    if change == 'replacement':
        replacement = path.with_suffix('.replacement')
        replacement.write_bytes(path.read_bytes())
        os.replace(replacement, path)
    elif change == 'same_inode':
        path.write_bytes(b'z'*20)
    elif change == 'hardlink':
        os.link(path, path.with_suffix('.alias'))
    elif change == 'missing_then_created':
        path.write_bytes(b'x'*20)
    else:
        with transaction(settings) as conn:
            conn.execute("UPDATE artifact_manifest SET content_digest=%s WHERE artifact_id=%s", ('a'*64, identifier))
    result = finish(settings, managed, prepared, now)
    assert result[0]['state'] == 'held' and path.exists()
    assert result[0]['reason'] in {'ARTIFACT_PREVALIDATION_CHANGED', 'ARTIFACT_LINK_REFUSED'}


def test_current_retention_withdrawal_blocks_but_source_withdrawal_does_not(settings, managed):
    path, _, now = create(settings, managed)
    prepared = seals.prepare_artifact_retention(managed, now=now)
    # No collection/ABR capability is present. Its expired approval cannot veto finite deletion.
    with transaction(settings) as conn:
        conn.execute("UPDATE release_gate SET expires_at=clock_timestamp()-interval '1 second',"
                     "approved_at=clock_timestamp()-interval '2 seconds' WHERE scope='collection'")
    assert finish(settings, managed, prepared, now)[0]['state'] == 'deleted' and not path.exists()
    path, _, now = create(settings, managed, 'second.zip')
    prepared = seals.prepare_artifact_retention(managed, now=now)
    with transaction(settings) as conn:
        conn.execute("INSERT INTO release_gate SELECT gate_name,environment,scope,2,evidence_ref,evidence_sha256,"
                     "actor_id,clock_timestamp()-interval '2 seconds',clock_timestamp()-interval '1 second' "
                     "FROM release_gate WHERE scope='retention' AND gate_name='G1'")
    with pytest.raises(DomainError, match='GATE_G1_CLOSED'):
        finish(settings, managed, prepared, now)
    assert path.exists()


def test_live_large_unprepared_file_is_held_before_hash(settings, managed, monkeypatch):
    path, _, now = create(settings, managed, size=17*1024**2)
    monkeypatch.setattr(retention, 'hashlib', SimpleNamespace(sha256=lambda: pytest.fail('unprepared large hash')))
    with transaction(settings) as conn:
        result = retention.artifact_retention(conn, managed, now=now, execute=True)
    assert result[0]['reason'] == 'ARTIFACT_PREVALIDATION_REQUIRED' and path.exists()


def test_runner_reports_held_and_bounded_backlog(settings, managed, monkeypatch):
    monkeypatch.setattr(seals, 'MAX_PREVALIDATED_FILES', 2)
    paths = []
    for index in range(4):
        path, identifier, now = create(settings, managed, f'raw{index}.zip')
        paths.append(path)
        if index == 0:
            with transaction(settings) as conn:
                conn.execute("INSERT INTO retention_hold VALUES(%s,'artifact',%s,'synthetic-owner','hold',clock_timestamp())",
                             (uuid4(), str(identifier)))
    result = seals.run_artifact_retention(managed, now=now)
    assert sum(item['state'] == 'deleted' for item in result) == 2
    assert any(item.get('reason') == 'ARTIFACT_ACTIVE_OR_HELD' for item in result)
    assert any(item.get('reason') == 'ARTIFACT_PREVALIDATION_BACKLOG' and item['pending_count'] == 1 for item in result)
    assert sum(path.exists() for path in paths) == 2


def test_expired_snapshot_prevalidated_removal_preserves_cursor_version(settings, managed):
    path, _, now = create(settings, managed, snapshot=True)
    result = seals.run_artifact_retention(managed, now=now)
    assert result[0]['state'] == 'deleted' and not path.exists()
    with transaction(settings) as conn:
        cursor = conn.execute("SELECT * FROM source_cursor WHERE source='abr'").fetchone()
        assert cursor['snapshot_id'] is None and cursor['version'] == 5


def test_prevalidated_preview_reports_due_without_unlink(settings, managed):
    path, identifier, now = create(settings, managed, size=17*1024**2)
    result = seals.run_artifact_retention(managed, now=now, execute=False)
    assert result[0]['state'] == 'due' and path.exists()
    with transaction(settings) as conn:
        assert conn.execute('SELECT state FROM artifact_manifest WHERE artifact_id=%s', (identifier,)).fetchone()['state'] == 'referenced'


@pytest.mark.parametrize('kind', ['file_symlink', 'parent_symlink'])
def test_original_symlink_path_is_refused(settings, managed, kind):
    original, identifier, now = create(settings, managed)
    link = managed.settings.output_dir / 'linked'
    try:
        link.symlink_to(original if kind == 'file_symlink' else original.parent, target_is_directory=kind=='parent_symlink')
    except OSError:
        pytest.skip('OS does not permit this synthetic symlink')
    path = link if kind == 'file_symlink' else link / original.name
    with transaction(settings) as conn:
        conn.execute('UPDATE artifact_manifest SET local_path=%s WHERE artifact_id=%s', (str(path), identifier))
    result = seals.run_artifact_retention(managed, now=now)
    assert result[0]['reason'] == 'ARTIFACT_LINK_REFUSED' and original.exists()


def test_personal_retention_skip_artifacts_never_starts_file_hash(db, service, monkeypatch):
    monkeypatch.setattr(retention, 'artifact_retention', lambda *args, **kwargs: pytest.fail('duplicate artifact pass'))
    result = retention.retention_run(db, service, now=Service.now(db), execute=True, skip_artifacts=True)
    assert result['status'] == 'primary_retention_complete' and result['artifacts'] == []


def test_opened_handle_must_match_original_file_before_any_bytes(settings, managed, monkeypatch):
    path, identifier, now = create(settings, managed)
    foreign = managed.settings.output_dir / 'foreign-synthetic.txt'
    foreign.write_bytes(b'y'*20)
    real_open = Path.open
    def changed_open(self, *args, **kwargs):
        return real_open(foreign if self == path and args == ('rb',) else self, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', changed_open)
    class NoReadHash:
        def update(self, data):
            pytest.fail('read a different opened file')
    monkeypatch.setattr(seals, 'hashlib', SimpleNamespace(sha256=NoReadHash))
    prepared = seals.prepare_artifact_retention(managed, now=now)
    assert prepared.files[str(identifier)]['reason'] == 'ARTIFACT_PREVALIDATION_CHANGED'
    assert path.exists() and foreign.exists()


def test_seal_scope_binds_actual_database_schema_not_only_config(settings, managed):
    path, _, now = create(settings, managed)
    prepared = seals.prepare_artifact_retention(managed, now=now)
    wrong_schema = 'abr_test_' + 'f'*32
    prepared = replace(prepared, schema_name=wrong_schema)
    managed.settings = managed.settings.model_copy(update={'schema_name': wrong_schema})
    result = finish(settings, managed, prepared, now)
    assert result[0]['reason'] == 'ARTIFACT_PREVALIDATION_SCOPE_CHANGED' and path.exists()
