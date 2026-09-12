"""Generate the committed real-FreeCAD PartDesign mutation fixture bundle.

Run only through the repository Nix shell and FreeCAD host:

    nix develop --command freecadcmd \
      scripts/generate_partdesign_mutation_fixtures.py \
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
import Part
import Sketcher  # noqa: F401 - registers Sketcher::SketchObject with FreeCAD


EXPECTED_FREECAD_VERSION = ("1", "1", "1")
PASS_PREFIX = "--pass="
DOCUMENT_NAME = "PartDesignMutations"
DOCUMENT_LABEL = "partdesign-mutations"
DOCUMENT_FILENAME = "partdesign-mutations.FCStd"
PERSISTED_DOCUMENT_NAME = "partdesign_mutations"
BODY_NAME = "MutationBody"
BASE_SKETCH_NAME = "BaseSketch"
INTERMEDIATE_PAD_NAME = "IntermediatePad"
POCKET_SKETCH_NAME = "PocketSketch"
INTERMEDIATE_POCKET_NAME = "IntermediatePocket"
TERMINAL_CHAMFER_NAME = "TerminalChamfer"
SAFE_DELETE_NAME = "SafeDeleteMarker"


def _output_directory() -> Path:
    values = [
        argument[len(PASS_PREFIX):]
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
            "fixture generation requires FreeCAD 1.1.1; observed "
            + ".".join(App.Version()[:3])
        )


def _close_all_documents() -> None:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)


def _require_created(value, name: str):
    if value is None:
        raise RuntimeError(f"FreeCAD did not create object {name!r}")
    value.Label = name
    return value


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


def _save(document, path: Path) -> None:
    document.recompute()
    document.save()
    if not path.is_file():
        raise RuntimeError(f"FreeCAD save produced no file for {document.Name!r}")


def _generate(staging: Path) -> None:
    document = App.newDocument(DOCUMENT_NAME)
    if document is None:
        raise RuntimeError("FreeCAD failed to create the mutation fixture document")
    document.saveAs(str(staging / DOCUMENT_FILENAME))
    document.Label = DOCUMENT_LABEL

    body = _require_created(
        document.addObject("PartDesign::Body", BODY_NAME), BODY_NAME
    )
    base_sketch = _require_created(
        document.addObject("Sketcher::SketchObject", BASE_SKETCH_NAME),
        BASE_SKETCH_NAME,
    )
    body.addObject(base_sketch)
    _add_rectangle(base_sketch)

    pad = _require_created(
        body.newObject("PartDesign::Pad", INTERMEDIATE_PAD_NAME),
        INTERMEDIATE_PAD_NAME,
    )
    pad.Profile = base_sketch
    pad.Length = 10.0
    document.recompute()
    if pad.Shape.isNull() or not pad.Shape.isValid():
        raise RuntimeError("intermediate pad did not produce a valid shape")

    pocket_sketch = _require_created(
        document.addObject("Sketcher::SketchObject", POCKET_SKETCH_NAME),
        POCKET_SKETCH_NAME,
    )
    body.addObject(pocket_sketch)
    pocket_sketch.Placement.Base.z = 10.0
    pocket_sketch.addGeometry(
        Part.Circle(App.Vector(0.0, 0.0, 0.0), App.Vector(0.0, 0.0, 1.0), 3.0),
        False,
    )

    pocket = _require_created(
        body.newObject("PartDesign::Pocket", INTERMEDIATE_POCKET_NAME),
        INTERMEDIATE_POCKET_NAME,
    )
    pocket.Profile = pocket_sketch
    pocket.Length = 5.0
    document.recompute()
    if pocket.Shape.isNull() or not pocket.Shape.isValid():
        raise RuntimeError("intermediate pocket did not produce a valid shape")

    chamfer = _require_created(
        body.newObject("PartDesign::Chamfer", TERMINAL_CHAMFER_NAME),
        TERMINAL_CHAMFER_NAME,
    )
    chamfer.Base = (pocket, ["Edge1"])
    chamfer.Size = 1.0
    document.recompute()
    if chamfer.Shape.isNull() or not chamfer.Shape.isValid():
        raise RuntimeError("terminal chamfer did not produce a valid unsuppressed shape")
    chamfer.Suppressed = True

    safe_delete = _require_created(
        document.addObject("PartDesign::Feature", SAFE_DELETE_NAME), SAFE_DELETE_NAME
    )

    body.Visibility = True
    base_sketch.Visibility = False
    pad.Visibility = False
    pocket_sketch.Visibility = False
    pocket.Visibility = False
    chamfer.Visibility = False
    safe_delete.Visibility = False

    _save(document, staging / DOCUMENT_FILENAME)


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


def _names(values) -> list[str]:
    return sorted(value.Name for value in values)


def _linked_object_name(value) -> str:
    linked = value[0] if isinstance(value, tuple) else value
    return linked.Name


def _validate(staging: Path) -> dict[str, object]:
    _close_all_documents()
    fixture_path = staging / DOCUMENT_FILENAME
    document = App.openDocument(str(fixture_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to reopen generated mutation fixture")
    if (
        document.Name != PERSISTED_DOCUMENT_NAME
        or document.Label != DOCUMENT_LABEL
    ):
        raise RuntimeError(
            "generated fixture document identity changed after reopen: "
            f"name={document.Name!r}, label={document.Label!r}"
        )

    body = _object(document, BODY_NAME, "PartDesign::Body")
    base_sketch = _object(document, BASE_SKETCH_NAME, "Sketcher::SketchObject")
    pad = _object(document, INTERMEDIATE_PAD_NAME, "PartDesign::Pad")
    pocket_sketch = _object(
        document, POCKET_SKETCH_NAME, "Sketcher::SketchObject"
    )
    pocket = _object(document, INTERMEDIATE_POCKET_NAME, "PartDesign::Pocket")
    chamfer = _object(document, TERMINAL_CHAMFER_NAME, "PartDesign::Chamfer")
    safe_delete = _object(document, SAFE_DELETE_NAME, "PartDesign::Feature")

    document.recompute()
    if _linked_object_name(body.Tip) != chamfer.Name:
        raise RuntimeError("terminal chamfer is not the persisted Body Tip")
    if pad.Name == chamfer.Name or pad.Name == _linked_object_name(body.Tip):
        raise RuntimeError("intermediate pad is not distinct from the terminal feature")
    if _linked_object_name(chamfer.Base) != pocket.Name:
        raise RuntimeError("terminal chamfer does not retain its pocket base")
    if pad.BaseFeature is not None:
        raise RuntimeError("intermediate pad unexpectedly gained a base feature")
    if _linked_object_name(pocket.BaseFeature) != pad.Name:
        raise RuntimeError("intermediate pocket does not depend on the pad")
    if _linked_object_name(pocket.Profile) != pocket_sketch.Name:
        raise RuntimeError("intermediate pocket does not retain its sketch profile")
    if _linked_object_name(pad.Profile) != base_sketch.Name:
        raise RuntimeError("intermediate pad does not retain its sketch profile")
    if INTERMEDIATE_PAD_NAME not in _names(base_sketch.InList):
        raise RuntimeError("unsafe-delete sketch lacks its surviving pad dependent")
    if INTERMEDIATE_POCKET_NAME not in _names(pad.InList):
        raise RuntimeError("intermediate pad lacks its later pocket dependent")

    for feature in (pad, pocket, chamfer):
        if "Suppressed" not in feature.PropertiesList:
            raise RuntimeError(f"{feature.Name!r} lacks native Suppressed")
        if feature.getTypeIdOfProperty("Suppressed") != "App::PropertyBool":
            raise RuntimeError(f"{feature.Name!r} Suppressed is not a native bool")
    if chamfer.Suppressed is not True:
        raise RuntimeError("terminal chamfer is not persisted initially suppressed")

    for target in (body, pad, pocket, chamfer, safe_delete):
        if "Visibility" not in target.PropertiesList:
            raise RuntimeError(f"{target.Name!r} lacks App-level Visibility")
    if body.Visibility is not True:
        raise RuntimeError("Body is not persisted initially visible")

    if safe_delete.InList or safe_delete.OutList:
        raise RuntimeError("safe-delete target is referenced by the fixture")
    if body.Shape.isNull() or not body.Shape.isValid() or len(body.Shape.Solids) != 1:
        raise RuntimeError("Body does not expose one accessible valid solid after reopen")

    inventory = []
    for value in (body, base_sketch, pad, pocket_sketch, pocket, chamfer, safe_delete):
        inventory.append({
            "name": value.Name,
            "typeId": value.TypeId,
            "inList": _names(value.InList),
            "outList": _names(value.OutList),
            "suppressed": (
                bool(value.Suppressed)
                if "Suppressed" in value.PropertiesList
                else None
            ),
            "visibility": (
                bool(value.Visibility)
                if "Visibility" in value.PropertiesList
                else None
            ),
        })
    return {
        "bodyTip": _linked_object_name(body.Tip),
        "bodyShape": {"isNull": body.Shape.isNull(), "isValid": body.Shape.isValid(), "solidCount": len(body.Shape.Solids)},
        "objects": inventory,
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
    print(json.dumps({
        "documents": [DOCUMENT_FILENAME],
        "freecadVersion": App.Version()[:3],
        "output": str(output),
        "reproducibility": "semantic",
        "semanticInventory": semantic_inventory,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


main()
