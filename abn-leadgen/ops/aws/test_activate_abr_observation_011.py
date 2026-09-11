"""Synthetic operator boundaries; no host, provider or production DB calls."""
import copy
import importlib.util
import json
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

SPEC = importlib.util.spec_from_file_location('activate_abr_observation_011', Path(__file__).with_name('activate_abr_observation_011.py'))
activation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(activation)


@pytest.fixture
def plan(tmp_path, monkeypatch):
    now = datetime.now(UTC)
    def save(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value))
        return {'file': name, 'sha256': activation.digest(path.read_bytes())}
    owner = save('owner.json', {'decision_id': 'abr-early-validation-delegated-owner-20260911',
        'source_purpose_approved': True, 'expires_at': activation.END, 'adviser_status': 'not_obtained',
        'legal_compliance_certified': False, 'effective_at': (now-timedelta(minutes=5)).isoformat(),
        'retention': {'finite_deletion_authority_expires_at': activation.RETENTION_END, 'retain_selected_evidence': False}})
    mapping = save('mapping.json', {'synthetic': 'mapping'})
    monkeypatch.setattr(activation, 'OWNER', owner['sha256'])
    monkeypatch.setattr(activation, 'MAPPING', mapping['sha256'])
    technical = save('technical.json', {'status': 'approved_for_scoped_abr_observation',
        'source_manifest_before_sha256': activation.OLD, 'source_manifest_sha256': 'b'*64,
        'owner_evidence_sha256': owner['sha256'], 'mapping_evidence_sha256': mapping['sha256'],
        'validation': {'independent_review': 'passed_no_blocking_findings'},
        'classification_enabled': False, 'full_production_release': False})
    notice = save('notice.json', {'http_status': 200, 'checks_passed': 21,
        'url': 'https://www.maintainmedia.com.au/business-research-notice', 'body_sha256': 'c'*64,
        'checked_at': (now-timedelta(minutes=4)).isoformat()})
    config = save('config.json', {'operation': 'observe_only', 'source_scope_evidence_sha256': owner['sha256'],
        'mapping_evidence_sha256': mapping['sha256'], 'expires_at': activation.END})
    monkeypatch.setattr(activation, 'CONFIG_SHA', config['sha256'])
    service, timer = save('worker.service', {'synthetic': 'unit'}), save('worker.timer', {'synthetic': 'timer'})
    values = {'version': 'abr-observation-011-v1', 'actor_id': activation.ACTOR, 'adviser_status': 'not_obtained',
        'approved_at': (now-timedelta(seconds=3)).isoformat(), 'policy_version': activation.POLICY,
        'source_manifest_before_sha256': activation.OLD, 'source_manifest_sha256': 'b'*64,
        'configuration_before_sha256': activation.BEFORE_CONFIG, 'baseline_state_sha256': None,
        'full_production_release': False, 'production_backup_accepted': False, 'source_runs_requested': 0,
        'owner_evidence': owner, 'mapping_evidence': mapping, 'technical_evidence': technical,
        'notice_evidence': notice, 'abr_config': config, 'worker_service': service, 'worker_timer': timer}
    path = tmp_path / 'plan.json'; path.write_text(json.dumps(values))
    return path, values


@pytest.fixture
def baseline():
    data = json.loads((Path(__file__).parents[1] / 'acceptance/aws/abr-preactivation-state-20260911.json').read_text())
    # The checked-in fixture contains public gate/policy metadata and counts only.
    # None of its files/IDs is used for a real operation.
    return {key: data[key] for key in ('counts', 'gates', 'policies', 'running_jobs', 'nonphone_contacts')}


def test_plan_has_nine_scoped_gates_and_preserves_existing_policy_content(plan, baseline):
    path, values = plan
    assert activation.read_plan(path) == values
    activation.validate_state(baseline)
    before = copy.deepcopy(baseline)
    rows = activation.gate_rows(values)
    assert {(x['scope'], x['gate_name'], x['revision']) for x in rows} == {
        *(('abr', gate, 1) for gate in ('G1', 'G2', 'G3', 'G6', 'G7')),
        ('retention', 'G1', 3), ('retention', 'G3', 4), ('retention', 'G7', 5), ('collection', 'G7', 5)}
    assert all(row['expires_at'] == (activation.RETENTION_END if row['scope'] == 'retention' else activation.END) for row in rows)
    current = activation.policy_row(values, baseline)
    assert baseline == before
    old_settings, new_settings = baseline['policies'][-1]['settings'], current['settings']
    assert new_settings['website_collection'] == old_settings['website_collection']
    assert {k: v for k, v in new_settings.items() if k not in {'abr', 'retention'}} == {
        k: v for k, v in old_settings.items() if k != 'retention'}
    assert new_settings['retention']['evidence_sha256'] == activation.OWNER
    assert new_settings['retention']['continued_evidence_sha256'] == [old_settings['retention']['evidence_sha256']]
    assert new_settings['retention']['retain_selected_evidence'] is False
    assert new_settings['retention']['restore_enabled'] is False
    assert new_settings['abr'] == {'approved': True, 'operation': 'observe_only', 'classification_enabled': False,
        'evidence_sha256': activation.OWNER, 'expires_at': activation.END}


