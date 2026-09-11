"""Synthetic installation files and isolated PostgreSQL; no provider/host calls."""
# ruff: noqa: F811 -- imported isolated database fixture is intentionally injected.
import importlib.util
import json
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb
from test_activate_qbcc_pilot import database  # noqa: F401

from abr_engine.compliance.keys import load_keys
from abr_engine.control.service import Service
from abr_engine.db import connect
from abr_engine.export.gohighlevel import FIELD_NAMES, workflow_inventory_digest
from abr_engine.fixture import seed_contact, seed_policy

SPEC = importlib.util.spec_from_file_location('activate_ghl_dnd_pilot', Path(__file__).with_name('activate_ghl_dnd_pilot.py'))
activation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(activation)


@pytest.fixture
def plan(tmp_path):
    now = datetime.now(UTC)
    owner = {'decision_id': 'ghl-dnd-pilot-delegated-owner-20260911',
        'effective_at': (now-timedelta(minutes=2)).isoformat(),
        'status': 'approved_with_limits_under_delegated_authority', 'adviser_status': 'not_obtained',
        'approved_for_release': True,
        'legal_compliance_certified': False, 'expires_at': activation.END,
        'recipient': {'location_id': activation.LOCATION},
        'disclosure_projection': {'allowed_channel': 'phone'}, 'operational_limits': {'dnd_always_true': True},
        'per_record_admission': {'selected_worklist_required': True, 'tier': 'A',
            'individual_reviewer_approval_bound_to_current_row_version': True,
            'genuine_dncr_clear_strictly_less_than_30_days_required': True},
        'retention': {'finite_deletion_authority_expires_at': activation.RETENTION_END, 'retain_selected_evidence': False},
        'notice_strategy': {'publication_status': 'verified_public_readback', 'live_readback_evidence': 'synthetic-only'}}
    def save(name, value, mode='json'):
        path = tmp_path / name
        path.write_text(json.dumps(value) if mode == 'json' else yaml.safe_dump(value))
        return {'file': name, 'sha256': activation.sha(path)}
    owner_ref = save('synthetic-owner.json', owner)
    tech_ref = save('synthetic-technical.json', {'synthetic_only': True})
    checks = {key: save('synthetic-'+key+'.json', {'synthetic_check_only': key}) for key in activation.CHECKS}
    config = {'location_id': activation.LOCATION, 'mapping_version': 'synthetic-local-test-v1',
        'field_ids': {name: 'synthetic_'+name for name in FIELD_NAMES}, 'allow_writes': True,
        'allowed_channels': ['phone'], 'group_search_field': 'customFields.synthetic_group_id',
        'workflow_inventory_sha256': workflow_inventory_digest({'workflows': []}, activation.LOCATION)}
    config_ref = save('synthetic-ghl.yaml', config, 'yaml')
    receipt = {'schema_version': 1, 'provider': 'gohighlevel', 'environment': 'pilot',
        'location_id': activation.LOCATION, 'approved_by': activation.ACTOR, 'config_sha256': config_ref['sha256'],
        'verified_at': (now-timedelta(minutes=1)).isoformat(), 'expires_at': activation.RETENTION_END,
        'checks': {name: {'passed': True, 'evidence_ref': str(activation.DECISIONS / ref['file']),
                         'evidence_sha256': ref['sha256']} for name, ref in checks.items()}}
    receipt_ref = save('synthetic-installation.yaml', receipt, 'yaml')
    values = {'version': 'ghl-dnd-pilot-activation-v1', 'actor_id': activation.ACTOR,
        'adviser_status': 'not_obtained', 'approved_at': (now-timedelta(seconds=5)).isoformat(),
        'crm_expires_at': activation.END, 'removal_expires_at': activation.RETENTION_END,
        'source_manifest_before_sha256': activation.BEFORE_MANIFEST, 'source_manifest_sha256': 'b'*64,
        'production_backup_accepted': False, 'full_production_release': False,
        'owner_evidence': owner_ref, 'technical_evidence': tech_ref, 'ghl_config': config_ref,
        'ghl_installation': receipt_ref, 'check_evidence': checks}
    path = tmp_path / 'plan.json'; path.write_text(json.dumps(values))
    return path, values


