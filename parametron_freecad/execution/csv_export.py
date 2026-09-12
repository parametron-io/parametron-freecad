"""Deterministic Phase 1 CSV artifact export helper."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Sequence

from parametron_freecad.common.paths import require_child_path, resolve_path
from parametron_freecad.execution.manifest_contract import (
    EXPORT_MANIFEST_V1_CONTRACT,
    OUTPUT_FORMAT_CSV,
)

_output_contract = EXPORT_MANIFEST_V1_CONTRACT.output

_CELL_ADDRESS_RE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")


class CsvArtifactExportError(ValueError):
    """Raised when a CSV artifact cannot be exported deterministically."""


def export_csv_artifacts(
    document: Any,
    outputs: Sequence[dict[str, Any]],
    *,
    working_copy: Path,
) -> None:
    """Export declared manifest outputs whose format is exactly "csv".

    Processes outputs in manifest order. Resolves each path relative to
    working_copy when relative, enforces containment, requires the parent
    directory to already exist, and writes a deterministic UTF-8 CSV file
    from the FreeCAD Spreadsheet object named by output["id"].
    """
    csv_outputs = [
        output
        for output in outputs
        if output.get(_output_contract.format_field) == OUTPUT_FORMAT_CSV
    ]

    if not csv_outputs:
        return

    for output in csv_outputs:
        output_path_str = output[_output_contract.path_field]
        output_id = output[_output_contract.id_field]
        resolved = _resolve_output_path(output_path_str, working_copy=working_copy, output_id=output_id)
        spreadsheet = _resolve_spreadsheet(document, output_id)
        grid = _extract_grid(spreadsheet, output_id)
        _write_csv(resolved, grid)


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
        raise CsvArtifactExportError(
            f"CSV output path escapes working copy (id={output_id!r}): {exc}"
        ) from exc

    parent = contained.parent
    if not parent.exists():
        raise CsvArtifactExportError(
            f"CSV output parent directory does not exist (id={output_id!r}): {parent}"
        )
    if not parent.is_dir():
        raise CsvArtifactExportError(
            f"CSV output parent path is not a directory (id={output_id!r}): {parent}"
        )

    return contained


def _resolve_spreadsheet(document: Any, output_id: str) -> Any:
    """Return the spreadsheet object for output_id or raise a deterministic error."""
    get_object = getattr(document, "getObject", None)
    if not callable(get_object):
        raise CsvArtifactExportError(
            f"document does not provide a callable getObject (id={output_id!r})"
        )

    try:
        spreadsheet = get_object(output_id)
    except Exception as exc:
        raise CsvArtifactExportError(
            f"document.getObject raised an exception (id={output_id!r}): {exc}"
        ) from exc

    if spreadsheet is None:
        raise CsvArtifactExportError(
            f"document.getObject returned no spreadsheet object (id={output_id!r})"
        )

    return spreadsheet


def _col_letter_to_index(col: str) -> int:
    """Convert column letter(s) to 1-based index. A->1, Z->26, AA->27."""
    result = 0
    for char in col:
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result


def _extract_grid(spreadsheet: Any, output_id: str) -> list[list[str]]:
    """Extract cell data as a rectangular row-major list of string rows."""
    content = getattr(spreadsheet, "Content", None)

    if content is None or not hasattr(content, "items"):
        raise CsvArtifactExportError(
            f"spreadsheet object does not expose a supported cell data surface"
            f" (id={output_id!r})"
        )

    occupied: dict[tuple[int, int], Any] = {}
    for key, value in content.items():
        m = _CELL_ADDRESS_RE.match(str(key).strip().upper())
        if not m:
            continue
        col_idx = _col_letter_to_index(m.group(1))
        row_idx = int(m.group(2))
        occupied[(row_idx, col_idx)] = value

    if not occupied:
        return []

    max_row = max(r for r, _ in occupied)
    max_col = max(c for _, c in occupied)

    rows: list[list[str]] = []
    for row in range(1, max_row + 1):
        row_data: list[str] = []
        for col in range(1, max_col + 1):
            val = occupied.get((row, col))
            row_data.append("" if val is None else str(val))
        rows.append(row_data)

    return rows


def _write_csv(path: Path, grid: list[list[str]]) -> None:
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            for row in grid:
                writer.writerow(row)
    except (OSError, csv.Error) as exc:
        raise CsvArtifactExportError(
            f"CSV file write failed ({path}): {exc}"
        ) from exc


__all__ = [
    "CsvArtifactExportError",
    "export_csv_artifacts",
]
