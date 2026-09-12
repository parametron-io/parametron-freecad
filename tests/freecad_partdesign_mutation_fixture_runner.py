"""Test-only FreeCAD-host helper for real PartDesign mutation fixture tests.

Not production code. Opens an arbitrary ``.FCStd`` file with real FreeCAD and
emits a deterministic JSON semantic inventory used by permanent Task 1 tests
to inspect the committed fixture and freshly generated fixtures through a
single shared inspection path.

    nix develop --command freecadcmd \
      tests/freecad_partdesign_mutation_fixture_runner.py \
      --pass=/absolute/path/to/document.FCStd \
      --pass=/absolute/path/to/output.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD as App


PASS_PREFIX = "--pass="

BODY_NAME = "MutationBody"
BASE_SKETCH_NAME = "BaseSketch"
INTERMEDIATE_PAD_NAME = "IntermediatePad"
POCKET_SKETCH_NAME = "PocketSketch"
INTERMEDIATE_POCKET_NAME = "IntermediatePocket"
TERMINAL_CHAMFER_NAME = "TerminalChamfer"
SAFE_DELETE_NAME = "SafeDeleteMarker"

FIXTURE_OBJECT_NAMES = (
    BODY_NAME,
    BASE_SKETCH_NAME,
    INTERMEDIATE_PAD_NAME,
    POCKET_SKETCH_NAME,
    INTERMEDIATE_POCKET_NAME,
    TERMINAL_CHAMFER_NAME,
    SAFE_DELETE_NAME,
)


def _arguments() -> tuple[Path, Path]:
    values = [
        argument[len(PASS_PREFIX):]
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 2:
        raise RuntimeError("runner requires source and output --pass arguments")
    return Path(values[0]), Path(values[1])


def _close_all_documents() -> None:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)


def _names(values) -> list[str]:
    return sorted(value.Name for value in values)


def _linked_object_name(value):
    if value is None:
        return None
    linked = value[0] if isinstance(value, tuple) else value
    return linked.Name


def _property_type(value, name: str):
    if name not in value.PropertiesList:
        return None
    return value.getTypeIdOfProperty(name)


def _inspect(document) -> dict[str, object]:
    objects = {name: document.getObject(name) for name in FIXTURE_OBJECT_NAMES}
    missing = sorted(name for name, value in objects.items() if value is None)
    if missing:
        raise RuntimeError(f"fixture missing expected objects: {missing!r}")

    body = objects[BODY_NAME]
    pad = objects[INTERMEDIATE_PAD_NAME]
    pocket = objects[INTERMEDIATE_POCKET_NAME]
    chamfer = objects[TERMINAL_CHAMFER_NAME]

    inventory = []
    for value in objects.values():
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
            "suppressedPropertyType": _property_type(value, "Suppressed"),
            "visibility": (
                bool(value.Visibility)
                if "Visibility" in value.PropertiesList
                else None
            ),
            "visibilityPropertyType": _property_type(value, "Visibility"),
        })

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
        "padBaseFeature": _linked_object_name(pad.BaseFeature),
        "pocketProfile": _linked_object_name(pocket.Profile),
        "pocketBaseFeature": _linked_object_name(pocket.BaseFeature),
        "chamferBase": _linked_object_name(chamfer.Base),
        "objects": sorted(inventory, key=lambda item: item["name"]),
    }


def main() -> None:
    source_path, output_path = _arguments()
    _close_all_documents()
    document = App.openDocument(str(source_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to open PartDesign mutation fixture")
    try:
        document.recompute()
        payload = _inspect(document)
    finally:
        _close_all_documents()
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


main()
