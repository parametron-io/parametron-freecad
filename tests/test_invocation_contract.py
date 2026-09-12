"""Tests for the Engine-to-FreeCAD runtime invocation contract surface."""

from __future__ import annotations

import builtins
import importlib
import sys
import types
import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass
from unittest import mock

MODULE_NAME = "parametron_freecad.runtime.invocation_contract"

EXPECTED_NEGATIVE_BOUNDARIES = (
    "no_combined_execute_observe_runtime",
    "no_observation_cli_mode",
    "no_combined_execute_observe_cli_mode",
    "no_automatic_verification_file_loading",
    "no_working_copy_sha256_computation",
    "no_component_observation",
    "no_check_evaluation",
    "no_expected_vs_observed_comparison",
    "no_verification_decisions",
    "no_gui_capture_behavior",
    "no_broad_target_resolution",
)

FORBIDDEN_SUPPORTED_MODES = frozenset(
    {"verification", "verify", "gui", "capture", "combined"}
)


def _import_contract_module():
    return importlib.import_module(MODULE_NAME)


class InvocationContractImportSafetyTests(unittest.TestCase):
    """The contract module must import under ordinary Python without FreeCAD."""

    def test_import_succeeds_without_freecad(self) -> None:
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
            raise AssertionError("importing the contract must not open files")

        def guarded_getenv(*args, **kwargs):
            raise AssertionError("importing the contract must not inspect environment")

        with mock.patch("builtins.open", side_effect=guarded_open):
            with mock.patch("os.getenv", side_effect=guarded_getenv):
                module = _import_contract_module()

        self.assertIsInstance(module, types.ModuleType)

    def test_module_exposes_expected_public_surface(self) -> None:
        module = _import_contract_module()

        for public_name in module.__all__:
            with self.subTest(public_name=public_name):
                self.assertTrue(hasattr(module, public_name))

        self.assertIn("ENGINE_INVOCATION_CONTRACT", module.__all__)
        self.assertIn("EngineInvocationContract", module.__all__)
        self.assertIn("SUPPORTED_ENGINE_INVOCATION_MODES", module.__all__)
        self.assertIn("PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES", module.__all__)
        self.assertIn("COMBINED_INVOCATION_UNSUPPORTED_MESSAGE", module.__all__)
        self.assertIn("ENGINE_FILE_ARGUMENT_CONTRACT", module.__all__)
        self.assertIn("EngineFileArgumentContract", module.__all__)
        self.assertIn("FileArgumentSpec", module.__all__)
        self.assertIn("REQUIRED_ENGINE_ENVIRONMENT_VARIABLES", module.__all__)
        self.assertIn("PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE", module.__all__)
        self.assertIn("PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE", module.__all__)


class _InvocationContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_contract_module()


class InvocationContractConstantsTests(_InvocationContractTestCase):
    def test_version_dispatcher_and_combined_message_are_exact(self) -> None:
        self.assertEqual(self.contract.ENGINE_INVOCATION_CONTRACT_VERSION, "1.0")
        self.assertEqual(
            self.contract.ENGINE_INVOCATION_DISPATCHER,
            "run_engine_invocation",
        )
        self.assertEqual(
            self.contract.COMBINED_INVOCATION_UNSUPPORTED_MESSAGE,
            "combined execute+observe runtime invocation is not supported",
        )


class InvocationContractModeTests(_InvocationContractTestCase):
    def test_supported_modes_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.SUPPORTED_ENGINE_INVOCATION_MODES,
            ("execute", "observe"),
        )
        self.assertIsInstance(self.contract.SUPPORTED_ENGINE_INVOCATION_MODES, tuple)

    def test_planned_unsupported_modes_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES,
            ("combined",),
        )
        self.assertIsInstance(
            self.contract.PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES,
            tuple,
        )

    def test_mode_surfaces_have_no_duplicates_or_overlap(self) -> None:
        supported = self.contract.SUPPORTED_ENGINE_INVOCATION_MODES
        planned = self.contract.PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES

        self.assertEqual(len(supported), len(set(supported)))
        self.assertEqual(len(planned), len(set(planned)))
        self.assertTrue(set(supported).isdisjoint(planned))

    def test_supported_modes_exclude_forbidden_capabilities(self) -> None:
        supported = set(self.contract.SUPPORTED_ENGINE_INVOCATION_MODES)
        self.assertTrue(supported.isdisjoint(FORBIDDEN_SUPPORTED_MODES))


