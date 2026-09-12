"""Tests for the stable Engine-facing error contract."""

from __future__ import annotations

import builtins
import importlib
import sys
import types
import unittest
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from unittest import mock

MODULE_NAME = "parametron_freecad.runtime.error_contract"
INVOCATION_MODULE_NAME = "parametron_freecad.runtime.invocation"
INVOCATION_CONTRACT_MODULE_NAME = "parametron_freecad.runtime.invocation_contract"

EXPECTED_STABLE_CLASS_NAMES = (
    "EngineInvocationError",
    "EngineInvocationRequestError",
    "EngineInvocationExecutionError",
    "EngineInvocationObservationError",
)

EXPECTED_CATEGORIES = (
    "base",
    "request",
    "execution",
    "observation",
)

EXPECTED_WRAPPING_BOUNDARIES = (
    "engine_invocation",
    "execution_entrypoint",
    "observation_entrypoint",
)


def _import_error_contract_module():
    return importlib.import_module(MODULE_NAME)


def _import_invocation_module():
    return importlib.import_module(INVOCATION_MODULE_NAME)


def _import_invocation_contract_module():
    return importlib.import_module(INVOCATION_CONTRACT_MODULE_NAME)


class ErrorContractImportSafetyTests(unittest.TestCase):
    """The error contract module must import under ordinary Python without FreeCAD."""

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
            module = _import_error_contract_module()

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
            raise AssertionError("importing the error contract must not open files")

        def guarded_getenv(*args, **kwargs):
            raise AssertionError("importing the error contract must not inspect environment")

        with mock.patch("builtins.open", side_effect=guarded_open):
            with mock.patch("os.getenv", side_effect=guarded_getenv):
                module = _import_error_contract_module()

        self.assertIsInstance(module, types.ModuleType)

    def test_module_exposes_all_public_surface_names(self) -> None:
        module = _import_error_contract_module()

        for public_name in module.__all__:
            with self.subTest(public_name=public_name):
                self.assertTrue(hasattr(module, public_name))

    def test_all_includes_contract_singleton_and_version(self) -> None:
        module = _import_error_contract_module()

        self.assertIn("ENGINE_ERROR_CONTRACT", module.__all__)
        self.assertIn("ENGINE_ERROR_CONTRACT_VERSION", module.__all__)

    def test_all_includes_contract_types(self) -> None:
        module = _import_error_contract_module()

        self.assertIn("EngineErrorClassSpec", module.__all__)
        self.assertIn("EngineErrorContract", module.__all__)

    def test_all_includes_stable_error_classes(self) -> None:
        module = _import_error_contract_module()

        for class_name in EXPECTED_STABLE_CLASS_NAMES:
            with self.subTest(class_name=class_name):
                self.assertIn(class_name, module.__all__)

    def test_stable_error_classes_are_exception_subclasses(self) -> None:
        module = _import_error_contract_module()

        for class_name in EXPECTED_STABLE_CLASS_NAMES:
            with self.subTest(class_name=class_name):
                cls = getattr(module, class_name)
                self.assertTrue(issubclass(cls, Exception))


class _ErrorContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.ec = _import_error_contract_module()


