"""Test-only FreeCAD host for the metadata mutation lifecycle proof.

Not production code. Copies the caller-prepared working copy, invokes the
production ``run_execution_entrypoint``, and emits a deterministic JSON summary
built from the production result, observed output, and persisted native state.

    nix develop --command freecadcmd -P <repo> \
      tests/freecad_metadata_mutation_lifecycle_runner.py \
      --pass=/absolute/path/to/working-copy \
      --pass=execute|failure
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import FreeCAD as App

from parametron_freecad.runtime import entrypoints

PASS_PREFIX = "--pass="

SOURCE_NAME = "metadata-coexistence.FCStd"
BODY_NAME = "MetadataBody"
SKETCH_NAME = "ProfileSketch"
PAD_NAME = "Pad"
MARKER_NAME = "DeletionMarker"
VARSET_NAME = "Parameters"
PARAMETER_NAME = "pilotValue"

METADATA_PROPERTY_NAMES = (
    "material",
    "tagged",
    "mass",
    "revision",
    "tolerance",
    "sequence",
    "measured_length",
)


def _arguments() -> tuple[Path, str]:
    values = [
        argument[len(PASS_PREFIX) :]
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 2:
        raise RuntimeError("runner requires root and mode --pass arguments")
    return Path(values[0]), values[1]


def _close_all_documents() -> None:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _property_value(native_object, name: str):
    value = getattr(native_object, name)
    if hasattr(value, "Value"):
        return float(value.Value)
    return value


def _shape_inventory(shape) -> dict[str, object]:
    return {
        "isNull": shape.isNull(),
        "isValid": shape.isValid(),
        "solidCount": len(shape.Solids),
    }


def _metadata_group_properties(native_object) -> list[str]:
    names: list[str] = []
    for name in native_object.PropertiesList:
        try:
            if native_object.getGroupOfProperty(name) == "Metadata":
                names.append(name)
        except Exception:
            continue
    return sorted(names)


def _native_inventory(source_path: Path) -> dict[str, object]:
    _close_all_documents()
    document = App.openDocument(str(source_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to reopen persisted working copy")
    try:
        body = document.getObject(BODY_NAME)
        sketch = document.getObject(SKETCH_NAME)
        pad = document.getObject(PAD_NAME)
        marker = document.getObject(MARKER_NAME)
        var_set = document.getObject(VARSET_NAME)
        missing = [
            name
            for name, value in (
                (BODY_NAME, body),
                (SKETCH_NAME, sketch),
                (PAD_NAME, pad),
                (VARSET_NAME, var_set),
            )
            if value is None
        ]
        if missing:
            raise RuntimeError(f"persisted working copy lacks objects: {missing!r}")

        metadata = {}
        for name in METADATA_PROPERTY_NAMES:
            if name in body.PropertiesList:
                metadata[name] = {
                    "present": True,
                    "typeId": body.getTypeIdOfProperty(name),
                    "value": _property_value(body, name),
                }
            else:
                metadata[name] = {"present": False}

        return {
            "metadata": metadata,
            "bodyProperties": list(body.PropertiesList),
            "metadataGroupProperties": _metadata_group_properties(body),
            "supplierPresent": "supplier" in body.PropertiesList,
            "bodyShape": _shape_inventory(body.Shape),
            "bodyVisibility": bool(body.Visibility),
            "padSuppressed": bool(pad.Suppressed),
            "parameterValue": _property_value(var_set, PARAMETER_NAME),
            "markerPresent": marker is not None,
            "sketchReadOnlyValue": int(getattr(sketch, "_ExternalGeoVersion")),
        }
    finally:
        _close_all_documents()


def _observed(document: Path) -> dict[str, object] | None:
    path = document / "outputs" / "prm.observed.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _result(document: Path) -> dict[str, object] | None:
    path = document / "prm.result.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    root, mode = _arguments()
    if mode not in ("execute", "failure"):
        raise RuntimeError(f"unsupported runner mode: {mode!r}")
    source_path = root / "source" / SOURCE_NAME
    if not source_path.is_file():
        raise RuntimeError(f"working copy lacks source document: {source_path}")

    before = _digest(source_path)
    _close_all_documents()
    error: dict[str, object] | None = None
    try:
        entrypoints.run_execution_entrypoint(
            working_copy=root,
            manifest_path=root / "prm.export-manifest.json",
            result_path=root / "prm.result.json",
            output_directory=root / "outputs",
            observation_request_path=(
                root / "prm.verification.json" if mode == "execute" else None
            ),
            freecad_module=App,
        )
    except entrypoints.ExecutionEntrypointError as exc:
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "causeType": (
                type(exc.__cause__).__name__ if exc.__cause__ is not None else None
            ),
        }
    finally:
        _close_all_documents()

    after = _digest(source_path)
    summary = {
        "mode": mode,
        "result": _result(root),
        "error": error,
        "observed": _observed(root),
        "native": _native_inventory(source_path),
        "sourceDigestBefore": before,
        "sourceDigestAfter": after,
    }
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


main()
