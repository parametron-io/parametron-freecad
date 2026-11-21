"""Generate the derived metadata mutation coexistence fixture.

Run only through the repository Nix shell and FreeCAD host:

    nix develop --command freecadcmd \
      scripts/generate_metadata_coexistence_fixture.py \
      --pass=/absolute/output/directory

The committed ``metadata-source.FCStd`` fixture from the metadata mutation
fixture bundle is opened read-only and never saved in place. The derived
document adds one standalone ``Part::Feature`` deletion marker that has no
native dependents and does not participate in the PartDesign Body shape.

The derived document is semantically reproducible. FreeCAD's ``.FCStd`` archive
bytes are not expected to be identical across regeneration runs.
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

EXPECTED_FREECAD_VERSION = ("1", "1", "4")
PASS_PREFIX = "--pass="

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FIXTURE = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "metadata_mutation"
    / "input"
    / "metadata-source.FCStd"
)

OUTPUT_FILENAME = "metadata-coexistence.FCStd"
DOCUMENT_LABEL = "metadata-coexistence"
PERSISTED_DOCUMENT_NAME = "metadata_coexistence"

BODY_NAME = "MetadataBody"
SKETCH_NAME = "ProfileSketch"
PAD_NAME = "Pad"
MARKER_NAME = "DeletionMarker"
VARSET_NAME = "Parameters"
PARAMETER_NAME = "pilotValue"
PARAMETER_INITIAL = 10.0

METADATA_PROPERTIES = (
    ("App::PropertyString", "material", "PLA"),
    ("App::PropertyBool", "tagged", False),
    ("App::PropertyFloat", "mass", 1.5),
    ("App::PropertyInteger", "revision", 1),
    ("App::PropertyFloatConstraint", "tolerance", 0.5),
    ("App::PropertyIntegerConstraint", "sequence", 10),
    ("App::PropertyLength", "measured_length", 12.5),
)

READ_ONLY_PROPERTY_NAME = "_ExternalGeoVersion"


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
    if not SOURCE_FIXTURE.is_file():
        raise RuntimeError(f"source metadata fixture is unavailable: {SOURCE_FIXTURE}")


def _close_all_documents() -> None:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)


def _object(document, name: str, expected_type: str):
    value = document.getObject(name)
    if value is None:
        raise RuntimeError(f"coexistence fixture lacks object {name!r}")
    if value.TypeId != expected_type:
        raise RuntimeError(
            f"coexistence fixture type mismatch for {name!r}: "
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
            if native_object.getGroupOfProperty(name) == "Metadata":
                names.append(name)
        except Exception:
            continue
    return sorted(names)


def _metadata_inventory(native_object) -> dict[str, dict[str, object]]:
    inventory: dict[str, dict[str, object]] = {}
    for type_id, name, expected_value in METADATA_PROPERTIES:
        if name not in native_object.PropertiesList:
            raise RuntimeError(f"coexistence fixture lost metadata {name!r}")
        observed_type = native_object.getTypeIdOfProperty(name)
        if observed_type != type_id:
            raise RuntimeError(
                f"coexistence metadata {name!r} type mismatch: "
                f"expected {type_id!r}, observed {observed_type!r}"
            )
        observed_value = _property_value(native_object, name)
        if observed_value != expected_value:
            raise RuntimeError(
                f"coexistence metadata {name!r} value mismatch: "
                f"expected {expected_value!r}, observed {observed_value!r}"
            )
        inventory[name] = {
            "typeId": observed_type,
            "value": observed_value,
        }
    return inventory


def _add_deletion_marker(document):
    marker = document.addObject("Part::Box", MARKER_NAME)
    if marker is None:
        raise RuntimeError(f"FreeCAD did not create object {MARKER_NAME!r}")
    marker.Label = MARKER_NAME
    marker.Length = 5.0
    marker.Width = 5.0
    marker.Height = 5.0
    marker.Placement.Base = App.Vector(100.0, 0.0, 0.0)
    marker.Visibility = True
    if marker.Shape.isNull() or not marker.Shape.isValid():
        raise RuntimeError("deletion marker did not produce a valid shape")
    return marker


def _add_varset(document):
    var_set = document.addObject("App::VarSet", VARSET_NAME)
    if var_set is None:
        raise RuntimeError(f"FreeCAD did not create object {VARSET_NAME!r}")
    var_set.Label = VARSET_NAME
    var_set.addProperty(
        "App::PropertyFloat",
        PARAMETER_NAME,
        "Parameters",
        "Parametron metadata coexistence parameter",
    )
    if PARAMETER_NAME not in var_set.PropertiesList:
        raise RuntimeError(f"FreeCAD did not create VarSet property {PARAMETER_NAME!r}")
    setattr(var_set, PARAMETER_NAME, PARAMETER_INITIAL)
    return var_set


def _save_as(document, path: Path) -> None:
    document.recompute()
    document.saveAs(str(path))
    if not path.is_file():
        raise RuntimeError(f"FreeCAD produced no file for {document.Name!r}")


def _generate(staging: Path) -> None:
    document = App.openDocument(str(SOURCE_FIXTURE))
    if document is None:
        raise RuntimeError("FreeCAD failed to open the source metadata fixture")
    document.Label = DOCUMENT_LABEL
    _add_varset(document)
    _add_deletion_marker(document)
    _save_as(document, staging / OUTPUT_FILENAME)


def _validate(staging: Path) -> dict[str, object]:
    _close_all_documents()
    fixture_path = staging / OUTPUT_FILENAME
    document = App.openDocument(str(fixture_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to reopen generated coexistence fixture")
    if document.Name != PERSISTED_DOCUMENT_NAME or document.Label != DOCUMENT_LABEL:
        raise RuntimeError(
            "generated coexistence fixture identity changed after reopen: "
            f"name={document.Name!r}, label={document.Label!r}"
        )

    body = _object(document, BODY_NAME, "PartDesign::Body")
    sketch = _object(document, SKETCH_NAME, "Sketcher::SketchObject")
    pad = _object(document, PAD_NAME, "PartDesign::Pad")
    marker = _object(document, MARKER_NAME, "Part::Box")
    var_set = _object(document, VARSET_NAME, "App::VarSet")

    document.recompute()
    if _linked_object_name(body.Tip) != pad.Name:
        raise RuntimeError("coexistence body Tip is not the generated pad")
    if _linked_object_name(pad.Profile) != sketch.Name:
        raise RuntimeError("coexistence pad does not retain its profile sketch")
    if body.Shape.isNull() or not body.Shape.isValid() or len(body.Shape.Solids) != 1:
        raise RuntimeError("coexistence body does not expose one valid solid")

    marker_in_list = [item.Name for item in marker.InList]
    if marker_in_list:
        raise RuntimeError(
            f"deletion marker has surviving native dependents: {marker_in_list!r}"
        )
    if MARKER_NAME in [item.Name for item in body.OutList]:
        raise RuntimeError("deletion marker must not be linked to the body")

    if PARAMETER_NAME not in var_set.PropertiesList:
        raise RuntimeError(f"coexistence VarSet lacks {PARAMETER_NAME!r}")
    if var_set.getTypeIdOfProperty(PARAMETER_NAME) != "App::PropertyFloat":
        raise RuntimeError(
            f"coexistence VarSet {PARAMETER_NAME!r} is not App::PropertyFloat"
        )
    if _property_value(var_set, PARAMETER_NAME) != PARAMETER_INITIAL:
        raise RuntimeError(f"coexistence VarSet {PARAMETER_NAME!r} value mismatch")
    if [item.Name for item in var_set.InList]:
        raise RuntimeError("coexistence VarSet must not have native dependents")
    if VARSET_NAME in [item.Name for item in body.OutList]:
        raise RuntimeError("coexistence VarSet must not be linked to the body")

    metadata_properties = _metadata_inventory(body)
    metadata_group_properties = _metadata_group_properties(body)
    expected_group_properties = sorted(name for _, name, _ in METADATA_PROPERTIES)
    if metadata_group_properties != expected_group_properties:
        raise RuntimeError(
            "coexistence metadata group properties mismatch: "
            f"expected {expected_group_properties!r}, "
            f"observed {metadata_group_properties!r}"
        )

    if READ_ONLY_PROPERTY_NAME not in sketch.PropertiesList:
        raise RuntimeError(
            f"coexistence profile sketch lacks {READ_ONLY_PROPERTY_NAME!r}"
        )

    result = {
        "documentName": document.Name,
        "documentLabel": document.Label,
        "bodyTip": _linked_object_name(body.Tip),
        "padProfile": _linked_object_name(pad.Profile),
        "bodyShape": {
            "isNull": body.Shape.isNull(),
            "isValid": body.Shape.isValid(),
            "solidCount": len(body.Shape.Solids),
        },
        "metadataProperties": metadata_properties,
        "metadataGroupProperties": metadata_group_properties,
        "readOnlyProperty": {
            "name": READ_ONLY_PROPERTY_NAME,
            "present": True,
            "typeId": sketch.getTypeIdOfProperty(READ_ONLY_PROPERTY_NAME),
        },
        "deletionMarker": {
            "name": marker.Name,
            "typeId": marker.TypeId,
            "inList": marker_in_list,
            "outList": [item.Name for item in marker.OutList],
            "shape": {
                "isNull": marker.Shape.isNull(),
                "isValid": marker.Shape.isValid(),
                "solidCount": len(marker.Shape.Solids),
            },
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
            {"name": marker.Name, "typeId": marker.TypeId},
            {"name": var_set.Name, "typeId": var_set.TypeId},
        ],
    }
    result["deletionTrial"] = _validate_deletion_trial(fixture_path)
    return result


def _validate_deletion_trial(fixture_path: Path) -> dict[str, object]:
    _close_all_documents()
    trial_directory = Path(
        tempfile.mkdtemp(
            prefix=".metadata-coexistence-delete.", dir=fixture_path.parent
        )
    )
    trial_path = trial_directory / OUTPUT_FILENAME
    shutil.copyfile(fixture_path, trial_path)
    try:
        document = App.openDocument(str(trial_path))
        if document is None:
            raise RuntimeError("FreeCAD failed to open deletion trial copy")
        body = document.getObject(BODY_NAME)
        marker = document.getObject(MARKER_NAME)
        if body is None or marker is None:
            raise RuntimeError("deletion trial copy lost expected objects")
        document.removeObject(MARKER_NAME)
        document.recompute()
        if document.getObject(MARKER_NAME) is not None:
            raise RuntimeError("deletion trial did not remove the marker")
        if body.Shape.isNull() or not body.Shape.isValid():
            raise RuntimeError(
                "deletion marker removal invalidated the coexistence body"
            )
        return {
            "markerRemoved": True,
            "bodyShape": {
                "isNull": body.Shape.isNull(),
                "isValid": body.Shape.isValid(),
                "solidCount": len(body.Shape.Solids),
            },
        }
    finally:
        _close_all_documents()
        shutil.rmtree(trial_directory, ignore_errors=True)


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
                "documents": [OUTPUT_FILENAME],
                "freecadVersion": App.Version()[:3],
                "output": str(output),
                "reproducibility": "semantic",
                "semanticInventory": semantic_inventory,
                "sourceFixture": str(SOURCE_FIXTURE.relative_to(REPOSITORY_ROOT)),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


main()
