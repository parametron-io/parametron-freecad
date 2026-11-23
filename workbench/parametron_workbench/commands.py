"""FreeCAD commands for the Parametron capture workbench.

The command opens a capture session for the active saved document and an
explicit project mapping. It reuses the GUI-free capture core for project
context, source verification, discovery, semantic selection, and session
writes. It never copies document lifecycle, discovery, or serialization logic.
"""

from __future__ import annotations

import os

from parametron_freecad.capture import (
    CaptureDiscoveryError,
    CaptureError,
    CaptureOrchestrationError,
    CaptureProjectError,
    CaptureSourceError,
    SemanticMapError,
    discover_capture_candidates,
    load_project_context,
    resolve_model_source_path,
    resolve_selected_model,
    verify_active_source,
)
from parametron_workbench.panel import CapturePanel
from parametron_workbench.qt import QtWidgets
from parametron_workbench.selection import load_semantic_selection
from parametron_workbench.session import CaptureSession


def _icon_path() -> str:
    here = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    return os.path.join(here, "resources", "parametron.svg")


def _freecad_version() -> str:
    try:
        import FreeCAD

        parts = [str(part) for part in FreeCAD.Version()[:3]]
    except Exception:
        return ""
    return ".".join(parts)


def _choose_project(parent: object, start_directory: str) -> str | None:
    path, _selected = QtWidgets.QFileDialog.getOpenFileName(
        parent,
        "Select prm.project.json",
        start_directory,
        "Project mapping (prm.project.json);;JSON files (*.json);;All files (*)",
    )
    return path or None


def _choose_model(parent: object, logical_ids: list[str]) -> str | None:
    model, accepted = QtWidgets.QInputDialog.getItem(
        parent,
        "Select project model",
        "Model logical ID",
        logical_ids,
        0,
        False,
    )
    if not accepted:
        return None
    return str(model)


class CaptureCommand:
    """Open the four-tab capture panel for the active project source."""

    def GetResources(self) -> dict[str, str]:
        return {
            "Pixmap": _icon_path(),
            "MenuText": "Capture Project…",
            "ToolTip": "Capture the active project source into Parametron outputs",
        }

    def IsActive(self) -> bool:
        try:
            import FreeCADGui

            return FreeCADGui.ActiveDocument is not None
        except Exception:
            return False

    def Activated(self) -> None:
        import FreeCAD

        document = FreeCAD.ActiveDocument
        if document is None:
            QtWidgets.QMessageBox.warning(
                None,
                "Parametron Capture",
                "Open the project source document before capturing.",
            )
            return

        start_directory = ""
        file_name = getattr(document, "FileName", "")
        if isinstance(file_name, str) and file_name:
            start_directory = os.path.dirname(file_name)

        mapping_path = _choose_project(None, start_directory)
        if mapping_path is None:
            return

        try:
            context = load_project_context(mapping_path)
        except CaptureProjectError as exc:
            QtWidgets.QMessageBox.critical(None, "Invalid project mapping", str(exc))
            return

        logical_ids = [model.logical_id for model in context.models]
        if not logical_ids:
            QtWidgets.QMessageBox.critical(
                None,
                "Invalid project mapping",
                "The project mapping declares no models.",
            )
            return
        if len(logical_ids) == 1:
            logical_id = logical_ids[0]
        else:
            chosen = _choose_model(None, logical_ids)
            if chosen is None:
                return
            logical_id = chosen

        try:
            model = resolve_selected_model(context, logical_id)
            source_path = resolve_model_source_path(context, model)
            verify_active_source(document, source_path)
            discovery = discover_capture_candidates(document)
            semantic_selection = load_semantic_selection(
                context,
                discovery,
                cad_system_min_version=_freecad_version(),
            )
            session = CaptureSession(
                context=context,
                model=model,
                discovery=discovery,
                semantic_selection=semantic_selection,
            )
        except (
            CaptureError,
            CaptureDiscoveryError,
            CaptureOrchestrationError,
            SemanticMapError,
            CaptureSourceError,
            OSError,
            ValueError,
        ) as exc:
            QtWidgets.QMessageBox.critical(None, "Capture setup failed", str(exc))
            return

        panel = CapturePanel(session)
        panel.exec_()


__all__ = ["CaptureCommand"]
