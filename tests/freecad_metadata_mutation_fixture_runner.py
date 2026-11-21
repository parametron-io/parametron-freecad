"""Test-only FreeCAD host for real metadata mutation fixture inspection.

Not production code. Opens an arbitrary ``.FCStd`` file with real FreeCAD and
emits a deterministic JSON semantic inventory used by permanent fixture tests.

    nix develop --command freecadcmd \
      tests/freecad_metadata_mutation_fixture_runner.py \
      --pass=/absolute/path/to/document.FCStd \
      --pass=/absolute/path/to/output.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD as App

PASS_PREFIX = "--pass="

BODY_NAME = "MetadataBody"
SKETCH_NAME = "ProfileSketch"
PAD_NAME = "Pad"

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


def _inspect(document) -> dict[str, object]:
    body = document.getObject(BODY_NAME)
    sketch = document.getObject(SKETCH_NAME)
    pad = document.getObject(PAD_NAME)
    missing = [
        name
        for name, value in (
            (BODY_NAME, body),
            (SKETCH_NAME, sketch),
            (PAD_NAME, pad),
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

    return {
        "documentName": document.Name,
        "documentLabel": document.Label,
        "bodyTip": _linked_object_name(body.Tip),
        "bodyShape": {
            "isNull": body.Shape.isNull(),
            "isValid": body.Shape.isValid(),
            "solidCount": len(body.Shape.Solids),
        },
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
        "objects": [
            {"name": body.Name, "typeId": body.TypeId},
            {"name": sketch.Name, "typeId": sketch.TypeId},
            {"name": pad.Name, "typeId": pad.TypeId},
        ],
    }


def main() -> None:
    source_path, output_path = _arguments()
    _close_all_documents()
    document = App.openDocument(str(source_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to open metadata mutation fixture")
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
