"""FreeCAD semantic-map generation, merge planning, and atomic writing.

This module owns the GUI-free, FreeCAD-free side of ``prm.semantic-map.json``
production. It starts from a versioned FreeCAD adapter template and applies
explicit project selections for semantic parameter types, default units, and
native-type mappings. It never infers a semantic type from ``App::Property*``
alone.

Existing maps are never silently replaced. Update planning decodes and
validates the existing map, checks adapter identity, preserves user edits in
adapter-policy sections, and reports a deterministic diff. Replacing an existing
map requires an explicit ``confirm_replace=True`` decision.

The caller supplies the explicit destination path. Project-root discovery,
``prm.project.json`` loading, capture orchestration, and Engine preflight belong
to the capture workflow around this module.
"""

from __future__ import annotations

import copy
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parametron_freecad.capture.native_types import (
    METADATA_RESOLVED_VALUE_KINDS,
    PARAMETER_NATIVE_TYPES,
)
from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.common.strict_json import StrictJsonError, loads_strict_json

SEMANTIC_MAP_FILENAME = "prm.semantic-map.json"
SEMANTIC_MAP_SCHEMA_VERSION = "1.0"

FREECAD_SEMANTIC_MAP_TEMPLATE_VERSION = "1"
FREECAD_ADAPTER_NAME = "freecad"
FREECAD_CAD_SYSTEM_NAME = "FreeCAD"
FREECAD_CAD_SYSTEM_MIN_VERSION = "1.1.4"

_SUPPORTED_PARAMETER_VALUE_KINDS = frozenset({"number", "integer", "boolean", "string"})
_SUPPORTED_COERCIONS = frozenset(
    {
        "number_to_length",
        "number_to_integer_exact",
        "number_to_dimensionless",
    }
)
_COERCION_REQUIRED_VALUE_KIND = {
    "number_to_length": "number",
    "number_to_integer_exact": "integer",
    "number_to_dimensionless": "number",
}
_SUPPORTED_RESOLUTION_PRECEDENCE = frozenset(
    {"explicit_parameter_mapping", "capture_native_type_mapping"}
)
_KNOWN_SEMANTIC_TARGETS = frozenset(
    {"assembly", "part", "feature", "parameter", "metadata", "drawing"}
)
_KNOWN_OUTPUT_MANIFEST_TYPES = frozenset({"step", "csv", "pdf"})
_KNOWN_MUTATION_COLLECTIONS = frozenset(
    {
        "assemblyMutations.parameters",
        "assemblyMutations.suppression",
        "assemblyMutations.visibility",
        "assemblyMutations.deletion",
        "partMutations.parameters",
        "partMutations.suppression",
        "partMutations.visibility",
        "partMutations.deletion",
    }
)
_SUPPORTED_OPERATION_NAMES = frozenset(
    {
        "suppress",
        "unsuppress",
        "hide",
        "unhide",
        "delete",
        "write_parameter",
        "write_metadata",
    }
)
_SUPPORTED_METADATA_VALUE_KINDS = frozenset({"string", "boolean", "number", "integer"})

_TOP_LEVEL_FIELDS = (
    "schemaVersion",
    "mappingId",
    "adapter",
    "cadSystem",
    "semanticTypes",
    "captureToSemantic",
    "semanticToManifest",
    "overridePolicy",
    "operationCapabilities",
    "determinism",
)
_CAD_SYSTEM_FIELDS = ("name", "minVersion")
_SEMANTIC_TYPES_FIELDS = ("parameterTypes", "resolutionPolicy")
_PARAMETER_TYPE_FIELDS = ("valueKind", "defaultUnit", "coercion")
_RESOLUTION_POLICY_FIELDS = (
    "precedence",
    "allowEngineDefault",
    "allowEngineInference",
)
_CAPTURE_TO_SEMANTIC_FIELDS = (
    "parameterGroups",
    "parameters",
    "components",
    "metadata",
)
_PARAMETER_GROUP_FIELDS = ("captureKind", "cadContainerType", "semanticKind")
_PARAMETER_FIELDS = (
    "captureKind",
    "semanticKind",
    "identity",
    "name",
    "group",
    "semanticType",
)
_PARAMETER_SEMANTIC_TYPE_FIELDS = ("from", "map")
_COMPONENT_FIELDS = (
    "captureKind",
    "semanticKinds",
    "identity",
    "targetability",
)
_METADATA_FIELDS = (
    "captureKind",
    "semanticKind",
    "identity",
    "key",
    "valueKind",
    "nativeValueKinds",
)
_SEMANTIC_TO_MANIFEST_FIELDS = ("parameters", "outputs", "mutations")
_PARAMETER_MANIFEST_FIELDS = ("target", "name", "value", "type", "unit")
_OUTPUT_MANIFEST_FIELDS = (
    "manifestType",
    "targetField",
    "targetSource",
    "scopeField",
    "scopeMap",
)
_MUTATION_MAPPING_FIELDS = (
    "manifestCollection",
    "targetField",
    "valueField",
    "value",
    "propertyField",
)
_CAPABILITY_FIELDS = (
    "requiresTargetability",
    "requiresWritable",
    "allowedSemanticTargets",
)
_OVERRIDE_POLICY_FIELDS = (
    "allowAdapterOverrides",
    "allowProjectOverrides",
    "allowUserOverrides",
)
_DETERMINISM_FIELDS = (
    "allowImplicitFallback",
    "allowCaseInsensitiveMatch",
    "allowDisplayNameIdentity",
    "allowAdapterInference",
)

_PRESERVED_SECTION_PATHS = (
    ("captureToSemantic", "parameterGroups"),
    ("captureToSemantic", "components"),
    ("captureToSemantic", "metadata"),
    ("semanticToManifest",),
    ("overridePolicy",),
    ("operationCapabilities",),
    ("determinism",),
)

_MISSING = object()


# ---------------------------------------------------------------------------
# Typed failures
# ---------------------------------------------------------------------------


class SemanticMapError(ValueError):
    """Base class for deterministic semantic-map failures."""


class SemanticMapContractError(SemanticMapError):
    """Raised when a semantic map violates the Engine schema 1.0 contract."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        if not self.problems:
            raise ValueError("SemanticMapContractError requires at least one problem")
        super().__init__(
            "semantic map contract validation failed: " + "; ".join(self.problems)
        )


class SemanticMapSelectionError(SemanticMapError):
    """Raised when explicit project semantic-map selections are invalid."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        if not self.problems:
            raise ValueError("SemanticMapSelectionError requires at least one problem")
        super().__init__(
            "semantic map selection validation failed: " + "; ".join(self.problems)
        )


class SemanticMapDecodeError(SemanticMapError):
    """Raised when an existing semantic map cannot be decoded safely."""


class SemanticMapIdentityError(SemanticMapError):
    """Raised when an existing map belongs to another adapter or CAD system."""


