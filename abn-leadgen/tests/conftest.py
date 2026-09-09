"""Actual isolated PostgreSQL16, rollback per unit of integration, no external fixture sockets."""
import ipaddress
import socket
from uuid import uuid4

import pytest
from psycopg import sql

from abr_engine.compliance.keys import load_keys
from abr_engine.config import Settings
from abr_engine.control.service import Service
from abr_engine.db import connect, migrate


@pytest.fixture
def settings():
    schema = "abr_test_" + uuid4().hex
    config = Settings(schema_name=schema)
    with connect(Settings()) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    migrate(config)
    try:
        yield config
    finally:
        assert schema.startswith("abr_test_") and len(schema) == 41
        with connect(Settings()) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def service(settings):
    return Service(settings, load_keys(settings))


@pytest.fixture
def db(settings):
    conn = connect(settings)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture(autouse=True)
def offline_sockets(monkeypatch):
    original = socket.socket.connect
    def guarded(sock, address):
        if isinstance(address, tuple):
            try:
                allowed = ipaddress.ip_address(address[0]).is_loopback
            except ValueError:
                allowed = address[0] == "localhost"
            if not allowed:
                raise AssertionError("Fixture attempted external network")
        return original(sock, address)
    monkeypatch.setattr(socket.socket, "connect", guarded)
