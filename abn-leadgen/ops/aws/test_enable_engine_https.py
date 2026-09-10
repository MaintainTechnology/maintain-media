"""Offline policy and exact-resource boundary tests; no AWS access."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BASE = Path(__file__).resolve().parent
for name in ("deploy_session", "enable_engine_https"):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
https = sys.modules["enable_engine_https"]


@pytest.fixture
def session():
    return https.HttpsSession(SimpleNamespace(aws="unused", profile="unused", account=https.ACCOUNT,
                                              operator_ip="8.8.8.8"))


def test_policy_has_only_exact_instance_firewall_write(session):
    for create in (True, False):
        statements = session.policy(create)["Statement"]
        writes = [s for s in statements if s["Action"] == "lightsail:PutInstancePublicPorts"]
        assert len(writes) == 1 and writes[0]["Resource"] == https.INSTANCE_ARN
        assert all("Create" not in str(s) and "*" != s["Action"] for s in statements)


def test_only_adds_https_and_redirect_with_operator_ssh(session, monkeypatch):
    calls = []
    current = session.desired_ports()[:1]
    monkeypatch.setattr(session, "verify_instance", lambda: None)
    monkeypatch.setattr(session, "current_ports", lambda: current)
    def call(service, operation, payload):
        assert (service, operation) == ("lightsail", "put-instance-public-ports")
        calls.append(payload)
        current[:] = payload["portInfos"]
    monkeypatch.setattr(session, "call", call)
    session.apply()
    session.apply()
    assert len(calls) == 1
    assert current[0]["cidrs"] == ["8.8.8.8/32"]
    assert [row["fromPort"] for row in current] == [22, 80, 443]


def test_unexpected_firewall_stops_before_mutation(session, monkeypatch):
    monkeypatch.setattr(session, "verify_instance", lambda: None)
    monkeypatch.setattr(session, "current_ports", list)
    monkeypatch.setattr(session, "call", lambda *_: pytest.fail("Cannot replace foreign firewall"))
    with pytest.raises(https.AwsFailure, match="Unexpected existing firewall"):
        session.apply()


def test_foreign_instance_stops_before_firewall(session, monkeypatch):
    monkeypatch.setattr(session, "call", lambda *_: {"instance": {"arn": "foreign"}})
    with pytest.raises(https.AwsFailure, match="identity changed"):
        session.apply()
