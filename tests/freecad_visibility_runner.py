"""Test-only FreeCAD-host helper for real visibility mutation fixture tests.

Not production code. Opens an arbitrary ``.FCStd`` file, captures a native
before-state inventory for caller-named objects, invokes the production
``parametron_freecad.execution.visibility.apply_visibility_mutations(...)``
consumer with caller-supplied mutations, captures a native after-state
inventory for the same objects, and emits a deterministic JSON payload. Any
``VisibilityMutationError`` raised by the production consumer is captured
and reported in the payload rather than propagated, so both successful and
controlled-failure behavior can be inspected from the JSON output. Any other
exception is left to propagate and fail the host process.

    nix develop --command freecadcmd \
      -P /absolute/path/to/repository/root \
      tests/freecad_visibility_runner.py \
      --pass=/absolute/path/to/document.FCStd \
      --pass=/absolute/path/to/request.json \
      --pass=/absolute/path/to/output.json

request.json shape:
    {
      "objects": ["MutationBody"],
      "mutations": [{"object": "MutationBody", "visible": false}]
    }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD as App

from parametron_freecad.execution.visibility import (
    VisibilityMutationError,
    apply_visibility_mutations,
)


PASS_PREFIX = "--pass="


def _arguments() -> tuple[Path, Path, Path]:
    values = [
        argument[len(PASS_PREFIX):]
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 3:
        raise RuntimeError("runner requires source, request, and output --pass arguments")
    return tuple(Path(value) for value in values)  # type: ignore[return-value]


def _close_all_documents() -> None:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)


def _property_type(value, name: str):
    if name not in value.PropertiesList:
        return None
    return value.getTypeIdOfProperty(name)


def _snapshot(document, object_names: list[str]) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for name in object_names:
        target = document.getObject(name)
        if target is None:
            snapshot[name] = None
            continue
        snapshot[name] = {
            "visibility": (
                bool(target.Visibility) if "Visibility" in target.PropertiesList else None
            ),
            "visibilityPropertyType": _property_type(target, "Visibility"),
            "suppressed": (
                bool(target.Suppressed) if "Suppressed" in target.PropertiesList else None
            ),
            "suppressedPropertyType": _property_type(target, "Suppressed"),
        }
    return snapshot


def main() -> None:
    source_path, request_path, output_path = _arguments()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    object_names = request["objects"]
    mutations = request["mutations"]

    _close_all_documents()
    document = App.openDocument(str(source_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to open visibility fixture")
    try:
        before = _snapshot(document, object_names)

        error = None
        try:
            apply_visibility_mutations(document, mutations)
        except VisibilityMutationError as exc:
            error = {
                "type": type(exc).__name__,
                "message": str(exc),
                "causeType": (
                    type(exc.__cause__).__name__ if exc.__cause__ is not None else None
                ),
            }

        after = _snapshot(document, object_names)
        payload = {"before": before, "after": after, "error": error}
    finally:
        _close_all_documents()

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


main()
