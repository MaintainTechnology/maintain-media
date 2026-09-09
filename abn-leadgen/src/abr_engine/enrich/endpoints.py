"""Deterministic endpoint candidates. No function in this module confers permission."""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import phonenumbers
from bs4 import BeautifulSoup


def normalize_email(value: str) -> str:
    result = value.strip().lower()
    if len(result) > 254 or not re.fullmatch(
        r"[^\s@<>\x00-\x1f]+@[^\s@<>\x00-\x1f]+\.[^\s@<>\x00-\x1f]+", result
    ):
        raise ValueError("EMAIL_INVALID")
    local, domain = result.rsplit("@", 1)
    if (
        len(local) > 64
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local)
        or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in domain.split(".")
        )
    ):
        raise ValueError("EMAIL_INVALID")
    return result


def normalize_phone(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"\+?[0-9() .-]+", value):
        raise ValueError("PHONE_INVALID")
    if value.startswith("+") and not value.startswith("+61"):
        raise ValueError("PHONE_NON_AU")
    # National trunk numbers and full-length 1300/1800 forms are unambiguous.
    if not value.startswith("+") and not re.fullmatch(r"(?:0\d{9}|1[38]00\d{6})", re.sub(r"\D", "", value)):
        raise ValueError("PHONE_AMBIGUOUS")
    try:
        parsed = phonenumbers.parse(value, "AU")
    except phonenumbers.NumberParseException as exc:
        raise ValueError("PHONE_INVALID") from exc
    if (
        parsed.extension
        or parsed.country_code != 61
        or not phonenumbers.is_valid_number(parsed)
        or phonenumbers.region_code_for_number(parsed) != "AU"
    ):
        raise ValueError("PHONE_INVALID")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


@dataclass(frozen=True)
class EmailCandidate:
    email: str
    reviewed_named_role: bool = False
    permitted_generic_role: bool = False
    provenance_id: str = ""


def select_email(candidates: list[EmailCandidate]) -> EmailCandidate | None:
    eligible = [
        EmailCandidate(
            normalize_email(c.email), c.reviewed_named_role, c.permitted_generic_role, c.provenance_id
        )
        for c in candidates
        if c.provenance_id and (c.reviewed_named_role or c.permitted_generic_role)
    ]
    return min(eligible, key=lambda c: (not c.reviewed_named_role, c.email)) if eligible else None


@dataclass(frozen=True)
class PositioningExcerpt:
    source_url: str
    text: str
    method: str = "title_meta_heading"


def positioning_excerpt(html: str, source_url: str) -> PositioningExcerpt:
    if urlsplit(source_url).scheme not in {"http", "https"}:
        raise ValueError("SOURCE_URL_INVALID")
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "template", "noscript"]):
        node.decompose()
    parts = []
    if soup.title:
        parts.append(soup.title.get_text(" ", strip=True))
    meta = soup.find("meta", attrs={"name": re.compile("^description$", re.IGNORECASE)})
    if meta and meta.get("content"):
        parts.append(str(meta["content"]))
    parts.extend(node.get_text(" ", strip=True) for node in soup.find_all(["h1", "h2"], limit=4))
    text = " | ".join(
        dict.fromkeys(" ".join(re.sub(r"[\x00-\x1f\x7f]", " ", p).split()) for p in parts if p)
    )[:400]
    return PositioningExcerpt(source_url, text)
