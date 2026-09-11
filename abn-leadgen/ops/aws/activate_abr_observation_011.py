"""Reviewed 010 -> 011 ABR observation activation; preview by default.

No source jobs, provider calls, credentials, service starts or timer enablement.
Any interrupted mutation requires operator reconciliation with services stopped.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path

import yaml

ACTOR = 'delegated-owner:jeph@quotemax.com.au'
OLD = '608bcbcb881f2787db2f6f408e666c5e3debe0d4a59760085e62d3c4aa1c5660'
OWNER = 'a47fec2220191ecb8f5fb44dcdf8c8dd1185e4f77d29a7ee02ce3ec2257dbc3e'
MAPPING = '18036346d16df9cefd2e0219ece86893fe6461d25639467b7d7653602a9da152'
CONFIG_SHA = 'd5f7c1544fc53b8b2ce40643cead40482a8876d586f62279b9fa9d9370e3010e'
BEFORE_CONFIG = '5aa20561d01da70059d0c9ff41a6c9cdc41b458db1d7eb0f7b5fc22217b6af2d'
END = '2026-09-24T23:18:20Z'
RETENTION_END = '2027-09-10T23:18:20Z'
POLICY = 'abr-observation-delegated-pilot-retention-20260911-v1'
CURRENT = Path('/opt/abn-leadgen')
STAGED = Path('/opt/abn-leadgen-live-20260911-011-stage')
PREVIOUS = Path('/opt/abn-leadgen-live-20260911-010-previous')
DECISIONS = Path('/etc/abr-engine/decisions/abr-observation-011-20260911')
ABR_CONFIG = Path('/etc/abr-engine/abr-observation.json')
BACKUP = Path('/etc/abr-engine/pilot.before-abr-observation-011-20260911.yaml')
UNITS = Path('/etc/systemd/system')
CORE_UNITS = ['abr-engine-api.service', 'abr-engine-worker.timer', 'abr-engine-worker.service',
    'abr-engine-control.timer', 'abr-engine-control.service', 'abr-engine-retention.timer',
    'abr-engine-retention.service', 'abr-engine-qbcc-review-cleanup.timer',
    'abr-engine-qbcc-review-cleanup.service']
ABR_UNITS = ['abr-engine-abr-worker.service', 'abr-engine-abr-worker.timer']
CLOSED_TIMERS = ['abr-engine-qbcc-weekly.timer', 'abr-engine-backup-daily.timer',
                 'abr-engine-backup-ledger.timer', 'abr-engine-backup-expiry.timer']
HELPERS = {'activate_qbcc_pilot.py': '21db170a7df3bf03bc9179f9b49d3adc90b430bc78f523618e66a4dc21f90b2f',
           'activate_live_source.py': 'e52d280dca56e55b01972243b6b0aad79a69128dcb6e1c46cec13d41e2a935d2'}
COUNTS = {'release_gate': 25, 'policy': 2, 'schema_migration': 26, 'lead_entity': 1,
    'contact_record': 2, 'source_snapshot': 1, 'source_cursor': 1, 'worklist_row': 0,
    'crm_outbox': 0, 'crm_identity': 0}
EVIDENCE = ('owner_evidence', 'mapping_evidence', 'technical_evidence', 'notice_evidence',
            'abr_config', 'worker_service', 'worker_timer')
FIELDS = {'version', 'actor_id', 'adviser_status', 'approved_at', 'source_manifest_before_sha256',
    'source_manifest_sha256', 'configuration_before_sha256', 'baseline_state_sha256', 'policy_version',
    'full_production_release', 'production_backup_accepted', 'source_runs_requested', *EVIDENCE}


class ActivationError(ValueError):
    """Fixed, non-sensitive operator codes only."""


def require(value, code):
    if not value:
        raise ActivationError(code)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def ordinary(path):
    require(path.is_absolute() and '..' not in path.parts, 'PUBLIC_PATH_REQUIRED')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'LINKED_PATH_REFUSED')
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'REGULAR_PUBLIC_FILE_REQUIRED')


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'DUPLICATE_JSON_FIELD')
        result[key] = value
    return result


def read_json(path):
    require(path.suffix == '.json' and not path.name.startswith('.'), 'PUBLIC_JSON_REQUIRED')
    ordinary(path)
    require(path.stat().st_size <= 1024 * 1024, 'PUBLIC_INPUT_SIZE_LIMIT')
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def is_sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def read_plan(path, *, now=None):
    plan = read_json(path)
    require(isinstance(plan, dict) and set(plan) == FIELDS, 'EXACT_PLAN_FIELDS_REQUIRED')
    require(plan['version'] == 'abr-observation-011-v1' and plan['actor_id'] == ACTOR
        and plan['adviser_status'] == 'not_obtained' and plan['policy_version'] == POLICY
        and plan['source_manifest_before_sha256'] == OLD
        and plan['configuration_before_sha256'] == BEFORE_CONFIG
        and is_sha(plan['source_manifest_sha256']) and plan['source_manifest_sha256'] != OLD
        and (plan['baseline_state_sha256'] is None or is_sha(plan['baseline_state_sha256']))
        and plan['full_production_release'] is False and plan['production_backup_accepted'] is False
        and type(plan['source_runs_requested']) is int and plan['source_runs_requested'] == 0,
        'EXACT_OBSERVATION_SCOPE_REQUIRED')
    start = datetime.fromisoformat(plan['approved_at'])
    require(start.tzinfo is not None and start <= (now or datetime.now(UTC)) < datetime.fromisoformat(END),
            'CURRENT_DECISION_REQUIRED')
    names = set()
    for key in EVIDENCE:
        record = plan[key]
        require(isinstance(record, dict) and set(record) == {'file', 'sha256'}
            and isinstance(record['file'], str)
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,159}\.(?:json|service|timer)', record['file'])
            and is_sha(record['sha256']) and record['file'] not in names, 'EXACT_PUBLIC_EVIDENCE_REQUIRED')
        names.add(record['file'])
        file = path.parent / record['file']
        ordinary(file)
        require(file.stat().st_size <= 1024 * 1024 and digest(file.read_bytes()) == record['sha256'],
                'EVIDENCE_DIGEST_CHANGED')
    require(plan['owner_evidence']['sha256'] == OWNER and plan['mapping_evidence']['sha256'] == MAPPING
            and plan['abr_config']['sha256'] == CONFIG_SHA,
            'PINNED_OWNER_AND_MAPPING_REQUIRED')
    owner = read_json(path.parent / plan['owner_evidence']['file'])
    require(owner['decision_id'] == 'abr-early-validation-delegated-owner-20260911'
        and owner['source_purpose_approved'] is True and owner['expires_at'] == END
        and owner['legal_compliance_certified'] is False and owner['adviser_status'] == 'not_obtained'
        and datetime.fromisoformat(owner['effective_at']) <= start
        and owner['retention']['finite_deletion_authority_expires_at'] == RETENTION_END
        and owner['retention']['retain_selected_evidence'] is False, 'OWNER_SCOPE_CHANGED')
    technical = read_json(path.parent / plan['technical_evidence']['file'])
    require(technical.get('status') == 'approved_for_scoped_abr_observation'
        and technical.get('source_manifest_sha256') == plan['source_manifest_sha256']
        and technical.get('source_manifest_before_sha256') == OLD
        and technical.get('owner_evidence_sha256') == OWNER and technical.get('mapping_evidence_sha256') == MAPPING
        and technical.get('validation', {}).get('independent_review') == 'passed_no_blocking_findings'
        and technical.get('classification_enabled') is False and technical.get('full_production_release') is False,
        'REVIEWED_TECHNICAL_RELEASE_REQUIRED')
    notice = read_json(path.parent / plan['notice_evidence']['file'])
    require(notice.get('http_status') == 200 and notice.get('checks_passed', 0) >= 21
        and notice.get('url') == 'https://www.maintainmedia.com.au/business-research-notice'
        and is_sha(notice.get('body_sha256')) and datetime.fromisoformat(notice['checked_at']) <= start,
        'NOTICE_BEFORE_ACTIVATION_REQUIRED')
    config = read_json(path.parent / plan['abr_config']['file'])
    require(config.get('operation') == 'observe_only' and config.get('source_scope_evidence_sha256') == OWNER
        and config.get('mapping_evidence_sha256') == MAPPING and config.get('expires_at') == END,
        'EXACT_ABR_CONFIGURATION_REQUIRED')
    return plan


def load_helpers(directory):
    modules = []
    for name, expected in HELPERS.items():
        path = directory / name
        ordinary(path)
        require(digest(path.read_bytes()) == expected, 'PINNED_HELPER_CHANGED')
        spec = importlib.util.spec_from_file_location('abr011_' + path.stem, path)
        if spec is None or spec.loader is None:
            raise ActivationError('PINNED_HELPER_IMPORT_FAILED')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


def state_query(common):
    counts = ','.join(common.literal(t) + ',(SELECT count(*) FROM ' + t + ')' for t in COUNTS)
    return "SELECT json_build_object('counts',json_build_object(" + counts + "),'gates'," \
        "(SELECT json_agg(g ORDER BY scope,gate_name,revision) FROM release_gate g),'policies'," \
        "(SELECT json_agg(p ORDER BY approved_at,version) FROM policy p),'running_jobs'," \
        "(SELECT count(*) FROM pipeline_run WHERE state='running'),'nonphone_contacts'," \
        "(SELECT count(*) FROM contact_record WHERE channel NOT IN ('mobile','landline')));"


def validate_state(state):
    require(state['counts'] == COUNTS and len(state['gates']) == 25 and len(state['policies']) == 2
        and state['running_jobs'] == 0 and state['nonphone_contacts'] == 0
        and all(g['environment'] == 'pilot' and g['scope'] != 'abr' for g in state['gates']),
        'EXACT_PREACTIVATION_STATE_REQUIRED')
    latest = state['policies'][-1]
    settings = latest['settings']
    require(latest['version'] == 'website-phone-delegated-pilot-retention-20260911-v1'
        and latest['state'] == 'approved' and latest['scope'] == 'pilot'
        and datetime.fromisoformat(latest['approved_at']) <= datetime.now(UTC) < datetime.fromisoformat(latest['expires_at'])
        and datetime.fromisoformat(latest['expires_at']) == datetime.fromisoformat(RETENTION_END)
        and settings['outreach'] == 'disabled' and settings['adviser_status'] == 'not_obtained'
        and settings['website_collection']['approved'] is True
        and settings['website_collection']['allowed_channels'] == ['mobile', 'landline']
        and settings['retention']['approved'] is True and settings['retention']['restore_enabled'] is False
        and settings['retention']['retain_selected_evidence'] is False and 'abr' not in settings,
        'EXISTING_PHONE_AND_RETENTION_SCOPE_REQUIRED')


def gate_rows(plan):
    additions = [('abr', gate, 1) for gate in ('G1', 'G2', 'G3', 'G6', 'G7')]
    additions += [('retention', 'G1', 3), ('retention', 'G3', 4), ('retention', 'G7', 5),
                  ('collection', 'G7', 5)]
    rows = []
    for scope, gate, revision in additions:
        evidence = plan['owner_evidence' if gate in {'G1', 'G6'} else
                        'mapping_evidence' if gate == 'G2' else 'technical_evidence']
        rows.append({'scope': scope, 'gate_name': gate, 'revision': revision, 'environment': 'pilot',
            'evidence_ref': str(DECISIONS / evidence['file']), 'evidence_sha256': evidence['sha256'],
            'actor_id': ACTOR, 'approved_at': plan['approved_at'],
            'expires_at': RETENTION_END if scope == 'retention' else END})
    return rows


def policy_row(plan, initial):
    settings = copy.deepcopy(initial['policies'][-1]['settings'])
    retention = settings['retention']
    retention['continued_evidence_sha256'] = list(dict.fromkeys([
        *retention.get('continued_evidence_sha256', []), retention['evidence_sha256']]))
    retention['evidence_sha256'] = OWNER
    settings['abr'] = {'approved': True, 'operation': 'observe_only', 'classification_enabled': False,
                       'evidence_sha256': OWNER, 'expires_at': END}
    return {'version': POLICY, 'state': 'approved', 'scope': 'pilot', 'actor_id': ACTOR,
        'evidence_ref': str(DECISIONS / plan['owner_evidence']['file']), 'approved_at': plan['approved_at'],
        'expires_at': RETENTION_END, 'settings': settings}


def statement(common, table, row):
    require(table in {'release_gate', 'policy'}, 'AUTHORITY_TABLE_REQUIRED')
    values = [common.literal(json.dumps(v) if isinstance(v, (dict, list)) else v) for v in row.values()]
    return 'INSERT INTO ' + table + '(' + ','.join(row) + ') VALUES(' + ','.join(values) + ');'


def normal(row):
    result = copy.deepcopy(row)
    for key in ('approved_at', 'expires_at'):
        if key in result:
            result[key] = datetime.fromisoformat(result[key]).isoformat()
    return result


def verify_after(initial, after, plan):
    rows = gate_rows(plan)
    new_keys = {(r['scope'], r['gate_name'], r['revision']) for r in rows}
    added: list[dict] = []
    old: list[dict] = []
    for row in after['gates']:
        (added if (row['scope'], row['gate_name'], row['revision']) in new_keys else old).append(row)
    require(after['counts'] == {**COUNTS, 'release_gate': 34, 'policy': 3}
        and old == initial['gates'] and after['policies'][:-1] == initial['policies']
        and sorted(map(normal, added), key=canonical) == sorted(map(normal, rows), key=canonical)
        and normal(after['policies'][-1]) == normal(policy_row(plan, initial))
        and after['running_jobs'] == 0 and after['nonphone_contacts'] == 0,
        'APPEND_ONLY_AUTHORITY_READBACK_FAILED')


def validate_staged(common, plan, settings, path):
    payload = {'settings': {**settings, 'abr_config_file': str(ABR_CONFIG),
                           'capabilities': {**settings['capabilities'], 'abr': True}},
               'abr': (path.parent / plan['abr_config']['file']).read_text()}
    code = "import json,sys; from pathlib import Path; import abr_engine.live.abr as a; " \
        "from abr_engine.config import Settings; d=json.load(sys.stdin); " \
        "assert Path(a.__file__).resolve().is_relative_to(Path(sys.argv[1])); " \
        "Settings.model_validate(d['settings']); a.ABRLiveConfig.model_validate_json(d['abr']); print('validated')"
    output = common.command(['unshare', '--net', '--', 'env', '-i', 'PATH=/usr/bin:/bin',
        'PYTHONDONTWRITEBYTECODE=1', 'PYTHONPATH=' + str(STAGED / 'src'),
        str(CURRENT / '.venv/bin/python'), '-c', code, str(STAGED)], data=json.dumps(payload))
    require(output == 'validated', 'STAGED_CONFIGURATION_VALIDATION_FAILED')


def host_preflight(common, source, plan, path):
    require(os.geteuid() == 0, 'ROOT_REQUIRED')
    source.CURRENT, source.STAGED, source.PREVIOUS = CURRENT, STAGED, PREVIOUS
    source.OLD_MANIFEST, source.NEW_MANIFEST = OLD, plan['source_manifest_sha256']
    source.manifest(CURRENT, OLD)
    source.manifest(STAGED, plan['source_manifest_sha256'])
    require(digest((CURRENT / 'uv.lock').read_bytes()) == digest((STAGED / 'uv.lock').read_bytes()),
            'UNCHANGED_DEPENDENCIES_REQUIRED')
    for target in (PREVIOUS, BACKUP, DECISIONS, ABR_CONFIG, *(UNITS / u for u in ABR_UNITS)):
        require(not any(p.is_symlink() for p in (target, *target.parents)) and not target.exists(),
                'PRIOR_ACTIVATION_REQUIRES_REVIEW')
    require(all(common.command(['systemctl', 'show', u, '--property=LoadState', '--value']) == 'not-found'
                for u in ABR_UNITS), 'EXISTING_ABR_UNIT_REQUIRES_REVIEW')
    for key, staged_file in [('mapping_evidence', 'config/sources/abr-public-mapping.json'),
        ('worker_service', 'ops/aws/abr-engine-abr-worker.service'),
        ('worker_timer', 'ops/aws/abr-engine-abr-worker.timer')]:
        require(digest((STAGED / staged_file).read_bytes()) == plan[key]['sha256'], 'STAGED_INPUT_CHANGED')
    original = common.read_config()
    require(digest(original) == BEFORE_CONFIG, 'CONFIGURATION_BASELINE_CHANGED')
    settings = yaml.safe_load(original)
    require(settings['mode'] == 'pilot' and settings.get('abr_config_file') is None
        and {key for key, enabled in settings['capabilities'].items() if enabled}
            == {'collection', 'retention', 'website_collection', 'crm'}
        and all(type(value) is bool for value in settings['capabilities'].values()), 'EXACT_EXISTING_CAPABILITIES_REQUIRED')
    validate_staged(common, plan, settings, path)
    return original, settings


def stopped(common, *, installed=False):
    names = CORE_UNITS + (ABR_UNITS if installed else [])
    require(all(common.unit_state('is-active', u) == 'inactive' for u in names), 'SERVICES_MUST_REMAIN_STOPPED')
    require(all(common.unit_state('is-active', u) == 'inactive'
        and common.unit_state('is-enabled', u) == 'disabled' for u in CLOSED_TIMERS), 'UNRELATED_TIMERS_MUST_REMAIN_DISABLED')
    if installed:
        require(common.unit_state('is-enabled', ABR_UNITS[1]) == 'disabled', 'ABR_TIMER_MUST_REMAIN_DISABLED')


def stop_all(common):
    # The new units can be absent before installation. Verify that status instead
    # of ignoring a failed systemctl stop for an unrelated operational failure.
    present = [u for u in ABR_UNITS
               if common.command(['systemctl', 'show', u, '--property=LoadState', '--value']) != 'not-found']
    common.command(['systemctl', 'stop', *CORE_UNITS, *present])


def write_new(common, target, data, mode, gid):
    require(not any(p.is_symlink() for p in (target, *target.parents)), 'LINKED_INSTALLATION_PATH_REFUSED')
    with os.fdopen(os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(data)
        os.fchown(stream.fileno(), 0, gid)
        os.fchmod(stream.fileno(), mode)
        stream.flush()
        os.fsync(stream.fileno())
    common.sync_directory(target.parent)
    require(digest(target.read_bytes()) == digest(data), 'NEW_FILE_READBACK_FAILED')


def install_files(common, path, plan, original):
    import grp
    gid = grp.getgrnam('abr-engine').gr_gid
    write_new(common, BACKUP, original, 0o600, 0)
    DECISIONS.mkdir(mode=0o750)
    os.chown(DECISIONS, 0, gid)
    os.chmod(DECISIONS, 0o750)
    common.sync_directory(DECISIONS)
    common.sync_directory(DECISIONS.parent)
    for key in EVIDENCE:
        record = plan[key]
        data = (path.parent / record['file']).read_bytes()
        require(digest(data) == record['sha256'], 'REVIEWED_EVIDENCE_CHANGED')
        write_new(common, DECISIONS / record['file'], data, 0o640, gid)
        if key == 'abr_config':
            write_new(common, ABR_CONFIG, data, 0o640, gid)
        elif key in {'worker_service', 'worker_timer'}:
            name = ABR_UNITS[0 if key == 'worker_service' else 1]
            write_new(common, UNITS / name, data, 0o644, 0)


def prepare_venv(common):
    import grp
    common.command(['/opt/abr-install-tools/bin/uv', '--directory', str(CURRENT), 'sync', '--frozen',
        '--no-install-project', '--no-build', '--python', '/usr/bin/python3.12', '--no-python-downloads'])
    gid = grp.getgrnam('abr-engine').gr_gid
    venv = CURRENT / '.venv'
    require(venv.is_dir() and not venv.is_symlink() and venv.resolve() == venv, 'VENV_BOUNDARY_CHANGED')
    for parent, dirs, files in os.walk(venv, followlinks=False):
        for item in [Path(parent), *(Path(parent) / name for name in dirs + files)]:
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode):
                continue
            require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode), 'VENV_FILE_TYPE_CHANGED')
            os.chown(item, 0, gid)
            os.chmod(item, 0o750 if item.is_dir() or info.st_mode & 0o111 else 0o640)


def install(path, *, execute=False, plan_sha256=None, helpers=None):
    plan = read_plan(path)
    reviewed = digest(path.read_bytes())
    require(not execute or plan_sha256 == reviewed and plan['baseline_state_sha256'] is not None,
            'REVIEWED_PLAN_AND_STATE_DIGEST_REQUIRED')
    common, source = helpers or load_helpers(Path(__file__).resolve().parent)
    original, settings = host_preflight(common, source, plan, path)
    initial = json.loads(common.sql(state_query(common)))
    validate_state(initial)
    require(datetime.fromisoformat(initial['policies'][-1]['approved_at']) < datetime.fromisoformat(plan['approved_at']),
            'APPENDED_POLICY_MUST_BE_NEWER')
    state_sha = digest(canonical(initial).encode())
    require(plan['baseline_state_sha256'] in (None, state_sha), 'DATABASE_BASELINE_CHANGED')
    require(common.sql('SELECT count(*) FROM action_intent;') == '0', 'INDIVIDUAL_ACTIONS_CHANGED')
    require(common.sql("SELECT has_table_privilege('abr-engine','release_gate','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR "
        "has_table_privilege('abr-engine','policy','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR "
        "has_any_column_privilege('abr-engine','release_gate','INSERT,UPDATE') OR "
        "has_any_column_privilege('abr-engine','policy','INSERT,UPDATE');") == 'f', 'RUNTIME_AUTHORITY_WRITES_FORBIDDEN')
    receipt = {'status': 'preview_passed', 'release': '011', 'plan_sha256': reviewed,
        'baseline_state_sha256': state_sha, 'source_manifest_sha256': plan['source_manifest_sha256'],
        'new_gates': 9, 'total_gates': 34, 'total_policies': 3, 'previous_gates_preserved': 25,
        'previous_policies_preserved': 2, 'services_started': False, 'timers_enabled': False,
        'source_runs_requested': 0, 'provider_calls': 0, 'classification_enabled': False,
        'outreach': 'disabled', 'production_backup_accepted': False, 'full_production_release': False}
    if not execute:
        return receipt
    with common.activation_lock():
        encoded = None
        try:
            stop_all(common)
            stopped(common)
            require(read_plan(path) == plan and digest(path.read_bytes()) == reviewed
                and common.read_config() == original
                and json.loads(common.sql(state_query(common))) == initial, 'STOPPED_BASELINE_CHANGED')
            install_files(common, path, plan, original)
            source.activate()
            prepare_venv(common)
            source.manifest(CURRENT, plan['source_manifest_sha256'])
            stopped(common)
            guard = state_query(common).removeprefix('SELECT ').removesuffix(';')
            rows, policy = gate_rows(plan), policy_row(plan, initial)
            common.sql('BEGIN; SELECT pg_advisory_xact_lock(2080912); LOCK TABLE ' + ','.join([*COUNTS, 'pipeline_run', 'action_intent'])
                + ' IN EXCLUSIVE MODE; DO $$ BEGIN IF (' + guard + ')::jsonb<>' + common.literal(json.dumps(initial))
                + "::jsonb OR (SELECT count(*) FROM action_intent)<>0 THEN RAISE EXCEPTION 'baseline changed'; END IF; "
                + 'IF clock_timestamp()<' + common.literal(plan['approved_at']) + '::timestamptz OR clock_timestamp()>='
                + common.literal(END) + "::timestamptz THEN RAISE EXCEPTION 'decision expired'; END IF; END $$; "
                + ''.join(statement(common, 'release_gate', row) for row in rows)
                + statement(common, 'policy', policy) + 'COMMIT;')
            verify_after(initial, json.loads(common.sql(state_query(common))), plan)
            require(common.read_config() == original, 'CONFIGURATION_CHANGED_DURING_ACTIVATION')
            settings['capabilities']['abr'] = True
            settings['abr_config_file'] = str(ABR_CONFIG)
            encoded = yaml.safe_dump(settings, sort_keys=True).encode()
            common.atomic_config(encoded)
            require(common.read_config() == encoded, 'CONFIGURATION_READBACK_FAILED')
            common.command(['systemctl', 'daemon-reload'])
            stop_all(common)
            stopped(common, installed=True)
        except Exception:  # noqa: BLE001 -- retain authority history, keep services stopped, redact failures.
            try:
                stop_all(common)
                current = common.read_config()
                if current != original:
                    require(encoded is not None and current == encoded, 'CONCURRENT_CONFIGURATION_REQUIRES_REVIEW')
                    common.atomic_config(original)
                stopped(common, installed=all((UNITS / u).exists() for u in ABR_UNITS))
            except Exception:  # noqa: BLE001 -- recovery must redact private failures too.
                raise ActivationError('ACTIVATION_RECOVERY_REQUIRES_REVIEW') from None
            raise ActivationError('ACTIVATION_FAILED_CLOSED_HISTORY_PRESERVED') from None
    return {**receipt, 'status': 'abr_observation_011_installed_services_stopped',
            'configuration_sha256': digest(encoded), 'verified_at': datetime.now(UTC).isoformat()}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('plan', type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--plan-sha256')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(install(args.plan, execute=args.execute, plan_sha256=args.plan_sha256)))
    except Exception as error:  # noqa: BLE001 -- no provider, private file or validation body output.
        print(json.dumps({'status': 'activation_failed', 'code': str(error)
            if isinstance(error, ActivationError) else 'ACTIVATION_FAILED'}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
