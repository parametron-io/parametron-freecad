"""Tests for Engine-to-FreeCAD required output-file contract metadata."""

from __future__ import annotations

import builtins
import importlib
import os
import sys
import types
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from unittest import mock

MODULE_NAME = "parametron_freecad.runtime.output_file_contract"


def _import_contract_module():
    return importlib.import_module(MODULE_NAME)


def _names(specs):
    return tuple(spec.name for spec in specs)


class OutputFileContractImportSafetyTests(unittest.TestCase):
    """The contract module must import under ordinary Python without FreeCAD."""

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
            raise AssertionError("output-file contract import must not open files")

        def guarded_getenv(*args, **kwargs):
            raise AssertionError("output-file contract import must not inspect env")

        class GuardedEnviron(dict):
            def __getitem__(self, key):
                raise AssertionError("output-file contract import must not read env")

            def get(self, key, default=None):
                raise AssertionError("output-file contract import must not read env")

        with mock.patch("builtins.open", side_effect=guarded_open):
            with mock.patch("os.getenv", side_effect=guarded_getenv):
                with mock.patch("os.environ", GuardedEnviron(os.environ)):
                    module = _import_contract_module()

        self.assertIsInstance(module, types.ModuleType)

    def test_import_does_not_import_execution_or_observation_writers(self) -> None:
        """Pure-metadata contract must not pull in writer or exporter modules."""
        writer_modules = [
            "parametron_freecad.execution.result_writer",
            "parametron_freecad.observation.observed_writer",
            "parametron_freecad.execution.csv_export",
            "parametron_freecad.execution.pdf_export",
            "parametron_freecad.execution.step_export",
        ]
        saved = {m: sys.modules.pop(m) for m in [MODULE_NAME, *writer_modules] if m in sys.modules}
        self.addCleanup(sys.modules.update, saved)

        _import_contract_module()

        for writer_module in writer_modules:
            with self.subTest(writer_module=writer_module):
                self.assertNotIn(writer_module, sys.modules)


class _OutputFileContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_contract_module()


