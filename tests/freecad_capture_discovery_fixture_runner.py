"""Test-only real-FreeCAD host for capture discovery fixture tests.

Not production code. Opens an arbitrary ``.FCStd`` document with real FreeCAD,
runs the GUI-free capture discovery, and writes deterministic JSON evidence.

    nix develop --command freecadcmd \
      tests/freecad_capture_discovery_fixture_runner.py \
      --pass=/absolute/path/to/document.FCStd \
      --pass=/absolute/path/to/output.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import FreeCAD as App

from parametron_freecad.capture import discover_capture_candidates

PASS_PREFIX = "--pass="


def _arguments() -> tuple[Path, Path]:
    values = [
        argument[len(PASS_PREFIX) :]
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 2:
        raise RuntimeError("runner requires source and output --pass arguments")
    return Path(values[0]), Path(values[1])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _close_all_documents() -> None:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)


def _optional_bool_call(value: Any, method_name: str) -> bool | None:
    method = getattr(value, method_name, None)
    if not callable(method):
        return None
    try:
        return bool(method())
    except Exception:
        return None


def main() -> None:
    source_path, output_path = _arguments()
    before_hash = _sha256(source_path)
    _close_all_documents()
    document = App.openDocument(str(source_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to open capture discovery fixture")

    try:
        touched_before = _optional_bool_call(document, "isTouched")
        saved_before = _optional_bool_call(document, "isSaved")
        discovery = discover_capture_candidates(document)
        touched_after = _optional_bool_call(document, "isTouched")
        saved_after = _optional_bool_call(document, "isSaved")
        document_name = document.Name
        document_label = document.Label
    finally:
        _close_all_documents()

    after_hash = _sha256(source_path)
    payload = {
        "source": {
            "path": str(source_path),
            "sha256BeforeOpen": before_hash,
            "sha256AfterClose": after_hash,
            "unchanged": before_hash == after_hash,
        },
        "document": {
            "name": document_name,
            "label": document_label,
            "touchedBefore": touched_before,
            "touchedAfter": touched_after,
            "savedBefore": saved_before,
            "savedAfter": saved_after,
        },
        "discovery": discovery.to_mapping(),
    }
    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


main()