class InvocationContractFieldTests(_InvocationContractTestCase):
    def test_engine_runtime_invocation_fields_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.ENGINE_RUNTIME_INVOCATION_FIELDS,
            ("mode", "execution", "observation"),
        )
        self.assertIsInstance(self.contract.ENGINE_RUNTIME_INVOCATION_FIELDS, tuple)

    def test_execution_invocation_fields_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.EXECUTION_INVOCATION_FIELDS,
            (
                "working_copy",
                "manifest_path",
                "result_path",
                "freecad_module",
                "resolve_freecad_module",
            ),
        )
        self.assertIsInstance(self.contract.EXECUTION_INVOCATION_FIELDS, tuple)

    def test_observation_invocation_fields_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.OBSERVATION_INVOCATION_FIELDS,
            (
                "document",
                "verification_data",
                "working_copy_path",
                "working_copy_sha256",
                "output_directory",
            ),
        )
        self.assertIsInstance(self.contract.OBSERVATION_INVOCATION_FIELDS, tuple)

    def test_field_tuples_contain_only_strings_without_duplicates(self) -> None:
        field_tuples = (
            self.contract.ENGINE_RUNTIME_INVOCATION_FIELDS,
            self.contract.EXECUTION_INVOCATION_FIELDS,
            self.contract.OBSERVATION_INVOCATION_FIELDS,
        )

        for field_tuple in field_tuples:
            with self.subTest(field_tuple=field_tuple):
                self.assertTrue(all(isinstance(name, str) for name in field_tuple))
                self.assertEqual(len(field_tuple), len(set(field_tuple)))


class InvocationContractNegativeBoundaryTests(_InvocationContractTestCase):
    def test_negative_boundaries_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.ENGINE_INVOCATION_NEGATIVE_BOUNDARIES,
            EXPECTED_NEGATIVE_BOUNDARIES,
        )
        self.assertIsInstance(self.contract.ENGINE_INVOCATION_NEGATIVE_BOUNDARIES, tuple)

    def test_negative_boundaries_are_strings_without_duplicates(self) -> None:
        boundaries = self.contract.ENGINE_INVOCATION_NEGATIVE_BOUNDARIES

        self.assertTrue(all(isinstance(value, str) for value in boundaries))
        self.assertEqual(len(boundaries), len(set(boundaries)))


