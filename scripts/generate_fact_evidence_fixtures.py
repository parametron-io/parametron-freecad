"""Generate the committed real-FreeCAD bounded fact fixture bundle.

Run only through the repository Nix shell and FreeCAD host:

    nix develop --command freecadcmd \
      scripts/generate_fact_evidence_fixtures.py \
      --pass=/absolute/output/directory

The generated documents are semantically reproducible. FreeCAD's ``.FCStd``
archive bytes are not expected to be identical across regeneration runs.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

import FreeCAD as App
import Part  # noqa: F401 - registers Part::Box in the FreeCAD object registry

EXPECTED_FREECAD_VERSION = ("1", "1", "4")
PASS_PREFIX = "--pass="

SOURCE_DOCUMENT = "fact-source.FCStd"
SECONDARY_DOCUMENT = "resources/secondary.FCStd"


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
    return document


def _add(document, type_id: str, name: str):
    native_object = document.addObject(type_id, name)
    if native_object is None:
        raise RuntimeError(f"FreeCAD did not create object {name!r}")
    native_object.Label = name
    return native_object


def _add_property(native_object, type_id: str, name: str) -> None:
    native_object.addProperty(type_id, name)
    if name not in native_object.PropertiesList:
        raise RuntimeError(f"FreeCAD did not create property {name!r}")


def _save_as(document, path: Path) -> None:
    document.recompute()
    document.saveAs(str(path))
    if not path.is_file():
        raise RuntimeError(f"FreeCAD produced no file for {document.Name!r}")


def _generate(staging: Path) -> None:
    resources = staging / "resources"
    resources.mkdir(parents=True)

    source = _new_document("FactsSource")
    box = _add(source, "Part::Box", "Box")
    box.Length = 25.5

    props = _add(source, "App::FeaturePython", "Props")
    _add_property(props, "App::PropertyLength", "MeasuredLength")
    _add_property(props, "App::PropertyFloat", "Ratio")
    _add_property(props, "App::PropertyInteger", "Count")
    _add_property(props, "App::PropertyBool", "Enabled")
    _add_property(props, "App::PropertyString", "PlainText")
    _add_property(props, "App::PropertyString", "SpecialText")
    _add_property(props, "App::PropertyFloat", "NonFinite")
    props.MeasuredLength = 12.5
    props.Ratio = 3.25
    props.Count = 42
    props.Enabled = True
    props.PlainText = "bounded fact string"
    props.SpecialText = "a<&>\u2028b"
    props.NonFinite = float("inf")

    _save_as(source, staging / SOURCE_DOCUMENT)

    secondary = _new_document("FactsSecondary")
    secondary_props = _add(secondary, "App::FeaturePython", "SecondaryProps")
    _add_property(secondary_props, "App::PropertyLength", "SecondaryLength")
    secondary_props.SecondaryLength = 20.0
    _save_as(secondary, staging / SECONDARY_DOCUMENT)

    _close_all_documents()
    for backup in staging.rglob("*.FCBak"):
        backup.unlink()


def _validate(staging: Path) -> None:
    _close_all_documents()
    source = App.openDocument(str(staging / SOURCE_DOCUMENT))
    if source is None:
        raise RuntimeError("FreeCAD failed to reopen the generated fact fixture")
    secondary = App.openDocument(str(staging / SECONDARY_DOCUMENT))
    if secondary is None:
        raise RuntimeError("FreeCAD failed to reopen the generated secondary fixture")
    try:
        box = source.getObject("Box")
        if box is None or box.TypeId != "Part::Box":
            raise RuntimeError("generated fixture lacks the Part::Box subject")
        if abs(box.Length.Value - 25.5) > 1e-9:
            raise RuntimeError("generated Box.Length was not preserved")

        props = source.getObject("Props")
        if props is None:
            raise RuntimeError("generated fixture lacks the property subject")
        if abs(props.MeasuredLength.Value - 12.5) > 1e-9:
            raise RuntimeError("generated MeasuredLength was not preserved")
        if abs(props.Ratio - 3.25) > 1e-9:
            raise RuntimeError("generated Ratio was not preserved")
        if props.Count != 42:
            raise RuntimeError("generated Count was not preserved")
        if props.Enabled is not True:
            raise RuntimeError("generated Enabled was not preserved")
        if props.PlainText != "bounded fact string":
            raise RuntimeError("generated PlainText was not preserved")
        if "<" not in props.SpecialText:
            raise RuntimeError("generated SpecialText was not preserved")
        if not math.isinf(props.NonFinite):
            raise RuntimeError("generated NonFinite was not preserved")

        secondary_props = secondary.getObject("SecondaryProps")
        if secondary_props is None:
            raise RuntimeError("generated fixture lacks the secondary subject")
        if abs(secondary_props.SecondaryLength.Value - 20.0) > 1e-9:
            raise RuntimeError("generated SecondaryLength was not preserved")
    finally:
        _close_all_documents()


def main() -> None:
    _require_environment()
    output = _output_directory()
    if output.exists():
        raise RuntimeError(f"fixture output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        _generate(staging)
        _validate(staging)
        staging.replace(output)
    except Exception:
        _close_all_documents()
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(
        json.dumps(
            {
                "freecadVersion": list(App.Version()[:3]),
                "output": str(output),
                "documents": [SOURCE_DOCUMENT, SECONDARY_DOCUMENT],
                "reproducibility": "semantic",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


main()
