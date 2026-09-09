from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from abr_engine.control.api import create_app
from abr_engine.control.auth import fixture_token
from abr_engine.db import transaction
from abr_engine.export.worklist import build_worklist
from abr_engine.fixture import seed_contact, seed_policy


@pytest.mark.parametrize('flag', ['restore_quarantine', 'key_compromised'])
def test_quarantine_prevents_personal_data_reads(settings, service, flag):
    with transaction(settings) as conn:
        seed_policy(conn, service)
        seeded = seed_contact(conn, service)
        now = service.now(conn)
        worklist = build_worklist(conn, service, now.date()-timedelta(days=now.weekday()))
    client = TestClient(create_app(settings))
    headers = {'Authorization': 'Bearer ' + fixture_token(service), 'X-Request-ID': str(uuid4())}
    evidence = '/v1/evidence/' + str(seeded['contact']['first_provenance_id'])
    work = '/v1/worklists/' + str(worklist['worklist_id'])
    assert client.get(evidence, headers=headers).status_code == 200
    assert client.get(work, headers=headers).status_code == 200
    with transaction(settings) as conn:
        conn.execute("UPDATE system_state SET value='true' WHERE name=%s", (flag,))
    for path in (evidence, work):
        response = client.get(path, headers=headers)
        assert response.status_code == 503
        assert response.json()['code'] == 'AUTHORITY_QUARANTINED'
        assert 'example.com' not in response.text and 'Synthetic Builder' not in response.text