class OutputFileContractVersionAndSingletonTests(_OutputFileContractTestCase):
    def test_output_file_contract_version_constant_is_exact(self) -> None:
        self.assertEqual(self.contract.OUTPUT_FILE_CONTRACT_VERSION, "1.0")

    def test_engine_output_file_contract_version_matches_module_constant(self) -> None:
        self.assertEqual(
            self.contract.ENGINE_OUTPUT_FILE_CONTRACT.version,
            self.contract.OUTPUT_FILE_CONTRACT_VERSION,
        )
        self.assertEqual(self.contract.ENGINE_OUTPUT_FILE_CONTRACT.version, "1.0")

    def test_output_file_spec_is_frozen_dataclass(self) -> None:
        self.assertTrue(is_dataclass(self.contract.OutputFileSpec))
        self.assertTrue(self.contract.OutputFileSpec.__dataclass_params__.frozen)

    def test_engine_output_file_contract_is_frozen_dataclass(self) -> None:
        self.assertTrue(is_dataclass(self.contract.EngineOutputFileContract))
        self.assertTrue(self.contract.EngineOutputFileContract.__dataclass_params__.frozen)

    def test_spec_mutation_raises_frozen_instance_error(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.contract.EXECUTE_RESULT_JSON_OUTPUT_SPEC.name = "mutated"  # type: ignore[misc]

    def test_contract_mutation_raises_frozen_instance_error(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.contract.ENGINE_OUTPUT_FILE_CONTRACT.version = "mutated"  # type: ignore[misc]

    def test_engine_output_file_contract_is_canonical_singleton_instance(self) -> None:
        self.assertIsInstance(
            self.contract.ENGINE_OUTPUT_FILE_CONTRACT,
            self.contract.EngineOutputFileContract,
        )


class OutputFileContractResultJsonSpecTests(_OutputFileContractTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.spec = self.contract.EXECUTE_RESULT_JSON_OUTPUT_SPEC

    def test_result_json_name_is_exact(self) -> None:
        self.assertEqual(self.spec.name, "result_json")

    def test_result_json_boundary_is_execute(self) -> None:
        self.assertEqual(self.spec.boundary, self.contract.OUTPUT_FILE_BOUNDARY_EXECUTE)
        self.assertEqual(self.spec.boundary, "execute")

    def test_result_json_required_and_status(self) -> None:
        self.assertTrue(self.spec.required)
        self.assertEqual(self.spec.status, self.contract.OUTPUT_FILE_STATUS_IMPLEMENTED)

    def test_result_json_role_is_runner_result(self) -> None:
        self.assertEqual(self.spec.role, self.contract.OUTPUT_FILE_ROLE_RUNNER_RESULT)
        self.assertEqual(self.spec.role, "runner_result")

    def test_result_json_canonical_filename_is_result_json(self) -> None:
        self.assertEqual(self.spec.canonical_filename, "result.json")

    def test_result_json_cardinality_is_one(self) -> None:
        self.assertEqual(self.spec.cardinality, self.contract.OUTPUT_FILE_CARDINALITY_ONE)
        self.assertEqual(self.spec.cardinality, "one")

    def test_result_json_path_source_references_execute_result_path(self) -> None:
        self.assertIn("result_path", self.spec.path_source)
        self.assertIn("--result", self.spec.path_source)

    def test_result_json_metadata_does_not_imply_verification_decisions(self) -> None:
        self.assertNotIn("verification_decision", self.spec.write_contract.lower())
        self.assertNotIn("verification_decision", self.spec.path_source.lower())


class OutputFileContractDeclaredArtifactsSpecTests(_OutputFileContractTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.spec = self.contract.EXECUTE_DECLARED_ARTIFACTS_OUTPUT_SPEC

    def test_declared_artifacts_name_is_exact(self) -> None:
        self.assertEqual(self.spec.name, "declared_artifacts")

    def test_declared_artifacts_boundary_is_execute(self) -> None:
        self.assertEqual(self.spec.boundary, self.contract.OUTPUT_FILE_BOUNDARY_EXECUTE)
        self.assertEqual(self.spec.boundary, "execute")

    def test_declared_artifacts_required_and_status(self) -> None:
        self.assertTrue(self.spec.required)
        self.assertEqual(self.spec.status, self.contract.OUTPUT_FILE_STATUS_IMPLEMENTED)

    def test_declared_artifacts_role_is_declared_artifact(self) -> None:
        self.assertEqual(self.spec.role, self.contract.OUTPUT_FILE_ROLE_DECLARED_ARTIFACT)
        self.assertEqual(self.spec.role, "declared_artifact")

    def test_declared_artifacts_canonical_filename_is_none(self) -> None:
        self.assertIsNone(self.spec.canonical_filename)

    def test_declared_artifacts_cardinality_is_per_manifest_output(self) -> None:
        self.assertEqual(
            self.spec.cardinality,
            self.contract.OUTPUT_FILE_CARDINALITY_PER_MANIFEST_OUTPUT,
        )
        self.assertEqual(self.spec.cardinality, "per_manifest_output")

    def test_declared_artifacts_path_source_references_manifest_outputs(self) -> None:
        self.assertIn("manifest outputs", self.spec.path_source)

    def test_declared_artifacts_payload_contract_references_all_supported_formats(self) -> None:
        for fmt in ("csv", "pdf", "step"):
            with self.subTest(fmt=fmt):
                self.assertIn(fmt, self.spec.payload_contract)

    def test_declared_artifacts_no_fixed_artifact_filename_implied(self) -> None:
        self.assertIsNone(self.spec.canonical_filename)


class OutputFileContractParametronObservedJsonSpecTests(_OutputFileContractTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.spec = self.contract.OBSERVE_PARAMETRON_OBSERVED_JSON_OUTPUT_SPEC

    def test_parametron_observed_json_name_is_exact(self) -> None:
        self.assertEqual(self.spec.name, "parametron_observed_json")

    def test_parametron_observed_json_boundary_is_observe(self) -> None:
        self.assertEqual(self.spec.boundary, self.contract.OUTPUT_FILE_BOUNDARY_OBSERVE)
        self.assertEqual(self.spec.boundary, "observe")

    def test_parametron_observed_json_required_and_status(self) -> None:
        self.assertTrue(self.spec.required)
        self.assertEqual(self.spec.status, self.contract.OUTPUT_FILE_STATUS_IMPLEMENTED)

    def test_parametron_observed_json_role_is_observed_output(self) -> None:
        self.assertEqual(self.spec.role, self.contract.OUTPUT_FILE_ROLE_OBSERVED_OUTPUT)
        self.assertEqual(self.spec.role, "observed_output")

    def test_parametron_observed_json_canonical_filename(self) -> None:
        self.assertEqual(self.spec.canonical_filename, "parametron.observed.json")

    def test_parametron_observed_json_cardinality_is_one(self) -> None:
        self.assertEqual(self.spec.cardinality, self.contract.OUTPUT_FILE_CARDINALITY_ONE)
        self.assertEqual(self.spec.cardinality, "one")

    def test_parametron_observed_json_path_source_references_output_directory(self) -> None:
        self.assertIn("output_directory", self.spec.path_source)
        self.assertIn("parametron.observed.json", self.spec.path_source)

    def test_parametron_observed_json_write_contract_excludes_cli_observation_mode(self) -> None:
        self.assertIn("no CLI observation mode is implied", self.spec.write_contract)

    def test_parametron_observed_json_write_contract_excludes_verification_decisions(self) -> None:
        self.assertIn("no verification decisions are written", self.spec.write_contract)


class OutputFileContractTupleGroupingTests(_OutputFileContractTestCase):
    def test_all_output_file_specs_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            _names(self.contract.ALL_OUTPUT_FILE_SPECS),
            ("result_json", "declared_artifacts", "parametron_observed_json"),
        )

    def test_required_output_file_specs_is_same_object_as_all(self) -> None:
        self.assertIs(
            self.contract.REQUIRED_OUTPUT_FILE_SPECS,
            self.contract.ALL_OUTPUT_FILE_SPECS,
        )

    def test_implemented_required_output_file_specs_is_same_object_as_all(self) -> None:
        self.assertIs(
            self.contract.IMPLEMENTED_REQUIRED_OUTPUT_FILE_SPECS,
            self.contract.ALL_OUTPUT_FILE_SPECS,
        )

    def test_planned_required_output_file_specs_is_empty_tuple(self) -> None:
        self.assertEqual(self.contract.PLANNED_REQUIRED_OUTPUT_FILE_SPECS, ())
        self.assertIsInstance(self.contract.PLANNED_REQUIRED_OUTPUT_FILE_SPECS, tuple)

    def test_execute_required_specs_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            _names(self.contract.EXECUTE_REQUIRED_OUTPUT_FILE_SPECS),
            ("result_json", "declared_artifacts"),
        )

    def test_observe_required_specs_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            _names(self.contract.OBSERVE_REQUIRED_OUTPUT_FILE_SPECS),
            ("parametron_observed_json",),
        )

    def test_output_file_canonical_names_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.OUTPUT_FILE_CANONICAL_NAMES,
            ("result.json", "parametron.observed.json"),
        )

    def test_declared_artifact_output_formats_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.DECLARED_ARTIFACT_OUTPUT_FORMATS,
            ("csv", "pdf", "step"),
        )

    def test_all_grouping_surfaces_are_tuples_not_lists(self) -> None:
        tuple_names = (
            "ALL_OUTPUT_FILE_SPECS",
            "REQUIRED_OUTPUT_FILE_SPECS",
            "IMPLEMENTED_REQUIRED_OUTPUT_FILE_SPECS",
            "PLANNED_REQUIRED_OUTPUT_FILE_SPECS",
            "EXECUTE_REQUIRED_OUTPUT_FILE_SPECS",
            "OBSERVE_REQUIRED_OUTPUT_FILE_SPECS",
            "OUTPUT_FILE_CANONICAL_NAMES",
            "DECLARED_ARTIFACT_OUTPUT_FORMATS",
        )
        for tuple_name in tuple_names:
            with self.subTest(tuple_name=tuple_name):
                self.assertIsInstance(getattr(self.contract, tuple_name), tuple)

    def test_singleton_reuses_exact_tuple_objects(self) -> None:
        singleton = self.contract.ENGINE_OUTPUT_FILE_CONTRACT
        self.assertIs(singleton.output_files, self.contract.ALL_OUTPUT_FILE_SPECS)
        self.assertIs(
            singleton.required_output_files,
            self.contract.REQUIRED_OUTPUT_FILE_SPECS,
        )
        self.assertIs(
            singleton.implemented_required_output_files,
            self.contract.IMPLEMENTED_REQUIRED_OUTPUT_FILE_SPECS,
        )
        self.assertIs(
            singleton.planned_required_output_files,
            self.contract.PLANNED_REQUIRED_OUTPUT_FILE_SPECS,
        )
        self.assertIs(
            singleton.execute_required_output_files,
            self.contract.EXECUTE_REQUIRED_OUTPUT_FILE_SPECS,
        )
        self.assertIs(
            singleton.observe_required_output_files,
            self.contract.OBSERVE_REQUIRED_OUTPUT_FILE_SPECS,
        )
        self.assertIs(
            singleton.canonical_output_filenames,
            self.contract.OUTPUT_FILE_CANONICAL_NAMES,
        )
        self.assertIs(
            singleton.declared_artifact_formats,
            self.contract.DECLARED_ARTIFACT_OUTPUT_FORMATS,
        )