class ErrorClassHierarchyTests(_ErrorContractTestCase):
    """Stable Engine-facing error class hierarchy must be correct and stable."""

    def test_engine_invocation_error_subclasses_value_error(self) -> None:
        self.assertTrue(issubclass(self.ec.EngineInvocationError, ValueError))

    def test_request_error_subclasses_engine_invocation_error(self) -> None:
        self.assertTrue(
            issubclass(
                self.ec.EngineInvocationRequestError,
                self.ec.EngineInvocationError,
            )
        )

    def test_execution_error_subclasses_engine_invocation_error(self) -> None:
        self.assertTrue(
            issubclass(
                self.ec.EngineInvocationExecutionError,
                self.ec.EngineInvocationError,
            )
        )

    def test_observation_error_subclasses_engine_invocation_error(self) -> None:
        self.assertTrue(
            issubclass(
                self.ec.EngineInvocationObservationError,
                self.ec.EngineInvocationError,
            )
        )

    def test_request_error_can_be_caught_as_engine_invocation_error(self) -> None:
        with self.assertRaises(self.ec.EngineInvocationError):
            raise self.ec.EngineInvocationRequestError("test")

    def test_execution_error_can_be_caught_as_engine_invocation_error(self) -> None:
        with self.assertRaises(self.ec.EngineInvocationError):
            raise self.ec.EngineInvocationExecutionError("test")

    def test_observation_error_can_be_caught_as_engine_invocation_error(self) -> None:
        with self.assertRaises(self.ec.EngineInvocationError):
            raise self.ec.EngineInvocationObservationError("test")

    def test_all_engine_errors_can_be_caught_as_value_error(self) -> None:
        for cls in (
            self.ec.EngineInvocationError,
            self.ec.EngineInvocationRequestError,
            self.ec.EngineInvocationExecutionError,
            self.ec.EngineInvocationObservationError,
        ):
            with self.subTest(cls=cls):
                with self.assertRaises(ValueError):
                    raise cls("test")

    def test_subclass_error_classes_are_distinct_from_base(self) -> None:
        for cls in (
            self.ec.EngineInvocationRequestError,
            self.ec.EngineInvocationExecutionError,
            self.ec.EngineInvocationObservationError,
        ):
            with self.subTest(cls=cls):
                self.assertIsNot(cls, self.ec.EngineInvocationError)

    def test_subclass_error_classes_are_distinct_from_each_other(self) -> None:
        subclasses = [
            self.ec.EngineInvocationRequestError,
            self.ec.EngineInvocationExecutionError,
            self.ec.EngineInvocationObservationError,
        ]
        self.assertEqual(len(subclasses), len(set(subclasses)))


class ErrorContractImportCompatibilityTests(_ErrorContractTestCase):
    """Classes re-exported from invocation must be identical to error_contract classes."""

    def test_engine_invocation_error_identity_from_invocation(self) -> None:
        invocation = _import_invocation_module()
        self.assertIs(
            invocation.EngineInvocationError,
            self.ec.EngineInvocationError,
        )

    def test_engine_invocation_request_error_identity_from_invocation(self) -> None:
        invocation = _import_invocation_module()
        self.assertIs(
            invocation.EngineInvocationRequestError,
            self.ec.EngineInvocationRequestError,
        )

    def test_engine_invocation_execution_error_identity_from_invocation(self) -> None:
        invocation = _import_invocation_module()
        self.assertIs(
            invocation.EngineInvocationExecutionError,
            self.ec.EngineInvocationExecutionError,
        )

    def test_engine_invocation_observation_error_identity_from_invocation(self) -> None:
        invocation = _import_invocation_module()
        self.assertIs(
            invocation.EngineInvocationObservationError,
            self.ec.EngineInvocationObservationError,
        )

    def test_all_four_error_classes_have_identical_class_objects(self) -> None:
        invocation = _import_invocation_module()
        for class_name in EXPECTED_STABLE_CLASS_NAMES:
            with self.subTest(class_name=class_name):
                ec_cls = getattr(self.ec, class_name)
                inv_cls = getattr(invocation, class_name)
                self.assertIs(ec_cls, inv_cls)