@pytest.mark.parametrize('failure', ['extra', 'actor', 'live', 'backup', 'job', 'bool_job', 'old', 'config',
    'path', 'duplicate_file', 'hash', 'owner', 'mapping', 'policy', 'future', 'state'])
def test_plan_refuses_unreviewed_scope_or_input(plan, failure):
    path, values = plan
    if failure == 'extra': values['enable_classification'] = True
    elif failure == 'actor': values['actor_id'] = 'unrelated'
    elif failure == 'live': values['full_production_release'] = True
    elif failure == 'backup': values['production_backup_accepted'] = True
    elif failure == 'job': values['source_runs_requested'] = 1
    elif failure == 'bool_job': values['source_runs_requested'] = False
    elif failure == 'old': values['source_manifest_before_sha256'] = 'd'*64
    elif failure == 'config': values['configuration_before_sha256'] = 'd'*64
    elif failure == 'path': values['owner_evidence']['file'] = '../private.json'
    elif failure == 'duplicate_file': values['mapping_evidence'] = values['owner_evidence']
    elif failure == 'hash': values['technical_evidence']['sha256'] = 'd'*64
    elif failure == 'owner': values['owner_evidence']['sha256'] = 'd'*64
    elif failure == 'mapping': values['mapping_evidence']['sha256'] = 'd'*64
    elif failure == 'policy': values['policy_version'] = 'replace-existing'
    elif failure == 'future': values['approved_at'] = (datetime.now(UTC)+timedelta(hours=1)).isoformat()
    elif failure == 'state': values['baseline_state_sha256'] = 'invalid'
    path.write_text(json.dumps(values))
    with pytest.raises(activation.ActivationError): activation.read_plan(path)


def test_environment_file_refused_before_content_access(tmp_path, monkeypatch):
    path = tmp_path / '.env.json'; path.write_text('never read')
    monkeypatch.setattr(activation, 'ordinary', lambda _: pytest.fail('Rejected before touching contents'))
    with pytest.raises(activation.ActivationError, match='PUBLIC_JSON_REQUIRED'): activation.read_json(path)


def test_duplicate_json_keys_refused(plan):
    path, _ = plan
    path.write_text('{"version":"one","version":"two"}')
    with pytest.raises(activation.ActivationError, match='DUPLICATE_JSON_FIELD'): activation.read_plan(path)


@pytest.mark.parametrize('key,change', [('technical_evidence', {'classification_enabled': True}),
    ('technical_evidence', {'validation': {'independent_review': 'pending'}}),
    ('technical_evidence', {'source_manifest_sha256': 'd'*64}),
    ('notice_evidence', {'http_status': 403}), ('notice_evidence', {'checks_passed': 0}),
    ('notice_evidence', {'checked_at': '2099-01-01T00:00:00Z'})])
def test_stale_or_unfinished_evidence_cannot_admit(plan, key, change):
    path, values = plan
    file = path.parent / values[key]['file']
    document = json.loads(file.read_text()) | change
    file.write_text(json.dumps(document)); values[key]['sha256'] = activation.digest(file.read_bytes())
    path.write_text(json.dumps(values))
    with pytest.raises(activation.ActivationError): activation.read_plan(path)


