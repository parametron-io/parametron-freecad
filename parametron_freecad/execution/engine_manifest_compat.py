"""Compatibility boundary for Engine-generated export manifests.

This module adapts only deterministic, evidence-backed Engine manifest fields
to the narrower Parametron FreeCAD execution manifest shape. It does not infer
CAD parameter targets from adapter-neutral Engine parameter names.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from parametron_freecad.execution.manifest_contract import (
    EXPORT_MANIFEST_V1_CONTRACT,
)
from parametron_freecad.execution.manifest_loader import LoadedManifest

ManifestShape = Literal["freecad_internal", "engine_generated", "unknown"]

MANIFEST_SHAPE_FREECAD_INTERNAL: ManifestShape = "freecad_internal"
MANIFEST_SHAPE_ENGINE_GENERATED: ManifestShape = "engine_generated"
MANIFEST_SHAPE_UNKNOWN: ManifestShape = "unknown"

ENGINE_FIELD_INPUTS = "inputs"
ENGINE_FIELD_INPUT_SOURCE_MODEL = "sourceModel"
ENGINE_FIELD_OUTPUT_TYPE = "type"
ENGINE_FIELD_OUTPUT_FILENAME = "filename"
ENGINE_FIELD_OUTPUT_OBJECT = "object"
ENGINE_FIELD_PARAMETER_NAME = "name"
ENGINE_FIELD_PARAMETER_TYPE = "type"

_contract = EXPORT_MANIFEST_V1_CONTRACT


class EngineManifestCompatibilityError(ValueError):
    """Raised when an Engine manifest cannot be safely adapted."""


class EngineManifestUnsupportedParameterTargetError(
    EngineManifestCompatibilityError
):
    """Raised when Engine parameter names cannot be mapped to CAD targets."""


class EngineManifestUnsupportedOutputTargetError(EngineManifestCompatibilityError):
    """Raised when an Engine output cannot be mapped to an internal output id."""


def detect_export_manifest_shape(data: Mapping[str, Any]) -> ManifestShape:
    """Classify a decoded manifest without mutating it."""

    if _looks_like_freecad_internal_manifest(data):
        return MANIFEST_SHAPE_FREECAD_INTERNAL

    if _looks_like_engine_generated_manifest(data):
        return MANIFEST_SHAPE_ENGINE_GENERATED

    return MANIFEST_SHAPE_UNKNOWN


def normalize_loaded_export_manifest_v1(
    loaded_manifest: LoadedManifest,
) -> LoadedManifest:
    """Return a loaded manifest with Engine shape adapted for execution.

    FreeCAD-internal and unknown shapes are returned unchanged so the existing
    internal manifest validator remains the authority for those payloads.
    """

    if detect_export_manifest_shape(loaded_manifest.data) != MANIFEST_SHAPE_ENGINE_GENERATED:
        return loaded_manifest

    return LoadedManifest(
        path=loaded_manifest.path,
        data=normalize_engine_export_manifest_v1(loaded_manifest.data),
    )


def normalize_engine_export_manifest_v1(
    data: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Normalize deterministic Engine manifest fields to the internal shape."""

    normalized: dict[str, Any] = {}

    if _contract.schema_version_field in data:
        normalized[_contract.schema_version_field] = data[
            _contract.schema_version_field
        ]

    normalized[_contract.source_document_field] = _normalize_source_document(data)
    normalized[_contract.parameter_assignments_field] = (
        _normalize_parameter_assignments(data)
    )
    normalized[_contract.outputs_field] = _normalize_outputs(data)

    return normalized


def _looks_like_freecad_internal_manifest(data: Mapping[str, Any]) -> bool:
    if _contract.source_document_field in data:
        return True

    parameter_assignments = data.get(_contract.parameter_assignments_field)
    if _sequence_contains_mapping_field(
        parameter_assignments,
        _contract.parameter_assignment.target_field,
    ):
        return True

    outputs = data.get(_contract.outputs_field)
    return (
        _sequence_contains_mapping_field(outputs, _contract.output.id_field)
        or _sequence_contains_mapping_field(outputs, _contract.output.format_field)
        or _sequence_contains_mapping_field(outputs, _contract.output.path_field)
    )


def _looks_like_engine_generated_manifest(data: Mapping[str, Any]) -> bool:
    for field_name in ("planHash", "adapter", "product", "values", ENGINE_FIELD_INPUTS):
        if field_name in data:
            return True

    parameter_assignments = data.get(_contract.parameter_assignments_field)
    if (
        _sequence_contains_mapping_field(parameter_assignments, ENGINE_FIELD_PARAMETER_NAME)
        or _sequence_contains_mapping_field(parameter_assignments, "unit")
    ):
        return True

    outputs = data.get(_contract.outputs_field)
    return (
        _sequence_contains_mapping_field(outputs, ENGINE_FIELD_OUTPUT_TYPE)
        or _sequence_contains_mapping_field(outputs, ENGINE_FIELD_OUTPUT_FILENAME)
    )


