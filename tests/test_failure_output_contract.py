from __future__ import annotations

import builtins
import importlib
import sys
import types
import unittest
from dataclasses import FrozenInstanceError
from unittest import mock

from parametron_freecad.common.canonical_json import dumps_canonical

MODULE_NAME = "parametron_freecad.runtime.failure_output_contract"


def _import_failure_output_contract_module():
    return importlib.import_module(MODULE_NAME)


def _execution_failure(stage: str | None = "parameter_assignment"):
    contract = _import_failure_output_contract_module()
    return contract.StructuredFailure(
        boundary=contract.FAILURE_BOUNDARY_EXECUTION_ENTRYPOINT,
        category=contract.FAILURE_CATEGORY_EXECUTION,
        code=contract.FAILURE_CODE_RUNTIME_FAILURE,
        message="parameter assignment failed",
        stage=stage,
    )


class FailureOutputContractImportSafetyTests(unittest.TestCase):
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
            module = _import_failure_output_contract_module()

        self.assertIsInstance(module, types.ModuleType)
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class FailureOutputContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_failure_output_contract_module()

    def test_build_failure_output_payload_returns_exact_successful_shape(self) -> None:
        failure = _execution_failure()

        payload = self.contract.build_failure_output_payload(failure)

        self.assertEqual(
            payload,
            {
                "schemaVersion": "1.0",
                "status": "failed",
                "failure": {
                    "boundary": "execution_entrypoint",
                    "category": "execution",
                    "code": "runtime_failure",
                    "message": "parameter assignment failed",
                    "stage": "parameter_assignment",
                },
            },
        )

    def test_build_failure_output_payload_preserves_null_stage(self) -> None:
        failure = _execution_failure(stage=None)

        payload = self.contract.build_failure_output_payload(failure)

        self.assertIsNone(payload["failure"]["stage"])

    def test_payload_top_level_keys_are_exact(self) -> None:
        payload = self.contract.build_failure_output_payload(_execution_failure())

        self.assertEqual(set(payload.keys()), {"schemaVersion", "status", "failure"})

    def test_failure_detail_keys_are_exact(self) -> None:
        payload = self.contract.build_failure_output_payload(_execution_failure())

        self.assertEqual(
            set(payload["failure"].keys()),
            {"boundary", "category", "code", "message", "stage"},
        )

    def test_constants_match_contract_values(self) -> None:
        self.assertEqual(self.contract.FAILURE_OUTPUT_SCHEMA_VERSION, "1.0")
        self.assertEqual(self.contract.FAILURE_OUTPUT_STATUS_FAILED, "failed")

        self.assertEqual(self.contract.FAILURE_FIELD_SCHEMA_VERSION, "schemaVersion")
        self.assertEqual(self.contract.FAILURE_FIELD_STATUS, "status")
        self.assertEqual(self.contract.FAILURE_FIELD_FAILURE, "failure")

        self.assertEqual(self.contract.FAILURE_DETAIL_FIELD_BOUNDARY, "boundary")
        self.assertEqual(self.contract.FAILURE_DETAIL_FIELD_CATEGORY, "category")
        self.assertEqual(self.contract.FAILURE_DETAIL_FIELD_CODE, "code")
        self.assertEqual(self.contract.FAILURE_DETAIL_FIELD_MESSAGE, "message")
        self.assertEqual(self.contract.FAILURE_DETAIL_FIELD_STAGE, "stage")

        self.assertEqual(self.contract.FAILURE_CATEGORY_EXECUTION, "execution")
        self.assertEqual(
            self.contract.FAILURE_BOUNDARY_EXECUTION_ENTRYPOINT,
            "execution_entrypoint",
        )
        self.assertEqual(
            self.contract.FAILURE_STAGE_PARAMETER_ASSIGNMENT,
            "parameter_assignment",
        )
        self.assertEqual(
            self.contract.FAILURE_STAGE_DOCUMENT_SAVE,
            "document_save",
        )
        self.assertIn("FAILURE_STAGE_DOCUMENT_SAVE", self.contract.__all__)
        self.assertEqual(
            self.contract.FAILURE_STAGE_REFERENCE_TRAVERSAL,
            "reference_traversal",
        )
        self.assertEqual(
            self.contract.FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_CONTAINMENT,
            "reference_traversal_output_containment",
        )
        self.assertEqual(
            self.contract.FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_WRITE,
            "reference_traversal_output_write",
        )
        self.assertEqual(self.contract.FAILURE_CODE_RUNTIME_FAILURE, "runtime_failure")

    def test_invalid_required_strings_raise_deterministic_errors(self) -> None:
        invalid_cases = (
            ("boundary", ""),
            ("category", ""),
            ("code", ""),
            ("message", ""),
            ("boundary", 123),
        )

        for field_name, value in invalid_cases:
            with self.subTest(field_name=field_name, value=value):
                failure = _execution_failure()
                invalid_failure = self.contract.StructuredFailure(
                    boundary=value if field_name == "boundary" else failure.boundary,
                    category=value if field_name == "category" else failure.category,
                    code=value if field_name == "code" else failure.code,
                    message=value if field_name == "message" else failure.message,
                    stage=failure.stage,
                )

                with self.assertRaises(self.contract.FailureOutputContractError) as ctx:
                    self.contract.build_failure_output_payload(invalid_failure)

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn(field_name, message)

    def test_invalid_stage_values_raise_deterministic_errors(self) -> None:
        for stage in ("", 123):
            with self.subTest(stage=stage):
                failure = _execution_failure(stage=stage)

                with self.assertRaises(self.contract.FailureOutputContractError) as ctx:
                    self.contract.build_failure_output_payload(failure)

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("stage", message)

    def test_input_failure_is_not_mutated_and_is_frozen(self) -> None:
        failure = _execution_failure()
        original_values = (
            failure.boundary,
            failure.category,
            failure.code,
            failure.message,
            failure.stage,
        )

        self.contract.build_failure_output_payload(failure)

        self.assertEqual(
            (
                failure.boundary,
                failure.category,
                failure.code,
                failure.message,
                failure.stage,
            ),
            original_values,
        )
        with self.assertRaises(FrozenInstanceError):
            failure.message = "changed"

    def test_payload_is_independent_per_call(self) -> None:
        failure = _execution_failure()

        first = self.contract.build_failure_output_payload(failure)
        second = self.contract.build_failure_output_payload(failure)

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["failure"], second["failure"])

    def test_payload_is_compatible_with_canonical_json(self) -> None:
        payload = self.contract.build_failure_output_payload(_execution_failure())

        first = dumps_canonical(payload)
        second = dumps_canonical(payload)

        self.assertEqual(first, second)
        self.assertIn('"status":"failed"', first)
        self.assertIn('"failure":{', first)
        self.assertIn('"boundary":"execution_entrypoint"', first)
        self.assertIn('"stage":"parameter_assignment"', first)


if __name__ == "__main__":
    unittest.main()
