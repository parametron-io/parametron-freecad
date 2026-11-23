"""Import-safety tests for the GUI-free capture core."""

from __future__ import annotations

import ast
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import parametron_freecad.capture as capture
from parametron_freecad.capture import (
    CaptureContractError,
    CaptureError,
    CaptureIdPolicyError,
    CaptureNamePolicyError,
    CaptureWriteError,
)

_GUARDED_ROOTS = {"FreeCAD", "FreeCADGui", "Part", "freecad"}
_CAPTURE_PACKAGE_DIR = Path(capture.__file__).resolve().parent


class CaptureImportSafetyTests(unittest.TestCase):
    def test_importing_capture_does_not_import_freecad(self) -> None:
        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            root = name.split(".", 1)[0]
            if root in _GUARDED_ROOTS:
                raise AssertionError(f"{name} must not be imported")
            return real_import(name, *args, **kwargs)

        for module_name in tuple(sys.modules):
            if module_name == "parametron_freecad.capture" or module_name.startswith(
                "parametron_freecad.capture."
            ):
                sys.modules.pop(module_name, None)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module("parametron_freecad.capture")

        self.assertIsInstance(module, types.ModuleType)
        for guarded in _GUARDED_ROOTS:
            self.assertNotIn(guarded, sys.modules)

    def test_capture_sources_do_not_import_freecad_modules(self) -> None:
        for source_path in sorted(_CAPTURE_PACKAGE_DIR.glob("*.py")):
            with self.subTest(source=source_path.name):
                tree = ast.parse(
                    source_path.read_text(encoding="utf-8"),
                    filename=str(source_path),
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

    def test_error_classes_are_distinct_and_typed(self) -> None:
        self.assertTrue(issubclass(CaptureContractError, CaptureError))
        self.assertTrue(issubclass(CaptureNamePolicyError, CaptureError))
        self.assertTrue(issubclass(CaptureIdPolicyError, CaptureError))
        self.assertFalse(issubclass(CaptureWriteError, CaptureError))
        self.assertTrue(issubclass(CaptureWriteError, OSError))

    def test_public_surface_is_available(self) -> None:
        for name in (
            "CaptureContractError",
            "CaptureDocument",
            "CaptureError",
            "CaptureIdPolicyError",
            "CaptureNamePolicyError",
            "CaptureWriteError",
            "canonical_capture_bytes",
            "canonical_capture_text",
            "generate_component_id",
            "generate_feature_id",
            "generate_group_owned_parameter_id",
            "generate_metadata_id",
            "generate_parameter_group_id",
            "generate_parameter_id",
            "generate_relationship_id",
            "validate_capture_document",
            "write_capture_document",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(capture, name), f"missing public name: {name}")


if __name__ == "__main__":
    unittest.main()
