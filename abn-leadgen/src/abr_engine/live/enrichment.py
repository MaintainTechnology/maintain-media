"""Reviewed own-website collection using the bounded, IP-pinned real crawler.

This free manual-discovery path needs no paid search provider. It creates genuine
contact evidence, never invented deliverability, consent or DNCR clearance.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid5

import phonenumbers
from bs4 import BeautifulSoup
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abr_engine import __version__
from abr_engine.compliance.keys import load_keys
from abr_engine.compliance.policy import website_collection_policy
from abr_engine.control.service import DomainError, Service, digest
from abr_engine.db import lock, transaction
from abr_engine.enrich.crawl import PinnedTransport, SafeCrawler, resolve_public, validate_url
from abr_engine.enrich.endpoints import normalize_phone, positioning_excerpt
from abr_engine.enrich.identity import registrable_domain
from abr_engine.ingest.qbcc_review import _configured
from abr_engine.pipeline import process_lock, safe_root
from abr_engine.qualify.queue import score


class WebsiteCollection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: UUID
    lead_id: UUID
    identity_id: UUID
    website_url: str = Field(min_length=10, max_length=300)
    terms_permit: bool = Field(strict=True)
    terms_evidence_ref: str = Field(min_length=1, max_length=500)
    terms_reviewed_at: datetime

    @model_validator(mode="after")
    def reviewed_root(self):
        url = urlsplit(validate_url(self.website_url))
        if url.scheme != "https" or url.path != "/" or url.query or url.fragment:
            raise ValueError("An HTTPS website root without query parameters is required")
        if (
            not self.terms_permit
            or not self.terms_evidence_ref.strip()
            or self.terms_reviewed_at.tzinfo is None
        ):
            raise ValueError("An explicit dated site-terms review permitting collection is required")
        return self


def _purpose(conn, settings, now):
    policy = website_collection_policy(conn, settings, now)
    if policy["reason_codes"]:
        raise DomainError(policy["reason_codes"][0], 403)
    return policy


def _admit(conn, service, request, *, initial=False, job_id=None):
    service.personal_data_access(conn)
    now = service.now(conn)
    _purpose(conn, service.settings, now)
    if job_id is not None:
        job = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (job_id,)).fetchone()
        if (not job or job["state"] != "running" or job["started_at"] <= now - timedelta(hours=24)
                or "request_encrypted" not in job["manifest"]):
            raise DomainError("WEBSITE_REQUEST_EXPIRED", 409)
    lead = service.lead(conn, request.lead_id)
    if lead["lifecycle"] != "active" or service.restricted(conn, lead["group_id"]):
        raise DomainError("LEAD_INACTIVE_OR_SUPPRESSED", 409)
    if lead["tier"] not in ("A", "B"):
        raise DomainError("TIER_INELIGIBLE", 409)
    from abr_engine.qualify.abr import target_geography

    if not target_geography(lead["state"], lead["postcode"]):
        raise DomainError("GEOGRAPHY_OUTSIDE_OR_UNKNOWN", 409)
    if not now - timedelta(days=30) < request.terms_reviewed_at <= now:
        raise DomainError("SITE_TERMS_REVIEW_NOT_CURRENT", 409)
    domain = registrable_domain(request.website_url)
    identity = conn.execute(
        "SELECT * FROM domain_identity WHERE lead_id=%s AND registrable_domain=%s ORDER BY assessment_seq DESC LIMIT 1",
        (request.lead_id, domain),
    ).fetchone()
    if (
        not identity
        or identity["identity_id"] != request.identity_id
        or identity["assessment"] != "approved"
        or not identity["assessed_at"] <= now < identity["expires_at"]
    ):
        raise DomainError("IDENTITY_NOT_CURRENT", 409)
    if lead["source"] == "qbcc":
        licence = conn.execute(
            "SELECT * FROM licence_review WHERE lead_id=%s ORDER BY reviewed_at DESC,import_seq DESC LIMIT 1",
            (request.lead_id,),
        ).fetchone()
        if (
            not licence
            or licence["status"] != "active"
            or not licence["identity_match"]
            or not licence["reviewed_at"] <= now < licence["reviewed_at"] + timedelta(days=30)
        ):
            raise DomainError("CURRENT_LICENCE_REVIEW_REQUIRED", 409)
    candidate = conn.execute(
        "SELECT * FROM candidate_queue WHERE lead_id=%s AND state IN ('pending_enrichment','needs_review') AND first_qualified_at>%s ORDER BY first_qualified_at,candidate_id LIMIT 1",
        (request.lead_id, now - timedelta(weeks=8)),
    ).fetchone()
    if not candidate or candidate["first_qualified_at"] + timedelta(weeks=8) <= now:
        raise DomainError("ELIGIBLE_CANDIDATE_REQUIRED", 409)
    if initial:
        attempted = conn.execute(
            "SELECT max(q.last_attempt_at) latest FROM candidate_queue q JOIN lead_entity l USING(lead_id) WHERE l.group_id=ANY(%s)",
            (service.group_family(conn, lead["group_id"]),),
        ).fetchone()
        if attempted and attempted["latest"] and attempted["latest"] + timedelta(days=90) > now:
            raise DomainError("ENRICHMENT_COOLDOWN", 409)
    return lead, candidate


def _endpoints(page, allowed_channels):
    soup = BeautifulSoup(page.html, "html.parser")
    for node in soup(["script", "style", "template", "noscript"]):
        node.decompose()
    phones = set()
    text = soup.get_text(" ", strip=True)
    # Do not reinterpret labelled business identifiers as telephone numbers.
    text = re.sub(r"\b(?:ABN|ACN|QBCC(?:\s+licen[cs]e)?|licen[cs]e(?:\s+(?:number|no\.?))?)"
                  r"\s*[:#]?\s*\d[\d -]{4,30}", " ", text, flags=re.IGNORECASE)
    for match in phonenumbers.PhoneNumberMatcher(text, "AU", max_tries=1000):
        if not match.number.extension and text[match.end:match.end+1] != "@":
            phones.add(match.raw_string)
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if href.lower().startswith("tel:"):
            phones.add(unquote(href[4:]))
    result = []
    for phone in sorted(phones):
        try:
            value = normalize_phone(phone)
            kind = phonenumbers.number_type(phonenumbers.parse(value, "AU"))
            if kind not in (phonenumbers.PhoneNumberType.MOBILE, phonenumbers.PhoneNumberType.FIXED_LINE):
                continue
            channel = "mobile" if kind == phonenumbers.PhoneNumberType.MOBILE else "landline"
            if channel in allowed_channels:
                result.append((channel, value))
        except ValueError:
            continue
    return result


def collect_website(settings, data: dict, actor: str, *, transport=None, resolver=None, sleep=None, job_id=None) -> dict:
    request = WebsiteCollection.model_validate(data)
    _configured(settings)
    if not actor.strip():
        raise DomainError("ACTOR_REQUIRED", 403)
    with transaction(settings) as conn:
        _purpose(conn, settings, Service.now(conn))
    service = Service(settings, load_keys(settings))
    body_digest = digest({**request.model_dump(mode="json"), "actor": actor})
    root = safe_root(settings)
    with process_lock(root / f"website-collection-{request.lead_id}.lock"):
        with transaction(settings) as conn:
            service.personal_data_access(conn)
            prior = conn.execute(
                "SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (request.request_id,)
            ).fetchone()
            if prior:
                if (
                    prior["config_digest"] != body_digest
                    or prior["manifest"].get("kind") != "website_collection"
                ):
                    raise DomainError("IDEMPOTENCY_CONFLICT", 409)
                if prior["manifest"].get("receipt"):
                    return {**prior["manifest"]["receipt"], "replayed": True}
                raise DomainError("INTERRUPTED_COLLECTION_REQUIRES_NEW_REQUEST", 409)
            _admit(conn, service, request, initial=True, job_id=job_id)
            conn.execute(
                "INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state,manifest) VALUES(%s,%s,%s,%s,'running',%s)",
                (
                    request.request_id,
                    settings.mode,
                    __version__,
                    body_digest,
                    Jsonb({"kind": "website_collection", "lead_id": str(request.lead_id)}),
                ),
            )

        class CheckedTransport:
            def __init__(self):
                self.base = transport or PinnedTransport()

            def request(self, *args, **kwargs):
                with transaction(settings) as conn:
                    _admit(conn, service, request, job_id=job_id)
                response = self.base.request(*args, **kwargs)
                with transaction(settings) as conn:
                    _admit(conn, service, request, job_id=job_id)
                return response

        def checked_resolver(*args, **kwargs):
            with transaction(settings) as conn:
                _admit(conn, service, request, job_id=job_id)
            addresses = (resolver or resolve_public)(*args, **kwargs)
            with transaction(settings) as conn:
                _admit(conn, service, request, job_id=job_id)
            return addresses

        options = {"resolver": checked_resolver}
        if sleep is not None:
            options["sleep"] = sleep
        crawler = SafeCrawler(CheckedTransport(), **options)
        forbidden = re.compile(
            r"(?:no|prohibit(?:ed)?|do not|not permit)[^.\n]{0,80}(?:scrap(?:e|ing)|automated (?:access|collection)|harvest)",
            re.IGNORECASE,
        )
        try:
            crawled = crawler.crawl(
                request.website_url,
                terms_permit=lambda page: (
                    not bool(forbidden.search(BeautifulSoup(page.html, "html.parser").get_text(" ")))
                ),
            )
            if crawled.reason not in ("complete", "PAGE_BUDGET"):
                raise DomainError("WEBSITE_COLLECTION_HELD", 409, {"reason": crawled.reason})
            contacts: list[str] = []
            seen: set[tuple[str, str]] = set()
            captured_at = None
            with transaction(settings) as conn:
                lead, candidate = _admit(conn, service, request, job_id=job_id)
                captured_at = service.now(conn)
                channels = _purpose(conn, settings, captured_at)["allowed_channels"]
                for page in crawled.pages:
                    for channel, value in _endpoints(page, channels):
                        if (channel, value) in seen or len(contacts) >= 10:
                            continue
                        seen.add((channel, value))
                        existing = any(
                            conn.execute(
                                "SELECT 1 FROM contact_record WHERE lead_id=%s AND channel=%s AND endpoint_token=%s AND token_key_version=%s",
                                (request.lead_id, channel, token, version),
                            ).fetchone()
                            for version, token in service.keys.matches(channel, value)
                        )
                        if existing:
                            continue
                        try:
                            with conn.transaction():
                                contact = service.add_contact(
                                    conn,
                                    lead_id=request.lead_id,
                                    channel=channel,
                                    value=value,
                                    identity_id=request.identity_id,
                                    source_url=page.url,
                                    excerpt=positioning_excerpt(page.html, page.url).text,
                                    actor=actor,
                                    capture={
                                        "html": page.html,
                                        "captured_at": captured_at,
                                        "collector_version": "reviewed-pinned-website-v1",
                                        "robots_result": page.robots_decision,
                                        "terms_scope": request.terms_evidence_ref,
                                        "method": "reviewer_supplied_own_domain",
                                    },
                                )
                                contacts.append(str(contact["contact_id"]))
                        except DomainError as exc:
                            if exc.code != "SUPPRESSED_ENDPOINT":
                                raise
                # Evidence exists; contact permission still requires its own review.
                final_score = score(
                    source=lead["source"],
                    tier=lead["tier"],
                    geography=True,
                    category=lead["fields"].get("financial_category"),
                    company=lead["fields"].get("entity_class") == "company",
                    phone=any(channel in ("mobile", "landline") for channel, _ in seen),
                    website=bool(crawled.pages),
                )
                conn.execute(
                    "UPDATE lead_entity SET score=%s WHERE lead_id=%s", (final_score, request.lead_id)
                )
                conn.execute(
                    "UPDATE candidate_queue SET state='needs_review',score=%s,last_attempt_at=%s,attempt_count=attempt_count+1,stage_data=stage_data||%s WHERE candidate_id=%s",
                    (
                        final_score,
                        captured_at,
                        Jsonb(
                            {
                                "enrichment_complete": True,
                                "enrichment_method": "reviewed_website",
                                "enrichment_run_id": str(request.request_id),
                                "permission_review_required": True,
                            }
                        ),
                        candidate["candidate_id"],
                    ),
                )
                receipt = {
                    "run_id": str(request.request_id),
                    "status": "complete" if contacts else "exhausted",
                    "contacts_created": len(contacts),
                    "contact_ids": contacts,
                    "pages_fetched": len(crawled.pages),
                    "requests": crawled.requests,
                    "reason_codes": ["CONTACT_PERMISSION_REVIEW_REQUIRED"]
                    if contacts
                    else ["NO_NEW_USABLE_ENDPOINT"],
                    "export_eligible": False,
                    "replayed": False,
                }
                conn.execute(
                    "UPDATE pipeline_run SET state='complete',finished_at=clock_timestamp(),manifest=manifest||%s WHERE run_id=%s",
                    (Jsonb({"receipt": receipt}), request.request_id),
                )
                service.audit(
                    conn,
                    actor,
                    "reviewed_website_collected",
                    request.request_id,
                    {"lead_id": request.lead_id, "contacts_created": len(contacts)},
                )
                return receipt
        except Exception as exc:
            reason = exc.code if isinstance(exc, DomainError) else "WEBSITE_COLLECTION_FAILED"
            if reason == "WEBSITE_COLLECTION_HELD":
                with transaction(settings) as conn:
                    _, candidate = _admit(conn, service, request, job_id=job_id)
                    conn.execute(
                        "UPDATE candidate_queue SET state='needs_review',last_attempt_at=clock_timestamp(),attempt_count=attempt_count+1,stage_data=stage_data||%s WHERE candidate_id=%s",
                        (
                            Jsonb(
                                {
                                    "enrichment_complete": True,
                                    "enrichment_reason": crawled.reason,
                                    "enrichment_run_id": str(request.request_id),
                                }
                            ),
                            candidate["candidate_id"],
                        ),
                    )
            with transaction(settings) as conn:
                conn.execute(
                    "UPDATE pipeline_run SET state='held',finished_at=clock_timestamp(),manifest=manifest||%s WHERE run_id=%s",
                    (Jsonb({"reason_codes": [reason]}), request.request_id),
                )
            raise


def submit_website_collection(settings, data: dict, actor: str) -> dict:
    request = WebsiteCollection.model_validate(data)
    _configured(settings)
    with transaction(settings) as conn:
        _purpose(conn, settings, Service.now(conn))
    service = Service(settings, load_keys(settings))
    body_digest = digest({**request.model_dump(mode="json"), "actor": actor})
    with transaction(settings) as conn:
        service.personal_data_access(conn)
        lock(conn, "website-job:" + str(request.request_id))
        prior = conn.execute(
            "SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (request.request_id,)
        ).fetchone()
        if prior:
            if (
                prior["config_digest"] != body_digest
                or prior["manifest"].get("kind") != "website_collection_job"
            ):
                raise DomainError("IDEMPOTENCY_CONFLICT", 409)
            return _website_receipt(prior)
        if not actor.strip():
            raise DomainError("ACTOR_REQUIRED", 403)
        _admit(conn, service, request, initial=True)
        inner = {
            **request.model_dump(mode="json"),
            "request_id": str(uuid5(request.request_id, "website-crawl")),
        }
        conn.execute(
            "INSERT INTO pipeline_run(run_id,mode,code_version,config_digest,state,manifest) VALUES(%s,%s,%s,%s,'running',%s)",
            (
                request.request_id,
                settings.mode,
                __version__,
                body_digest,
                Jsonb(
                    {
                        "kind": "website_collection_job",
                        "phase": "queued",
                        "actor": actor,
                        "request_encrypted": service.keys.encrypt(json.dumps(inner)),
                        "lead_id": str(request.lead_id),
                    }
                ),
            ),
        )
        row = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (request.request_id,)).fetchone()
        return _website_receipt(row)


def _website_receipt(row):
    return {
        "job_id": str(row["run_id"]),
        "run_id": str(row["run_id"]),
        "state": row["manifest"]["phase"],
        "phase": row["manifest"]["phase"],
        "source": "qbcc",
        "result": row["manifest"].get("receipt"),
        "reason_codes": row["manifest"].get("reason_codes", []),
    }


def get_website_collection(settings, job_id) -> dict:
    with transaction(settings) as conn:
        row = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s", (UUID(str(job_id)),)).fetchone()
        if not row or row["mode"] != settings.mode or row["manifest"].get("kind") != "website_collection_job":
            raise DomainError("NOT_FOUND", 404)
        return _website_receipt(row)


def execute_website_collection(settings, job_id, **transport_options) -> dict:
    job_id = UUID(str(job_id))
    current = get_website_collection(settings, job_id)
    if current["state"] in ("complete", "held", "failed"):
        return current
    with transaction(settings) as conn:
        reasons = website_collection_policy(conn, settings, Service.now(conn))["reason_codes"]
        if reasons:
            conn.execute(
                "UPDATE pipeline_run SET state='held',finished_at=clock_timestamp(),manifest=(manifest-'request_encrypted')||%s WHERE run_id=%s",
                (Jsonb({"phase": "held", "reason_codes": reasons}), job_id),
            )
            return {**current, "state": "held", "phase": "held", "reason_codes": reasons}
    service = Service(settings, load_keys(settings))
    with process_lock(safe_root(settings) / f"website-job-{job_id}.lock"):
        with transaction(settings) as conn:
            service.personal_data_access(conn)
            row = conn.execute("SELECT * FROM pipeline_run WHERE run_id=%s FOR UPDATE", (job_id,)).fetchone()
            if not row:
                raise DomainError("NOT_FOUND", 404)
            if row["manifest"]["phase"] in ("complete", "held", "failed"):
                return _website_receipt(row)
            if row["started_at"] <= service.now(conn) - timedelta(hours=24):
                conn.execute(
                    "UPDATE pipeline_run SET state='held',finished_at=clock_timestamp(),manifest=(manifest-'request_encrypted')||%s WHERE run_id=%s",
                    (Jsonb({"phase": "held", "reason_codes": ["WEBSITE_REQUEST_EXPIRED"]}), job_id),
                )
                return {
                    **current,
                    "state": "held",
                    "phase": "held",
                    "reason_codes": ["WEBSITE_REQUEST_EXPIRED"],
                }
            data = json.loads(service.keys.decrypt(row["manifest"]["request_encrypted"]))
            actor = row["manifest"]["actor"]
            conn.execute(
                "UPDATE pipeline_run SET manifest=manifest||%s,heartbeat_at=clock_timestamp() WHERE run_id=%s",
                (Jsonb({"phase": "running"}), job_id),
            )
        try:
            receipt = collect_website(settings, data, actor, job_id=job_id, **transport_options)
            phase, reasons = "complete", receipt["reason_codes"]
        except (DomainError, ValueError) as exc:
            receipt, phase = None, "held"
            reasons = [exc.code if isinstance(exc, DomainError) else "WEBSITE_COLLECTION_FAILED"]
        except Exception:  # noqa: BLE001 - serialize a safe failure instead of logging private transport errors.
            receipt, phase, reasons = None, "failed", ["WEBSITE_COLLECTION_FAILED"]
        with transaction(settings) as conn:
            conn.execute(
                "UPDATE pipeline_run SET state=%s,finished_at=clock_timestamp(),manifest=(manifest-'request_encrypted')||%s WHERE run_id=%s",
                (
                    "complete" if phase == "complete" else "failed" if phase == "failed" else "held",
                    Jsonb({"phase": phase, "receipt": receipt, "reason_codes": reasons}),
                    job_id,
                ),
            )
        return get_website_collection(settings, job_id)


def execute_pending_websites(settings, limit=1) -> list:
    if not 1 <= limit <= 10:
        raise DomainError("INVALID_JOB_LIMIT")
    with transaction(settings) as conn:
        jobs = conn.execute(
            "SELECT run_id FROM pipeline_run WHERE mode=%s AND state='running' AND manifest->>'kind'='website_collection_job' AND (manifest->>'phase'='queued' OR heartbeat_at<clock_timestamp()-interval '1 hour') ORDER BY started_at,run_id LIMIT %s",
            (settings.mode, limit),
        ).fetchall()
    return [execute_website_collection(settings, row["run_id"]) for row in jobs]
