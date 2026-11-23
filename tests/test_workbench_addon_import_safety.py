"""Import-safety and artifact tests for the Parametron FreeCAD workbench.

These tests prove that the GUI-free workbench state and session import without
FreeCAD, FreeCADGui, or Qt, that the headless ``Init.py`` bootstrap is safe, and
that the add-on metadata and GUI-layer boundaries are valid.
"""

from __future__ import annotations

import ast
import importlib
import os
import runpy
import sys
import types
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKBENCH_ROOT = REPOSITORY_ROOT / "workbench"
PACKAGE_ROOT = WORKBENCH_ROOT / "parametron_workbench"

if str(WORKBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKBENCH_ROOT))

_GUARDED_ROOTS = {
    "FreeCAD",
    "FreeCADGui",
    "Part",
    "freecad",
    "PySide",
    "PySide2",
    "PySide6",
    "shiboken6",
}

_GUI_FREE_MODULES = (
    PACKAGE_ROOT / "__init__.py",
    PACKAGE_ROOT / "state.py",
    PACKAGE_ROOT / "session.py",
    PACKAGE_ROOT / "selection.py",
)


class WorkbenchImportSafetyTests(unittest.TestCase):
    def test_gui_free_package_imports_without_freecad_or_qt(self) -> None:
        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            root = name.split(".", 1)[0]
            if root in _GUARDED_ROOTS:
                raise AssertionError(f"{name} must not be imported")
            return real_import(name, *args, **kwargs)

        for module_name in tuple(sys.modules):
            if module_name == "parametron_workbench" or module_name.startswith(
                "parametron_workbench."
            ):
                sys.modules.pop(module_name, None)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module("parametron_workbench")
            importlib.import_module("parametron_workbench.state")
            importlib.import_module("parametron_workbench.session")
            importlib.import_module("parametron_workbench.selection")

        self.assertIsInstance(module, types.ModuleType)
        for guarded in _GUARDED_ROOTS:
            self.assertNotIn(guarded, sys.modules)
        for name in (
            "CapturePanelState",
            "CaptureSession",
            "CaptureTab",
            "build_default_semantic_selection",
            "load_semantic_selection",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(module, name), f"missing {name}")

    def test_gui_free_sources_do_not_import_freecad_or_qt(self) -> None:
        for source_path in _GUI_FREE_MODULES:
            with self.subTest(source=source_path.name):
                tree = ast.parse(
                    source_path.read_text(encoding="utf-8"), filename=str(source_path)
                )
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertNotIn(
                                alias.name.split(".", 1)[0],
                                _GUARDED_ROOTS,
                                f"{source_path.name} imports {alias.name}",
                            )
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        self.assertNotIn(
                            node.module.split(".", 1)[0],
                            _GUARDED_ROOTS,
                            f"{source_path.name} imports from {node.module}",
                        )

    def test_init_py_is_headless_safe_and_bootstraps_paths(self) -> None:
        init_path = WORKBENCH_ROOT / "Init.py"
        original_path = list(sys.path)
        try:
            runpy.run_path(str(init_path), run_name="__parametron_init__")
            self.assertIn(str(WORKBENCH_ROOT), sys.path)
            self.assertIn(str(REPOSITORY_ROOT), sys.path)
        finally:
            sys.path[:] = original_path

    def test_gui_layer_is_the_only_freecad_gui_importer(self) -> None:
        gui_modules = {
            "InitGui.py",
            "parametron_workbench/commands.py",
            "parametron_workbench/panel.py",
            "parametron_workbench/qt.py",
            "parametron_workbench/workbench.py",
        }
        for source_path in sorted(WORKBENCH_ROOT.rglob("*.py")):
            relative = str(source_path.relative_to(WORKBENCH_ROOT))
            if relative in gui_modules:
                continue
            tree = ast.parse(
                source_path.read_text(encoding="utf-8"), filename=str(source_path)
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    with self.subTest(source=relative, imported=name):
                        self.assertNotIn(
                            name.split(".", 1)[0],
                            _GUARDED_ROOTS,
                            f"{relative} must not import {name}",
                        )


class WorkbenchArtifactTests(unittest.TestCase):
    def test_package_xml_is_valid_freecad_metadata(self) -> None:
        tree = ET.parse(WORKBENCH_ROOT / "package.xml")
        root = tree.getroot()
        namespace = {"pkg": "https://wiki.freecad.org/Package_Metadata"}
        self.assertEqual(root.tag.split("}")[-1], "package")

        name = root.find("pkg:name", namespace)
        version = root.find("pkg:version", namespace)
        license_element = root.find("pkg:license", namespace)
        classname = root.find("pkg:content/pkg:workbench/pkg:classname", namespace)
        icon = root.find("pkg:content/pkg:workbench/pkg:icon", namespace)

        self.assertIsNotNone(name)
        self.assertEqual(name.text, "Parametron")
        self.assertIsNotNone(version)
        self.assertTrue(version.text)
        self.assertIsNotNone(license_element)
        self.assertEqual(license_element.text, "AGPL-3.0-or-later")
        self.assertIsNotNone(classname)
        self.assertEqual(classname.text, "ParametronWorkbench")
        self.assertIsNotNone(icon)
        self.assertTrue((WORKBENCH_ROOT / icon.text).is_file())

    def test_addon_artifacts_exist(self) -> None:
        for relative in (
            "Init.py",
            "InitGui.py",
            "package.xml",
            "resources/parametron.svg",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((WORKBENCH_ROOT / relative).is_file())

    def test_icon_is_well_formed_svg(self) -> None:
        tree = ET.parse(WORKBENCH_ROOT / "resources" / "parametron.svg")
        self.assertEqual(tree.getroot().tag.split("}")[-1], "svg")

    def test_gui_modules_compile(self) -> None:
        for relative in (
            "InitGui.py",
            "parametron_workbench/commands.py",
            "parametron_workbench/panel.py",
            "parametron_workbench/qt.py",
            "parametron_workbench/workbench.py",
        ):
            with self.subTest(relative=relative):
                source = (WORKBENCH_ROOT / relative).read_text(encoding="utf-8")
                compile(source, relative, "exec")


class WorkbenchGuiSmokeTests(unittest.TestCase):
    def test_registers_workbench_when_gui_is_available(self) -> None:
        if os.environ.get("PARAMETRON_FREECAD_GUI") != "1":
            self.skipTest("set PARAMETRON_FREECAD_GUI=1 to run GUI smoke")
        try:
            import FreeCADGui  # noqa: F401
        except Exception as exc:  # pragma: no cover - GUI-only
            self.skipTest(f"FreeCADGui unavailable: {exc}")

        import parametron_workbench.workbench as workbench_module

        instance = workbench_module.ParametronWorkbench()
        self.assertEqual(instance.GetClassName(), "Gui::PythonWorkbench")


if __name__ == "__main__":
    unittest.main()