def test_append_readback_rejects_changed_history_business_counts_or_wrong_policy(plan, baseline):
    _, values = plan
    after = copy.deepcopy(baseline)
    after['counts'] |= {'release_gate': 34, 'policy': 3}
    after['gates'] = sorted([*after['gates'], *activation.gate_rows(values)], key=lambda r: (r['scope'], r['gate_name'], r['revision']))
    after['policies'].append(activation.policy_row(values, baseline))
    activation.verify_after(baseline, after, values)
    for change in ('old_gate', 'phone', 'policy', 'lead', 'approval', 'gate'):
        bad = copy.deepcopy(after)
        if change == 'old_gate': next(g for g in bad['gates'] if g['scope'] == 'crm')['evidence_sha256'] = 'd'*64
        elif change == 'phone': bad['policies'][-1]['settings']['website_collection']['allowed_channels'] = ['email']
        elif change == 'policy': bad['policies'][0]['settings']['outreach'] = 'enabled'
        elif change == 'lead': bad['counts']['lead_entity'] += 1
        elif change == 'approval': bad['counts']['worklist_row'] += 1
        else: bad['gates'].pop()
        with pytest.raises(activation.ActivationError): activation.verify_after(baseline, bad, values)


@pytest.fixture
def host(plan, baseline, monkeypatch):
    path, values = plan
    values['baseline_state_sha256'] = activation.digest(activation.canonical(baseline).encode())
    path.write_text(json.dumps(values))
    config = {'mode': 'pilot', 'capabilities': {'collection': True, 'retention': True, 'website_collection': True,
        'crm': True, 'abr': False, 'sheets': False, 'backup': False}, 'ghl_config_file': '/synthetic/ghl.yaml',
        'ghl_installation_file': '/synthetic/receipt.yaml'}
    original = yaml.safe_dump(config).encode()
    state = copy.deepcopy(baseline)
    calls, database_writes, saved = [], [], {'config': original}
    def command(args, **kwargs):
        calls.append(args)
        return 'not-found' if args[:2] == ['systemctl', 'show'] else ''
    def sql(query):
        if query == 'SELECT count(*) FROM action_intent;': return '0'
        if query.startswith('SELECT has_table_privilege'): return 'f'
        if query.startswith('BEGIN'):
            database_writes.append(query)
            state['counts'] |= {'release_gate': 34, 'policy': 3}
            state['gates'] = sorted([*state['gates'], *activation.gate_rows(values)], key=lambda r: (r['scope'], r['gate_name'], r['revision']))
            state['policies'].append(activation.policy_row(values, baseline))
            return ''
        return json.dumps(state)
    common = SimpleNamespace(sql=sql, command=command, literal=lambda x: "'"+str(x).replace("'", "''")+"'",
        read_config=lambda: saved['config'], atomic_config=lambda x: saved.update(config=x),
        activation_lock=nullcontext, unit_state=lambda action, _: 'disabled' if action == 'is-enabled' else 'inactive')
    source = SimpleNamespace(activate=lambda: calls.append(['source_cutover']), manifest=lambda *_: None)
    monkeypatch.setattr(activation, 'host_preflight', lambda *args: (original, copy.deepcopy(config)))
    monkeypatch.setattr(activation, 'install_files', lambda *args: calls.append(['install_files']))
    monkeypatch.setattr(activation, 'prepare_venv', lambda *args: calls.append(['prepare_venv']))
    return path, values, common, source, calls, database_writes, saved, original


def test_default_preview_has_no_mutation_and_reports_exact_counts(host):
    path, _, common, source, calls, writes, saved, original = host
    result = activation.install(path, helpers=(common, source))
    assert result['status'] == 'preview_passed'
    assert (result['new_gates'], result['total_gates'], result['total_policies']) == (9, 34, 3)
    assert calls == [] and writes == [] and saved['config'] == original


def test_apply_requires_reviewed_plan_and_state_digests(host):
    path, values, common, source, calls, writes, _, _ = host
    with pytest.raises(activation.ActivationError, match='REVIEWED_PLAN_AND_STATE_DIGEST_REQUIRED'):
        activation.install(path, execute=True, plan_sha256='d'*64, helpers=(common, source))
    values['baseline_state_sha256'] = None; path.write_text(json.dumps(values))
    with pytest.raises(activation.ActivationError, match='REVIEWED_PLAN_AND_STATE_DIGEST_REQUIRED'):
        activation.install(path, execute=True, plan_sha256=activation.digest(path.read_bytes()), helpers=(common, source))
    assert calls == [] and writes == []