class OutputFileContractCanonicalDriftTests(_OutputFileContractTestCase):
    def test_result_json_canonical_filename_matches_file_argument_contract_constant(self) -> None:
        file_argument_contract = importlib.import_module(
            "parametron_freecad.runtime.file_argument_contract"
        )
        self.assertEqual(
            self.contract.EXECUTE_RESULT_JSON_OUTPUT_SPEC.canonical_filename,
            file_argument_contract.RESULT_JSON_FILENAME,
        )

    def test_parametron_observed_json_canonical_filename_matches_observed_contract(self) -> None:
        observed_contract = importlib.import_module(
            "parametron_freecad.observation.observed_contract"
        )
        self.assertEqual(
            self.contract.OBSERVE_PARAMETRON_OBSERVED_JSON_OUTPUT_SPEC.canonical_filename,
            observed_contract.PARAMETRON_OBSERVED_FILENAME,
        )

    def test_declared_artifact_formats_match_supported_output_formats(self) -> None:
        manifest_contract = importlib.import_module(
            "parametron_freecad.execution.manifest_contract"
        )
        self.assertEqual(
            self.contract.DECLARED_ARTIFACT_OUTPUT_FORMATS,
            manifest_contract.SUPPORTED_OUTPUT_FORMATS,
        )

    def test_engine_output_file_contract_declared_artifact_formats_matches_supported_formats(
        self,
    ) -> None:
        manifest_contract = importlib.import_module(
            "parametron_freecad.execution.manifest_contract"
        )
        self.assertEqual(
            self.contract.ENGINE_OUTPUT_FILE_CONTRACT.declared_artifact_formats,
            manifest_contract.SUPPORTED_OUTPUT_FORMATS,
        )

    def test_output_file_canonical_names_uses_same_result_json_filename(self) -> None:
        file_argument_contract = importlib.import_module(
            "parametron_freecad.runtime.file_argument_contract"
        )
        self.assertIn(
            file_argument_contract.RESULT_JSON_FILENAME,
            self.contract.OUTPUT_FILE_CANONICAL_NAMES,
        )

    def test_output_file_canonical_names_uses_same_parametron_observed_filename(self) -> None:
        observed_contract = importlib.import_module(
            "parametron_freecad.observation.observed_contract"
        )
        self.assertIn(
            observed_contract.PARAMETRON_OBSERVED_FILENAME,
            self.contract.OUTPUT_FILE_CANONICAL_NAMES,
        )


