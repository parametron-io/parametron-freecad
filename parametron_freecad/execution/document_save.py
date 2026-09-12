"""Deterministic Phase 1 native document persistence execution helper."""

from __future__ import annotations

from typing import Any


class DocumentSaveError(ValueError):
    """Raised when document save cannot be completed deterministically."""


def save_document(document: Any) -> None:
    """Call document.save() exactly once on an opened FreeCAD document."""
    save = getattr(document, "save", None)
    if not callable(save):
        raise DocumentSaveError(
            "document does not provide a callable save method"
        )

    try:
        save()
    except Exception as exc:
        raise DocumentSaveError(
            f"document save raised an exception: {exc}"
        ) from exc


__all__ = [
    "DocumentSaveError",
    "save_document",
]
