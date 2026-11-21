"""Generate the committed real-FreeCAD metadata mutation fixture bundle.

Run only through the repository Nix shell and FreeCAD host:

    nix develop --command freecadcmd \
      scripts/generate_metadata_mutation_fixtures.py \
      --pass=/absolute/output/directory

The generated document is semantically reproducible. FreeCAD's ``.FCStd``
archive bytes are not expected to be identical across regeneration runs.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import FreeCAD as App
import Part  # noqa: F401 - registers Part geometry types with FreeCAD
import Sketcher  # noqa: F401 - registers Sketcher::SketchObject with FreeCAD

EXPECTED_FREECAD_VERSION = ("1", "1", "4")
PASS_PREFIX = "--pass="

DOCUMENT_NAME = "MetadataMutation"
DOCUMENT_LABEL = "metadata-source"
DOCUMENT_FILENAME = "metadata-source.FCStd"
PERSISTED_DOCUMENT_NAME = "metadata_source"

BODY_NAME = "MetadataBody"
SKETCH_NAME = "ProfileSketch"
PAD_NAME = "Pad"

METADATA_GROUP_NAME = "Metadata"

METADATA_PROPERTIES = (
    ("App::PropertyString", "material", "PLA"),
    ("App::PropertyBool", "tagged", False),
    ("App::PropertyFloat", "mass", 1.5),
    ("App::PropertyInteger", "revision", 1),
    ("App::PropertyFloatConstraint", "tolerance", 0.5),
    ("App::PropertyIntegerConstraint", "sequence", 10),
    ("App::PropertyLength", "measured_length", 12.5),
)

MISSING_PROPERTY_NAME = "supplier"
READ_ONLY_PROPERTY_NAME = "_ExternalGeoVersion"
READ_ONLY_PROPERTY_TYPE = "App::PropertyInteger"


def _output_directory() -> Path:
    values = [
        argument[len(PASS_PREFIX) :]
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 1 or not values[0]:
        raise RuntimeError(
            "generator requires exactly one --pass=/absolute/output/directory"
        )
    output = Path(values[0])
    if not output.is_absolute():
        raise RuntimeError("fixture output directory must be absolute")
    return output


def _require_environment() -> None:
    if not os.environ.get("IN_NIX_SHELL"):
        raise RuntimeError("fixture generation must run inside nix develop")
    if tuple(App.Version()[:3]) != EXPECTED_FREECAD_VERSION:
        raise RuntimeError(
            "fixture generation requires FreeCAD "
            + ".".join(EXPECTED_FREECAD_VERSION)
            + "; observed "
            + ".".join(App.Version()[:3])
        )


def _close_all_documents() -> None:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)


def _new_document(name: str):
    document = App.newDocument(name)
    if document is None:
        raise RuntimeError(f"FreeCAD did not create document {name!r}")
    document.Label = DOCUMENT_LABEL
    return document


def _add(document, type_id: str, name: str):
    native_object = document.addObject(type_id, name)
    if native_object is None:
        raise RuntimeError(f"FreeCAD did not create object {name!r}")
    native_object.Label = name
    return native_object


def _add_property(native_object, type_id: str, name: str) -> None:
    native_object.addProperty(
        type_id,
        name,
        METADATA_GROUP_NAME,
        "Parametron metadata fixture",
    )
    if name not in native_object.PropertiesList:
        raise RuntimeError(f"FreeCAD did not create property {name!r}")


def _add_rectangle(sketch) -> None:
    points = ((-10.0, -8.0), (10.0, -8.0), (10.0, 8.0), (-10.0, 8.0))
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        sketch.addGeometry(
            Part.LineSegment(
                App.Vector(start[0], start[1], 0.0),
                App.Vector(end[0], end[1], 0.0),
            ),
            False,
        )


def _save_as(document, path: Path) -> None:
    document.recompute()
    document.saveAs(str(path))
    if not path.is_file():
        raise RuntimeError(f"FreeCAD produced no file for {document.Name!r}")


def _generate(staging: Path) -> None:
    document = _new_document(DOCUMENT_NAME)

    body = _add(document, "PartDesign::Body", BODY_NAME)
    sketch = _add(document, "Sketcher::SketchObject", SKETCH_NAME)
    body.addObject(sketch)
    _add_rectangle(sketch)

    pad = body.newObject("PartDesign::Pad", PAD_NAME)
    if pad is None:
        raise RuntimeError(f"FreeCAD did not create object {PAD_NAME!r}")
    pad.Label = PAD_NAME
    pad.Profile = sketch
    pad.Length = 10.0
    document.recompute()
    if pad.Shape.isNull() or not pad.Shape.isValid():
        raise RuntimeError("metadata mutation pad did not produce a valid shape")

    for type_id, name, value in METADATA_PROPERTIES:
        _add_property(body, type_id, name)
        setattr(body, name, value)

    body.Visibility = True
    sketch.Visibility = False
    pad.Visibility = False

    _save_as(document, staging / DOCUMENT_FILENAME)


def _object(document, name: str, expected_type: str):
    value = document.getObject(name)
    if value is None:
        raise RuntimeError(f"generated fixture lacks object {name!r}")
    if value.TypeId != expected_type:
        raise RuntimeError(
            f"generated fixture type mismatch for {name!r}: "
            f"expected {expected_type!r}, observed {value.TypeId!r}"
        )
    return value


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
            if native_object.getGroupOfProperty(name) == METADATA_GROUP_NAME:
                names.append(name)
        except Exception:
            continue
    return sorted(names)


def _metadata_inventory(native_object) -> dict[str, dict[str, object]]:
    inventory: dict[str, dict[str, object]] = {}
    for _, name, _ in METADATA_PROPERTIES:
        inventory[name] = {
            "typeId": native_object.getTypeIdOfProperty(name),
            "value": _property_value(native_object, name),
        }
    return inventory


def _validate(staging: Path) -> dict[str, object]:
    _close_all_documents()
    fixture_path = staging / DOCUMENT_FILENAME
    document = App.openDocument(str(fixture_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to reopen generated metadata fixture")
    if document.Name != PERSISTED_DOCUMENT_NAME or document.Label != DOCUMENT_LABEL:
        raise RuntimeError(
            "generated fixture document identity changed after reopen: "
            f"name={document.Name!r}, label={document.Label!r}"
        )

    body = _object(document, BODY_NAME, "PartDesign::Body")
    sketch = _object(document, SKETCH_NAME, "Sketcher::SketchObject")
    pad = _object(document, PAD_NAME, "PartDesign::Pad")

    document.recompute()
    if _linked_object_name(body.Tip) != pad.Name:
        raise RuntimeError("metadata body Tip is not the generated pad")
    if _linked_object_name(pad.Profile) != sketch.Name:
        raise RuntimeError("generated pad does not retain its profile sketch")
    if body.Shape.isNull() or not body.Shape.isValid() or len(body.Shape.Solids) != 1:
        raise RuntimeError("metadata body does not expose one valid solid")

    for type_id, name, expected_value in METADATA_PROPERTIES:
        if name not in body.PropertiesList:
            raise RuntimeError(f"generated metadata property {name!r} is missing")
        observed_type = body.getTypeIdOfProperty(name)
        if observed_type != type_id:
            raise RuntimeError(
                f"metadata property {name!r} type mismatch: "
                f"expected {type_id!r}, observed {observed_type!r}"
            )
        observed_value = _property_value(body, name)
        if observed_value != expected_value:
            raise RuntimeError(
                f"metadata property {name!r} value mismatch: "
                f"expected {expected_value!r}, observed {observed_value!r}"
            )

    expected_group_properties = sorted(
        name for _, name, _ in METADATA_PROPERTIES
    )
    if _metadata_group_properties(body) != expected_group_properties:
        raise RuntimeError(
            "metadata group properties mismatch: "
            f"expected {expected_group_properties!r}, "
            f"observed {_metadata_group_properties(body)!r}"
        )

    if MISSING_PROPERTY_NAME in body.PropertiesList:
        raise RuntimeError(
            f"metadata fixture unexpectedly defines {MISSING_PROPERTY_NAME!r}"
        )
    if READ_ONLY_PROPERTY_NAME not in sketch.PropertiesList:
        raise RuntimeError(
            f"profile sketch lacks {READ_ONLY_PROPERTY_NAME!r} read-only property"
        )
    if sketch.getTypeIdOfProperty(READ_ONLY_PROPERTY_NAME) != READ_ONLY_PROPERTY_TYPE:
        raise RuntimeError(
            f"{READ_ONLY_PROPERTY_NAME!r} is not {READ_ONLY_PROPERTY_TYPE!r}"
        )

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
        "metadataProperties": _metadata_inventory(body),
        "metadataGroupProperties": _metadata_group_properties(body),
        "missingProperty": MISSING_PROPERTY_NAME,
        "missingPropertyPresent": MISSING_PROPERTY_NAME in body.PropertiesList,
        "readOnlyProperty": {
            "name": READ_ONLY_PROPERTY_NAME,
            "typeId": sketch.getTypeIdOfProperty(READ_ONLY_PROPERTY_NAME),
            "present": READ_ONLY_PROPERTY_NAME in sketch.PropertiesList,
        },
        "objects": [
            {"name": body.Name, "typeId": body.TypeId},
            {"name": sketch.Name, "typeId": sketch.TypeId},
            {"name": pad.Name, "typeId": pad.TypeId},
        ],
    }


def main() -> None:
    _require_environment()
    output = _output_directory()
    if output.exists():
        raise RuntimeError(f"fixture output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        _generate(staging)
        semantic_inventory = _validate(staging)
        _close_all_documents()
        for backup in staging.rglob("*.FCBak"):
            backup.unlink()
        staging.replace(output)
    except Exception:
        _close_all_documents()
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(
        json.dumps(
            {
                "documents": [DOCUMENT_FILENAME],
                "freecadVersion": App.Version()[:3],
                "output": str(output),
                "reproducibility": "semantic",
                "semanticInventory": semantic_inventory,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


main()
