"""Test-only FreeCAD-host helper for real deletion mutation fixture tests.

Not production code. Supports two request modes and emits a deterministic
JSON payload built entirely from invoking the production
``parametron_freecad.execution.deletion.apply_deletion_mutations(...)``
consumer. The runner does not reimplement deletion, dependency, or validity
logic; it only opens documents, captures inventory snapshots, invokes the
production consumer, and reports results as JSON.

Mode "fixture" opens an existing ``.FCStd`` file, captures a native
before-state inventory for caller-named objects, invokes the production
consumer with caller-supplied mutations, captures a native after-state
inventory for the same objects, and emits the result. Any
``DeletionMutationError`` raised by the production consumer is captured and
reported in the payload rather than propagated, so both successful and
controlled-failure behavior can be inspected from the JSON output. Any other
exception is left to propagate and fail the host process.

Mode "invalid_state" creates a brand-new, test-owned, in-memory document
containing a freely removable unreferenced object and a genuinely invalid
(empty, unrecomputed-feature) ``PartDesign::Body``, then invokes the
production consumer requesting deletion of only the removable object. This
proves the consumer reaches the native post-delete validity boundary and
reports ``DeletionValidityError`` rather than success, driven by genuine
native evidence rather than a fabricated engineering rule.

    nix develop --command freecadcmd \
      -P /absolute/path/to/repository/root \
      tests/freecad_deletion_runner.py \
      --pass=/absolute/path/to/request.json \
      --pass=/absolute/path/to/output.json

request.json shape (mode "fixture"):
    {
      "mode": "fixture",
      "sourcePath": "/absolute/path/to/document.FCStd",
      "objects": ["SafeDeleteMarker", "MutationBody"],
      "mutations": [{"object": "SafeDeleteMarker"}]
    }

request.json shape (mode "invalid_state"):
    {
      "mode": "invalid_state"
    }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD as App

from parametron_freecad.execution.deletion import (
    DeletionMutationError,
    apply_deletion_mutations,
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


def _object_names(document) -> list[str]:
    return sorted(target.Name for target in document.Objects)


def _snapshot(document, object_names: list[str]) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for name in object_names:
        target = document.getObject(name)
        snapshot[name] = None if target is None else {"typeId": target.TypeId}
    return snapshot


def _run_deletion(document, mutations: list[dict[str, object]]) -> dict[str, object]:
    try:
        apply_deletion_mutations(document, mutations)
    except DeletionMutationError as exc:
        return {
            "type": type(exc).__name__,
            "message": str(exc),
            "causeType": (
                type(exc.__cause__).__name__ if exc.__cause__ is not None else None
            ),
        }
    return None


def _run_fixture(request: dict[str, object]) -> dict[str, object]:
    source_path = Path(request["sourcePath"])  # type: ignore[arg-type]
    object_names = list(request["objects"])  # type: ignore[arg-type]
    mutations = list(request["mutations"])  # type: ignore[arg-type]

    _close_all_documents()
    document = App.openDocument(str(source_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to open deletion fixture")
    try:
        before = _snapshot(document, object_names)
        before_inventory = _object_names(document)

        error = _run_deletion(document, mutations)

        after = _snapshot(document, object_names)
        after_inventory = _object_names(document)
    finally:
        _close_all_documents()

    return {
        "before": before,
        "after": after,
        "beforeInventory": before_inventory,
        "afterInventory": after_inventory,
        "error": error,
    }


def _run_invalid_state() -> dict[str, object]:
    _close_all_documents()
    document = App.newDocument("deletion_invalid_state_probe")
    try:
        document.addObject("App::DocumentObjectGroup", "SafeRemovable")
        document.addObject("PartDesign::Body", "EmptyBody")
        document.recompute()

        error = _run_deletion(document, [{"object": "SafeRemovable"}])

        after = {
            "SafeRemovable": document.getObject("SafeRemovable"),
            "EmptyBody": document.getObject("EmptyBody") is not None,
        }
        after_inventory = _object_names(document)
    finally:
        _close_all_documents()

    return {
        "error": error,
        "safeRemovableStillPresent": after["SafeRemovable"] is not None,
        "emptyBodyStillPresent": after["EmptyBody"],
        "afterInventory": after_inventory,
    }


def main() -> None:
    request_path, output_path = _arguments()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    mode = request["mode"]

    if mode == "fixture":
        payload = _run_fixture(request)
    elif mode == "invalid_state":
        payload = _run_invalid_state()
    else:
        raise RuntimeError(f"unsupported mode: {mode!r}")

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


main()
