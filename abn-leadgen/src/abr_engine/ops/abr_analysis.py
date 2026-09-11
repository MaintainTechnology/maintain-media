"""Full analytical verification outside the short staff-control commit lock.

The in-memory receipt is never accepted from JSON or an API. It binds the exact
manifest, cursor, immutable artifact ledger and filesystem identities. Final
promotion rechecks those bindings and current authority before becoming visible.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from uuid import UUID

import duckdb

from abr_engine.control.service import digest
from abr_engine.ingest.common import SourceError
from abr_engine.ingest.quality import parquet_fill, validate_fill
from abr_engine.ops.analytical import analytical_guard


def identity(path):
    stat = path.stat()
    if path.is_symlink() or not path.is_file():
        raise SourceError("ARTIFACT_NOT_VERIFIED")
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def known_aliases(conn):
    rows = conn.execute("SELECT link_id,group_id,encrypted_identifier,alias_token,key_version "
                        "FROM lead_source_link WHERE source_type='abn' ORDER BY link_id LIMIT 10001").fetchall()
    if len(rows) > 10000:
        raise SourceError("ABR_KNOWN_IDENTITY_LIMIT")
    return rows


@dataclass(frozen=True)
class ABRAnalysis:
    run_id: UUID
    manifest_digest: str
    expected_version: int
    paths: tuple[str, ...]
    events_path: str
    quality: dict
    files: dict
    aliases_digest: str
    known_abns: tuple[str, ...]
    cancelled_abns: tuple[str, ...]

    def file_digest(self, path):
        sealed = self.files.get(str(Path(path).resolve()))
        if not sealed or identity(Path(path)) != sealed[0]:
            raise SourceError("ANALYSED_ARTIFACT_CHANGED")
        return sealed[1]

    def validate(self, run_id, manifest, paths, events_path, expected_version):
        if (self.run_id != run_id or self.manifest_digest != digest(manifest)
                or self.expected_version != expected_version
                or self.paths != tuple(str(Path(p).resolve()) for p in paths)
                or self.events_path != str(Path(events_path).resolve())):
            raise SourceError("ABR_ANALYSIS_BINDING_CHANGED")
        for path in self.files:
            self.file_digest(path)

    def finalize(self, conn, service, snapshot_id, authority, local_check):
        from abr_engine.ops.promotion import _source_restriction

        started = monotonic()
        conn.execute("SET LOCAL lock_timeout='2s'")
        conn.execute("SET LOCAL statement_timeout='1500ms'")
        authority(conn)
        if digest(known_aliases(conn)) != self.aliases_digest:
            raise SourceError("ABR_KNOWN_IDENTITIES_CHANGED")
        for path in self.files:
            if monotonic() - started > 2:
                raise SourceError("ABR_CONTROL_COMMIT_DEADLINE")
            checksum = self.file_digest(path)
            artifact = conn.execute("SELECT content_digest,byte_count,state FROM artifact_manifest WHERE local_path=%s "
                "AND state IN ('verified','referenced') ORDER BY created_at DESC LIMIT 1 FOR UPDATE", (path,)).fetchone()
            if not artifact or artifact['content_digest'] != checksum or artifact['byte_count'] != self.files[path][0][2]:
                raise SourceError("ANALYSED_ARTIFACT_CHANGED")
        for abn in self.cancelled_abns:
            if monotonic() - started > 2:
                raise SourceError("ABR_CONTROL_COMMIT_DEADLINE")
            _source_restriction(conn, service, abn, "abn_cancelled", snapshot_id)
        local_check()
        if monotonic() - started > 2:
            raise SourceError("ABR_CONTROL_COMMIT_DEADLINE")
        return started


def prepare_analysis(conn, service, run_id, manifest, paths, events_path, expected_version, *, check):
    from abr_engine.ops.promotion import _validate_event_set

    paths = [Path(p) for p in paths]
    cursor = conn.execute("SELECT c.*,s.manifest FROM source_cursor c LEFT JOIN source_snapshot s USING(snapshot_id) "
                          "WHERE c.source='abr'").fetchone()
    if (cursor['version'] if cursor else 0) != expected_version:
        raise SourceError("SOURCE_CURSOR_CONFLICT")
    previous = [Path(p) for p in cursor['manifest']['parquet_paths']] if cursor and cursor['snapshot_id'] else []
    sealed = {}
    for path in [*paths, Path(events_path), *previous]:
        check()
        before = identity(path)
        checksum_builder = hashlib.sha256()
        since_check = 0
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                checksum_builder.update(block)
                since_check += len(block)
                if since_check >= 64 * 1024**2:
                    check()
                    since_check = 0
        checksum = checksum_builder.hexdigest()
        if identity(path) != before:
            raise SourceError("ANALYSED_ARTIFACT_CHANGED")
        row = conn.execute("SELECT content_digest,byte_count FROM artifact_manifest WHERE local_path=%s "
                           "AND state IN ('verified','referenced') ORDER BY created_at DESC LIMIT 1",
                           (str(path.resolve()),)).fetchone()
        if not row or row['content_digest'] != checksum or row['byte_count'] != before[2]:
            raise SourceError("ARTIFACT_NOT_VERIFIED")
        sealed[str(path.resolve())] = (before, checksum)
    analytical = duckdb.connect()
    try:
        analytical.execute("SET memory_limit='512MB'")
        analytical.execute("SET threads=2")
        analytical.execute("SET max_temp_directory_size='8GB'")
        analytical.execute("SET temp_directory=?", [str(Path(events_path).parent / 'analysis-spill')])
        current_quality = parquet_fill(paths, check=check)
        previous_quality = parquet_fill(previous, check=check) if previous else None
        validate_fill(current_quality, manifest, previous_quality)
        with analytical_guard(analytical, check):
            aliases = known_aliases(conn)
            analytical.execute("CREATE TABLE wanted(abn VARCHAR PRIMARY KEY)")
            if aliases:
                analytical.executemany("INSERT INTO wanted VALUES(?) ON CONFLICT DO NOTHING",
                                      [(service.keys.decrypt(row['encrypted_identifier']),) for row in aliases])
                cancelled = analytical.execute("SELECT DISTINCT c.abn FROM read_parquet(?) c JOIN wanted USING(abn) "
                    "WHERE c.status='CAN' ORDER BY c.abn", [[str(p) for p in paths]]).fetchall()
            else:
                cancelled = []
        if previous:
            _validate_event_set([str(p) for p in previous], paths, Path(events_path), check=check)
        result = ABRAnalysis(UUID(str(run_id)), digest(manifest), expected_version,
            tuple(str(p.resolve()) for p in paths), str(Path(events_path).resolve()), current_quality,
            sealed, digest(aliases), tuple(sorted({service.keys.decrypt(row['encrypted_identifier']) for row in aliases})),
            tuple(row[0] for row in cancelled))
        for path in sealed:
            result.file_digest(path)
        check()
        return result
    finally:
        analytical.close()
