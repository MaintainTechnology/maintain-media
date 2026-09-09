"""Recovered patterns are review inputs, never a production approval."""

import hashlib
import json

import pytest

from abr_engine.classify.rules import classify, load_rules
from abr_engine.config import ROOT
from abr_engine.ingest.common import SourceError

RULE_PATH = ROOT / "config/rules.review.yaml"


def test_recovered_corpus_has_exact_order_and_remains_unapproved():
    decision = json.loads((ROOT / "ops/acceptance/live-sources/rules-review-decision.json").read_text())
    rules = load_rules(RULE_PATH)
    assert len(rules.rules) == decision["rule_count"] == 30
    assert [r.rule_id for r in rules.rules] == [f"legacy-{n:02}" for n in range(1, 31)]
    assert [r.rule_id for r in rules.rules] == decision["ordered_rule_ids"]
    assert hashlib.sha256(RULE_PATH.read_bytes()).hexdigest() == decision["rule_file_digest"]
    assert decision["status"] == "pending" and decision["owner_approved_at"] is None
    assert decision["precision_sample_count"] == 0
    assert rules.fixture_only and not rules.production_approved
    with pytest.raises(SourceError, match="CLASSIFIER_DISABLED"):
        load_rules(RULE_PATH, production=True, decision=decision)


@pytest.mark.parametrize(
    "names,rule_id,confidence,literal",
    [
        ({"BN": ["Example Solar"], "MAIN": ["Example Electrical"]}, "legacy-03", "high", "Example Solar"),
        ({"BN": ["Z Plumbing", "A Builder"]}, "legacy-21", "high", "A Builder"),
        ({"MAIN": ["Example Plumber"], "TRD": ["Example Solar"]}, "legacy-01", "medium", "Example Plumber"),
        ({"TRD": ["Example Solar"]}, "legacy-03", "medium", "Example Solar"),
        ({"BN": ["Plumbing Electrical"]}, "legacy-01", "high", "Plumbing Electrical"),
        ({"BN": ["  Example   SOLAR  ", "example solar"]}, "legacy-03", "high", "  Example   SOLAR  "),
        ({"BN": ["Example ＳＯＬＡＲ"]}, "legacy-03", "high", "Example ＳＯＬＡＲ"),
        ({"OTN": ["Plumbing"], "MAIN": ["Example Holdings"]}, None, "none", None),
        ({"BN": ["Example Pool Table"]}, None, "none", None),
        ({"BN": []}, None, "none", None),
    ],
)
def test_v4_name_selection_and_recovered_overlap_rules(names, rule_id, confidence, literal):
    result = classify(names, load_rules(RULE_PATH))
    assert (result.rule_id, result.confidence, result.matched_name) == (rule_id, confidence, literal)
