from __future__ import annotations

import json
from pathlib import Path

import pytest

from security_ai.contracts import ContractValidationError, validate_incident_event

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = (
    REPOSITORY_ROOT
    / "packages"
    / "contracts"
    / "fixtures"
    / "incident-event.v1.valid.json"
)


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_shared_fixture_is_valid() -> None:
    validate_incident_event(load_fixture())


def test_out_of_range_risk_is_rejected() -> None:
    event = load_fixture()
    event["riskLevel"] = 5

    with pytest.raises(ContractValidationError, match="riskLevel"):
        validate_incident_event(event)


def test_unknown_fields_are_rejected() -> None:
    event = load_fixture()
    event["unversionedField"] = True

    with pytest.raises(ContractValidationError, match="Additional properties"):
        validate_incident_event(event)
