"""Tests for the Engine-to-FreeCAD environment-variable contract surface."""

from __future__ import annotations

import builtins
import importlib
import os
import sys
import types
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from unittest import mock

MODULE_NAME = "parametron_freecad.runtime.environment_contract"

EXPECTED_OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES = (
    "PARAMETRON_FREECAD_BIN",
    "PARAMETRON_FREECAD_STRICT_SMOKE",
)


def _import_contract_module():
    return importlib.import_module(MODULE_NAME)


def _reload_contract_module():
    sys.modules.pop(MODULE_NAME, None)
    return importlib.import_module(MODULE_NAME)


class EnvironmentContractImportSafetyTests(unittest.TestCase):
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

        expected_public_names = {
            "ENVIRONMENT_CONTRACT_VERSION",
            "PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE",
            "PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE",
            "REQUIRED_ENGINE_ENVIRONMENT_VARIABLES",
            "REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES",
            "OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES",
            "EnvironmentVariableSpec",
            "EngineEnvironmentContract",
            "ENGINE_ENVIRONMENT_CONTRACT",
        }
        self.assertTrue(expected_public_names.issubset(set(module.__all__)))


class _EnvironmentContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_contract_module()


class EnvironmentContractVersionTests(_EnvironmentContractTestCase):
    def test_environment_contract_version_is_exact(self) -> None:
        self.assertEqual(self.contract.ENVIRONMENT_CONTRACT_VERSION, "1.0")

    def test_canonical_singleton_version_is_exact(self) -> None:
        self.assertEqual(self.contract.ENGINE_ENVIRONMENT_CONTRACT.version, "1.0")


class EnvironmentContractRequiredVariableTests(_EnvironmentContractTestCase):
    def test_required_engine_environment_variables_are_empty_tuple(self) -> None:
        self.assertEqual(self.contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES, ())
        self.assertIsInstance(self.contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES, tuple)

    def test_required_runtime_process_environment_variables_are_empty_tuple(self) -> None:
        self.assertEqual(self.contract.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES, ())
        self.assertIsInstance(
            self.contract.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES,
            tuple,
        )

    def test_required_classifications_exclude_optional_smoke_variables(self) -> None:
        optional_names = {
            self.contract.PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE,
            self.contract.PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE,
        }

        self.assertTrue(
            optional_names.isdisjoint(
                self.contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES
            )
        )
        self.assertTrue(
            optional_names.isdisjoint(
                self.contract.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES
            )
        )


class EnvironmentContractOptionalSmokeVariableTests(_EnvironmentContractTestCase):
    def test_optional_smoke_test_environment_variables_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
            EXPECTED_OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
        )
        self.assertIsInstance(
            self.contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
            tuple,
        )

    def test_optional_smoke_test_environment_variables_have_no_unknown_names(self) -> None:
        allowed = set(EXPECTED_OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES)
        self.assertEqual(
            set(self.contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES),
            allowed,
        )


class EnvironmentContractVariableSpecTests(_EnvironmentContractTestCase):
    def _spec_by_name(self, name: str):
        specs_by_name = {
            spec.name: spec for spec in self.contract.ENGINE_ENVIRONMENT_CONTRACT.variables
        }
        self.assertIn(name, specs_by_name)
        return specs_by_name[name]

    def test_engine_environment_contract_variables_are_immutable_specs(self) -> None:
        variables = self.contract.ENGINE_ENVIRONMENT_CONTRACT.variables

        self.assertIsInstance(variables, tuple)
        self.assertEqual(len(variables), 2)
        for spec in variables:
            with self.subTest(spec=spec):
                self.assertIsInstance(spec, self.contract.EnvironmentVariableSpec)
                self.assertTrue(is_dataclass(spec))
                self.assertTrue(spec.__dataclass_params__.frozen)

    def test_parametron_freecad_bin_spec_metadata(self) -> None:
        spec = self._spec_by_name(
            self.contract.PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE
        )

        self.assertEqual(
            spec.name,
            self.contract.PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE,
        )
        self.assertFalse(spec.required)
        self.assertEqual(
            spec.scope,
            self.contract.ENVIRONMENT_VARIABLE_SCOPE_ENGINE_INTEGRATION_LAUNCH,
        )
        self.assertIn("launch", spec.purpose.lower())
        self.assertIn("freecad", spec.purpose.lower())
        self.assertEqual(
            spec.value_contract,
            self.contract.PARAMETRON_FREECAD_BIN_VALUE_CONTRACT,
        )
        self.assertIn("freecadcmd", spec.value_contract.lower())
        self.assertNotIn(
            spec.name,
            self.contract.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES,
        )

    def test_parametron_freecad_bin_names_the_underlying_host_not_wrapper(self) -> None:
        spec = self._spec_by_name(
            self.contract.PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE
        )

        self.assertIn("freecadcmd", spec.value_contract.lower())
        self.assertIn("executable", spec.value_contract.lower())
        self.assertNotIn("parametron-freecad", spec.value_contract.lower())

    def test_parametron_freecad_strict_smoke_spec_metadata(self) -> None:
        spec = self._spec_by_name(
            self.contract.PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE
        )

        self.assertEqual(
            spec.name,
            self.contract.PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE,
        )
        self.assertFalse(spec.required)
        self.assertEqual(
            spec.scope,
            self.contract.ENVIRONMENT_VARIABLE_SCOPE_SMOKE_TEST,
        )
        self.assertIn("smoke", spec.purpose.lower())
        self.assertIn("strict", spec.purpose.lower())
        self.assertEqual(
            spec.value_contract,
            self.contract.PARAMETRON_FREECAD_STRICT_SMOKE_VALUE_CONTRACT,
        )
        self.assertIn('"1"', spec.value_contract)
        self.assertNotIn(
            spec.name,
            self.contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES,
        )


