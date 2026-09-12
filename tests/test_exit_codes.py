from __future__ import annotations

import importlib
import sys
import unittest
from unittest import mock


class ExitCodesTaxonomyImportTests(unittest.TestCase):
    def test_exit_codes_module_imports_without_freecad(self) -> None:
        original_import = __import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "FreeCAD":
                raise AssertionError("FreeCAD must not be imported during exit_codes import")
            return original_import(name, globals, locals, fromlist, level)

        sys.modules.pop("parametron_freecad.runtime.exit_codes", None)
        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module("parametron_freecad.runtime.exit_codes")

        self.assertIsNotNone(module)

    def test_runtime_package_imports_without_freecad(self) -> None:
        original_import = __import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "FreeCAD":
                raise AssertionError("FreeCAD must not be imported during runtime import")
            return original_import(name, globals, locals, fromlist, level)

        sys.modules.pop("parametron_freecad.runtime", None)
        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module("parametron_freecad.runtime")

        self.assertIsNotNone(module)


class ExitCodeConstantValueTests(unittest.TestCase):
    def setUp(self) -> None:
        from parametron_freecad.runtime import exit_codes
        self.exit_codes = exit_codes

    def test_success_exit_code_is_zero(self) -> None:
        self.assertEqual(self.exit_codes.SUCCESS_EXIT_CODE, 0)

    def test_freecad_unavailable_exit_code_is_two(self) -> None:
        self.assertEqual(self.exit_codes.FREECAD_UNAVAILABLE_EXIT_CODE, 2)

    def test_argument_error_exit_code_is_64(self) -> None:
        self.assertEqual(self.exit_codes.ARGUMENT_ERROR_EXIT_CODE, 64)

    def test_execution_failure_exit_code_is_70(self) -> None:
        self.assertEqual(self.exit_codes.EXECUTION_FAILURE_EXIT_CODE, 70)


class ExitCodeDataclassTests(unittest.TestCase):
    def setUp(self) -> None:
        from parametron_freecad.runtime.exit_codes import ExitCode
        self.ExitCode = ExitCode

    def test_exit_code_is_frozen(self) -> None:
        ec = self.ExitCode(name="test", code=99, description="test entry")
        with self.assertRaises((AttributeError, TypeError)):
            ec.code = 0  # type: ignore[misc]

    def test_exit_code_equality_by_value(self) -> None:
        a = self.ExitCode(name="x", code=1, description="d")
        b = self.ExitCode(name="x", code=1, description="d")
        self.assertEqual(a, b)

    def test_exit_code_inequality_on_different_code(self) -> None:
        a = self.ExitCode(name="x", code=1, description="d")
        b = self.ExitCode(name="x", code=2, description="d")
        self.assertNotEqual(a, b)


class ExitCodeTaxonomyTests(unittest.TestCase):
    def setUp(self) -> None:
        from parametron_freecad.runtime import exit_codes
        self.exit_codes = exit_codes

    def test_taxonomy_has_four_entries(self) -> None:
        self.assertEqual(len(self.exit_codes.EXIT_CODE_TAXONOMY), 4)

    def test_taxonomy_contains_success_entry(self) -> None:
        codes = {e.code for e in self.exit_codes.EXIT_CODE_TAXONOMY}
        self.assertIn(0, codes)

    def test_taxonomy_contains_freecad_unavailable_entry(self) -> None:
        codes = {e.code for e in self.exit_codes.EXIT_CODE_TAXONOMY}
        self.assertIn(2, codes)

    def test_taxonomy_contains_argument_error_entry(self) -> None:
        codes = {e.code for e in self.exit_codes.EXIT_CODE_TAXONOMY}
        self.assertIn(64, codes)

    def test_taxonomy_contains_execution_failure_entry(self) -> None:
        codes = {e.code for e in self.exit_codes.EXIT_CODE_TAXONOMY}
        self.assertIn(70, codes)

    def test_taxonomy_does_not_contain_obsolete_code_3(self) -> None:
        codes = {e.code for e in self.exit_codes.EXIT_CODE_TAXONOMY}
        self.assertNotIn(3, codes)

    def test_taxonomy_entry_names_are_stable(self) -> None:
        names = {e.name for e in self.exit_codes.EXIT_CODE_TAXONOMY}
        self.assertIn("success", names)
        self.assertIn("freecad_unavailable", names)
        self.assertIn("invalid_arguments", names)
        self.assertIn("execute_failure", names)

    def test_taxonomy_is_tuple(self) -> None:
        self.assertIsInstance(self.exit_codes.EXIT_CODE_TAXONOMY, tuple)