class OutputFileContractNegativeBoundaryTests(_OutputFileContractTestCase):
    def test_module_all_does_not_expose_observation_cli_mode_names(self) -> None:
        forbidden_terms = ("cli_mode", "observation_cli", "cli_observation")
        for name in self.contract.__all__:
            name_lower = name.lower()
            for term in forbidden_terms:
                with self.subTest(name=name, term=term):
                    self.assertNotIn(term, name_lower)

    def test_module_all_does_not_expose_combined_mode_names(self) -> None:
        for name in self.contract.__all__:
            with self.subTest(name=name):
                self.assertNotIn("combined_mode", name.lower())

    def test_module_all_does_not_expose_verification_decision_names(self) -> None:
        for name in self.contract.__all__:
            with self.subTest(name=name):
                self.assertNotIn("verification_decision", name.lower())

    def test_module_all_does_not_expose_sha256_computation_names(self) -> None:
        for name in self.contract.__all__:
            with self.subTest(name=name):
                self.assertNotIn("sha256", name.lower())

    def test_module_all_does_not_expose_gui_capture_names(self) -> None:
        forbidden_terms = ("gui_capture", "capture_behavior")
        for name in self.contract.__all__:
            name_lower = name.lower()
            for term in forbidden_terms:
                with self.subTest(name=name, term=term):
                    self.assertNotIn(term, name_lower)

    def test_observe_spec_write_contract_explicitly_excludes_cli_observation_mode(
        self,
    ) -> None:
        spec = self.contract.OBSERVE_PARAMETRON_OBSERVED_JSON_OUTPUT_SPEC
        self.assertIn("no CLI observation mode is implied", spec.write_contract)

    def test_observe_spec_write_contract_explicitly_excludes_verification_decisions(
        self,
    ) -> None:
        spec = self.contract.OBSERVE_PARAMETRON_OBSERVED_JSON_OUTPUT_SPEC
        self.assertIn("no verification decisions are written", spec.write_contract)


