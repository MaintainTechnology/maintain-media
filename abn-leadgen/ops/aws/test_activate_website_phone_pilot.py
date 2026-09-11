"""Local plan checks and actual isolated-PG append-only activation; no host calls."""
# ruff: noqa: F811 -- imported database fixture intentionally injected by name.
import importlib.util
import json
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb
from test_activate_qbcc_pilot import database  # noqa: F401

from abr_engine.compliance.keys import load_keys
from abr_engine.compliance.policy import website_collection_policy
from abr_engine.control.service import Service
from abr_engine.db import connect

SPEC = importlib.util.spec_from_file_location('activate_website_phone_pilot', Path(__file__).with_name('activate_website_phone_pilot.py'))
activation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(activation)


@pytest.fixture
def plan(tmp_path):
    owner = tmp_path / 'synthetic-owner.json'
    owner.write_text(json.dumps({'decision_id': 'website-phone-pilot-delegated-owner-20260911',
        'status': 'approved_with_limits_under_delegated_authority', 'adviser_status': 'not_obtained',
        'effective_at': (datetime.now(UTC)-timedelta(minutes=1)).isoformat(),
        'legal_compliance_certified': False, 'expires_at': activation.END,
        'retention': {'retain_selected_evidence': False},
        'source_and_admission': {'allowed_channels': ['mobile', 'landline'], 'email_extraction_allowed': False}}))
    technical = tmp_path / 'synthetic-technical.md'
    technical.write_text('Synthetic test evidence only.\n')
    values = {'version': 'website-phone-pilot-activation-v1', 'actor_id': activation.ACTOR,
        'adviser_status': 'not_obtained', 'approved_at': (datetime.now(UTC)-timedelta(seconds=5)).isoformat(),
        'collection_expires_at': activation.END, 'website_expires_at': activation.END,
        'retention_expires_at': activation.RETENTION_END, 'source_manifest_before_sha256': activation.BEFORE_MANIFEST,
        'source_manifest_sha256': activation.MANIFEST, 'production_backup_accepted': False,
        'full_production_release': False, 'policy_version': activation.POLICY,
        'owner_evidence': {'file': owner.name, 'sha256': activation.sha(owner)},
        'technical_evidence': {'file': technical.name, 'sha256': activation.sha(technical)},
        'gate_revisions': activation.REVISIONS}
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(values))
    return path, values


def test_exact_current_plan_and_append_only_revision_map(plan):
    path, values = plan
    assert activation.read_plan(path) == values
    assert len(activation.authority_rows(values)) == 7
    record = activation.policy_record(values)
    settings = json.loads(record['settings'])
    assert settings['website_collection']['allowed_channels'] == ['mobile', 'landline']
    assert settings['retention']['retain_selected_evidence'] is False


def test_readback_normalizes_timestamp_and_json_representations():
    left = {'approved_at': '2026-09-11T00:33:22Z', 'expires_at': activation.END, 'settings': '{"value":false}'}
    right = {'approved_at': '2026-09-11T00:33:22+00:00', 'expires_at': '2026-09-24T23:18:20+00:00', 'settings': {'value': False}}
    assert activation.normalized_record(left) == activation.normalized_record(right)


@pytest.mark.parametrize('failure', ['extra', 'future', 'naive', 'backdated', 'expiry', 'manifest', 'revision', 'hash', 'path', 'draft'])
def test_unreviewed_or_broadened_plan_is_rejected(plan, failure):
    path, values = plan
    if failure == 'extra': values['enable_email'] = True
    elif failure == 'future': values['approved_at'] = (datetime.now(UTC)+timedelta(days=1)).isoformat()
    elif failure == 'naive': values['approved_at'] = datetime.now(UTC).replace(tzinfo=None).isoformat()
    elif failure == 'backdated': values['approved_at'] = (datetime.now(UTC)-timedelta(minutes=2)).isoformat()
    elif failure == 'expiry': values['website_expires_at'] = '2026-10-01T00:00:00Z'
    elif failure == 'manifest': values['source_manifest_sha256'] = 'f'*64
    elif failure == 'revision': values['gate_revisions'] = {'collection': {'G1': 4}}
    elif failure == 'hash': values['technical_evidence']['sha256'] = 'f'*64
    elif failure == 'path': values['owner_evidence']['file'] = '../outside.json'
    else:
        owner = path.parent / values['owner_evidence']['file']
        document = json.loads(owner.read_text()); document['status'] = 'draft'
        owner.write_text(json.dumps(document)); values['owner_evidence']['sha256'] = activation.sha(owner)
    path.write_text(json.dumps(values))
    with pytest.raises(activation.ActivationError):
        activation.read_plan(path)


