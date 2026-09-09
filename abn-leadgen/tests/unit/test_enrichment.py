from datetime import UTC, date, datetime, timedelta

import pytest

from abr_engine.compliance.calling import (
    HolidayCalendar,
    evaluate_call_window,
    evaluate_licence_review,
    invitation_state,
)
from abr_engine.enrich.endpoints import (
    EmailCandidate,
    normalize_email,
    normalize_phone,
    positioning_excerpt,
    select_email,
)
from abr_engine.enrich.identity import (
    IdentityEvidence,
    assess_identity,
    current_identity,
    discovery_queries,
    domain_excluded,
    registrable_domain,
)
from abr_engine.enrich.worker import (
    AttemptState,
    Eligibility,
    complete_stage,
    enrichment_block,
    finish,
    interrupt,
    stage_needed,
)

NOW = datetime(2026, 9, 8, tzinfo=UTC)


def test_email_preserves_endpoint_identity_and_selects_one():
    assert normalize_email(" A.B+Tag@EXAMPLE.COM ") == "a.b+tag@example.com"
    options = [
        EmailCandidate("a@example.com", permitted_generic_role=True, provenance_id="p1"),
        EmailCandidate("Z@example.com", reviewed_named_role=True, provenance_id="p2"),
        EmailCandidate("b@example.com", reviewed_named_role=True, provenance_id="p3"),
    ]
    assert select_email(options).email == "b@example.com"
    assert select_email([EmailCandidate("a@example.com")]) is None


@pytest.mark.parametrize(
    "value",
    ["000", "+12025550123", "0412 345 678 ext 2", "412345678", "0001234567", "61 412345678", "13 11 14"],
)
def test_reject_bad_phones(value):
    with pytest.raises(ValueError):
        normalize_phone(value)


def test_phone_e164_is_idempotent():
    assert normalize_phone("0412 345 678") == "+61412345678"
    assert normalize_phone("+61 412 345 678") == "+61412345678"
    assert normalize_phone("(07) 3123 4567") == "+61731234567"
    assert normalize_phone("1300 123 456") == "+611300123456"


@pytest.mark.parametrize("email", ["a@example..com", "a@exam_ple.com", "a@exam/ple.com", "a..b@example.com"])
def test_invalid_email_domains_do_not_become_candidates(email):
    with pytest.raises(ValueError, match="EMAIL_INVALID"):
        normalize_email(email)


def test_sourced_positioning_is_bounded_static_text():
    value = positioning_excerpt(
        "<title>ACME</title><meta name='description' content='"
        + "x" * 450
        + "'><script>evil()</script><h1>Heading</h1>",
        "https://example.com/",
    )
    assert len(value.text) == 400
    assert value.source_url == "https://example.com/"
    assert "evil" not in value.text


def test_private_psl_domains_and_blocklists_match_boundaries():
    assert registrable_domain("https://a.business.com.au/") == "business.com.au"
    assert registrable_domain("https://tenant.github.io/") == "tenant.github.io"
    assert domain_excluded("https://www.facebook.com/example", ("facebook.com",))
    assert not domain_excluded("https://facebook.com.example.com/", ("facebook.com",))


def test_discovery_queries_bounded_and_deterministic():
    queries = discovery_queries("Example Plumbing", "QLD", "4000", ("Zulu", "Alpha", "Alpha"))
    assert len(queries) == 3
    assert '"Alpha"' in queries[1]
    assert all("QLD 4000" in q for q in queries)


def evidence(html, **kwargs):
    return IdentityEvidence("group", "example.com", "https://example.com/", html, NOW, **kwargs)


def test_exact_validated_abn_or_reviewer_corroboration_only():
    good = assess_identity(evidence("ABN 51 824 753 556", source_abn="51824753556"), now=NOW)
    assert good.approved and good.method == "exact_abn"
    assert not assess_identity(evidence("Example Pty Ltd"), now=NOW).approved
    assert not assess_identity(
        evidence("<script>51824753556</script>", source_abn="51824753556"), now=NOW
    ).approved
    assert not assess_identity(evidence("ABN 11 111 111 111", source_abn="11111111111"), now=NOW).approved
    assert assess_identity(evidence("QBCC 123456", source_licence="123456"), now=NOW).approved
    assert not assess_identity(evidence("QBCC 1234567", source_licence="123456"), now=NOW).approved
    assert assess_identity(
        evidence(
            "Example",
            reviewer_id="reviewer",
            reviewer_approved=True,
            matching_attributes=("name", "full_address"),
            references=("source", "page"),
        ),
        now=NOW,
    ).approved
    assert not assess_identity(
        evidence(
            "Example",
            reviewer_id="reviewer",
            reviewer_approved=True,
            matching_attributes=("name",),
            references=("source", "page"),
        ),
        now=NOW,
    ).approved


