"""Read-only verification that the active document is the declared source.

Capture must not invent project context or capture an unsaved document. These
helpers operate on an already-open FreeCAD document through duck-typed native
interfaces and never import FreeCAD, FreeCADGui, or Part. They only read the
document file name and saved state; they never write, recompute, or save.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parametron_freecad.capture.orchestration_errors import (
    CaptureSourceError,
    CaptureUnsavedDocumentError,
)


@dataclass(frozen=True, slots=True)
class ActiveSourceEvidence:
    """Read-only evidence that the active document is the declared source."""

    document_name: str
    document_label: str
    file_name: str
    saved: bool

    def to_mapping(self) -> dict[str, object]:
        return {
            "documentName": self.document_name,
            "documentLabel": self.document_label,
            "fileName": self.file_name,
            "saved": self.saved,
        }


def verify_active_source(
    document: Any,
    expected_source: str | Path,
) -> ActiveSourceEvidence:
    """Verify the active document is the declared source and is saved.

    Raises :class:`CaptureSourceError` when the document has no saved file path,
    the saved path does not resolve to the declared source, or the saved state
    cannot be determined. Raises :class:`CaptureUnsavedDocumentError` when the
    document has unsaved changes.
    """

    file_name = getattr(document, "FileName", None)
    if not isinstance(file_name, str) or file_name.strip() == "":
        raise CaptureSourceError(
            "active document has no saved file path; save or open the declared "
            "project source before capture"
        )

    actual = Path(file_name).resolve(strict=False)
    expected = Path(expected_source).resolve(strict=False)
    if actual != expected:
        raise CaptureSourceError(
            "active document is not the declared project source: "
            f"active={actual} declared={expected}"
        )

    saved = _document_saved(document)
    if saved is False:
        raise CaptureUnsavedDocumentError(
            f"active source document has unsaved changes: {actual}"
        )

    name = getattr(document, "Name", None)
    label = getattr(document, "Label", None)
    return ActiveSourceEvidence(
        document_name=name if isinstance(name, str) else "",
        document_label=label if isinstance(label, str) else "",
        file_name=str(actual),
        saved=saved,
    )


def _document_saved(document: Any) -> bool:
    predicate = getattr(document, "isSaved", None)
    if callable(predicate):
        try:
            value = predicate()
        except Exception as exc:
            raise CaptureSourceError(
                "active document saved-state inspection failed"
            ) from exc
        if isinstance(value, bool):
            return value

    modified = getattr(document, "Modified", None)
    if isinstance(modified, bool):
        return not modified

    raise CaptureSourceError(
        "active document does not expose a usable saved-state signal"
    )


__all__ = ["ActiveSourceEvidence", "verify_active_source"]
