"""Deterministic Phase 1 STEP artifact export helper."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from parametron_freecad.common.paths import require_child_path, resolve_path
from parametron_freecad.execution.manifest_contract import (
    EXPORT_MANIFEST_V1_CONTRACT,
    OUTPUT_FORMAT_STEP,
)

_output_contract = EXPORT_MANIFEST_V1_CONTRACT.output


class StepArtifactExportError(ValueError):
    """Raised when a STEP artifact cannot be exported deterministically."""


def export_step_artifacts(
    document: Any,
    outputs: Sequence[dict[str, Any]],
    *,
    working_copy: Path,
    import_module: Any | None = None,
) -> None:
    """Export declared manifest outputs whose format is exactly "step".

    Processes outputs in manifest order. For each STEP output, resolves the
    exact FreeCAD object named by output["id"] through document.getObject,
    resolves each path relative to working_copy when relative, enforces
    containment, requires the parent directory to already exist, and calls the
    FreeCAD STEP exporter once per matching output with that selected object.
    """
    step_outputs = [
        output
        for output in outputs
        if output.get(_output_contract.format_field) == OUTPUT_FORMAT_STEP
    ]

    if not step_outputs:
        return

    exporter = _resolve_exporter(import_module)

    for output in step_outputs:
        output_id = output[_output_contract.id_field]
        selected_object = _resolve_step_object(document, output_id)
        output_path_str = output[_output_contract.path_field]
        resolved = _resolve_output_path(output_path_str, working_copy=working_copy, output_id=output_id)
        _export_single(exporter, selected_object, resolved, output_id=output_id)


def _resolve_exporter(import_module: Any | None) -> Any:
    if import_module is not None:
        return import_module

    try:
        from importlib import import_module as _import_module
        return _import_module("Import")
    except ImportError as exc:
        raise StepArtifactExportError(
            f"FreeCAD Import module is not available: {exc}"
        ) from exc


def _resolve_step_object(document: Any, output_id: str) -> Any:
    get_object = getattr(document, "getObject", None)
    if not callable(get_object):
        raise StepArtifactExportError(
            f"document does not provide a callable getObject (id={output_id!r})"
        )

    try:
        selected = get_object(output_id)
    except Exception as exc:
        raise StepArtifactExportError(
            f"document.getObject raised an exception (id={output_id!r}): {exc}"
        ) from exc

    if selected is None:
        raise StepArtifactExportError(
            f"document.getObject returned no STEP export object (id={output_id!r})"
        )

    return selected


def _resolve_output_path(
    path_str: str,
    *,
    working_copy: Path,
    output_id: str,
) -> Path:
    raw = Path(path_str)

    if raw.is_absolute():
        resolved = raw.resolve(strict=False)
    else:
        resolved = resolve_path(raw, base=working_copy)

    try:
        contained = require_child_path(working_copy, resolved)
    except ValueError as exc:
        raise StepArtifactExportError(
            f"STEP output path escapes working copy (id={output_id!r}): {exc}"
        ) from exc

    parent = contained.parent
    if not parent.exists():
        raise StepArtifactExportError(
            f"STEP output parent directory does not exist (id={output_id!r}): {parent}"
        )
    if not parent.is_dir():
        raise StepArtifactExportError(
            f"STEP output parent path is not a directory (id={output_id!r}): {parent}"
        )

    return contained


def _export_single(
    exporter: Any,
    selected_object: Any,
    path: Path,
    *,
    output_id: str,
) -> None:
    export_fn = getattr(exporter, "export", None)
    if not callable(export_fn):
        raise StepArtifactExportError(
            f"STEP exporter does not provide a callable export function (id={output_id!r})"
        )

    try:
        export_fn([selected_object], str(path))
    except Exception as exc:
        raise StepArtifactExportError(
            f"STEP export raised an exception (id={output_id!r}): {exc}"
        ) from exc


__all__ = [
    "StepArtifactExportError",
    "export_step_artifacts",
]