def test_apply_orders_stop_cutover_append_then_exact_config_without_start_or_admission(host):
    path, _, common, source, calls, writes, saved, original = host
    result = activation.install(path, execute=True, plan_sha256=activation.digest(path.read_bytes()), helpers=(common, source))
    assert result['status'] == 'abr_observation_011_installed_services_stopped'
    assert calls.index(next(c for c in calls if c[:2] == ['systemctl', 'stop'])) < calls.index(['source_cutover'])
    assert len(writes) == 1 and 'LOCK TABLE' in writes[0] and 'baseline changed' in writes[0]
    assert writes[0].count('INSERT INTO release_gate(') == 9 and writes[0].count('INSERT INTO policy(') == 1
    assert all(not any(word in command for word in ('start', 'enable', 'restart')) for command in calls)
    expected = yaml.safe_load(original); expected['capabilities']['abr'] = True
    expected['abr_config_file'] = str(activation.ABR_CONFIG)
    assert yaml.safe_load(saved['config']) == expected
    assert result['source_runs_requested'] == 0 and result['services_started'] is False


@pytest.mark.parametrize('boundary', ['files', 'cutover', 'venv', 'readback', 'config', 'reload'])
def test_failure_keeps_services_stopped_original_config_and_never_deletes_authority(host, monkeypatch, boundary):
    path, _, common, source, calls, writes, saved, original = host
    def fail(*args, **kwargs): raise RuntimeError('synthetic_secret_do_not_reflect')
    if boundary == 'files': monkeypatch.setattr(activation, 'install_files', fail)
    elif boundary == 'cutover': source.activate = fail
    elif boundary == 'venv': monkeypatch.setattr(activation, 'prepare_venv', fail)
    elif boundary == 'readback': monkeypatch.setattr(activation, 'verify_after', fail)
    elif boundary == 'config': common.atomic_config = fail
    else:
        original_command = common.command
        common.command = lambda args, **kwargs: fail() if args == ['systemctl', 'daemon-reload'] else original_command(args, **kwargs)
    with pytest.raises(activation.ActivationError, match='ACTIVATION_FAILED_CLOSED_HISTORY_PRESERVED') as caught:
        activation.install(path, execute=True, plan_sha256=activation.digest(path.read_bytes()), helpers=(common, source))
    assert 'synthetic_secret' not in str(caught.value)
    assert saved['config'] == original
    assert all('DELETE FROM' not in query and 'UPDATE release_gate' not in query for query in writes)
    assert any(c[:2] == ['systemctl', 'stop'] for c in calls)
    assert all(not any(word in command for word in ('start', 'enable', 'restart')) for command in calls)


@pytest.fixture
def preflight(plan, tmp_path, monkeypatch):
    path, values = plan
    for name in ('CURRENT', 'STAGED', 'PREVIOUS', 'DECISIONS', 'ABR_CONFIG', 'BACKUP', 'UNITS'):
        monkeypatch.setattr(activation, name, tmp_path / name.lower())
    activation.CURRENT.mkdir(); activation.STAGED.mkdir(); activation.UNITS.mkdir()
    for folder in (activation.CURRENT, activation.STAGED):
        (folder / 'uv.lock').write_bytes(b'synthetic reviewed unchanged dependencies')
    for key, relative in [('mapping_evidence', 'config/sources/abr-public-mapping.json'),
        ('worker_service', 'ops/aws/abr-engine-abr-worker.service'),
        ('worker_timer', 'ops/aws/abr-engine-abr-worker.timer')]:
        target = activation.STAGED / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((path.parent / values[key]['file']).read_bytes())
    settings = {'mode': 'pilot', 'capabilities': {'collection': True, 'retention': True,
        'website_collection': True, 'crm': True, 'abr': False, 'sheets': False, 'backup': False}}
    original = yaml.safe_dump(settings).encode()
    monkeypatch.setattr(activation, 'BEFORE_CONFIG', activation.digest(original))
    monkeypatch.setattr(activation.os, 'geteuid', lambda: 0, raising=False)
    calls, manifests, validations = [], [], []
    common = SimpleNamespace(read_config=lambda: original,
        command=lambda args: calls.append(args) or 'not-found')
    source = SimpleNamespace(manifest=lambda *args: manifests.append(args))
    monkeypatch.setattr(activation, 'validate_staged', lambda *args: validations.append(args))
    return path, values, common, source, calls, manifests, validations, original, settings


def test_preflight_verifies_both_manifests_and_inputs_without_mutations(preflight):
    path, values, common, source, calls, manifests, validations, original, settings = preflight
    assert activation.host_preflight(common, source, values, path) == (original, settings)
    assert manifests == [(activation.CURRENT, activation.OLD),
        (activation.STAGED, values['source_manifest_sha256'])]
    assert len(validations) == 1
    assert calls == [['systemctl', 'show', unit, '--property=LoadState', '--value'] for unit in activation.ABR_UNITS]
    assert not activation.BACKUP.exists() and not activation.ABR_CONFIG.exists()