class InvocationContractFrozenDataclassTests(_InvocationContractTestCase):
    def test_engine_invocation_contract_is_frozen_dataclass(self) -> None:
        self.assertTrue(is_dataclass(self.contract.EngineInvocationContract))
        self.assertTrue(self.contract.EngineInvocationContract.__dataclass_params__.frozen)
        self.assertIn(
            "file_argument_contract",
            {field.name for field in fields(self.contract.EngineInvocationContract)},
        )

    def test_canonical_singleton_is_contract_instance(self) -> None:
        self.assertIsInstance(
            self.contract.ENGINE_INVOCATION_CONTRACT,
            self.contract.EngineInvocationContract,
        )

    def test_canonical_singleton_is_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.contract.ENGINE_INVOCATION_CONTRACT.version = "mutated"  # type: ignore[misc]

    def test_canonical_singleton_matches_module_level_constants(self) -> None:
        singleton = self.contract.ENGINE_INVOCATION_CONTRACT

        self.assertEqual(
            singleton.version,
            self.contract.ENGINE_INVOCATION_CONTRACT_VERSION,
        )
        self.assertEqual(
            singleton.dispatcher,
            self.contract.ENGINE_INVOCATION_DISPATCHER,
        )
        self.assertEqual(
            singleton.supported_modes,
            self.contract.SUPPORTED_ENGINE_INVOCATION_MODES,
        )
        self.assertEqual(
            singleton.planned_unsupported_modes,
            self.contract.PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES,
        )
        self.assertEqual(
            singleton.combined_invocation_unsupported_message,
            self.contract.COMBINED_INVOCATION_UNSUPPORTED_MESSAGE,
        )
        self.assertEqual(
            singleton.execution_invocation_fields,
            self.contract.EXECUTION_INVOCATION_FIELDS,
        )
        self.assertEqual(
            singleton.observation_invocation_fields,
            self.contract.OBSERVATION_INVOCATION_FIELDS,
        )
        self.assertEqual(
            singleton.engine_runtime_invocation_fields,
            self.contract.ENGINE_RUNTIME_INVOCATION_FIELDS,
        )
        self.assertEqual(
            singleton.negative_boundaries,
            self.contract.ENGINE_INVOCATION_NEGATIVE_BOUNDARIES,
        )
        self.assertEqual(
            singleton.required_engine_environment_variables,
            self.contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES,
        )
        self.assertEqual(
            singleton.required_runtime_process_environment_variables,
            self.contract.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES,
        )
        self.assertEqual(
            singleton.optional_smoke_test_environment_variables,
            self.contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
        )
        self.assertIs(
            singleton.file_argument_contract,
            self.contract.ENGINE_FILE_ARGUMENT_CONTRACT,
        )
        self.assertIs(
            singleton.error_contract,
            self.contract.ENGINE_ERROR_CONTRACT,
        )


class InvocationContractFileArgumentIntegrationTests(_InvocationContractTestCase):
    def test_invocation_contract_exposes_canonical_file_argument_contract(self) -> None:
        file_argument_contract = importlib.import_module(
            "parametron_freecad.runtime.file_argument_contract"
        )

        self.assertIs(
            self.contract.ENGINE_FILE_ARGUMENT_CONTRACT,
            file_argument_contract.ENGINE_FILE_ARGUMENT_CONTRACT,
        )
        self.assertIs(
            self.contract.ENGINE_INVOCATION_CONTRACT.file_argument_contract,
            file_argument_contract.ENGINE_FILE_ARGUMENT_CONTRACT,
        )
        self.assertIs(
            self.contract.ENGINE_INVOCATION_CONTRACT.file_argument_contract,
            self.contract.ENGINE_FILE_ARGUMENT_CONTRACT,
        )


class InvocationContractEnvironmentIntegrationTests(_InvocationContractTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.environment_contract = importlib.import_module(
            "parametron_freecad.runtime.environment_contract"
        )

    def test_invocation_contract_exposes_environment_classification_tuples(self) -> None:
        singleton = self.contract.ENGINE_INVOCATION_CONTRACT

        self.assertEqual(
            singleton.required_engine_environment_variables,
            self.environment_contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES,
        )
        self.assertEqual(
            singleton.required_runtime_process_environment_variables,
            self.environment_contract.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES,
        )
        self.assertEqual(
            singleton.optional_smoke_test_environment_variables,
            self.environment_contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
        )

    def test_module_level_environment_constants_match_environment_contract(self) -> None:
        self.assertEqual(
            self.contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES,
            self.environment_contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES,
        )
        self.assertEqual(
            self.contract.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES,
            self.environment_contract.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES,
        )
        self.assertEqual(
            self.contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
            self.environment_contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
        )

    def test_invocation_contract_re_exports_environment_variable_name_constants(self) -> None:
        self.assertEqual(
            self.contract.PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE,
            self.environment_contract.PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE,
        )
        self.assertEqual(
            self.contract.PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE,
            self.environment_contract.PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE,
        )
        self.assertEqual(
            self.contract.PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE,
            "PARAMETRON_FREECAD_BIN",
        )
        self.assertEqual(
            self.contract.PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE,
            "PARAMETRON_FREECAD_STRICT_SMOKE",
        )

    def test_required_environment_classifications_are_empty(self) -> None:
        self.assertEqual(self.contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES, ())
        self.assertEqual(
            self.contract.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES,
            (),
        )

    def test_optional_smoke_test_environment_variables_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
            (
                self.contract.PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE,
                self.contract.PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE,
            ),
        )


