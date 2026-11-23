"""Typed deterministic failures for the GUI-free capture core.

The capture core validates FreeCAD-authored capture drafts against the
Engine-owned ``prm.cad.json`` schema and applies the repository's semantic-name
and stable-ID policy. It does not import FreeCAD. Every failure is classified so
callers can distinguish contract validation, authoring policy, and file-write
failures without inspecting error text.
"""

from __future__ import annotations

from collections.abc import Iterable


class CaptureError(ValueError):
    """Base class for deterministic capture failures."""


class CaptureContractError(CaptureError):
    """Raised when a capture draft violates the schema 1.0 contract."""

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = tuple(problems)
        if not self.problems:
            raise ValueError("CaptureContractError requires at least one problem")
        super().__init__(
            "capture contract validation failed: " + "; ".join(self.problems)
        )


class CaptureNamePolicyError(CaptureError):
    """Raised when a semantic name violates the authoring name policy."""


class CaptureIdPolicyError(CaptureError):
    """Raised when a stable identifier violates the authoring ID policy."""


class CaptureWriteError(OSError):
    """Raised when a canonical capture file cannot be written atomically."""


__all__ = [
    "CaptureContractError",
    "CaptureError",
    "CaptureIdPolicyError",
    "CaptureNamePolicyError",
    "CaptureWriteError",
]
