"""Qt binding import shim for the Parametron workbench GUI layer.

FreeCAD builds ship different Qt bindings. This module centralizes the import
so the GUI modules do not duplicate fallback logic. It must only be imported by
GUI modules, never by the GUI-free state or session.
"""

from __future__ import annotations

try:  # FreeCAD ships a PySide compatibility shim first.
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover - depends on the FreeCAD build
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
    except ImportError:  # pragma: no cover
        from PySide6 import QtCore, QtGui, QtWidgets

__all__ = ["QtCore", "QtGui", "QtWidgets"]