class InvocationContractOutputFileIntegrationTests(_InvocationContractTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.output_file_contract = importlib.import_module(
            "parametron_freecad.runtime.output_file_contract"
        )

    def test_invocation_contract_exposes_output_file_contract_field(self) -> None:
        from dataclasses import fields

        field_names = {field.name for field in fields(self.contract.EngineInvocationContract)}
        self.assertIn("output_file_contract", field_names)

    def test_engine_invocation_contract_output_file_contract_is_canonical_singleton(
        self,
    ) -> None:
        self.assertIs(
            self.contract.ENGINE_INVOCATION_CONTRACT.output_file_contract,
            self.output_file_contract.ENGINE_OUTPUT_FILE_CONTRACT,
        )

    def test_engine_invocation_contract_output_file_contract_matches_module_level_export(
        self,
    ) -> None:
        self.assertIs(
            self.contract.ENGINE_INVOCATION_CONTRACT.output_file_contract,
            self.contract.ENGINE_OUTPUT_FILE_CONTRACT,
        )

    def test_invocation_contract_re_exports_engine_output_file_contract(self) -> None:
        self.assertIs(
            self.contract.ENGINE_OUTPUT_FILE_CONTRACT,
            self.output_file_contract.ENGINE_OUTPUT_FILE_CONTRACT,
        )

    def test_invocation_contract_re_exports_engine_output_file_contract_type(self) -> None:
        self.assertIs(
            self.contract.EngineOutputFileContract,
            self.output_file_contract.EngineOutputFileContract,
        )

    def test_invocation_contract_re_exports_output_file_spec_type(self) -> None:
        self.assertIs(
            self.contract.OutputFileSpec,
            self.output_file_contract.OutputFileSpec,
        )

    def test_output_file_contract_re_exports_are_in_module_all(self) -> None:
        self.assertIn("ENGINE_OUTPUT_FILE_CONTRACT", self.contract.__all__)
        self.assertIn("EngineOutputFileContract", self.contract.__all__)
        self.assertIn("OutputFileSpec", self.contract.__all__)

    def test_adding_output_file_contract_did_not_change_supported_modes(self) -> None:
        self.assertEqual(
            self.contract.SUPPORTED_ENGINE_INVOCATION_MODES,
            ("execute", "observe"),
        )

    def test_adding_output_file_contract_did_not_change_planned_unsupported_modes(
        self,
    ) -> None:
        self.assertEqual(
            self.contract.PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES,
            ("combined",),
        )

    def test_adding_output_file_contract_did_not_change_dispatcher(self) -> None:
        self.assertEqual(
            self.contract.ENGINE_INVOCATION_DISPATCHER,
            "run_engine_invocation",
        )

    def test_adding_output_file_contract_did_not_change_combined_unsupported_message(
        self,
    ) -> None:
        self.assertEqual(
            self.contract.COMBINED_INVOCATION_UNSUPPORTED_MESSAGE,
            "combined execute+observe runtime invocation is not supported",
        )

    def test_existing_file_argument_contract_exposure_is_unchanged(self) -> None:
        file_argument_contract = importlib.import_module(
            "parametron_freecad.runtime.file_argument_contract"
        )
        self.assertIs(
            self.contract.ENGINE_INVOCATION_CONTRACT.file_argument_contract,
            file_argument_contract.ENGINE_FILE_ARGUMENT_CONTRACT,
        )

    def test_existing_environment_contract_exposure_is_unchanged(self) -> None:
        environment_contract = importlib.import_module(
            "parametron_freecad.runtime.environment_contract"
        )
        self.assertEqual(
            self.contract.ENGINE_INVOCATION_CONTRACT.required_engine_environment_variables,
            environment_contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES,
        )
        self.assertEqual(
            self.contract.ENGINE_INVOCATION_CONTRACT.optional_smoke_test_environment_variables,
            environment_contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
        )


class InvocationContractTupleImmutabilityTests(_InvocationContractTestCase):
    def test_module_level_tuple_constants_are_immutable(self) -> None:
        tuple_constants = (
            self.contract.SUPPORTED_ENGINE_INVOCATION_MODES,
            self.contract.PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES,
            self.contract.EXECUTION_INVOCATION_FIELDS,
            self.contract.OBSERVATION_INVOCATION_FIELDS,
            self.contract.ENGINE_RUNTIME_INVOCATION_FIELDS,
            self.contract.ENGINE_INVOCATION_NEGATIVE_BOUNDARIES,
            self.contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES,
            self.contract.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES,
            self.contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
        )

        for value in tuple_constants:
            with self.subTest(value=value):
                if not value:
                    self.assertIsInstance(value, tuple)
                    continue
                with self.assertRaises((TypeError, AttributeError)):
                    value[0] = "mutated"  # type: ignore[index]


class InvocationContractErrorContractIntegrationTests(_InvocationContractTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.error_contract = importlib.import_module(
            "parametron_freecad.runtime.error_contract"
        )

    def test_invocation_contract_exposes_canonical_error_contract(self) -> None:
        self.assertIs(
            self.contract.ENGINE_ERROR_CONTRACT,
            self.error_contract.ENGINE_ERROR_CONTRACT,
        )
        self.assertIs(
            self.contract.ENGINE_INVOCATION_CONTRACT.error_contract,
            self.error_contract.ENGINE_ERROR_CONTRACT,
        )
        self.assertIs(
            self.contract.ENGINE_INVOCATION_CONTRACT.error_contract,
            self.contract.ENGINE_ERROR_CONTRACT,
        )

    def test_invocation_contract_re_exports_error_contract_types(self) -> None:
        self.assertIs(
            self.contract.EngineErrorContract,
            self.error_contract.EngineErrorContract,
        )
        self.assertIs(
            self.contract.EngineErrorClassSpec,
            self.error_contract.EngineErrorClassSpec,
        )

    def test_error_contract_types_are_in_invocation_contract_all(self) -> None:
        self.assertIn("ENGINE_ERROR_CONTRACT", self.contract.__all__)
        self.assertIn("EngineErrorContract", self.contract.__all__)
        self.assertIn("EngineErrorClassSpec", self.contract.__all__)

    def test_existing_file_argument_contract_is_not_displaced(self) -> None:
        file_argument_contract = importlib.import_module(
            "parametron_freecad.runtime.file_argument_contract"
        )
        self.assertIs(
            self.contract.ENGINE_INVOCATION_CONTRACT.file_argument_contract,
            file_argument_contract.ENGINE_FILE_ARGUMENT_CONTRACT,
        )

    def test_existing_output_file_contract_is_not_displaced(self) -> None:
        output_file_contract = importlib.import_module(
            "parametron_freecad.runtime.output_file_contract"
        )
        self.assertIs(
            self.contract.ENGINE_INVOCATION_CONTRACT.output_file_contract,
            output_file_contract.ENGINE_OUTPUT_FILE_CONTRACT,
        )

    def test_existing_environment_contract_is_not_displaced(self) -> None:
        environment_contract = importlib.import_module(
            "parametron_freecad.runtime.environment_contract"
        )
        self.assertEqual(
            self.contract.ENGINE_INVOCATION_CONTRACT.required_engine_environment_variables,
            environment_contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES,
        )
        self.assertEqual(
            self.contract.ENGINE_INVOCATION_CONTRACT.optional_smoke_test_environment_variables,
            environment_contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
        )

    def test_existing_invocation_contract_version_is_not_displaced(self) -> None:
        self.assertEqual(self.contract.ENGINE_INVOCATION_CONTRACT_VERSION, "1.0")
        self.assertEqual(self.contract.ENGINE_INVOCATION_CONTRACT.version, "1.0")


if __name__ == "__main__":
    unittest.main()
