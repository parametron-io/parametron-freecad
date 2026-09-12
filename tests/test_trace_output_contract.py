from __future__ import annotations

import builtins
import importlib
import sys
import types
import unittest
from dataclasses import FrozenInstanceError, is_dataclass
from unittest import mock

from parametron_freecad.common.canonical_json import dumps_canonical

MODULE_NAME = "parametron_freecad.runtime.trace_output_contract"


def _import_trace_output_contract_module():
    return importlib.import_module(MODULE_NAME)


def _build_payload(contract, events):
    return contract.build_trace_output_payload(
        boundary=contract.TRACE_BOUNDARY_EXECUTION_ENTRYPOINT,
        operation=contract.TRACE_OPERATION_EXECUTE,
        status=contract.TRACE_STATUS_SUCCEEDED,
        events=events,
    )


class TraceOutputContractImportSafetyTests(unittest.TestCase):
    def test_import_succeeds_without_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
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
            module = _import_trace_output_contract_module()

        self.assertIsInstance(module, types.ModuleType)
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class TraceOutputContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_trace_output_contract_module()

    def test_public_api_exports_expected_names(self) -> None:
        expected_public_api = {
            "TRACE_OUTPUT_SCHEMA_VERSION",
            "TRACE_OUTPUT_KIND_RUNTIME_TRACE",
            "TRACE_FIELD_SCHEMA_VERSION",
            "TRACE_FIELD_KIND",
            "TRACE_FIELD_BOUNDARY",
            "TRACE_FIELD_OPERATION",
            "TRACE_FIELD_STATUS",
            "TRACE_FIELD_EVENTS",
            "TRACE_EVENT_FIELD_SEQUENCE",
            "TRACE_EVENT_FIELD_STAGE",
            "TRACE_EVENT_FIELD_STATE",
            "TRACE_EVENT_FIELD_MESSAGE",
            "TRACE_BOUNDARY_HEADLESS_CLI",
            "TRACE_BOUNDARY_EXECUTION_ENTRYPOINT",
            "TRACE_BOUNDARY_OBSERVATION_ENTRYPOINT",
            "TRACE_BOUNDARY_ENGINE_INVOCATION",
            "TRACE_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT",
            "TRACE_OPERATION_EXECUTE",
            "TRACE_OPERATION_OBSERVE",
            "TRACE_OPERATION_REFERENCE_TRAVERSAL",
            "TRACE_STATUS_STARTED",
            "TRACE_STATUS_SUCCEEDED",
            "TRACE_STATUS_FAILED",
            "TRACE_EVENT_STATE_STARTED",
            "TRACE_EVENT_STATE_SUCCEEDED",
            "TRACE_EVENT_STATE_FAILED",
            "TRACE_EVENT_STATE_SKIPPED",
            "TRACE_STAGE_ARGUMENT_VALIDATION",
            "TRACE_STAGE_FREECAD_RESOLUTION",
            "TRACE_STAGE_MANIFEST_LOADING",
            "TRACE_STAGE_MANIFEST_COMPATIBILITY",
            "TRACE_STAGE_MANIFEST_VALIDATION",
            "TRACE_STAGE_SOURCE_DOCUMENT_RESOLUTION",
            "TRACE_STAGE_DOCUMENT_OPEN",
            "TRACE_STAGE_PARAMETER_ASSIGNMENT",
            "TRACE_STAGE_RECOMPUTE",
            "TRACE_STAGE_ARTIFACT_EXPORT",
            "TRACE_STAGE_RESULT_WRITE",
            "TRACE_STAGE_OBSERVATION_OUTPUT",
            "TRACE_STAGE_REFERENCE_TRAVERSAL",
            "TRACE_STAGE_UNKNOWN",
            "TraceOutputContractError",
            "RuntimeTraceEvent",
            "build_trace_output_payload",
        }

        self.assertEqual(set(self.contract.__all__), expected_public_api)

    def test_key_constants_match_contract_values(self) -> None:
        self.assertEqual(self.contract.TRACE_OUTPUT_SCHEMA_VERSION, "1.0")
        self.assertEqual(
            self.contract.TRACE_OUTPUT_KIND_RUNTIME_TRACE,
            "runtime_trace",
        )
        self.assertEqual(self.contract.TRACE_FIELD_SCHEMA_VERSION, "schemaVersion")
        self.assertEqual(self.contract.TRACE_FIELD_KIND, "kind")
        self.assertEqual(self.contract.TRACE_FIELD_BOUNDARY, "boundary")
        self.assertEqual(self.contract.TRACE_FIELD_OPERATION, "operation")
        self.assertEqual(self.contract.TRACE_FIELD_STATUS, "status")
        self.assertEqual(self.contract.TRACE_FIELD_EVENTS, "events")
        self.assertEqual(self.contract.TRACE_EVENT_FIELD_SEQUENCE, "sequence")
        self.assertEqual(self.contract.TRACE_EVENT_FIELD_STAGE, "stage")
        self.assertEqual(self.contract.TRACE_EVENT_FIELD_STATE, "state")
        self.assertEqual(self.contract.TRACE_EVENT_FIELD_MESSAGE, "message")

    def test_error_type_is_value_error(self) -> None:
        self.assertTrue(issubclass(self.contract.TraceOutputContractError, ValueError))

    def test_runtime_trace_event_is_frozen_slot_backed_dataclass(self) -> None:
        event = self.contract.RuntimeTraceEvent(
            stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
            state=self.contract.TRACE_EVENT_STATE_SUCCEEDED,
        )

        self.assertTrue(is_dataclass(event))
        self.assertFalse(hasattr(event, "__dict__"))
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            event.stage = "other"

    def test_runtime_trace_event_accepts_supported_shapes(self) -> None:
        self.contract.RuntimeTraceEvent(
            stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
            state=self.contract.TRACE_EVENT_STATE_SUCCEEDED,
        )
        self.contract.RuntimeTraceEvent(
            stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
            state=self.contract.TRACE_EVENT_STATE_FAILED,
            message="deterministic diagnostic",
        )
        self.contract.RuntimeTraceEvent(
            stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
            state=self.contract.TRACE_EVENT_STATE_SUCCEEDED,
            message=None,
        )

    def test_build_trace_output_payload_returns_exact_minimal_success_shape(
        self,
    ) -> None:
        payload = _build_payload(
            self.contract,
            [
                self.contract.RuntimeTraceEvent(
                    stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
                    state=self.contract.TRACE_EVENT_STATE_SUCCEEDED,
                )
            ],
        )

        self.assertEqual(
            payload,
            {
                "schemaVersion": "1.0",
                "kind": "runtime_trace",
                "boundary": "execution_entrypoint",
                "operation": "execute",
                "status": "succeeded",
                "events": [
                    {
                        "sequence": 0,
                        "stage": "manifest_loading",
                        "state": "succeeded",
                        "message": None,
                    }
                ],
            },
        )

    def test_message_is_preserved_exactly(self) -> None:
        payload = _build_payload(
            self.contract,
            [
                self.contract.RuntimeTraceEvent(
                    stage=self.contract.TRACE_STAGE_PARAMETER_ASSIGNMENT,
                    state=self.contract.TRACE_EVENT_STATE_FAILED,
                    message="parameter assignment failed",
                )
            ],
        )

        self.assertEqual(
            payload["events"][0]["message"],
            "parameter assignment failed",
        )

    def test_event_order_is_preserved_with_deterministic_sequences(self) -> None:
        payload = _build_payload(
            self.contract,
            [
                self.contract.RuntimeTraceEvent(
                    stage=self.contract.TRACE_STAGE_ARGUMENT_VALIDATION,
                    state=self.contract.TRACE_EVENT_STATE_STARTED,
                ),
                self.contract.RuntimeTraceEvent(
                    stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
                    state=self.contract.TRACE_EVENT_STATE_SUCCEEDED,
                ),
                self.contract.RuntimeTraceEvent(
                    stage=self.contract.TRACE_STAGE_RECOMPUTE,
                    state=self.contract.TRACE_EVENT_STATE_SKIPPED,
                ),
            ],
        )

        self.assertEqual(
            payload["events"],
            [
                {
                    "sequence": 0,
                    "stage": "argument_validation",
                    "state": "started",
                    "message": None,
                },
                {
                    "sequence": 1,
                    "stage": "manifest_loading",
                    "state": "succeeded",
                    "message": None,
                },
                {
                    "sequence": 2,
                    "stage": "recompute",
                    "state": "skipped",
                    "message": None,
                },
            ],
        )

    def test_payload_is_compatible_with_canonical_json(self) -> None:
        payload = _build_payload(
            self.contract,
            [
                self.contract.RuntimeTraceEvent(
                    stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
                    state=self.contract.TRACE_EVENT_STATE_SUCCEEDED,
                )
            ],
        )

        serialized = dumps_canonical(payload)

        self.assertIn('"kind":"runtime_trace"', serialized)
        self.assertIn('"events":[{', serialized)
        self.assertNotIsInstance(
            payload["events"][0],
            self.contract.RuntimeTraceEvent,
        )

    def test_input_events_are_not_mutated(self) -> None:
        events = [
            self.contract.RuntimeTraceEvent(
                stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
                state=self.contract.TRACE_EVENT_STATE_STARTED,
            ),
            self.contract.RuntimeTraceEvent(
                stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
                state=self.contract.TRACE_EVENT_STATE_SUCCEEDED,
            ),
        ]
        before = list(events)

        _build_payload(self.contract, events)

        self.assertEqual(events, before)

    def test_repeated_calls_return_independent_payloads(self) -> None:
        events = [
            self.contract.RuntimeTraceEvent(
                stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
                state=self.contract.TRACE_EVENT_STATE_SUCCEEDED,
            )
        ]

        payload_a = _build_payload(self.contract, events)
        payload_b = _build_payload(self.contract, events)

        self.assertEqual(payload_a, payload_b)
        self.assertIsNot(payload_a, payload_b)
        self.assertIsNot(payload_a["events"], payload_b["events"])

        payload_a["events"][0]["stage"] = "mutated"
        self.assertEqual(payload_b["events"][0]["stage"], "manifest_loading")

    def test_invalid_top_level_fields_raise_deterministic_errors(self) -> None:
        valid_events = [
            self.contract.RuntimeTraceEvent(
                stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
                state=self.contract.TRACE_EVENT_STATE_SUCCEEDED,
            )
        ]
        invalid_cases = (
            ("boundary", ""),
            ("boundary", None),
            ("boundary", 123),
            ("operation", ""),
            ("operation", None),
            ("operation", 123),
            ("status", ""),
            ("status", None),
            ("status", 123),
        )

        for field_name, value in invalid_cases:
            with self.subTest(field_name=field_name, value=value):
                kwargs = {
                    "boundary": self.contract.TRACE_BOUNDARY_EXECUTION_ENTRYPOINT,
                    "operation": self.contract.TRACE_OPERATION_EXECUTE,
                    "status": self.contract.TRACE_STATUS_SUCCEEDED,
                    "events": valid_events,
                }
                kwargs[field_name] = value

                with self.assertRaises(self.contract.TraceOutputContractError) as ctx:
                    self.contract.build_trace_output_payload(**kwargs)

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn(field_name, message)

    def test_invalid_events_inputs_raise_deterministic_errors(self) -> None:
        invalid_cases = (
            [],
            (),
            "not-events",
            b"not-events",
            None,
            object(),
            [object()],
        )

        for events in invalid_cases:
            with self.subTest(events=events):
                with self.assertRaises(self.contract.TraceOutputContractError) as ctx:
                    self.contract.build_trace_output_payload(
                        boundary=self.contract.TRACE_BOUNDARY_EXECUTION_ENTRYPOINT,
                        operation=self.contract.TRACE_OPERATION_EXECUTE,
                        status=self.contract.TRACE_STATUS_SUCCEEDED,
                        events=events,
                    )

                self.assertNotIn("\n", str(ctx.exception))

    def test_invalid_event_fields_raise_deterministic_errors(self) -> None:
        invalid_cases = (
            ("stage", ""),
            ("stage", 123),
            ("state", ""),
            ("state", 123),
            ("message", ""),
            ("message", 123),
        )

        for field_name, value in invalid_cases:
            with self.subTest(field_name=field_name, value=value):
                event = self.contract.RuntimeTraceEvent(
                    stage=self.contract.TRACE_STAGE_MANIFEST_LOADING,
                    state=self.contract.TRACE_EVENT_STATE_SUCCEEDED,
                )
                object.__setattr__(event, field_name, value)

                with self.assertRaises(self.contract.TraceOutputContractError) as ctx:
                    _build_payload(self.contract, [event])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn(field_name, message)

    def test_trace_contract_does_not_expose_runtime_wiring_functions(self) -> None:
        self.assertFalse(hasattr(self.contract, "write_trace_output"))
        self.assertFalse(hasattr(self.contract, "write_trace_file"))
        self.assertFalse(hasattr(self.contract, "run_trace_entrypoint"))


if __name__ == "__main__":
    unittest.main()
