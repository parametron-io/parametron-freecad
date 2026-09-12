"""Tests for required Engine/CLI file-argument contract metadata."""

from __future__ import annotations

import builtins
import importlib
import os
import sys
import types
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from unittest import mock

MODULE_NAME = "parametron_freecad.runtime.file_argument_contract"


def _import_contract_module():
    return importlib.import_module(MODULE_NAME)


def _names(specs):
    return tuple(spec.name for spec in specs)


def _spec_keys(specs):
    return tuple((spec.boundary, spec.name) for spec in specs)


class FileArgumentContractImportSafetyTests(unittest.TestCase):
    def test_import_succeeds_without_freecad_modules(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_contract_module()

        self.assertIsInstance(module, types.ModuleType)
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)

    def test_import_does_not_touch_filesystem_or_environment(self) -> None:
        previous = sys.modules.pop(MODULE_NAME, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_open(*args, **kwargs):
            raise AssertionError("file-argument contract import must not open files")

        def guarded_getenv(*args, **kwargs):
            raise AssertionError("file-argument contract import must not inspect env")

        class GuardedEnviron(dict):
            def __getitem__(self, key):
                raise AssertionError("file-argument contract import must not read env")

            def get(self, key, default=None):
                raise AssertionError("file-argument contract import must not read env")

        with mock.patch("builtins.open", side_effect=guarded_open):
            with mock.patch("os.getenv", side_effect=guarded_getenv):
                with mock.patch("os.environ", GuardedEnviron(os.environ)):
                    module = _import_contract_module()

        self.assertIsInstance(module, types.ModuleType)


class _FileArgumentContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_contract_module()


class FileArgumentContractPublicSurfaceTests(_FileArgumentContractTestCase):
    def test_public_constants_and_singleton_version_are_exact(self) -> None:
        self.assertEqual(self.contract.FILE_ARGUMENT_CONTRACT_VERSION, "1.0")
        self.assertEqual(self.contract.RESULT_JSON_FILENAME, "result.json")
        self.assertEqual(self.contract.ENGINE_FILE_ARGUMENT_CONTRACT.version, "1.0")

    def test_all_exports_exist_and_include_expected_public_names(self) -> None:
        expected_exports = {
            "ALL_FILE_ARGUMENT_SPECS",
            "ENGINE_EXECUTE_REQUIRED_FILE_ARGUMENT_SPECS",
            "ENGINE_FILE_ARGUMENT_CONTRACT",
            "ENGINE_OBSERVE_REQUIRED_FILE_ARGUMENT_SPECS",
            "EngineFileArgumentContract",
            "EXECUTE_CLI_REQUIRED_FILE_ARGUMENT_SPECS",
            "EXECUTE_CLI_REFERENCE_TRAVERSAL_OUTPUT_SPEC",
            "EXECUTE_CLI_REFERENCE_TRAVERSAL_REQUEST_SPEC",
            "FILE_ARGUMENT_BOUNDARY_ENGINE_EXECUTE",
            "FILE_ARGUMENT_BOUNDARY_ENGINE_OBSERVE",
            "FILE_ARGUMENT_BOUNDARY_EXECUTE_CLI",
            "FILE_ARGUMENT_CANONICAL_NAMES",
            "FILE_ARGUMENT_CONTRACT_VERSION",
            "FILE_ARGUMENT_ROLE_CONTEXT_PATH",
            "FILE_ARGUMENT_ROLE_INPUT_FILE",
            "FILE_ARGUMENT_ROLE_OUTPUT_DIRECTORY",
            "FILE_ARGUMENT_ROLE_OUTPUT_PATH",
            "FILE_ARGUMENT_STATUS_IMPLEMENTED",
            "FILE_ARGUMENT_STATUS_PLANNED",
            "FileArgumentSpec",
            "IMPLEMENTED_REQUIRED_FILE_ARGUMENT_SPECS",
            "PLANNED_REQUIRED_FILE_ARGUMENT_SPECS",
            "REQUIRED_FILE_ARGUMENT_SPECS",
            "RESULT_JSON_FILENAME",
        }

        self.assertTrue(expected_exports.issubset(set(self.contract.__all__)))
        for public_name in self.contract.__all__:
            with self.subTest(public_name=public_name):
                self.assertTrue(hasattr(self.contract, public_name))


class FileArgumentContractImmutabilityTests(_FileArgumentContractTestCase):
    def test_contract_dataclasses_are_frozen(self) -> None:
        self.assertTrue(is_dataclass(self.contract.FileArgumentSpec))
        self.assertTrue(self.contract.FileArgumentSpec.__dataclass_params__.frozen)
        self.assertTrue(is_dataclass(self.contract.EngineFileArgumentContract))
        self.assertTrue(
            self.contract.EngineFileArgumentContract.__dataclass_params__.frozen
        )

    def test_spec_and_contract_instances_are_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.contract.EXECUTE_CLI_RESULT_SPEC.name = "mutated"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            self.contract.ENGINE_FILE_ARGUMENT_CONTRACT.version = "mutated"  # type: ignore[misc]

    def test_tuple_surfaces_are_tuples_not_lists(self) -> None:
        tuple_names = (
            "ALL_FILE_ARGUMENT_SPECS",
            "REQUIRED_FILE_ARGUMENT_SPECS",
            "IMPLEMENTED_REQUIRED_FILE_ARGUMENT_SPECS",
            "PLANNED_REQUIRED_FILE_ARGUMENT_SPECS",
            "EXECUTE_CLI_REQUIRED_FILE_ARGUMENT_SPECS",
            "ENGINE_EXECUTE_REQUIRED_FILE_ARGUMENT_SPECS",
            "ENGINE_OBSERVE_REQUIRED_FILE_ARGUMENT_SPECS",
            "FILE_ARGUMENT_CANONICAL_NAMES",
        )
        for tuple_name in tuple_names:
            with self.subTest(tuple_name=tuple_name):
                value = getattr(self.contract, tuple_name)
                self.assertIsInstance(value, tuple)
                self.assertNotIsInstance(value, list)


class FileArgumentContractBoundaryTests(_FileArgumentContractTestCase):
    def test_execute_cli_required_file_arguments_are_exact_and_ordered(self) -> None:
        specs = self.contract.EXECUTE_CLI_REQUIRED_FILE_ARGUMENT_SPECS
        self.assertEqual(_names(specs), ("working_copy", "manifest", "result"))

        expected = (
            (
                "working_copy",
                self.contract.FILE_ARGUMENT_ROLE_CONTEXT_PATH,
                "--working-copy",
                None,
                None,
                (
                    "The supplied existing directory is the authoritative "
                    "execution-instance root. All runtime file arguments and "
                    "manifest-resolved paths must remain contained beneath it. "
                    "The root name is not prescribed."
                ),
            ),
            (
                "manifest",
                self.contract.FILE_ARGUMENT_ROLE_INPUT_FILE,
                "--manifest",
                None,
                self.contract.EXPORT_MANIFEST_V1_FILENAME,
                "must be an existing file inside the working copy",
            ),
            (
                "result",
                self.contract.FILE_ARGUMENT_ROLE_OUTPUT_PATH,
                "--result",
                None,
                self.contract.RESULT_JSON_FILENAME,
                "must resolve inside the working copy; not created during argument validation",
            ),
        )

        for spec, expected_values in zip(specs, expected, strict=True):
            with self.subTest(spec=spec.name):
                name, role, cli_flag, invocation_field, filename, path_contract = (
                    expected_values
                )
                self.assertEqual(spec.name, name)
                self.assertEqual(
                    spec.boundary, self.contract.FILE_ARGUMENT_BOUNDARY_EXECUTE_CLI
                )
                self.assertTrue(spec.required)
                self.assertEqual(
                    spec.status, self.contract.FILE_ARGUMENT_STATUS_IMPLEMENTED
                )
                self.assertEqual(spec.role, role)
                self.assertEqual(spec.cli_flag, cli_flag)
                self.assertEqual(spec.invocation_field, invocation_field)
                self.assertEqual(spec.canonical_filename, filename)
                self.assertEqual(spec.path_contract, path_contract)
                self.assertTrue(spec.path_contract)

    def test_engine_execute_required_file_arguments_are_exact_and_ordered(self) -> None:
        specs = self.contract.ENGINE_EXECUTE_REQUIRED_FILE_ARGUMENT_SPECS
        self.assertEqual(_names(specs), ("working_copy", "manifest_path", "result_path"))

        expected = (
            (
                "working_copy",
                "working_copy",
                self.contract.FILE_ARGUMENT_ROLE_CONTEXT_PATH,
                None,
                "context directory path for execute invocation",
            ),
            (
                "manifest_path",
                "manifest_path",
                self.contract.FILE_ARGUMENT_ROLE_INPUT_FILE,
                self.contract.EXPORT_MANIFEST_V1_FILENAME,
                "input manifest file path for execute invocation",
            ),
            (
                "result_path",
                "result_path",
                self.contract.FILE_ARGUMENT_ROLE_OUTPUT_PATH,
                self.contract.RESULT_JSON_FILENAME,
                "output result file path for execute invocation",
            ),
        )

        for spec, expected_values in zip(specs, expected, strict=True):
            with self.subTest(spec=spec.name):
                name, invocation_field, role, filename, path_contract = expected_values
                self.assertEqual(spec.name, name)
                self.assertEqual(
                    spec.boundary, self.contract.FILE_ARGUMENT_BOUNDARY_ENGINE_EXECUTE
                )
                self.assertTrue(spec.required)
                self.assertEqual(
                    spec.status, self.contract.FILE_ARGUMENT_STATUS_IMPLEMENTED
                )
                self.assertEqual(spec.role, role)
                self.assertIsNone(spec.cli_flag)
                self.assertEqual(spec.invocation_field, invocation_field)
                self.assertEqual(spec.canonical_filename, filename)
                self.assertEqual(spec.path_contract, path_contract)

    def test_engine_observe_required_file_arguments_are_exact_and_ordered(self) -> None:
        specs = self.contract.ENGINE_OBSERVE_REQUIRED_FILE_ARGUMENT_SPECS
        self.assertEqual(_names(specs), ("working_copy_path", "output_directory"))

        working_copy, output_directory = specs
        self.assertEqual(working_copy.invocation_field, "working_copy_path")
        self.assertEqual(
            working_copy.role, self.contract.FILE_ARGUMENT_ROLE_CONTEXT_PATH
        )
        self.assertEqual(
            working_copy.status, self.contract.FILE_ARGUMENT_STATUS_IMPLEMENTED
        )
        self.assertIsNone(working_copy.cli_flag)
        self.assertIsNone(working_copy.canonical_filename)
        self.assertIn("caller-supplied context path metadata", working_copy.path_contract)
        self.assertIn("not validated or computed", working_copy.path_contract)
        self.assertNotIn("sha256", working_copy.path_contract.lower())

        self.assertEqual(output_directory.invocation_field, "output_directory")
        self.assertEqual(
            output_directory.role, self.contract.FILE_ARGUMENT_ROLE_OUTPUT_DIRECTORY
        )
        self.assertEqual(
            output_directory.status, self.contract.FILE_ARGUMENT_STATUS_IMPLEMENTED
        )
        self.assertIsNone(output_directory.cli_flag)
        self.assertEqual(
            output_directory.canonical_filename,
            self.contract.PARAMETRON_OBSERVED_FILENAME,
        )
        self.assertIn("output directory", output_directory.path_contract)

    def test_non_file_observation_fields_are_not_file_arguments(self) -> None:
        file_argument_names = {spec.name for spec in self.contract.ALL_FILE_ARGUMENT_SPECS}
        self.assertTrue(
            file_argument_names.isdisjoint(
                {"document", "verification_data", "working_copy_sha256"}
            )
        )

    def test_reference_traversal_metadata_distinguishes_cli_and_output_status(self) -> None:
        request = self.contract.EXECUTE_CLI_REFERENCE_TRAVERSAL_REQUEST_SPEC
        output = self.contract.EXECUTE_CLI_REFERENCE_TRAVERSAL_OUTPUT_SPEC

        self.assertFalse(request.required)
        self.assertEqual(request.status, self.contract.FILE_ARGUMENT_STATUS_IMPLEMENTED)
        self.assertEqual(request.role, self.contract.FILE_ARGUMENT_ROLE_INPUT_FILE)
        self.assertEqual(request.cli_flag, "--reference-traversal-request")
        self.assertEqual(request.invocation_field, "reference_traversal_request")
        self.assertEqual(
            request.canonical_filename,
            "parametron.reference-traversal-request.json",
        )
        self.assertIn("authoritative working copy", request.path_contract)
        self.assertIn("requires --output-dir", request.path_contract)
        self.assertIn("not loaded", request.path_contract)

        self.assertFalse(output.required)
        self.assertEqual(output.status, self.contract.FILE_ARGUMENT_STATUS_IMPLEMENTED)
        self.assertEqual(output.role, self.contract.FILE_ARGUMENT_ROLE_OUTPUT_PATH)
        self.assertIsNone(output.cli_flag)
        self.assertIsNone(output.invocation_field)
        self.assertEqual(
            output.canonical_filename, "parametron.reference-traversal.json"
        )
        self.assertIn("beneath the existing --output-dir", output.path_contract)
        self.assertIn("working copy", output.path_contract)
        self.assertIn("containment root", output.path_contract)
        self.assertIn("caller-created", output.path_contract)
        self.assertIn("not request-controlled", output.path_contract)

    def test_planned_verification_input_metadata_is_not_implemented(self) -> None:
        specs = self.contract.PLANNED_REQUIRED_FILE_ARGUMENT_SPECS
        self.assertEqual(_names(specs), ("verification_input",))

        spec = specs[0]
        self.assertEqual(spec.boundary, self.contract.FILE_ARGUMENT_BOUNDARY_ENGINE_OBSERVE)
        self.assertTrue(spec.required)
        self.assertEqual(spec.status, self.contract.FILE_ARGUMENT_STATUS_PLANNED)
        self.assertEqual(spec.role, self.contract.FILE_ARGUMENT_ROLE_INPUT_FILE)
        self.assertIsNone(spec.cli_flag)
        self.assertIsNone(spec.invocation_field)
        self.assertEqual(
            spec.canonical_filename, self.contract.PARAMETRON_VERIFICATION_FILENAME
        )
        self.assertIn("not yet supported", spec.path_contract)


class FileArgumentContractAggregateTests(_FileArgumentContractTestCase):
    def test_aggregate_tuple_groupings_are_exact_and_ordered(self) -> None:
        expected_keys = (
            ("execute_cli", "working_copy"),
            ("execute_cli", "manifest"),
            ("execute_cli", "result"),
            ("engine_execute", "working_copy"),
            ("engine_execute", "manifest_path"),
            ("engine_execute", "result_path"),
            ("engine_observe", "working_copy_path"),
            ("engine_observe", "output_directory"),
            ("engine_observe", "verification_input"),
        )

        self.assertEqual(_spec_keys(self.contract.ALL_FILE_ARGUMENT_SPECS), expected_keys)
        self.assertEqual(
            self.contract.REQUIRED_FILE_ARGUMENT_SPECS,
            self.contract.ALL_FILE_ARGUMENT_SPECS,
        )
        self.assertEqual(
            _names(self.contract.IMPLEMENTED_REQUIRED_FILE_ARGUMENT_SPECS),
            (
                "working_copy",
                "manifest",
                "result",
                "working_copy",
                "manifest_path",
                "result_path",
                "working_copy_path",
                "output_directory",
            ),
        )
        self.assertNotIn(
            "verification_input",
            _names(self.contract.IMPLEMENTED_REQUIRED_FILE_ARGUMENT_SPECS),
        )
        self.assertEqual(
            _names(self.contract.PLANNED_REQUIRED_FILE_ARGUMENT_SPECS),
            ("verification_input",),
        )

    def test_canonical_filenames_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.FILE_ARGUMENT_CANONICAL_NAMES,
            (
                "export_manifest_v1.json",
                "result.json",
                "parametron.verification.json",
                "parametron.observed.json",
                "parametron.reference-traversal-request.json",
                "parametron.reference-traversal.json",
            ),
        )

    def test_singleton_reuses_exact_tuple_objects(self) -> None:
        singleton = self.contract.ENGINE_FILE_ARGUMENT_CONTRACT
        self.assertIs(singleton.file_arguments, self.contract.ALL_FILE_ARGUMENT_SPECS)
        self.assertIs(
            singleton.required_file_arguments,
            self.contract.REQUIRED_FILE_ARGUMENT_SPECS,
        )
        self.assertIs(
            singleton.implemented_required_file_arguments,
            self.contract.IMPLEMENTED_REQUIRED_FILE_ARGUMENT_SPECS,
        )
        self.assertIs(
            singleton.planned_required_file_arguments,
            self.contract.PLANNED_REQUIRED_FILE_ARGUMENT_SPECS,
        )
        self.assertIs(
            singleton.execute_cli_required_file_arguments,
            self.contract.EXECUTE_CLI_REQUIRED_FILE_ARGUMENT_SPECS,
        )
        self.assertIs(
            singleton.engine_execute_required_file_arguments,
            self.contract.ENGINE_EXECUTE_REQUIRED_FILE_ARGUMENT_SPECS,
        )
        self.assertIs(
            singleton.engine_observe_required_file_arguments,
            self.contract.ENGINE_OBSERVE_REQUIRED_FILE_ARGUMENT_SPECS,
        )
        self.assertIs(
            singleton.canonical_file_contract_names,
            self.contract.FILE_ARGUMENT_CANONICAL_NAMES,
        )


