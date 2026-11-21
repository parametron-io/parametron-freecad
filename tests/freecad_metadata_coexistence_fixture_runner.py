"""Test-only FreeCAD host for the metadata mutation coexistence fixture.

Not production code. Opens an arbitrary ``.FCStd`` file with real FreeCAD and
emits a deterministic JSON semantic inventory used by permanent fixture tests.

    nix develop --command freecadcmd \
      tests/freecad_metadata_coexistence_fixture_runner.py \
      --pass=/absolute/path/to/document.FCStd \
      --pass=/absolute/path/to/output.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD as App

from parametron_freecad.execution.deletion import (
    DeletionMutationError,
    apply_deletion_mutations,
)

PASS_PREFIX = "--pass="

BODY_NAME = "MetadataBody"
SKETCH_NAME = "ProfileSketch"
PAD_NAME = "Pad"
MARKER_NAME = "DeletionMarker"
VARSET_NAME = "Parameters"
PARAMETER_NAME = "pilotValue"

METADATA_PROPERTY_NAMES = (
    "material",
    "tagged",
    "mass",
    "revision",
    "tolerance",
    "sequence",
    "measured_length",
)

MISSING_PROPERTY_NAME = "supplier"
READ_ONLY_PROPERTY_NAME = "_ExternalGeoVersion"


def _arguments() -> tuple[Path, Path]:
    values = [
        argument[len(PASS_PREFIX) :]
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 2:
        raise RuntimeError("runner requires source and output --pass arguments")
    return Path(values[0]), Path(values[1])


def _close_all_documents() -> None:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)


def _linked_object_name(value) -> str:
    linked = value[0] if isinstance(value, tuple) else value
    return linked.Name


def _property_value(native_object, name: str):
    value = getattr(native_object, name)
    if hasattr(value, "Value"):
        return float(value.Value)
    return value


def _metadata_group_properties(native_object) -> list[str]:
    names: list[str] = []
    for name in native_object.PropertiesList:
        try:
            if native_object.getGroupOfProperty(name) == "Metadata":
                names.append(name)
        except Exception:
            continue
    return sorted(names)


def _metadata_properties(native_object) -> dict[str, dict[str, object]]:
    inventory: dict[str, dict[str, object]] = {}
    for name in METADATA_PROPERTY_NAMES:
        if name not in native_object.PropertiesList:
            inventory[name] = {"present": False}
            continue
        inventory[name] = {
            "present": True,
            "typeId": native_object.getTypeIdOfProperty(name),
            "value": _property_value(native_object, name),
        }
    return inventory


def _shape_inventory(shape) -> dict[str, object]:
    return {
        "isNull": shape.isNull(),
        "isValid": shape.isValid(),
        "solidCount": len(shape.Solids),
    }


def _inspect(document) -> dict[str, object]:
    body = document.getObject(BODY_NAME)
    sketch = document.getObject(SKETCH_NAME)
    pad = document.getObject(PAD_NAME)
    marker = document.getObject(MARKER_NAME)
    var_set = document.getObject(VARSET_NAME)
    missing = [
        name
        for name, value in (
            (BODY_NAME, body),
            (SKETCH_NAME, sketch),
            (PAD_NAME, pad),
            (MARKER_NAME, marker),
            (VARSET_NAME, var_set),
        )
        if value is None
    ]
    if missing:
        raise RuntimeError(f"fixture missing expected objects: {missing!r}")

    document.recompute()

    read_only_present = READ_ONLY_PROPERTY_NAME in sketch.PropertiesList
    read_only_write_rejected = None
    read_only_error_type = None
    if read_only_present:
        try:
            setattr(sketch, READ_ONLY_PROPERTY_NAME, 2)
        except Exception as exc:
            read_only_write_rejected = True
            read_only_error_type = type(exc).__name__
        else:
            read_only_write_rejected = False

    marker_in_list = [item.Name for item in marker.InList]
    marker_out_list = [item.Name for item in marker.OutList]
    marker_name = marker.Name
    marker_type_id = marker.TypeId
    marker_shape = _shape_inventory(marker.Shape)

    payload: dict[str, object] = {
        "documentName": document.Name,
        "documentLabel": document.Label,
        "bodyTip": _linked_object_name(body.Tip),
        "bodyShape": _shape_inventory(body.Shape),
        "padProfile": _linked_object_name(pad.Profile),
        "metadataProperties": _metadata_properties(body),
        "metadataGroupProperties": _metadata_group_properties(body),
        "missingProperty": MISSING_PROPERTY_NAME,
        "missingPropertyPresent": MISSING_PROPERTY_NAME in body.PropertiesList,
        "readOnlyProperty": {
            "name": READ_ONLY_PROPERTY_NAME,
            "present": read_only_present,
            "typeId": (
                sketch.getTypeIdOfProperty(READ_ONLY_PROPERTY_NAME)
                if read_only_present
                else None
            ),
            "writeRejected": read_only_write_rejected,
            "errorType": read_only_error_type,
        },
        "deletionMarker": {
            "name": marker_name,
            "typeId": marker_type_id,
            "inList": marker_in_list,
            "outList": marker_out_list,
            "shape": marker_shape,
        },
        "parameterGroup": {
            "name": var_set.Name,
            "typeId": var_set.TypeId,
            "property": PARAMETER_NAME,
            "propertyTypeId": var_set.getTypeIdOfProperty(PARAMETER_NAME),
            "value": _property_value(var_set, PARAMETER_NAME),
            "inList": [item.Name for item in var_set.InList],
            "outList": [item.Name for item in var_set.OutList],
        },
        "objects": [
            {"name": body.Name, "typeId": body.TypeId},
            {"name": sketch.Name, "typeId": sketch.TypeId},
            {"name": pad.Name, "typeId": pad.TypeId},
            {"name": marker_name, "typeId": marker_type_id},
            {"name": var_set.Name, "typeId": var_set.TypeId},
        ],
    }

    deletion_consumer: dict[str, object] = {}
    try:
        apply_deletion_mutations(document, [{"object": marker_name}])
    except DeletionMutationError as exc:
        deletion_consumer = {
            "ok": False,
            "errorType": type(exc).__name__,
            "message": str(exc),
        }
    else:
        deletion_consumer = {
            "ok": True,
            "markerPresentAfter": document.getObject(marker_name) is not None,
            "bodyShape": _shape_inventory(body.Shape),
        }
    payload["deletionConsumer"] = deletion_consumer
    return payload


def main() -> None:
    source_path, output_path = _arguments()
    _close_all_documents()
    document = App.openDocument(str(source_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to open metadata coexistence fixture")
    try:
        payload = _inspect(document)
    finally:
        _close_all_documents()
    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


main()
