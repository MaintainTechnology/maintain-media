"""Manual receipt import: fixture format is explicitly not a claimed vendor format."""
from datetime import datetime
from uuid import uuid4

from psycopg.types.json import Jsonb

from abr_engine.control.service import DomainError, digest
from abr_engine.enrich.endpoints import normalize_phone


def create_batch(conn, service, phones: list[str]):
    service.authority(conn)
    normalized = sorted({normalize_phone(v) for v in phones})
    tokens = sorted(service.keys.token("phone", v) for v in normalized)
    batch_id = uuid4()
    conn.execute("INSERT INTO wash_batch(batch_id,digest,expected_tokens) VALUES(%s,%s,%s)",
                 (batch_id, digest(tokens), Jsonb(tokens)))
    return {"batch_id": batch_id, "digest": digest(tokens), "count": len(tokens)}


def import_receipt(conn, service, batch_id, records: list[dict], receipt: dict, actor: str):
    service.authority(conn)
    if service.settings.mode != "fixture":
        raise DomainError("VENDOR_RECEIPT_MAPPING_PENDING", 409)
    if receipt.get("format") != "maintain-fixture-wash-v1" or not receipt.get("account"):
        raise DomainError("RECEIPT_FORMAT_UNAPPROVED")
    batch = conn.execute("SELECT * FROM wash_batch WHERE batch_id=%s FOR UPDATE", (batch_id,)).fetchone()
    if not batch or receipt.get("batch_digest") != batch["digest"] or receipt.get("count") != len(batch["expected_tokens"]):
        raise DomainError("BATCH_MISMATCH")
    now = service.now(conn)
    validated = {}
    for record in records:
        token = service.keys.token("phone", normalize_phone(record["phone"]))
        when = datetime.fromisoformat(record["washed_at"])
        if when.tzinfo is None or when > now or record["result"] not in {"clear", "listed", "error"}:
            raise DomainError("INVALID_WASH_OBSERVATION")
        if token in validated:
            raise DomainError("DUPLICATE_WASH_ROW")
        validated[token] = (record["result"], when)
    if set(validated) != set(batch["expected_tokens"]):
        raise DomainError("BATCH_MEMBERSHIP_MISMATCH")
    if receipt.get("records_digest") != digest(records):
        raise DomainError("RECEIPT_CONTENT_MISMATCH")
    receipt_digest = digest(receipt)
    for token, (result, when) in validated.items():
        conn.execute("INSERT INTO dnc_wash(wash_id,batch_id,endpoint_token,key_version,checked_at,result,provider,receipt_sha256,actor_id) "
                     "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                     (uuid4(), batch_id, token, service.keys.active_version, when, result, receipt["account"], receipt_digest, actor))
        for contact in conn.execute("SELECT lead_id FROM contact_record WHERE endpoint_token=%s", (token,)).fetchall():
            service.invalidate(conn, contact["lead_id"])
    service.audit(conn, actor, "wash_imported", batch_id, {"count": len(validated)})
    return {"batch_id": batch_id, "count": len(validated), "receipt_digest": receipt_digest}
