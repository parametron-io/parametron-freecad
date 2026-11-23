"""Parametron FreeCAD workbench: GUI-free capture state and session.

This package holds the GUI-free four-tab capture state model and capture
session. The FreeCAD/Qt panel, commands, and workbench registration live in
separate modules that are only imported by ``InitGui.py``. Importing this
package is safe under headless FreeCAD and plain Python; it does not import
``FreeCAD``, ``FreeCADGui``, or Qt.
"""

from __future__ import annotations

from parametron_workbench.selection import (
    build_default_semantic_selection,
    load_semantic_selection,
)
from parametron_workbench.session import CaptureSession, default_options
from parametron_workbench.state import (
    CapturePanelError,
    CapturePanelOptions,
    CapturePanelSnapshot,
    CapturePanelState,
    CaptureTab,
    ComponentRow,
    FeatureRow,
    MetadataRow,
    ParameterRow,
    TabAvailability,
)

__all__ = [
    "CapturePanelError",
    "CapturePanelOptions",
    "CapturePanelSnapshot",
    "CapturePanelState",
    "CaptureSession",
    "CaptureTab",
    "ComponentRow",
    "FeatureRow",
    "MetadataRow",
    "ParameterRow",
    "TabAvailability",
    "build_default_semantic_selection",
    "default_options",
    "load_semantic_selection",
]
