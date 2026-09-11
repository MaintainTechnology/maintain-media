"""One-time, stopped-service activation of the reviewed website phone pilot.

Preview is read-only. This helper never starts timers/services, contacts a source,
reads environment/key files, or removes authority history, including after failure.
Run alongside activate_qbcc_pilot.py for its reviewed local SQL/file primitives.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import activate_qbcc_pilot as common
import yaml

ActivationError = common.ActivationError
command, sql, literal, sha, ordinary = common.command, common.sql, common.literal, common.sha, common.ordinary
unit_state, sync_directory = common.unit_state, common.sync_directory
read_config, atomic_config, activation_lock = common.read_config, common.atomic_config, common.activation_lock
ROOT, CONFIG, ACTOR = common.ROOT, common.CONFIG, common.ACTOR
BACKUP = Path('/etc/abr-engine/pilot.before-website-phone-20260911.yaml')
DECISIONS = Path('/etc/abr-engine/decisions/website-phone-pilot-20260911')
BEFORE_MANIFEST = '5ec6694f2ba4c555083398b4c5a9a1bffbf3a0b17c4e97667ec2c9759b8c0fbd'
MANIFEST = '51a364b416b8b333c5651631e9db27d1e35e69e68f3ff1aae6ec8c9d501e58fb'
OLD_POLICY = 'qbcc-delegated-pilot-retention-20260911-v1'
POLICY = 'website-phone-delegated-pilot-retention-20260911-v1'
END = '2026-09-24T23:18:20Z'
RETENTION_END = '2027-09-10T23:18:20Z'
REVISIONS = {'website_collection': {'G1': 1, 'G3': 1, 'G7': 1},
             'retention': {'G1': 2, 'G3': 3, 'G7': 3}, 'collection': {'G7': 3}}
OLD_REVISIONS = {('collection', gate, 1) for gate in ('G1', 'G2', 'G3', 'G7')} | {
    ('retention', gate, 1) for gate in ('G1', 'G3', 'G7')} | {
    ('collection', gate, 2) for gate in ('G2', 'G3', 'G7')} | {
    ('retention', gate, 2) for gate in ('G3', 'G7')}
STOPPED_UNITS = [*common.SOURCE_UNITS, 'abr-engine-retention.timer', 'abr-engine-retention.service',
                 'abr-engine-qbcc-review-cleanup.timer', 'abr-engine-qbcc-review-cleanup.service']
EXPECTED_COUNTS = {'release_gate': 12, 'policy': 1, 'schema_migration': 26, 'lead_entity': 1,
                   'contact_record': 0, 'source_snapshot': 1, 'source_cursor': 1}
FIELDS = {'version', 'actor_id', 'adviser_status', 'approved_at', 'collection_expires_at',
          'website_expires_at', 'retention_expires_at', 'source_manifest_before_sha256',
          'source_manifest_sha256', 'production_backup_accepted', 'full_production_release',
          'policy_version', 'owner_evidence', 'technical_evidence', 'gate_revisions'}


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ActivationError('DUPLICATE_PLAN_FIELD')
        result[key] = value
    return result


def read_plan(path):
    ordinary(path)
    if path.stat().st_size > 65536:
        raise ActivationError('PLAN_SIZE_LIMIT')
    plan = json.loads(path.read_text(), object_pairs_hook=unique_fields)
    if not isinstance(plan, dict) or set(plan) != FIELDS:
        raise ActivationError('EXACT_PLAN_FIELDS_REQUIRED')
    if (plan['version'] != 'website-phone-pilot-activation-v1' or plan['actor_id'] != ACTOR
        or plan['adviser_status'] != 'not_obtained' or plan['full_production_release'] is not False
        or plan['production_backup_accepted'] is not False or plan['policy_version'] != POLICY
        or plan['gate_revisions'] != REVISIONS):
        raise ActivationError('EXACT_PHONE_ONLY_DECISION_REQUIRED')
    if (plan['source_manifest_before_sha256'] != BEFORE_MANIFEST or plan['source_manifest_sha256'] != MANIFEST
        or plan['collection_expires_at'] != END or plan['website_expires_at'] != END
        or plan['retention_expires_at'] != RETENTION_END):
        raise ActivationError('PINNED_RELEASE_AND_EXISTING_EXPIRIES_REQUIRED')
    now, start, end = datetime.now(UTC), datetime.fromisoformat(plan['approved_at']), datetime.fromisoformat(END)
    if start.tzinfo is None or not start <= now < end <= start + timedelta(days=14):
        raise ActivationError('CURRENT_FOURTEEN_DAY_DECISION_REQUIRED')
    names = set()
    for key in ('owner_evidence', 'technical_evidence'):
        evidence = plan[key]
        if (not isinstance(evidence, dict) or set(evidence) != {'file', 'sha256'}
            or not isinstance(evidence['file'], str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,159}\.(?:json|md)', evidence['file'])
            or evidence['file'] in names or not isinstance(evidence['sha256'], str)
            or not re.fullmatch(r'[0-9a-f]{64}', evidence['sha256'])):
            raise ActivationError('CLOSED_PUBLIC_EVIDENCE_REQUIRED')
        names.add(evidence['file'])
        file = path.parent / evidence['file']
        ordinary(file)
        if file.stat().st_size > 1024 * 1024 or sha(file) != evidence['sha256']:
            raise ActivationError('PUBLIC_EVIDENCE_DIGEST_MISMATCH')
    owner = json.loads((path.parent / plan['owner_evidence']['file']).read_text(), object_pairs_hook=unique_fields)
    effective = datetime.fromisoformat(owner.get('effective_at', ''))
    if effective.tzinfo is None or start < effective:
        raise ActivationError('PLAN_CANNOT_PREDATE_OWNER_AUTHORITY')
    if (owner.get('decision_id') != 'website-phone-pilot-delegated-owner-20260911'
        or owner.get('status') != 'approved_with_limits_under_delegated_authority'
        or owner.get('adviser_status') != 'not_obtained' or owner.get('legal_compliance_certified') is not False
        or owner.get('expires_at') != END or owner.get('retention', {}).get('retain_selected_evidence') is not False
        or owner.get('source_and_admission', {}).get('allowed_channels') != ['mobile', 'landline']
        or owner.get('source_and_admission', {}).get('email_extraction_allowed') is not False):
        raise ActivationError('FINAL_PHONE_ONLY_OWNER_EVIDENCE_REQUIRED')
    return plan


def stopped():
    if any(unit_state('is-active', unit) != 'inactive' for unit in STOPPED_UNITS):
        raise ActivationError('ALL_COLLECTION_AND_MAINTENANCE_UNITS_MUST_BE_STOPPED')
    if (unit_state('is-active', 'abr-engine-qbcc-weekly.timer') != 'inactive'
        or unit_state('is-enabled', 'abr-engine-qbcc-weekly.timer') != 'disabled'):
        raise ActivationError('WEEKLY_SOURCE_TIMER_MUST_REMAIN_DISABLED')


def host_config():
    ordinary(ROOT / 'RELEASE-MANIFEST.json')
    if os.geteuid() != 0 or sha(ROOT / 'RELEASE-MANIFEST.json') != MANIFEST:
        raise ActivationError('EXPECTED_ROOT_RELEASE008_REQUIRED')
    original = read_config()
    settings = yaml.safe_load(original)
    capabilities = settings.get('capabilities') if isinstance(settings, dict) else None
    if (not isinstance(capabilities, dict) or settings.get('mode') != 'pilot'
        or any(type(value) is not bool for value in capabilities.values())
        or {key for key, value in capabilities.items() if value} != {'collection', 'retention'}):
        raise ActivationError('EXACT_QBCC_AND_RETENTION_ONLY_CONFIGURATION_REQUIRED')
    if BACKUP.exists():
        raise ActivationError('PRIOR_WEBSITE_ACTIVATION_REQUIRES_REVIEW')
    return original, settings


def state_query():
    counts = ','.join(literal(table)+', (SELECT count(*) FROM '+table+')' for table in EXPECTED_COUNTS)
    return "SELECT json_build_object('counts',json_build_object(" + counts + "), 'gates'," \
        "(SELECT json_agg(g ORDER BY scope,gate_name,revision) FROM release_gate g), 'policies'," \
        "(SELECT json_agg(p ORDER BY approved_at,version) FROM policy p), 'running_jobs'," \
        "(SELECT count(*) FROM pipeline_run WHERE state='running'));"


def expected_state(state):
    if (state['counts'] != EXPECTED_COUNTS or state['running_jobs'] != 0
        or {(g['scope'], g['gate_name'], g['revision']) for g in state['gates']} != OLD_REVISIONS
        or any(g['environment'] != 'pilot' for g in state['gates'])
        or len(state['policies']) != 1):
        raise ActivationError('EXPECTED_REVIEWED_SINGLE_BUSINESS_BASELINE_REQUIRED')
    policy = state['policies'][0]
    now = datetime.now(UTC)
    if (policy['version'] != OLD_POLICY or policy['state'] != 'approved' or policy['scope'] != 'pilot'
        or not datetime.fromisoformat(policy['approved_at']) <= now < datetime.fromisoformat(policy['expires_at'])
        or datetime.fromisoformat(policy['expires_at']) != datetime.fromisoformat(RETENTION_END)
        or policy['settings'].get('source_scope') != 'qbcc-internal-review-only'
        or policy['settings'].get('retention', {}).get('restore_enabled') is not False):
        raise ActivationError('EXPECTED_CURRENT_QBCC_RETENTION_POLICY_REQUIRED')


def policy_record(plan):
    return {'version': POLICY, 'state': 'approved', 'scope': 'pilot',
            'evidence_ref': str(DECISIONS / plan['owner_evidence']['file']), 'actor_id': ACTOR,
            'approved_at': plan['approved_at'], 'expires_at': RETENTION_END,
            'settings': json.dumps({'website_collection': {'approved': True, 'allowed_channels': ['mobile', 'landline'],
                'evidence_sha256': plan['owner_evidence']['sha256'], 'expires_at': END},
                'retention': {'approved': True, 'schedule_version': 'abr-v4-defaults',
                    'evidence_sha256': plan['owner_evidence']['sha256'], 'restore_enabled': False,
                    'retain_selected_evidence': False},
                'source_scope': 'qbcc-plus-manual-own-website-phone-review-only',
                'adviser_status': 'not_obtained', 'outreach': 'disabled'})}


def authority_rows(plan):
    rows = []
    for scope, gates in REVISIONS.items():
        for gate, revision in gates.items():
            evidence = plan['owner_evidence' if gate == 'G1' else 'technical_evidence']
            rows.append({'gate_name': gate, 'environment': 'pilot', 'scope': scope, 'revision': revision,
                'evidence_ref': str(DECISIONS / evidence['file']), 'evidence_sha256': evidence['sha256'],
                'actor_id': ACTOR, 'approved_at': plan['approved_at'],
                'expires_at': RETENTION_END if scope == 'retention' else END})
    return rows


def statement(table, row):
    return 'INSERT INTO '+table+'('+','.join(row)+') VALUES('+','.join(map(literal, row.values()))+');'


def normalized_record(row):
    result = dict(row)
    for key in ('approved_at', 'expires_at'):
        result[key] = datetime.fromisoformat(result[key]).astimezone(UTC)
    if 'settings' in result and isinstance(result['settings'], str):
        result['settings'] = json.loads(result['settings'])
    return result


def install_evidence(path, plan):
    import grp
    gid = grp.getgrnam('abr-engine').gr_gid
    for directory in (DECISIONS.parent, DECISIONS):
        if any(item.is_symlink() for item in (directory, *directory.parents)) or '..' in directory.parts:
            raise ActivationError('ORDINARY_DECISIONS_DIRECTORY_REQUIRED')
        if not directory.exists():
            directory.mkdir(mode=0o750)
            os.chown(directory, 0, gid)
            os.chmod(directory, 0o750)
            sync_directory(directory)
            sync_directory(directory.parent)
        info = directory.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_gid != gid
            or stat.S_IMODE(info.st_mode) != 0o750):
            raise ActivationError('PRIVATE_DECISIONS_DIRECTORY_REQUIRED')
    for key in ('owner_evidence', 'technical_evidence'):
        record = plan[key]
        source, target = path.parent / record['file'], DECISIONS / record['file']
        ordinary(source)
        data = source.read_bytes()
        if common.hashlib.sha256(data).hexdigest() != record['sha256']:
            raise ActivationError('PUBLIC_EVIDENCE_DIGEST_MISMATCH')
        if not target.exists():
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
                stream.write(data)
                os.fchown(stream.fileno(), 0, gid)
                os.fchmod(stream.fileno(), 0o640)
                stream.flush()
                os.fsync(stream.fileno())
            sync_directory(DECISIONS)
        ordinary(target)
        info = target.lstat()
        if (info.st_uid != 0 or info.st_gid != gid or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o640 or sha(target) != record['sha256']):
            raise ActivationError('INSTALLED_PUBLIC_EVIDENCE_MISMATCH')


def install(path, *, execute=False, plan_sha256=None):
    plan = read_plan(path)
    reviewed = sha(path)
    if execute and plan_sha256 != reviewed:
        raise ActivationError('REVIEWED_PLAN_DIGEST_REQUIRED')
    original, settings = host_config()
    stopped()
    initial = json.loads(sql(state_query()))
    expected_state(initial)
    if sql("SELECT has_table_privilege('abr-engine','release_gate','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR "
           "has_table_privilege('abr-engine','policy','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR "
           "has_any_column_privilege('abr-engine','release_gate','INSERT,UPDATE') OR "
           "has_any_column_privilege('abr-engine','policy','INSERT,UPDATE');") != 'f':
        raise ActivationError('RUNTIME_AUTHORITY_WRITES_FORBIDDEN')
    receipt = {'status': 'preview_passed', 'plan_sha256': reviewed, 'new_gate_rows': 7,
        'new_policy_version': POLICY, 'website_expires_at': END, 'retention_expires_at': RETENTION_END,
        'enabled_capabilities': ['collection', 'retention', 'website_collection'],
        'allowed_channels': ['mobile', 'landline'], 'services_started': False,
        'timers_enabled': False, 'outreach': 'disabled', 'production_backup_accepted': False}
    if not execute:
        return receipt
    with activation_lock():
        encoded = None
        try:
            stopped()
            if read_plan(path) != plan or sha(path) != reviewed or read_config() != original:
                raise ActivationError('REVIEWED_INPUT_CHANGED')
            with os.fdopen(os.open(BACKUP, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
            sync_directory(BACKUP.parent)
            install_evidence(path, plan)
            stopped()
            guard = state_query().removeprefix('SELECT ').removesuffix(';')
            sql('BEGIN; SELECT pg_advisory_xact_lock(2080912); LOCK TABLE release_gate,policy,lead_entity,'
                'contact_record,source_snapshot,source_cursor,pipeline_run IN EXCLUSIVE MODE; '
                'DO $$ BEGIN IF ('+guard+')::jsonb<>'+literal(json.dumps(initial))+'::jsonb '
                "THEN RAISE EXCEPTION 'activation baseline changed'; END IF; "
                'IF clock_timestamp()<'+literal(plan['approved_at'])+'::timestamptz OR clock_timestamp()>='
                +literal(END)+"::timestamptz THEN RAISE EXCEPTION 'decision expired'; END IF; END $$; "
                +''.join(statement('release_gate', row) for row in authority_rows(plan))
                +statement('policy', policy_record(plan))+'COMMIT;')
            after = json.loads(sql(state_query()))
            expected_gates = {(g['scope'], g['gate_name'], g['revision']) for g in authority_rows(plan)}
            observed_new = {(g['scope'], g['gate_name'], g['revision']): normalized_record(g)
                for g in after['gates'] if (g['scope'], g['gate_name'], g['revision']) in expected_gates}
            expected_new = {(g['scope'], g['gate_name'], g['revision']): normalized_record(g) for g in authority_rows(plan)}
            if (after['counts'] != {**EXPECTED_COUNTS, 'release_gate': 19, 'policy': 2}
                or after['running_jobs'] != 0 or after['policies'][0] != initial['policies'][0]
                or [g for g in after['gates'] if (g['scope'], g['gate_name'], g['revision']) not in expected_gates] != initial['gates']
                or observed_new != expected_new or normalized_record(after['policies'][1]) != normalized_record(policy_record(plan))):
                raise ActivationError('APPENDED_AUTHORITY_READBACK_FAILED')
            stopped()
            if read_config() != original or sha(ROOT / 'RELEASE-MANIFEST.json') != MANIFEST:
                raise ActivationError('REVIEWED_INPUT_CHANGED')
            settings['capabilities'] = {**settings['capabilities'], 'website_collection': True}
            encoded = yaml.safe_dump(settings, sort_keys=True).encode()
            atomic_config(encoded)
            if read_config() != encoded:
                raise ActivationError('CONFIGURATION_READBACK_FAILED')
            stopped()
        except Exception:  # noqa: BLE001 - any failure must close the configuration and preserve history.
            try:
                command(['systemctl', 'stop', *STOPPED_UNITS])
                current = read_config()
                if current != original:
                    if encoded is None or current != encoded:
                        raise ActivationError('CONCURRENT_CONFIGURATION_REQUIRES_REVIEW')
                    atomic_config(original)
                stopped()
            except Exception:  # noqa: BLE001 - never reflect private operator or file errors.
                raise ActivationError('ACTIVATION_RECOVERY_REQUIRES_REVIEW') from None
            raise ActivationError('ACTIVATION_FAILED_CLOSED_HISTORY_PRESERVED') from None
    return {**receipt, 'status': 'website_phone_authority_installed', 'original_configuration_preserved': str(BACKUP)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('plan', type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--plan-sha256')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(install(args.plan, execute=args.execute, plan_sha256=args.plan_sha256)))
    except Exception as error:  # noqa: BLE001 - serialize only safe operator failure codes.
        print(json.dumps({'status': 'activation_failed', 'code': str(error)
            if isinstance(error, ActivationError) else 'ACTIVATION_FAILED'}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
