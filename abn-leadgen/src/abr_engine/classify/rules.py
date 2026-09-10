from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from abr_engine.ingest.common import SourceError, canonical_name, ordered_names


@dataclass(frozen=True)
class Rule:
    rule_id: str
    industry: str
    pattern: str


@dataclass(frozen=True)
class RuleSet:
    version: str
    digest: str
    rules: tuple[Rule, ...]
    fixture_only: bool = True
    production_approved: bool = False


@dataclass(frozen=True)
class Classification:
    industry: str
    confidence: str
    matched_name: str | None
    name_source: str | None
    rule_id: str | None
    rule_version: str
    rule_digest: str


def load_rules(path: Path, *, production: bool = False, decision: dict | None = None) -> RuleSet:
    raw = path.read_bytes()
    value = yaml.safe_load(raw)
    if not isinstance(value, dict) or set(value) != {"version", "fixture_only", "rules"}:
        raise SourceError("INVALID_RULE_SCHEMA")
    if (
        not isinstance(value["fixture_only"], bool)
        or not isinstance(value["version"], str)
        or not value["version"]
    ):
        raise SourceError("INVALID_RULE_SCHEMA")
    # Newline-canonical: the corpus is a text file whose line endings Git rewrites per
    # checkout, so hashing raw bytes would read a Windows working tree and a Linux
    # deployment as different corpora and disable the classifier on one of them.
    digest = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    rules = []
    for row in value["rules"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"rule_id", "industry", "pattern"}
            or any(not isinstance(v, str) or not v for v in row.values())
        ):
            raise SourceError("INVALID_RULE_SCHEMA")
        try:
            re.compile(row["pattern"])
        except re.error as exc:
            raise SourceError("INVALID_RULE_REGEX") from exc
        rules.append(Rule(**row))
    if len({r.rule_id for r in rules}) != len(rules) or not rules:
        raise SourceError("DUPLICATE_OR_EMPTY_RULES")
    if production:
        required = (
            "decision_id",
            "source_sha256",
            "rule_file_digest",
            "ordered_rule_ids",
            "mapping_version",
            "reviewer",
            "owner_approved_at",
            "fixture_suite_digest",
        )
        if (
            value["fixture_only"]
            or not decision
            or any(not decision.get(k) for k in required)
            or decision.get("status") not in ("recovered", "replacement_approved")
            or decision["rule_file_digest"] != digest
            or decision["ordered_rule_ids"] != [r.rule_id for r in rules]
            or decision.get("rule_count") != len(rules)
            or decision.get("precision_sample_count", 0) < 100
            or decision.get("blocked_rule_ids")
            or (decision["status"] == "recovered" and len(rules) != 30)
        ):
            raise SourceError("CLASSIFIER_DISABLED")
    return RuleSet(value["version"], digest, tuple(rules), value["fixture_only"], production)


def classify(names: dict[str, list[str]], rules: RuleSet, *, production: bool = False) -> Classification:
    if production and (rules.fixture_only or not rules.production_approved):
        raise SourceError("CLASSIFIER_DISABLED")
    for kind in ("BN", "MAIN", "TRD"):
        for literal in ordered_names(names.get(kind, [])):
            for rule in rules.rules:
                if re.search(rule.pattern, canonical_name(literal)):
                    return Classification(
                        rule.industry,
                        "high" if kind == "BN" else "medium",
                        literal,
                        kind,
                        rule.rule_id,
                        rules.version,
                        rules.digest,
                    )
    return Classification("Unclassified", "none", None, None, None, rules.version, rules.digest)
