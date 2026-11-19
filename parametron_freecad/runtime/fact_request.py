"""Strict contract boundary for Engine fact request sidecars."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parametron_freecad.common.strict_json import StrictJsonError, load_strict_json_file
from parametron_freecad.runtime.occurrence_request import (
    OccurrenceContextFrame,
    OccurrenceEntity,
    OccurrenceRequestError,
    normalize_context,
    normalize_entity,
)

FACT_REQUEST_FILENAME = "prm.fact-request.json"
FACT_REQUEST_SCHEMA_VERSION = "1.0"
FACT_KIND_BOUND_PROPERTY = "bound_property"

FACT_VALUE_KIND_NUMBER = "number"
FACT_VALUE_KIND_INTEGER = "integer"
FACT_VALUE_KIND_STRING = "string"
FACT_VALUE_KIND_BOOLEAN = "boolean"

FACT_REQUIREMENT_OPTIONAL = "optional"
FACT_REQUIREMENT_REQUIRED = "required"

FACT_MAX_BINDINGS = 32
FACT_MAX_PROPERTY_LENGTH = 128
FACT_MAX_UNIT_LENGTH = 32

_VALUE_KINDS = frozenset(
    {
        FACT_VALUE_KIND_NUMBER,
        FACT_VALUE_KIND_INTEGER,
        FACT_VALUE_KIND_STRING,
        FACT_VALUE_KIND_BOOLEAN,
    }
)
_NON_NUMERIC_VALUE_KINDS = frozenset({FACT_VALUE_KIND_STRING, FACT_VALUE_KIND_BOOLEAN})

_REQUEST_FIELDS = frozenset({"schemaVersion", "bindings"})
_BINDING_REQUIRED_FIELDS = frozenset(
    {
        "kind",
        "subject",
        "context",
        "property",
        "valueKind",
        "requirement",
    }
)
_BINDING_OPTIONAL_FIELDS = frozenset({"unit"})


class FactRequestError(ValueError):
    """Raised when a fact request cannot be discovered or consumed."""


@dataclass(frozen=True, slots=True)
class FactBinding:
    """One explicitly bound native property observation."""

    kind: str
    subject: OccurrenceEntity
    context: tuple[OccurrenceContextFrame, ...]
    property: str
    value_kind: str
    unit: str
    requirement: str

    def key(self) -> tuple[Any, ...]:
        subject = self.subject
        resource = subject.resource
        subject_key = (
            resource.project_id,
            resource.kind,
            resource.logical_id,
            subject.native_kind,
            subject.name,
        )
        context_key = tuple(
            (
                frame.parent.resource.project_id,
                frame.parent.resource.kind,
                frame.parent.resource.logical_id,
                frame.parent.native_kind,
                frame.parent.name,
                frame.parent.semantic_id,
                frame.member,
            )
            for frame in self.context
        )
        return (self.kind, subject_key, context_key, self.property)


@dataclass(frozen=True, slots=True)
class FactRequest:
    """Immutable strict fact request."""

    schema_version: str
    bindings: tuple[FactBinding, ...]


def discover_fact_request(working_copy: str | Path) -> Path | None:
    """Return the confined request path when the working copy provides one."""
    root = Path(working_copy).expanduser().resolve(strict=False)
    candidate = root / FACT_REQUEST_FILENAME

    if candidate.is_symlink():
        raise FactRequestError("fact request must not be a symbolic link")
    if not candidate.exists():
        return None
    if not candidate.is_file():
        raise FactRequestError("fact request must be a regular file")
    return candidate


def load_fact_request(path: str | Path) -> FactRequest:
    """Load and strictly validate one fact request file."""
    request_path = Path(path)
    try:
        decoded = load_strict_json_file(request_path)
    except StrictJsonError as exc:
        raise FactRequestError(f"fact request is invalid: {exc}") from exc
    try:
        return _normalize_request(decoded)
    except FactRequestError:
        raise
    except OccurrenceRequestError as exc:
        raise FactRequestError(f"fact request is invalid: {exc}") from exc
    except ValueError as exc:
        raise FactRequestError(f"fact request is invalid: {exc}") from exc


def _normalize_request(decoded: Any) -> FactRequest:
    if not isinstance(decoded, dict):
        raise FactRequestError("fact request root must be a JSON object")

    _require_exact_fields(decoded, _REQUEST_FIELDS, "fact request")

    schema_version = decoded["schemaVersion"]
    if schema_version != FACT_REQUEST_SCHEMA_VERSION:
        raise FactRequestError(
            f"fact request schemaVersion must equal {FACT_REQUEST_SCHEMA_VERSION!r}"
        )

    raw_bindings = decoded["bindings"]
    if not isinstance(raw_bindings, list):
        raise FactRequestError("fact request bindings must be an array")
    if not raw_bindings:
        raise FactRequestError("fact request requires at least one binding")
    if len(raw_bindings) > FACT_MAX_BINDINGS:
        raise FactRequestError(
            f"fact request must contain at most {FACT_MAX_BINDINGS} bindings"
        )

    bindings = tuple(
        _normalize_binding(binding, f"fact request bindings[{index}]")
        for index, binding in enumerate(raw_bindings)
    )
    seen: set[tuple[Any, ...]] = set()
    for binding in bindings:
        key = binding.key()
        if key in seen:
            raise FactRequestError(
                "fact request contains a duplicate or conflicting binding"
            )
        seen.add(key)

    return FactRequest(schema_version=schema_version, bindings=bindings)


def _normalize_binding(value: Any, context: str) -> FactBinding:
    if not isinstance(value, dict):
        raise FactRequestError(f"{context} must be a JSON object")

    _require_exact_fields(
        value,
        _BINDING_REQUIRED_FIELDS,
        context,
        optional=_BINDING_OPTIONAL_FIELDS,
    )

    kind = value["kind"]
    if kind != FACT_KIND_BOUND_PROPERTY:
        raise FactRequestError(
            f"{context}.kind must equal {FACT_KIND_BOUND_PROPERTY!r}"
        )

    subject = normalize_entity(value["subject"], f"{context}.subject")
    frames = normalize_context(
        value["context"],
        subject,
        f"{context}.context",
    )

    property_name = _bounded_text(
        value["property"],
        f"{context}.property",
        maximum=FACT_MAX_PROPERTY_LENGTH,
    )

    value_kind = value["valueKind"]
    if value_kind not in _VALUE_KINDS:
        raise FactRequestError(f"{context}.valueKind is unsupported")

    unit = ""
    if "unit" in value:
        unit = _normalize_unit(value["unit"], value_kind, f"{context}.unit")

    requirement = value["requirement"]
    if requirement not in (
        FACT_REQUIREMENT_OPTIONAL,
        FACT_REQUIREMENT_REQUIRED,
    ):
        raise FactRequestError(
            f"{context}.requirement must be 'optional' or 'required'"
        )

    return FactBinding(
        kind=kind,
        subject=subject,
        context=frames,
        property=property_name,
        value_kind=value_kind,
        unit=unit,
        requirement=requirement,
    )


def _normalize_unit(value: Any, value_kind: str, field: str) -> str:
    if not isinstance(value, str):
        raise FactRequestError(f"{field} must be a string")
    unit = value.strip()
    if unit == "":
        return ""
    if (
        unit != value
        or "\x00" in unit
        or any(character in unit for character in "\n\r\t")
        or len(unit) > FACT_MAX_UNIT_LENGTH
    ):
        raise FactRequestError(f"{field} must be a bounded unit token")
    if value_kind in _NON_NUMERIC_VALUE_KINDS:
        raise FactRequestError(f"{field} is incompatible with non-numeric fact values")
    return unit


def _bounded_text(value: Any, field: str, *, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or "\x00" in value
        or len(value) > maximum
    ):
        raise FactRequestError(f"{field} must be a bounded non-empty unspaced string")
    return value


def _require_exact_fields(
    value: dict[str, Any],
    required: frozenset[str],
    context: str,
    *,
    optional: frozenset[str] = frozenset(),
) -> None:
    actual = set(value)
    missing = required - actual
    if missing:
        raise FactRequestError(f"{context} requires field {sorted(missing)[0]!r}")
    unknown = actual - required - optional
    if unknown:
        rendered = ", ".join(repr(field) for field in sorted(unknown))
        raise FactRequestError(f"{context} contains unknown field(s): {rendered}")


__all__ = [
    "FACT_KIND_BOUND_PROPERTY",
    "FACT_MAX_BINDINGS",
    "FACT_MAX_PROPERTY_LENGTH",
    "FACT_MAX_UNIT_LENGTH",
    "FACT_REQUEST_FILENAME",
    "FACT_REQUEST_SCHEMA_VERSION",
    "FACT_REQUIREMENT_OPTIONAL",
    "FACT_REQUIREMENT_REQUIRED",
    "FACT_VALUE_KIND_BOOLEAN",
    "FACT_VALUE_KIND_INTEGER",
    "FACT_VALUE_KIND_NUMBER",
    "FACT_VALUE_KIND_STRING",
    "FactBinding",
    "FactRequest",
    "FactRequestError",
    "discover_fact_request",
    "load_fact_request",
]
