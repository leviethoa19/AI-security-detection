"""Validation for versioned cross-system contracts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


class ContractValidationError(ValueError):
    """Raised when a value violates a shared system contract."""


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


@lru_cache(maxsize=3)
def _validator(schema_name: str) -> Draft202012Validator:
    schema_path = _repository_root() / "packages" / "contracts" / "schema" / schema_name
    schema: dict[str, Any] = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_incident_event(value: object) -> None:
    """Validate an incident event or raise one concise domain error."""

    try:
        _validator("incident-event.v1.schema.json").validate(value)
    except ValidationError as error:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        message = f"invalid incident event at {location}: {error.message}"
        raise ContractValidationError(message) from error


def validate_incident_snapshot(value: object) -> None:
    """Validate a materialized incident snapshot."""

    try:
        _validator("incident-snapshot.v1.schema.json").validate(value)
    except ValidationError as error:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        message = f"invalid incident snapshot at {location}: {error.message}"
        raise ContractValidationError(message) from error


def validate_evaluation_manifest(value: object) -> None:
    """Validate the leakage-aware event evaluation manifest."""

    try:
        _validator("evaluation-manifest.v1.schema.json").validate(value)
    except ValidationError as error:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        message = f"invalid evaluation manifest at {location}: {error.message}"
        raise ContractValidationError(message) from error
