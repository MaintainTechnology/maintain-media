"""Persistent fixture CRM simulator; no HTTP and no real location/account."""
import json

from abr_engine.control.service import DomainError, json_safe
from abr_engine.db import transaction


class PersistentMockCRM:
    def __init__(self, settings, keys):
        if settings.mode != "fixture":
            raise DomainError("FIXTURE_PROVIDER_ONLY", 403)
        self.settings, self.keys = settings, keys

    def find_group(self, group_id):
        with transaction(self.settings) as conn:
            return [r["remote_id"] for r in conn.execute("SELECT remote_id FROM fixture_crm_record WHERE group_id=%s", (group_id,)).fetchall()]

    def fetch(self, remote_id):
        with transaction(self.settings) as conn:
            row = conn.execute("SELECT * FROM fixture_crm_record WHERE remote_id=%s", (remote_id,)).fetchone()
            if not row:
                return None
            return {"group_id": str(row["group_id"]), "payload": json.loads(self.keys.decrypt(row["encrypted_payload"]))}

    def create(self, group_id, payload, request_id):
        remote_id = "fixture-" + request_id
        with transaction(self.settings) as conn:
            conn.execute("INSERT INTO fixture_crm_record(remote_id,group_id,encrypted_payload) VALUES(%s,%s,%s) ON CONFLICT(group_id) DO NOTHING",
                         (remote_id, group_id, self.keys.encrypt(json.dumps(json_safe(payload)))))
            saved = conn.execute("SELECT remote_id FROM fixture_crm_record WHERE group_id=%s", (group_id,)).fetchone()
            assert saved is not None
            return saved["remote_id"]

    def update(self, remote_id, payload, request_id):
        with transaction(self.settings) as conn:
            row = conn.execute("SELECT * FROM fixture_crm_record WHERE remote_id=%s FOR UPDATE", (remote_id,)).fetchone()
            if not row:
                raise ValueError("Unknown fixture CRM record")
            old = json.loads(self.keys.decrypt(row["encrypted_payload"]))
            unrelated = {v for v in old.get("tags", []) if not v.startswith("maintain-media:")}
            desired = {**payload, "tags": sorted(unrelated | set(payload.get("tags", [])))}
            conn.execute("UPDATE fixture_crm_record SET encrypted_payload=%s WHERE remote_id=%s", (self.keys.encrypt(json.dumps(json_safe(desired))), remote_id))
