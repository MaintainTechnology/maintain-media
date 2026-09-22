"""Research claims require explicit evidence and never infer absence from empty fields."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from abr_engine.live.prospects import ProspectQuery, ProspectSave, query_prospects


def payload(**updates):
    return {"request_id": str(uuid4()), "abn": "51824753556", "expected_revision": 0,
            "source": "abr", "snapshot_id": str(uuid4()), **updates}


def test_unknown_defaults_are_not_missing_presence():
    record = ProspectSave.model_validate(payload())
    assert record.website_presence == record.email_presence == record.social_presence == "unknown"
    assert record.registration_date is None and record.contact_stage == "not_contacted"


@pytest.mark.parametrize("updates", [
    {"website_presence": "absent"}, {"email_presence": "present"},
    {"social_presence": "absent"}, {"contact_stage": "contacted"},
    {"website_url": "https://example.com"},
    {"website_presence": "absent", "website_url": "https://example.com", "evidence_ref": "synthetic"},
    {"website_presence": "present", "website_url": "javascript:alert(1)", "evidence_ref": "synthetic"},
    {"website_presence": "present", "website_url": "https://user:pass@example.com", "evidence_ref": "synthetic"},
    {"email_presence": "present", "email": "not an email", "evidence_ref": "synthetic"},
    {"phone": "+12025550123", "evidence_ref": "synthetic"},
    {"registration_date": "2026-09-22"}, {"registration_evidence_ref": "synthetic"},
    {"contact_stage": "follow_up", "evidence_ref": "synthetic"},
    {"expected_revision": True}, {"expected_revision": -1}, {"run_id": "arbitrary"},
    {"abn": "123"}, {"send_email": True},
    {"registration_date": 0, "registration_evidence_ref": "synthetic"},
])
def test_invalid_or_unsupported_research_is_rejected(updates):
    with pytest.raises(ValidationError):
        ProspectSave.model_validate(payload(**updates))


def test_verified_presence_and_registration_have_separate_evidence():
    record = ProspectSave.model_validate(payload(website_presence="absent", email_presence="present",
        email=" HELLO@example.com ", evidence_ref="Search and owner confirmation, synthetic",
        registration_date="2026-09-20", registration_evidence_ref="Original registration history, synthetic",
        contact_stage="follow_up", follow_up_on="2026-09-25"))
    assert record.email == "hello@example.com" and record.registration_date.isoformat() == "2026-09-20"


@pytest.mark.parametrize("query", [
    {"offset": -1}, {"offset": True}, {"filters": {"status_date_from": "2026-09-01"}},
    {"filters": {"registration_date_from": "2026-09-22", "registration_date_to": "2026-09-01"}},
    {"filters": {"website_presence": "missing"}},
    {"filters": {"registration_date_from": 0}},
])
def test_query_is_closed_and_registration_range_validated(query):
    with pytest.raises(ValidationError):
        ProspectQuery.model_validate(query)


@pytest.mark.parametrize("abns", [
    [], ["51824753556", "51824753556"], ["5182475355"], ["518247535560"],
    ["51 824 753 556"], ["５１８２４７５３５５６"], [51824753556], [True],
    [f"{number:011}" for number in range(51)], "51824753556",
])
def test_batch_query_rejects_empty_duplicate_invalid_and_oversize_identifiers(abns):
    with pytest.raises(ValidationError):
        ProspectQuery.model_validate({"abns": abns})


def test_batch_query_is_optional_and_accepts_up_to_fifty_identifiers():
    assert ProspectQuery().abns is None
    assert ProspectQuery(abns=None).abns is None
    abns = [f"{number:011}" for number in range(50)]
    assert ProspectQuery(abns=abns).abns == abns


def test_batch_lookup_bounds_sql_by_every_requested_hmac_and_retained_key_version():
    conn, service = MagicMock(), MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.__iter__.return_value = iter([])
    service.now.return_value = "synthetic-now"
    service.keys.matches.side_effect = lambda namespace, abn: [(1, "old:" + abn), (2, "new:" + abn)]
    abns = ["51824753556", "11111111111"]
    result = query_prospects(conn, service, ProspectQuery(abns=abns), "synthetic-reviewer")

    service.personal_data_access.assert_called_once_with(conn)
    sql, params = cursor.execute.call_args.args
    assert sql.count("alias_token=%s AND key_version=%s") == 4
    assert all(abn not in sql for abn in abns)
    assert params == ["synthetic-now", "old:" + abns[0], 1, "new:" + abns[0], 2,
                      "old:" + abns[1], 1, "new:" + abns[1], 2]
    assert result == {"records": [], "total": 0, "offset": 0, "limit": 50, "next_offset": None}
