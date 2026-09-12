"""Deterministic Phase 1 document recompute execution helper."""

from __future__ import annotations

from typing import Any


class DocumentRecomputeError(ValueError):
    """Raised when document recompute cannot be completed deterministically."""


def recompute_document(document: Any) -> None:
    """Call document.recompute() exactly once on an opened FreeCAD document."""
    recompute = getattr(document, "recompute", None)
    if not callable(recompute):
        raise DocumentRecomputeError(
            "document does not provide a callable recompute method"
        )

    try:
        recompute()
    except Exception as exc:
        raise DocumentRecomputeError(
            f"document recompute raised an exception: {exc}"
        ) from exc


__all__ = [
    "DocumentRecomputeError",
    "recompute_document",
]
