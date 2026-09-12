"""Generate the committed real-FreeCAD reference traversal fixture bundle.

Run only through the repository Nix shell and FreeCAD host:

    nix develop --command freecadcmd \
      scripts/generate_reference_traversal_fixtures.py \
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


EXPECTED_FREECAD_VERSION = ("1", "1", "1")
PASS_PREFIX = "--pass="


def _output_directory() -> Path:
    values = [argument[len(PASS_PREFIX):] for argument in sys.argv if argument.startswith(PASS_PREFIX)]
    if len(values) != 1 or not values[0]:
        raise RuntimeError("generator requires exactly one --pass=/absolute/output/directory")
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


def _feature(document, name: str):
    value = document.addObject("App::FeaturePython", name)
    if value is None:
        raise RuntimeError(f"FreeCAD did not create object {name!r}")
    value.Label = name
    return value


def _save(document) -> None:
    document.recompute()
    document.save()
    if not Path(document.FileName).is_file():
        raise RuntimeError(f"FreeCAD save produced no file for {document.Name!r}")


def _generate(staging: Path) -> None:
    references = staging / "references"
    references.mkdir(parents=True)

    reference_a = App.newDocument("ReferenceA")
    reference_a.Label = "Reference A"
    shared_target = _feature(reference_a, "SharedTarget")
    reference_a.saveAs(str(references / "reference-a.FCStd"))
    if not (references / "reference-a.FCStd").is_file():
        raise RuntimeError("FreeCAD produced no reference-a.FCStd")

    reference_b = App.newDocument("ReferenceB")
    reference_b.Label = "Reference B"
    second_target = _feature(reference_b, "SecondTarget")
    reference_b.saveAs(str(references / "reference-b.FCStd"))
    if not (references / "reference-b.FCStd").is_file():
        raise RuntimeError("FreeCAD produced no reference-b.FCStd")

    root = App.newDocument("ReferenceRoot")
    root.saveAs(str(staging / "reference-root.FCStd"))
    # FreeCAD derives the persisted document label from this stable filename.
    root.Label = "reference-root"

    internal_target = _feature(root, "InternalTarget")
    internal_source = _feature(root, "InternalSource")
    internal_source.addProperty("App::PropertyLink", "InternalLink")
    internal_source.InternalLink = internal_target

    external_source_one = _feature(root, "ExternalSourceOne")
    external_source_one.addProperty("App::PropertyXLink", "ExternalLink")
    external_source_one.ExternalLink = shared_target

    external_source_two = _feature(root, "ExternalSourceTwo")
    external_source_two.addProperty("App::PropertyXLink", "ExternalLink")
    external_source_two.ExternalLink = shared_target

    second_external_source = _feature(root, "SecondExternalSource")
    second_external_source.addProperty("App::PropertyXLink", "ExternalLink")
    second_external_source.ExternalLink = second_target

    missing_source = _feature(root, "MissingSource")
    missing_source.addProperty("App::PropertyXLink", "MissingLink")
    missing_source.MissingLink = None

    _save(root)
    for backup in staging.rglob("*.FCBak"):
        backup.unlink()


def _validate(staging: Path) -> None:
    _close_all_documents()
    root = App.openDocument(str(staging / "reference-root.FCStd"))
    if root is None:
        raise RuntimeError("FreeCAD failed to reopen generated root fixture")
    expected = {
        ("InternalSource", "InternalLink"): ("App::PropertyLink", "InternalTarget"),
        ("ExternalSourceOne", "ExternalLink"): ("App::PropertyXLink", "SharedTarget"),
        ("ExternalSourceTwo", "ExternalLink"): ("App::PropertyXLink", "SharedTarget"),
        ("SecondExternalSource", "ExternalLink"): ("App::PropertyXLink", "SecondTarget"),
        ("MissingSource", "MissingLink"): ("App::PropertyXLink", None),
    }
    for (object_name, property_name), (mechanism, target_name) in expected.items():
        source = root.getObject(object_name)
        if source is None:
            raise RuntimeError(f"generated fixture lacks object {object_name!r}")
        if source.getTypeIdOfProperty(property_name) != mechanism:
            raise RuntimeError(f"generated fixture mechanism mismatch at {object_name}.{property_name}")
        target = source.getPropertyByName(property_name)
        observed_name = None if target is None else target.Name
        if observed_name != target_name:
            raise RuntimeError(f"generated fixture target mismatch at {object_name}.{property_name}")
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
    print(json.dumps({
        "freecadVersion": App.Version()[:3],
        "output": str(output),
        "documents": [
            "reference-root.FCStd",
            "references/reference-a.FCStd",
            "references/reference-b.FCStd",
        ],
        "reproducibility": "semantic",
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


main()
