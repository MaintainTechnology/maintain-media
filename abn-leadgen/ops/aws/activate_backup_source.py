"""Activate reviewed backup scheduling and ledger queue; preserve release 004."""
import json
from pathlib import Path

import activate_live_source as release

release.STAGED = Path('/opt/abn-leadgen-live-20260911-005')
release.PREVIOUS = Path('/opt/abn-leadgen-live-20260911-004-previous')
release.OLD_MANIFEST = '3ca70c9b2f3eb8fbdc76cee29eee081dfd16e3d0dfcb0357a70a23180014d04d'
release.NEW_MANIFEST = '63d60911fe6fa6ef24d5f025dc5018e39ae577ed3602937f2d292ad6fa214c7b'

if __name__ == '__main__':
    print(json.dumps(release.activate()))
