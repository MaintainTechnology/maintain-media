from abr_engine.fixture import seed_contact, seed_policy
from abr_engine.qualify.identity import duplicate_hints


def test_same_name_alone_never_hints_or_merges(db, service):
    a = service.create_lead(db, name='Same Name', source='qbcc', alias='440001')
    service.create_lead(db, name='Same Name', source='qbcc', alias='440002')
    assert duplicate_hints(db, service, a['lead_id']) == []
    assert db.execute('SELECT count(*) n FROM business_group').fetchone()['n'] == 2


def test_shared_domain_hints_never_disclose_contact_or_merge(db, service):
    seed_policy(db, service)
    a, b = seed_contact(db, service), seed_contact(db, service)
    hints = duplicate_hints(db, service, a['lead']['lead_id'])
    assert any(h['lead_id'] == b['lead']['lead_id'] and h['reason'] == 'shared_domain' for h in hints)
    assert all(set(h) == {'lead_id','group_id','reason','action'} for h in hints)
    assert db.execute('SELECT count(*) n FROM business_group').fetchone()['n'] == 2
