"""Schema 1.0 capture contract validation for ``prm.cad.json`` drafts.

This module validates the Engine-owned CAD capture contract shape and its
referential/structural invariants without importing FreeCAD. It is deliberately
stricter than the runtime parser in one authoring-specific area: semantic names
must be DSL identifiers and must not collide, and stable IDs must be exact and
unique. That authoring policy lives in
:mod:`parametron_freecad.capture.naming`.

Validation order is intentional and deterministic:

1. closed-field/required-field/scalar shape of the whole document;
2. semantic-name and stable-ID policy;
3. component, feature, group, parameter, metadata, drawing, sheet,
   identity-source, and structure reference consistency.

A document with a shape problem reports only shape problems. A document with a
policy problem reports the policy failure before reference checks. This keeps
failure classification stable for callers.
"""

from __future__ import annotations

import math
import posixpath
import re
from collections.abc import Callable, Mapping
from typing import Any

from parametron_freecad.capture.errors import CaptureContractError
from parametron_freecad.capture.naming import validate_capture_policy

CAPTURE_SCHEMA_VERSION = "1.0"

TOP_LEVEL_FIELDS = (
    "schemaVersion",
    "captureId",
    "adapter",
    "cadSystem",
    "sourceDocument",
    "rootProduct",
    "annotations",
    "entities",
    "structure",
)
NAMED_VERSION_FIELDS = ("name", "version")
SOURCE_DOCUMENT_FIELDS = ("logicalId", "path", "fingerprint")
ROOT_PRODUCT_FIELDS = ("id",)
ANNOTATION_FIELDS = ("description", "comment", "purpose")
ENTITY_REGISTRY_FIELDS = (
    "components",
    "features",
    "relationships",
    "parameterGroups",
    "parameters",
    "metadata",
    "drawings",
)
IDENTITY_SOURCE_FIELDS = (
    "kind",
    "path",
    "ownerScopedKey",
    "groupScopedKey",
    "nativeRef",
)
TARGETABILITY_FIELDS = ("suppress", "unsuppress", "hide", "unhide", "delete")
SOURCE_FILE_FIELDS = ("path",)
STRUCTURE_FIELDS = ("rootComponentId", "nodes")
STRUCTURE_NODE_FIELDS = ("componentId", "parentComponentId", "children")

COMPONENT_FIELDS = (
    "id",
    "kind",
    "name",
    "displayName",
    "cadType",
    "quantity",
    "material",
    "identitySource",
    "stabilityClass",
    "sourceFile",
    "targetability",
    "annotations",
)
FEATURE_FIELDS = (
    "id",
    "componentId",
    "name",
    "displayName",
    "cadType",
    "identitySource",
    "stabilityClass",
    "targetability",
    "annotations",
)
RELATIONSHIP_FIELDS = (
    "id",
    "kind",
    "componentId",
    "name",
    "cadType",
    "endpoints",
    "identitySource",
    "stabilityClass",
    "targetability",
    "annotations",
)
PARAMETER_GROUP_FIELDS = (
    "id",
    "ownerComponentId",
    "name",
    "displayName",
    "groupKind",
    "cadType",
    "observable",
    "writable",
    "identitySource",
    "stabilityClass",
    "annotations",
)
PARAMETER_FIELDS = (
    "id",
    "ownerKind",
    "ownerId",
    "componentId",
    "name",
    "displayName",
    "cadType",
    "valueType",
    "observable",
    "writable",
    "currentValue",
    "unit",
    "identitySource",
    "stabilityClass",
    "annotations",
)
METADATA_FIELDS = (
    "id",
    "ownerKind",
    "ownerId",
    "componentId",
    "key",
    "displayName",
    "cadType",
    "valueType",
    "observable",
    "writable",
    "currentValue",
    "identitySource",
    "stabilityClass",
    "annotations",
)
DRAWING_FIELDS = (
    "id",
    "name",
    "displayName",
    "componentIds",
    "resource",
    "sheets",
    "identitySource",
)
DRAWING_RESOURCE_FIELDS = ("topology", "path")
DRAWING_SHEET_FIELDS = (
    "id",
    "name",
    "displayName",
    "order",
    "cadType",
    "identitySource",
)

_COMPONENT_KINDS = ("assembly", "part")
_RELATIONSHIP_KINDS = ("mate", "relationship")
_PARAMETER_OWNER_KINDS = ("group", "component", "feature")
_METADATA_OWNER_KINDS = ("component", "feature", "relationship")
_PARAMETER_GROUP_KINDS = ("varset", "design_table", "cad_native_group")
_VALUE_TYPES = ("number", "string", "boolean")
_STABILITY_CLASSES = ("stable", "conditionally_stable", "unstable")
_DRAWING_TOPOLOGIES = ("embedded", "separate")


def _join(path: str, field: str) -> str:
    return f"{path}.{field}" if path else field


def _location(path: str) -> str:
    return path if path else "root"


def validate_capture_document(value: object) -> None:
    """Validate a capture draft and raise a typed deterministic failure.

    ``value`` is a decoded mapping in the Engine schema 1.0 capture shape.
    Contract violations raise :class:`CaptureContractError`; semantic-name and
    stable-ID policy violations raise
    :class:`~parametron_freecad.capture.errors.CaptureNamePolicyError` or
    :class:`~parametron_freecad.capture.errors.CaptureIdPolicyError`.
    """

    shape_problems = _validate_shape(value)
    if shape_problems:
        raise CaptureContractError(shape_problems)

    if not isinstance(value, Mapping):
        raise CaptureContractError(("root must be an object",))

    validate_capture_policy(value)

    semantic_problems = _validate_semantics(value)
    if semantic_problems:
        raise CaptureContractError(semantic_problems)