def test_latest_identity_rejection_and_expiry_override_pass():
    good = assess_identity(evidence("ABN 51824753556", source_abn="51824753556"), now=NOW)
    bad = assess_identity(evidence("Other business"), now=NOW)
    assert current_identity([(1, good)], group_id="group", domain="example.com", now=NOW)
    assert not current_identity([(1, good), (2, bad)], group_id="group", domain="example.com", now=NOW)
    assert not current_identity(
        [(1, good)], group_id="group", domain="example.com", now=NOW + timedelta(days=90)
    )


def test_budget_interrupt_resumes_completed_receipts_and_failures_cool_down():
    state = complete_stage(AttemptState("attempt"), "search", "receipt")
    held = interrupt(state, "BUDGET_STOP")
    assert not stage_needed(held, "search") and stage_needed(held, "verify")
    assert held.next_eligible_at is None
    with pytest.raises(ValueError, match="INTERRUPTED"):
        finish(held, now=NOW, exhausted=True)
    resumed = complete_stage(held, "verify", "receipt2")
    done = finish(resumed, now=NOW, exhausted=True)
    candidate = Eligibility("A", "QLD", "4000", False, True)
    assert enrichment_block(candidate, done, now=NOW) == "ENRICHMENT_COOLDOWN"
    assert enrichment_block(candidate, done, now=NOW + timedelta(days=90)) is None
    with pytest.raises(ValueError, match="CONFLICT"):
        complete_stage(state, "search", "different")


@pytest.mark.parametrize(
    "candidate",
    [
        Eligibility("C", "QLD", "4000", False, True),
        Eligibility("A", None, "4000", False, True),
        Eligibility("A", "NSW", "2491", False, True),
        Eligibility("A", "QLD", "4000", True, True),
        Eligibility("A", "QLD", "4000", False, False),
    ],
)
def test_ineligible_enrichment_never_runs(candidate):
    assert enrichment_block(candidate, None, now=NOW)


def calendar(zone="Australia/Brisbane", holidays=frozenset()):
    return HolidayCalendar(
        "reviewed locality", zone, date(2026, 1, 1), date(2026, 12, 31), holidays, "v1", "evidence", True
    )


@pytest.mark.parametrize(
    "timestamp,allowed,reason",
    [
        ("2026-09-07T22:59:59+00:00", False, "OUTSIDE_CALL_WINDOW"),
        ("2026-09-07T23:00:00+00:00", True, "CALL_WINDOW_PASSED"),
        ("2026-09-08T07:59:59+00:00", True, "CALL_WINDOW_PASSED"),
        ("2026-09-08T08:00:00+00:00", False, "OUTSIDE_CALL_WINDOW"),
        ("2026-09-12T07:00:00+00:00", False, "OUTSIDE_CALL_WINDOW"),
        ("2026-09-13T00:00:00+00:00", False, "SUNDAY"),
    ],
)
def test_call_window_boundaries(timestamp, allowed, reason):
    d = evaluate_call_window(
        now=datetime.fromisoformat(timestamp),
        timezone="Australia/Brisbane",
        locality="reviewed locality",
        timezone_confirmed=True,
        calendar=calendar(),
    )
    assert (d.allowed, d.reason) == (allowed, reason)


def test_holiday_timezone_unknown_and_dst():
    args = {
        "now": NOW,
        "timezone": "Australia/Brisbane",
        "locality": "reviewed locality",
        "timezone_confirmed": True,
    }
    assert not evaluate_call_window(**args, calendar=None).allowed
    assert not evaluate_call_window(**(args | {"timezone_confirmed": False}), calendar=calendar()).allowed
    assert (
        evaluate_call_window(**args, calendar=calendar(holidays=frozenset({NOW.date()}))).reason
        == "PUBLIC_HOLIDAY"
    )
    d = evaluate_call_window(
        **(args | {"now": datetime(2026, 10, 5, 7, tzinfo=UTC), "timezone": "Australia/Sydney"}),
        calendar=calendar("Australia/Sydney"),
    )
    assert d.local_time.hour == 18 and not d.allowed


def test_licence_expiry_and_invitation_is_independent():
    args = {"now": NOW, "status": "active", "identity_match": True, "evidence_ref": "evidence"}
    assert evaluate_licence_review(**args, reviewed_at=NOW - timedelta(days=29))
    assert not evaluate_licence_review(**args, reviewed_at=NOW - timedelta(days=30))
    assert not evaluate_licence_review(**args, reviewed_at=NOW + timedelta(seconds=1))
    assert invitation_state() == "unknown"
    with pytest.raises(ValueError):
        invitation_state("invited")