class FileArgumentContractCanonicalDriftTests(_FileArgumentContractTestCase):
    def test_canonical_filenames_match_existing_contract_modules(self) -> None:
        manifest_contract = importlib.import_module(
            "parametron_freecad.execution.manifest_contract"
        )
        verification_contract = importlib.import_module(
            "parametron_freecad.observation.verification_contract"
        )
        observed_contract = importlib.import_module(
            "parametron_freecad.observation.observed_contract"
        )

        self.assertEqual(
            self.contract.EXECUTE_CLI_MANIFEST_SPEC.canonical_filename,
            manifest_contract.EXPORT_MANIFEST_V1_FILENAME,
        )
        self.assertEqual(
            self.contract.ENGINE_EXECUTE_MANIFEST_PATH_SPEC.canonical_filename,
            manifest_contract.EXPORT_MANIFEST_V1_FILENAME,
        )
        self.assertEqual(
            self.contract.ENGINE_OBSERVE_VERIFICATION_INPUT_SPEC.canonical_filename,
            verification_contract.PARAMETRON_VERIFICATION_FILENAME,
        )
        self.assertEqual(
            self.contract.ENGINE_OBSERVE_OUTPUT_DIRECTORY_SPEC.canonical_filename,
            observed_contract.PARAMETRON_OBSERVED_FILENAME,
        )
        self.assertEqual(
            self.contract.EXECUTE_CLI_RESULT_SPEC.canonical_filename,
            self.contract.RESULT_JSON_FILENAME,
        )
        self.assertEqual(
            self.contract.ENGINE_EXECUTE_RESULT_PATH_SPEC.canonical_filename,
            self.contract.RESULT_JSON_FILENAME,
        )
