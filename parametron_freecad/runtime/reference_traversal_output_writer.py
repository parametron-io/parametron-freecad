"""Direct writer for deterministic raw reference traversal output."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

from parametron_freecad.runtime.reference_traversal_output_contract import (
    ReferenceTraversalOutputContractError,
    RawReferenceTraversalDiagnostic,
    resolve_reference_traversal_output_path as _resolve_output_path,
)
from parametron_freecad.runtime.reference_traversal_output import (
    RawReferenceTraversalEdge,
    RawReferenceTraversalNode,
    serialize_reference_traversal_output,
)


class ReferenceTraversalOutputWriteError(OSError):
    """Raised when raw reference traversal output cannot be written."""


def write_reference_traversal_output(
    output_path: str | Path,
    *,
    boundary: str,
    operation: str,
    status: str,
    source_document: str,
    nodes: Sequence[RawReferenceTraversalNode],
    edges: Sequence[RawReferenceTraversalEdge],
    diagnostics: Sequence[RawReferenceTraversalDiagnostic] = (),
) -> None:
    """Serialize and directly write raw traversal bytes to ``output_path``."""
    try:
        serialized = serialize_reference_traversal_output(
            boundary=boundary,
            operation=operation,
            status=status,
            source_document=source_document,
            nodes=nodes,
            edges=edges,
            diagnostics=diagnostics,
        )
        with open(output_path, "wb") as output_file:
            output_file.write(serialized)
    except Exception as exc:
        raise ReferenceTraversalOutputWriteError(
            f"failed to write reference traversal output file {output_path}"
        ) from exc


def write_reference_traversal_output_atomically(
    working_copy: str | Path,
    output_path: str | Path,
    *,
    boundary: str,
    operation: str,
    status: str,
    source_document: str,
    nodes: Sequence[RawReferenceTraversalNode],
    edges: Sequence[RawReferenceTraversalEdge],
    diagnostics: Sequence[RawReferenceTraversalDiagnostic] = (),
) -> None:
    """Atomically write raw traversal bytes within ``working_copy``."""
    _write_reference_traversal_output_atomically(
        working_copy,
        output_path,
        serializer=serialize_reference_traversal_output,
        boundary=boundary,
        operation=operation,
        status=status,
        source_document=source_document,
        nodes=nodes,
        edges=edges,
        diagnostics=diagnostics,
    )


def _write_reference_traversal_output_atomically(
    working_copy: str | Path,
    output_path: str | Path,
    *,
    serializer,
    boundary: str,
    operation: str,
    status: str,
    source_document: str,
    nodes,
    edges,
    diagnostics,
) -> None:
    temporary_path: Path | None = None
    descriptor: int | None = None
    primary_error: Exception | None = None
    failure_phase = "containment"

    try:
        target = _resolve_output_path(
            working_copy=working_copy,
            output_path=output_path,
        )
        failure_phase = "write"
        serialized = serializer(
            boundary=boundary,
            operation=operation,
            status=status,
            source_document=source_document,
            nodes=nodes,
            edges=edges,
            diagnostics=diagnostics,
        )
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        output_file = os.fdopen(descriptor, "wb")
        descriptor = None
        with output_file:
            output_file.write(serialized)
        os.replace(temporary_path, target)
        temporary_path = None
    except Exception as exc:
        primary_error = exc
        writer_error = ReferenceTraversalOutputWriteError(
            f"failed to atomically write reference traversal output file "
            f"{output_path}"
        )
        writer_error._is_containment_failure = (
            failure_phase == "containment"
            and isinstance(exc, ReferenceTraversalOutputContractError)
        )
        raise writer_error from exc
    finally:
        cleanup_error: Exception | None = None
        if descriptor is not None:
            try:
                os.close(descriptor)
            except Exception as exc:
                cleanup_error = exc
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except Exception as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if primary_error is None and cleanup_error is not None:
            raise ReferenceTraversalOutputWriteError(
                f"failed to atomically write reference traversal output file "
                f"{output_path}"
            ) from cleanup_error


__all__ = [
    "ReferenceTraversalOutputWriteError",
    "write_reference_traversal_output",
    "write_reference_traversal_output_atomically",
]