def _validate_shape(value: object) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return ("root must be an object",)

    validator = _ShapeValidator()
    validator.allowed(value, "", TOP_LEVEL_FIELDS)

    schema_version = validator.required_string(value, "schemaVersion", "")
    if schema_version is not None and schema_version != CAPTURE_SCHEMA_VERSION:
        validator.add(f'schemaVersion must be "{CAPTURE_SCHEMA_VERSION}"')

    capture_id = validator.required_string(value, "captureId", "")
    if capture_id is not None and capture_id != capture_id.strip():
        validator.add("captureId must not have leading or trailing whitespace")

    validator.named_version(value, "adapter", "")
    validator.named_version(value, "cadSystem", "")
    validator.source_document(value, "")
    validator.root_product(value, "")
    validator.annotations(value, "")
    validator.entities(value, "")
    validator.structure(value, "")

    return tuple(validator.problems)


class _ShapeValidator:
    """Collect deterministic shape problems for one capture draft."""

    def __init__(self) -> None:
        self.problems: list[str] = []

    def add(self, message: str) -> None:
        self.problems.append(message)

    def allowed(
        self,
        value: Mapping[str, Any],
        location: str,
        allowed: tuple[str, ...],
    ) -> None:
        unknown = sorted(key for key in value if key not in allowed)
        for key in unknown:
            self.add(f'{_location(location)} has unknown field "{key}"')

    def required_object(
        self,
        value: Mapping[str, Any],
        field: str,
        path: str,
    ) -> Mapping[str, Any] | None:
        field_path = _join(path, field)
        if field not in value:
            self.add(f"{field_path} is required")
            return None
        candidate = value[field]
        if not isinstance(candidate, Mapping):
            self.add(f"{field_path} must be an object")
            return None
        return candidate

    def required_array(
        self,
        value: Mapping[str, Any],
        field: str,
        path: str,
    ) -> list[Any] | None:
        field_path = _join(path, field)
        if field not in value:
            self.add(f"{field_path} is required")
            return None
        candidate = value[field]
        if not isinstance(candidate, list):
            self.add(f"{field_path} must be an array")
            return None
        return candidate

    def required_string(
        self,
        value: Mapping[str, Any],
        field: str,
        path: str,
        *,
        allow_empty: bool = False,
    ) -> str | None:
        field_path = _join(path, field)
        if field not in value:
            self.add(f"{field_path} is required")
            return None
        candidate = value[field]
        if not isinstance(candidate, str):
            self.add(f"{field_path} must be a string")
            return None
        if not allow_empty and candidate.strip() == "":
            self.add(f"{field_path} is required")
            return None
        return candidate

    def optional_string(
        self,
        value: Mapping[str, Any],
        field: str,
        path: str,
        *,
        allow_empty: bool = False,
    ) -> str | None:
        if field not in value:
            return None
        field_path = _join(path, field)
        candidate = value[field]
        if not isinstance(candidate, str):
            self.add(f"{field_path} must be a string")
            return None
        if not allow_empty and candidate.strip() == "":
            self.add(f"{field_path} is required")
            return None
        return candidate

    def required_bool(
        self,
        value: Mapping[str, Any],
        field: str,
        path: str,
    ) -> bool | None:
        field_path = _join(path, field)
        if field not in value:
            self.add(f"{field_path} is required")
            return None
        candidate = value[field]
        if not isinstance(candidate, bool):
            self.add(f"{field_path} must be a boolean")
            return None
        return candidate

    def required_int(
        self,
        value: Mapping[str, Any],
        field: str,
        path: str,
    ) -> int | None:
        field_path = _join(path, field)
        if field not in value:
            self.add(f"{field_path} is required")
            return None
        candidate = value[field]
        if isinstance(candidate, bool) or not isinstance(candidate, int):
            self.add(f"{field_path} must be an integer")
            return None
        return candidate

    def named_version(
        self,
        value: Mapping[str, Any],
        field: str,
        path: str,
    ) -> None:
        location = _join(path, field)
        candidate = self.required_object(value, field, path)
        if candidate is None:
            return
        self.allowed(candidate, location, NAMED_VERSION_FIELDS)
        self.required_string(candidate, "name", location)
        version = self.required_string(
            candidate,
            "version",
            location,
            allow_empty=True,
        )
        if version is not None and version != "" and version.strip() == "":
            self.add(f"{location}.version must not be blank")

    def source_document(self, value: Mapping[str, Any], path: str) -> None:
        location = _join(path, "sourceDocument")
        candidate = self.required_object(value, "sourceDocument", path)
        if candidate is None:
            return
        self.allowed(candidate, location, SOURCE_DOCUMENT_FIELDS)
        for field in SOURCE_DOCUMENT_FIELDS:
            self.required_string(candidate, field, location)

    def root_product(self, value: Mapping[str, Any], path: str) -> None:
        location = _join(path, "rootProduct")
        candidate = self.required_object(value, "rootProduct", path)
        if candidate is None:
            return
        self.allowed(candidate, location, ROOT_PRODUCT_FIELDS)
        self.required_string(candidate, "id", location)

    def annotations(self, value: Mapping[str, Any], path: str) -> None:
        location = _join(path, "annotations")
        candidate = self.required_object(value, "annotations", path)
        if candidate is None:
            return
        self.allowed(candidate, location, ANNOTATION_FIELDS)
        for field in ANNOTATION_FIELDS:
            self.required_string(candidate, field, location, allow_empty=True)

    def identity_source(
        self,
        value: Mapping[str, Any],
        path: str,
    ) -> Mapping[str, Any] | None:
        if "identitySource" not in value:
            return None
        location = _join(path, "identitySource")
        candidate = value["identitySource"]
        if not isinstance(candidate, Mapping):
            self.add(f"{location} must be an object")
            return None
        self.allowed(candidate, location, IDENTITY_SOURCE_FIELDS)
        self.required_string(candidate, "kind", location)
        self.optional_string(candidate, "path", location)
        self.optional_string(candidate, "ownerScopedKey", location)
        self.optional_string(candidate, "groupScopedKey", location)
        self.optional_string(candidate, "nativeRef", location, allow_empty=True)
        return candidate

    def source_file(self, value: Mapping[str, Any], path: str) -> None:
        if "sourceFile" not in value:
            return
        location = _join(path, "sourceFile")
        candidate = value["sourceFile"]
        if not isinstance(candidate, Mapping):
            self.add(f"{location} must be an object")
            return
        self.allowed(candidate, location, SOURCE_FILE_FIELDS)
        self.required_string(candidate, "path", location)

    def stability_class(self, value: Mapping[str, Any], path: str) -> None:
        candidate = self.optional_string(value, "stabilityClass", path)
        if candidate is None:
            return
        if candidate not in _STABILITY_CLASSES:
            self.add(
                f"{path}.stabilityClass must be one of "
                '"stable", "conditionally_stable", or "unstable"'
            )

    def targetability(self, value: Mapping[str, Any], path: str) -> None:
        location = _join(path, "targetability")
        candidate = self.required_object(value, "targetability", path)
        if candidate is None:
            return
        self.allowed(candidate, location, TARGETABILITY_FIELDS)
        for field in TARGETABILITY_FIELDS:
            self.required_bool(candidate, field, location)

    def entities(self, value: Mapping[str, Any], path: str) -> None:
        location = _join(path, "entities")
        candidate = self.required_object(value, "entities", path)
        if candidate is None:
            return
        self.allowed(candidate, location, ENTITY_REGISTRY_FIELDS)

        self.entity_array(candidate, "components", location, self.component)
        self.entity_array(candidate, "features", location, self.feature)
        self.entity_array(candidate, "relationships", location, self.relationship)
        self.entity_array(
            candidate,
            "parameterGroups",
            location,
            self.parameter_group,
        )
        self.entity_array(candidate, "parameters", location, self.parameter)
        self.entity_array(candidate, "metadata", location, self.metadata)
        self.entity_array(candidate, "drawings", location, self.drawing)

    def entity_array(
        self,
        value: Mapping[str, Any],
        registry: str,
        path: str,
        validate_entity: Callable[[Mapping[str, Any], str], None],
    ) -> None:
        items = self.required_array(value, registry, path)
        if items is None:
            return
        for index, item in enumerate(items):
            location = f"{path}.{registry}[{index}]"
            if not isinstance(item, Mapping):
                self.add(f"{location} must be an object")
                continue
            validate_entity(item, location)

    def component(self, value: Mapping[str, Any], path: str) -> None:
        self.allowed(value, path, COMPONENT_FIELDS)
        self.required_string(value, "id", path)
        kind = self.required_string(value, "kind", path)
        if kind is not None and kind not in _COMPONENT_KINDS:
            self.add(f'{path}.kind must be one of "assembly" or "part"')
        self.required_string(value, "name", path)
        self.required_string(value, "displayName", path, allow_empty=True)
        self.required_string(value, "cadType", path)
        quantity = self.required_int(value, "quantity", path)
        if quantity is not None and quantity <= 0:
            self.add(f"{path}.quantity must be a positive integer")
        self.required_string(value, "material", path, allow_empty=True)
        identity = self.identity_source(value, path)
        self.stability_class(value, path)
        self.source_file(value, path)
        self.targetability(value, path)
        self.annotations(value, path)

        self.require_identity_kind(identity, path, "parent_scoped_path")
        self.require_identity_field(identity, path, "path")

    def feature(self, value: Mapping[str, Any], path: str) -> None:
        self.allowed(value, path, FEATURE_FIELDS)
        self.required_string(value, "id", path)
        self.required_string(value, "componentId", path)
        self.required_string(value, "name", path)
        self.required_string(value, "displayName", path, allow_empty=True)
        self.required_string(value, "cadType", path)
        identity = self.identity_source(value, path)
        self.stability_class(value, path)
        self.targetability(value, path)
        self.annotations(value, path)

        self.require_identity_kind(identity, path, "owner_scoped_key")
        self.require_identity_field(identity, path, "ownerScopedKey")

    def relationship(self, value: Mapping[str, Any], path: str) -> None:
        self.allowed(value, path, RELATIONSHIP_FIELDS)
        self.required_string(value, "id", path)
        kind = self.required_string(value, "kind", path)
        if kind is not None and kind not in _RELATIONSHIP_KINDS:
            self.add(f'{path}.kind must be one of "mate" or "relationship"')
        self.required_string(value, "componentId", path)
        self.required_string(value, "name", path)
        self.required_string(value, "cadType", path)
        endpoints = self.required_array(value, "endpoints", path)
        if endpoints is not None:
            for index, endpoint in enumerate(endpoints):
                if not isinstance(endpoint, str):
                    self.add(f"{path}.endpoints[{index}] must be a string")
                elif endpoint.strip() == "":
                    self.add(f"{path}.endpoints[{index}] is required")
        self.identity_source(value, path)
        self.stability_class(value, path)
        self.targetability(value, path)
        self.annotations(value, path)

    def parameter_group(self, value: Mapping[str, Any], path: str) -> None:
        self.allowed(value, path, PARAMETER_GROUP_FIELDS)
        self.required_string(value, "id", path)
        self.required_string(value, "ownerComponentId", path)
        self.required_string(value, "name", path)
        self.required_string(value, "displayName", path, allow_empty=True)
        group_kind = self.required_string(value, "groupKind", path)
        if group_kind is not None and group_kind not in _PARAMETER_GROUP_KINDS:
            self.add(
                f"{path}.groupKind must be one of "
                '"varset", "design_table", or "cad_native_group"'
            )
        self.required_string(value, "cadType", path)
        self.required_bool(value, "observable", path)
        self.required_bool(value, "writable", path)
        identity = self.identity_source(value, path)
        self.stability_class(value, path)
        self.annotations(value, path)

        self.require_identity_kind(identity, path, "owner_scoped_key")
        self.require_identity_field(identity, path, "ownerScopedKey")

    def parameter(self, value: Mapping[str, Any], path: str) -> None:
        self.allowed(value, path, PARAMETER_FIELDS)
        self.required_string(value, "id", path)
        owner_kind = self.required_string(value, "ownerKind", path)
        if owner_kind is not None and owner_kind not in _PARAMETER_OWNER_KINDS:
            self.add(
                f'{path}.ownerKind must be one of "group", "component", or "feature"'
            )
        self.required_string(value, "ownerId", path)
        self.required_string(value, "componentId", path)
        self.required_string(value, "name", path)
        self.required_string(value, "displayName", path, allow_empty=True)
        self.required_string(value, "cadType", path)
        value_type = self.required_string(value, "valueType", path)
        if value_type is not None and value_type not in _VALUE_TYPES:
            self.add(
                f'{path}.valueType must be one of "number", "string", or "boolean"'
            )
        self.required_bool(value, "observable", path)
        self.required_bool(value, "writable", path)
        self.current_value(value, path, value_type)
        self.optional_string(value, "unit", path)
        identity = self.identity_source(value, path)
        self.stability_class(value, path)
        self.annotations(value, path)

        if owner_kind in ("component", "feature"):
            self.require_identity_kind(identity, path, "owner_scoped_key")
            self.require_identity_field(identity, path, "ownerScopedKey")
        elif owner_kind == "group":
            self.require_identity_kind(identity, path, "owner_scoped_key")
            self.require_identity_field(identity, path, "ownerScopedKey")
            self.require_identity_field(identity, path, "groupScopedKey")

    def metadata(self, value: Mapping[str, Any], path: str) -> None:
        self.allowed(value, path, METADATA_FIELDS)
        self.required_string(value, "id", path)
        owner_kind = self.required_string(value, "ownerKind", path)
        if owner_kind is not None and owner_kind not in _METADATA_OWNER_KINDS:
            self.add(
                f'{path}.ownerKind must be one of "component", "feature", '
                'or "relationship"'
            )
        self.required_string(value, "ownerId", path)
        self.required_string(value, "componentId", path)
        key = self.required_string(value, "key", path)
        if key is not None and (key != key.strip() or "\x00" in key):
            self.add(f"{path}.key must be an exact native property key")
        self.required_string(value, "displayName", path, allow_empty=True)
        self.required_string(value, "cadType", path)
        value_type = self.required_string(value, "valueType", path)
        if value_type is not None and value_type not in _VALUE_TYPES:
            self.add(
                f'{path}.valueType must be one of "number", "string", or "boolean"'
            )
        self.required_bool(value, "observable", path)
        self.required_bool(value, "writable", path)
        self.current_value(value, path, value_type)
        identity = self.identity_source(value, path)
        self.stability_class(value, path)
        self.annotations(value, path)

        self.require_identity_kind(identity, path, "owner_scoped_key")
        self.require_identity_field(identity, path, "ownerScopedKey")

    def drawing(self, value: Mapping[str, Any], path: str) -> None:
        self.allowed(value, path, DRAWING_FIELDS)
        self.required_string(value, "id", path)
        self.required_string(value, "name", path)
        self.required_string(value, "displayName", path, allow_empty=True)
        component_ids = self.required_array(value, "componentIds", path)
        if component_ids is not None:
            for index, component_id in enumerate(component_ids):
                if not isinstance(component_id, str):
                    self.add(f"{path}.componentIds[{index}] must be a string")
                elif component_id.strip() == "":
                    self.add(f"{path}.componentIds[{index}] is required")
        self.drawing_resource(value, path)
        self.drawing_sheets(value, path)
        identity = self.identity_source(value, path)
        self.require_drawing_identity_source(identity, path)

    def drawing_resource(self, value: Mapping[str, Any], path: str) -> None:
        location = _join(path, "resource")
        candidate = self.required_object(value, "resource", path)
        if candidate is None:
            return
        self.allowed(candidate, location, DRAWING_RESOURCE_FIELDS)
        topology = self.required_string(candidate, "topology", location)
        path_value = self.optional_string(
            candidate,
            "path",
            location,
            allow_empty=True,
        )
        if topology is not None and topology not in _DRAWING_TOPOLOGIES:
            self.add(f'{location}.topology must be one of "embedded" or "separate"')
        if topology == "embedded" and path_value:
            self.add(f'{location}.path must be empty when topology is "embedded"')
        if topology == "separate":
            if path_value is None or path_value.strip() == "":
                self.add(f'{location}.path is required when topology is "separate"')
            elif not _is_canonical_relative_path(path_value):
                self.add(f"{location}.path must be a canonical project-relative path")

    def drawing_sheets(self, value: Mapping[str, Any], path: str) -> None:
        sheets = self.required_array(value, "sheets", path)
        if sheets is None:
            return
        for index, sheet in enumerate(sheets):
            location = f"{path}.sheets[{index}]"
            if not isinstance(sheet, Mapping):
                self.add(f"{location} must be an object")
                continue
            self.drawing_sheet(sheet, location)

    def drawing_sheet(self, value: Mapping[str, Any], path: str) -> None:
        self.allowed(value, path, DRAWING_SHEET_FIELDS)
        self.required_string(value, "id", path)
        self.required_string(value, "name", path)
        self.required_string(value, "displayName", path, allow_empty=True)
        order = self.required_int(value, "order", path)
        if order is not None and order < 1:
            self.add(f"{path}.order must be a positive integer")
        self.required_string(value, "cadType", path)
        identity = self.required_identity_source(value, path)
        if identity is None:
            return
        kind = identity.get("kind")
        if isinstance(kind, str) and kind.strip() != "" and kind != "native_ref":
            self.add(f'{path}.identitySource.kind must be "native_ref"')
        native_ref = identity.get("nativeRef")
        if not isinstance(native_ref, str) or native_ref.strip() == "":
            self.add(f"{path}.identitySource.nativeRef is required")

    def required_identity_source(
        self,
        value: Mapping[str, Any],
        path: str,
    ) -> Mapping[str, Any] | None:
        if "identitySource" not in value:
            self.add(f"{_join(path, 'identitySource')} is required")
            return None
        return self.identity_source(value, path)

    def require_drawing_identity_source(
        self,
        identity: Mapping[str, Any] | None,
        path: str,
    ) -> None:
        if identity is None:
            return
        kind = identity.get("kind")
        if isinstance(kind, str) and kind == "native_ref":
            native_ref = identity.get("nativeRef")
            if not isinstance(native_ref, str) or native_ref.strip() == "":
                self.add(f"{path}.identitySource.nativeRef is required")

    def current_value(
        self,
        value: Mapping[str, Any],
        path: str,
        value_type: str | None,
    ) -> None:
        if "currentValue" not in value:
            return
        current = value["currentValue"]
        if not _is_json_scalar(current):
            self.add(f"{path}.currentValue must be a JSON scalar")
            return
        if value_type == "number":
            if isinstance(current, bool) or not isinstance(current, (int, float)):
                self.add(f'{path}.currentValue must match valueType "number"')
        elif value_type == "string":
            if not isinstance(current, str):
                self.add(f'{path}.currentValue must match valueType "string"')
        elif value_type == "boolean":
            if not isinstance(current, bool):
                self.add(f'{path}.currentValue must match valueType "boolean"')

    def structure(self, value: Mapping[str, Any], path: str) -> None:
        location = _join(path, "structure")
        candidate = self.required_object(value, "structure", path)
        if candidate is None:
            return
        self.allowed(candidate, location, STRUCTURE_FIELDS)
        self.required_string(candidate, "rootComponentId", location)
        nodes = self.required_array(candidate, "nodes", location)
        if nodes is None:
            return
        if len(nodes) == 0:
            self.add(f"{location}.nodes must not be empty")
        for index, node in enumerate(nodes):
            node_location = f"{location}.nodes[{index}]"
            if not isinstance(node, Mapping):
                self.add(f"{node_location} must be an object")
                continue
            self.allowed(node, node_location, STRUCTURE_NODE_FIELDS)
            self.required_string(node, "componentId", node_location)
            self.required_string(
                node,
                "parentComponentId",
                node_location,
                allow_empty=True,
            )
            children = self.required_array(node, "children", node_location)
            if children is None:
                continue
            for child_index, child in enumerate(children):
                if not isinstance(child, str):
                    self.add(
                        f"{node_location}.children[{child_index}] must be a string"
                    )
                elif child.strip() == "":
                    self.add(f"{node_location}.children[{child_index}] is required")

    def require_identity_kind(
        self,
        identity: Mapping[str, Any] | None,
        path: str,
        expected_kind: str,
    ) -> None:
        if identity is None:
            return
        kind = identity.get("kind")
        if isinstance(kind, str) and kind.strip() != "" and kind != expected_kind:
            self.add(f'{path}.identitySource.kind must be "{expected_kind}"')

    def require_identity_field(
        self,
        identity: Mapping[str, Any] | None,
        path: str,
        field: str,
    ) -> None:
        if identity is None:
            return
        if field not in identity:
            self.add(f"{path}.identitySource.{field} is required")


