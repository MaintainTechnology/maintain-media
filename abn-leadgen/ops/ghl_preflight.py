"""Read only GHL location/custom-field metadata from explicit operator config.

Example: uv run python ops/ghl_preflight.py --config /etc/abr-engine/ghl.yaml
The running process receives ABR_GHL_TOKEN from a secret manager. No .env reading.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from abr_engine.control.service import DomainError
from abr_engine.export.gohighlevel import GHLRetryableError, GoHighLevel, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Non-secret GHL YAML configuration")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        # No guard is supplied, so this executable can never perform a write,
        # even if a supplied configuration mistakenly has allow_writes=true.
        with GoHighLevel.from_environment(config) as provider:
            report = provider.preflight()
        print(json.dumps(report, sort_keys=True))
        return 0 if report["fields_verified"] else 2
    except GHLRetryableError as exc:
        report = {"code": exc.code, "retry_after_seconds": exc.retry_after}
    except DomainError as exc:
        report = {"code": exc.code}
    except (OSError, ValueError, ValidationError):
        report = {"code": "GHL_CONFIGURATION_INVALID"}
    print(json.dumps({**report, "writes_performed": 0, "ready_for_production": False}, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