@pytest.fixture
def host(plan, tmp_path, monkeypatch, database):
    path, values = plan
    release = tmp_path / 'release'; release.mkdir()
    manifest = release / 'RELEASE-MANIFEST.json'; manifest.write_text('synthetic release')
    monkeypatch.setattr(activation, 'ROOT', release)
    monkeypatch.setattr(activation, 'MANIFEST', activation.sha(manifest))
    values['source_manifest_sha256'] = activation.MANIFEST
    path.write_text(json.dumps(values))
    config = tmp_path / 'pilot.yaml'
    original = b'mode: pilot\ncapabilities:\n  collection: true\n  retention: true\n  website_collection: false\n  abr: false\n  crm: false\n  sheets: false\n'
    config.write_bytes(original)
    monkeypatch.setattr(activation, 'CONFIG', config)
    monkeypatch.setattr(activation, 'BACKUP', tmp_path / 'original.yaml')
    monkeypatch.setattr(activation, 'DECISIONS', tmp_path / 'decisions')
    monkeypatch.setattr(activation.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(activation.os, 'O_NOFOLLOW', 0, raising=False)  # Linux-only flag; private test directory.
    monkeypatch.setattr(activation, 'read_config', config.read_bytes)
    monkeypatch.setattr(activation, 'sync_directory', lambda _: None)
    monkeypatch.setattr(activation, 'activation_lock', nullcontext)
    commands, queries = [], []
    monkeypatch.setattr(activation, 'command', lambda args, **kwargs: commands.append(args) or '')
    monkeypatch.setattr(activation, 'unit_state', lambda action, name: 'disabled' if action == 'is-enabled' else 'inactive')
    monkeypatch.setattr(activation, 'atomic_config', config.write_bytes)
    def evidence(source, decision):
        activation.DECISIONS.mkdir(exist_ok=True)
        for key in ('owner_evidence', 'technical_evidence'):
            name = decision[key]['file']
            (activation.DECISIONS / name).write_bytes((source.parent / name).read_bytes())
    monkeypatch.setattr(activation, 'install_evidence', evidence)
    with connect(database) as conn:
        now = Service.now(conn)
        for scope, gate, revision in sorted(activation.OLD_REVISIONS):
            conn.execute('INSERT INTO release_gate VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (gate, 'pilot', scope, revision, 'synthetic-existing-record', 'a'*64, 'synthetic-owner',
                 now-timedelta(minutes=5), activation.RETENTION_END if scope == 'retention' else activation.END))
        conn.execute('INSERT INTO policy VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
            (activation.OLD_POLICY, 'approved', 'pilot', 'synthetic-existing-policy', 'synthetic-owner',
             now-timedelta(minutes=5), activation.RETENTION_END, Jsonb({'source_scope': 'qbcc-internal-review-only',
                'retention': {'approved': True, 'restore_enabled': False}})))
        Service(database, load_keys(database)).create_lead(conn, name='Synthetic reviewed business', source='qbcc', alias='12345678')
        content, snapshot = uuid4(), uuid4()
        conn.execute("INSERT INTO source_content VALUES(%s,'qbcc',%s,'synthetic','synthetic','synthetic')", (content, 'a'*64))
        conn.execute("INSERT INTO source_snapshot(snapshot_id,source,content_id,expected_cursor_version,manifest,state) VALUES(%s,'qbcc',%s,0,'{}','committed')", (snapshot, content))
        conn.execute("INSERT INTO source_cursor(source,snapshot_id,version) VALUES('qbcc',%s,1)", (snapshot,))
    def run_sql(query):
        queries.append(query)
        if 'has_table_privilege' in query:
            return 'f'  # Actual Linux runtime privileges are separate host acceptance.
        with connect(database) as conn, conn.cursor(row_factory=tuple_row) as cursor:
            cursor.execute(query)
            if cursor.description:
                value = cursor.fetchone()[0]
                return json.dumps(value) if isinstance(value, dict) else str(value)
        return ''
    monkeypatch.setattr(activation, 'sql', run_sql)
    return {'path': path, 'values': values, 'config': config, 'original': original,
            'commands': commands, 'queries': queries, 'database': database, 'sql': run_sql}


def test_preview_checks_real_state_without_writing_anything(host):
    before = set(host['path'].parent.rglob('*'))
    result = activation.install(host['path'])
    assert result['status'] == 'preview_passed' and result['new_gate_rows'] == 7
    assert host['commands'] == [] and all(query.startswith('SELECT') for query in host['queries'])
    assert before == set(host['path'].parent.rglob('*')) and host['config'].read_bytes() == host['original']