def _is_json_scalar(value: Any) -> bool:
    if isinstance(value, bool) or isinstance(value, str):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return False


def _is_canonical_relative_path(value: str) -> bool:
    if value == "" or value.strip() != value or "\\" in value or "\x00" in value:
        return False
    if value.startswith("/") or posixpath.isabs(value):
        return False
    if posixpath.normpath(value) != value:
        return False
    if value in (".", "..") or value.startswith("../"):
        return False
    return re.match(r"^[A-Za-z]:/", value) is None


def _validate_semantics(value: Mapping[str, Any]) -> tuple[str, ...]:
    problems: list[str] = []

    entities = value["entities"]
    components = entities["components"]
    features = entities["features"]
    relationships = entities["relationships"]
    groups = entities["parameterGroups"]
    parameters = entities["parameters"]
    metadata = entities["metadata"]
    drawings = entities["drawings"]

    component_by_id = {component["id"]: component for component in components}
    feature_by_id = {feature["id"]: feature for feature in features}
    relationship_by_id = {
        relationship["id"]: relationship for relationship in relationships
    }
    group_by_id = {group["id"]: group for group in groups}

    root_product_id = value["rootProduct"]["id"]
    structure_root_id = value["structure"]["rootComponentId"]

    if root_product_id not in component_by_id:
        problems.append(
            f'rootProduct.id "{root_product_id}" must resolve to an existing component'
        )
    if structure_root_id not in component_by_id:
        problems.append(
            f'structure.rootComponentId "{structure_root_id}" must resolve to '
            "an existing component"
        )
    elif component_by_id[structure_root_id]["kind"] != "assembly":
        problems.append(
            f'structure.rootComponentId "{structure_root_id}" must resolve to '
            "an assembly component"
        )
    if root_product_id != structure_root_id:
        problems.append("structure.rootComponentId must equal rootProduct.id")

    for index, feature in enumerate(features):
        if feature["componentId"] not in component_by_id:
            problems.append(
                f"entities.features[{index}].componentId "
                f'"{feature["componentId"]}" must resolve to an existing '
                "component"
            )

    for index, relationship in enumerate(relationships):
        location = f"entities.relationships[{index}]"
        if relationship["componentId"] not in component_by_id:
            problems.append(
                f'{location}.componentId "{relationship["componentId"]}" '
                "must resolve to an existing component"
            )
        seen_endpoints: dict[str, int] = {}
        for endpoint_index, endpoint in enumerate(relationship["endpoints"]):
            if endpoint not in component_by_id and endpoint not in feature_by_id:
                problems.append(
                    f'{location}.endpoints[{endpoint_index}] "{endpoint}" '
                    "must resolve to an existing component or feature"
                )
            previous = seen_endpoints.get(endpoint)
            if previous is not None:
                problems.append(
                    f"{location}.endpoints[{endpoint_index}] duplicates "
                    f'endpoint "{endpoint}" already declared at '
                    f"{location}.endpoints[{previous}]"
                )
            else:
                seen_endpoints[endpoint] = endpoint_index

    for index, group in enumerate(groups):
        if group["ownerComponentId"] not in component_by_id:
            problems.append(
                f"entities.parameterGroups[{index}].ownerComponentId "
                f'"{group["ownerComponentId"]}" must resolve to an existing '
                "component"
            )

    for index, parameter in enumerate(parameters):
        location = f"entities.parameters[{index}]"
        component_id = parameter["componentId"]
        if component_id not in component_by_id:
            problems.append(
                f'{location}.componentId "{component_id}" must resolve to an '
                "existing component"
            )
        owner_kind = parameter["ownerKind"]
        owner_id = parameter["ownerId"]
        if owner_kind == "group":
            group = group_by_id.get(owner_id)
            if group is None:
                problems.append(
                    f'{location}.ownerId "{owner_id}" must resolve to an '
                    "existing parameter group"
                )
            elif group["ownerComponentId"] != component_id:
                problems.append(
                    f'{location}.componentId "{component_id}" must match owner '
                    f"parameter group component "
                    f'"{group["ownerComponentId"]}"'
                )
        elif owner_kind == "component":
            if owner_id not in component_by_id:
                problems.append(
                    f'{location}.ownerId "{owner_id}" must resolve to an '
                    "existing component"
                )
            elif owner_id != component_id:
                problems.append(
                    f'{location}.componentId "{component_id}" must equal '
                    "ownerId for component-owned parameters"
                )
        elif owner_kind == "feature":
            feature = feature_by_id.get(owner_id)
            if feature is None:
                problems.append(
                    f'{location}.ownerId "{owner_id}" must resolve to an '
                    "existing feature"
                )
            elif feature["componentId"] != component_id:
                problems.append(
                    f'{location}.componentId "{component_id}" must match owner '
                    f'feature component "{feature["componentId"]}"'
                )

    for index, entry in enumerate(metadata):
        location = f"entities.metadata[{index}]"
        component_id = entry["componentId"]
        if component_id not in component_by_id:
            problems.append(
                f'{location}.componentId "{component_id}" must resolve to an '
                "existing component"
            )
        owner_kind = entry["ownerKind"]
        owner_id = entry["ownerId"]
        if owner_kind == "component":
            if owner_id not in component_by_id:
                problems.append(
                    f'{location}.ownerId "{owner_id}" must resolve to an '
                    "existing component"
                )
            elif owner_id != component_id:
                problems.append(
                    f'{location}.componentId "{component_id}" must equal '
                    "ownerId for component-owned metadata"
                )
        elif owner_kind == "feature":
            feature = feature_by_id.get(owner_id)
            if feature is None:
                problems.append(
                    f'{location}.ownerId "{owner_id}" must resolve to an '
                    "existing feature"
                )
            elif feature["componentId"] != component_id:
                problems.append(
                    f'{location}.componentId "{component_id}" must match owner '
                    f'feature component "{feature["componentId"]}"'
                )
        elif owner_kind == "relationship":
            relationship = relationship_by_id.get(owner_id)
            if relationship is None:
                problems.append(
                    f'{location}.ownerId "{owner_id}" must resolve to an '
                    "existing relationship"
                )
            elif relationship["componentId"] != component_id:
                problems.append(
                    f'{location}.componentId "{component_id}" must match owner '
                    f'relationship component "{relationship["componentId"]}"'
                )

    problems.extend(
        _validate_identity_source_uniqueness(
            components,
            features,
            groups,
            parameters,
            metadata,
        )
    )
    problems.extend(_validate_drawing_semantics(drawings, component_by_id))
    problems.extend(_validate_structure(value, component_by_id))

    return tuple(problems)