def _sequence_contains_mapping_field(value: Any, field_name: str) -> bool:
    if not isinstance(value, list):
        return False

    return any(isinstance(item, Mapping) and field_name in item for item in value)


def _normalize_source_document(data: Mapping[str, Any]) -> str:
    inputs = data.get(ENGINE_FIELD_INPUTS)
    if not isinstance(inputs, Mapping):
        raise EngineManifestCompatibilityError(
            "Engine export manifest requires inputs.sourceModel to normalize "
            "sourceDocument"
        )

    source_model = inputs.get(ENGINE_FIELD_INPUT_SOURCE_MODEL)
    if not isinstance(source_model, str) or source_model.strip() == "":
        raise EngineManifestCompatibilityError(
            "Engine export manifest inputs.sourceModel must be a non-empty "
            "string to normalize sourceDocument"
        )

    return source_model


def _normalize_parameter_assignments(
    data: Mapping[str, Any],
) -> list[dict[str, Any]]:
    assignments = data.get(_contract.parameter_assignments_field, [])
    if assignments is None:
        return []
    if not isinstance(assignments, list):
        raise EngineManifestCompatibilityError(
            "Engine export manifest parameterAssignments must be a list"
        )

    normalized: list[dict[str, Any]] = []
    for index, assignment in enumerate(assignments):
        if not isinstance(assignment, Mapping):
            raise EngineManifestCompatibilityError(
                f"Engine export manifest parameterAssignments[{index}] must be an object"
            )

        target = assignment.get(_contract.parameter_assignment.target_field)
        if target is None:
            name = assignment.get(ENGINE_FIELD_PARAMETER_NAME)
            raise EngineManifestUnsupportedParameterTargetError(
                "Engine export manifest parameterAssignments"
                f"[{index}].name {name!r} is adapter-neutral and cannot be "
                "normalized to the required FreeCAD target format "
                "<ObjectName>.<PropertyName>; an explicit CAD target or "
                "semantic-map projection is required before execution"
            )

        value_kind = assignment.get(_contract.parameter_assignment.value_kind_field)
        if value_kind is None:
            value_kind = assignment.get(ENGINE_FIELD_PARAMETER_TYPE)
        if value_kind is None:
            value_kind = "engine"

        normalized.append(
            {
                _contract.parameter_assignment.target_field: target,
                _contract.parameter_assignment.value_field: assignment.get(
                    _contract.parameter_assignment.value_field
                ),
                _contract.parameter_assignment.value_kind_field: value_kind,
            }
        )

    return normalized


def _normalize_outputs(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    outputs = data.get(_contract.outputs_field)
    if not isinstance(outputs, list):
        raise EngineManifestCompatibilityError(
            "Engine export manifest outputs must be a list"
        )

    normalized: list[dict[str, Any]] = []
    for index, output in enumerate(outputs):
        if not isinstance(output, Mapping):
            raise EngineManifestCompatibilityError(
                f"Engine export manifest outputs[{index}] must be an object"
            )

        output_format = output.get(ENGINE_FIELD_OUTPUT_TYPE)
        filename = output.get(ENGINE_FIELD_OUTPUT_FILENAME)
        if output_format != "step":
            raise EngineManifestUnsupportedOutputTargetError(
                "Engine export manifest outputs"
                f"[{index}].type {output_format!r} cannot be normalized to the "
                "current internal output contract without changing output "
                "semantics"
            )
        if not isinstance(filename, str) or filename.strip() == "":
            raise EngineManifestCompatibilityError(
                f"Engine export manifest outputs[{index}].filename must be a "
                "non-empty string"
            )

        object_name = output.get(ENGINE_FIELD_OUTPUT_OBJECT)
        if not isinstance(object_name, str) or object_name.strip() == "":
            raise EngineManifestUnsupportedOutputTargetError(
                "Engine export manifest step output "
                f"outputs[{index}].object must be a non-empty string to "
                "normalize outputs[].id"
            )

        normalized.append(
            {
                _contract.output.id_field: object_name,
                _contract.output.format_field: output_format,
                _contract.output.path_field: filename,
            }
        )

    return normalized


__all__ = [
    "EngineManifestCompatibilityError",
    "EngineManifestUnsupportedOutputTargetError",
    "EngineManifestUnsupportedParameterTargetError",
    "MANIFEST_SHAPE_ENGINE_GENERATED",
    "MANIFEST_SHAPE_FREECAD_INTERNAL",
    "MANIFEST_SHAPE_UNKNOWN",
    "ManifestShape",
    "detect_export_manifest_shape",
    "normalize_engine_export_manifest_v1",
    "normalize_loaded_export_manifest_v1",
]