@pytest.mark.parametrize('change,code', [('dependency', 'UNCHANGED_DEPENDENCIES_REQUIRED'),
    ('existing_config', 'PRIOR_ACTIVATION_REQUIRES_REVIEW'),
    ('existing_unit', 'EXISTING_ABR_UNIT_REQUIRES_REVIEW'), ('mapping', 'STAGED_INPUT_CHANGED'),
    ('configuration', 'CONFIGURATION_BASELINE_CHANGED'), ('root', 'ROOT_REQUIRED')])
def test_preflight_refuses_changed_host_before_staged_execution(preflight, monkeypatch, change, code):
    path, values, common, source, calls, _, validations, _, _ = preflight
    if change == 'dependency': (activation.STAGED / 'uv.lock').write_bytes(b'unreviewed dependencies')
    elif change == 'existing_config': activation.ABR_CONFIG.write_bytes(b'unrelated owned configuration')
    elif change == 'existing_unit': common.command = lambda args: calls.append(args) or 'loaded'
    elif change == 'mapping': (activation.STAGED / 'config/sources/abr-public-mapping.json').write_bytes(b'changed')
    elif change == 'configuration': common.read_config = lambda: b'unreviewed configuration'
    else: monkeypatch.setattr(activation.os, 'geteuid', lambda: 1000)
    with pytest.raises(activation.ActivationError, match=code):
        activation.host_preflight(common, source, values, path)
    assert not validations
    assert all(args[:2] == ['systemctl', 'show'] for args in calls)


def test_stopped_database_change_prevents_cutover_and_authority_append(host):
    path, _, common, source, calls, writes, saved, original = host
    original_sql = common.sql
    seen = 0
    def sql(query):
        nonlocal seen
        result = original_sql(query)
        if query.startswith('SELECT json_build_object'):
            seen += 1
            if seen == 2:
                changed = json.loads(result); changed['counts']['lead_entity'] += 1
                return json.dumps(changed)
        return result
    common.sql = sql
    with pytest.raises(activation.ActivationError, match='ACTIVATION_FAILED_CLOSED_HISTORY_PRESERVED'):
        activation.install(path, execute=True, plan_sha256=activation.digest(path.read_bytes()), helpers=(common, source))
    assert ['source_cutover'] not in calls and ['install_files'] not in calls and not writes
    assert saved['config'] == original


def test_concurrent_configuration_after_commit_is_not_overwritten(host, monkeypatch):
    path, _, common, source, calls, writes, saved, _ = host
    changed = b'synthetic concurrent operator configuration'
    original_verify = activation.verify_after
    def verify(*args):
        original_verify(*args)
        saved['config'] = changed
    monkeypatch.setattr(activation, 'verify_after', verify)
    common.atomic_config = lambda _: pytest.fail('Must never overwrite concurrent configuration')
    with pytest.raises(activation.ActivationError, match='ACTIVATION_RECOVERY_REQUIRES_REVIEW'):
        activation.install(path, execute=True, plan_sha256=activation.digest(path.read_bytes()), helpers=(common, source))
    assert len(writes) == 1 and saved['config'] == changed
    assert all('DELETE FROM' not in query for query in writes)
    assert all(not any(word in args for word in ('start', 'enable', 'restart')) for args in calls)


def test_staged_validation_uses_isolated_network_and_only_planned_stdin(preflight):
    path, values, common, _, _, _, _, _, settings = preflight
    # Call the original function, not the fixture's preflight-only validation stub.
    spec = importlib.util.spec_from_file_location('abr011_validation_test', Path(activation.__file__))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    calls = []
    common.command = lambda args, **kwargs: calls.append((args, kwargs)) or 'validated'
    module.validate_staged(common, values, settings, path)
    args, kwargs = calls[0]
    assert args[:5] == ['unshare', '--net', '--', 'env', '-i']
    assert 'PYTHONDONTWRITEBYTECODE=1' in args and '.env' not in ' '.join(args)
    assert 'observe_only' not in ' '.join(args)
    payload = json.loads(kwargs['data'])
    assert payload['settings']['capabilities']['abr'] is True
    assert payload['settings']['abr_config_file'] == str(module.ABR_CONFIG)
    assert json.loads(payload['abr'])['operation'] == 'observe_only'
    assert settings['capabilities']['abr'] is False
