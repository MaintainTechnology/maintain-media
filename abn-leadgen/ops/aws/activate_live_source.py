"""Activate the verified September 11 source, preserving the dormant release."""
import hashlib
import json
import os
import stat
from pathlib import Path

CURRENT = Path('/opt/abn-leadgen')
STAGED = Path('/opt/abn-leadgen-live-20260911-001')
PREVIOUS = Path('/opt/abn-leadgen-foundation-20260910')
OLD_MANIFEST = '2cc26eea965e51ac1772d9048e07752e38881d1efa939ef3c06ed3b59d079847'
NEW_MANIFEST = '71a7d0a78c0340f2e3e2c7afcfb0f1fa62f500b42da6f337df08adeab4788607'


def ordinary(path):
    for item in (path, *path.parents):
        if item.is_symlink() or item.resolve() != item:
            raise ValueError('SOURCE_PATH_REFUSED')


def manifest(path, expected):
    ordinary(path)
    source = path / 'RELEASE-MANIFEST.json'
    ordinary(source)
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('SOURCE_MANIFEST_MISMATCH')
    for row in json.loads(raw)['files']:
        member = path / row['path']
        ordinary(member)
        if path not in member.parents or not member.is_file():
            raise ValueError('SOURCE_MEMBER_REFUSED')
        if hashlib.sha256(member.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('SOURCE_MEMBER_CHANGED')


def activate():
    import grp

    if os.geteuid() != 0:
        raise ValueError('ROOT_REQUIRED')
    for path in (CURRENT, STAGED, PREVIOUS):
        ordinary(path)
        if path.parent != Path('/opt'):
            raise ValueError('SOURCE_BOUNDARY_REFUSED')
    if PREVIOUS.exists():
        raise ValueError('PREVIOUS_RELEASE_ALREADY_EXISTS')
    manifest(CURRENT, OLD_MANIFEST)
    manifest(STAGED, NEW_MANIFEST)
    group = grp.getgrnam('abr-engine').gr_gid
    # Only the new public allowlist is traversed; runtime data/config stay elsewhere.
    for parent, directories, files in os.walk(STAGED, followlinks=False):
        for item in [Path(parent), *(Path(parent) / name for name in directories + files)]:
            ordinary(item)
            info = item.lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError('SOURCE_FILE_TYPE_REFUSED')
            os.chown(item, 0, group)
            os.chmod(item, 0o750 if item.is_dir() else 0o640)
    CURRENT.rename(PREVIOUS)
    try:
        STAGED.rename(CURRENT)
    except OSError:
        PREVIOUS.rename(CURRENT)
        raise
    return {'status': 'live_source_activated', 'source_manifest_sha256': NEW_MANIFEST,
            'previous_release_preserved': str(PREVIOUS), 'services_started': False}


if __name__ == '__main__':
    print(json.dumps(activate()))