class ErrorContractMetadataCompletenessTests(_ErrorContractTestCase):
    """ENGINE_ERROR_CONTRACT must expose deterministic metadata for all stable error classes."""

    def test_contract_version_is_one_zero(self) -> None:
        self.assertEqual(self.ec.ENGINE_ERROR_CONTRACT.version, "1.0")
        self.assertEqual(self.ec.ENGINE_ERROR_CONTRACT_VERSION, "1.0")
        self.assertEqual(
            self.ec.ENGINE_ERROR_CONTRACT.version,
            self.ec.ENGINE_ERROR_CONTRACT_VERSION,
        )

    def test_error_classes_tuple_has_exactly_four_specs(self) -> None:
        self.assertEqual(len(self.ec.ENGINE_ERROR_CONTRACT.error_classes), 4)
        self.assertIsInstance(self.ec.ENGINE_ERROR_CONTRACT.error_classes, tuple)

    def test_error_class_names_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.ec.ENGINE_ERROR_CONTRACT.error_class_names,
            EXPECTED_STABLE_CLASS_NAMES,
        )
        self.assertIsInstance(self.ec.ENGINE_ERROR_CONTRACT.error_class_names, tuple)

    def test_categories_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.ec.ENGINE_ERROR_CONTRACT.categories,
            EXPECTED_CATEGORIES,
        )
        self.assertIsInstance(self.ec.ENGINE_ERROR_CONTRACT.categories, tuple)

    def test_wrapping_boundaries_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.ec.ENGINE_ERROR_CONTRACT.wrapping_boundaries,
            EXPECTED_WRAPPING_BOUNDARIES,
        )
        self.assertIsInstance(self.ec.ENGINE_ERROR_CONTRACT.wrapping_boundaries, tuple)

    def test_named_error_class_references_are_correct(self) -> None:
        contract = self.ec.ENGINE_ERROR_CONTRACT
        self.assertEqual(
            contract.request_validation_error_class_name,
            "EngineInvocationRequestError",
        )
        self.assertEqual(
            contract.execution_wrapping_error_class_name,
            "EngineInvocationExecutionError",
        )
        self.assertEqual(
            contract.observation_wrapping_error_class_name,
            "EngineInvocationObservationError",
        )

    def test_error_class_names_match_spec_class_names(self) -> None:
        contract = self.ec.ENGINE_ERROR_CONTRACT
        spec_names = tuple(spec.class_name for spec in contract.error_classes)
        self.assertEqual(spec_names, contract.error_class_names)

    def test_spec_ordering_has_base_class_first(self) -> None:
        contract = self.ec.ENGINE_ERROR_CONTRACT
        names = contract.error_class_names
        self.assertEqual(names[0], "EngineInvocationError")
        self.assertIn("EngineInvocationRequestError", names[1:])
        self.assertIn("EngineInvocationExecutionError", names[1:])
        self.assertIn("EngineInvocationObservationError", names[1:])

    def test_base_error_spec_fields(self) -> None:
        spec = next(
            s for s in self.ec.ENGINE_ERROR_CONTRACT.error_classes
            if s.class_name == "EngineInvocationError"
        )
        self.assertEqual(spec.category, "base")
        self.assertEqual(
            spec.public_import_path,
            "parametron_freecad.runtime.error_contract.EngineInvocationError",
        )
        self.assertEqual(spec.base_class_name, "ValueError")
        self.assertFalse(spec.directly_raised_by_request_validation)
        self.assertFalse(spec.wraps_delegated_runtime_failure)
        self.assertIsNone(spec.delegated_source_boundary)
        self.assertFalse(spec.preserves_cause)

    def test_request_error_spec_fields(self) -> None:
        spec = next(
            s for s in self.ec.ENGINE_ERROR_CONTRACT.error_classes
            if s.class_name == "EngineInvocationRequestError"
        )
        self.assertEqual(spec.category, "request")
        self.assertEqual(
            spec.public_import_path,
            "parametron_freecad.runtime.error_contract.EngineInvocationRequestError",
        )
        self.assertEqual(spec.base_class_name, "EngineInvocationError")
        self.assertTrue(spec.directly_raised_by_request_validation)
        self.assertFalse(spec.wraps_delegated_runtime_failure)
        self.assertEqual(spec.delegated_source_boundary, "engine_invocation")
        self.assertFalse(spec.preserves_cause)

    def test_execution_error_spec_fields(self) -> None:
        spec = next(
            s for s in self.ec.ENGINE_ERROR_CONTRACT.error_classes
            if s.class_name == "EngineInvocationExecutionError"
        )
        self.assertEqual(spec.category, "execution")
        self.assertEqual(
            spec.public_import_path,
            "parametron_freecad.runtime.error_contract.EngineInvocationExecutionError",
        )
        self.assertEqual(spec.base_class_name, "EngineInvocationError")
        self.assertFalse(spec.directly_raised_by_request_validation)
        self.assertTrue(spec.wraps_delegated_runtime_failure)
        self.assertEqual(spec.delegated_source_boundary, "execution_entrypoint")
        self.assertTrue(spec.preserves_cause)

    def test_observation_error_spec_fields(self) -> None:
        spec = next(
            s for s in self.ec.ENGINE_ERROR_CONTRACT.error_classes
            if s.class_name == "EngineInvocationObservationError"
        )
        self.assertEqual(spec.category, "observation")
        self.assertEqual(
            spec.public_import_path,
            "parametron_freecad.runtime.error_contract.EngineInvocationObservationError",
        )
        self.assertEqual(spec.base_class_name, "EngineInvocationError")
        self.assertFalse(spec.directly_raised_by_request_validation)
        self.assertTrue(spec.wraps_delegated_runtime_failure)
        self.assertEqual(spec.delegated_source_boundary, "observation_entrypoint")
        self.assertTrue(spec.preserves_cause)

    def test_public_import_paths_are_rooted_in_error_contract_module(self) -> None:
        contract = self.ec.ENGINE_ERROR_CONTRACT
        for spec in contract.error_classes:
            with self.subTest(class_name=spec.class_name):
                module_path, _, attr_name = spec.public_import_path.rpartition(".")
                self.assertEqual(module_path, MODULE_NAME)
                self.assertEqual(attr_name, spec.class_name)

    def test_no_duplicate_class_names_in_contract(self) -> None:
        names = self.ec.ENGINE_ERROR_CONTRACT.error_class_names
        self.assertEqual(len(names), len(set(names)))

    def test_no_duplicate_categories_in_contract(self) -> None:
        categories = self.ec.ENGINE_ERROR_CONTRACT.categories
        self.assertEqual(len(categories), len(set(categories)))

    def test_no_duplicate_wrapping_boundaries_in_contract(self) -> None:
        boundaries = self.ec.ENGINE_ERROR_CONTRACT.wrapping_boundaries
        self.assertEqual(len(boundaries), len(set(boundaries)))

    def test_module_level_spec_constants_match_contract_entries(self) -> None:
        contract = self.ec.ENGINE_ERROR_CONTRACT
        expected_by_name = {spec.class_name: spec for spec in contract.error_classes}

        self.assertIs(
            self.ec.ENGINE_INVOCATION_ERROR_SPEC,
            expected_by_name["EngineInvocationError"],
        )
        self.assertIs(
            self.ec.ENGINE_INVOCATION_REQUEST_ERROR_SPEC,
            expected_by_name["EngineInvocationRequestError"],
        )
        self.assertIs(
            self.ec.ENGINE_INVOCATION_EXECUTION_ERROR_SPEC,
            expected_by_name["EngineInvocationExecutionError"],
        )
        self.assertIs(
            self.ec.ENGINE_INVOCATION_OBSERVATION_ERROR_SPEC,
            expected_by_name["EngineInvocationObservationError"],
        )

    def test_module_level_class_names_tuple_matches_contract(self) -> None:
        self.assertEqual(
            self.ec.ENGINE_ERROR_CLASS_NAMES,
            self.ec.ENGINE_ERROR_CONTRACT.error_class_names,
        )

    def test_module_level_class_specs_tuple_matches_contract(self) -> None:
        self.assertEqual(
            self.ec.ENGINE_ERROR_CLASS_SPECS,
            self.ec.ENGINE_ERROR_CONTRACT.error_classes,
        )


