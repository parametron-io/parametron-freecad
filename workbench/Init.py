"""Parametron FreeCAD add-on module initialization (headless-safe).

FreeCAD executes this file at startup in both GUI and headless modes. It must
not import ``FreeCADGui`` or Qt. It only makes the repository package and the
workbench package importable. The GUI workbench is registered from
``InitGui.py``.
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