def test_exact_plan_and_acquisition_removal_expiry_split(plan):
    path, values = plan
    assert activation.read_plan(path) == values
    rows = activation.authority_rows(values)
    assert [row['gate_name'] for row in rows] == ['G1', 'G3', 'G5', 'G7']
    assert all(row['scope'] == 'crm' and row['revision'] == 1 for row in rows)
    assert {row['gate_name']: row['expires_at'] for row in rows} == {
        'G1': activation.END, 'G3': activation.RETENTION_END, 'G5': activation.RETENTION_END, 'G7': activation.END}
    assert rows[2]['evidence_sha256'] == values['ghl_installation']['sha256']


def test_environment_named_input_is_refused_before_content_read(tmp_path, monkeypatch):
    path = tmp_path / '.env.json'
    path.write_text('synthetic input only')
    monkeypatch.setattr(activation, 'read_json', lambda _: pytest.fail('Content must not be read'))
    with pytest.raises(activation.ActivationError, match='PUBLIC_JSON_PLAN_REQUIRED'):
        activation.read_plan(path)


def test_real_test_time_can_precede_owner_finalisation_but_must_be_fresh(plan):
    path, values = plan
    receipt_path = path.parent / values['ghl_installation']['file']
    receipt = yaml.safe_load(receipt_path.read_text())
    for age, accepted in ((timedelta(minutes=10), True), (timedelta(hours=25), False)):
        receipt['verified_at'] = (datetime.now(UTC)-age).isoformat()
        receipt_path.write_text(yaml.safe_dump(receipt))
        values['ghl_installation']['sha256'] = activation.sha(receipt_path)
        path.write_text(json.dumps(values))
        if accepted:
            assert activation.read_plan(path) == values
        else:
            with pytest.raises(activation.ActivationError, match='EXACT_PHONE_DND_INSTALLATION'):
                activation.read_plan(path)


@pytest.mark.parametrize('failure', ['extra', 'draft', 'release_flag', 'old_release', 'backdate', 'expiry', 'path', 'hash',
    'email', 'no_inventory', 'location', 'short_removal', 'check_hash', 'check_path', 'missing_check', 'notice', 'dncr'])
def test_unreviewed_or_broadened_inputs_cannot_admit(plan, failure):
    path, values = plan
    if failure == 'extra': values['enable_emails'] = True
    elif failure == 'old_release': values['source_manifest_sha256'] = activation.BEFORE_MANIFEST
    elif failure == 'backdate': values['approved_at'] = (datetime.now(UTC)-timedelta(minutes=3)).isoformat()
    elif failure == 'expiry': values['crm_expires_at'] = activation.RETENTION_END
    elif failure == 'path': values['owner_evidence']['file'] = '../private.json'
    elif failure == 'hash': values['technical_evidence']['sha256'] = 'a'*64
    else:
        key = 'owner_evidence' if failure in {'draft', 'release_flag', 'notice', 'dncr'} else (
            'ghl_config' if failure in {'email', 'no_inventory', 'location'} else 'ghl_installation')
        target = path.parent / values[key]['file']
        document = json.loads(target.read_text()) if key == 'owner_evidence' else yaml.safe_load(target.read_text())
        if failure == 'draft': document['status'] = 'draft'
        elif failure == 'release_flag': document['approved_for_release'] = False
        elif failure == 'notice': document['notice_strategy']['publication_status'] = 'pending'
        elif failure == 'dncr': document['per_record_admission']['genuine_dncr_clear_strictly_less_than_30_days_required'] = False
        elif failure == 'email': document['allowed_channels'] = ['email', 'phone']
        elif failure == 'no_inventory': document.pop('workflow_inventory_sha256')
        elif failure == 'location': document['location_id'] = 'otherLocation'
        elif failure == 'short_removal': document['expires_at'] = activation.END
        elif failure == 'missing_check': document['checks'].pop('metadata')
        else: document['checks']['metadata']['evidence_sha256' if failure == 'check_hash' else 'evidence_ref'] = 'a'*64
        target.write_text(json.dumps(document) if key == 'owner_evidence' else yaml.safe_dump(document))
        values[key]['sha256'] = activation.sha(target)
    path.write_text(json.dumps(values))
    with pytest.raises((activation.ActivationError, ValueError)):
        activation.read_plan(path)


