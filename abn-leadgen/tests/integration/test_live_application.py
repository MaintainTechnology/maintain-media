"""Real application composition and isolated worker failure behaviour."""
import pytest
from fastapi.testclient import TestClient

from abr_engine.compliance import keys
from abr_engine.control import api as control_api
from abr_engine.control.service import DomainError
from abr_engine.live.application import build_application, worker_tick
from abr_engine.live.runtime import QBCCRuntime
from abr_engine.ops import propagation


def test_live_factory_requires_dedicated_signing_authority(settings):
    with pytest.raises(ValueError, match="Explicit live"):
        build_application(settings, environ={})
    with pytest.raises(ValueError, match="Dedicated"):
        build_application(settings.model_copy(update={"mode": "pilot"}), environ={})


def test_live_factory_composes_real_protected_routes(settings, service, monkeypatch):
    monkeypatch.setattr(control_api, "load_keys", lambda _: service.keys)
    config = settings.model_copy(update={"mode": "pilot"})
    app = build_application(config, environ={"ABN_ENGINE_ASSERTION_KEY": "synthetic-only-" + "x" * 43})
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/dashboard").status_code == 401
        assert client.get("/api/qbcc-reviews").status_code == 401


def test_empty_live_worker_uses_actual_schema_and_closed_vendor_gate(settings, service, monkeypatch):
    monkeypatch.setattr(keys, "load_keys", lambda _: service.keys)
    result = worker_tick(settings.model_copy(update={"mode": "pilot"}))
    assert result["source_jobs"] == [] and result["website_jobs"] == []
    assert result["crm"] == []
    assert result["propagation"]["status"] == "held"


def test_control_lane_cannot_be_delayed_by_source_job(settings, service, monkeypatch):
    monkeypatch.setattr(keys, "load_keys", lambda _: service.keys)
    monkeypatch.setattr(QBCCRuntime, "execute_pending", lambda *_a, **_k: pytest.fail("No source work in control lane"))
    monkeypatch.setattr(propagation, "drain_propagation", lambda *_a, **_k: {"saved": True})
    result = worker_tick(settings.model_copy(update={"mode": "pilot"}), lane_group="control")
    assert result == {"propagation": {"saved": True}, "crm": []}


def test_closed_vendor_does_not_abort_independent_source_recovery(settings, service, monkeypatch):
    monkeypatch.setattr(keys, "load_keys", lambda _: service.keys)
    events = []
    def closed(*_a, **_k):
        events.append("removals_first")
        raise DomainError("GATE_G5_CLOSED", 403)
    def source(*_a, **_k):
        events.append("source")
        return []
    monkeypatch.setattr(propagation, "drain_propagation", closed)
    monkeypatch.setattr(QBCCRuntime, "execute_pending", source)
    result = worker_tick(settings.model_copy(update={"mode": "pilot"}))
    assert events == ["removals_first", "source"]
    assert result["propagation"]["code"] == "GATE_G5_CLOSED" and result["crm"] == []
