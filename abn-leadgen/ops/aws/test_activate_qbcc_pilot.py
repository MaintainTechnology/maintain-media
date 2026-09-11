"""Activation decisions, previews and real isolated PostgreSQL rollback; no host/provider operations."""
import importlib.util
import json
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg import sql as postgres_sql
from psycopg.rows import tuple_row

from abr_engine.config import Settings
from abr_engine.db import connect, migrate, transaction

SPEC = importlib.util.spec_from_file_location('activate_qbcc_pilot', Path(__file__).with_name('activate_qbcc_pilot.py'))
activation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(activation)


@pytest.fixture
def decision(tmp_path):
    evidence = tmp_path / 'synthetic-owner-decision.json'
    evidence.write_text('{"synthetic_test_only":true}\n')
    now = datetime.now(UTC)
    plan = {'actor_id': activation.ACTOR, 'adviser_status': 'not_obtained',
            'approved_at': (now-timedelta(minutes=1)).isoformat(),
            'collection_expires_at': (now+timedelta(days=1)).isoformat(),
            'retention_expires_at': (now+timedelta(days=200)).isoformat(),
            'production_backup_accepted': False, 'full_production_release': False,
            'gates': {scope: {gate: {'file': evidence.name, 'sha256': activation.sha(evidence)}
                              for gate in gates} for scope, gates in activation.SCOPES.items()}}
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(plan))
    return path, plan


def test_read_plan_accepts_only_current_finite_owner_decision(decision):
    path, plan = decision
    assert activation.read_plan(path) == plan


@pytest.mark.parametrize('change', ['future', 'expired', 'over14', 'naive', 'short_retention',
                                  'unbounded_retention', 'adviser_claim', 'production_claim',
                                  'backup_claim', 'actor', 'extra_scope', 'missing_gate',
                                  'hash', 'traversal', 'extra_evidence'])
def test_invalid_decisions_are_rejected_before_any_operator_action(decision, change):
    path, plan = decision
    now = datetime.now(UTC)
    if change == 'future': plan['approved_at'] = (now+timedelta(hours=1)).isoformat()
    elif change == 'expired': plan['collection_expires_at'] = now.isoformat()
    elif change == 'over14': plan['collection_expires_at'] = (now+timedelta(days=15)).isoformat()
    elif change == 'naive': plan['approved_at'] = now.replace(tzinfo=None).isoformat()
    elif change == 'short_retention': plan['retention_expires_at'] = (now+timedelta(days=180)).isoformat()
    elif change == 'unbounded_retention': plan['retention_expires_at'] = (now+timedelta(days=400)).isoformat()
    elif change == 'adviser_claim': plan['adviser_status'] = 'obtained'
    elif change == 'production_claim': plan['full_production_release'] = True
    elif change == 'backup_claim': plan['production_backup_accepted'] = True
    elif change == 'actor': plan['actor_id'] = 'invented-owner'
    elif change == 'extra_scope': plan['gates']['website_collection'] = {}
    elif change == 'missing_gate': del plan['gates']['collection']['G3']
    elif change == 'hash': plan['gates']['collection']['G2']['sha256'] = 'f'*64
    elif change == 'traversal': plan['gates']['collection']['G2']['file'] = '../outside.json'
    else: plan['gates']['collection']['G2']['secret'] = 'must-not-be-accepted'
    path.write_text(json.dumps(plan))
    with pytest.raises(activation.ActivationError):
        activation.read_plan(path)


def test_duplicate_json_authority_field_is_rejected(decision):
    path, _ = decision
    path.write_text('{"actor_id":"first","actor_id":"second"}')
    with pytest.raises(activation.ActivationError, match='DUPLICATE_PLAN_FIELD'):
        activation.read_plan(path)


