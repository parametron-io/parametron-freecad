"""Parametron FreeCAD workbench GUI initialization.

FreeCAD executes this file only in GUI mode. It imports ``FreeCADGui`` through
the workbench layer and registers the Parametron workbench. The GUI-free capture
state and session remain importable without this module.
"""

from __future__ import annotations

import os
import sys

_WORKBENCH_ROOT = os.path.dirname(os.path.realpath(__file__))
_REPOSITORY_ROOT = os.path.dirname(_WORKBENCH_ROOT)

for _path in (_REPOSITORY_ROOT, _WORKBENCH_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

del _path

import FreeCADGui  # noqa: E402
from parametron_workbench.workbench import ParametronWorkbench  # noqa: E402

FreeCADGui.addWorkbench(ParametronWorkbench())