class ErrorContractImmutabilityTests(_ErrorContractTestCase):
    """Error contract metadata must be immutable and frozen."""

    def test_engine_error_contract_type_is_frozen_dataclass(self) -> None:
        self.assertTrue(self.ec.EngineErrorContract.__dataclass_params__.frozen)

    def test_engine_error_class_spec_type_is_frozen_dataclass(self) -> None:
        self.assertTrue(self.ec.EngineErrorClassSpec.__dataclass_params__.frozen)

    def test_assigning_version_to_contract_singleton_raises(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.ec.ENGINE_ERROR_CONTRACT.version = "mutated"  # type: ignore[misc]

    def test_assigning_error_classes_to_contract_singleton_raises(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.ec.ENGINE_ERROR_CONTRACT.error_classes = ()  # type: ignore[misc]

    def test_assigning_error_class_names_to_contract_singleton_raises(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.ec.ENGINE_ERROR_CONTRACT.error_class_names = ()  # type: ignore[misc]

    def test_assigning_field_on_spec_raises(self) -> None:
        spec = self.ec.ENGINE_ERROR_CONTRACT.error_classes[0]
        with self.assertRaises(FrozenInstanceError):
            spec.class_name = "mutated"  # type: ignore[misc]

    def test_assigning_field_on_module_level_spec_constants_raises(self) -> None:
        spec_constants = (
            self.ec.ENGINE_INVOCATION_ERROR_SPEC,
            self.ec.ENGINE_INVOCATION_REQUEST_ERROR_SPEC,
            self.ec.ENGINE_INVOCATION_EXECUTION_ERROR_SPEC,
            self.ec.ENGINE_INVOCATION_OBSERVATION_ERROR_SPEC,
        )
        for spec in spec_constants:
            with self.subTest(spec=spec.class_name):
                with self.assertRaises(FrozenInstanceError):
                    spec.class_name = "mutated"  # type: ignore[misc]

    def test_error_classes_tuple_cannot_be_appended(self) -> None:
        error_classes = self.ec.ENGINE_ERROR_CONTRACT.error_classes
        with self.assertRaises((TypeError, AttributeError)):
            error_classes.append(error_classes[0])  # type: ignore[attr-defined]

    def test_error_class_names_tuple_cannot_be_appended(self) -> None:
        error_class_names = self.ec.ENGINE_ERROR_CONTRACT.error_class_names
        with self.assertRaises((TypeError, AttributeError)):
            error_class_names.append("ExtraName")  # type: ignore[attr-defined]

    def test_categories_tuple_cannot_be_appended(self) -> None:
        categories = self.ec.ENGINE_ERROR_CONTRACT.categories
        with self.assertRaises((TypeError, AttributeError)):
            categories.append("extra")  # type: ignore[attr-defined]

    def test_wrapping_boundaries_tuple_cannot_be_appended(self) -> None:
        boundaries = self.ec.ENGINE_ERROR_CONTRACT.wrapping_boundaries
        with self.assertRaises((TypeError, AttributeError)):
            boundaries.append("extra")  # type: ignore[attr-defined]

    def test_module_level_tuple_constants_are_immutable(self) -> None:
        tuple_constants = (
            self.ec.ENGINE_ERROR_CLASS_NAMES,
            self.ec.ENGINE_ERROR_CLASS_SPECS,
            self.ec.ENGINE_ERROR_CATEGORIES,
            self.ec.ENGINE_ERROR_WRAPPING_BOUNDARIES,
        )
        for value in tuple_constants:
            with self.subTest(value=value):
                with self.assertRaises((TypeError, AttributeError)):
                    value[0] = "mutated"  # type: ignore[index]


class ErrorContractInvocationContractWiringTests(_ErrorContractTestCase):
    """ENGINE_INVOCATION_CONTRACT.error_contract must be the canonical ENGINE_ERROR_CONTRACT."""

    def test_invocation_contract_error_contract_is_canonical_singleton(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        self.assertIs(
            invocation_contract.ENGINE_INVOCATION_CONTRACT.error_contract,
            self.ec.ENGINE_ERROR_CONTRACT,
        )

    def test_invocation_contract_has_error_contract_field(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        field_names = {
            f.name
            for f in fields(invocation_contract.EngineInvocationContract)
        }
        self.assertIn("error_contract", field_names)

    def test_invocation_contract_module_level_error_contract_is_canonical(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        self.assertIs(
            invocation_contract.ENGINE_ERROR_CONTRACT,
            self.ec.ENGINE_ERROR_CONTRACT,
        )

    def test_invocation_contract_re_exports_error_contract_type(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        self.assertIs(
            invocation_contract.EngineErrorContract,
            self.ec.EngineErrorContract,
        )

    def test_invocation_contract_re_exports_error_class_spec_type(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        self.assertIs(
            invocation_contract.EngineErrorClassSpec,
            self.ec.EngineErrorClassSpec,
        )

    def test_invocation_contract_error_contract_field_is_correct_type(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        self.assertIsInstance(
            invocation_contract.ENGINE_INVOCATION_CONTRACT.error_contract,
            self.ec.EngineErrorContract,
        )

    def test_error_contract_wiring_did_not_displace_file_argument_contract(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        file_argument_contract = importlib.import_module(
            "parametron_freecad.runtime.file_argument_contract"
        )
        self.assertIs(
            invocation_contract.ENGINE_INVOCATION_CONTRACT.file_argument_contract,
            file_argument_contract.ENGINE_FILE_ARGUMENT_CONTRACT,
        )

    def test_error_contract_wiring_did_not_displace_output_file_contract(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        output_file_contract = importlib.import_module(
            "parametron_freecad.runtime.output_file_contract"
        )
        self.assertIs(
            invocation_contract.ENGINE_INVOCATION_CONTRACT.output_file_contract,
            output_file_contract.ENGINE_OUTPUT_FILE_CONTRACT,
        )

    def test_error_contract_wiring_did_not_change_supported_modes(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        self.assertEqual(
            invocation_contract.SUPPORTED_ENGINE_INVOCATION_MODES,
            ("execute", "observe"),
        )

    def test_error_contract_wiring_did_not_change_planned_unsupported_modes(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        self.assertEqual(
            invocation_contract.PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES,
            ("combined",),
        )

    def test_error_contract_wiring_did_not_change_dispatcher(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        self.assertEqual(
            invocation_contract.ENGINE_INVOCATION_DISPATCHER,
            "run_engine_invocation",
        )

    def test_error_contract_wiring_did_not_change_invocation_contract_version(self) -> None:
        invocation_contract = _import_invocation_contract_module()
        self.assertEqual(invocation_contract.ENGINE_INVOCATION_CONTRACT_VERSION, "1.0")


def _make_execution_invocation(invocation):
    return invocation.ExecutionInvocation(
        working_copy=Path("/fake/work"),
        manifest_path=Path("/fake/work/export_manifest_v1.json"),
        result_path=Path("/fake/work/result.json"),
    )


def _make_observation_invocation(invocation):
    return invocation.ObservationInvocation(
        document=object(),
        verification_data={"schemaVersion": "1.0"},
        working_copy_path="/fake/work",
        working_copy_sha256="abc123",
        output_directory="/fake/out",
    )


class ErrorContractBehaviorPreservationTests(unittest.TestCase):
    """Runtime invocation behavior must be unchanged after error class re-homing."""

    def test_invalid_request_raises_error_contract_request_error(self) -> None:
        from parametron_freecad.runtime import invocation
        from parametron_freecad.runtime.error_contract import EngineInvocationRequestError

        with self.assertRaises(EngineInvocationRequestError):
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(mode="execute")
            )

    def test_invalid_request_also_catchable_as_error_contract_base_error(self) -> None:
        from parametron_freecad.runtime import invocation
        from parametron_freecad.runtime.error_contract import EngineInvocationError

        with self.assertRaises(EngineInvocationError):
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(mode="execute")
            )

    def test_combined_mode_still_raises_request_error_with_contract_message(self) -> None:
        from parametron_freecad.runtime import invocation
        from parametron_freecad.runtime.error_contract import EngineInvocationRequestError
        from parametron_freecad.runtime.invocation_contract import (
            COMBINED_INVOCATION_UNSUPPORTED_MESSAGE,
        )

        with self.assertRaises(EngineInvocationRequestError) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(mode="combined")  # type: ignore[arg-type]
            )

        self.assertEqual(
            str(excinfo.exception),
            COMBINED_INVOCATION_UNSUPPORTED_MESSAGE,
        )
        self.assertIsNone(excinfo.exception.__cause__)

    def test_execution_entrypoint_failure_raises_error_contract_execution_error(self) -> None:
        from parametron_freecad.runtime import entrypoints, invocation
        from parametron_freecad.runtime.error_contract import EngineInvocationExecutionError

        original = entrypoints.ExecutionEntrypointError("execution failed")

        with mock.patch.object(
            invocation, "run_execution_entrypoint", side_effect=original
        ), self.assertRaises(EngineInvocationExecutionError) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(
                    mode="execute",
                    execution=_make_execution_invocation(invocation),
                )
            )

        self.assertIs(excinfo.exception.__cause__, original)

    def test_observation_entrypoint_failure_raises_error_contract_observation_error(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints, invocation
        from parametron_freecad.runtime.error_contract import EngineInvocationObservationError

        original = entrypoints.ObservationEntrypointError("observation failed")

        with mock.patch.object(
            invocation, "run_observation_entrypoint", side_effect=original
        ), self.assertRaises(EngineInvocationObservationError) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(
                    mode="observe",
                    observation=_make_observation_invocation(invocation),
                )
            )

        self.assertIs(excinfo.exception.__cause__, original)

    def test_execution_cause_is_preserved_as_execution_entrypoint_error(self) -> None:
        from parametron_freecad.runtime import entrypoints, invocation
        from parametron_freecad.runtime.error_contract import EngineInvocationExecutionError

        original = entrypoints.ExecutionEntrypointError("fake execution failure")

        with mock.patch.object(
            invocation, "run_execution_entrypoint", side_effect=original
        ), self.assertRaises(EngineInvocationExecutionError) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(
                    mode="execute",
                    execution=_make_execution_invocation(invocation),
                )
            )

        self.assertIs(excinfo.exception.__cause__, original)
        self.assertIsInstance(excinfo.exception.__cause__, entrypoints.ExecutionEntrypointError)

    def test_observation_cause_is_preserved_as_observation_entrypoint_error(self) -> None:
        from parametron_freecad.runtime import entrypoints, invocation
        from parametron_freecad.runtime.error_contract import EngineInvocationObservationError

        original = entrypoints.ObservationEntrypointError("fake observation failure")

        with mock.patch.object(
            invocation, "run_observation_entrypoint", side_effect=original
        ), self.assertRaises(EngineInvocationObservationError) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(
                    mode="observe",
                    observation=_make_observation_invocation(invocation),
                )
            )

        self.assertIs(excinfo.exception.__cause__, original)
        self.assertIsInstance(
            excinfo.exception.__cause__, entrypoints.ObservationEntrypointError
        )

    def test_request_validation_error_has_no_cause(self) -> None:
        from parametron_freecad.runtime import invocation
        from parametron_freecad.runtime.error_contract import EngineInvocationRequestError

        with self.assertRaises(EngineInvocationRequestError) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(mode="execute")
            )

        self.assertIsNone(excinfo.exception.__cause__)

    def test_invocation_module_error_classes_catchable_as_error_contract_classes(self) -> None:
        from parametron_freecad.runtime import invocation
        from parametron_freecad.runtime.error_contract import (
            EngineInvocationError,
            EngineInvocationRequestError,
        )

        with self.assertRaises(EngineInvocationRequestError):
            raise invocation.EngineInvocationRequestError("test")

        with self.assertRaises(EngineInvocationError):
            raise invocation.EngineInvocationRequestError("test")


if __name__ == "__main__":
    unittest.main()