def _validate_identity_source_uniqueness(
    components: list[Mapping[str, Any]],
    features: list[Mapping[str, Any]],
    groups: list[Mapping[str, Any]],
    parameters: list[Mapping[str, Any]],
    metadata: list[Mapping[str, Any]],
) -> list[str]:
    problems: list[str] = []

    component_paths: dict[str, str] = {}
    for index, component in enumerate(components):
        identity = component.get("identitySource")
        if not isinstance(identity, Mapping):
            continue
        path_value = identity.get("path")
        if not isinstance(path_value, str) or path_value == "":
            continue
        location = f"entities.components[{index}].identitySource.path"
        previous = component_paths.get(path_value)
        if previous is not None:
            problems.append(
                f'{location} "{path_value}" duplicates parent-scoped identity '
                f"source already declared at {previous}"
            )
        else:
            component_paths[path_value] = location

    owner_scoped_seen: dict[str, str] = {}

    def add_owner_scoped(
        scope: str,
        key: Any,
        location: str,
        field: str,
    ) -> None:
        if not scope or not isinstance(key, str) or key == "":
            return
        compound = scope + "\x00" + key
        field_path = f"{location}.identitySource.{field}"
        previous = owner_scoped_seen.get(compound)
        if previous is not None:
            problems.append(
                f'{field_path} "{key}" duplicates owner-scoped identity source '
                f"already declared at {previous}"
            )
        else:
            owner_scoped_seen[compound] = field_path

    for index, feature in enumerate(features):
        identity = feature.get("identitySource")
        if isinstance(identity, Mapping):
            add_owner_scoped(
                "feature:" + feature["componentId"],
                identity.get("ownerScopedKey"),
                f"entities.features[{index}]",
                "ownerScopedKey",
            )

    for index, group in enumerate(groups):
        identity = group.get("identitySource")
        if isinstance(identity, Mapping):
            add_owner_scoped(
                "group:" + group["ownerComponentId"],
                identity.get("ownerScopedKey"),
                f"entities.parameterGroups[{index}]",
                "ownerScopedKey",
            )

    for index, parameter in enumerate(parameters):
        identity = parameter.get("identitySource")
        if isinstance(identity, Mapping):
            add_owner_scoped(
                parameter["ownerKind"] + ":" + parameter["ownerId"],
                identity.get("ownerScopedKey"),
                f"entities.parameters[{index}]",
                "ownerScopedKey",
            )

    for index, entry in enumerate(metadata):
        identity = entry.get("identitySource")
        if isinstance(identity, Mapping):
            add_owner_scoped(
                entry["ownerKind"] + ":" + entry["ownerId"],
                identity.get("ownerScopedKey"),
                f"entities.metadata[{index}]",
                "ownerScopedKey",
            )

    return problems