@pytest.fixture
def host(decision, tmp_path, monkeypatch):
    path, _ = decision
    release = tmp_path / 'release'
    release.mkdir()
    manifest = release / 'RELEASE-MANIFEST.json'
    manifest.write_text('{"synthetic_release":true}')
    config = tmp_path / 'pilot.yaml'
    original = b'mode: pilot\ncapabilities:\n  collection: false\n  website_collection: false\n  abr: false\n  crm: false\n  sheets: false\n  backup: false\n'
    config.write_bytes(original)
    monkeypatch.setattr(activation, 'ROOT', release)
    monkeypatch.setattr(activation, 'MANIFEST_SHA', activation.sha(manifest))
    monkeypatch.setattr(activation, 'CONFIG', config)
    monkeypatch.setattr(activation, 'BACKUP', tmp_path / 'before.yaml')
    monkeypatch.setattr(activation.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(activation, 'read_config', config.read_bytes)
    monkeypatch.setattr(activation, 'sync_directory', lambda ignored: None)
    monkeypatch.setattr(activation, 'activation_lock', nullcontext)
    commands, queries, replacements = [], [], []
    monkeypatch.setattr(activation, 'command', lambda args, **kwargs: commands.append(args) or '')
    monkeypatch.setattr(activation, 'unit_state', lambda action, name:
                        ('disabled' if action == 'is-enabled' else 'inactive')
                        if name in ('abr-engine-qbcc-weekly.timer', 'abr-engine-retention.timer') else 'active')

    def query(text):
        queries.append(text)
        return 'f' if 'has_table_privilege' in text else '0|0|0|26|0|0|0'

    def replace(data):
        replacements.append(data)
        config.write_bytes(data)

    monkeypatch.setattr(activation, 'sql', query)
    monkeypatch.setattr(activation, 'atomic_config', replace)
    return {'path': path, 'original': original, 'config': config,
            'commands': commands, 'queries': queries, 'replacements': replacements}


def test_preview_is_read_only_and_returns_reviewed_digest(host):
    before = set(host['path'].parent.rglob('*'))
    result = activation.install(host['path'])
    assert result['status'] == 'preview_passed' and result['plan_sha256'] == activation.sha(host['path'])
    assert result['enabled_capabilities'] == ['collection', 'retention']
    assert host['commands'] == host['replacements'] == []
    assert all(query.startswith('SELECT') for query in host['queries'])
    assert set(host['path'].parent.rglob('*')) == before
    assert not activation.BACKUP.exists()


@pytest.mark.parametrize('digest', [None, 'f'*64])
def test_execute_requires_the_exact_previewed_plan(host, digest):
    with pytest.raises(activation.ActivationError, match='REVIEWED_PLAN_DIGEST_REQUIRED'):
        activation.install(host['path'], execute=True, plan_sha256=digest)
    assert host['commands'] == host['queries'] == host['replacements'] == []


def test_runtime_mutation_privileges_and_enabled_but_inactive_weekly_timer_are_denied(host, monkeypatch):
    monkeypatch.setattr(activation, 'sql', lambda query: 't' if 'has_table_privilege' in query else '0|0|0|26|0|0|0')
    with pytest.raises(activation.ActivationError, match='RUNTIME_AUTHORITY_WRITES_FORBIDDEN'):
        activation.install(host['path'])
    monkeypatch.setattr(activation, 'sql', lambda query: 'f' if 'has_table_privilege' in query else '0|0|0|26|0|0|0')
    monkeypatch.setattr(activation, 'unit_state', lambda action, name: 'enabled' if action == 'is-enabled' else 'inactive')
    with pytest.raises(activation.ActivationError, match='DORMANT_SOURCE_AND_RETENTION_TIMERS_REQUIRED'):
        activation.install(host['path'])
    assert host['commands'] == []


@pytest.fixture
def database():
    settings = Settings(schema_name='abr_test_'+uuid4().hex)
    with connect(Settings()) as conn:
        conn.execute(postgres_sql.SQL('CREATE SCHEMA {}').format(postgres_sql.Identifier(settings.schema_name)))
    try:
        migrate(settings)
        yield settings
    finally:
        with connect(Settings()) as conn:
            conn.execute(postgres_sql.SQL('DROP SCHEMA {} CASCADE').format(postgres_sql.Identifier(settings.schema_name)))


def actual_sql(settings, query):
    if 'has_table_privilege' in query:
        return 'f'  # Installed runtime-role metadata is separately checked on the Linux host.
    with connect(settings) as conn, conn.cursor(row_factory=tuple_row) as cursor:
        cursor.execute(query)
        if cursor.description:
            return '|'.join(str(value) for value in cursor.fetchone())
    return ''


def test_actual_pg_activation_installs_exact_scopes_and_keeps_other_capabilities_off(host, database, monkeypatch):
    monkeypatch.setattr(activation, 'sql', lambda query: actual_sql(database, query))
    result = activation.install(host['path'], execute=True, plan_sha256=activation.sha(host['path']))
    assert result['status'] == 'pilot_authority_installed'
    settings = activation.yaml.safe_load(host['config'].read_bytes())
    assert {name for name, enabled in settings['capabilities'].items() if enabled} == {'collection', 'retention'}
    assert activation.BACKUP.read_bytes() == host['original']
    with transaction(database) as conn:
        gates = conn.execute('SELECT gate_name,scope FROM release_gate').fetchall()
        assert {(row['gate_name'], row['scope']) for row in gates} == {(gate, scope) for scope, gates in activation.SCOPES.items() for gate in gates}
        policy = conn.execute('SELECT * FROM policy').fetchone()
        assert policy['settings']['adviser_status'] == 'not_obtained'
        assert policy['settings']['retention']['restore_enabled'] is False
    assert host['commands'][0] == ['systemctl', 'stop', *activation.SOURCE_UNITS]


def test_actual_pg_failure_rolls_back_only_owned_authority_and_restores_dormant_config(host, database, monkeypatch):
    monkeypatch.setattr(activation, 'sql', lambda query: actual_sql(database, query))

    def fail_retention(args, **kwargs):
        host['commands'].append(args)
        if args[1] == 'enable': raise activation.ActivationError('OPERATOR_COMMAND_FAILED')
        return ''

    monkeypatch.setattr(activation, 'command', fail_retention)
    with pytest.raises(activation.ActivationError, match='OPERATOR_COMMAND_FAILED'):
        activation.install(host['path'], execute=True, plan_sha256=activation.sha(host['path']))
    assert host['config'].read_bytes() == host['original']
    assert activation.BACKUP.read_bytes() == host['original']
    with transaction(database) as conn:
        assert conn.execute('SELECT count(*) n FROM release_gate').fetchone()['n'] == 0
        assert conn.execute('SELECT count(*) n FROM policy').fetchone()['n'] == 0
    assert ['systemctl', 'disable', 'abr-engine-retention.timer'] in host['commands']


@pytest.mark.parametrize('change', ['foreign_policy', 'changed_policy', 'source_data'])
def test_rollback_preserves_changed_authority_or_source_data_and_leaves_services_stopped(host, database, monkeypatch, change):
    monkeypatch.setattr(activation, 'sql', lambda query: actual_sql(database, query))

    def fail_after_change(args, **kwargs):
        host['commands'].append(args)
        if args[1] == 'enable':
            with transaction(database) as conn:
                if change == 'foreign_policy':
                    conn.execute("INSERT INTO policy SELECT 'synthetic-foreign',state,scope,evidence_ref,actor_id,approved_at,expires_at,settings FROM policy")
                elif change == 'changed_policy':
                    conn.execute("UPDATE policy SET settings=settings||'{\"externally_changed\":true}'::jsonb")
                else:
                    from abr_engine.compliance.keys import load_keys
                    from abr_engine.control.service import Service
                    Service(database, load_keys(database)).create_lead(conn, name='Synthetic rollback boundary', source='qbcc', alias='SYNTHETIC-ROLLBACK')
            raise activation.ActivationError('OPERATOR_COMMAND_FAILED')
        return ''

    monkeypatch.setattr(activation, 'command', fail_after_change)
    with pytest.raises(activation.ActivationError, match='ACTIVATION_ROLLBACK_REQUIRES_REVIEW'):
        activation.install(host['path'], execute=True, plan_sha256=activation.sha(host['path']))
    assert host['config'].read_bytes() == host['original']
    assert not any(command[1] == 'start' for command in host['commands'])
    with transaction(database) as conn:
        assert conn.execute('SELECT count(*) n FROM release_gate').fetchone()['n'] == 7
        assert conn.execute('SELECT count(*) n FROM policy').fetchone()['n'] == (2 if change == 'foreign_policy' else 1)
        if change == 'source_data': assert conn.execute('SELECT count(*) n FROM lead_entity').fetchone()['n'] == 1


def test_cli_error_does_not_reflect_unexpected_private_exception(decision, monkeypatch, capsys):
    def fail(*args, **kwargs): raise RuntimeError('private-secret-sentinel')
    monkeypatch.setattr(activation, 'install', fail)
    assert activation.main([str(decision[0])]) == 2
    assert json.loads(capsys.readouterr().out) == {'status': 'activation_failed', 'code': 'ACTIVATION_FAILED'}