class OutputFileContractAllPublicApiTests(_OutputFileContractTestCase):
    def test_all_exports_include_expected_public_names(self) -> None:
        expected = {
            # dataclasses
            "OutputFileSpec",
            "EngineOutputFileContract",
            # version
            "OUTPUT_FILE_CONTRACT_VERSION",
            # role constants
            "OUTPUT_FILE_ROLE_RUNNER_RESULT",
            "OUTPUT_FILE_ROLE_DECLARED_ARTIFACT",
            "OUTPUT_FILE_ROLE_OBSERVED_OUTPUT",
            # boundary constants
            "OUTPUT_FILE_BOUNDARY_EXECUTE",
            "OUTPUT_FILE_BOUNDARY_OBSERVE",
            # status constants
            "OUTPUT_FILE_STATUS_IMPLEMENTED",
            "OUTPUT_FILE_STATUS_PLANNED",
            # cardinality constants
            "OUTPUT_FILE_CARDINALITY_ONE",
            "OUTPUT_FILE_CARDINALITY_PER_MANIFEST_OUTPUT",
            # spec constants
            "EXECUTE_RESULT_JSON_OUTPUT_SPEC",
            "EXECUTE_DECLARED_ARTIFACTS_OUTPUT_SPEC",
            "OBSERVE_PARAMETRON_OBSERVED_JSON_OUTPUT_SPEC",
            # tuple groupings
            "ALL_OUTPUT_FILE_SPECS",
            "REQUIRED_OUTPUT_FILE_SPECS",
            "IMPLEMENTED_REQUIRED_OUTPUT_FILE_SPECS",
            "PLANNED_REQUIRED_OUTPUT_FILE_SPECS",
            "EXECUTE_REQUIRED_OUTPUT_FILE_SPECS",
            "OBSERVE_REQUIRED_OUTPUT_FILE_SPECS",
            "OUTPUT_FILE_CANONICAL_NAMES",
            "DECLARED_ARTIFACT_OUTPUT_FORMATS",
            # singleton
            "ENGINE_OUTPUT_FILE_CONTRACT",
        }
        self.assertTrue(expected.issubset(set(self.contract.__all__)))

    def test_all_exports_exist_on_module(self) -> None:
        for public_name in self.contract.__all__:
            with self.subTest(public_name=public_name):
                self.assertTrue(hasattr(self.contract, public_name))

    def test_all_does_not_expose_internal_import_names(self) -> None:
        internal_names = {
            "SUPPORTED_OUTPUT_FORMATS",
            "PARAMETRON_OBSERVED_FILENAME",
            "RESULT_JSON_FILENAME",
        }
        for internal_name in internal_names:
            with self.subTest(internal_name=internal_name):
                self.assertNotIn(internal_name, self.contract.__all__)


if __name__ == "__main__":
    unittest.main()
