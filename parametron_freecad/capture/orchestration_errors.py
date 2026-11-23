"""Typed deterministic failures for capture orchestration.

The orchestration layer ties project context, native discovery, explicit user
decisions, capture/semantic-map generation, drift detection, preview, and
project-root writing together. It does not import FreeCAD. Every failure is
classified so callers can distinguish project context, source document,
decision, drift, confirmation, and Engine-preflight failures without inspecting
error text.
"""

from __future__ import annotations

from collections.abc import Iterable


class CaptureOrchestrationError(ValueError):
    """Base class for deterministic capture orchestration failures."""


class CaptureProjectError(CaptureOrchestrationError):
    """Raised when ``prm.project.json`` context is missing or invalid."""

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = tuple(problems)
        if not self.problems:
            raise ValueError("CaptureProjectError requires at least one problem")
        super().__init__(
            "capture project context validation failed: " + "; ".join(self.problems)
        )


class CaptureSourceError(CaptureOrchestrationError):
    """Raised when the active document is not the declared capture source."""


class CaptureUnsavedDocumentError(CaptureSourceError):
    """Raised when the declared source document has unsaved changes."""


class CaptureDecisionError(CaptureOrchestrationError):
    """Raised when explicit capture decisions are invalid or incomplete."""

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = tuple(problems)
        if not self.problems:
            raise ValueError("CaptureDecisionError requires at least one problem")
        super().__init__(
            "capture decision validation failed: " + "; ".join(self.problems)
        )


class CaptureDriftEntry:
    """One deterministic difference between retained capture and current state."""

    __slots__ = ("code", "native_ref", "entity", "detail")

    def __init__(
        self,
        code: str,
        *,
        native_ref: str | None,
        entity: str,
        detail: str,
    ) -> None:
        self.code = code
        self.native_ref = native_ref
        self.entity = entity
        self.detail = detail

    def to_mapping(self) -> dict[str, object]:
        return {
            "code": self.code,
            "nativeRef": self.native_ref,
            "entity": self.entity,
            "detail": self.detail,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CaptureDriftEntry):
            return NotImplemented
        return (
            self.code,
            self.native_ref,
            self.entity,
            self.detail,
        ) == (
            other.code,
            other.native_ref,
            other.entity,
            other.detail,
        )

    def __hash__(self) -> int:
        return hash((self.code, self.native_ref, self.entity, self.detail))

    def __repr__(self) -> str:
        return (
            "CaptureDriftEntry("
            f"code={self.code!r}, native_ref={self.native_ref!r}, "
            f"entity={self.entity!r}, detail={self.detail!r})"
        )


class CaptureDriftError(CaptureOrchestrationError):
    """Raised when retained capture identity drifted from current evidence."""

    def __init__(self, entries: Iterable[CaptureDriftEntry]) -> None:
        self.entries = tuple(entries)
        if not self.entries:
            raise ValueError("CaptureDriftError requires at least one entry")
        summary = "; ".join(
            f"{entry.entity} {entry.native_ref!r}: {entry.detail}"
            for entry in self.entries
        )
        super().__init__(
            "capture drift detected; rebind or review required: " + summary
        )


class CaptureConfirmationRequiredError(CaptureOrchestrationError):
    """Raised when writing would replace a differing existing output file."""

    def __init__(self, paths: Iterable[str]) -> None:
        self.paths = tuple(paths)
        if not self.paths:
            raise ValueError(
                "CaptureConfirmationRequiredError requires at least one path"
            )
        super().__init__(
            "capture output replacement requires explicit confirmation for: "
            + ", ".join(self.paths)
        )


class CapturePreflightError(CaptureOrchestrationError):
    """Raised when an explicitly required Engine preflight is unavailable/fails."""


__all__ = [
    "CaptureConfirmationRequiredError",
    "CaptureDecisionError",
    "CaptureDriftEntry",
    "CaptureDriftError",
    "CaptureOrchestrationError",
    "CapturePreflightError",
    "CaptureProjectError",
    "CaptureSourceError",
    "CaptureUnsavedDocumentError",
]