class EnvironmentContractFrozenDataclassTests(_EnvironmentContractTestCase):
    def test_environment_variable_spec_is_frozen_dataclass(self) -> None:
        self.assertTrue(is_dataclass(self.contract.EnvironmentVariableSpec))
        self.assertTrue(self.contract.EnvironmentVariableSpec.__dataclass_params__.frozen)

    def test_engine_environment_contract_is_frozen_dataclass(self) -> None:
        self.assertTrue(is_dataclass(self.contract.EngineEnvironmentContract))
        self.assertTrue(
            self.contract.EngineEnvironmentContract.__dataclass_params__.frozen
        )

    def test_canonical_singleton_is_contract_instance(self) -> None:
        self.assertIsInstance(
            self.contract.ENGINE_ENVIRONMENT_CONTRACT,
            self.contract.EngineEnvironmentContract,
        )

    def test_canonical_singleton_is_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.contract.ENGINE_ENVIRONMENT_CONTRACT.version = "mutated"  # type: ignore[misc]

    def test_environment_variable_spec_is_immutable(self) -> None:
        spec = self.contract.PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE_SPEC

        with self.assertRaises(FrozenInstanceError):
            spec.required = True  # type: ignore[misc]

    def test_canonical_singleton_matches_module_level_constants(self) -> None:
        singleton = self.contract.ENGINE_ENVIRONMENT_CONTRACT

        self.assertEqual(
            singleton.version,
            self.contract.ENVIRONMENT_CONTRACT_VERSION,
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
        self.assertEqual(
            singleton.variables,
            self.contract.ENGINE_ENVIRONMENT_VARIABLE_SPECS,
        )


class EnvironmentContractTupleImmutabilityTests(_EnvironmentContractTestCase):
    def test_module_level_tuple_constants_are_immutable(self) -> None:
        tuple_constants = (
            self.contract.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES,
            self.contract.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES,
            self.contract.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
            self.contract.ENGINE_ENVIRONMENT_VARIABLE_SPECS,
        )

        for value in tuple_constants:
            with self.subTest(value=value):
                if not value:
                    self.assertIsInstance(value, tuple)
                    continue
                with self.assertRaises((TypeError, AttributeError)):
                    value[0] = "mutated"  # type: ignore[index]


class EnvironmentContractNoEnvironmentReadsTests(unittest.TestCase):
    def test_contract_metadata_is_independent_of_os_environ_values(self) -> None:
        unusual_values = {
            "PARAMETRON_FREECAD_BIN": "/definitely/not/a/real/freecadcmd",
            "PARAMETRON_FREECAD_STRICT_SMOKE": "not-a-valid-strict-value",
        }
        original_values = {
            name: os.environ.get(name) for name in unusual_values
        }

        try:
            os.environ.update(unusual_values)
            module = _reload_contract_module()
        finally:
            for name, value in original_values.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

        self.assertEqual(module.ENVIRONMENT_CONTRACT_VERSION, "1.0")
        self.assertEqual(module.REQUIRED_ENGINE_ENVIRONMENT_VARIABLES, ())
        self.assertEqual(module.REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES, ())
        self.assertEqual(
            module.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
            EXPECTED_OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
        )
        self.assertEqual(module.ENGINE_ENVIRONMENT_CONTRACT.version, "1.0")

        bin_spec = next(
            spec
            for spec in module.ENGINE_ENVIRONMENT_CONTRACT.variables
            if spec.name == module.PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE
        )
        self.assertFalse(bin_spec.required)
        self.assertEqual(
            bin_spec.value_contract,
            module.PARAMETRON_FREECAD_BIN_VALUE_CONTRACT,
        )

    def test_inspecting_contract_does_not_call_getenv_or_environ_lookup(self) -> None:
        module = _import_contract_module()

        def guarded_getenv(*args, **kwargs):
            raise AssertionError("contract inspection must not call os.getenv")

        class GuardedEnviron(dict):
            def __getitem__(self, key):
                raise AssertionError("contract inspection must not read os.environ")

            def get(self, key, default=None):
                raise AssertionError("contract inspection must not read os.environ")

        with mock.patch("os.getenv", side_effect=guarded_getenv):
            with mock.patch("os.environ", GuardedEnviron(os.environ)):
                self.assertEqual(module.ENVIRONMENT_CONTRACT_VERSION, "1.0")
                self.assertEqual(
                    module.OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
                    EXPECTED_OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
                )
                self.assertEqual(len(module.ENGINE_ENVIRONMENT_CONTRACT.variables), 2)


if __name__ == "__main__":
    unittest.main()
