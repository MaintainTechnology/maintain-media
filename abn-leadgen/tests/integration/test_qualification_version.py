from abr_engine.db import transaction
from abr_engine.enrich.worker import SyntheticProvider, drain_one
from abr_engine.fixture import seed_policy
from abr_engine.qualify.policy import policy_metadata


def test_created_candidate_records_reviewed_policy_version(db, service):
    lead = service.create_lead(db, name="Synthetic policy version", source="qbcc", alias="87654321")
    row = db.execute("SELECT stage_data FROM candidate_queue WHERE lead_id=%s", (lead["lead_id"],)).fetchone()
    assert all(lead["fields"][key] == value for key, value in policy_metadata().items())
    assert row["stage_data"] == policy_metadata()


def test_final_scoring_records_version_on_completed_attempt(settings, service):
    with transaction(settings) as conn:
        seed_policy(conn, service)
        lead = service.create_lead(
            conn,
            name="Synthetic final score",
            source="qbcc",
            alias="87654322",
            fields={"financial_category": "1", "entity_class": "company"},
        )
        conn.execute(
            "UPDATE candidate_queue SET state='pending_enrichment',stage_data='{}' WHERE lead_id=%s",
            (lead["lead_id"],),
        )
    assert drain_one(settings, service, SyntheticProvider())["status"] == "complete"
    with transaction(settings) as conn:
        row = conn.execute(
            "SELECT score,stage_data FROM candidate_queue WHERE lead_id=%s", (lead["lead_id"],)
        ).fetchone()
        assert row["score"] == 90
        assert all(row["stage_data"][key] == value for key, value in policy_metadata().items())
