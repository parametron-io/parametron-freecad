"""GUI-free semantic-map selection loading for the workbench session.

The workbench reuses the project's semantic mapping when one exists and falls
back to a conservative default otherwise. Defaults only cover native scalar
types the capture core can actually resolve; unsupported native types remain
unmapped and are shown as disabled in the Parameters tab.

This module never imports FreeCAD, FreeCADGui, or Qt.
"""

from __future__ import annotations

from parametron_freecad.capture import (
    SEMANTIC_MAP_FILENAME,
    CaptureDiscovery,
    FreeCADSemanticMapSelection,
    SemanticMapContractError,
    SemanticMapDecodeError,
    SemanticParameterTypeSelection,
    validate_semantic_map,
)
from parametron_freecad.capture.project import CaptureProjectContext
from parametron_freecad.common.strict_json import StrictJsonError, loads_strict_json

DEFAULT_SEMANTIC_TYPES: dict[str, tuple[str, str, str]] = {
    "length": ("number", "mm", "number_to_length"),
    "dimensionless": ("number", "none", "number_to_dimensionless"),
    "count": ("integer", "count", "number_to_integer_exact"),
}

_DEFAULT_NATIVE_MAP: dict[str, str] = {
    "App::PropertyLength": "length",
    "App::PropertyDistance": "length",
    "App::PropertyFloat": "dimensionless",
    "App::PropertyFloatConstraint": "dimensionless",
    "App::PropertyInteger": "count",
    "App::PropertyIntegerConstraint": "count",
}


def build_default_semantic_selection(
    discovery: CaptureDiscovery,
    *,
    mapping_id: str = "workbench-capture-v1",
    cad_system_min_version: str = "",
) -> FreeCADSemanticMapSelection:
    """Return a conservative selection covering discovered scalar parameters.

    The Engine requires at least one parameter type, so ``length`` is always
    declared. Native types without a safe default are left unmapped.
    """

    native_map: dict[str, str] = {}
    for candidate in discovery.parameters:
        native_type = candidate.property.native_type_id
        if not candidate.property.supported or native_type is None:
            continue
        semantic = _DEFAULT_NATIVE_MAP.get(native_type)
        if semantic is not None:
            native_map[native_type] = semantic

    used = set(native_map.values())
    used.add("length")
    parameter_types = tuple(
        SemanticParameterTypeSelection(
            name,
            DEFAULT_SEMANTIC_TYPES[name][0],
            DEFAULT_SEMANTIC_TYPES[name][1],
            DEFAULT_SEMANTIC_TYPES[name][2],
        )
        for name in sorted(used)
    )
    return FreeCADSemanticMapSelection(
        mapping_id=mapping_id,
        parameter_types=parameter_types,
        native_type_to_semantic_type=native_map,
        cad_system_min_version=cad_system_min_version,
    )


def load_semantic_selection(
    context: CaptureProjectContext,
    discovery: CaptureDiscovery,
    *,
    mapping_id: str = "workbench-capture-v1",
    cad_system_min_version: str = "",
) -> FreeCADSemanticMapSelection:
    """Load the project's semantic map, or build a conservative default."""

    path = context.root / SEMANTIC_MAP_FILENAME
    if not path.is_file():
        return build_default_semantic_selection(
            discovery,
            mapping_id=mapping_id,
            cad_system_min_version=cad_system_min_version,
        )

    try:
        decoded = loads_strict_json(path.read_bytes())
    except StrictJsonError as exc:
        raise SemanticMapDecodeError(
            f"invalid existing semantic map JSON at {path}: {exc}"
        ) from exc
    validate_semantic_map(decoded)

    try:
        parameter_types = tuple(
            SemanticParameterTypeSelection(
                name=name,
                value_kind=entry["valueKind"],
                default_unit=entry["defaultUnit"],
                coercion=entry["coercion"],
            )
            for name, entry in sorted(
                decoded["semanticTypes"]["parameterTypes"].items()
            )
        )
    except (KeyError, TypeError) as exc:
        raise SemanticMapContractError(
            ["semantic map parameterTypes are not usable for capture"]
        ) from exc

    native_map = decoded["captureToSemantic"]["parameters"][0]["semanticType"]["map"]
    return FreeCADSemanticMapSelection(
        mapping_id=decoded["mappingId"],
        parameter_types=parameter_types,
        native_type_to_semantic_type=dict(native_map),
        cad_system_min_version=decoded["cadSystem"]["minVersion"],
    )


__all__ = [
    "DEFAULT_SEMANTIC_TYPES",
    "build_default_semantic_selection",
    "load_semantic_selection",
]
