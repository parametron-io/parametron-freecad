"""Generate the committed real-FreeCAD capture drawing fixture bundle.

Run only through the repository Nix shell and FreeCAD host:

    nix develop --command freecadcmd \
      scripts/generate_capture_drawing_fixtures.py \
      --pass=/absolute/output/directory

The generated documents are semantically reproducible. FreeCAD's ``.FCStd``
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

EXPECTED_FREECAD_VERSION = ("1", "1", "4")
PASS_PREFIX = "--pass="

SINGLE_DOCUMENT = "single-page.FCStd"
MULTIPLE_DOCUMENT = "multiple-pages.FCStd"


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


def _new_document(name: str) -> App.Document:
    document = App.newDocument(name)
    if document is None:
        raise RuntimeError(f"FreeCAD did not create document {name!r}")
    return document


def _add(document: App.Document, type_id: str, name: str, *, label: str | None = None):
    native_object = document.addObject(type_id, name)
    if native_object is None:
        raise RuntimeError(f"FreeCAD did not create object {name!r}")
    native_object.Label = label if label is not None else name
    return native_object


def _add_body(document: App.Document, name: str):
    body = _add(document, "PartDesign::Body", name)
    feature = body.newObject("PartDesign::AdditiveBox", f"{name}Box")
    if feature is None:
        raise RuntimeError(f"FreeCAD did not create a feature for {name!r}")
    feature.Length = 10
    feature.Width = 15
    feature.Height = 20
    return body, feature


def _drawing_page(document: App.Document, name: str, label: str):
    page = _add(document, "TechDraw::DrawPage", name, label=label)
    if page.TypeId != "TechDraw::DrawPage":
        raise RuntimeError(f"unexpected page type for {name!r}")
    return page


def _drawing_view(
    document: App.Document,
    name: str,
    *,
    label: str,
    source: list[object],
):
    view = _add(document, "TechDraw::DrawViewPart", name, label=label)
    view.Source = source
    return view


def _save_as(document: App.Document, path: Path, label: str) -> None:
    document.recompute()
    document.saveAs(str(path))
    document.Label = label
    document.save()
    if not path.is_file():
        raise RuntimeError(f"FreeCAD produced no file for {document.Name!r}")


def _generate(staging: Path) -> None:
    single = _new_document("CaptureDrawingSingle")
    single_path = staging / SINGLE_DOCUMENT
    single_body, _ = _add_body(single, "Body")
    single_page = _drawing_page(single, "Page", "Assembly sheet")
    single_view = _drawing_view(
        single,
        "BodyView",
        label="Body view",
        source=[single_body],
    )
    single_page.Views = [single_view]
    _save_as(single, single_path, "single-page")
    _close_all_documents()

    multiple = _new_document("CaptureDrawingMultiple")
    multiple_path = staging / MULTIPLE_DOCUMENT
    body_one, feature_one = _add_body(multiple, "Body")
    body_two, _ = _add_body(multiple, "Body2")

    page_a = _drawing_page(multiple, "PageA", "Sheet A")
    body_view = _drawing_view(
        multiple,
        "BodyView",
        label="Body view",
        source=[body_one],
    )
    feature_view = _drawing_view(
        multiple,
        "FeatureView",
        label="Feature view",
        source=[feature_one],
    )
    page_a.Views = [body_view, feature_view]

    page_b = _drawing_page(multiple, "PageB", "Sheet B")
    second_body_view = _drawing_view(
        multiple,
        "SecondBodyView",
        label="Second body view",
        source=[body_two],
    )
    annotation = _add(multiple, "TechDraw::DrawViewAnnotation", "Note", label="Note")
    page_b.Views = [second_body_view, annotation]

    _add(multiple, "TechDraw::DrawViewSymbol", "OrphanSymbol", label="Orphan symbol")

    _save_as(multiple, multiple_path, "multiple-pages")
    _close_all_documents()

    for backup in staging.rglob("*.FCBak"):
        backup.unlink()


def _require_page(document: App.Document, name: str) -> None:
    page = document.getObject(name)
    if page is None or page.TypeId != "TechDraw::DrawPage":
        raise RuntimeError(f"generated fixture lacks drawing page {name!r}")


def _require_source(page_name: str, view, expected: list[str]) -> None:
    observed = [source.Name for source in view.Source]
    if observed != expected:
        raise RuntimeError(
            f"generated view {view.Name!r} on {page_name!r} has sources "
            f"{observed!r}, expected {expected!r}"
        )


def _validate(staging: Path) -> None:
    _close_all_documents()

    single = App.openDocument(str(staging / SINGLE_DOCUMENT))
    if single is None:
        raise RuntimeError("FreeCAD failed to reopen the single-page fixture")
    try:
        _require_page(single, "Page")
        page = single.getObject("Page")
        if [view.Name for view in page.Views] != ["BodyView"]:
            raise RuntimeError("single-page fixture has unexpected page Views")
        _require_source("Page", single.getObject("BodyView"), ["Body"])
    finally:
        _close_all_documents()

    multiple = App.openDocument(str(staging / MULTIPLE_DOCUMENT))
    if multiple is None:
        raise RuntimeError("FreeCAD failed to reopen the multiple-pages fixture")
    try:
        _require_page(multiple, "PageA")
        _require_page(multiple, "PageB")
        page_a = multiple.getObject("PageA")
        page_b = multiple.getObject("PageB")
        if [view.Name for view in page_a.Views] != ["BodyView", "FeatureView"]:
            raise RuntimeError("multiple-pages fixture has unexpected PageA Views")
        if [view.Name for view in page_b.Views] != ["SecondBodyView", "Note"]:
            raise RuntimeError("multiple-pages fixture has unexpected PageB Views")
        _require_source("PageA", multiple.getObject("BodyView"), ["Body"])
        _require_source("PageA", multiple.getObject("FeatureView"), ["BodyBox"])
        _require_source("PageB", multiple.getObject("SecondBodyView"), ["Body2"])
        orphan = multiple.getObject("OrphanSymbol")
        if orphan is None or orphan.InList:
            raise RuntimeError("generated orphan view is not orphaned")
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
                "documents": [SINGLE_DOCUMENT, MULTIPLE_DOCUMENT],
                "reproducibility": "semantic",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


main()
