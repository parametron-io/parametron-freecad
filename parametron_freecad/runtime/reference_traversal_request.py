"""Strict contract boundary for reference traversal request files."""

from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, NoReturn

REFERENCE_TRAVERSAL_REQUEST_SCHEMA_VERSION = "1.0"
REFERENCE_TRAVERSAL_REQUEST_SCHEMA_VERSION_V2 = "2.0"
REFERENCE_TRAVERSAL_REQUEST_FILENAME = (
    "parametron.reference-traversal-request.json"
)
REFERENCE_TRAVERSAL_OUTPUT_FILENAME = "parametron.reference-traversal.json"
REFERENCE_TRAVERSAL_REQUEST_CLI_FLAG = "--reference-traversal-request"


@dataclass(frozen=True, slots=True)
class ReferenceTraversalExternalTarget:
    source_object_name: str
    source_property: str
    reference_mechanism: str
    target_object_name: str
    target_document_path: str


@dataclass(frozen=True, slots=True)
class ReferenceTraversalRequest:
    """Immutable normalized request for optional reference traversal."""

    schema_version: str


@dataclass(frozen=True, slots=True)
class ReferenceTraversalRequestV2(ReferenceTraversalRequest):
    """Immutable normalized schema-2 request with Engine target mappings."""

    external_targets: tuple[ReferenceTraversalExternalTarget, ...] = ()


_SUPPORTED_REFERENCE_MECHANISMS = (
    "App::PropertyLink",
    "App::PropertyLinkChild",
    "App::PropertyLinkGlobal",
    "App::PropertyLinkHidden",
    "App::PropertyLinkList",
    "App::PropertyLinkListChild",
    "App::PropertyLinkListGlobal",
    "App::PropertyLinkListHidden",
    "App::PropertyLinkSub",
    "App::PropertyLinkSubChild",
    "App::PropertyLinkSubGlobal",
    "App::PropertyLinkSubHidden",
    "App::PropertyLinkSubList",
    "App::PropertyLinkSubListChild",
    "App::PropertyLinkSubListGlobal",
    "App::PropertyLinkSubListHidden",
    "App::PropertyXLink",
    "App::PropertyXLinkList",
    "App::PropertyXLinkSub",
    "App::PropertyXLinkSubHidden",
    "App::PropertyXLinkSubList",
)
_LIST_REFERENCE_MECHANISMS = frozenset(
    mechanism for mechanism in _SUPPORTED_REFERENCE_MECHANISMS if "List" in mechanism
)
_EXTERNAL_TARGET_FIELDS = (
    "sourceObjectName",
    "sourceProperty",
    "referenceMechanism",
    "targetObjectName",
    "targetDocumentPath",
)


class ReferenceTraversalRequestError(ValueError):
    """Raised when a reference traversal request cannot be loaded or validated."""


class _DuplicateKeyError(ValueError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"duplicate object key: {key!r}")


class _NonJsonConstantError(ValueError):
    def __init__(self, constant: str) -> None:
        self.constant = constant
        super().__init__(f"non-standard JSON constant: {constant}")


