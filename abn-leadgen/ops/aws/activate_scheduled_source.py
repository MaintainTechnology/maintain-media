"""Activate the reviewed scheduler/backup source while retaining the first live release."""
import json
from pathlib import Path

import activate_live_source as release

release.STAGED = Path('/opt/abn-leadgen-live-20260911-002')
release.PREVIOUS = Path('/opt/abn-leadgen-live-20260911-001-previous')
release.OLD_MANIFEST = '71a7d0a78c0340f2e3e2c7afcfb0f1fa62f500b42da6f337df08adeab4788607'
release.NEW_MANIFEST = 'fce7c862196a6bc65096b5377bdc5a2ed4f2eef58728300a6584394a48eab0a6'

if __name__ == '__main__':
    print(json.dumps(release.activate()))
