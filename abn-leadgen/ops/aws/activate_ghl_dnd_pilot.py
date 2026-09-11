"""Append reviewed CRM-only authority with services stopped; preview is default.

No provider calls, credentials, individual lead approvals, policy replacement or
service starts. The reviewed plan binds the new runtime and every installed file.
Run with activate_qbcc_pilot.py and activate_website_phone_pilot.py alongside it.
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
import activate_website_phone_pilot as phone
import yaml

from abr_engine.export.gohighlevel import GHLConfig
from abr_engine.export.live_contract import CHECKS, Installation

ActivationError = common.ActivationError
command, sql, literal, sha, ordinary = common.command, common.sql, common.literal, common.sha, common.ordinary
unit_state, sync_directory = common.unit_state, common.sync_directory
read_config, atomic_config, activation_lock = common.read_config, common.atomic_config, common.activation_lock
ROOT, ACTOR = common.ROOT, common.ACTOR
BACKUP = Path('/etc/abr-engine/pilot.before-ghl-dnd-20260911.yaml')
DECISIONS = Path('/etc/abr-engine/decisions/ghl-dnd-pilot-20260911')
BEFORE_MANIFEST = '51a364b416b8b333c5651631e9db27d1e35e69e68f3ff1aae6ec8c9d501e58fb'
LOCATION = 'xHZFHMOE476t5CxY9vCG'
END, RETENTION_END = phone.END, phone.RETENTION_END
OLD_REVISIONS = phone.OLD_REVISIONS | {(scope, gate, revision)
    for scope, gates in phone.REVISIONS.items() for gate, revision in gates.items()}
STOPPED_UNITS = phone.STOPPED_UNITS
EXPECTED_COUNTS = {'release_gate': 19, 'policy': 2, 'schema_migration': 26, 'lead_entity': 1,
    'contact_record': 2, 'source_snapshot': 1, 'source_cursor': 1, 'worklist_row': 0,
    'crm_outbox': 0, 'crm_identity': 0}
EVIDENCE_KEYS = ('owner_evidence', 'technical_evidence', 'ghl_config', 'ghl_installation')
FIELDS = {'version', 'actor_id', 'adviser_status', 'approved_at', 'crm_expires_at',
    'removal_expires_at', 'source_manifest_before_sha256', 'source_manifest_sha256',
    'production_backup_accepted', 'full_production_release', 'check_evidence', *EVIDENCE_KEYS}
unique_fields, statement, normalized_record = phone.unique_fields, phone.statement, phone.normalized_record


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_fields)


def evidence_records(plan):
    return [*(plan[key] for key in EVIDENCE_KEYS), *plan['check_evidence'].values()]


def read_plan(path):
    ordinary(path)
    if path.suffix != '.json' or path.name.startswith('.env'):
        raise ActivationError('PUBLIC_JSON_PLAN_REQUIRED')
    if path.stat().st_size > 65536:
        raise ActivationError('PLAN_SIZE_LIMIT')
    plan = read_json(path)
    if not isinstance(plan, dict) or set(plan) != FIELDS:
        raise ActivationError('EXACT_PLAN_FIELDS_REQUIRED')
    if (plan['version'] != 'ghl-dnd-pilot-activation-v1' or plan['actor_id'] != ACTOR
        or plan['adviser_status'] != 'not_obtained' or plan['production_backup_accepted'] is not False
        or plan['full_production_release'] is not False or plan['crm_expires_at'] != END
        or plan['removal_expires_at'] != RETENTION_END
        or plan['source_manifest_before_sha256'] != BEFORE_MANIFEST
        or not isinstance(plan['source_manifest_sha256'], str)
        or not re.fullmatch(r'[0-9a-f]{64}', plan['source_manifest_sha256'])
        or plan['source_manifest_sha256'] == BEFORE_MANIFEST
        or not isinstance(plan['check_evidence'], dict) or set(plan['check_evidence']) != CHECKS):
        raise ActivationError('EXACT_GHL_PILOT_PLAN_REQUIRED')
    start = datetime.fromisoformat(plan['approved_at'])
    if start.tzinfo is None or not start <= datetime.now(UTC) < datetime.fromisoformat(END) <= start + timedelta(days=14):
        raise ActivationError('CURRENT_FOURTEEN_DAY_DECISION_REQUIRED')
    names = {}
    for record in evidence_records(plan):
        if (not isinstance(record, dict) or set(record) != {'file', 'sha256'}
            or not isinstance(record['file'], str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,159}\.(?:json|md|yaml|yml|xml)', record['file'])
            or record['file'].startswith('.env') or not isinstance(record['sha256'], str)
            or not re.fullmatch(r'[0-9a-f]{64}', record['sha256'])):
            raise ActivationError('CLOSED_PUBLIC_EVIDENCE_REQUIRED')
        previous = names.setdefault(record['file'], record['sha256'])
        if previous != record['sha256']:
            raise ActivationError('CONFLICTING_EVIDENCE_FILE')
        file = path.parent / record['file']
        ordinary(file)
        if file.stat().st_size > 1024 * 1024 or sha(file) != record['sha256']:
            raise ActivationError('PUBLIC_EVIDENCE_DIGEST_MISMATCH')
    if len({plan[key]['file'] for key in EVIDENCE_KEYS}) != len(EVIDENCE_KEYS):
        raise ActivationError('DISTINCT_AUTHORITY_AND_CONFIGURATION_REQUIRED')
    owner = read_json(path.parent / plan['owner_evidence']['file'])
    effective = datetime.fromisoformat(owner.get('effective_at', ''))
    retention, admission = owner.get('retention', {}), owner.get('per_record_admission', {})
    if (effective.tzinfo is None or start < effective
        or owner.get('decision_id') != 'ghl-dnd-pilot-delegated-owner-20260911'
        or owner.get('status') != 'approved_with_limits_under_delegated_authority'
        or owner.get('approved_for_release') is not True
        or owner.get('adviser_status') != 'not_obtained' or owner.get('legal_compliance_certified') is not False
        or owner.get('expires_at') != END or owner.get('recipient', {}).get('location_id') != LOCATION
        or owner.get('disclosure_projection', {}).get('allowed_channel') != 'phone'
        or owner.get('operational_limits', {}).get('dnd_always_true') is not True
        or admission.get('selected_worklist_required') is not True or admission.get('tier') != 'A'
        or admission.get('individual_reviewer_approval_bound_to_current_row_version') is not True
        or admission.get('genuine_dncr_clear_strictly_less_than_30_days_required') is not True
        or retention.get('finite_deletion_authority_expires_at') != RETENTION_END
        or retention.get('retain_selected_evidence') is not False
        or owner.get('notice_strategy', {}).get('publication_status') != 'verified_public_readback'
        or not owner.get('notice_strategy', {}).get('live_readback_evidence')):
        raise ActivationError('FINAL_PHONE_DND_OWNER_EVIDENCE_REQUIRED')
    config_path, installation_path = (path.parent / plan[key]['file'] for key in ('ghl_config', 'ghl_installation'))
    if config_path.suffix not in {'.yaml', '.yml'} or installation_path.suffix not in {'.yaml', '.yml'}:
        raise ActivationError('NONSECRET_YAML_CONFIG_AND_INSTALLATION_REQUIRED')
    config = GHLConfig.model_validate(yaml.safe_load(config_path.read_bytes()))
    receipt = Installation.model_validate(yaml.safe_load(installation_path.read_bytes()))
    if (config.location_id != LOCATION or not config.allow_writes or config.allowed_channels != ['phone']
        or not config.workflow_inventory_sha256 or config.token_env != 'ABR_GHL_TOKEN'
        or receipt.location_id != LOCATION or receipt.environment != 'pilot'
        or receipt.config_sha256 != plan['ghl_config']['sha256'] or receipt.approved_by != ACTOR
        or not start - timedelta(hours=24) <= receipt.verified_at <= start
        or receipt.expires_at != datetime.fromisoformat(RETENTION_END)):
        raise ActivationError('EXACT_PHONE_DND_INSTALLATION_REQUIRED')
    for name, check in receipt.checks.items():
        evidence = plan['check_evidence'][name]
        if check.evidence_ref != str(DECISIONS / evidence['file']) or check.evidence_sha256 != evidence['sha256']:
            raise ActivationError('INSTALLATION_CHECK_EVIDENCE_MISMATCH')
    return plan


def stopped():
    if any(unit_state('is-active', unit) != 'inactive' for unit in STOPPED_UNITS):
        raise ActivationError('ALL_COLLECTION_AND_MAINTENANCE_UNITS_MUST_BE_STOPPED')
    if (unit_state('is-active', 'abr-engine-qbcc-weekly.timer') != 'inactive'
        or unit_state('is-enabled', 'abr-engine-qbcc-weekly.timer') != 'disabled'):
        raise ActivationError('WEEKLY_SOURCE_TIMER_MUST_REMAIN_DISABLED')
    for unit in ('abr-engine-backup-daily.timer', 'abr-engine-backup-ledger.timer', 'abr-engine-backup-expiry.timer'):
        if unit_state('is-active', unit) != 'inactive' or unit_state('is-enabled', unit) != 'disabled':
            raise ActivationError('BACKUP_TIMERS_MUST_REMAIN_DISABLED')


def host_config(plan):
    ordinary(ROOT / 'RELEASE-MANIFEST.json')
    if os.geteuid() != 0 or sha(ROOT / 'RELEASE-MANIFEST.json') != plan['source_manifest_sha256']:
        raise ActivationError('EXPECTED_REVIEWED_ROOT_RELEASE_REQUIRED')
    original = read_config()
    settings = yaml.safe_load(original)
    caps = settings.get('capabilities') if isinstance(settings, dict) else None
    if (not isinstance(caps, dict) or settings.get('mode') != 'pilot'
        or any(type(value) is not bool for value in caps.values())
        or {key for key, value in caps.items() if value} != {'collection', 'retention', 'website_collection'}
        or settings.get('ghl_config_file') is not None or settings.get('ghl_installation_file') is not None):
        raise ActivationError('EXACT_EXISTING_PHONE_ONLY_CONFIGURATION_REQUIRED')
    if BACKUP.exists():
        raise ActivationError('PRIOR_GHL_ACTIVATION_REQUIRES_REVIEW')
    return original, settings


def state_query():
    counts = ','.join(literal(table)+', (SELECT count(*) FROM '+table+')' for table in EXPECTED_COUNTS)
    return "SELECT json_build_object('counts',json_build_object("+counts+"),'gates'," \
        "(SELECT json_agg(g ORDER BY scope,gate_name,revision) FROM release_gate g),'policies'," \
        "(SELECT json_agg(p ORDER BY approved_at,version) FROM policy p),'running_jobs'," \
        "(SELECT count(*) FROM pipeline_run WHERE state='running'),'nonphone_contacts'," \
        "(SELECT count(*) FROM contact_record WHERE channel NOT IN ('mobile','landline')));"


def expected_state(state):
    if (state['counts'] != EXPECTED_COUNTS or state['running_jobs'] != 0 or state['nonphone_contacts'] != 0
        or {(g['scope'], g['gate_name'], g['revision']) for g in state['gates']} != OLD_REVISIONS
        or any(g['environment'] != 'pilot' for g in state['gates']) or len(state['policies']) != 2):
        raise ActivationError('EXACT_UNEXPORTED_PHONE_PILOT_BASELINE_REQUIRED')
    old, latest = state['policies']
    settings = latest['settings']
    if (old['version'] != phone.OLD_POLICY or latest['version'] != phone.POLICY
        or latest['state'] != 'approved' or latest['scope'] != 'pilot'
        or not datetime.fromisoformat(latest['approved_at']) <= datetime.now(UTC) < datetime.fromisoformat(latest['expires_at'])
        or datetime.fromisoformat(latest['expires_at']) != datetime.fromisoformat(RETENTION_END)
        or settings.get('source_scope') != 'qbcc-plus-manual-own-website-phone-review-only'
        or settings.get('outreach') != 'disabled' or settings.get('adviser_status') != 'not_obtained'
        or settings.get('retention', {}).get('approved') is not True
        or settings.get('retention', {}).get('restore_enabled') is not False
        or settings.get('retention', {}).get('retain_selected_evidence') is not False
        or settings.get('website_collection', {}).get('approved') is not True
        or settings.get('website_collection', {}).get('allowed_channels') != ['mobile', 'landline']
        or settings.get('website_collection', {}).get('expires_at') != END):
        raise ActivationError('EXISTING_PHONE_PURPOSE_AND_FINITE_RETENTION_REQUIRED')


def authority_rows(plan):
    rows = []
    for gate in ('G1', 'G3', 'G5', 'G7'):
        evidence = plan['owner_evidence' if gate == 'G1' else 'ghl_installation' if gate == 'G5' else 'technical_evidence']
        rows.append({'gate_name': gate, 'environment': 'pilot', 'scope': 'crm', 'revision': 1,
            'evidence_ref': str(DECISIONS / evidence['file']), 'evidence_sha256': evidence['sha256'],
            'actor_id': ACTOR, 'approved_at': plan['approved_at'],
            'expires_at': RETENTION_END if gate in {'G3', 'G5'} else END})
    return rows


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
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_gid != gid or stat.S_IMODE(info.st_mode) != 0o750:
            raise ActivationError('PRIVATE_DECISIONS_DIRECTORY_REQUIRED')
    for record in evidence_records(plan):
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
    plan, reviewed = read_plan(path), sha(path)
    if execute and plan_sha256 != reviewed:
        raise ActivationError('REVIEWED_PLAN_DIGEST_REQUIRED')
    original, settings = host_config(plan)
    stopped()
    initial = json.loads(sql(state_query()))
    expected_state(initial)
    if sql("SELECT has_table_privilege('abr-engine','release_gate','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR "
           "has_table_privilege('abr-engine','policy','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR "
           "has_any_column_privilege('abr-engine','release_gate','INSERT,UPDATE') OR "
           "has_any_column_privilege('abr-engine','policy','INSERT,UPDATE');") != 'f':
        raise ActivationError('RUNTIME_AUTHORITY_WRITES_FORBIDDEN')
    receipt = {'status': 'preview_passed', 'plan_sha256': reviewed, 'new_gate_rows': 4,
        'policy_changed': False, 'crm_expires_at': END, 'removal_expires_at': RETENTION_END,
        'allowed_channels': ['phone'], 'services_started': False, 'timers_enabled': False,
        'individual_approvals_created': 0, 'provider_calls': 0, 'outreach': 'disabled'}
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
            tables = ','.join([*EXPECTED_COUNTS, 'pipeline_run'])
            sql('BEGIN; SELECT pg_advisory_xact_lock(2080912); LOCK TABLE '+tables+' IN EXCLUSIVE MODE; '
                'DO $$ BEGIN IF ('+guard+')::jsonb<>'+literal(json.dumps(initial))+'::jsonb '
                "THEN RAISE EXCEPTION 'activation baseline changed'; END IF; "
                'IF clock_timestamp()<'+literal(plan['approved_at'])+'::timestamptz OR clock_timestamp()>='
                +literal(END)+"::timestamptz THEN RAISE EXCEPTION 'decision expired'; END IF; END $$; "
                +''.join(statement('release_gate', row) for row in authority_rows(plan))+'COMMIT;')
            after = json.loads(sql(state_query()))
            observed = [normalized_record(g) for g in after['gates'] if g['scope'] == 'crm']
            if (after['counts'] != {**EXPECTED_COUNTS, 'release_gate': 23} or after['running_jobs'] != 0
                or after['nonphone_contacts'] != 0 or after['policies'] != initial['policies']
                or [g for g in after['gates'] if g['scope'] != 'crm'] != initial['gates']
                or observed != [normalized_record(g) for g in authority_rows(plan)]):
                raise ActivationError('APPENDED_AUTHORITY_READBACK_FAILED')
            stopped()
            if read_config() != original or sha(ROOT / 'RELEASE-MANIFEST.json') != plan['source_manifest_sha256']:
                raise ActivationError('REVIEWED_INPUT_CHANGED')
            settings['capabilities'] = {**settings['capabilities'], 'crm': True}
            settings['ghl_config_file'] = str(DECISIONS / plan['ghl_config']['file'])
            settings['ghl_installation_file'] = str(DECISIONS / plan['ghl_installation']['file'])
            encoded = yaml.safe_dump(settings, sort_keys=True).encode()
            atomic_config(encoded)
            if read_config() != encoded:
                raise ActivationError('CONFIGURATION_READBACK_FAILED')
            stopped()
        except Exception:  # noqa: BLE001 - preserve authority history and stop services on any failure.
            try:
                command(['systemctl', 'stop', *STOPPED_UNITS])
                current = read_config()
                if current != original:
                    if encoded is None or current != encoded:
                        raise ActivationError('CONCURRENT_CONFIGURATION_REQUIRES_REVIEW')
                    atomic_config(original)
                stopped()
            except Exception:  # noqa: BLE001 - never reflect private operator/file errors.
                raise ActivationError('ACTIVATION_RECOVERY_REQUIRES_REVIEW') from None
            raise ActivationError('ACTIVATION_FAILED_CLOSED_HISTORY_PRESERVED') from None
    return {**receipt, 'status': 'ghl_phone_dnd_authority_installed', 'original_configuration_preserved': str(BACKUP)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('plan', type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--plan-sha256')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(install(args.plan, execute=args.execute, plan_sha256=args.plan_sha256)))
    except Exception as error:  # noqa: BLE001 - serialize fixed codes only, never credential or provider bodies.
        print(json.dumps({'status': 'activation_failed', 'code': str(error)
            if isinstance(error, ActivationError) else 'ACTIVATION_FAILED'}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
