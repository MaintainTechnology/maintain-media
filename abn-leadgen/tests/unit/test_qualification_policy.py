import copy
from datetime import date
from itertools import product

import pytest
import yaml

from abr_engine.qualify.abr import qualify_abr, qualify_qbcc, target_geography
from abr_engine.qualify.policy import APPROVED, current_policy, load_policy, policy_metadata
from abr_engine.qualify.queue import score


def test_all_score_combinations_match_exact_v4():
    for source, tier, category in [("abr", t, None) for t in "ABC"] + [("qbcc", "A", c) for c in ("1", "2")]:
        for confidence, geography, company, email, phone, website, provisional in product(
            ("high", "medium", "none"), *([(False, True)] * 6)
        ):
            contact = 0 if provisional else max(20 if email else 0, 15 if phone else 0, 5 if website else 0)
            base = (
                ({"A": 60, "B": 30, "C": 0}[tier] + {"high": 15, "medium": 5, "none": 0}[confidence])
                if source == "abr"
                else 60 + (20 if category == "2" else 15)
            )
            assert score(
                source=source,
                tier=tier,
                category=category,
                confidence=confidence,
                geography=geography,
                company=company,
                deliverable_email=email,
                phone=phone,
                website=website,
                provisional=provisional,
            ) == min(100, base + 10 * geography + 5 * company + contact)


@pytest.mark.parametrize("mutation", ["coefficient", "unknown", "missing", "version", "bool", "postcode"])
def test_invalid_or_unapproved_policy_is_rejected(tmp_path, mutation):
    data = copy.deepcopy(APPROVED)
    if mutation == "coefficient":
        data["scoring"]["abr_tier"]["A"] = 61
    if mutation == "unknown":
        data["override"] = True
    if mutation == "missing":
        del data["queue"]
    if mutation == "version":
        data["rule_version"] = "unreviewed-v5"
    if mutation == "bool":
        data["schema_version"] = True
    if mutation == "postcode":
        data["qualification"]["postcode_min"] = 2450
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="NOT_APPROVED"):
        load_policy(path)


def test_duplicate_keys_and_mutation_are_rejected(tmp_path):
    path = tmp_path / "duplicate.yaml"
    path.write_text("schema_version: 1\nschema_version: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="DUPLICATE"):
        load_policy(path)
    with pytest.raises(TypeError):
        current_policy().scoring["abr_tier"]["A"] = 99


def test_qualification_boundaries_and_version_are_preserved():
    record = {
        "status": "ACT",
        "gst_status": "ACT",
        "status_date": "2025-09-08",
        "state": "NSW",
        "postcode": "2450",
    }
    result = qualify_abr(record, {"gst_registered"}, date(2026, 9, 8))
    assert result.tier == "A" and result.enrichment_eligible
    assert result.rule_version == policy_metadata()["qualification_rule_version"] == "abr-qualification-v4.0"
    assert not qualify_abr(record, {"gst_registered"}, date(2026, 9, 7)).enrichment_eligible
    assert not qualify_abr(record, {"gst_registered"}, date(2030, 9, 8)).enrichment_eligible
    assert target_geography("NSW", "2490") and not target_geography("NSW", "2491")
    assert (
        qualify_qbcc(
            {"status": "ACTIVE", "financial_category": "1", "state": "QLD", "postcode": "4000"}, "icp_backlog"
        ).tier
        == "A"
    )
