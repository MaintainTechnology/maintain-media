import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "ops/aws"))
import backup_cli
import backup_schedule_install as installer
from backup_crypto import BackupError
from backup_runtime import publication_lease


def test_units_use_exact_current_authority_and_dormant_installer(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["backup_schedule_install"])
    monkeypatch.setattr(installer, "run", lambda *_: pytest.fail("Review cannot invoke systemd"))
    assert installer.main() == 0
    assert json.loads(capsys.readouterr().out)["services_enabled"] is False
    values = installer.units()
    assert len(values) == 7
    for name, content in values.items():
        if name.endswith(".service") and "alert" not in name:
            assert "--config /etc/abr-engine/pilot.yaml" in content
            assert "--authority /etc/abr-engine/backup/authority.json" in content
            assert "User=abr-engine" in content and "OnFailure=abr-engine-backup-alert.service" in content
            assert "--private-key" not in content
        if name.endswith(".timer"):
            assert "Persistent=true" in content and "RandomizedDelaySec=0" in content
    assert "OnUnitActiveSec=15s" in values["abr-engine-backup-ledger.timer"]
    assert "OnCalendar=*-*-* *:0/4:00 UTC" in values["abr-engine-backup-ledger.timer"]
    assert "03,15:00:00 UTC" in values["abr-engine-backup-expiry.timer"]
    assert "02:00:00 UTC" in values["abr-engine-backup-daily.timer"]


@pytest.mark.parametrize("state", ["ActiveState=active\nUnitFileState=disabled", "ActiveState=inactive\nUnitFileState=enabled", "ActiveState=activating\nUnitFileState=static"])
def test_installer_refuses_active_or_enabled_units(monkeypatch, state):
    monkeypatch.setattr(installer, "run", lambda _: state)
    with pytest.raises(installer.ScheduleError, match="DISABLED"):
        installer.inactive("abr-engine-backup-ledger.timer")


def test_interrupted_publisher_os_lock_releases_and_capture_is_independent(tmp_path):
    source = Path(__file__).parents[2]
    marker = tmp_path / "held"
    code = (f"import sys,time;sys.path[:0]={sys.path!r};sys.path[:0]=[{str(source/'ops/aws')!r},{str(source/'src')!r}];"
        f"from pathlib import Path;from backup_runtime import publication_lease;"
        f"lock=publication_lease(Path({str(tmp_path)!r}));lock.__enter__();"
        f"Path({str(marker)!r}).write_text('held');time.sleep(30)")
    # Windows venv python.exe can be a redirector with a surviving grandchild.
    child = subprocess.Popen([sys._base_executable, "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline and child.poll() is None:
            time.sleep(.02)
        assert marker.exists()
        with pytest.raises(BackupError, match="PUBLICATION_BUSY"), publication_lease(tmp_path):
            pass
        with publication_lease(tmp_path, capture=True):
            pass
    finally:
        child.kill()
        child.wait(timeout=5)
    with publication_lease(tmp_path):
        pass


def test_legacy_unknown_publication_file_requires_reconciliation(tmp_path):
    (tmp_path / "publication.lock").write_text("synthetic old publisher")
    with pytest.raises(BackupError, match="RECOVERY_REQUIRED"), publication_lease(tmp_path):
        pass


def test_missing_authority_writes_durable_failed_receipt_without_reading_env(tmp_path, monkeypatch, capsys):
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    args = ["backup_cli", "worker", "--config", str(tmp_path / "pilot.yaml"),
        "--authority", str(tmp_path / "not-approved.json"), "--aws-cli", str(tmp_path / "aws"),
        "--public-key", str(tmp_path / "recipient.pem"), "--staging", str(tmp_path),
        "--receipts", str(receipts), "--bucket", "synthetic-bucket", "--account-id", "123456789012"]
    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(backup_cli, "load_settings", lambda *_: pytest.fail("Missing authority must stop first"))
    assert backup_cli.main() == 3
    assert json.loads(capsys.readouterr().out)["status"] == "held"
    assert json.loads((receipts / "latest-ledger-worker.json").read_text())["status"] == "held"


def test_failed_receipt_replaces_prior_success_atomically(tmp_path):
    backup_cli.write_receipt(tmp_path, "latest-ledger-worker.json", {"status": "acknowledged"})
    backup_cli.write_receipt(tmp_path, "latest-ledger-worker.json", {"status": "held", "code": "BACKUP_OPERATION_FAILED"})
    assert json.loads((tmp_path / "latest-ledger-worker.json").read_text())["status"] == "held"
    assert not list(tmp_path.glob(".receipt-*"))
