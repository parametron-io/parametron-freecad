"""Test-only FreeCAD-host helper for real post-mutation validity fixture tests.

Not production code. Supports two request modes and emits a deterministic
JSON payload built entirely from
``parametron_freecad.execution.post_mutation_validity`` results.

Mode "inspect" opens an existing ``.FCStd`` file and, for each named object,
runs ``inspect_post_mutation_validity`` and ``inspect_native_dependencies``
twice each (same live document, same process) to prove repeated-call
determinism, and captures a before/after Suppressed/Visibility snapshot of
every named object to prove the inspection functions are read-only.

Mode "empty_body" creates a brand-new, test-owned, in-memory document
containing a single freshly added ``PartDesign::Body`` (no fixture file
involved), recomputes it once, and runs ``inspect_post_mutation_validity``
against it twice to prove that a genuinely null native Body shape is
deterministically classified as ``InvalidNativeCadStateError`` by real
FreeCAD, not only by a fake Python object.

    nix develop --command freecadcmd \
      -P /absolute/path/to/repository/root \
      tests/freecad_post_mutation_validity_runner.py \
      --pass=/absolute/path/to/request.json \
      --pass=/absolute/path/to/output.json

request.json shape (mode "inspect"):
    {
      "mode": "inspect",
      "sourcePath": "/absolute/path/to/document.FCStd",
      "objects": ["MutationBody", "SafeDeleteMarker", "BaseSketch"]
    }

request.json shape (mode "empty_body"):
    {
      "mode": "empty_body"
    }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD as App

from parametron_freecad.execution.post_mutation_validity import (
    PostMutationValidityError,
    inspect_native_dependencies,
    inspect_post_mutation_validity,
)


PASS_PREFIX = "--pass="


def _arguments() -> tuple[Path, Path]:
    values = [
        argument[len(PASS_PREFIX):]
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 2:
        raise RuntimeError("runner requires request and output --pass arguments")
    return Path(values[0]), Path(values[1])


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
            "suppressed": (
                bool(target.Suppressed) if "Suppressed" in target.PropertiesList else None
            ),
            "suppressedPropertyType": _property_type(target, "Suppressed"),
            "visibility": (
                bool(target.Visibility) if "Visibility" in target.PropertiesList else None
            ),
            "visibilityPropertyType": _property_type(target, "Visibility"),
        }
    return snapshot


def _validity_result(document, object_name: str) -> dict[str, object]:
    try:
        evidence = inspect_post_mutation_validity(document, object_name)
    except PostMutationValidityError as exc:
        return {
            "ok": False,
            "type": type(exc).__name__,
            "message": str(exc),
            "causeType": (
                type(exc.__cause__).__name__ if exc.__cause__ is not None else None
            ),
        }
    return {
        "ok": True,
        "objectName": evidence.object_name,
        "isNull": evidence.is_null,
        "isValid": evidence.is_valid,
        "solidCount": evidence.solid_count,
    }


def _dependency_result(document, object_name: str) -> dict[str, object]:
    try:
        evidence = inspect_native_dependencies(document, object_name)
    except PostMutationValidityError as exc:
        return {
            "ok": False,
            "type": type(exc).__name__,
            "message": str(exc),
            "causeType": (
                type(exc.__cause__).__name__ if exc.__cause__ is not None else None
            ),
        }
    return {
        "ok": True,
        "objectName": evidence.object_name,
        "dependents": list(evidence.dependent_object_names),
        "dependencies": list(evidence.dependency_object_names),
    }


def _run_inspect(request: dict[str, object]) -> dict[str, object]:
    source_path = Path(request["sourcePath"])  # type: ignore[arg-type]
    object_names = list(request["objects"])  # type: ignore[arg-type]

    _close_all_documents()
    document = App.openDocument(str(source_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to open post-mutation validity fixture")
    try:
        document.recompute()
        before = _snapshot(document, object_names)

        results: dict[str, object] = {}
        for name in object_names:
            results[name] = {
                "validity": [
                    _validity_result(document, name),
                    _validity_result(document, name),
                ],
                "dependency": [
                    _dependency_result(document, name),
                    _dependency_result(document, name),
                ],
            }

        after = _snapshot(document, object_names)
    finally:
        _close_all_documents()

    return {"before": before, "after": after, "results": results}


def _run_empty_body() -> dict[str, object]:
    _close_all_documents()
    document = App.newDocument("empty_body_probe")
    try:
        document.addObject("PartDesign::Body", "EmptyBody")
        document.recompute()

        results = [
            _validity_result(document, "EmptyBody"),
            _validity_result(document, "EmptyBody"),
        ]
    finally:
        _close_all_documents()

    return {"validity": results}


def main() -> None:
    request_path, output_path = _arguments()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    mode = request["mode"]

    if mode == "inspect":
        payload = _run_inspect(request)
    elif mode == "empty_body":
        payload = _run_empty_body()
    else:
        raise RuntimeError(f"unsupported mode: {mode!r}")

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


main()
