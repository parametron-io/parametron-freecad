"""Strict contract boundary for Engine occurrence request sidecars."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parametron_freecad.common.strict_json import StrictJsonError, load_strict_json_file

OCCURRENCE_REQUEST_FILENAME = "prm.occurrence-request.json"
OCCURRENCE_REQUEST_SCHEMA_VERSION = "1.0"
OCCURRENCE_MECHANISM_DIRECT_MEMBER = "freecad-1.1.4-assembly-group-individual-link"
OCCURRENCE_REQUIREMENT_OPTIONAL = "optional"
OCCURRENCE_REQUIREMENT_COMPLETE = "complete"
OCCURRENCE_RESOURCE_KIND_MODEL = "model"
OCCURRENCE_NATIVE_KIND_OBJECT = "object"
OCCURRENCE_MAX_CONTEXT_FRAMES = 16

_REQUEST_FIELDS = frozenset({"schemaVersion", "requirement", "scope"})
_SCOPE_FIELDS = frozenset({"parent", "context", "mechanism"})
_ENTITY_REQUIRED_FIELDS = frozenset({"resource", "nativeKind", "name"})
_ENTITY_OPTIONAL_FIELDS = frozenset({"semanticId"})
_RESOURCE_FIELDS = frozenset({"projectId", "kind", "logicalId"})
_CONTEXT_FRAME_FIELDS = frozenset({"parent", "member"})

# FreeCAD native object names cannot contain these characters. Rejecting them
# keeps the request identical to the Engine-owned entity contract.
_NATIVE_NAME_REJECTED_CHARACTERS = frozenset("\x00/\\. \t\r\n")


class OccurrenceRequestError(ValueError):
    """Raised when an occurrence request cannot be discovered or consumed."""


@dataclass(frozen=True, slots=True)
class OccurrenceResourceIdentity:
    """Declared logical resource identity for one occurrence entity."""

    project_id: str
    kind: str
    logical_id: str

    def to_payload(self) -> dict[str, str]:
        return {
            "projectId": self.project_id,
            "kind": self.kind,
            "logicalId": self.logical_id,
        }


@dataclass(frozen=True, slots=True)
class OccurrenceEntity:
    """Resource-qualified native object identity."""

    resource: OccurrenceResourceIdentity
    native_kind: str
    name: str
    semantic_id: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "resource": self.resource.to_payload(),
            "nativeKind": self.native_kind,
            "name": self.name,
        }
        if self.semantic_id:
            payload["semanticId"] = self.semantic_id
        return payload


@dataclass(frozen=True, slots=True)
class OccurrenceContextFrame:
    """Bounded enclosing instance coordinate; context only, not membership."""

    parent: OccurrenceEntity
    member: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "parent": self.parent.to_payload(),
            "member": self.member,
        }


@dataclass(frozen=True, slots=True)
class OccurrenceScope:
    """The explicitly requested native occurrence scope."""

    parent: OccurrenceEntity
    context: tuple[OccurrenceContextFrame, ...]
    mechanism: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "parent": self.parent.to_payload(),
            "context": [frame.to_payload() for frame in self.context],
            "mechanism": self.mechanism,
        }


@dataclass(frozen=True, slots=True)
class OccurrenceRequest:
    """Immutable strict occurrence request."""

    schema_version: str
    requirement: str
    scope: OccurrenceScope


def discover_occurrence_request(working_copy: str | Path) -> Path | None:
    """Return the confined request path when the working copy provides one."""
    root = Path(working_copy).expanduser().resolve(strict=False)
    candidate = root / OCCURRENCE_REQUEST_FILENAME

    if candidate.is_symlink():
        raise OccurrenceRequestError("occurrence request must not be a symbolic link")
    if not candidate.exists():
        return None
    if not candidate.is_file():
        raise OccurrenceRequestError("occurrence request must be a regular file")
    return candidate


def load_occurrence_request(path: str | Path) -> OccurrenceRequest:
    """Load and strictly validate one occurrence request file."""
    request_path = Path(path)
    try:
        decoded = load_strict_json_file(request_path)
    except StrictJsonError as exc:
        raise OccurrenceRequestError(f"occurrence request is invalid: {exc}") from exc
    try:
        return _normalize_request(decoded)
    except OccurrenceRequestError:
        raise
    except ValueError as exc:
        raise OccurrenceRequestError(f"occurrence request is invalid: {exc}") from exc


def _normalize_request(decoded: Any) -> OccurrenceRequest:
    if not isinstance(decoded, dict):
        raise OccurrenceRequestError("occurrence request root must be a JSON object")

    _require_exact_fields(decoded, _REQUEST_FIELDS, "occurrence request")

    schema_version = decoded["schemaVersion"]
    if schema_version != OCCURRENCE_REQUEST_SCHEMA_VERSION:
        raise OccurrenceRequestError(
            "occurrence request schemaVersion must equal "
            f"{OCCURRENCE_REQUEST_SCHEMA_VERSION!r}"
        )

    requirement = decoded["requirement"]
    if requirement not in (
        OCCURRENCE_REQUIREMENT_OPTIONAL,
        OCCURRENCE_REQUIREMENT_COMPLETE,
    ):
        raise OccurrenceRequestError(
            "occurrence request requirement must be 'optional' or 'complete'"
        )

    scope = _normalize_scope(decoded["scope"], "occurrence request scope")

    return OccurrenceRequest(
        schema_version=schema_version,
        requirement=requirement,
        scope=scope,
    )


def _normalize_scope(value: Any, context: str) -> OccurrenceScope:
    if not isinstance(value, dict):
        raise OccurrenceRequestError(f"{context} must be a JSON object")

    _require_exact_fields(value, _SCOPE_FIELDS, context)

    parent = _normalize_entity(value["parent"], f"{context}.parent")
    mechanism = _exact_text(value["mechanism"], f"{context}.mechanism")

    raw_context = value["context"]
    if not isinstance(raw_context, list):
        raise OccurrenceRequestError(f"{context}.context must be an array")
    if len(raw_context) > OCCURRENCE_MAX_CONTEXT_FRAMES:
        raise OccurrenceRequestError(
            f"{context}.context must contain at most "
            f"{OCCURRENCE_MAX_CONTEXT_FRAMES} frames"
        )

    frames = tuple(
        _normalize_context_frame(frame, f"{context}.context[{index}]")
        for index, frame in enumerate(raw_context)
    )
    _validate_context_uniqueness(parent, frames, context)

    return OccurrenceScope(
        parent=parent,
        context=frames,
        mechanism=mechanism,
    )


def _normalize_context_frame(value: Any, context: str) -> OccurrenceContextFrame:
    if not isinstance(value, dict):
        raise OccurrenceRequestError(f"{context} must be a JSON object")

    _require_exact_fields(value, _CONTEXT_FRAME_FIELDS, context)

    return OccurrenceContextFrame(
        parent=_normalize_entity(value["parent"], f"{context}.parent"),
        member=_native_name(value["member"], f"{context}.member"),
    )


def _normalize_entity(value: Any, context: str) -> OccurrenceEntity:
    if not isinstance(value, dict):
        raise OccurrenceRequestError(f"{context} must be a JSON object")

    _require_exact_fields(
        value,
        _ENTITY_REQUIRED_FIELDS,
        context,
        optional=_ENTITY_OPTIONAL_FIELDS,
    )

    resource = _normalize_resource(value["resource"], f"{context}.resource")
    native_kind = value["nativeKind"]
    if native_kind != OCCURRENCE_NATIVE_KIND_OBJECT:
        raise OccurrenceRequestError(
            f"{context}.nativeKind must equal {OCCURRENCE_NATIVE_KIND_OBJECT!r}"
        )
    semantic_id = ""
    if "semanticId" in value:
        semantic_id = _exact_string(value["semanticId"], f"{context}.semanticId")

    return OccurrenceEntity(
        resource=resource,
        native_kind=native_kind,
        name=_native_name(value["name"], f"{context}.name"),
        semantic_id=semantic_id,
    )


def _normalize_resource(value: Any, context: str) -> OccurrenceResourceIdentity:
    if not isinstance(value, dict):
        raise OccurrenceRequestError(f"{context} must be a JSON object")

    _require_exact_fields(value, _RESOURCE_FIELDS, context)

    kind = value["kind"]
    if kind != OCCURRENCE_RESOURCE_KIND_MODEL:
        raise OccurrenceRequestError(
            f"{context}.kind must equal {OCCURRENCE_RESOURCE_KIND_MODEL!r}"
        )

    return OccurrenceResourceIdentity(
        project_id=_exact_text(value["projectId"], f"{context}.projectId"),
        kind=kind,
        logical_id=_exact_text(value["logicalId"], f"{context}.logicalId"),
    )


def _validate_context_uniqueness(
    parent: OccurrenceEntity,
    frames: tuple[OccurrenceContextFrame, ...],
    context: str,
) -> None:
    parent_key = _entity_key(parent)
    seen = {parent_key}
    for index, frame in enumerate(frames):
        key = _entity_key(frame.parent)
        if key in seen:
            raise OccurrenceRequestError(
                f"{context}.context[{index}] repeats or cycles a parent entity"
            )
        seen.add(key)


def _entity_key(entity: OccurrenceEntity) -> tuple[str, str, str, str]:
    resource = entity.resource
    return (
        resource.project_id,
        resource.kind,
        resource.logical_id,
        entity.name,
    )


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
        raise OccurrenceRequestError(f"{context} requires field {sorted(missing)[0]!r}")
    unknown = actual - required - optional
    if unknown:
        rendered = ", ".join(repr(field) for field in sorted(unknown))
        raise OccurrenceRequestError(f"{context} contains unknown field(s): {rendered}")


def _exact_text(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or "\x00" in value
    ):
        raise OccurrenceRequestError(f"{field} must be a non-empty unspaced string")
    return value


def _exact_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or value.strip() != value or "\x00" in value:
        raise OccurrenceRequestError(f"{field} must be an unspaced string")
    return value


def _native_name(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or any(character in _NATIVE_NAME_REJECTED_CHARACTERS for character in value)
    ):
        raise OccurrenceRequestError(f"{field} must be an exact native object name")
    return value


__all__ = [
    "OCCURRENCE_MECHANISM_DIRECT_MEMBER",
    "OCCURRENCE_MAX_CONTEXT_FRAMES",
    "OCCURRENCE_NATIVE_KIND_OBJECT",
    "OCCURRENCE_REQUEST_FILENAME",
    "OCCURRENCE_REQUEST_SCHEMA_VERSION",
    "OCCURRENCE_REQUIREMENT_COMPLETE",
    "OCCURRENCE_REQUIREMENT_OPTIONAL",
    "OCCURRENCE_RESOURCE_KIND_MODEL",
    "OccurrenceContextFrame",
    "OccurrenceEntity",
    "OccurrenceRequest",
    "OccurrenceRequestError",
    "OccurrenceResourceIdentity",
    "OccurrenceScope",
    "discover_occurrence_request",
    "load_occurrence_request",
]