@pytest.fixture
def host(plan, tmp_path, monkeypatch, database):
    path, values = plan
    release = tmp_path / 'release'; release.mkdir()
    manifest = release / 'RELEASE-MANIFEST.json'; manifest.write_text('synthetic reviewed runtime only')
    monkeypatch.setattr(activation, 'ROOT', release)
    values['source_manifest_sha256'] = activation.sha(manifest)
    config = tmp_path / 'pilot.yaml'
    original = b'mode: pilot\ncapabilities:\n  collection: true\n  retention: true\n  website_collection: true\n  abr: false\n  crm: false\n  sheets: false\n  backup: false\n'
    config.write_bytes(original)
    monkeypatch.setattr(activation, 'BACKUP', tmp_path / 'before.yaml')
    monkeypatch.setattr(activation, 'DECISIONS', tmp_path / 'decisions')
    receipt_path = path.parent / values['ghl_installation']['file']
    receipt = yaml.safe_load(receipt_path.read_text())
    for name, check in receipt['checks'].items():
        check['evidence_ref'] = str(activation.DECISIONS / values['check_evidence'][name]['file'])
    receipt_path.write_text(yaml.safe_dump(receipt))
    values['ghl_installation']['sha256'] = activation.sha(receipt_path)
    path.write_text(json.dumps(values))
    monkeypatch.setattr(activation.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(activation.os, 'O_NOFOLLOW', 0, raising=False)
    monkeypatch.setattr(activation, 'read_config', config.read_bytes)
    monkeypatch.setattr(activation, 'atomic_config', config.write_bytes)
    monkeypatch.setattr(activation, 'sync_directory', lambda _: None)
    monkeypatch.setattr(activation, 'activation_lock', nullcontext)
    commands, queries = [], []
    monkeypatch.setattr(activation, 'command', lambda args, **kwargs: commands.append(args) or '')
    monkeypatch.setattr(activation, 'unit_state', lambda action, unit: 'disabled' if action == 'is-enabled' else 'inactive')
    def evidence(source, plan):
        activation.DECISIONS.mkdir(exist_ok=True)
        for ref in activation.evidence_records(plan):
            (activation.DECISIONS / ref['file']).write_bytes((source.parent / ref['file']).read_bytes())
    monkeypatch.setattr(activation, 'install_evidence', evidence)
    service = Service(database, load_keys(database))
    with connect(database) as conn:
        fixture_policy = seed_policy(conn, service)
        record = seed_contact(conn, service, phone=True)
        service.add_contact(conn, lead_id=record['lead']['lead_id'], channel='landline', value='0730000001',
            identity_id=record['identity']['identity_id'], source_url='https://example.com/contact',
            excerpt='Synthetic test only', actor='fixture-collector', capture={
                'html': '<p>Synthetic phone 0730000001</p>', 'captured_at': service.now(conn),
                'collector_version': 'fixture-v1', 'robots_result': 'allowed',
                'terms_scope': 'Synthetic content only', 'method': 'synthetic-static'})
        conn.execute('DELETE FROM policy WHERE version=%s', (fixture_policy,))
        now = service.now(conn)
        for scope, gate, revision in sorted(activation.OLD_REVISIONS):
            conn.execute('INSERT INTO release_gate VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (gate, 'pilot', scope, revision, 'synthetic-old-authority', 'a'*64, 'synthetic-owner',
                 now-timedelta(minutes=5), activation.RETENTION_END if scope == 'retention' else activation.END))
        for number, version in enumerate((activation.phone.OLD_POLICY, activation.phone.POLICY)):
            conn.execute('INSERT INTO policy VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                (version, 'approved', 'pilot', 'synthetic-old-policy', 'synthetic-owner',
                 now-timedelta(minutes=4-number), activation.RETENTION_END, Jsonb({
                    'source_scope': 'qbcc-plus-manual-own-website-phone-review-only',
                    'adviser_status': 'not_obtained', 'outreach': 'disabled',
                    'retention': {'approved': True, 'restore_enabled': False, 'retain_selected_evidence': False},
                    'website_collection': {'approved': True, 'allowed_channels': ['mobile', 'landline'], 'expires_at': activation.END}})))
        content, snapshot = uuid4(), uuid4()
        conn.execute("INSERT INTO source_content VALUES(%s,'qbcc',%s,'synthetic','synthetic','synthetic')", (content, 'a'*64))
        conn.execute("INSERT INTO source_snapshot(snapshot_id,source,content_id,expected_cursor_version,manifest,state) VALUES(%s,'qbcc',%s,0,'{}','committed')", (snapshot, content))
        conn.execute("INSERT INTO source_cursor(source,snapshot_id,version) VALUES('qbcc',%s,1)", (snapshot,))
    def run_sql(query):
        queries.append(query)
        if 'has_table_privilege' in query: return 'f'
        with connect(database) as conn, conn.cursor(row_factory=tuple_row) as cursor:
            cursor.execute(query)
            if cursor.description:
                value = cursor.fetchone()[0]
                return json.dumps(value) if isinstance(value, dict) else str(value)
        return ''
    monkeypatch.setattr(activation, 'sql', run_sql)
    return {'path': path, 'values': values, 'config': config, 'original': original,
            'commands': commands, 'queries': queries, 'database': database, 'sql': run_sql}


