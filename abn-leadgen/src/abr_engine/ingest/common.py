"""Small, strict source primitives shared by the analytical adapters."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


class SourceError(ValueError):
    """A held source, identified by a non-personal reason code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def normalize_abn(value: str, *, optional: bool = False) -> str | None:
    digits = re.sub(r"\s", "", value)
    if not digits and optional:
        return None
    if not re.fullmatch(r"[0-9]{11}", digits):
        raise SourceError("INVALID_ABN")
    numbers = [int(n) for n in digits]
    numbers[0] -= 1
    if sum(a * b for a, b in zip(numbers, (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19), strict=True)) % 89:
        raise SourceError("INVALID_ABN")
    return digits


def canonical_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).upper().split())


def ordered_names(names: list[str]) -> list[str]:
    """Deduplicate canonical names; preserve deterministic literal evidence."""
    result: dict[str, str] = {}
    for name in sorted(names, key=lambda n: (canonical_name(n), n)):
        if canonical_name(name):
            result.setdefault(canonical_name(name), name)
    return list(result.values())
