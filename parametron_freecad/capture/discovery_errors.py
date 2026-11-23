"""Typed deterministic failures for FreeCAD-native capture discovery.

Discovery reads an already-open FreeCAD document through duck-typed native
interfaces. It does not import FreeCAD, FreeCADGui, or Part. Failures are
classified so callers can distinguish an unusable document boundary from a
native inspection failure that prevented deterministic capture candidates.
"""

from __future__ import annotations


class CaptureDiscoveryError(ValueError):
    """Base class for deterministic capture discovery failures."""


class CaptureDiscoveryDocumentError(CaptureDiscoveryError):
    """Raised when a document cannot support native capture discovery."""


class CaptureDiscoveryInspectionError(CaptureDiscoveryError):
    """Raised when required native inspection evidence cannot be obtained."""


__all__ = [
    "CaptureDiscoveryDocumentError",
    "CaptureDiscoveryError",
    "CaptureDiscoveryInspectionError",
]