def test_preview_reads_actual_pg_and_never_writes(host):
    before = set(host['path'].parent.rglob('*'))
    result = activation.install(host['path'])
    assert result['status'] == 'preview_passed' and result['new_gate_rows'] == 4
    assert result['provider_calls'] == 0 and not result['policy_changed']
    assert host['commands'] == [] and all(query.startswith('SELECT') for query in host['queries'])
    assert before == set(host['path'].parent.rglob('*')) and host['config'].read_bytes() == host['original']


def test_actual_pg_appends_only_crm_gates_preserves_policies_and_approves_no_lead(host):
    before = json.loads(host['sql'](activation.state_query()))
    result = activation.install(host['path'], execute=True, plan_sha256=activation.sha(host['path']))
    assert result['status'] == 'ghl_phone_dnd_authority_installed'
    after = json.loads(host['sql'](activation.state_query()))
    assert after['counts'] == {**activation.EXPECTED_COUNTS, 'release_gate': 23}
    assert after['policies'] == before['policies'] and host['commands'] == []
    changed = yaml.safe_load(host['config'].read_bytes())
    assert {key for key, enabled in changed['capabilities'].items() if enabled} == {'collection', 'retention', 'website_collection', 'crm'}
    assert Path(changed['ghl_config_file']).is_absolute() and Path(changed['ghl_installation_file']).is_absolute()
    assert activation.BACKUP.read_bytes() == host['original']


@pytest.mark.parametrize('failure', ['digest', 'active', 'backup', 'extra_business', 'privilege', 'unsafe_policy'])
def test_preview_rejects_changed_host_before_mutation(host, monkeypatch, failure):
    if failure in {'active', 'backup'}:
        monkeypatch.setattr(activation, 'unit_state', lambda action, unit: 'active' if failure == 'active' or unit == 'abr-engine-backup-daily.timer' else ('disabled' if action == 'is-enabled' else 'inactive'))
    elif failure == 'extra_business':
        with connect(host['database']) as conn:
            Service(host['database'], load_keys(host['database'])).create_lead(conn, name='Extra synthetic', source='qbcc', alias='87654321')
    elif failure == 'unsafe_policy':
        with connect(host['database']) as conn:
            conn.execute("UPDATE policy SET settings=jsonb_set(settings,'{retention,retain_selected_evidence}','true') WHERE version=%s", (activation.phone.POLICY,))
    elif failure == 'privilege':
        monkeypatch.setattr(activation, 'sql', lambda query: 't' if 'has_table_privilege' in query else host['sql'](query))
    with pytest.raises(activation.ActivationError):
        activation.install(host['path'], execute=True, plan_sha256='f'*64 if failure == 'digest' else activation.sha(host['path']))
    assert not activation.BACKUP.exists() and host['config'].read_bytes() == host['original']


@pytest.mark.parametrize('failure', ['before_sql', 'after_commit', 'changed_gate', 'concurrent_config'])
def test_failure_preserves_history_and_never_starts_services(host, monkeypatch, failure):
    if failure == 'before_sql':
        monkeypatch.setattr(activation, 'install_evidence', lambda *args: (_ for _ in ()).throw(RuntimeError('synthetic-private-error')))
    else:
        def changed(query):
            result = host['sql'](query)
            if query.startswith('BEGIN'):
                if failure == 'after_commit': raise RuntimeError('synthetic-private-error')
                if failure == 'changed_gate':
                    with connect(host['database']) as conn:
                        conn.execute("UPDATE release_gate SET actor_id='unexpected' WHERE scope='crm' AND gate_name='G5'")
                else: host['config'].write_bytes(b'synthetic concurrent configuration')
            return result
        monkeypatch.setattr(activation, 'sql', changed)
    with pytest.raises(activation.ActivationError, match='ACTIVATION_'):
        activation.install(host['path'], execute=True, plan_sha256=activation.sha(host['path']))
    after = json.loads(host['sql'](activation.state_query()))
    assert after['counts']['release_gate'] == (19 if failure == 'before_sql' else 23)
    assert all(command[:2] == ['systemctl', 'stop'] for command in host['commands'])
    assert host['config'].read_bytes() == (b'synthetic concurrent configuration' if failure == 'concurrent_config' else host['original'])
