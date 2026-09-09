"""Own-domain evidence primitives; search rank never grants identity or consent."""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib.resources import files
from urllib.parse import urlsplit

import tldextract
from bs4 import BeautifulSoup

# The exact package is locked; disable both network refresh and mutable user cache.
_PSL = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, include_psl_private_domains=True)
PSL_SHA256 = hashlib.sha256(files("tldextract").joinpath(".tld_set_snapshot").read_bytes()).hexdigest()


def registrable_domain(value: str) -> str:
    hostname = urlsplit(value).hostname if "://" in value else value
    if not hostname:
        raise ValueError("DOMAIN_INVALID")
    hostname = hostname.rstrip(".").encode("idna").decode("ascii").lower()
    result = _PSL(hostname)
    if not result.domain or not result.suffix:
        raise ValueError("DOMAIN_NO_PUBLIC_SUFFIX")
    return result.top_domain_under_public_suffix


def domain_excluded(url: str, blocked_domains: tuple[str, ...]) -> bool:
    return registrable_domain(url) in {registrable_domain(item) for item in blocked_domains}


def discovery_queries(
    name: str, state: str, postcode: str, business_names: tuple[str, ...] = ()
) -> tuple[str, ...]:
    if state not in {"QLD", "NSW"} or not re.fullmatch(r"\d{4}", postcode):
        raise ValueError("GEOGRAPHY_UNKNOWN")
    names = [" ".join(name.split())]
    names.extend(sorted({" ".join(n.split()) for n in business_names if n.strip()})[:1])
    queries = [f'"{n}" {state} {postcode}' for n in names if n]
    if names[0]:
        queries.append(f'"{names[0]}" {state} {postcode} official website')
    return tuple(dict.fromkeys(queries))[:3]


def valid_abn(value: str) -> bool:
    if not re.fullmatch(r"\d{11}", value, flags=re.ASCII):
        return False
    digits = [int(c) for c in value]
    digits[0] -= 1
    return sum(d * w for d, w in zip(digits, (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19))) % 89 == 0


@dataclass(frozen=True)
class IdentityEvidence:
    group_id: str
    domain: str
    page_url: str
    html: str
    captured_at: datetime
    source_abn: str | None = None
    source_licence: str | None = None
    reviewer_id: str | None = None
    reviewer_approved: bool = False
    matching_attributes: tuple[str, ...] = ()
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class IdentityDecision:
    group_id: str
    domain: str
    approved: bool
    method: str
    assessed_at: datetime
    expires_at: datetime


def assess_identity(evidence: IdentityEvidence, *, now: datetime) -> IdentityDecision:
    if now.tzinfo is None or evidence.captured_at.tzinfo is None or evidence.captured_at > now:
        raise ValueError("IDENTITY_TIME_INVALID")
    domain = registrable_domain(evidence.page_url)
    if domain != registrable_domain(evidence.domain):
        raise ValueError("IDENTITY_DOMAIN_MISMATCH")
    soup = BeautifulSoup(evidence.html, "html.parser")
    for tag in soup(["script", "style", "template", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    abns = {
        re.sub(r"\D", "", m) for m in re.findall(r"(?<!\d)\d{2}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{3}(?!\d)", text)
    }
    method = "ambiguous"
    if evidence.source_abn and valid_abn(evidence.source_abn) and evidence.source_abn in abns:
        method = "exact_abn"
    elif (
        evidence.source_licence
        and re.fullmatch(r"[0-9]{1,12}", evidence.source_licence)
        and re.search(
            r"\b(?:QBCC|licen[cs]e)\s*(?:number|no\.?|#)?\s*[:#-]?\s*"
            + re.escape(evidence.source_licence)
            + r"(?!\d)",
            text,
            re.IGNORECASE,
        )
    ):
        method = "exact_licence"
    elif (
        evidence.reviewer_approved
        and evidence.reviewer_id
        and len(set(evidence.references)) >= 2
        and "name" in evidence.matching_attributes
        and {"full_address", "phone"}.intersection(evidence.matching_attributes)
    ):
        method = "reviewed_corroboration"
    expiry = evidence.captured_at + timedelta(days=90)
    return IdentityDecision(
        evidence.group_id, domain, method != "ambiguous" and now < expiry, method, now, expiry
    )


def current_identity(
    decisions: list[tuple[int, IdentityDecision]], *, group_id: str, domain: str, now: datetime
) -> bool:
    matching = [
        (seq, d) for seq, d in decisions if d.group_id == group_id and d.domain == registrable_domain(domain)
    ]
    if not matching:
        return False
    decision = max(matching, key=lambda item: item[0])[1]
    return decision.approved and decision.assessed_at <= now < decision.expires_at
