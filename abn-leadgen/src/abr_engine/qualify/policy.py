"""Exact reviewed v4 policy, loaded from YAML; changes require a reviewed version migration."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from abr_engine.config import ROOT

# This approval schema deliberately does not turn configuration into a policy override.
APPROVED = {
    "schema_version": 1,
    "rule_version": "abr-qualification-v4.0",
    "spec_version": "4.0",
    "scoring": {
        "abr_tier": {"A": 60, "B": 30, "C": 0},
        "confidence": {"high": 15, "medium": 5, "none": 0},
        "qbcc_tier_a": 60,
        "qbcc_category": {"1": 15, "2": 20},
        "geography": 10,
        "company": 5,
        "contact": {"deliverable_email": 20, "phone": 15, "website": 5, "none": 0},
        "cap": 100,
    },
    "qualification": {
        "full_state": "QLD",
        "partial_state": "NSW",
        "postcode_min": "2450",
        "postcode_max": "2490",
        "gst_age_min_months": 12,
        "gst_age_max_months_exclusive": 60,
        "tier_b_entity_classes": ["company", "trust"],
        "tier_b_confidences": ["high", "medium"],
        "qbcc_categories": ["1", "2"],
        "qbcc_events": ["icp_backlog", "new", "category_changed"],
    },
    "queue": {"expiry_weeks": 8, "weekly_limit": 60, "oldest_reserve": 10},
}


class PolicyLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in result:
            raise ValueError("QUALIFICATION_DUPLICATE_OR_INVALID_KEY")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


PolicyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def _matches(actual, expected) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_matches(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _matches(a, e) for a, e in zip(actual, expected, strict=True)
        )
    return actual == expected


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(value)
    return value


@dataclass(frozen=True)
class QualificationPolicy:
    rule_version: str
    scoring: Mapping[str, Any]
    qualification: Mapping[str, Any]
    queue: Mapping[str, int]


def load_policy(path: Path | None = None) -> QualificationPolicy:
    data = yaml.load(
        (path or ROOT / "config/qualification.yaml").read_text(encoding="utf-8"), Loader=PolicyLoader
    )
    if not _matches(data, APPROVED):
        raise ValueError("QUALIFICATION_POLICY_NOT_APPROVED_V4")
    return QualificationPolicy(
        data["rule_version"], _freeze(data["scoring"]), _freeze(data["qualification"]), _freeze(data["queue"])
    )


@lru_cache(maxsize=1)
def current_policy() -> QualificationPolicy:
    return load_policy()


def policy_metadata() -> dict[str, str]:
    version = current_policy().rule_version
    return {"qualification_rule_version": version, "scoring_rule_version": version}