class SemanticMapConfirmationRequiredError(SemanticMapError):
    """Raised when updating an existing map without explicit confirmation."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        diff: Sequence[SemanticMapDiffEntry],
    ) -> None:
        self.path = Path(path)
        self.diff = tuple(diff)
        super().__init__(
            f"semantic map update requires explicit confirmation for "
            f"{self.path}: {len(self.diff)} change(s)"
        )


class SemanticMapWriteError(OSError):
    """Raised when a semantic map cannot be read or written atomically."""


# ---------------------------------------------------------------------------
# Explicit project selection
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SemanticParameterTypeSelection:
    """One explicitly selected semantic parameter type and unit."""

    name: str
    value_kind: str
    default_unit: str
    coercion: str


@dataclass(frozen=True, slots=True)
class FreeCADSemanticMapSelection:
    """Explicit project selections applied to the FreeCAD map template."""

    mapping_id: str
    parameter_types: tuple[SemanticParameterTypeSelection, ...]
    native_type_to_semantic_type: Mapping[str, str]
    cad_system_min_version: str = FREECAD_CAD_SYSTEM_MIN_VERSION


# ---------------------------------------------------------------------------
# Diff, plan, and write result records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SemanticMapDiffEntry:
    """One deterministic difference between an existing and proposed map."""

    path: str
    change: str
    existing: Any = None
    proposed: Any = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "change": self.change,
            "existing": copy.deepcopy(self.existing),
            "proposed": copy.deepcopy(self.proposed),
        }


@dataclass(frozen=True, slots=True)
class SemanticMapUpdatePlan:
    """Deterministic update plan for an explicit semantic-map destination."""

    path: Path
    status: str
    generated: Mapping[str, Any]
    existing: Mapping[str, Any] | None
    merged: Mapping[str, Any]
    diff: tuple[SemanticMapDiffEntry, ...]
    requires_confirmation: bool

    def to_mapping(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "status": self.status,
            "requiresConfirmation": self.requires_confirmation,
            "diff": [entry.to_mapping() for entry in self.diff],
        }


@dataclass(frozen=True, slots=True)
class SemanticMapWriteResult:
    """Result of one semantic-map create, no-op, or confirmed merge."""

    path: Path
    status: str
    wrote: bool
    diff: tuple[SemanticMapDiffEntry, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "status": self.status,
            "wrote": self.wrote,
            "diff": [entry.to_mapping() for entry in self.diff],
        }


# ---------------------------------------------------------------------------
# Versioned FreeCAD template
# ---------------------------------------------------------------------------


def freecad_semantic_map_template() -> dict[str, Any]:
    """Return a fresh copy of the versioned FreeCAD semantic-map template.

    The returned mapping is an incomplete template: ``mappingId``, parameter
    types, and the native-to-semantic parameter map are project selections and
    are empty here. ``build_semantic_map`` fills them and validates the result.
    """

    return {
        "schemaVersion": SEMANTIC_MAP_SCHEMA_VERSION,
        "mappingId": "",
        "adapter": FREECAD_ADAPTER_NAME,
        "cadSystem": {
            "name": FREECAD_CAD_SYSTEM_NAME,
            "minVersion": FREECAD_CAD_SYSTEM_MIN_VERSION,
        },
        "semanticTypes": {
            "parameterTypes": {},
            "resolutionPolicy": {
                "precedence": [
                    "explicit_parameter_mapping",
                    "capture_native_type_mapping",
                ],
                "allowEngineDefault": False,
                "allowEngineInference": False,
            },
        },
        "captureToSemantic": {
            "parameterGroups": [
                {
                    "captureKind": "parameter_group",
                    "cadContainerType": "App::VarSet",
                    "semanticKind": "parameter_group",
                }
            ],
            "parameters": [
                {
                    "captureKind": "parameter",
                    "semanticKind": "parameter",
                    "identity": "capture.id",
                    "name": "capture.name",
                    "group": "capture.groupId",
                    "semanticType": {
                        "from": "capture.nativeType",
                        "map": {},
                    },
                }
            ],
            "components": [
                {
                    "captureKind": "component",
                    "semanticKinds": {
                        "assembly": "assembly",
                        "part": "part",
                    },
                    "identity": "capture.id",
                    "targetability": "capture.targetability",
                }
            ],
            "metadata": [
                {
                    "captureKind": "metadata",
                    "semanticKind": "metadata",
                    "identity": "capture.id",
                    "key": "capture.key",
                    "valueKind": "capture.nativeType",
                    "nativeValueKinds": dict(METADATA_RESOLVED_VALUE_KINDS),
                }
            ],
        },
        "semanticToManifest": {
            "parameters": {
                "target": "parameterAssignments",
                "name": "semantic.parameter.name",
                "value": "resolved.value",
                "type": "number",
                "unit": "resolved.unit",
            },
            "outputs": {
                "step": {
                    "manifestType": "step",
                    "targetField": "object",
                    "targetSource": "semantic.output.target.manifestName",
                },
                "csv": {
                    "manifestType": "csv",
                    "targetField": "target",
                    "targetSource": "semantic.output.target.manifestName",
                    "scopeField": "rollup",
                    "scopeMap": {
                        "flat": "flat",
                        "assembly": "assembly",
                        "subtree": "assembly",
                    },
                },
                "pdf": {
                    "manifestType": "pdf",
                },
            },
            "mutations": {
                "set_parameter": {
                    "manifestCollection": "partMutations.parameters",
                    "targetField": "object",
                    "propertyField": "property",
                    "valueField": "valueParam",
                },
                "suppress": {
                    "manifestCollection": "partMutations.suppression",
                    "targetField": "object",
                    "valueField": "suppressed",
                    "value": True,
                },
                "unsuppress": {
                    "manifestCollection": "partMutations.suppression",
                    "targetField": "object",
                    "valueField": "suppressed",
                    "value": False,
                },
            },
        },
        "overridePolicy": {
            "allowAdapterOverrides": False,
            "allowProjectOverrides": False,
            "allowUserOverrides": False,
        },
        "operationCapabilities": {
            "suppress": {
                "requiresTargetability": "suppress",
                "allowedSemanticTargets": ["assembly", "part", "feature"],
            },
            "hide": {
                "requiresTargetability": "hide",
                "allowedSemanticTargets": ["assembly", "part", "feature"],
            },
            "delete": {
                "requiresTargetability": "delete",
                "allowedSemanticTargets": ["part"],
            },
            "write_parameter": {
                "requiresWritable": True,
                "allowedSemanticTargets": ["parameter"],
            },
            "write_metadata": {
                "requiresWritable": True,
                "allowedSemanticTargets": ["metadata"],
            },
        },
        "determinism": {
            "allowImplicitFallback": False,
            "allowCaseInsensitiveMatch": False,
            "allowDisplayNameIdentity": False,
            "allowAdapterInference": False,
        },
    }


# ---------------------------------------------------------------------------
# Selection validation and generation
# ---------------------------------------------------------------------------


def build_semantic_map(selection: FreeCADSemanticMapSelection) -> dict[str, Any]:
    """Build one complete, validated semantic map from explicit selections."""

    if not isinstance(selection, FreeCADSemanticMapSelection):
        raise TypeError("build_semantic_map requires FreeCADSemanticMapSelection")

    problems = _validate_selection(selection)
    if problems:
        raise SemanticMapSelectionError(problems)

    parameter_types: dict[str, Any] = {}
    for entry in selection.parameter_types:
        parameter_types[entry.name] = {
            "valueKind": entry.value_kind,
            "defaultUnit": entry.default_unit,
            "coercion": entry.coercion,
        }

    generated = freecad_semantic_map_template()
    generated["mappingId"] = selection.mapping_id
    generated["cadSystem"]["minVersion"] = selection.cad_system_min_version
    generated["semanticTypes"]["parameterTypes"] = parameter_types
    generated["captureToSemantic"]["parameters"][0]["semanticType"]["map"] = dict(
        selection.native_type_to_semantic_type
    )

    validate_semantic_map(generated)
    return generated


def _validate_selection(
    selection: FreeCADSemanticMapSelection,
) -> tuple[str, ...]:
    problems: list[str] = []

    mapping_id = selection.mapping_id
    if not isinstance(mapping_id, str) or mapping_id.strip() == "":
        problems.append("mappingId is required")
    elif mapping_id != mapping_id.strip():
        problems.append("mappingId must not have leading or trailing whitespace")

    min_version = selection.cad_system_min_version
    if not isinstance(min_version, str) or min_version.strip() == "":
        problems.append("cadSystem.minVersion is required")
    elif min_version != min_version.strip():
        problems.append(
            "cadSystem.minVersion must not have leading or trailing whitespace"
        )

    parameter_types = selection.parameter_types
    if not isinstance(parameter_types, Sequence) or isinstance(
        parameter_types, (str, bytes)
    ):
        problems.append("parameterTypes must be a sequence")
        parameter_types = ()
    if len(parameter_types) == 0:
        problems.append("semanticTypes.parameterTypes must not be empty")

    declared: set[str] = set()
    for index, entry in enumerate(parameter_types):
        location = f"semanticTypes.parameterTypes[{index}]"
        if not isinstance(entry, SemanticParameterTypeSelection):
            problems.append(f"{location} must be a SemanticParameterTypeSelection")
            continue
        name = entry.name
        if not isinstance(name, str) or name.strip() == "":
            problems.append(f"{location}.name is required")
        elif name != name.strip():
            problems.append(
                f"{location}.name must not have leading or trailing whitespace"
            )
        elif name in declared:
            problems.append(f'{location}.name duplicates semantic type "{name}"')
        else:
            declared.add(name)

        value_kind = entry.value_kind
        if not isinstance(value_kind, str) or value_kind.strip() == "":
            problems.append(f"{location}.valueKind is required")
        elif value_kind not in _SUPPORTED_PARAMETER_VALUE_KINDS:
            problems.append(f'{location}.valueKind "{value_kind}" is not supported')

        default_unit = entry.default_unit
        if not isinstance(default_unit, str) or default_unit.strip() == "":
            problems.append(f"{location}.defaultUnit is required")
        elif default_unit != default_unit.strip():
            problems.append(
                f"{location}.defaultUnit must not have leading or trailing whitespace"
            )

        coercion = entry.coercion
        if not isinstance(coercion, str) or coercion.strip() == "":
            problems.append(f"{location}.coercion is required")
        elif coercion not in _SUPPORTED_COERCIONS:
            problems.append(f'{location}.coercion "{coercion}" is not supported')
        else:
            required_kind = _COERCION_REQUIRED_VALUE_KIND[coercion]
            if value_kind != required_kind:
                problems.append(
                    f'{location}.coercion "{coercion}" requires valueKind '
                    f'"{required_kind}"'
                )

    native_map = selection.native_type_to_semantic_type
    if not isinstance(native_map, Mapping):
        problems.append(
            "captureToSemantic.parameters[0].semanticType.map must be an object"
        )
        native_map = {}
    if len(native_map) == 0:
        problems.append(
            "captureToSemantic.parameters[0].semanticType.map must not be empty"
        )
    for native_key in sorted(
        native_map,
        key=lambda key: (str(type(key)), str(key)),
    ):
        location = "captureToSemantic.parameters[0].semanticType.map"
        if not isinstance(native_key, str) or native_key.strip() == "":
            problems.append(f"{location} key must be a nonblank string")
            continue
        if native_key != native_key.strip():
            problems.append(
                f'{location} key "{native_key}" must not have leading or '
                "trailing whitespace"
            )
            continue
        if native_key not in PARAMETER_NATIVE_TYPES:
            problems.append(
                f'{location} key "{native_key}" is not a supported FreeCAD '
                "parameter native type"
            )
            continue
        semantic_type = native_map[native_key]
        if not isinstance(semantic_type, str) or semantic_type.strip() == "":
            problems.append(
                f'{location}["{native_key}"] must reference a non-empty '
                "semantic type key"
            )
        elif semantic_type != semantic_type.strip():
            problems.append(
                f'{location}["{native_key}"] must not have leading or trailing '
                "whitespace"
            )
        elif semantic_type not in declared:
            problems.append(
                f'{location}["{native_key}"] references unknown semantic type '
                f'"{semantic_type}"'
            )

    return tuple(problems)


# ---------------------------------------------------------------------------
# Canonical serialization
# ---------------------------------------------------------------------------


def canonical_semantic_map_bytes(value: Mapping[str, Any]) -> bytes:
    """Return canonical UTF-8 semantic-map bytes."""

    validate_semantic_map(value)
    ordered = _canonicalize_semantic_map(value)
    return dumps_canonical(ordered).encode("utf-8")


def canonical_semantic_map_text(value: Mapping[str, Any]) -> str:
    """Return canonical semantic-map JSON text with one trailing newline."""

    return canonical_semantic_map_bytes(value).decode("utf-8")


def _canonicalize_semantic_map(value: Mapping[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = copy.deepcopy(dict(value))
    capture_to_semantic = ordered.get("captureToSemantic")
    if isinstance(capture_to_semantic, dict):
        _sort_array(
            capture_to_semantic,
            "parameterGroups",
            ("captureKind", "cadContainerType", "semanticKind"),
        )
        _sort_array(
            capture_to_semantic,
            "parameters",
            ("captureKind", "semanticKind"),
        )
        _sort_array(capture_to_semantic, "components", ("captureKind",))
        _sort_array(
            capture_to_semantic,
            "metadata",
            ("captureKind", "semanticKind"),
        )

    capabilities = ordered.get("operationCapabilities")
    if isinstance(capabilities, dict):
        for capability in capabilities.values():
            if not isinstance(capability, dict):
                continue
            targets = capability.get("allowedSemanticTargets")
            if isinstance(targets, list):
                targets.sort()
    return ordered


def _sort_array(
    parent: dict[str, Any],
    field: str,
    fields: tuple[str, ...],
) -> None:
    values = parent.get(field)
    if not isinstance(values, list):
        return
    values.sort(
        key=lambda entry: tuple(
            str(entry.get(field_name, "")) if isinstance(entry, Mapping) else ""
            for field_name in fields
        )
    )


# ---------------------------------------------------------------------------
# Engine schema 1.0 validation
# ---------------------------------------------------------------------------


def validate_semantic_map(value: Any) -> None:
    """Validate one semantic map against the Engine schema 1.0 requirements."""

    problems = _validate_semantic_map(value)
    if problems:
        raise SemanticMapContractError(problems)


def _validate_semantic_map(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return ("root must be an object",)

    problems: list[str] = []
    _allowed(value, "", _TOP_LEVEL_FIELDS, problems)

    schema_version = _required_string(value, "schemaVersion", "", problems)
    if schema_version is not None and schema_version != SEMANTIC_MAP_SCHEMA_VERSION:
        problems.append(f'schemaVersion must be "{SEMANTIC_MAP_SCHEMA_VERSION}"')
    _required_string(value, "mappingId", "", problems)
    _required_string(value, "adapter", "", problems)

    cad_system = _required_mapping(value, "cadSystem", "", problems)
    if cad_system is not None:
        _allowed(cad_system, "cadSystem", _CAD_SYSTEM_FIELDS, problems)
        _required_string(cad_system, "name", "cadSystem", problems)
        _optional_string(cad_system, "minVersion", "cadSystem", problems)

    declared_parameter_types: set[str] = set()
    semantic_types = _required_mapping(value, "semanticTypes", "", problems)
    if semantic_types is not None:
        _allowed(
            semantic_types,
            "semanticTypes",
            _SEMANTIC_TYPES_FIELDS,
            problems,
        )
        _validate_parameter_types(
            semantic_types,
            declared_parameter_types,
            problems,
        )
        _validate_resolution_policy(semantic_types, problems)

    capture_to_semantic = _required_mapping(
        value,
        "captureToSemantic",
        "",
        problems,
    )
    if capture_to_semantic is not None:
        _allowed(
            capture_to_semantic,
            "captureToSemantic",
            _CAPTURE_TO_SEMANTIC_FIELDS,
            problems,
        )
        _validate_parameter_groups(capture_to_semantic, problems)
        _validate_parameters(
            capture_to_semantic,
            declared_parameter_types,
            problems,
        )
        _validate_components(capture_to_semantic, problems)
        _validate_metadata(capture_to_semantic, problems)

    semantic_to_manifest = _required_mapping(
        value,
        "semanticToManifest",
        "",
        problems,
    )
    if semantic_to_manifest is not None:
        _validate_semantic_to_manifest(semantic_to_manifest, problems)

    override_policy = _required_mapping(
        value,
        "overridePolicy",
        "",
        problems,
    )
    if override_policy is not None:
        _allowed(
            override_policy,
            "overridePolicy",
            _OVERRIDE_POLICY_FIELDS,
            problems,
        )
        for field in _OVERRIDE_POLICY_FIELDS:
            _required_false_bool(override_policy, field, "overridePolicy", problems)

    _validate_operation_capabilities(value, problems)

    determinism = _required_mapping(value, "determinism", "", problems)
    if determinism is not None:
        _allowed(determinism, "determinism", _DETERMINISM_FIELDS, problems)
        for field in _DETERMINISM_FIELDS:
            _required_false_bool(determinism, field, "determinism", problems)

    return tuple(problems)


def _validate_parameter_types(
    semantic_types: Mapping[str, Any],
    declared: set[str],
    problems: list[str],
) -> None:
    parameter_types = _required_mapping(
        semantic_types,
        "parameterTypes",
        "semanticTypes",
        problems,
    )
    if parameter_types is None:
        return
    if len(parameter_types) == 0:
        problems.append("semanticTypes.parameterTypes must not be empty")

    for key in _sorted_keys(parameter_types):
        location = f"semanticTypes.parameterTypes[{key!r}]"
        if not isinstance(key, str) or key.strip() == "":
            problems.append("semanticTypes.parameterTypes key must not be empty")
            continue
        if key != key.strip():
            problems.append(
                f"semanticTypes.parameterTypes key {key!r} must not have "
                "leading or trailing whitespace"
            )
            continue
        declared.add(key)

        entry = parameter_types[key]
        if not isinstance(entry, Mapping):
            problems.append(f"{location} must be an object")
            continue
        _allowed(entry, location, _PARAMETER_TYPE_FIELDS, problems)
        value_kind = _required_string(entry, "valueKind", location, problems)
        if (
            value_kind is not None
            and value_kind not in _SUPPORTED_PARAMETER_VALUE_KINDS
        ):
            problems.append(f'{location}.valueKind "{value_kind}" is not supported')
        _required_string(entry, "defaultUnit", location, problems)
        coercion = _required_string(entry, "coercion", location, problems)
        if coercion is not None and coercion not in _SUPPORTED_COERCIONS:
            problems.append(f'{location}.coercion "{coercion}" is not supported')


def _validate_resolution_policy(
    semantic_types: Mapping[str, Any],
    problems: list[str],
) -> None:
    location = "semanticTypes.resolutionPolicy"
    policy = _required_mapping(
        semantic_types, "resolutionPolicy", "semanticTypes", problems
    )
    if policy is None:
        return
    _allowed(policy, location, _RESOLUTION_POLICY_FIELDS, problems)

    precedence = _required_array(policy, "precedence", location, problems)
    if precedence is not None:
        if len(precedence) == 0:
            problems.append(f"{location}.precedence must not be empty")
        seen: set[str] = set()
        for index, item in enumerate(precedence):
            item_location = f"{location}.precedence[{index}]"
            if not isinstance(item, str) or item.strip() == "":
                problems.append(f"{item_location} is required")
                continue
            if item not in _SUPPORTED_RESOLUTION_PRECEDENCE:
                problems.append(f'{item_location} "{item}" is not supported')
                continue
            if item in seen:
                problems.append(
                    f"{item_location} duplicates an earlier precedence value"
                )
                continue
            seen.add(item)

    _required_false_bool(policy, "allowEngineDefault", location, problems)
    _required_false_bool(policy, "allowEngineInference", location, problems)


def _validate_parameter_groups(
    capture_to_semantic: Mapping[str, Any],
    problems: list[str],
) -> None:
    items = _required_array(
        capture_to_semantic,
        "parameterGroups",
        "captureToSemantic",
        problems,
    )
    if items is None:
        return
    seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(items):
        location = f"captureToSemantic.parameterGroups[{index}]"
        if not isinstance(item, Mapping):
            problems.append(f"{location} must be an object")
            continue
        _allowed(item, location, _PARAMETER_GROUP_FIELDS, problems)
        capture_kind = _required_string(item, "captureKind", location, problems)
        container_type = _required_string(
            item,
            "cadContainerType",
            location,
            problems,
        )
        semantic_kind = _required_string(
            item,
            "semanticKind",
            location,
            problems,
        )
        if capture_kind is None or container_type is None or semantic_kind is None:
            continue
        key = (capture_kind, container_type, semantic_kind)
        if key in seen:
            problems.append(
                f"{location} duplicates the natural key of an earlier "
                "parameter group mapping"
            )
        else:
            seen.add(key)


def _validate_parameters(
    capture_to_semantic: Mapping[str, Any],
    declared_parameter_types: set[str],
    problems: list[str],
) -> None:
    items = _required_array(
        capture_to_semantic,
        "parameters",
        "captureToSemantic",
        problems,
    )
    if items is None:
        return
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(items):
        location = f"captureToSemantic.parameters[{index}]"
        if not isinstance(item, Mapping):
            problems.append(f"{location} must be an object")
            continue
        _allowed(item, location, _PARAMETER_FIELDS, problems)
        capture_kind = _required_string(item, "captureKind", location, problems)
        semantic_kind = _required_string(item, "semanticKind", location, problems)
        _exact_string(item, "identity", location, "capture.id", problems)
        _exact_string(item, "name", location, "capture.name", problems)
        _exact_string(item, "group", location, "capture.groupId", problems)

        semantic_type = _required_mapping(
            item,
            "semanticType",
            location,
            problems,
        )
        if semantic_type is not None:
            semantic_location = f"{location}.semanticType"
            _allowed(
                semantic_type,
                semantic_location,
                _PARAMETER_SEMANTIC_TYPE_FIELDS,
                problems,
            )
            _exact_string(
                semantic_type,
                "from",
                semantic_location,
                "capture.nativeType",
                problems,
            )
            native_map = _required_mapping(
                semantic_type,
                "map",
                semantic_location,
                problems,
            )
            if native_map is not None:
                if len(native_map) == 0:
                    problems.append(f"{semantic_location}.map must not be empty")
                for native_key in _sorted_keys(native_map):
                    key_location = f"{semantic_location}.map[{native_key!r}]"
                    if not isinstance(native_key, str) or native_key.strip() == "":
                        problems.append(
                            f"{semantic_location}.map key must not be empty"
                        )
                        continue
                    if native_key != native_key.strip():
                        problems.append(
                            f"{semantic_location}.map key {native_key!r} must "
                            "not have leading or trailing whitespace"
                        )
                        continue
                    semantic_type_name = native_map[native_key]
                    if (
                        not isinstance(semantic_type_name, str)
                        or semantic_type_name.strip() == ""
                    ):
                        problems.append(
                            f"{key_location} must reference a non-empty "
                            "semantic type key"
                        )
                    elif semantic_type_name != semantic_type_name.strip():
                        problems.append(
                            f"{key_location} must not have leading or trailing "
                            "whitespace"
                        )
                    elif semantic_type_name not in declared_parameter_types:
                        problems.append(
                            f"{key_location} references unknown "
                            f"semanticTypes.parameterTypes key "
                            f'"{semantic_type_name}"'
                        )

        if capture_kind is not None and semantic_kind is not None:
            key = (capture_kind, semantic_kind)
            if key in seen:
                problems.append(
                    f"{location} duplicates the natural key of an earlier "
                    "parameter mapping"
                )
            else:
                seen.add(key)


def _validate_components(
    capture_to_semantic: Mapping[str, Any],
    problems: list[str],
) -> None:
    items = _required_array(
        capture_to_semantic,
        "components",
        "captureToSemantic",
        problems,
    )
    if items is None:
        return
    seen: set[str] = set()
    for index, item in enumerate(items):
        location = f"captureToSemantic.components[{index}]"
        if not isinstance(item, Mapping):
            problems.append(f"{location} must be an object")
            continue
        _allowed(item, location, _COMPONENT_FIELDS, problems)
        capture_kind = _required_string(item, "captureKind", location, problems)
        _exact_string(item, "identity", location, "capture.id", problems)
        _exact_string(
            item,
            "targetability",
            location,
            "capture.targetability",
            problems,
        )
        semantic_kinds = _required_mapping(
            item,
            "semanticKinds",
            location,
            problems,
        )
        if semantic_kinds is not None:
            semantic_location = f"{location}.semanticKinds"
            if len(semantic_kinds) == 0:
                problems.append(f"{semantic_location} must not be empty")
            for native_kind in _sorted_keys(semantic_kinds):
                kind_location = f"{semantic_location}[{native_kind!r}]"
                if not isinstance(native_kind, str) or native_kind.strip() == "":
                    problems.append(f"{semantic_location} key must not be empty")
                    continue
                if native_kind != native_kind.strip():
                    problems.append(
                        f"{semantic_location} key {native_kind!r} must not have "
                        "leading or trailing whitespace"
                    )
                    continue
                semantic_target = semantic_kinds[native_kind]
                if (
                    not isinstance(semantic_target, str)
                    or semantic_target.strip() == ""
                ):
                    problems.append(f"{kind_location} is required")
                elif semantic_target != semantic_target.strip():
                    problems.append(
                        f"{kind_location} must not have leading or trailing whitespace"
                    )
                elif semantic_target not in _KNOWN_SEMANTIC_TARGETS:
                    problems.append(
                        f'{kind_location} "{semantic_target}" is not supported'
                    )
        if capture_kind is not None:
            if capture_kind in seen:
                problems.append(
                    f"{location} duplicates the natural key of an earlier "
                    "component mapping"
                )
            else:
                seen.add(capture_kind)


def _validate_metadata(
    capture_to_semantic: Mapping[str, Any],
    problems: list[str],
) -> None:
    items = _required_array(
        capture_to_semantic,
        "metadata",
        "captureToSemantic",
        problems,
    )
    if items is None:
        return
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(items):
        location = f"captureToSemantic.metadata[{index}]"
        if not isinstance(item, Mapping):
            problems.append(f"{location} must be an object")
            continue
        _allowed(item, location, _METADATA_FIELDS, problems)
        capture_kind = _required_string(item, "captureKind", location, problems)
        semantic_kind = _required_string(item, "semanticKind", location, problems)
        _exact_string(item, "identity", location, "capture.id", problems)
        _exact_string(item, "key", location, "capture.key", problems)
        _exact_string(
            item,
            "valueKind",
            location,
            "capture.nativeType",
            problems,
        )
        native_value_kinds = item.get("nativeValueKinds", _MISSING)
        if native_value_kinds is not _MISSING:
            if not isinstance(native_value_kinds, Mapping):
                problems.append(f"{location}.nativeValueKinds must be an object")
            elif len(native_value_kinds) == 0:
                problems.append(f"{location}.nativeValueKinds must not be empty")
            else:
                native_location = f"{location}.nativeValueKinds"
                for native_type in _sorted_keys(native_value_kinds):
                    value_location = f"{native_location}[{native_type!r}]"
                    if not isinstance(native_type, str) or native_type.strip() == "":
                        problems.append(f"{native_location} key must not be empty")
                        continue
                    if native_type != native_type.strip():
                        problems.append(
                            f"{native_location} key {native_type!r} must not "
                            "have leading or trailing whitespace"
                        )
                        continue
                    value_kind = native_value_kinds[native_type]
                    if not isinstance(value_kind, str) or value_kind.strip() == "":
                        problems.append(
                            f"{value_location} must reference a non-empty "
                            "metadata value kind"
                        )
                    elif value_kind != value_kind.strip():
                        problems.append(
                            f"{value_location} must not have leading or "
                            "trailing whitespace"
                        )
                    elif value_kind not in _SUPPORTED_METADATA_VALUE_KINDS:
                        problems.append(
                            f'{value_location} "{value_kind}" is not supported'
                        )
        if capture_kind is not None and semantic_kind is not None:
            key = (capture_kind, semantic_kind)
            if key in seen:
                problems.append(
                    f"{location} duplicates the natural key of an earlier "
                    "metadata mapping"
                )
            else:
                seen.add(key)


def _validate_semantic_to_manifest(
    mapping: Mapping[str, Any],
    problems: list[str],
) -> None:
    location = "semanticToManifest"
    _allowed(mapping, location, _SEMANTIC_TO_MANIFEST_FIELDS, problems)

    parameters = _required_mapping(mapping, "parameters", location, problems)
    if parameters is not None:
        parameter_location = f"{location}.parameters"
        _allowed(
            parameters,
            parameter_location,
            _PARAMETER_MANIFEST_FIELDS,
            problems,
        )
        _exact_string(
            parameters,
            "target",
            parameter_location,
            "parameterAssignments",
            problems,
        )
        _exact_string(
            parameters,
            "name",
            parameter_location,
            "semantic.parameter.name",
            problems,
        )
        _exact_string(
            parameters,
            "value",
            parameter_location,
            "resolved.value",
            problems,
        )
        _exact_string(parameters, "type", parameter_location, "number", problems)
        _exact_string(
            parameters,
            "unit",
            parameter_location,
            "resolved.unit",
            problems,
        )

    outputs = _required_mapping(mapping, "outputs", location, problems)
    if outputs is not None:
        for output_key in _sorted_keys(outputs):
            output_location = f"{location}.outputs[{output_key!r}]"
            if not isinstance(output_key, str) or output_key.strip() == "":
                problems.append(f"{location}.outputs key must not be empty")
                continue
            if output_key != output_key.strip():
                problems.append(
                    f"{location}.outputs key {output_key!r} must not have "
                    "leading or trailing whitespace"
                )
                continue
            entry = outputs[output_key]
            if not isinstance(entry, Mapping):
                problems.append(f"{output_location} must be an object")
                continue
            _allowed(entry, output_location, _OUTPUT_MANIFEST_FIELDS, problems)
            manifest_type = _required_string(
                entry,
                "manifestType",
                output_location,
                problems,
            )
            if manifest_type is None:
                continue
            if manifest_type not in _KNOWN_OUTPUT_MANIFEST_TYPES:
                problems.append(
                    f'{output_location}.manifestType "{manifest_type}" is not supported'
                )
                continue
            if manifest_type == "step":
                _exact_string(
                    entry,
                    "targetField",
                    output_location,
                    "object",
                    problems,
                )
                _exact_string(
                    entry,
                    "targetSource",
                    output_location,
                    "semantic.output.target.manifestName",
                    problems,
                )
                _forbid_field(entry, "scopeField", output_location, problems)
                _forbid_field(entry, "scopeMap", output_location, problems)
            elif manifest_type == "csv":
                _exact_string(
                    entry,
                    "targetField",
                    output_location,
                    "target",
                    problems,
                )
                _exact_string(
                    entry,
                    "targetSource",
                    output_location,
                    "semantic.output.target.manifestName",
                    problems,
                )
                _exact_string(
                    entry,
                    "scopeField",
                    output_location,
                    "rollup",
                    problems,
                )
                scope_map = _required_mapping(
                    entry,
                    "scopeMap",
                    output_location,
                    problems,
                )
                if scope_map is not None:
                    if len(scope_map) == 0:
                        problems.append(f"{output_location}.scopeMap must not be empty")
                    for scope_key in _sorted_keys(scope_map):
                        scope_location = f"{output_location}.scopeMap[{scope_key!r}]"
                        if not isinstance(scope_key, str) or scope_key.strip() == "":
                            problems.append(
                                f"{output_location}.scopeMap key must not be empty"
                            )
                            continue
                        if scope_key != scope_key.strip():
                            problems.append(
                                f"{output_location}.scopeMap key {scope_key!r} "
                                "must not have leading or trailing whitespace"
                            )
                            continue
                        scope_value = scope_map[scope_key]
                        if (
                            not isinstance(scope_value, str)
                            or scope_value.strip() == ""
                        ):
                            problems.append(f"{scope_location} is required")
                        elif scope_value != scope_value.strip():
                            problems.append(
                                f"{scope_location} must not have leading or "
                                "trailing whitespace"
                            )
            elif manifest_type == "pdf":
                _forbid_field(entry, "targetField", output_location, problems)
                _forbid_field(entry, "targetSource", output_location, problems)
                _forbid_field(entry, "scopeField", output_location, problems)
                _forbid_field(entry, "scopeMap", output_location, problems)

    mutations = _required_mapping(mapping, "mutations", location, problems)
    if mutations is not None:
        for mutation_key in _sorted_keys(mutations):
            mutation_location = f"{location}.mutations[{mutation_key!r}]"
            if not isinstance(mutation_key, str) or mutation_key.strip() == "":
                problems.append(f"{location}.mutations key must not be empty")
                continue
            if mutation_key != mutation_key.strip():
                problems.append(
                    f"{location}.mutations key {mutation_key!r} must not have "
                    "leading or trailing whitespace"
                )
                continue
            entry = mutations[mutation_key]
            if not isinstance(entry, Mapping):
                problems.append(f"{mutation_location} must be an object")
                continue
            _allowed(entry, mutation_location, _MUTATION_MAPPING_FIELDS, problems)
            collection = _required_string(
                entry,
                "manifestCollection",
                mutation_location,
                problems,
            )
            if collection is None:
                continue
            if collection not in _KNOWN_MUTATION_COLLECTIONS:
                problems.append(
                    f'{mutation_location}.manifestCollection "{collection}" '
                    "is not supported"
                )
                continue
            if collection.endswith(".suppression"):
                _exact_string(
                    entry,
                    "targetField",
                    mutation_location,
                    "object",
                    problems,
                )
                _exact_string(
                    entry,
                    "valueField",
                    mutation_location,
                    "suppressed",
                    problems,
                )
                _required_bool(entry, "value", mutation_location, problems)
                _forbid_field(entry, "propertyField", mutation_location, problems)
            elif collection.endswith(".visibility"):
                _exact_string(
                    entry,
                    "targetField",
                    mutation_location,
                    "object",
                    problems,
                )
                _exact_string(
                    entry,
                    "valueField",
                    mutation_location,
                    "visible",
                    problems,
                )
                _required_bool(entry, "value", mutation_location, problems)
                _forbid_field(entry, "propertyField", mutation_location, problems)
            elif collection.endswith(".deletion"):
                _exact_string(
                    entry,
                    "targetField",
                    mutation_location,
                    "object",
                    problems,
                )
                _forbid_field(entry, "valueField", mutation_location, problems)
                _forbid_field(entry, "value", mutation_location, problems)
                _forbid_field(entry, "propertyField", mutation_location, problems)
            elif collection.endswith(".parameters"):
                _exact_string(
                    entry,
                    "targetField",
                    mutation_location,
                    "object",
                    problems,
                )
                _exact_string(
                    entry,
                    "propertyField",
                    mutation_location,
                    "property",
                    problems,
                )
                _exact_string(
                    entry,
                    "valueField",
                    mutation_location,
                    "valueParam",
                    problems,
                )
                _forbid_field(entry, "value", mutation_location, problems)


def _validate_operation_capabilities(
    value: Mapping[str, Any],
    problems: list[str],
) -> None:
    capabilities = _required_mapping(
        value,
        "operationCapabilities",
        "",
        problems,
    )
    if capabilities is None:
        return
    for operation in _sorted_keys(capabilities):
        location = f"operationCapabilities[{operation!r}]"
        if not isinstance(operation, str) or operation.strip() == "":
            problems.append("operationCapabilities key must not be empty")
            continue
        if operation != operation.strip():
            problems.append(
                f"operationCapabilities key {operation!r} must not have leading "
                "or trailing whitespace"
            )
            continue
        if operation not in _SUPPORTED_OPERATION_NAMES:
            problems.append(f"operationCapabilities[{operation!r}] is not supported")
            continue
        entry = capabilities[operation]
        if not isinstance(entry, Mapping):
            problems.append(f"{location} must be an object")
            continue
        _allowed(entry, location, _CAPABILITY_FIELDS, problems)
        _optional_string(entry, "requiresTargetability", location, problems)
        requires_writable = entry.get("requiresWritable", _MISSING)
        if requires_writable is not _MISSING and not isinstance(
            requires_writable,
            bool,
        ):
            problems.append(f"{location}.requiresWritable must be a boolean")
        targets = _required_array(
            entry,
            "allowedSemanticTargets",
            location,
            problems,
        )
        if targets is None:
            continue
        if len(targets) == 0:
            problems.append(f"{location}.allowedSemanticTargets must not be empty")
        seen: set[str] = set()
        for index, target in enumerate(targets):
            target_location = f"{location}.allowedSemanticTargets[{index}]"
            if not isinstance(target, str) or target.strip() == "":
                problems.append(f"{target_location} is required")
                continue
            if target != target.strip():
                problems.append(
                    f"{target_location} must not have leading or trailing whitespace"
                )
                continue
            if target not in _KNOWN_SEMANTIC_TARGETS:
                problems.append(f'{target_location} "{target}" is not supported')
                continue
            if target in seen:
                problems.append(
                    f"{target_location} duplicates an earlier semantic target"
                )
                continue
            seen.add(target)


# ---------------------------------------------------------------------------
# Small deterministic validation helpers
# ---------------------------------------------------------------------------


def _allowed(
    value: Mapping[str, Any],
    location: str,
    allowed: tuple[str, ...],
    problems: list[str],
) -> None:
    for key in _sorted_keys(value):
        if key not in allowed:
            problems.append(f'{location or "root"} has unknown field "{key}"')


def _required_mapping(
    value: Mapping[str, Any],
    field: str,
    path: str,
    problems: list[str],
) -> Mapping[str, Any] | None:
    field_path = _join(path, field)
    if field not in value:
        problems.append(f"{field_path} is required")
        return None
    candidate = value[field]
    if not isinstance(candidate, Mapping):
        problems.append(f"{field_path} must be an object")
        return None
    return candidate


def _required_array(
    value: Mapping[str, Any],
    field: str,
    path: str,
    problems: list[str],
) -> list[Any] | None:
    field_path = _join(path, field)
    if field not in value:
        problems.append(f"{field_path} is required")
        return None
    candidate = value[field]
    if not isinstance(candidate, list):
        problems.append(f"{field_path} must be an array")
        return None
    return candidate


def _required_string(
    value: Mapping[str, Any],
    field: str,
    path: str,
    problems: list[str],
) -> str | None:
    field_path = _join(path, field)
    if field not in value:
        problems.append(f"{field_path} is required")
        return None
    candidate = value[field]
    if not isinstance(candidate, str):
        problems.append(f"{field_path} must be a string")
        return None
    if candidate.strip() == "":
        problems.append(f"{field_path} is required")
        return None
    if candidate != candidate.strip():
        problems.append(f"{field_path} must not have leading or trailing whitespace")
        return None
    return candidate


def _optional_string(
    value: Mapping[str, Any],
    field: str,
    path: str,
    problems: list[str],
) -> str | None:
    if field not in value:
        return None
    field_path = _join(path, field)
    candidate = value[field]
    if not isinstance(candidate, str):
        problems.append(f"{field_path} must be a string")
        return None
    if candidate.strip() == "":
        problems.append(f"{field_path} is required")
        return None
    if candidate != candidate.strip():
        problems.append(f"{field_path} must not have leading or trailing whitespace")
        return None
    return candidate


def _required_bool(
    value: Mapping[str, Any],
    field: str,
    path: str,
    problems: list[str],
) -> bool | None:
    field_path = _join(path, field)
    if field not in value:
        problems.append(f"{field_path} is required")
        return None
    candidate = value[field]
    if not isinstance(candidate, bool):
        problems.append(f"{field_path} must be a boolean")
        return None
    return candidate


def _required_false_bool(
    value: Mapping[str, Any],
    field: str,
    path: str,
    problems: list[str],
) -> None:
    field_path = _join(path, field)
    candidate = _required_bool(value, field, path, problems)
    if candidate is True:
        problems.append(f"{field_path} must be false")


def _exact_string(
    value: Mapping[str, Any],
    field: str,
    path: str,
    expected: str,
    problems: list[str],
) -> None:
    field_path = _join(path, field)
    candidate = _required_string(value, field, path, problems)
    if candidate is not None and candidate != expected:
        problems.append(f'{field_path} must equal "{expected}"')


def _forbid_field(
    value: Mapping[str, Any],
    field: str,
    path: str,
    problems: list[str],
) -> None:
    if field not in value:
        return
    candidate = value[field]
    if candidate in (None, "", {}, []):
        return
    problems.append(f"{_join(path, field)} must not be set")


def _join(path: str, field: str) -> str:
    return f"{path}.{field}" if path else field


def _sorted_keys(value: Mapping[Any, Any]) -> list[Any]:
    try:
        return sorted(value)
    except TypeError:
        return sorted(value, key=lambda key: (str(type(key)), str(key)))


# ---------------------------------------------------------------------------
# Diff and merge planning
# ---------------------------------------------------------------------------


def plan_semantic_map_update(
    path: str | os.PathLike[str],
    generated: Mapping[str, Any],
) -> SemanticMapUpdatePlan:
    """Plan a create, no-op, or confirmed merge for an explicit destination."""

    validate_semantic_map(generated)
    generated_copy = copy.deepcopy(dict(generated))
    target = Path(path)

    if not target.exists():
        return SemanticMapUpdatePlan(
            path=target,
            status="create",
            generated=generated_copy,
            existing=None,
            merged=generated_copy,
            diff=(),
            requires_confirmation=False,
        )
    if not target.is_file():
        raise SemanticMapWriteError(
            f"semantic map update failed for {target}: target is not a file"
        )

    try:
        existing_bytes = target.read_bytes()
    except OSError as exc:
        raise SemanticMapWriteError(
            f"semantic map update failed for {target}: {exc}"
        ) from exc

    try:
        decoded = loads_strict_json(existing_bytes)
    except StrictJsonError as exc:
        raise SemanticMapDecodeError(
            f"invalid existing semantic map JSON at {target}: {exc}"
        ) from exc
    if not isinstance(decoded, Mapping):
        raise SemanticMapDecodeError(
            f"existing semantic map at {target} must be a JSON object"
        )

    validate_semantic_map(decoded)
    existing = _canonicalize_semantic_map(decoded)
    _require_freecad_identity(existing, target)

    merged = _merge_preserved_sections(existing, generated_copy)
    validate_semantic_map(merged)
    merged = _canonicalize_semantic_map(merged)

    existing_bytes_canonical = canonical_semantic_map_bytes(existing)
    merged_bytes_canonical = canonical_semantic_map_bytes(merged)
    if existing_bytes_canonical == merged_bytes_canonical:
        return SemanticMapUpdatePlan(
            path=target,
            status="unchanged",
            generated=generated_copy,
            existing=existing,
            merged=merged,
            diff=(),
            requires_confirmation=False,
        )

    diff = _diff_semantic_maps(existing, merged)
    return SemanticMapUpdatePlan(
        path=target,
        status="merge",
        generated=generated_copy,
        existing=existing,
        merged=merged,
        diff=diff,
        requires_confirmation=True,
    )


def _require_freecad_identity(
    existing: Mapping[str, Any],
    path: Path,
) -> None:
    adapter = existing.get("adapter")
    cad_system = existing.get("cadSystem")
    cad_system_name = (
        cad_system.get("name") if isinstance(cad_system, Mapping) else None
    )
    if adapter != FREECAD_ADAPTER_NAME or cad_system_name != FREECAD_CAD_SYSTEM_NAME:
        raise SemanticMapIdentityError(
            f"existing semantic map at {path} targets adapter {adapter!r} and "
            f"CAD system {cad_system_name!r}; FreeCAD template merge is not "
            "allowed"
        )


def _merge_preserved_sections(
    existing: Mapping[str, Any],
    generated: Mapping[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(dict(generated))
    for section_path in _PRESERVED_SECTION_PATHS:
        value = _get_path(existing, section_path)
        if value is _MISSING:
            continue
        _set_path(merged, section_path, copy.deepcopy(value))
    return merged


def _get_path(value: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return _MISSING
        current = current[key]
    return current


def _set_path(
    value: dict[str, Any],
    path: tuple[str, ...],
    new_value: Any,
) -> None:
    current: dict[str, Any] = value
    for key in path[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            return
        current = child
    current[path[-1]] = new_value


def _diff_semantic_maps(
    existing: Mapping[str, Any],
    proposed: Mapping[str, Any],
) -> tuple[SemanticMapDiffEntry, ...]:
    entries: list[SemanticMapDiffEntry] = []
    _diff_value(existing, proposed, "", entries)
    entries.sort(key=lambda entry: entry.path)
    return tuple(entries)


def _diff_value(
    existing: Any,
    proposed: Any,
    path: str,
    entries: list[SemanticMapDiffEntry],
) -> None:
    if isinstance(existing, Mapping) and isinstance(proposed, Mapping):
        keys = sorted(
            set(existing) | set(proposed),
            key=lambda key: str(key),
        )
        for key in keys:
            child_path = f"{path}/{_pointer_escape(str(key))}"
            if key not in existing:
                entries.append(
                    SemanticMapDiffEntry(
                        path=child_path,
                        change="added",
                        proposed=copy.deepcopy(proposed[key]),
                    )
                )
            elif key not in proposed:
                entries.append(
                    SemanticMapDiffEntry(
                        path=child_path,
                        change="removed",
                        existing=copy.deepcopy(existing[key]),
                    )
                )
            else:
                _diff_value(
                    existing[key],
                    proposed[key],
                    child_path,
                    entries,
                )
        return

    if isinstance(existing, list) and isinstance(proposed, list):
        for index in range(max(len(existing), len(proposed))):
            child_path = f"{path}/{index}"
            if index >= len(existing):
                entries.append(
                    SemanticMapDiffEntry(
                        path=child_path,
                        change="added",
                        proposed=copy.deepcopy(proposed[index]),
                    )
                )
            elif index >= len(proposed):
                entries.append(
                    SemanticMapDiffEntry(
                        path=child_path,
                        change="removed",
                        existing=copy.deepcopy(existing[index]),
                    )
                )
            else:
                _diff_value(
                    existing[index],
                    proposed[index],
                    child_path,
                    entries,
                )
        return

    if existing != proposed:
        entries.append(
            SemanticMapDiffEntry(
                path=path,
                change="changed",
                existing=copy.deepcopy(existing),
                proposed=copy.deepcopy(proposed),
            )
        )


def _pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


# ---------------------------------------------------------------------------
# Atomic writing
# ---------------------------------------------------------------------------


def write_semantic_map(
    path: str | os.PathLike[str],
    generated: Mapping[str, Any],
    *,
    confirm_replace: bool,
) -> SemanticMapWriteResult:
    """Atomically create or merge a semantic map at an explicit path.

    ``confirm_replace`` is a required explicit decision. An existing map is
    never replaced when it differs unless this is exactly ``True``.
    """

    if not isinstance(confirm_replace, bool):
        raise TypeError("confirm_replace must be an explicit bool decision")

    plan = plan_semantic_map_update(path, generated)
    if plan.status == "unchanged":
        return SemanticMapWriteResult(
            path=plan.path,
            status=plan.status,
            wrote=False,
            diff=(),
        )

    if plan.status == "create":
        data = canonical_semantic_map_bytes(plan.merged)
        _atomic_write(plan.path, data, overwrite=False)
        return SemanticMapWriteResult(
            path=plan.path,
            status=plan.status,
            wrote=True,
            diff=(),
        )

    if not confirm_replace:
        raise SemanticMapConfirmationRequiredError(plan.path, plan.diff)

    data = canonical_semantic_map_bytes(plan.merged)
    _atomic_write(plan.path, data, overwrite=True)
    return SemanticMapWriteResult(
        path=plan.path,
        status=plan.status,
        wrote=True,
        diff=plan.diff,
    )


def update_semantic_map(
    path: str | os.PathLike[str],
    selection: FreeCADSemanticMapSelection,
    *,
    confirm_replace: bool,
) -> SemanticMapWriteResult:
    """Build from explicit selections and atomically update ``path``."""

    generated = build_semantic_map(selection)
    return write_semantic_map(path, generated, confirm_replace=confirm_replace)


def _atomic_write(target: Path, data: bytes, *, overwrite: bool) -> None:
    if not target.parent.is_dir():
        raise SemanticMapWriteError(
            f"semantic map write failed for {target}: parent directory does not exist"
        )
    if not overwrite and target.exists():
        raise SemanticMapWriteError(
            f"semantic map write failed for {target}: target already exists"
        )

    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

        if overwrite:
            os.replace(temporary_path, target)
            temporary_path = None
        else:
            try:
                os.link(temporary_path, target)
            except FileExistsError as exc:
                raise SemanticMapWriteError(
                    f"semantic map write failed for {target}: target already exists"
                ) from exc
            os.unlink(temporary_path)
            temporary_path = None
    except SemanticMapWriteError:
        raise
    except OSError as exc:
        raise SemanticMapWriteError(
            f"semantic map write failed for {target}: {exc}"
        ) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


__all__ = [
    "FREECAD_ADAPTER_NAME",
    "FREECAD_CAD_SYSTEM_MIN_VERSION",
    "FREECAD_CAD_SYSTEM_NAME",
    "FREECAD_SEMANTIC_MAP_TEMPLATE_VERSION",
    "FreeCADSemanticMapSelection",
    "SEMANTIC_MAP_FILENAME",
    "SEMANTIC_MAP_SCHEMA_VERSION",
    "SemanticMapConfirmationRequiredError",
    "SemanticMapContractError",
    "SemanticMapDecodeError",
    "SemanticMapDiffEntry",
    "SemanticMapError",
    "SemanticMapIdentityError",
    "SemanticMapSelectionError",
    "SemanticMapUpdatePlan",
    "SemanticMapWriteError",
    "SemanticMapWriteResult",
    "SemanticParameterTypeSelection",
    "build_semantic_map",
    "canonical_semantic_map_bytes",
    "canonical_semantic_map_text",
    "freecad_semantic_map_template",
    "plan_semantic_map_update",
    "update_semantic_map",
    "validate_semantic_map",
    "write_semantic_map",
]
