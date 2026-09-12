"""Deterministic Phase 1 PDF artifact export helper."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, Sequence

from parametron_freecad.common.paths import require_child_path, resolve_path
from parametron_freecad.execution.manifest_contract import (
    EXPORT_MANIFEST_V1_CONTRACT,
    OUTPUT_FORMAT_PDF,
)

_output_contract = EXPORT_MANIFEST_V1_CONTRACT.output


class PdfArtifactExportError(ValueError):
    """Raised when a PDF artifact cannot be exported deterministically."""


def export_pdf_artifacts(
    document: Any,
    outputs: Sequence[dict[str, Any]],
    *,
    working_copy: Path,
    techdraw_gui_module: Any | None = None,
) -> None:
    """Export declared manifest outputs whose format is exactly "pdf".

    Processes outputs in manifest order. Resolves each path relative to
    working_copy when relative, enforces containment, requires the parent
    directory to already exist, and calls the TechDrawGui PDF exporter once
    per matching output using the FreeCAD document object named by output["id"].
    """
    pdf_outputs = [
        output
        for output in outputs
        if output.get(_output_contract.format_field) == OUTPUT_FORMAT_PDF
    ]

    if not pdf_outputs:
        return

    exporter = _resolve_exporter(techdraw_gui_module)

    for output in pdf_outputs:
        output_path_str = output[_output_contract.path_field]
        output_id = output[_output_contract.id_field]
        resolved = _resolve_output_path(output_path_str, working_copy=working_copy, output_id=output_id)
        page = _resolve_page(document, output_id)
        _export_single(exporter, page, resolved, output_id=output_id)


def _resolve_exporter(techdraw_gui_module: Any | None) -> Any:
    if techdraw_gui_module is not None:
        return techdraw_gui_module

    try:
        return import_module("TechDrawGui")
    except ImportError as exc:
        raise PdfArtifactExportError(
            f"TechDrawGui module is not available: {exc}"
        ) from exc


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
        raise PdfArtifactExportError(
            f"PDF output path escapes working copy (id={output_id!r}): {exc}"
        ) from exc

    parent = contained.parent
    if not parent.exists():
        raise PdfArtifactExportError(
            f"PDF output parent directory does not exist (id={output_id!r}): {parent}"
        )
    if not parent.is_dir():
        raise PdfArtifactExportError(
            f"PDF output parent path is not a directory (id={output_id!r}): {parent}"
        )

    return contained


def _resolve_page(document: Any, output_id: str) -> Any:
    get_object = getattr(document, "getObject", None)
    if not callable(get_object):
        raise PdfArtifactExportError(
            f"document does not provide a callable getObject (id={output_id!r})"
        )

    try:
        page = get_object(output_id)
    except Exception as exc:
        raise PdfArtifactExportError(
            f"document.getObject raised an exception (id={output_id!r}): {exc}"
        ) from exc

    if page is None:
        raise PdfArtifactExportError(
            f"document.getObject returned no page object (id={output_id!r})"
        )

    return page


def _export_single(
    exporter: Any,
    page: Any,
    path: Path,
    *,
    output_id: str,
) -> None:
    export_page_fn = getattr(exporter, "exportPageAsPdf", None)
    if callable(export_page_fn):
        try:
            export_page_fn(page, str(path))
        except Exception as exc:
            raise PdfArtifactExportError(
                f"PDF export raised an exception (id={output_id!r}): {exc}"
            ) from exc
        return

    export_fn = getattr(exporter, "export", None)
    if callable(export_fn):
        try:
            export_fn([page], str(path))
        except Exception as exc:
            raise PdfArtifactExportError(
                f"PDF export raised an exception (id={output_id!r}): {exc}"
            ) from exc
        return

    raise PdfArtifactExportError(
        f"TechDrawGui exporter provides no supported PDF export function"
        f" (id={output_id!r}): tried exportPageAsPdf and export"
    )


__all__ = [
    "PdfArtifactExportError",
    "export_pdf_artifacts",
]
