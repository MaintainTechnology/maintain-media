"""One-time reviewed 009b to 010 maintenance repair; preview by default.

Keep services stopped on failure. No configuration, policy or CRM changes.
"""
import hashlib
import json
import os
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path('/home/ubuntu/abn-ghl-activation-20260911')
INPUT = Path('/home/ubuntu/abn-cleanup-activation-20260911')
DECISIONS = Path('/etc/abr-engine/decisions/qbcc-cleanup-release-010-20260911')
NAME = 'qbcc-cleanup-release-010-decision-20260911.json'
EVIDENCE_SHA = '6612d43c21a20821c29ad234bf26fad0776df8a01ae7b51cadbaba8da94f1706'
OLD = '7b1b866ec895c3fbe84409113602859200f0fd83cc18576d14bc35db8dc8f8c9'
NEW = '608bcbcb881f2787db2f6f408e666c5e3debe0d4a59760085e62d3c4aa1c5660'
HELPERS = {
    'activate_qbcc_pilot.py': '21db170a7df3bf03bc9179f9b49d3adc90b430bc78f523618e66a4dc21f90b2f',
    'activate_website_phone_pilot.py': '9788d929c7254f09ec0171050a92248e55065da3ede04cc8a7fc29d0a28bd4bc',
    'activate_ghl_dnd_pilot.py': 'bb64fa3f1d28556dc1b90539e8e1d9744bca95d6e29d872189b8d299666c4e84',
    'activate_live_source.py': 'e52d280dca56e55b01972243b6b0aad79a69128dcb6e1c46cec13d41e2a935d2',
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def run(execute=False):
    import grp

    require(os.geteuid() == 0, 'ROOT_REQUIRED')
    for name, digest in HELPERS.items():
        p = BASE / name
        require(not any(x.is_symlink() for x in (p, *p.parents))
                and hashlib.sha256(p.read_bytes()).hexdigest() == digest, 'HELPER_CHANGED')
    sys.path[:0] = [str(BASE), '/opt/abn-leadgen/src']
    import activate_ghl_dnd_pilot as ghl
    import activate_live_source as source
    import activate_qbcc_pilot as common

    evidence = INPUT / NAME
    common.ordinary(evidence)
    require(common.sha(evidence) == EVIDENCE_SHA, 'TECHNICAL_EVIDENCE_CHANGED')
    decision = json.loads(evidence.read_bytes())
    require(decision['validation']['independent_review'] == 'passed_no_blocking_findings'
            and decision['source_manifest_sha256'] == NEW, 'REVIEW_REQUIRED')
    source.STAGED = Path('/opt/abn-leadgen-live-20260911-010-stage')
    source.PREVIOUS = Path('/opt/abn-leadgen-live-20260911-009b-previous')
    source.OLD_MANIFEST, source.NEW_MANIFEST = OLD, NEW
    source.manifest(source.CURRENT, OLD)
    source.manifest(source.STAGED, NEW)
    require(not source.PREVIOUS.exists(), 'PRIOR_CUTOVER_REQUIRES_REVIEW')
    original = common.read_config()
    settings = ghl.yaml.safe_load(original)
    require(settings['mode'] == 'pilot' and {k for k, v in settings['capabilities'].items() if v}
            == {'collection', 'retention', 'website_collection', 'crm'}, 'PILOT_CAPABILITIES_CHANGED')
    for key, digest in (
        ('ghl_config_file', 'd9353beca5e3490fa7aa6f249e6ce1c784193337de04cd0a4515b199a3339477'),
        ('ghl_installation_file', '3ba2247eb3ffa495e0a890ebcf02e05e1e5f9bcc5be3d5de7e0e525fab82eeec'),
    ):
        common.ordinary(Path(settings[key]))
        require(common.sha(Path(settings[key])) == digest, 'GHL_INSTALLATION_CHANGED')
    query = ghl.state_query()
    counts = {**ghl.EXPECTED_COUNTS, 'release_gate': 23}
    revisions = ghl.OLD_REVISIONS | {('crm', gate, 1) for gate in ('G1', 'G3', 'G5', 'G7')}

    def read_state():
        state = json.loads(common.sql(query))
        require(state['counts'] == counts and len(state['policies']) == 2
                and state['running_jobs'] == 0 and state['nonphone_contacts'] == 0
                and {(g['scope'], g['gate_name'], g['revision']) for g in state['gates']} == revisions
                and all(g['environment'] == 'pilot' for g in state['gates']), 'BASELINE_CHANGED')
        require(common.sql('SELECT count(*) FROM action_intent;') == '0', 'INDIVIDUAL_ACTIONS_CHANGED')
        return state

    initial = read_state()
    require(common.sql("SELECT has_table_privilege('abr-engine','release_gate','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR "
                       "has_table_privilege('abr-engine','policy','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR "
                       "has_any_column_privilege('abr-engine','release_gate','INSERT,UPDATE') OR "
                       "has_any_column_privilege('abr-engine','policy','INSERT,UPDATE');") == 'f', 'AUTHORITY_ROLE_CHANGED')
    receipt = {'release': '010', 'status': 'preview_passed', 'source_manifest_sha256': NEW,
               'technical_evidence_sha256': EVIDENCE_SHA, 'configuration_sha256': common.hashlib.sha256(original).hexdigest(),
               'policy_changed': False, 'configuration_changed': False, 'provider_calls': 0,
               'individual_approvals_created': 0, 'new_gates': 2, 'services_started': False}
    if not execute:
        return receipt
    with common.activation_lock():
        common.command(['systemctl', 'stop', *ghl.STOPPED_UNITS])
        # The already-recorded exit3 is the exact fault being repaired. Reset only
        # this stopped unit so the stop precondition remains strict; rerun after cutover.
        common.command(['systemctl', 'reset-failed', 'abr-engine-qbcc-review-cleanup.service'])
        ghl.stopped()
        require(read_state() == initial and common.read_config() == original, 'STOPPED_BASELINE_CHANGED')
        require(common.sha(evidence) == EVIDENCE_SHA, 'TECHNICAL_EVIDENCE_CHANGED')
        gid = grp.getgrnam('abr-engine').gr_gid
        require(not any(x.is_symlink() for x in (DECISIONS, *DECISIONS.parents))
                and not DECISIONS.exists(), 'DECISION_PATH_REQUIRES_REVIEW')
        DECISIONS.mkdir(mode=0o750)
        os.chown(DECISIONS, 0, gid)
        os.chmod(DECISIONS, 0o750)
        target = DECISIONS / NAME
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
            stream.write(evidence.read_bytes())
            os.fchown(stream.fileno(), 0, gid)
            os.fchmod(stream.fileno(), 0o640)
            stream.flush()
            os.fsync(stream.fileno())
        common.sync_directory(DECISIONS)
        common.sync_directory(DECISIONS.parent)
        require(common.sha(target) == EVIDENCE_SHA, 'INSTALLED_EVIDENCE_CHANGED')
        receipt['source_activation'] = source.activate()
        common.command(['/opt/abr-install-tools/bin/uv', '--directory', '/opt/abn-leadgen', 'sync', '--frozen',
                        '--no-install-project', '--no-build', '--python', '/usr/bin/python3.12', '--no-python-downloads'])
        venv = source.CURRENT / '.venv'
        require(venv.is_dir() and not venv.is_symlink() and venv.resolve() == venv, 'VENV_BOUNDARY_CHANGED')
        for parent, dirs, files in os.walk(venv, followlinks=False):
            for item in [Path(parent), *(Path(parent) / name for name in dirs + files)]:
                info = item.lstat()
                if stat.S_ISLNK(info.st_mode):
                    continue
                require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode), 'VENV_FILE_TYPE_CHANGED')
                os.chown(item, 0, gid)
                os.chmod(item, 0o750 if item.is_dir() or info.st_mode & 0o111 else 0o640)
        ghl.stopped()
        source.manifest(source.CURRENT, NEW)
        rows = [{'gate_name': 'G7', 'environment': 'pilot', 'scope': g['scope'], 'revision': 4,
                 'evidence_ref': str(target), 'evidence_sha256': EVIDENCE_SHA, 'actor_id': common.ACTOR,
                 'approved_at': decision['approved_at'], 'expires_at': g['expires_at']}
                for g in decision['new_gate_revisions']]
        require([(g['scope'], g['revision']) for g in rows] == [('collection', 4), ('retention', 4)], 'EXACT_TWO_GATES_REQUIRED')
        guard = query.removeprefix('SELECT ').removesuffix(';')
        tables = ','.join([*counts, 'pipeline_run', 'action_intent'])
        common.sql('BEGIN; SELECT pg_advisory_xact_lock(2080912); LOCK TABLE '+tables+' IN EXCLUSIVE MODE; '
                   'DO $$ BEGIN IF ('+guard+')::jsonb<>'+common.literal(json.dumps(initial))+'::jsonb '
                   "OR (SELECT count(*) FROM action_intent)<>0 THEN RAISE EXCEPTION 'baseline changed'; END IF; "
                   'IF clock_timestamp()<'+common.literal(decision['approved_at'])+'::timestamptz OR clock_timestamp()>='
                   +common.literal(ghl.END)+"::timestamptz THEN RAISE EXCEPTION 'decision expired'; END IF; END $$; "
                   +''.join(ghl.statement('release_gate', row) for row in rows)+'COMMIT;')
        after = json.loads(common.sql(query))
        appended = [g for g in after['gates'] if g['gate_name'] == 'G7' and g['revision'] == 4]
        require(after['counts'] == {**counts, 'release_gate': 25} and after['policies'] == initial['policies']
                and [g for g in after['gates'] if g not in appended] == initial['gates']
                and [ghl.normalized_record(g) for g in appended] == [ghl.normalized_record(g) for g in rows]
                and after['running_jobs'] == 0 and after['nonphone_contacts'] == 0
                and common.read_config() == original, 'READBACK_CHANGED')
        ghl.stopped()
        return {**receipt, 'status': 'cleanup010_installed_services_stopped', 'counts': after['counts'],
                'previous_gates_preserved': 23, 'policies_preserved': 2, 'verified_at': datetime.now(UTC).isoformat()}


if __name__ == '__main__':
    print(json.dumps(run(execute=sys.argv[1:] == ['--execute'])))
