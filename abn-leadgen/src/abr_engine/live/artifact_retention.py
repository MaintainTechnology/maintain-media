"""Checked file hashes outside the short live retention authority transaction."""
from __future__ import annotations

import hashlib
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from abr_engine.control.service import DomainError, Service, digest
from abr_engine.db import transaction

MAX_PREVALIDATED_FILES = 128


def file_identity(path: Path, root: Path):
    """Validate the original path, including junctions and every parent, before resolve."""
    if not path.is_absolute() or '..' in path.parts or path == root or not path.is_relative_to(root):
        raise DomainError('ARTIFACT_OUTSIDE_RETENTION_ROOT')
    for item in (*reversed(path.parents), path):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise DomainError('ARTIFACT_LINK_REFUSED')
        if item != path and not stat.S_ISDIR(info.st_mode):
            raise DomainError('ARTIFACT_PARENT_CHANGED')
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise DomainError('ARTIFACT_LINK_REFUSED')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def row_digest(row):
    return digest({key: row.get(key) for key in ('artifact_id', 'run_id', 'source', 'object_key',
        'local_path', 'content_digest', 'byte_count', 'state', 'snapshot_id', 'artifact_class', 'created_at')})


@dataclass(frozen=True)
class ArtifactRetentionSeals:
    schema_name: str
    root: str
    files: dict
    observations: list

    def validate(self, row, path, root, schema_name):
        if self.schema_name != schema_name or self.root != str(root):
            raise DomainError('ARTIFACT_PREVALIDATION_SCOPE_CHANGED')
        sealed = self.files.get(str(row['artifact_id']))
        if not sealed or sealed['row_digest'] != row_digest(row):
            raise DomainError('ARTIFACT_PREVALIDATION_CHANGED')
        if sealed.get('reason'):
            raise DomainError(sealed['reason'])
        if file_identity(path, root) != sealed['identity']:
            raise DomainError('ARTIFACT_PREVALIDATION_CHANGED')
        return sealed['identity']


def prepare_artifact_retention(service, *, now):
    """Seal at most128 due files; no file is unlinked or authority record changed."""
    from abr_engine.compliance.retention import _execute_gate, _held, retention_deadline
    from abr_engine.pipeline import safe_root

    root = safe_root(service.settings)
    with transaction(service.settings) as conn:
        service.personal_data_access(conn)
        _execute_gate(conn, service, now=Service.now(conn))
        rows = conn.execute('SELECT a.*,r.state AS run_state FROM artifact_manifest a '
            "JOIN pipeline_run r USING(run_id) WHERE a.state<>'deleted' ORDER BY a.created_at,a.artifact_id").fetchall()
        selected: list[dict] = []
        observations: list[dict] = []
        backlog = 0
        for row in rows:
            orphan = row['state'] in {'writing', 'orphan'} or (row['snapshot_id'] is None
                and row['state'] == 'verified' and row['run_state'] in {'failed', 'held'})
            kind = 'orphan' if orphan else row.get('artifact_class')
            try:
                due = retention_deadline(kind or '', row['created_at'])
            except DomainError as error:
                if len(observations) < MAX_PREVALIDATED_FILES:
                    observations.append({'artifact_id': str(row['artifact_id']), 'state': 'held', 'reason': error.code})
                else:
                    backlog += 1
                continue
            if now < due:
                continue
            if (row['run_state'] == 'running' or _held(conn, 'artifact', row['artifact_id'])
                    or _held(conn, 'run', row['run_id']) or _held(conn, 'pipeline_run', row['run_id'])
                    or row['snapshot_id'] and _held(conn, 'snapshot', row['snapshot_id'])):
                if len(observations) < MAX_PREVALIDATED_FILES:
                    observations.append({'artifact_id': str(row['artifact_id']), 'state': 'held',
                        'reason': 'ARTIFACT_ACTIVE_OR_HELD', 'due_at': due.isoformat()})
                else:
                    backlog += 1
            elif len(selected) < MAX_PREVALIDATED_FILES:
                selected.append(row)
            else:
                backlog += 1
        if backlog:
            observations.append({'state': 'held', 'reason': 'ARTIFACT_PREVALIDATION_BACKLOG', 'pending_count': backlog})
    # No authority/row lock survives the transaction above. Long disk reads can
    # neither block a stop request nor obtain deletion permission on their own.
    started, last_authority = time.monotonic(), 0.0

    def check():
        nonlocal last_authority
        if time.monotonic() - started > 300:
            raise DomainError('ARTIFACT_PREVALIDATION_DEADLINE')
        if time.monotonic() - last_authority >= 2:
            with transaction(service.settings) as conn:
                conn.execute("SET LOCAL lock_timeout='2s'")
                conn.execute("SET LOCAL statement_timeout='5s'")
                service.personal_data_access(conn)
                _execute_gate(conn, service, now=Service.now(conn))
            last_authority = time.monotonic()

    files = {}
    for row in selected:
        sealed = {'row_digest': row_digest(row), 'identity': None}
        try:
            check()
            if not row.get('local_path'):
                raise DomainError('ARTIFACT_LOCATION_UNAVAILABLE')
            if not row['object_key'].startswith(f"staging/{row['source']}/{row['run_id']}/"):
                raise DomainError('ARTIFACT_OWNERSHIP_MISMATCH')
            path = Path(row['local_path'])
            before = file_identity(path, root)
            if before is not None:
                if before[2] != row['byte_count']:
                    raise DomainError('ARTIFACT_SIZE_MISMATCH')
                checksum = hashlib.sha256()
                checked_bytes = 0
                with path.open('rb') as stream:
                    opened = os.fstat(stream.fileno())
                    # Windows fstat exposes a different ctime from path.lstat;
                    # pathname ctime is still bound before/after every hash and
                    # final deletion. The opened handle must match inode/size/mtime.
                    if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                        or (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != before[:4]
                        or os.name != 'nt' and opened.st_ctime_ns != before[4]):
                        raise DomainError('ARTIFACT_PREVALIDATION_CHANGED')
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        checksum.update(block)
                        checked_bytes += len(block)
                        if checked_bytes >= 16 * 1024**2:
                            check()
                            checked_bytes = 0
                check()
                if file_identity(path, root) != before:
                    raise DomainError('ARTIFACT_PREVALIDATION_CHANGED')
                if checksum.hexdigest() != row['content_digest']:
                    raise DomainError('ARTIFACT_DIGEST_MISMATCH')
            sealed['identity'] = before
        except DomainError as error:
            sealed['reason'] = error.code
        except OSError:
            sealed['reason'] = 'ARTIFACT_IO_FAILURE'
        files[str(row['artifact_id'])] = sealed
    check()
    return ArtifactRetentionSeals(service.settings.schema_name, str(root), files, observations)


def run_artifact_retention(service, *, now, execute=True):
    """Scheduled live entry point: each final unlink uses its own short transaction."""
    from abr_engine.compliance.retention import artifact_retention

    prepared = prepare_artifact_retention(service, now=now)
    results = list(prepared.observations)
    for artifact_id in prepared.files:
        with transaction(service.settings) as conn:
            conn.execute("SET LOCAL lock_timeout='2s'")
            conn.execute("SET LOCAL statement_timeout='1500ms'")
            results.extend(artifact_retention(conn, service, now=Service.now(conn), execute=execute,
                prepared=prepared, artifact_ids=[artifact_id]))
    return results
