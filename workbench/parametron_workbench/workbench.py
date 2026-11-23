"""Parametron FreeCAD workbench registration.

This module is GUI-layer only and is imported by ``InitGui.py``. It registers
the Parametron workbench, toolbar, and capture command. Headless imports never
load this module.
"""

from __future__ import annotations

import os

import FreeCADGui


def _icon_path() -> str:
    workbench_directory = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    return os.path.join(workbench_directory, "resources", "parametron.svg")


class ParametronWorkbench(FreeCADGui.Workbench):
    """Parametron capture workbench shell."""

    MenuText = "Parametron"
    ToolTip = "Parametron capture: parts, features, parameters, and metadata"
    Icon = _icon_path()

    def Initialize(self) -> None:
        from parametron_workbench.commands import CaptureCommand

        self.commands = ["Parametron_Capture"]
        FreeCADGui.addCommand("Parametron_Capture", CaptureCommand())
        self.appendToolbar("Parametron", self.commands)
        self.appendMenu("Parametron", self.commands)

    def Activated(self) -> None:
        pass

    def Deactivated(self) -> None:
        pass

    def GetClassName(self) -> str:
        return "Gui::PythonWorkbench"


__all__ = ["ParametronWorkbench"]