def _validate_drawing_semantics(
    drawings: list[Mapping[str, Any]],
    component_by_id: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    problems: list[str] = []

    for index, drawing in enumerate(drawings):
        location = f"entities.drawings[{index}]"
        component_ids = drawing["componentIds"]
        if not component_ids:
            problems.append(f"{location}.componentIds must not be empty")
        seen_components: set[str] = set()
        for component_index, component_id in enumerate(component_ids):
            if component_id in seen_components:
                problems.append(
                    f"{location}.componentIds[{component_index}] duplicates "
                    f'component ID "{component_id}"'
                )
            else:
                seen_components.add(component_id)
            if component_id not in component_by_id:
                problems.append(
                    f'{location}.componentIds[{component_index}] "{component_id}" '
                    "must resolve to an existing component"
                )

        sheets = drawing["sheets"]
        if not sheets:
            problems.append(f"{location}.sheets must not be empty")
        seen_orders: dict[int, int] = {}
        for sheet_index, sheet in enumerate(sheets):
            sheet_location = f"{location}.sheets[{sheet_index}]"
            order = sheet.get("order")
            if isinstance(order, int) and not isinstance(order, bool):
                if order in seen_orders:
                    problems.append(
                        f"{sheet_location}.order duplicates order already "
                        f"declared at {location}.sheets[{seen_orders[order]}].order"
                    )
                else:
                    seen_orders[order] = sheet_index
    return problems


def _validate_structure(
    value: Mapping[str, Any],
    component_by_id: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    problems: list[str] = []

    structure = value["structure"]
    root_id = structure["rootComponentId"]
    nodes = structure["nodes"]

    node_by_component: dict[str, int] = {}
    parent_of: dict[str, str] = {}
    root_node_count = 0

    for index, node in enumerate(nodes):
        location = f"structure.nodes[{index}]"
        component_id = node["componentId"]
        previous_node = node_by_component.get(component_id)
        if previous_node is not None:
            problems.append(
                f'{location}.componentId "{component_id}" duplicates node '
                f"already declared at structure.nodes[{previous_node}]"
                ".componentId"
            )
        else:
            node_by_component[component_id] = index

        if component_id not in component_by_id:
            problems.append(
                f'{location}.componentId "{component_id}" must resolve to an '
                "existing component"
            )

        parent_id = node["parentComponentId"]
        if parent_id == "":
            root_node_count += 1
            if component_id != root_id:
                problems.append(
                    f'{location}.componentId "{component_id}" must equal '
                    "structure.rootComponentId when parentComponentId is empty"
                )
        else:
            if parent_id not in component_by_id:
                problems.append(
                    f'{location}.parentComponentId "{parent_id}" must resolve '
                    "to an existing component"
                )
            if parent_id == component_id:
                problems.append(
                    f"{location}.parentComponentId must not reference the same "
                    "component as componentId"
                )
            previous_parent = parent_of.get(component_id)
            if previous_parent is not None and previous_parent != parent_id:
                problems.append(
                    f'{location}.componentId "{component_id}" must not declare '
                    "more than one parent"
                )
            else:
                parent_of[component_id] = parent_id

        seen_children: dict[str, int] = {}
        for child_index, child_id in enumerate(node["children"]):
            if child_id not in component_by_id:
                problems.append(
                    f'{location}.children[{child_index}] "{child_id}" must '
                    "resolve to an existing component"
                )
            if child_id == component_id:
                problems.append(
                    f"{location}.children[{child_index}] must not reference the "
                    "same component as componentId"
                )
            previous_child = seen_children.get(child_id)
            if previous_child is not None:
                problems.append(
                    f"{location}.children[{child_index}] duplicates child "
                    f'"{child_id}" already declared at {location}.children'
                    f"[{previous_child}]"
                )
            else:
                seen_children[child_id] = child_index

    if len(nodes) > 0 and root_node_count != 1:
        problems.append(
            "structure.nodes must contain exactly one root node with empty "
            "parentComponentId"
        )

    for index, node in enumerate(nodes):
        location = f"structure.nodes[{index}]"
        for child_index, child_id in enumerate(node["children"]):
            declared_parent = parent_of.get(child_id)
            if declared_parent is not None and declared_parent != node["componentId"]:
                problems.append(
                    f"{location}.children[{child_index}] references child "
                    f'"{child_id}" whose declared parent is '
                    f'"{declared_parent}"'
                )
            if child_id not in node_by_component:
                problems.append(
                    f"{location}.children[{child_index}] references child "
                    f'"{child_id}" that has no node entry'
                )

    for component in value["entities"]["components"]:
        component_id = component["id"]
        if component_id not in node_by_component:
            problems.append(f'structure.nodes must include component "{component_id}"')

    for component_id, index in node_by_component.items():
        if nodes[index]["parentComponentId"] == "":
            continue
        if component_id not in parent_of:
            problems.append(
                f'structure component "{component_id}" must have exactly one parent'
            )

    if root_id not in node_by_component:
        return problems

    visited: set[str] = set()
    active: set[str] = set()
    cycle_found = False

    def visit(component_id: str) -> None:
        nonlocal cycle_found
        if component_id in active:
            cycle_found = True
            return
        if component_id in visited:
            return
        visited.add(component_id)
        active.add(component_id)
        node_index = node_by_component.get(component_id)
        if node_index is not None:
            for child_id in nodes[node_index]["children"]:
                if child_id in node_by_component:
                    visit(child_id)
        active.discard(component_id)

    for component in value["entities"]["components"]:
        component_id = component["id"]
        if component_id in node_by_component:
            visit(component_id)

    if cycle_found:
        problems.append("structure.nodes must not contain cycles")

    reachable: set[str] = set()
    pending = [root_id]
    while pending:
        component_id = pending.pop()
        if component_id in reachable:
            continue
        reachable.add(component_id)
        node_index = node_by_component.get(component_id)
        if node_index is not None:
            for child_id in nodes[node_index]["children"]:
                if child_id in node_by_component:
                    pending.append(child_id)

    for component in value["entities"]["components"]:
        component_id = component["id"]
        if component_id not in reachable:
            problems.append(
                f'structure component "{component_id}" is not reachable from '
                "structure.rootComponentId"
            )
            break

    return problems


__all__ = [
    "CAPTURE_SCHEMA_VERSION",
    "validate_capture_document",
]
