"""Declared resource inventory for one FreeCAD execution attempt."""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parametron_freecad.common.paths import (
    require_child_path,
    require_existing_directory,
    resolve_path,
)
from parametron_freecad.common.strict_json import StrictJsonError, load_strict_json_file

INTEGRITY_REQUEST_ENVIRONMENT_VARIABLE = "PARAMETRON_RUNTIME_INTEGRITY_REQUEST"
INTEGRITY_REQUEST_SCHEMA_VERSION = "1.0"
INTEGRITY_REQUEST_FILENAME = "prm.integrity-request.json"
RESOURCE_KIND_MODEL = "model"

NATIVE_RESOURCE_STATUS_RESOLVED = "resolved"
NATIVE_RESOURCE_STATUS_UNDECLARED = "undeclared"
NATIVE_RESOURCE_STATUS_AMBIGUOUS = "ambiguous"
NATIVE_RESOURCE_STATUS_MISSING = "missing"
NATIVE_RESOURCE_STATUS_UNAVAILABLE = "unavailable"

_REQUEST_FIELDS = frozenset({"schemaVersion", "resources"})
_RESOURCE_FIELDS = frozenset(
    {
        "logicalId",
        "kind",
        "materializedCoordinate",
        "baselineSha256",
        "expectsPersistedResult",
    }
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ResourceInventoryError(ValueError):
    """Raised when a declared resource inventory cannot be consumed."""


@dataclass(frozen=True, slots=True)
class ResourceBinding:
    """One declared resource joined to its attempt-relative coordinate."""

    logical_id: str
    kind: str
    materialized_coordinate: str
    baseline_sha256: str
    expects_persisted_result: bool
    resolved_path: Path


@dataclass(frozen=True, slots=True)
class NativeResourceResolution:
    """Result of joining a native document identity to the declared inventory.

    A missing result retains the matched binding so callers can preserve the
    declared identity while reporting the missing native file. Consumers must
    treat ``status`` as the authoritative state.
    """

    status: str
    binding: ResourceBinding | None = None
    diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class ResourceInventory:
    """Immutable declared resources for one attempt working copy."""

    working_copy: Path
    bindings: tuple[ResourceBinding, ...]

    @property
    def persisted_result_binding(self) -> ResourceBinding:
        for binding in self.bindings:
            if binding.expects_persisted_result:
                return binding
        raise ResourceInventoryError(
            "resource inventory has no persisted-result resource"
        )

    @property
    def selected_source_binding(self) -> ResourceBinding:
        return self.persisted_result_binding

    def binding_for_logical_id(self, logical_id: str) -> ResourceBinding | None:
        for binding in self.bindings:
            if binding.logical_id == logical_id:
                return binding
        return None

    def binding_for_coordinate(self, coordinate: str) -> ResourceBinding | None:
        for binding in self.bindings:
            if binding.materialized_coordinate == coordinate:
                return binding
        return None

    def resolve_native_document(self, document: Any) -> NativeResourceResolution:
        """Join a native document object to one declared resource."""
        file_name = getattr(document, "FileName", None)
        if not isinstance(file_name, (str, Path)):
            return NativeResourceResolution(
                status=NATIVE_RESOURCE_STATUS_UNAVAILABLE,
                diagnostic="native document has no stable file identity",
            )
        return self.resolve_native_document_path(file_name)

    def resolve_native_document_path(
        self,
        file_name: str | Path | None,
    ) -> NativeResourceResolution:
        """Join a native document path to one declared resource."""
        if file_name is None:
            return NativeResourceResolution(
                status=NATIVE_RESOURCE_STATUS_UNAVAILABLE,
                diagnostic="native document has no stable file identity",
            )
        if not isinstance(file_name, (str, Path)):
            return NativeResourceResolution(
                status=NATIVE_RESOURCE_STATUS_UNAVAILABLE,
                diagnostic="native document has no stable file identity",
            )

        candidate = Path(file_name).expanduser()
        if not str(candidate) or not candidate.is_absolute():
            return NativeResourceResolution(
                status=NATIVE_RESOURCE_STATUS_UNAVAILABLE,
                diagnostic="native document path is not absolute",
            )

        resolved = resolve_path(candidate)
        matches = tuple(
            binding for binding in self.bindings if binding.resolved_path == resolved
        )
        if len(matches) == 1:
            binding = matches[0]
            if not binding.resolved_path.is_file():
                return NativeResourceResolution(
                    status=NATIVE_RESOURCE_STATUS_MISSING,
                    binding=binding,
                    diagnostic=(
                        "native document file is missing or is not a regular file"
                    ),
                )
            return NativeResourceResolution(
                status=NATIVE_RESOURCE_STATUS_RESOLVED,
                binding=binding,
            )
        if not matches:
            return NativeResourceResolution(
                status=NATIVE_RESOURCE_STATUS_UNDECLARED,
                diagnostic="native document is not a declared resource",
            )
        return NativeResourceResolution(
            status=NATIVE_RESOURCE_STATUS_AMBIGUOUS,
            diagnostic="native document matches multiple declared resources",
        )


def load_resource_inventory(
    request_path: str | Path,
    *,
    working_copy: str | Path,
    expected_source_path: str | Path | None = None,
) -> ResourceInventory:
    """Load one Engine integrity request as a confined resource inventory."""
    resolved_request_path = _validate_request_path(request_path)
    resolved_working_copy = _resolve_working_copy(working_copy)
    resolved_expected_source = _resolve_expected_source_path(
        expected_source_path,
        resolved_working_copy,
    )

    try:
        decoded = load_strict_json_file(resolved_request_path)
    except StrictJsonError as exc:
        raise ResourceInventoryError(f"integrity request is invalid: {exc}") from exc

    return _normalize_request(
        decoded,
        working_copy=resolved_working_copy,
        expected_source_path=resolved_expected_source,
    )


def _validate_request_path(request_path: str | Path) -> Path:
    if isinstance(request_path, str):
        if request_path == "" or request_path.strip() == "":
            raise ResourceInventoryError("integrity request path must not be empty")
        if request_path != request_path.strip():
            raise ResourceInventoryError(
                "integrity request path must not contain surrounding whitespace"
            )

    candidate = Path(request_path).expanduser()
    if not candidate.is_absolute():
        raise ResourceInventoryError("integrity request path must be absolute")
    if candidate.is_symlink():
        raise ResourceInventoryError(
            "integrity request path must not be a symbolic link"
        )
    if not candidate.is_file():
        raise ResourceInventoryError(
            "integrity request path must reference an existing regular file"
        )
    return candidate


def _resolve_working_copy(working_copy: str | Path) -> Path:
    try:
        return require_existing_directory(working_copy)
    except ValueError as exc:
        raise ResourceInventoryError(
            "working copy must be an existing directory"
        ) from exc


def _resolve_expected_source_path(
    expected_source_path: str | Path | None,
    working_copy: Path,
) -> Path | None:
    if expected_source_path is None:
        return None

    candidate = resolve_path(expected_source_path, base=working_copy)
    try:
        return require_child_path(working_copy, candidate)
    except ValueError as exc:
        raise ResourceInventoryError(
            "selected source document must resolve inside the working copy"
        ) from exc


def _normalize_request(
    decoded: Any,
    *,
    working_copy: Path,
    expected_source_path: Path | None,
) -> ResourceInventory:
    if not isinstance(decoded, dict):
        raise ResourceInventoryError("integrity request root must be a JSON object")

    _require_exact_fields(decoded, _REQUEST_FIELDS, "integrity request")

    if decoded["schemaVersion"] != INTEGRITY_REQUEST_SCHEMA_VERSION:
        raise ResourceInventoryError(
            "integrity request schemaVersion must equal "
            f"{INTEGRITY_REQUEST_SCHEMA_VERSION!r}"
        )

    resources = decoded["resources"]
    if not isinstance(resources, list) or not resources:
        raise ResourceInventoryError(
            "integrity request resources must be a non-empty array"
        )

    bindings: list[ResourceBinding] = []
    persisted_results = 0
    previous_logical_id: str | None = None
    coordinates: dict[str, str] = {}
    resolved_paths: dict[Path, str] = {}

    for index, raw_resource in enumerate(resources):
        context = f"integrity request resources[{index}]"
        if not isinstance(raw_resource, dict):
            raise ResourceInventoryError(f"{context} must be a JSON object")

        _require_exact_fields(raw_resource, _RESOURCE_FIELDS, context)

        logical_id = _exact_text(
            raw_resource["logicalId"],
            f"{context}.logicalId",
        )
        if previous_logical_id is not None and logical_id <= previous_logical_id:
            raise ResourceInventoryError(
                "integrity request resources must be unique and ordered by logical ID"
            )
        previous_logical_id = logical_id

        if raw_resource["kind"] != RESOURCE_KIND_MODEL:
            raise ResourceInventoryError(
                f"{context}.kind must equal {RESOURCE_KIND_MODEL!r}"
            )

        coordinate = _canonical_coordinate(
            raw_resource["materializedCoordinate"],
            f"{context}.materializedCoordinate",
        )
        digest = _canonical_sha256(
            raw_resource["baselineSha256"],
            f"{context}.baselineSha256",
        )
        expects_persisted_result = raw_resource["expectsPersistedResult"]
        if not isinstance(expects_persisted_result, bool):
            raise ResourceInventoryError(
                f"{context}.expectsPersistedResult must be a boolean"
            )
        if expects_persisted_result:
            persisted_results += 1

        if coordinate in coordinates:
            raise ResourceInventoryError(
                f"{context}.materializedCoordinate is already bound"
            )
        for previous_coordinate in coordinates:
            if coordinate.startswith(
                previous_coordinate + "/"
            ) or previous_coordinate.startswith(coordinate + "/"):
                raise ResourceInventoryError(
                    f"{context}.materializedCoordinate conflicts with another "
                    "declared resource coordinate"
                )
        coordinates[coordinate] = logical_id

        resolved_path = _resolve_coordinate_path(coordinate, working_copy)
        if resolved_path in resolved_paths:
            raise ResourceInventoryError(
                f"{context}.materializedCoordinate resolves to the same "
                "working-copy path as another declared resource"
            )
        resolved_paths[resolved_path] = logical_id

        bindings.append(
            ResourceBinding(
                logical_id=logical_id,
                kind=RESOURCE_KIND_MODEL,
                materialized_coordinate=coordinate,
                baseline_sha256=digest,
                expects_persisted_result=expects_persisted_result,
                resolved_path=resolved_path,
            )
        )

    if persisted_results != 1:
        raise ResourceInventoryError(
            "integrity request must expect exactly one persisted result"
        )

    inventory = ResourceInventory(
        working_copy=working_copy,
        bindings=tuple(bindings),
    )

    if expected_source_path is not None:
        persisted = inventory.persisted_result_binding
        if persisted.resolved_path != expected_source_path:
            raise ResourceInventoryError(
                "selected source document is not the integrity request "
                "persisted-result resource"
            )

    return inventory


def _require_exact_fields(
    value: dict[str, Any],
    expected: frozenset[str],
    context: str,
) -> None:
    actual = set(value)
    missing = expected - actual
    if missing:
        raise ResourceInventoryError(f"{context} requires field {sorted(missing)[0]!r}")
    unknown = actual - expected
    if unknown:
        rendered = ", ".join(repr(field) for field in sorted(unknown))
        raise ResourceInventoryError(f"{context} contains unknown field(s): {rendered}")


def _exact_text(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or "\x00" in value
    ):
        raise ResourceInventoryError(f"{field} must be a non-empty unspaced string")
    return value


def _canonical_coordinate(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or "\x00" in value
        or "\\" in value
        or posixpath.isabs(value)
        or (len(value) >= 3 and value[1] == ":" and value[2] == "/")
        or posixpath.normpath(value) != value
        or value in {".", ".."}
        or value.startswith("../")
    ):
        raise ResourceInventoryError(f"{field} must be a canonical relative coordinate")
    return value


def _canonical_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ResourceInventoryError(
            f"{field} must be a canonical lowercase SHA-256 digest"
        )
    return value


def _resolve_coordinate_path(coordinate: str, working_copy: Path) -> Path:
    candidate = resolve_path(coordinate, base=working_copy)
    try:
        return require_child_path(working_copy, candidate)
    except ValueError as exc:
        raise ResourceInventoryError(
            f"resource coordinate escapes the working copy: {coordinate!r}"
        ) from exc


__all__ = [
    "INTEGRITY_REQUEST_ENVIRONMENT_VARIABLE",
    "INTEGRITY_REQUEST_FILENAME",
    "INTEGRITY_REQUEST_SCHEMA_VERSION",
    "NATIVE_RESOURCE_STATUS_AMBIGUOUS",
    "NATIVE_RESOURCE_STATUS_MISSING",
    "NATIVE_RESOURCE_STATUS_RESOLVED",
    "NATIVE_RESOURCE_STATUS_UNAVAILABLE",
    "NATIVE_RESOURCE_STATUS_UNDECLARED",
    "RESOURCE_KIND_MODEL",
    "NativeResourceResolution",
    "ResourceBinding",
    "ResourceInventory",
    "ResourceInventoryError",
    "load_resource_inventory",
]