def _reject_duplicate_object_keys(
    pairs: Iterable[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def _reject_non_json_constant(constant: str) -> NoReturn:
    raise _NonJsonConstantError(constant)


def _decode_request(raw_text: str) -> Any:
    return json.loads(
        raw_text,
        object_pairs_hook=_reject_duplicate_object_keys,
        parse_constant=_reject_non_json_constant,
    )


def _normalize_request(decoded: Any) -> ReferenceTraversalRequest:
    if not isinstance(decoded, dict):
        raise ValueError("request root must be a JSON object")

    if "schemaVersion" not in decoded:
        raise ValueError("request requires field 'schemaVersion'")
    schema_version = decoded["schemaVersion"]
    if schema_version == REFERENCE_TRAVERSAL_REQUEST_SCHEMA_VERSION:
        expected_fields = {"schemaVersion"}
    elif schema_version == REFERENCE_TRAVERSAL_REQUEST_SCHEMA_VERSION_V2:
        expected_fields = {"schemaVersion", "externalTargets"}
    else:
        raise ValueError(
            "request field 'schemaVersion' must equal '1.0' or '2.0'"
        )
    actual_fields = set(decoded)
    missing_fields = expected_fields - actual_fields
    unknown_fields = actual_fields - expected_fields
    if missing_fields:
        raise ValueError(f"request requires field {sorted(missing_fields)[0]!r}")
    if unknown_fields:
        rendered = ", ".join(repr(field) for field in sorted(unknown_fields))
        raise ValueError(f"request contains unknown field(s): {rendered}")

    if schema_version == REFERENCE_TRAVERSAL_REQUEST_SCHEMA_VERSION:
        return ReferenceTraversalRequest(schema_version=schema_version)

    raw_targets = decoded["externalTargets"]
    if not isinstance(raw_targets, list):
        raise ValueError("request field 'externalTargets' must be an array")
    targets = tuple(
        _normalize_external_target(value, index)
        for index, value in enumerate(raw_targets)
    )
    ordered = tuple(sorted(targets, key=_external_target_key))
    _validate_external_target_conflicts(ordered)
    return ReferenceTraversalRequestV2(
        schema_version=schema_version,
        external_targets=ordered,
    )


def _exact_non_empty_string(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or "\x00" in value
    ):
        raise ValueError(
            f"mapping field {field!r} must be an exact non-empty string"
        )
    return value


def _canonical_target_path(value: object) -> str:
    result = _exact_non_empty_string(value, "targetDocumentPath")
    if (
        result.startswith(("/", "\\"))
        or "\\" in result
        or (len(result) >= 2 and result[1] == ":")
        or posixpath.normpath(result) != result
        or result in {".", ".."}
        or result.startswith("../")
    ):
        raise ValueError(
            "mapping field 'targetDocumentPath' must be a canonical "
            "contract-relative slash-separated path"
        )
    return result


def _normalize_external_target(
    value: object, index: int
) -> ReferenceTraversalExternalTarget:
    if not isinstance(value, dict):
        raise ValueError(f"externalTargets[{index}] must be a JSON object")
    expected = set(_EXTERNAL_TARGET_FIELDS)
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise ValueError(
            f"externalTargets[{index}] requires field {sorted(missing)[0]!r}"
        )
    if unknown:
        rendered = ", ".join(repr(field) for field in sorted(unknown))
        raise ValueError(
            f"externalTargets[{index}] contains unknown field(s): {rendered}"
        )
    mechanism = _exact_non_empty_string(
        value["referenceMechanism"], "referenceMechanism"
    )
    if mechanism not in _SUPPORTED_REFERENCE_MECHANISMS:
        raise ValueError(f"unsupported reference mechanism {mechanism!r}")
    return ReferenceTraversalExternalTarget(
        source_object_name=_exact_non_empty_string(
            value["sourceObjectName"], "sourceObjectName"
        ),
        source_property=_exact_non_empty_string(
            value["sourceProperty"], "sourceProperty"
        ),
        reference_mechanism=mechanism,
        target_object_name=_exact_non_empty_string(
            value["targetObjectName"], "targetObjectName"
        ),
        target_document_path=_canonical_target_path(value["targetDocumentPath"]),
    )


def _external_target_key(value: ReferenceTraversalExternalTarget) -> tuple[str, ...]:
    return (
        value.source_object_name,
        value.source_property,
        value.reference_mechanism,
        value.target_object_name,
        value.target_document_path,
    )


def _validate_external_target_conflicts(
    values: tuple[ReferenceTraversalExternalTarget, ...],
) -> None:
    seen_entries: set[tuple[str, ...]] = set()
    seen_lookup: dict[tuple[str, ...], tuple[str, str]] = {}
    property_targets: dict[tuple[str, ...], set[str]] = {}
    for value in values:
        entry_key = _external_target_key(value)
        if entry_key in seen_entries:
            raise ValueError("externalTargets contains an exact duplicate entry")
        seen_entries.add(entry_key)
        property_key = entry_key[:3]
        lookup_key = entry_key[:4]
        identity = (value.target_document_path, value.target_object_name)
        previous = seen_lookup.get(lookup_key)
        if previous is not None and previous != identity:
            raise ValueError(
                "externalTargets lookup coordinate has conflicting target identities"
            )
        seen_lookup[lookup_key] = identity
        targets = property_targets.setdefault(property_key, set())
        if value.target_object_name in targets:
            raise ValueError("externalTargets contains a duplicate target object name")
        targets.add(value.target_object_name)
        if (
            value.reference_mechanism not in _LIST_REFERENCE_MECHANISMS
            and len(targets) > 1
        ):
            raise ValueError(
                "single-target reference mechanism has multiple mapped targets"
            )


def load_reference_traversal_request(
    path: str | Path,
) -> ReferenceTraversalRequest:
    """Load the closed version-1 request schema without runtime side effects."""

    request_path = Path(path)
    try:
        raw_text = request_path.read_bytes().decode("utf-8")
        decoded = _decode_request(raw_text)
        return _normalize_request(decoded)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ReferenceTraversalRequestError(
            f"invalid reference traversal request {request_path}: {exc}"
        ) from exc


__all__ = [
    "REFERENCE_TRAVERSAL_OUTPUT_FILENAME",
    "REFERENCE_TRAVERSAL_REQUEST_CLI_FLAG",
    "REFERENCE_TRAVERSAL_REQUEST_FILENAME",
    "REFERENCE_TRAVERSAL_REQUEST_SCHEMA_VERSION",
    "REFERENCE_TRAVERSAL_REQUEST_SCHEMA_VERSION_V2",
    "ReferenceTraversalExternalTarget",
    "ReferenceTraversalRequest",
    "ReferenceTraversalRequestV2",
    "ReferenceTraversalRequestError",
    "load_reference_traversal_request",
]
