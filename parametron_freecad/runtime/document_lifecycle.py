"""Deterministic FreeCAD document lifecycle helpers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from parametron_freecad.common.paths import require_child_path, resolve_path


@dataclass(frozen=True, slots=True)
class OpenedDocument:
    """Resolved source path and the opened FreeCAD document handle."""

    path: Path
    document: Any
    document_name: str


class DocumentLifecycleError(ValueError):
    """Base class for deterministic document lifecycle failures."""


class SourceDocumentPathError(DocumentLifecycleError):
    """Raised when manifest sourceDocument cannot be resolved safely."""


class DocumentOpenError(DocumentLifecycleError):
    """Raised when FreeCAD cannot open the requested document."""


class DocumentCloseError(DocumentLifecycleError):
    """Raised when FreeCAD cannot close an opened document deterministically."""


def resolve_source_document_path(working_copy: Path, source_document: str) -> Path:
    """Resolve a manifest source document path within the validated working copy."""

    resolved_working_copy = resolve_path(working_copy)
    resolved_source_document = resolve_path(source_document, base=resolved_working_copy)

    try:
        resolved_source_document = require_child_path(
            resolved_working_copy,
            resolved_source_document,
        )
    except ValueError as exc:
        raise SourceDocumentPathError(
            f"sourceDocument path escapes working copy: {resolved_source_document}"
        ) from exc

    if not resolved_source_document.exists():
        raise SourceDocumentPathError(
            f"sourceDocument file does not exist: {resolved_source_document}"
        )

    if not resolved_source_document.is_file():
        raise SourceDocumentPathError(
            f"sourceDocument path is not a file: {resolved_source_document}"
        )

    return resolved_source_document


def open_freecad_document(freecad_module: Any, path: Path) -> OpenedDocument:
    """Open a FreeCAD document through the supplied module-like object."""

    resolved_path = resolve_path(path)
    open_document = getattr(freecad_module, "openDocument", None)
    if not callable(open_document):
        raise DocumentOpenError("FreeCAD module does not provide openDocument")

    try:
        document = open_document(str(resolved_path))
    except Exception as exc:
        raise DocumentOpenError(
            f"FreeCAD failed to open document: {resolved_path}"
        ) from exc

    document_name = getattr(document, "Name", None)
    if not isinstance(document_name, str) or document_name == "":
        raise DocumentOpenError(
            f"FreeCAD returned document without a stable Name: {resolved_path}"
        )

    return OpenedDocument(
        path=resolved_path,
        document=document,
        document_name=document_name,
    )


def close_freecad_document(freecad_module: Any, opened: OpenedDocument) -> None:
    """Close an opened FreeCAD document by its stable document name."""

    close_document = getattr(freecad_module, "closeDocument", None)
    if not callable(close_document):
        raise DocumentCloseError("FreeCAD module does not provide closeDocument")

    try:
        close_document(opened.document_name)
    except Exception as exc:
        raise DocumentCloseError(
            f"FreeCAD failed to close document: {opened.document_name}"
        ) from exc


@contextmanager
def opened_freecad_document(
    freecad_module: Any,
    path: Path,
) -> Iterator[OpenedDocument]:
    """Open a FreeCAD document and close it deterministically on exit."""

    opened = open_freecad_document(freecad_module, path)
    try:
        yield opened
    except BaseException as exc:
        try:
            close_freecad_document(freecad_module, opened)
        except Exception as close_exc:
            exc.add_note(f"document cleanup also failed: {close_exc}")
        raise
    else:
        close_freecad_document(freecad_module, opened)


__all__ = [
    "DocumentCloseError",
    "DocumentLifecycleError",
    "DocumentOpenError",
    "OpenedDocument",
    "SourceDocumentPathError",
    "close_freecad_document",
    "open_freecad_document",
    "opened_freecad_document",
    "resolve_source_document_path",
]
