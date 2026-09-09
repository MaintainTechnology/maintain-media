"""Transactional domain authority. All mutable eligibility paths use common control locks.

The small weekly workload deliberately uses a coarse advisory lock before group/endpoint
locks. This makes merge, erasure, suppression and action order explicit and deadlock-safe.
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from abr_engine.compliance.keys import KeyStore
from abr_engine.compliance.policy import gate_reasons
from abr_engine.config import Settings
from abr_engine.db import lock
from abr_engine.enrich.endpoints import normalize_email, normalize_phone


class DomainError(Exception):
    def __init__(self, code: str, status: int = 422, details: dict | None = None):
        self.code, self.status, self.details = code, status, details or {}
        super().__init__(code)


def json_safe(value):
    return json.loads(json.dumps(value, default=str))


def digest(value) -> str:
    return hashlib.sha256(json.dumps(json_safe(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Service:
    def __init__(self, settings: Settings, keys: KeyStore):
        self.settings, self.keys = settings, keys

    @staticmethod
    def now(conn) -> datetime:
        return conn.execute("SELECT clock_timestamp() AS t").fetchone()["t"]

    def authority(self, conn, lead_id=None):
        lock(conn, "control-authority")
        self.keys.validate_dependencies(conn)
        if lead_id:
            lead = self.lead(conn, lead_id)
            lock(conn, "group:" + str(lead["group_id"]))
            endpoints = conn.execute("SELECT endpoint_token FROM contact_record WHERE lead_id=%s", (lead_id,)).fetchall()
            lock(conn, *("endpoint:" + r["endpoint_token"] for r in endpoints))

    def personal_data_access(self, conn):
        self.authority(conn)
        flags = conn.execute("SELECT name,value FROM system_state WHERE name IN ('restore_quarantine','key_compromised')").fetchall()
        if self.keys.compromised or any(row["value"] for row in flags):
            raise DomainError("AUTHORITY_QUARANTINED", 503)

    @staticmethod
    def audit(conn, actor: str, action: str, object_id, metadata=None):
        conn.execute("INSERT INTO audit_event(event_id,actor_id,action,object_type,object_id,metadata) "
                     "VALUES(%s,%s,%s,'control',%s,%s)",
                     (uuid4(), actor, action, str(object_id), Jsonb(json_safe(metadata or {}))))

    @staticmethod
    def lead(conn, lead_id):
        row = conn.execute("SELECT * FROM lead_entity WHERE lead_id=%s", (lead_id,)).fetchone()
        if not row:
            raise DomainError("NOT_FOUND", 404)
        return row

    @staticmethod
    def contact(conn, contact_id):
        row = conn.execute("SELECT * FROM contact_record WHERE contact_id=%s", (contact_id,)).fetchone()
        if not row:
            raise DomainError("NOT_FOUND", 404)
        return row

    def tokens(self, channel, value):
        normalized = normalize_email(value) if channel == "email" else normalize_phone(value)
        return normalized, self.keys.matches(channel, normalized)

    @staticmethod
    def canonical_group(conn, group_id):
        seen = set()
        while group_id not in seen:
            seen.add(group_id)
            row = conn.execute("SELECT merged_into_group_id FROM business_group WHERE group_id=%s", (group_id,)).fetchone()
            if not row or not row["merged_into_group_id"]:
                return group_id
            group_id = row["merged_into_group_id"]
        raise DomainError("GROUP_IDENTITY_CYCLE", 503)

    def group_family(self, conn, group_id):
        canonical = self.canonical_group(conn, group_id)
        return [r["group_id"] for r in conn.execute("WITH RECURSIVE family AS (SELECT group_id FROM business_group WHERE group_id=%s "
                "UNION SELECT g.group_id FROM business_group g JOIN family f ON g.merged_into_group_id=f.group_id) SELECT group_id FROM family", (canonical,)).fetchall()] or [canonical]

    def restricted(self, conn, group_id, tokens=()) -> list[str]:
        reasons: list[str] = []
        rows = conn.execute("SELECT * FROM suppression_event e WHERE action='add' AND "
                            "NOT EXISTS(SELECT 1 FROM suppression_event r WHERE r.resolves_event_id=e.event_id) "
                            "AND group_id=ANY(%s)", (self.group_family(conn, group_id),)).fetchall()
        reasons.extend("SUPPRESSED_" + row["reason"].upper() for row in rows)
        for version, token in tokens:
            rows = conn.execute("SELECT reason FROM suppression_event WHERE action='add' AND endpoint_token=%s "
                                "AND key_version=%s", (token, version)).fetchall()
            reasons.extend("SUPPRESSED_" + row["reason"].upper() for row in rows)
        return sorted(set(reasons))

    @staticmethod
    def invalidate(conn, lead_id):
        conn.execute("UPDATE action_intent SET state='cancelled' WHERE lead_id=%s AND state='pending'", (lead_id,))
        conn.execute("UPDATE crm_outbox SET state='blocked' WHERE lead_id=%s AND state IN ('pending','retry','inflight')", (lead_id,))

    def create_lead(self, conn, *, name: str, source: str, alias: str, abn: str | None = None,
                    state="QLD", postcode="4000", tier="A", signal="qbcc_backlog", score=90,
                    event_key: str | None = None, fields: dict | None = None) -> dict:
        from abr_engine.qualify.policy import policy_metadata

        fields = {**(fields or {}), **policy_metadata()}
        self.authority(conn)
        aliases = [("qbcc" if source == "qbcc" else "abn", alias)]
        if abn and ("abn", abn) not in aliases:
            aliases.append(("abn", abn))
        groups = set()
        for kind, value in aliases:
            for version, token in self.keys.matches(kind, value):
                row = conn.execute("SELECT group_id FROM suppression_alias WHERE alias_type=%s AND key_version=%s "
                                   "AND alias_token=%s", (kind, version, token)).fetchone()
                if row:
                    groups.add(self.canonical_group(conn, row["group_id"]))
        if len(groups) > 1:
            raise DomainError("IDENTITY_MERGE_REVIEW_REQUIRED", 409)
        group_id = next(iter(groups), uuid4())
        if self.restricted(conn, group_id):
            raise DomainError("SUPPRESSED_SOURCE_IDENTITY", 409)
        conn.execute("INSERT INTO business_group(group_id) VALUES(%s) ON CONFLICT DO NOTHING", (group_id,))
        prior = conn.execute("SELECT * FROM lead_entity WHERE group_id=%s", (group_id,)).fetchone()
        lead_id = prior["lead_id"] if prior else uuid4()
        if not prior:
            conn.execute("INSERT INTO lead_entity(lead_id,group_id,display_name,source,state,postcode,tier,signal,score,fields) "
                         "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                         (lead_id, group_id, name, source, state, postcode, tier, signal, score, Jsonb(fields or {})))
        for kind, value in aliases:
            token = self.keys.token(kind, value)
            conn.execute("INSERT INTO suppression_alias(alias_type,key_version,alias_token,group_id) VALUES(%s,%s,%s,%s) "
                         "ON CONFLICT DO NOTHING", (kind, self.keys.active_version, token, group_id))
            conn.execute("INSERT INTO lead_source_link(link_id,group_id,source_type,encrypted_identifier,alias_token,key_version,evidence_ref) "
                         "VALUES(%s,%s,%s,%s,%s,%s,'source-manifest') ON CONFLICT DO NOTHING",
                         (uuid4(), group_id, kind, self.keys.encrypt(value), token, self.keys.active_version))
        now = self.now(conn)
        conn.execute("INSERT INTO candidate_queue(candidate_id,lead_id,event_key,first_qualified_at,last_qualifying_at,state,tier,score) "
                     "VALUES(%s,%s,%s,%s,%s,'needs_review',%s,%s) ON CONFLICT DO NOTHING",
                     (uuid4(), lead_id, event_key or f"{source}:initial", now, now, tier, score))
        conn.execute("UPDATE candidate_queue SET stage_data=stage_data||%s WHERE lead_id=%s AND event_key=%s",
                     (Jsonb(policy_metadata()), lead_id, event_key or f"{source}:initial"))
        return self.lead(conn, lead_id)

    def identity(self, conn, data: dict, actor: str):
        lead_id = data["lead_id"]
        self.authority(conn, lead_id)
        lead = self.lead(conn, lead_id)
        if data["expected_revision"] != lead["revision"]:
            raise DomainError("REVISION_CONFLICT", 409)
        evidence = data["evidence_refs"]
        if data["assessment"] == "approved":
            if data["method"] == "exact_identifier":
                if not isinstance(evidence, dict) or not evidence.get("source_identifier") or not evidence.get("page_identifier"):
                    raise DomainError("IDENTITY_EVIDENCE_REQUIRED")
                if evidence["source_identifier"] != evidence["page_identifier"]:
                    raise DomainError("IDENTITY_MISMATCH")
                linked = conn.execute("SELECT encrypted_identifier,source_type FROM lead_source_link WHERE group_id=ANY(%s)", (self.group_family(conn, lead["group_id"]),)).fetchall()
                if evidence["source_identifier"] not in {self.keys.decrypt(r["encrypted_identifier"]) for r in linked}:
                    raise DomainError("IDENTIFIER_NOT_THIS_LEAD")
                if not all(evidence.get(k) for k in ("html", "page_url", "captured_at")):
                    raise DomainError("IDENTITY_CAPTURE_REQUIRED")
                from abr_engine.enrich.identity import IdentityEvidence, assess_identity
                matched = next(r for r in linked if self.keys.decrypt(r["encrypted_identifier"]) == evidence["source_identifier"])
                try:
                    decision = assess_identity(IdentityEvidence(
                        group_id=str(lead["group_id"]), domain=data["registrable_domain"], page_url=evidence["page_url"],
                        html=evidence["html"], captured_at=datetime.fromisoformat(str(evidence["captured_at"])),
                        source_abn=evidence["source_identifier"] if matched["source_type"] == "abn" else None,
                        source_licence=evidence["source_identifier"] if matched["source_type"] == "qbcc" else None,
                    ), now=self.now(conn))
                except (ValueError, TypeError):
                    raise DomainError("IDENTITY_CAPTURE_INVALID") from None
                if not decision.approved:
                    raise DomainError("IDENTIFIER_NOT_VISIBLE_ON_PAGE")
            elif data["method"] == "reviewed_attributes":
                references = evidence.get("references") if isinstance(evidence, dict) else None
                valid_refs = isinstance(references, (list, tuple)) and len(references) >= 2 and all(
                    isinstance(ref, str) and ref.strip() for ref in references) and len(set(references)) >= 2
                if not isinstance(evidence, dict) or evidence.get("name_match") is not True or not (
                        evidence.get("address_match") is True or evidence.get("phone_match") is True) or not valid_refs:
                    raise DomainError("TWO_ATTRIBUTES_REQUIRED")
            else:
                raise DomainError("UNSUPPORTED_IDENTITY_METHOD")
        from abr_engine.enrich.identity import registrable_domain
        domain = data["registrable_domain"].lower()
        if registrable_domain("https://" + domain) != domain:
            raise DomainError("REGISTRABLE_DOMAIN_REQUIRED")
        now = self.now(conn)
        identity_expiry = min(now + timedelta(days=90), decision.expires_at) if data["assessment"] == "approved" and data["method"] == "exact_identifier" else now + timedelta(days=90)
        # The evidence body can contain identifiers; encrypt, do not persist source aliases in plaintext.
        safe_evidence = {"encrypted": self.keys.encrypt(json.dumps(json_safe(evidence), sort_keys=True))}
        result = conn.execute("INSERT INTO domain_identity(identity_id,lead_id,registrable_domain,assessment,method,evidence,reason,actor_id,assessed_at,expires_at) "
                              "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                              (uuid4(), lead_id, domain, data["assessment"], data["method"], Jsonb(safe_evidence),
                               data["reason"], actor, now, identity_expiry)).fetchone()
        conn.execute("UPDATE lead_entity SET revision=revision+1 WHERE lead_id=%s", (lead_id,))
        self.invalidate(conn, lead_id)
        self.audit(conn, actor, "identity_assessed", result["identity_id"])
        return {k: result[k] for k in ("identity_id", "assessment_seq", "expires_at")}

    def add_contact(self, conn, *, lead_id, channel, value, identity_id, source_url, excerpt,
                    actor, capture: dict, verification="unverified", verified_at=None):
        self.authority(conn, lead_id)
        lead = self.lead(conn, lead_id)
        normalized, tokens = self.tokens(channel, value)
        if self.restricted(conn, lead["group_id"], tokens):
            raise DomainError("SUPPRESSED_ENDPOINT", 409)
        identity = conn.execute("SELECT * FROM domain_identity WHERE identity_id=%s AND lead_id=%s", (identity_id, lead_id)).fetchone()
        if not identity:
            raise DomainError("IDENTITY_NOT_THIS_LEAD")
        now = self.now(conn)
        if gate_reasons(conn, self.settings, "collection", now):
            raise DomainError("COLLECTION_GATE_CLOSED", 403)
        current = conn.execute("SELECT identity_id,assessment,expires_at FROM domain_identity WHERE lead_id=%s "
                               "AND registrable_domain=%s ORDER BY assessment_seq DESC LIMIT 1",
                               (lead_id, identity["registrable_domain"])).fetchone()
        if not current or current["identity_id"] != identity_id or current["assessment"] != "approved" or current["expires_at"] <= now:
            raise DomainError("IDENTITY_NOT_CURRENT")
        required = {"html", "captured_at", "collector_version", "robots_result", "terms_scope", "method"}
        if not required.issubset(capture) or not capture["html"] or capture["robots_result"] != "allowed" or not capture["terms_scope"]:
            raise DomainError("CAPTURE_EVIDENCE_REQUIRED")
        captured_at = capture["captured_at"]
        if isinstance(captured_at, str):
            captured_at = datetime.fromisoformat(captured_at)
        if captured_at.tzinfo is None or captured_at > self.now(conn):
            raise DomainError("CAPTURE_TIME_INVALID")
        capture_digest = hashlib.sha256(capture["html"].encode()).hexdigest()
        contact_id, provenance_id = uuid4(), uuid4()
        conn.execute("INSERT INTO contact_record(contact_id,lead_id,channel,encrypted_value,endpoint_token,token_key_version,first_provenance_id,verification_status,verified_at) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                     (contact_id, lead_id, channel, self.keys.encrypt(normalized), self.keys.token(channel, normalized),
                      self.keys.active_version, provenance_id, verification, verified_at))
        conn.execute("INSERT INTO collection_provenance(provenance_id,contact_id,lead_id,channel,registrable_domain,domain_identity_id,source_url,source_type,content_sha256,encrypted_excerpt,object_ref,collector_version,method,robots_result,terms_scope,actor_id,encrypted_capture,capture_sha256,collected_at) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s,'website',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                     (provenance_id, contact_id, lead_id, channel, identity["registrable_domain"], identity_id, source_url,
                      capture_digest, self.keys.encrypt(excerpt), "encrypted-db:" + str(provenance_id), capture["collector_version"],
                      capture["method"], capture["robots_result"], capture["terms_scope"], actor,
                      self.keys.encrypt(capture["html"]), capture_digest, captured_at))
        self.audit(conn, actor, "contact_collected", contact_id)
        return self.contact(conn, contact_id)

    def basis(self, conn, data: dict, actor: str):
        contact = self.contact(conn, data["contact_id"])
        self.authority(conn, contact["lead_id"])
        contact = self.contact(conn, data["contact_id"])
        if contact["channel"] != "email" or data["channel"] != "email":
            raise DomainError("EMAIL_BASIS_ONLY")
        if data["expected_revision"] != contact["revision"]:
            raise DomainError("REVISION_CONFLICT", 409)
        evidence = conn.execute("SELECT * FROM collection_provenance WHERE provenance_id=%s AND contact_id=%s AND channel='email'",
                                (data["evidence_provenance_id"], contact["contact_id"])).fetchone()
        if not evidence:
            raise DomainError("EVIDENCE_NOT_THIS_CONTACT")
        if evidence.get("capture_erased_at") and data["assessment_state"] == "pass":
            raise DomainError("EVIDENCE_EXPIRED", 410)
        policy = self.current_policy(conn)
        if not policy:
            raise DomainError("POLICY_MISSING")
        now = self.now(conn)
        expires = min(now + timedelta(days=90), policy["expires_at"])
        express = data.get("express_evidence")
        if data["basis_type"] == "express" and data["assessment_state"] == "pass":
            try:
                if not isinstance(express, dict):
                    raise TypeError("Explicit consent evidence required")
                consented = datetime.fromisoformat(str(express["consented_at"]))
                if consented.tzinfo is None or consented > now or express["withdrawal_state"] != "active" or not express["source_ref"] or not isinstance(express["campaign_ids"], list) or not express["campaign_ids"] or not all(isinstance(v, str) and v for v in express["campaign_ids"]):
                    raise ValueError("Invalid consent")
            except (KeyError, TypeError, ValueError):
                raise DomainError("EXPRESS_CONSENT_EVIDENCE_REQUIRED") from None
        row = conn.execute("INSERT INTO contact_basis(basis_id,contact_id,channel,state,basis_type,provenance_id,limbs,express_scope,reason,actor_id,policy_version,assessed_at,expires_at,express_evidence_encrypted) "
                           "VALUES(%s,%s,'email',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                           (uuid4(), contact["contact_id"], data["assessment_state"], data["basis_type"], data["evidence_provenance_id"],
                            Jsonb(data.get("limbs")), data.get("express_scope"), data["reason"], actor, policy["version"], now, expires,
                            self.keys.encrypt(json.dumps(json_safe(express))) if express else None)).fetchone()
        conn.execute("UPDATE contact_record SET revision=revision+1 WHERE contact_id=%s", (contact["contact_id"],))
        self.invalidate(conn, contact["lead_id"])
        self.audit(conn, actor, "basis_assessed", row["basis_id"])
        return {k: row[k] for k in ("basis_id", "assessment_seq", "expires_at")}

    def current_policy(self, conn):
        return conn.execute("SELECT * FROM policy ORDER BY approved_at DESC, version DESC LIMIT 1").fetchone()

    def licence(self, conn, data, actor):
        self.authority(conn, data["lead_id"])
        now = self.now(conn)
        if data["reviewed_at"] > now:
            raise DomainError("FUTURE_REVIEW")
        lead = self.lead(conn, data["lead_id"])
        aliases = conn.execute("SELECT encrypted_identifier FROM lead_source_link WHERE group_id=ANY(%s) AND source_type='qbcc'", (self.group_family(conn, lead["group_id"]),)).fetchall()
        if data["licence_number"] not in {self.keys.decrypt(r["encrypted_identifier"]) for r in aliases}:
            raise DomainError("LICENCE_NOT_THIS_LEAD")
        review_id = uuid4()
        conn.execute("INSERT INTO licence_review(review_id,lead_id,encrypted_licence,status,identity_match,evidence_ref,actor_id,reviewed_at) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)", (review_id, data["lead_id"], self.keys.encrypt(data["licence_number"]),
                      data["status"], data["identity_match"], data["evidence_ref"], actor, data["reviewed_at"]))
        self.invalidate(conn, data["lead_id"])
        return {"review_id": review_id}

    def gate(self, conn, contact_id, *, action: dict | None = None) -> dict:
        contact = self.contact(conn, contact_id)
        self.authority(conn, contact["lead_id"])
        now = self.now(conn)
        contact = self.contact(conn, contact_id)
        lead = self.lead(conn, contact["lead_id"])
        value = self.keys.decrypt(contact["encrypted_value"])
        reasons = self.restricted(conn, lead["group_id"], self.keys.matches(contact["channel"], value))
        versions: dict[str, Any] = {"contact": contact["revision"], "lead": lead["revision"]}
        expires = now + timedelta(days=90)
        if lead["lifecycle"] != "active":
            reasons.append("LEAD_INACTIVE")
        if lead["tier"] not in {"A", "B"}:
            reasons.append("TIER_NOT_ELIGIBLE")
        if lead["state"] != "QLD" and not (lead["state"] == "NSW" and lead["postcode"] and "2450" <= lead["postcode"] <= "2490"):
            reasons.append("GEOGRAPHY_HELD")
        state = conn.execute("SELECT * FROM system_state").fetchall()
        if self.keys.compromised or any(r["value"] for r in state if r["name"] in {"restore_quarantine", "key_compromised"}):
            reasons.append("AUTHORITY_QUARANTINED")
        provenance = conn.execute("SELECT * FROM collection_provenance WHERE provenance_id=%s", (contact["first_provenance_id"],)).fetchone()
        if provenance.get("capture_erased_at"):
            reasons.append("CONTACT_EVIDENCE_ERASED")
        identity = conn.execute("SELECT * FROM domain_identity WHERE lead_id=%s AND registrable_domain=%s ORDER BY assessment_seq DESC LIMIT 1",
                                (lead["lead_id"], provenance["registrable_domain"])).fetchone()
        if not identity or identity["assessment"] != "approved" or not identity["assessed_at"] <= now < identity["expires_at"]:
            reasons.append("IDENTITY_NOT_CURRENT")
        else:
            expires = min(expires, identity["expires_at"])
            versions["identity"] = identity["assessment_seq"]
        if lead["source"] == "qbcc":
            licence = conn.execute("SELECT * FROM licence_review WHERE lead_id=%s ORDER BY reviewed_at DESC,import_seq DESC LIMIT 1", (lead["lead_id"],)).fetchone()
            if not licence or licence["status"] != "active" or not licence["identity_match"] or not licence["reviewed_at"] <= now < licence["reviewed_at"] + timedelta(days=30):
                reasons.append("LICENCE_REVIEW_REQUIRED")
            else:
                versions["licence"] = licence["import_seq"]
                expires = min(expires, licence["reviewed_at"] + timedelta(days=30))
        policy = self.current_policy(conn)
        if not policy or policy["state"] != "approved" or not policy["approved_at"] <= now < policy["expires_at"]:
            reasons.append("POLICY_NOT_CURRENT")
        else:
            versions["policy"] = policy["version"]
            expires = min(expires, policy["expires_at"])
        reasons += gate_reasons(conn, self.settings, "collection", now)
        channel = "email" if contact["channel"] == "email" else "phone"
        if channel == "email":
            basis = conn.execute("SELECT * FROM contact_basis WHERE contact_id=%s ORDER BY assessment_seq DESC LIMIT 1", (contact_id,)).fetchone()
            if not basis or basis["state"] != "pass" or not basis["assessed_at"] <= now < basis["expires_at"] or not policy or basis["policy_version"] != policy["version"]:
                reasons.append("BASIS_NOT_CURRENT")
            else:
                versions["basis"] = basis["assessment_seq"]
                expires = min(expires, basis["expires_at"])
            if contact["verification_status"] != "deliverable" or not contact["verified_at"] or not contact["verified_at"] <= now < contact["verified_at"] + timedelta(days=90):
                reasons.append("EMAIL_NOT_VERIFIED")
            else:
                expires = min(expires, contact["verified_at"] + timedelta(days=90))
        else:
            observations = []
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            try:
                ZoneInfo(lead["fields"].get("recipient_timezone", ""))
            except (ValueError, ZoneInfoNotFoundError):
                reasons.append("TIMEZONE_UNCONFIRMED")
            if not lead["fields"].get("recipient_timezone") or not lead["fields"].get("locality") or not lead["fields"].get("timezone_reviewed"):
                reasons.append("TIMEZONE_UNCONFIRMED")
            for version, token in self.keys.matches("phone", value):
                observations += conn.execute("SELECT * FROM dnc_wash WHERE endpoint_token=%s AND key_version=%s", (token, version)).fetchall()
            wash = max(observations, key=lambda r: (r["checked_at"], r["import_sequence"]), default=None)
            if not wash or wash["result"] != "clear" or not wash["checked_at"] <= now < wash["checked_at"] + timedelta(days=30):
                reasons.append("WASH_NOT_CURRENT_CLEAR")
            else:
                versions["wash"] = wash["import_sequence"]
                expires = min(expires, wash["checked_at"] + timedelta(days=30))
        if action:
            if any(r["name"] == "integration_uncertified" and r["value"] for r in state):
                reasons.append("ACTION_INTEGRATION_UNCERTIFIED")
            reasons += gate_reasons(conn, self.settings, channel + "_action", now)
            if action["expected_contact_revision"] != contact["revision"] or str(action["lead_id"]) != str(lead["lead_id"]) or action["channel"] != channel:
                reasons.append("ACTION_BINDING_CHANGED")
            approved_content = policy["settings"].get("approved_content", {}) if policy else {}
            content_key = action["campaign_id"] + ":" + action["template_id"]
            if approved_content.get(content_key) != action["content_sha256"]:
                reasons.append("CONTENT_NOT_APPROVED")
            if channel == "email":
                if basis and basis["basis_type"] == "express":
                    express = json.loads(self.keys.decrypt(basis["express_evidence_encrypted"])) if basis["express_evidence_encrypted"] else {}
                    if action["campaign_id"] not in express.get("campaign_ids", []) or express.get("withdrawal_state") != "active":
                        reasons.append("EXPRESS_SCOPE_MISMATCH")
                relevance = conn.execute("SELECT * FROM relevance_assessment WHERE contact_id=%s AND campaign_id=%s AND template_id=%s "
                                         "ORDER BY assessment_seq DESC LIMIT 1", (contact_id, action["campaign_id"], action["template_id"])).fetchone()
                if not relevance or str(relevance["assessment_id"]) != str(action.get("relevance_assessment_id")) or relevance["content_sha256"] != action["content_sha256"] or relevance["state"] != "pass" or not relevance["assessed_at"] <= now < relevance["expires_at"] or not policy or relevance["policy_version"] != policy["version"]:
                    reasons.append("RELEVANCE_NOT_CURRENT")
                else:
                    versions["relevance"] = relevance["assessment_seq"]
                    expires = min(expires, relevance["expires_at"])
            else:
                if not policy or action.get("script_policy_version") != policy["version"]:
                    reasons.append("SCRIPT_POLICY_NOT_CURRENT")
                reasons += self.calling_reasons(lead, policy, action, now)
        return {"allowed": not reasons, "reason_codes": sorted(set(reasons)), "checked_at": now,
                "expires_at": expires, "versions": versions, "channel": channel,
                "label": ("Email: needs send-time checks" if channel == "email" else "Phone: check before calling") if not reasons else "Do not contact"}

    @staticmethod
    def calling_reasons(lead, policy, action, now):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        timezone = lead["fields"].get("recipient_timezone")
        locality = lead["fields"].get("locality")
        if not timezone or not locality or not lead["fields"].get("timezone_reviewed") or action.get("recipient_timezone") != timezone:
            return ["TIMEZONE_UNCONFIRMED"]
        calendar = policy["settings"].get("holiday_calendar", {}) if policy else {}
        try:
            local = now.astimezone(ZoneInfo(timezone))
            from datetime import date
            covered = date.fromisoformat(calendar.get("from", "")) <= local.date() <= date.fromisoformat(calendar.get("to", ""))
            holidays = {date.fromisoformat(value) for value in calendar.get("holidays", [])}
        except (ValueError, ZoneInfoNotFoundError):
            return ["HOLIDAY_CALENDAR_UNAPPROVED"]
        if not covered or locality not in calendar.get("localities", []) or not calendar.get("evidence_ref"):
            return ["HOLIDAY_CALENDAR_UNAPPROVED"]
        if local.date() in holidays:
            return ["PUBLIC_HOLIDAY"]
        closing = 17 if local.weekday() == 5 else 18
        if local.weekday() == 6 or not 9 <= local.hour < closing:
            return ["OUTSIDE_CALL_WINDOW"]
        return []

    def relevance(self, conn, data, actor):
        contact = self.contact(conn, data["contact_id"])
        self.authority(conn, contact["lead_id"])
        gate = self.gate(conn, contact["contact_id"])
        if contact["channel"] != "email" or contact["revision"] != data["expected_contact_revision"]:
            raise DomainError("CONTACT_CHANNEL_OR_REVISION", 409)
        if data["state"] == "pass" and not gate["allowed"]:
            raise DomainError("CANDIDATE_NOT_ELIGIBLE", 409)
        policy = self.current_policy(conn)
        if not policy or policy["version"] != data["policy_version"]:
            raise DomainError("POLICY_NOT_CURRENT")
        now = self.now(conn)
        row = conn.execute("INSERT INTO relevance_assessment(assessment_id,contact_id,channel,campaign_id,template_id,content_sha256,policy_version,state,role_evidence_id,reason,actor_id,assessed_at,expires_at) "
                           "VALUES(%s,%s,'email',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                           (uuid4(), contact["contact_id"], data["campaign_id"], data["template_id"], data["content_sha256"],
                            data["policy_version"], data["state"], data["role_evidence_id"], data["reason"], actor, now,
                            min(now + timedelta(hours=24), gate["expires_at"])) ).fetchone()
        self.invalidate(conn, contact["lead_id"])
        self.audit(conn, actor, "relevance_assessed", row["assessment_id"])
        return {k: row[k] for k in ("assessment_id", "assessment_seq", "expires_at")}

    def suppress(self, conn, data, actor, request_id):
        self.authority(conn)
        now = self.now(conn)
        requested = data.get("requested_at", now)
        if isinstance(requested, str):
            requested = datetime.fromisoformat(requested)
        if requested > now + timedelta(minutes=5):
            raise DomainError("FUTURE_REQUEST")
        group_ids = set()
        tokens = set()
        if data.get("lead_id"):
            group_ids.add(self.lead(conn, data["lead_id"])["group_id"])
        if data.get("group_id"):
            group_ids.add(UUID(str(data["group_id"])))
        if data.get("endpoint"):
            _, endpoint_tokens = self.tokens(data["channel"], data["endpoint"])
            tokens.update(endpoint_tokens)
        if not group_ids and not tokens:
            raise DomainError("SUPPRESSION_TARGET_REQUIRED")
        group_ids = {member for group in group_ids for member in self.group_family(conn, group)}
        affected = []
        for group in sorted(group_ids, key=str):
            lock(conn, "group:" + str(group))
            leads = conn.execute("SELECT lead_id FROM lead_entity WHERE group_id=%s", (group,)).fetchall()
            for lead in leads:
                affected.append(lead["lead_id"])
                if data["reason"] not in {"cancellation", "disappearance", "source_inactive"} and not data.get("entity_only"):
                    for contact in conn.execute("SELECT * FROM contact_record WHERE lead_id=%s", (lead["lead_id"],)).fetchall():
                        tokens.update(self.keys.matches(contact["channel"], self.keys.decrypt(contact["encrypted_value"])))
        for version, token in sorted(tokens):
            lock(conn, "endpoint:" + token)
            for row in conn.execute("SELECT lead_id FROM contact_record WHERE endpoint_token=%s", (token,)).fetchall():
                affected.append(row["lead_id"])
        event_ids = []
        for scope, group, version, token in [("business", g, None, None) for g in group_ids] + [("endpoint", None, v, t) for v, t in tokens]:
            event_id = uuid4()
            row = conn.execute("INSERT INTO suppression_event(event_id,request_id,scope,group_id,endpoint_token,key_version,reason,requested_at,actor_id,source) "
                               "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING event_id",
                               (event_id, request_id, scope, group, token, version, data["reason"], requested, actor, data["source"])).fetchone()
            if row:
                event_ids.append(event_id)
        for lead_id in set(affected):
            self.invalidate(conn, lead_id)
            conn.execute("UPDATE candidate_queue SET state='suppressed' WHERE lead_id=%s", (lead_id,))
            # Endpoint-only opt-outs still require removal of every affected downstream projection.
            if self.lead(conn, lead_id)["group_id"] not in group_ids:
                conn.execute("INSERT INTO propagation_outbox(outbox_id,group_id,reason) VALUES(%s,%s,%s)",
                             (uuid4(), self.lead(conn, lead_id)["group_id"], data["reason"]))
                conn.execute("INSERT INTO deletion_job(job_id,group_id) VALUES(%s,%s)",
                             (uuid4(), self.lead(conn, lead_id)["group_id"]))
        for group in group_ids:
            conn.execute("UPDATE business_group SET restriction_revision=restriction_revision+1 WHERE group_id=%s", (group,))
            conn.execute("UPDATE lead_entity SET lifecycle='suppressed',revision=revision+1 WHERE group_id=%s", (group,))
            conn.execute("INSERT INTO deletion_job(job_id,group_id) VALUES(%s,%s)", (uuid4(), group))
            conn.execute("INSERT INTO propagation_outbox(outbox_id,group_id,reason) VALUES(%s,%s,%s)", (uuid4(), group, data["reason"]))
        self.audit(conn, actor, "suppression_committed", request_id, {"affected_leads": len(set(affected))})
        return {"suppression_id": event_ids[0] if event_ids else request_id, "committed_at": now,
                "scope": "business" if group_ids else "endpoint", "affected_leads": len(set(affected)), "receipt_id": request_id}

    def action(self, conn, data, actor):
        self.authority(conn, data["lead_id"])
        gate = self.gate(conn, data["contact_id"], action=data)
        now = self.now(conn)
        intent_id = uuid4()
        expires = min(now + timedelta(seconds=60), gate["expires_at"])
        conn.execute("INSERT INTO action_intent(intent_id,lead_id,contact_id,actor_id,channel,campaign_id,template_id,content_sha256,relevance_id,script_policy_version,expected_revision,versions,state,created_at,expires_at,request) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                     (intent_id, data["lead_id"], data["contact_id"], actor, data["channel"], data["campaign_id"], data["template_id"],
                      data["content_sha256"], data.get("relevance_assessment_id"), data.get("script_policy_version"), data["expected_contact_revision"],
                      Jsonb(json_safe(gate["versions"])), "pending" if gate["allowed"] else "denied", now, expires, Jsonb(json_safe(data))))
        return {"intent_id": intent_id, "state": "pending" if gate["allowed"] else "denied", "expires_at": expires, "reason_codes": gate["reason_codes"]}

    def consume(self, conn, intent_id, data, actor):
        self.authority(conn)
        row = conn.execute("SELECT * FROM action_intent WHERE intent_id=%s FOR UPDATE", (intent_id,)).fetchone()
        if not row:
            raise DomainError("NOT_FOUND", 404)
        if row["actor_id"] != actor:
            raise DomainError("INTENT_ACTOR_MISMATCH", 403)
        if data["content_sha256"] != row["content_sha256"]:
            raise DomainError("CONTENT_MISMATCH", 409)
        if row["dispatch_id"]:
            if str(row["dispatch_id"]) != str(data["dispatch_id"]):
                raise DomainError("INTENT_ALREADY_CONSUMED", 409)
            # Retrieval of an existing decision is not a fresh dispatch permit.
            return {**row["decision"], "replayed": True}
        gate = self.gate(conn, row["contact_id"], action=row["request"])
        now = self.now(conn)
        reasons = gate["reason_codes"]
        if row["state"] != "pending" or now >= row["expires_at"]:
            reasons = reasons + ["INTENT_NOT_CURRENT"]
        if row["versions"] != json_safe(gate["versions"]):
            reasons = reasons + ["AUTHORITY_REVISION_CHANGED"]
        decision = {"decision": "denied" if reasons else "allowed", "decision_id": str(intent_id),
                    "checked_at": now.isoformat(), "valid_until": (now + timedelta(seconds=5)).isoformat(),
                    "dispatch_id": str(data["dispatch_id"]), "reason_codes": sorted(set(reasons)), "replayed": False}
        conn.execute("UPDATE action_intent SET state=%s,dispatch_id=%s,decision=%s WHERE intent_id=%s",
                     ("denied" if reasons else "consumed", data["dispatch_id"], Jsonb(decision), intent_id))
        self.audit(conn, actor, "action_consumed", intent_id, {"decision": decision["decision"]})
        return decision

    def outcome(self, conn, row_id, data, actor, request_id):
        self.authority(conn)
        row = conn.execute("SELECT * FROM worklist_row WHERE row_id=%s FOR UPDATE", (row_id,)).fetchone()
        if not row:
            raise DomainError("NOT_FOUND", 404)
        now = self.now(conn)
        if data["occurred_at"] > now + timedelta(minutes=5):
            raise DomainError("FUTURE_ACTIVITY")
        conflict = row["version"] != data["expected_version"]
        if data["status"] == "do_not_contact_requested":
            self.suppress(conn, {"lead_id": row["lead_id"], "reason": "unsubscribe", "source": "worklist",
                                 "requested_at": data["occurred_at"]}, actor, request_id)
        elif conflict:
            raise DomainError("REVISION_CONFLICT", 409, {"current_version": row["version"], "status": row["outcome"]})
        conn.execute("INSERT INTO outcome_event(event_id,row_id,expected_version,actor_id,status,attempts,invitation_state,invitation_evidence_ref,notes,occurred_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                     (request_id, row_id, data["expected_version"], actor, data["status"], data["attempts"],
                      data["invitation_state"], data.get("invitation_evidence_ref"), data.get("notes", ""), data["occurred_at"]))
        conn.execute("UPDATE worklist_row SET version=version+1,outcome=%s,approval_state='pending' WHERE row_id=%s", (data["status"], row_id))
        self.invalidate(conn, row["lead_id"])
        return {"row_id": row_id, "version": row["version"] + 1, "status": data["status"], "saved_at": now,
                "suppression_committed": data["status"] == "do_not_contact_requested", "outcome_conflict": conflict}