class CodeNameFunctionTests(unittest.TestCase):
    def setUp(self) -> None:
        from parametron_freecad.runtime.exit_codes import code_name
        self.code_name = code_name

    def test_code_name_for_0_is_success(self) -> None:
        self.assertEqual(self.code_name(0), "success")

    def test_code_name_for_2_is_freecad_unavailable(self) -> None:
        self.assertEqual(self.code_name(2), "freecad_unavailable")

    def test_code_name_for_64_is_invalid_arguments(self) -> None:
        self.assertEqual(self.code_name(64), "invalid_arguments")

    def test_code_name_for_70_is_execute_failure(self) -> None:
        self.assertEqual(self.code_name(70), "execute_failure")

    def test_code_name_for_unknown_returns_none(self) -> None:
        self.assertIsNone(self.code_name(99))

    def test_code_name_for_3_returns_none(self) -> None:
        self.assertIsNone(self.code_name(3))


class RuntimePackageExportTests(unittest.TestCase):
    def setUp(self) -> None:
        from parametron_freecad import runtime
        self.runtime = runtime

    def test_runtime_exports_success_exit_code(self) -> None:
        self.assertEqual(self.runtime.SUCCESS_EXIT_CODE, 0)

    def test_runtime_exports_freecad_unavailable_exit_code(self) -> None:
        self.assertEqual(self.runtime.FREECAD_UNAVAILABLE_EXIT_CODE, 2)

    def test_runtime_exports_argument_error_exit_code(self) -> None:
        self.assertEqual(self.runtime.ARGUMENT_ERROR_EXIT_CODE, 64)

    def test_runtime_exports_execution_failure_exit_code(self) -> None:
        self.assertEqual(self.runtime.EXECUTION_FAILURE_EXIT_CODE, 70)

    def test_runtime_exports_exit_code_taxonomy(self) -> None:
        self.assertIsNotNone(self.runtime.EXIT_CODE_TAXONOMY)
        self.assertEqual(len(self.runtime.EXIT_CODE_TAXONOMY), 4)

    def test_runtime_exports_exit_code_class(self) -> None:
        self.assertIsNotNone(self.runtime.ExitCode)

    def test_runtime_exports_code_name_function(self) -> None:
        self.assertEqual(self.runtime.code_name(0), "success")

    def test_runtime_exports_match_taxonomy_module(self) -> None:
        from parametron_freecad.runtime import exit_codes
        self.assertEqual(self.runtime.SUCCESS_EXIT_CODE, exit_codes.SUCCESS_EXIT_CODE)
        self.assertEqual(self.runtime.FREECAD_UNAVAILABLE_EXIT_CODE, exit_codes.FREECAD_UNAVAILABLE_EXIT_CODE)
        self.assertEqual(self.runtime.ARGUMENT_ERROR_EXIT_CODE, exit_codes.ARGUMENT_ERROR_EXIT_CODE)
        self.assertEqual(self.runtime.EXECUTION_FAILURE_EXIT_CODE, exit_codes.EXECUTION_FAILURE_EXIT_CODE)


class HeadlessCompatibilityAliasTests(unittest.TestCase):
    def setUp(self) -> None:
        from parametron_freecad.runtime import headless
        self.headless = headless

    def test_headless_execution_failure_exit_code_is_70(self) -> None:
        self.assertEqual(self.headless.EXECUTION_FAILURE_EXIT_CODE, 70)

    def test_headless_freecad_unavailable_exit_code_is_2(self) -> None:
        self.assertEqual(self.headless.FREECAD_UNAVAILABLE_EXIT_CODE, 2)

    def test_headless_argument_error_exit_code_is_64(self) -> None:
        self.assertEqual(self.headless.ARGUMENT_ERROR_EXIT_CODE, 64)

    def test_headless_success_exit_code_is_0(self) -> None:
        self.assertEqual(self.headless.SUCCESS_EXIT_CODE, 0)

    def test_obsolete_not_implemented_exit_code_is_3(self) -> None:
        self.assertEqual(self.headless.EXECUTION_NOT_IMPLEMENTED_EXIT_CODE, 3)

    def test_execution_failure_exit_code_differs_from_obsolete(self) -> None:
        self.assertNotEqual(
            self.headless.EXECUTION_FAILURE_EXIT_CODE,
            self.headless.EXECUTION_NOT_IMPLEMENTED_EXIT_CODE,
        )


if __name__ == "__main__":
    unittest.main()
