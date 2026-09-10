"""Execute real Apps Script merge, timers, masking and exact GET binding offline."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("scenario", [
    "positive_idempotent", "pending_sorted", "invalid_unsaved_without_event",
    "withdrawn_and_retired", "pending_stop_never_redisclosed", "closed_gate",
    "restriction_tick_never_adds", "malformed_before_apply", "local_identity_conflict",
    "privacy_and_availability_fail_closed", "literal_formula", "readback_failure_no_receipt",
    "activation_idempotent_and_gated",
])
def test_executable_sheets_pull(scenario):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for Apps Script behavioral checks")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([node, str(root/"tests/fixtures/sheets_sync_harness.cjs"),
        str(root/"integrations/maintain_media_standalone.gs"), str(root/"templates/worklist_schema.json"), scenario],
        capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "PASS " + scenario