@pytest.mark.parametrize('failure', ['digest', 'active', 'unexpected_lead', 'privileges'])
def test_changed_host_or_unreviewed_execute_is_rejected_without_mutation(host, monkeypatch, failure):
    if failure == 'active':
        monkeypatch.setattr(activation, 'unit_state', lambda action, unit: 'active')
    elif failure == 'unexpected_lead':
        with connect(host['database']) as conn:
            Service(host['database'], load_keys(host['database'])).create_lead(conn, name='Extra synthetic', source='qbcc', alias='23456789')
    elif failure == 'privileges':
        monkeypatch.setattr(activation, 'sql', lambda query: 't' if 'has_table_privilege' in query else host['sql'](query))
    with pytest.raises(activation.ActivationError):
        activation.install(host['path'], execute=True,
            plan_sha256='f'*64 if failure == 'digest' else activation.sha(host['path']))
    assert not activation.BACKUP.exists() and host['config'].read_bytes() == host['original']


def test_real_pg_activation_appends_exact_rows_preserves_old_state_and_enables_only_phone(host):
    before = json.loads(host['sql'](activation.state_query()))
    result = activation.install(host['path'], execute=True, plan_sha256=activation.sha(host['path']))
    assert result['status'] == 'website_phone_authority_installed' and host['commands'] == []
    after = json.loads(host['sql'](activation.state_query()))
    assert after['counts']['release_gate'] == 19 and after['counts']['policy'] == 2
    assert after['policies'][0] == before['policies'][0]
    with connect(host['database']) as conn:
        settings = host['database'].model_copy(update={'mode': 'pilot', 'capabilities': {
            'collection': True, 'retention': True, 'website_collection': True}})
        assert website_collection_policy(conn, settings, Service.now(conn))['allowed_channels'] == ['mobile', 'landline']
    assert activation.BACKUP.read_bytes() == host['original']
    assert b'website_collection: true' in host['config'].read_bytes() and b'crm: false' in host['config'].read_bytes()


@pytest.mark.parametrize('failure', ['before_sql', 'concurrent_authority', 'after_commit', 'changed_gate', 'changed_policy'])
def test_failures_keep_services_stopped_config_closed_and_never_remove_authority(host, monkeypatch, failure):
    if failure == 'before_sql':
        monkeypatch.setattr(activation, 'install_evidence', lambda *args: (_ for _ in ()).throw(RuntimeError('synthetic-secret')))
    elif failure == 'concurrent_authority':
        def changed(query):
            if query.startswith('BEGIN'):
                with connect(host['database']) as conn:
                    conn.execute("UPDATE release_gate SET evidence_ref='synthetic-concurrent-change' WHERE scope='collection' AND gate_name='G1'")
            return host['sql'](query)
        monkeypatch.setattr(activation, 'sql', changed)
    elif failure == 'after_commit':
        attempts = []
        def write(data):
            attempts.append(data)
            host['config'].write_bytes(data)
            if len(attempts) == 1:
                raise RuntimeError('synthetic-secret')
        monkeypatch.setattr(activation, 'atomic_config', write)
    else:
        def changed_readback(query):
            result = host['sql'](query)
            if query.startswith('BEGIN'):
                with connect(host['database']) as conn:
                    if failure == 'changed_gate':
                        conn.execute("UPDATE release_gate SET evidence_sha256=%s WHERE scope='website_collection' AND gate_name='G1'", ('f'*64,))
                    else:
                        conn.execute("UPDATE policy SET settings=jsonb_set(settings,'{website_collection,allowed_channels}','[\"email\"]') WHERE version=%s", (activation.POLICY,))
            return result
        monkeypatch.setattr(activation, 'sql', changed_readback)
    with pytest.raises(activation.ActivationError, match='ACTIVATION_FAILED_CLOSED_HISTORY_PRESERVED'):
        activation.install(host['path'], execute=True, plan_sha256=activation.sha(host['path']))
    assert host['config'].read_bytes() == host['original']
    assert all(args[:2] == ['systemctl', 'stop'] for args in host['commands'])
    after = json.loads(host['sql'](activation.state_query()))
    assert after['counts']['release_gate'] == (19 if failure in ('after_commit', 'changed_gate', 'changed_policy') else 12)
    assert all('DELETE FROM release_gate' not in query and 'DELETE FROM policy' not in query for query in host['queries'])


def test_failure_does_not_overwrite_concurrently_changed_private_configuration(host, monkeypatch):
    changed = host['original'] + b'# synthetic concurrent operator change\n'
    def evidence(*args):
        host['config'].write_bytes(changed)
        raise RuntimeError('synthetic failure')
    monkeypatch.setattr(activation, 'install_evidence', evidence)
    with pytest.raises(activation.ActivationError, match='ACTIVATION_RECOVERY_REQUIRES_REVIEW'):
        activation.install(host['path'], execute=True, plan_sha256=activation.sha(host['path']))
    assert host['config'].read_bytes() == changed
    assert all(args[:2] == ['systemctl', 'stop'] for args in host['commands'])
    assert json.loads(host['sql'](activation.state_query()))['counts']['release_gate'] == 12
