"""Install the reviewed, time-limited QBCC pilot decision; no credentials or sends.

One-time operator helper. It pins public evidence and installed source, refuses
existing authority/data, retains the original private configuration, and keeps
all unrelated capabilities and the weekly source timer off. Preview is default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path('/opt/abn-leadgen')
CONFIG = Path('/etc/abr-engine/pilot.yaml')
BACKUP = Path('/etc/abr-engine/pilot.before-qbcc-20260911.yaml')
MANIFEST_SHA = 'aeb806afdaad134494cfa3147ea72f58d5c99116db3c616c177bb154872cd5ea'
ACTOR = 'delegated-owner:jeph@quotemax.com.au'
SCOPES = {'collection': {'G1', 'G2', 'G3', 'G7'}, 'retention': {'G1', 'G3', 'G7'}}
POLICY_VERSION = 'qbcc-delegated-pilot-retention-20260911-v1'
ENVIRONMENT = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}
SOURCE_UNITS = ['abr-engine-worker.timer', 'abr-engine-control.timer',
                'abr-engine-worker.service', 'abr-engine-control.service', 'abr-engine-api.service']
EMPTY_DATA = ('NOT EXISTS(SELECT FROM lead_entity) AND NOT EXISTS(SELECT FROM contact_record) '
              'AND NOT EXISTS(SELECT FROM source_snapshot) AND NOT EXISTS(SELECT FROM source_cursor)')
TABLE_LOCK = ('LOCK TABLE release_gate,policy,lead_entity,contact_record,source_snapshot,source_cursor '
              'IN EXCLUSIVE MODE; ')


class ActivationError(ValueError):
    """Only fixed, non-sensitive messages may be returned by the command boundary."""


def command(args, *, data=None):
    result = subprocess.run(args, input=data, text=True, capture_output=True, check=False,
                            timeout=120, env=ENVIRONMENT)
    if result.returncode:
        raise ActivationError('OPERATOR_COMMAND_FAILED')
    return result.stdout.strip()


def sql(query):
    return command(['sudo', '-u', 'postgres', 'psql', '-X', '-v', 'ON_ERROR_STOP=1',
                    '-h', '/var/run/postgresql', '-p', '5432', '-U', 'postgres',
                    '-d', 'abr_leadgen', '-Atq'],
                   data="SET standard_conforming_strings=on; SET search_path=public,pg_catalog; "
                        "SET lock_timeout='10s'; SET statement_timeout='60s'; " + query)


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordinary(path):
    if (not path.is_absolute() or '..' in path.parts
        or any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()):
        raise ActivationError('ORDINARY_ABSOLUTE_PATH_REQUIRED')


def read_plan(path):
    ordinary(path)
    if path.stat().st_size > 65536:
        raise ActivationError('PLAN_SIZE_LIMIT')
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ActivationError('DUPLICATE_PLAN_FIELD')
            result[key] = value
        return result
    plan = json.loads(path.read_text(), object_pairs_hook=unique_fields)
    now = datetime.now(UTC)
    start, end, deletion_end = (datetime.fromisoformat(plan[k]) for k in
                              ('approved_at', 'collection_expires_at', 'retention_expires_at'))
    if any(x.tzinfo is None for x in (start, end, deletion_end)):
        raise ActivationError('AWARE_DECISION_TIMES_REQUIRED')
    if not start <= now < end <= start + timedelta(days=14):
        raise ActivationError('CURRENT_FOURTEEN_DAY_DECISION_REQUIRED')
    if not end + timedelta(days=181) <= deletion_end <= start + timedelta(days=366):
        raise ActivationError('SEPARATE_FINITE_DELETION_AUTHORITY_REQUIRED')
    if plan['actor_id'] != ACTOR or plan['adviser_status'] != 'not_obtained':
        raise ActivationError('HONEST_DELEGATED_OWNER_RECORD_REQUIRED')
    if plan['production_backup_accepted'] is not False or plan['full_production_release'] is not False:
        raise ActivationError('PILOT_LIMITATIONS_REQUIRED')
    if set(plan['gates']) != set(SCOPES):
        raise ActivationError('EXACT_PILOT_SCOPES_REQUIRED')
    for scope, gates in SCOPES.items():
        if set(plan['gates'][scope]) != gates:
            raise ActivationError('EXACT_GATE_SET_REQUIRED')
        for evidence in plan['gates'][scope].values():
            if (set(evidence) != {'file', 'sha256'} or not isinstance(evidence['file'], str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,159}\.(?:json|md|xml)', evidence['file'])
                or not isinstance(evidence['sha256'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', evidence['sha256'])):
                raise ActivationError('CLOSED_PUBLIC_EVIDENCE_REQUIRED')
            file = path.parent / evidence['file']
            ordinary(file)
            if file.parent != path.parent or sha(file) != evidence['sha256']:
                raise ActivationError('PUBLIC_EVIDENCE_DIGEST_MISMATCH')
    return plan


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_config():
    import grp
    ordinary(CONFIG)
    info = CONFIG.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != 0
        or info.st_gid != grp.getgrnam('abr-engine').gr_gid or stat.S_IMODE(info.st_mode) != 0o640):
        raise ActivationError('PRIVATE_CONFIGURATION_METADATA_REQUIRED')
    return CONFIG.read_bytes()  # Explicit private YAML only, never environment or key files.


def unit_state(action, name):
    result = subprocess.run(['systemctl', action, name], text=True, capture_output=True,
                            timeout=30, check=False, env=ENVIRONMENT)
    return result.stdout.strip() if result.returncode in (0, 1, 3) else 'unverified'


@contextmanager
def activation_lock():
    import fcntl
    path = CONFIG.with_name('qbcc-activation-20260911.lock')
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
            raise ActivationError('PRIVATE_ACTIVATION_LOCK_REQUIRED')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ActivationError('ACTIVATION_BUSY') from None
        yield
    finally:
        os.close(fd)


def atomic_config(data):
    temp = CONFIG.with_name('pilot.qbcc-20260911.tmp')
    created = None
    try:
        with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            created = os.fstat(stream.fileno())
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        info = CONFIG.stat()
        os.chown(temp, info.st_uid, info.st_gid)
        os.chmod(temp, stat.S_IMODE(info.st_mode))
        fd = os.open(temp, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temp, CONFIG)
        sync_directory(CONFIG.parent)
    finally:
        if created and temp.exists():
            current = temp.lstat()
            if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                temp.unlink()


def policy_record(path, plan):
    retention = plan['gates']['retention']['G1']
    settings = {'retention': {'approved': True, 'schedule_version': 'abr-v4-defaults',
                             'evidence_sha256': retention['sha256'], 'restore_enabled': False},
                'source_scope': 'qbcc-internal-review-only', 'adviser_status': 'not_obtained',
                'outreach': 'disabled'}
    return {'version': POLICY_VERSION, 'state': 'approved', 'scope': 'pilot',
            'evidence_ref': str(path.parent / retention['file']), 'actor_id': ACTOR,
            'approved_at': plan['approved_at'], 'expires_at': plan['retention_expires_at'],
            'settings': json.dumps(settings)}


def install(path, *, execute=False, plan_sha256=None):
    plan = read_plan(path)
    reviewed_sha = sha(path)
    if execute and plan_sha256 != reviewed_sha:
        raise ActivationError('REVIEWED_PLAN_DIGEST_REQUIRED')
    ordinary(CONFIG)
    ordinary(ROOT / 'RELEASE-MANIFEST.json')
    if os.geteuid() != 0 or sha(ROOT / 'RELEASE-MANIFEST.json') != MANIFEST_SHA:
        raise ActivationError('EXPECTED_ROOT_HOST_RELEASE_REQUIRED')
    original = read_config()
    settings = yaml.safe_load(original)
    if settings['mode'] != 'pilot' or any(settings['capabilities'].values()):
        raise ActivationError('DORMANT_PILOT_REQUIRED')
    if BACKUP.exists():
        raise ActivationError('PRIOR_ACTIVATION_MUST_BE_REVIEWED')
    counts = sql('SELECT (SELECT count(*) FROM release_gate), (SELECT count(*) FROM policy), '
                 '(SELECT count(*) FROM lead_entity), (SELECT count(*) FROM schema_migration), '
                 '(SELECT count(*) FROM contact_record), (SELECT count(*) FROM source_snapshot), '
                 '(SELECT count(*) FROM source_cursor);')
    if counts != '0|0|0|26|0|0|0':
        raise ActivationError('EXPECTED_EMPTY_AUTHORITY_AND_REVIEW_STORE_REQUIRED')
    if sql("SELECT has_table_privilege('abr-engine','release_gate','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR "
           "has_table_privilege('abr-engine','policy','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR "
           "has_any_column_privilege('abr-engine','release_gate','INSERT,UPDATE') OR "
           "has_any_column_privilege('abr-engine','policy','INSERT,UPDATE');") != 'f':
        raise ActivationError('RUNTIME_AUTHORITY_WRITES_FORBIDDEN')
    for unit in ('abr-engine-qbcc-weekly.timer', 'abr-engine-retention.timer'):
        if unit_state('is-active', unit) != 'inactive' or unit_state('is-enabled', unit) != 'disabled':
            raise ActivationError('DORMANT_SOURCE_AND_RETENTION_TIMERS_REQUIRED')
    for unit in ('abr-engine-api.service', 'abr-engine-worker.timer', 'abr-engine-control.timer'):
        if unit_state('is-active', unit) != 'active':
            raise ActivationError('EXISTING_CONTROL_SERVICE_REQUIRED')
    rows = []
    for scope, gates in plan['gates'].items():
        expiry = plan['collection_expires_at' if scope == 'collection' else 'retention_expires_at']
        for gate, evidence in sorted(gates.items()):
            values = [gate, 'pilot', scope, 1, str(path.parent / evidence['file']),
                      evidence['sha256'], ACTOR, plan['approved_at'], expiry]
            rows.append('INSERT INTO release_gate VALUES(' + ','.join(map(literal, values)) + ');')
    record = policy_record(path, plan)
    rows.append('INSERT INTO policy(' + ','.join(record) + ') VALUES(' + ','.join(map(literal, record.values())) + ');')
    result = {'status': 'preview_passed', 'plan_sha256': reviewed_sha, 'gate_rows': 7, 'collection_expires_at': plan['collection_expires_at'],
              'retention_expires_at': plan['retention_expires_at'], 'weekly_source_timer_enabled': False,
              'enabled_capabilities': ['collection', 'retention'], 'production_backup_accepted': False}
    if not execute:
        return result
    with activation_lock():
        return execute_activation(path, plan, reviewed_sha, original, settings, rows, result)


def rollback_authority(path, plan):
    owned = []
    for scope, gates in plan['gates'].items():
        expiry = plan['collection_expires_at' if scope == 'collection' else 'retention_expires_at']
        for gate, evidence in gates.items():
            fields = {'gate_name': gate, 'environment': 'pilot', 'scope': scope, 'revision': 1,
                      'evidence_ref': str(path.parent / evidence['file']), 'evidence_sha256': evidence['sha256'],
                      'actor_id': ACTOR, 'approved_at': plan['approved_at'], 'expires_at': expiry}
            owned.append('(' + ' AND '.join(k+'='+literal(v) for k, v in fields.items()) + ')')
    predicate = ' OR '.join(owned)
    policy = policy_record(path, plan)
    policy_predicate = ' AND '.join(k+'='+literal(v)+('::jsonb' if k == 'settings' else '') for k, v in policy.items())
    sql('BEGIN; ' + TABLE_LOCK + "DO $$ BEGIN IF NOT (" + EMPTY_DATA + ") OR "
        "EXISTS(SELECT FROM release_gate WHERE NOT (" + predicate + ")) OR "
        "EXISTS(SELECT FROM policy WHERE NOT (" + policy_predicate + ")) "
        "THEN RAISE EXCEPTION 'rollback requires review'; "
        "END IF; END $$; DELETE FROM release_gate WHERE " + predicate + '; '
        'DELETE FROM policy WHERE ' + policy_predicate + '; COMMIT;')


def execute_activation(path, plan, reviewed_sha, original, settings, rows, result):
    sql_attempted = False
    try:
        command(['systemctl', 'stop', *SOURCE_UNITS])
        if read_plan(path) != plan or sha(path) != reviewed_sha or read_config() != original:
            raise ActivationError('REVIEWED_INPUT_CHANGED')
        if BACKUP.exists():
            raise ActivationError('PRIOR_ACTIVATION_MUST_BE_REVIEWED')
        with os.fdopen(os.open(BACKUP, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        sync_directory(BACKUP.parent)
        sql_attempted = True
        sql("BEGIN; SELECT pg_advisory_xact_lock(2080911); " + TABLE_LOCK +
            "DO $$ BEGIN IF EXISTS(SELECT FROM release_gate) OR EXISTS(SELECT FROM policy) OR NOT (" + EMPTY_DATA + ") "
            "THEN RAISE EXCEPTION 'authority changed'; END IF; "
            "IF clock_timestamp()<" + literal(plan['approved_at']) + "::timestamptz OR clock_timestamp()>=" +
            literal(plan['collection_expires_at']) + "::timestamptz THEN RAISE EXCEPTION 'decision expired'; "
            "END IF; END $$; " + '\n'.join(rows) + 'COMMIT;')
        settings['capabilities'] = {**settings['capabilities'], 'collection': True, 'retention': True}
        atomic_config(yaml.safe_dump(settings, sort_keys=True).encode())
        command(['systemctl', 'enable', '--now', 'abr-engine-retention.timer'])
        command(['systemctl', 'start', 'abr-engine-api.service'])
        command(['systemctl', 'is-active', '--quiet', 'abr-engine-api.service'])
        command(['systemctl', 'start', 'abr-engine-worker.timer', 'abr-engine-control.timer'])
    except Exception:
        try:
            command(['systemctl', 'stop', *SOURCE_UNITS, 'abr-engine-retention.timer', 'abr-engine-retention.service'])
            command(['systemctl', 'disable', 'abr-engine-retention.timer'])
            atomic_config(original)
            if sql_attempted:
                rollback_authority(path, plan)
            command(['systemctl', 'start', 'abr-engine-api.service'])
            command(['systemctl', 'start', 'abr-engine-worker.timer', 'abr-engine-control.timer'])
        except Exception:  # noqa: BLE001 - stop services and require review if rollback cannot be proved.
            raise ActivationError('ACTIVATION_ROLLBACK_REQUIRES_REVIEW') from None
        raise
    return {**result, 'status': 'pilot_authority_installed', 'original_private_config_preserved': str(BACKUP)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('plan', type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--plan-sha256')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(install(args.plan, execute=args.execute, plan_sha256=args.plan_sha256)))
    except Exception as error:  # noqa: BLE001 - never reflect a private file/provider error in stdout.
        print(json.dumps({'status': 'activation_failed', 'code': str(error)
                          if isinstance(error, ActivationError) else 'ACTIVATION_FAILED'}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
