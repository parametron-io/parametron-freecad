from __future__ import annotations

import builtins
import importlib
import json
import os
import re
import sys
import tempfile
import types
import unittest
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from unittest import mock

from parametron_freecad.runtime.invocation_contract import (
    COMBINED_INVOCATION_UNSUPPORTED_MESSAGE,
    ENGINE_RUNTIME_INVOCATION_FIELDS,
    EXECUTION_INVOCATION_FIELDS,
    OBSERVATION_INVOCATION_FIELDS,
    PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES,
    SUPPORTED_ENGINE_INVOCATION_MODES,
)


class RuntimeInvocationImportSafetyTests(unittest.TestCase):
    def test_invocation_module_imports_without_freecad_modules(self) -> None:
        guarded_names = {"FreeCAD", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        for name in [
            "parametron_freecad.runtime.invocation",
            "parametron_freecad.runtime.entrypoints",
            *guarded_names,
        ]:
            sys.modules.pop(name, None)

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module("parametron_freecad.runtime.invocation")

        for public_name in [
            "RuntimeInvocationMode",
            "ExecutionInvocation",
            "ObservationInvocation",
            "EngineRuntimeInvocation",
            "EngineInvocationError",
            "EngineInvocationRequestError",
            "EngineInvocationExecutionError",
            "EngineInvocationObservationError",
            "run_engine_invocation",
        ]:
            self.assertTrue(hasattr(module, public_name), public_name)

        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("Import", sys.modules)
        self.assertNotIn("TechDrawGui", sys.modules)

    def test_invocation_all_exposes_only_engine_invocation_api(self) -> None:
        module = importlib.import_module("parametron_freecad.runtime.invocation")

        self.assertEqual(
            set(module.__all__),
            {
                "RuntimeInvocationMode",
                "ExecutionInvocation",
                "ObservationInvocation",
                "EngineRuntimeInvocation",
                "EngineInvocationError",
                "EngineInvocationRequestError",
                "EngineInvocationExecutionError",
                "EngineInvocationObservationError",
                "run_engine_invocation",
            },
        )

    def test_request_dataclasses_are_frozen(self) -> None:
        from parametron_freecad.runtime.invocation import (
            EngineRuntimeInvocation,
            ExecutionInvocation,
            ObservationInvocation,
        )

        execution = ExecutionInvocation(
            working_copy=Path("/fake/work"),
            manifest_path=Path("/fake/work/export_manifest_v1.json"),
            result_path=Path("/fake/work/result.json"),
        )
        observation = ObservationInvocation(
            document=object(),
            verification_data={"schemaVersion": "1.0"},
            working_copy_path="/fake/work",
            working_copy_sha256="abc123",
            output_directory="/fake/out",
        )
        invocation = EngineRuntimeInvocation(mode="execute", execution=execution)

        with self.assertRaises(FrozenInstanceError):
            execution.working_copy = Path("/other")  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            observation.working_copy_sha256 = "def456"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            invocation.mode = "observe"  # type: ignore[misc]

    def test_creating_request_objects_does_not_call_entrypoints_or_filesystem(self) -> None:
        from parametron_freecad.runtime import invocation

        class PathSentinel:
            def __fspath__(self) -> str:
                raise AssertionError("request construction must not touch filesystem paths")

        with mock.patch.object(
            invocation, "run_execution_entrypoint"
        ) as run_execution, mock.patch.object(
            invocation, "run_observation_entrypoint"
        ) as run_observation:
            execution = invocation.ExecutionInvocation(
                working_copy=Path("/fake/work"),
                manifest_path=Path("/fake/work/export_manifest_v1.json"),
                result_path=Path("/fake/work/result.json"),
                freecad_module=object(),
            )
            observation = invocation.ObservationInvocation(
                document=object(),
                verification_data={"schemaVersion": "1.0"},
                working_copy_path=PathSentinel(),
                working_copy_sha256="abc123",
                output_directory=PathSentinel(),
            )
            invocation.EngineRuntimeInvocation(mode="execute", execution=execution)
            invocation.EngineRuntimeInvocation(mode="observe", observation=observation)

        run_execution.assert_not_called()
        run_observation.assert_not_called()


class RuntimeInvocationEnvironmentNonRegressionTests(unittest.TestCase):
    def test_run_engine_invocation_does_not_read_environment_variables(self) -> None:
        from parametron_freecad.runtime import invocation

        request = invocation.EngineRuntimeInvocation(
            mode="execute",
            execution=_make_execution_invocation(invocation),
        )

        def guarded_getenv(*args, **kwargs):
            raise AssertionError("run_engine_invocation must not read environment variables")

        class GuardedEnviron(dict):
            def __getitem__(self, key):
                raise AssertionError("run_engine_invocation must not read os.environ")

            def get(self, key, default=None):
                raise AssertionError("run_engine_invocation must not read os.environ")

        with mock.patch("os.getenv", side_effect=guarded_getenv):
            with mock.patch("os.environ", GuardedEnviron(os.environ)):
                with mock.patch.object(
                    invocation, "run_execution_entrypoint", return_value=None
                ) as run_execution, mock.patch.object(
                    invocation, "run_observation_entrypoint"
                ) as run_observation:
                    invocation.run_engine_invocation(request)

        run_execution.assert_called_once()
        run_observation.assert_not_called()

    def test_observe_invocation_does_not_read_environment_variables(self) -> None:
        from parametron_freecad.runtime import invocation

        request = invocation.EngineRuntimeInvocation(
            mode="observe",
            observation=_make_observation_invocation(invocation),
        )

        def guarded_getenv(*args, **kwargs):
            raise AssertionError("observe invocation must not read environment variables")

        class GuardedEnviron(dict):
            def __getitem__(self, key):
                raise AssertionError("observe invocation must not read os.environ")

            def get(self, key, default=None):
                raise AssertionError("observe invocation must not read os.environ")

        with mock.patch("os.getenv", side_effect=guarded_getenv):
            with mock.patch("os.environ", GuardedEnviron(os.environ)):
                with mock.patch.object(
                    invocation, "run_execution_entrypoint"
                ) as run_execution, mock.patch.object(
                    invocation, "run_observation_entrypoint", return_value=None
                ) as run_observation:
                    invocation.run_engine_invocation(request)

        run_observation.assert_called_once()
        run_execution.assert_not_called()


class RuntimeInvocationDelegationTests(unittest.TestCase):
    def test_execute_without_traversal_request_preserves_engine_contract(self) -> None:
        from parametron_freecad.runtime import invocation

        execution = _make_execution_invocation(invocation)
        self.assertFalse(hasattr(execution, "reference_traversal_request"))
        request = invocation.EngineRuntimeInvocation(
            mode="execute",
            execution=execution,
        )

        with mock.patch.object(
            invocation, "run_execution_entrypoint", return_value=None
        ) as run_execution:
            invocation.run_engine_invocation(request)

        run_execution.assert_called_once_with(
            working_copy=execution.working_copy,
            manifest_path=execution.manifest_path,
            result_path=execution.result_path,
            freecad_module=execution.freecad_module,
            resolve_freecad_module=execution.resolve_freecad_module,
        )

    def test_execute_invocation_delegates_once_with_execution_fields(self) -> None:
        from parametron_freecad.runtime import invocation

        freecad_module = object()

        def resolver() -> object:
            raise AssertionError("resolver must only be passed through")

        execution = invocation.ExecutionInvocation(
            working_copy=Path("/fake/work"),
            manifest_path=Path("/fake/work/export_manifest_v1.json"),
            result_path=Path("/fake/work/result.json"),
            freecad_module=freecad_module,
            resolve_freecad_module=resolver,
        )
        request = invocation.EngineRuntimeInvocation(mode="execute", execution=execution)

        with mock.patch.object(
            invocation, "run_execution_entrypoint", return_value=None
        ) as run_execution, mock.patch.object(
            invocation, "run_observation_entrypoint"
        ) as run_observation:
            result = invocation.run_engine_invocation(request)

        self.assertIsNone(result)
        run_execution.assert_called_once_with(
            working_copy=Path("/fake/work"),
            manifest_path=Path("/fake/work/export_manifest_v1.json"),
            result_path=Path("/fake/work/result.json"),
            freecad_module=freecad_module,
            resolve_freecad_module=resolver,
        )
        run_observation.assert_not_called()
        self.assertEqual(request.execution, execution)

    def test_execute_invocation_does_not_reach_observation_helpers(self) -> None:
        from parametron_freecad.observation import observed_writer, verification_loader
        from parametron_freecad.runtime import entrypoints, invocation

        request = invocation.EngineRuntimeInvocation(
            mode="execute",
            execution=_make_execution_invocation(invocation),
        )

        with mock.patch.object(
            invocation, "run_execution_entrypoint", return_value=None
        ) as run_execution, mock.patch.object(
            invocation,
            "run_observation_entrypoint",
            side_effect=AssertionError("execute mode must not observe"),
        ) as run_observation, mock.patch.object(
            entrypoints,
            "run_document_observation_entrypoint",
            side_effect=AssertionError("execute mode must not open observation documents"),
        ) as run_document_observation, mock.patch.object(
            entrypoints,
            "generate_observed_output",
            side_effect=AssertionError("execute mode must not generate observed output"),
        ) as generate_observed, mock.patch.object(
            verification_loader,
            "load_parametron_verification_v1",
            side_effect=AssertionError("execute mode must not load verification data"),
        ) as load_verification, mock.patch.object(
            observed_writer,
            "write_observed_json",
            side_effect=AssertionError("execute mode must not write observed output"),
        ) as write_observed:
            result = invocation.run_engine_invocation(request)

        self.assertIsNone(result)
        run_execution.assert_called_once()
        run_observation.assert_not_called()
        run_document_observation.assert_not_called()
        generate_observed.assert_not_called()
        load_verification.assert_not_called()
        write_observed.assert_not_called()

    def test_observe_invocation_delegates_once_with_observation_fields(self) -> None:
        from parametron_freecad.runtime import invocation

        document = object()
        verification_data = {
            "schemaVersion": "1.0",
            "requested": {"parameters": [{"target": "Box.Length"}]},
        }
        original_verification_data = {
            "schemaVersion": "1.0",
            "requested": {"parameters": [{"target": "Box.Length"}]},
        }
        observation = invocation.ObservationInvocation(
            document=document,
            verification_data=verification_data,
            working_copy_path="/fake/work",
            working_copy_sha256="abc123",
            output_directory="/fake/out",
        )
        request = invocation.EngineRuntimeInvocation(mode="observe", observation=observation)

        with mock.patch.object(
            invocation, "run_execution_entrypoint"
        ) as run_execution, mock.patch.object(
            invocation, "run_observation_entrypoint", return_value=None
        ) as run_observation:
            result = invocation.run_engine_invocation(request)

        self.assertIsNone(result)
        run_observation.assert_called_once_with(
            document,
            verification_data,
            working_copy_path="/fake/work",
            working_copy_sha256="abc123",
            output_directory="/fake/out",
        )
        run_execution.assert_not_called()
        self.assertEqual(verification_data, original_verification_data)

    def test_observe_invocation_does_not_reach_execution_helpers(self) -> None:
        from parametron_freecad.execution import manifest_loader, result_writer
        from parametron_freecad.runtime import entrypoints, invocation

        request = invocation.EngineRuntimeInvocation(
            mode="observe",
            observation=_make_observation_invocation(invocation),
        )

        with mock.patch.object(
            invocation, "run_execution_entrypoint"
        ) as run_execution, mock.patch.object(
            invocation, "run_observation_entrypoint", return_value=None
        ) as run_observation, mock.patch.object(
            entrypoints,
            "load_export_manifest_v1",
            side_effect=AssertionError("observe mode must not load manifest"),
        ) as load_manifest, mock.patch.object(
            entrypoints,
            "run_document_observation_entrypoint",
            side_effect=AssertionError("observe mode must not open observation documents"),
        ) as run_document_observation, mock.patch.object(
            manifest_loader,
            "load_export_manifest_v1",
            side_effect=AssertionError("observe mode must not load manifest"),
        ) as load_manifest_module, mock.patch.object(
            result_writer,
            "write_success_result",
            side_effect=AssertionError("observe mode must not write execution result"),
        ) as write_result, mock.patch.object(
            entrypoints,
            "apply_parameter_assignments",
            side_effect=AssertionError("observe mode must not assign parameters"),
        ) as apply_assignments, mock.patch.object(
            entrypoints,
            "recompute_document",
            side_effect=AssertionError("observe mode must not recompute"),
        ) as recompute:
            result = invocation.run_engine_invocation(request)

        self.assertIsNone(result)
        run_observation.assert_called_once()
        run_execution.assert_not_called()
        load_manifest.assert_not_called()
        load_manifest_module.assert_not_called()
        write_result.assert_not_called()
        apply_assignments.assert_not_called()
        recompute.assert_not_called()
        run_document_observation.assert_not_called()


class RuntimeInvocationInvalidRequestTests(unittest.TestCase):
    def assert_request_error(
        self,
        request,
        expected_message: str,
    ) -> None:
        from parametron_freecad.runtime import entrypoints
        from parametron_freecad.runtime import invocation

        with mock.patch.object(
            invocation, "run_execution_entrypoint"
        ) as run_execution, mock.patch.object(
            invocation, "run_observation_entrypoint"
        ) as run_observation, mock.patch.object(
            entrypoints, "run_document_observation_entrypoint"
        ) as run_document_observation, mock.patch.object(
            entrypoints, "generate_observed_output"
        ) as generate_observed, self.assertRaises(
            invocation.EngineInvocationRequestError
        ) as excinfo:
            invocation.run_engine_invocation(request)

        self.assertEqual(str(excinfo.exception), expected_message)
        self.assertIsNone(excinfo.exception.__cause__)
        self.assertIsNone(re.search(r"0x[0-9a-fA-F]+", str(excinfo.exception)))
        run_execution.assert_not_called()
        run_observation.assert_not_called()
        run_document_observation.assert_not_called()
        generate_observed.assert_not_called()

    def test_execute_missing_execution_payload_fails_deterministically(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(mode="execute"),
            "execute mode requires an execution request",
        )

    def test_execute_with_both_payloads_fails_deterministically(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(
                mode="execute",
                execution=_make_execution_invocation(invocation),
                observation=_make_observation_invocation(invocation),
            ),
            "execute mode must not include an observation request",
        )

    def test_observe_missing_observation_payload_fails_deterministically(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(mode="observe"),
            "observe mode requires an observation request",
        )

    def test_observe_with_both_payloads_fails_deterministically(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(
                mode="observe",
                execution=_make_execution_invocation(invocation),
                observation=_make_observation_invocation(invocation),
            ),
            "observe mode must not include an execution request",
        )

    def test_observe_with_execution_payload_only_fails_deterministically(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(
                mode="observe",
                execution=_make_execution_invocation(invocation),
            ),
            "observe mode requires an observation request",
        )

    def test_unknown_mode_fails_deterministically(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(mode="export"),  # type: ignore[arg-type]
            "unsupported runtime invocation mode: export",
        )

    def test_combined_mode_is_rejected_as_planned_unsupported(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(mode="combined"),  # type: ignore[arg-type]
            COMBINED_INVOCATION_UNSUPPORTED_MESSAGE,
        )

    def test_combined_mode_with_payloads_is_rejected_before_delegation(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(
                mode="combined",  # type: ignore[arg-type]
                execution=_make_execution_invocation(invocation),
                observation=_make_observation_invocation(invocation),
            ),
            "combined execute+observe runtime invocation is not supported",
        )

    def test_unknown_mode_with_payloads_fails_before_delegation(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(
                mode="export",  # type: ignore[arg-type]
                execution=_make_execution_invocation(invocation),
                observation=_make_observation_invocation(invocation),
            ),
            "unsupported runtime invocation mode: export",
        )

    def test_verify_mode_fails_deterministically(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(mode="verify"),  # type: ignore[arg-type]
            "unsupported runtime invocation mode: verify",
        )

    def test_execute_and_observe_mode_fails_deterministically(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(mode="execute_and_observe"),  # type: ignore[arg-type]
            "unsupported runtime invocation mode: execute_and_observe",
        )

    def test_unexpected_mode_fails_deterministically(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assert_request_error(
            invocation.EngineRuntimeInvocation(mode="unexpected"),  # type: ignore[arg-type]
            "unsupported runtime invocation mode: unexpected",
        )


class RuntimeInvocationObservationPreservationTests(unittest.TestCase):
    class FakeObject:
        def __init__(self, **properties):
            for name, value in properties.items():
                setattr(self, name, value)

    class FakeDocument:
        def __init__(self):
            self._objects = {
                "Spreadsheet": RuntimeInvocationObservationPreservationTests.FakeObject(
                    Length=10.0,
                    Count=5,
                ),
                "Doc": RuntimeInvocationObservationPreservationTests.FakeObject(
                    Author="Jane"
                ),
                "Sketch001": RuntimeInvocationObservationPreservationTests.FakeObject(),
            }

        @property
        def Objects(self):  # noqa: N802 - mimic FreeCAD attribute name
            raise AssertionError("document.Objects must not be accessed")

        @property
        def Label(self):  # noqa: N802 - mimic FreeCAD attribute name
            raise AssertionError("document Label lookup must not be used")

        def getObject(self, name):  # noqa: N802 - mimic FreeCAD method name
            return self._objects.get(name)

    def _verification_data(self) -> dict:
        return {
            "observe": {
                "parameters": True,
                "metadata": True,
                "references": True,
                "components": True,
            },
            "observationContext": {
                "parameters": [
                    {"id": "p.length", "name": "Length", "groupName": "Spreadsheet"},
                    {"id": "p.count", "name": "Count", "groupName": "Spreadsheet"},
                ]
            },
            "expected": {
                "metadata": [
                    {"id": "m.author", "key": "Author", "ownerId": "Doc"},
                ],
                "references": [
                    {"kind": "constraint", "name": "Sketch001"},
                ],
            },
        }

    def test_observe_invocation_preserves_phase_2_requested_scope_output(self) -> None:
        from parametron_freecad.runtime import invocation

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            working_copy = Path(tmp_dir) / "work"
            working_copy.mkdir()
            document = self.FakeDocument()
            verification_data = self._verification_data()
            request = invocation.EngineRuntimeInvocation(
                mode="observe",
                observation=invocation.ObservationInvocation(
                    document=document,
                    verification_data=verification_data,
                    working_copy_path=working_copy,
                    working_copy_sha256="b" * 64,
                    output_directory=output_directory,
                ),
            )

            with mock.patch.object(
                invocation, "run_execution_entrypoint"
            ) as run_execution:
                invocation.run_engine_invocation(request)

            observed_path = output_directory / "parametron.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))

        run_execution.assert_not_called()
        self.assertEqual(decoded["schemaVersion"], "1.0")
        self.assertEqual(decoded["workingCopy"]["path"], str(working_copy))
        self.assertEqual(decoded["workingCopy"]["sha256"], "b" * 64)
        self.assertEqual(
            list(decoded["observation"].keys()),
            ["metadata", "parameters", "references"],
        )
        self.assertNotIn("components", decoded["observation"])
        self.assertEqual(
            [item["id"] for item in decoded["observation"]["parameters"]],
            ["p.length", "p.count"],
        )
        self.assertEqual(decoded["observation"]["metadata"][0]["id"], "m.author")
        self.assertEqual(decoded["observation"]["references"][0]["name"], "Sketch001")

    def test_observe_invocation_failure_wraps_real_observation_error_with_cause_chain(
        self,
    ) -> None:
        from parametron_freecad.observation.parameter_observation import (
            ParameterObservationObjectNotFoundError,
        )
        from parametron_freecad.runtime import entrypoints, invocation

        class EmptyDocument:
            @property
            def Objects(self):  # noqa: N802 - mimic FreeCAD attribute name
                raise AssertionError("document.Objects must not be accessed")

            def getObject(self, name):  # noqa: N802 - mimic FreeCAD method name
                del name
                return None

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            request = invocation.EngineRuntimeInvocation(
                mode="observe",
                observation=invocation.ObservationInvocation(
                    document=EmptyDocument(),
                    verification_data={
                        "observe": {"parameters": True},
                        "observationContext": {
                            "parameters": [
                                {
                                    "id": "p.length",
                                    "name": "Length",
                                    "groupName": "Spreadsheet",
                                }
                            ]
                        },
                    },
                    working_copy_path=Path(tmp_dir) / "work",
                    working_copy_sha256="c" * 64,
                    output_directory=output_directory,
                ),
            )

            with mock.patch.object(
                invocation, "run_execution_entrypoint"
            ) as run_execution, self.assertRaises(
                invocation.EngineInvocationObservationError
            ) as excinfo:
                invocation.run_engine_invocation(request)

            observed_path = output_directory / "parametron.observed.json"
            observed_path_exists = observed_path.exists()

        run_execution.assert_not_called()
        self.assertFalse(observed_path_exists)
        observation_entrypoint_error = excinfo.exception.__cause__
        self.assertIsInstance(
            observation_entrypoint_error,
            entrypoints.ObservationEntrypointError,
        )
        observed_output_error = observation_entrypoint_error.__cause__
        self.assertIsInstance(observed_output_error, entrypoints.ObservedOutputError)
        self.assertIsInstance(
            observed_output_error.__cause__,
            ParameterObservationObjectNotFoundError,
        )


class RuntimeInvocationFailureWrappingTests(unittest.TestCase):
    def _assert_failed_result(
        self,
        result_path: Path,
        *,
        stage: str,
        category: str = "execution",
        code: str = "runtime_failure",
    ) -> None:
        self.assertTrue(result_path.exists())
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(payload["status"], "failed")
        failure = payload["failure"]
        self.assertEqual(failure["boundary"], "execution_entrypoint")
        self.assertEqual(failure["category"], category)
        self.assertEqual(failure["code"], code)
        self.assertEqual(failure["stage"], stage)
        self.assertEqual(failure["message"], " ".join(failure["message"].split()))

    def test_execution_entrypoint_error_is_wrapped_with_cause(self) -> None:
        from parametron_freecad.runtime import entrypoints, invocation

        original = entrypoints.ExecutionEntrypointError("fake execution failure")

        with mock.patch.object(
            invocation, "run_execution_entrypoint", side_effect=original
        ), mock.patch.object(
            invocation, "run_observation_entrypoint"
        ) as run_observation, self.assertRaises(
            invocation.EngineInvocationExecutionError
        ) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(
                    mode="execute",
                    execution=_make_execution_invocation(invocation),
                )
            )

        self.assertEqual(str(excinfo.exception), "fake execution failure")
        self.assertIs(excinfo.exception.__cause__, original)
        self.assertNotIn("Traceback", str(excinfo.exception))
        self.assertNotRegex(str(excinfo.exception), r"observ|verif|combined")
        run_observation.assert_not_called()

    def test_freecad_unavailable_error_is_wrapped_as_execution_error(self) -> None:
        from parametron_freecad.runtime import entrypoints, invocation

        original = entrypoints.FreeCADUnavailableEntrypointError(
            "FreeCAD module is not available"
        )

        with mock.patch.object(
            invocation, "run_execution_entrypoint", side_effect=original
        ), mock.patch.object(
            invocation, "run_observation_entrypoint"
        ) as run_observation, self.assertRaises(
            invocation.EngineInvocationExecutionError
        ) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(
                    mode="execute",
                    execution=_make_execution_invocation(invocation),
                )
            )

        self.assertEqual(str(excinfo.exception), "FreeCAD module is not available")
        self.assertIs(excinfo.exception.__cause__, original)
        self.assertNotIn("Traceback", str(excinfo.exception))
        self.assertNotRegex(str(excinfo.exception), r"observ|verif|combined")
        run_observation.assert_not_called()

    def test_observation_entrypoint_error_is_wrapped_with_cause(self) -> None:
        from parametron_freecad.runtime import entrypoints, invocation

        original = entrypoints.ObservationEntrypointError("fake observation failure")

        with mock.patch.object(
            invocation, "run_execution_entrypoint"
        ) as run_execution, mock.patch.object(
            invocation, "run_observation_entrypoint", side_effect=original
        ), self.assertRaises(
            invocation.EngineInvocationObservationError
        ) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(
                    mode="observe",
                    observation=_make_observation_invocation(invocation),
                )
            )

        self.assertEqual(str(excinfo.exception), "fake observation failure")
        self.assertIs(excinfo.exception.__cause__, original)
        self.assertNotIn("Traceback", str(excinfo.exception))
        run_execution.assert_not_called()

    def test_execute_invocation_preserves_failed_result_written_by_entrypoint(self) -> None:
        from parametron_freecad.runtime import entrypoints, invocation

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            manifest_path = working_copy / "missing_manifest.json"
            result_path = working_copy / "result.json"

            with self.assertRaises(invocation.EngineInvocationExecutionError) as excinfo:
                invocation.run_engine_invocation(
                    invocation.EngineRuntimeInvocation(
                        mode="execute",
                        execution=invocation.ExecutionInvocation(
                            working_copy=working_copy,
                            manifest_path=manifest_path,
                            result_path=result_path,
                            freecad_module=object(),
                        ),
                    )
                )

            self._assert_failed_result(result_path, stage="manifest_loading")

        self.assertIsInstance(
            excinfo.exception.__cause__,
            entrypoints.ExecutionEntrypointError,
        )
        self.assertNotIn("Traceback", str(excinfo.exception))


class RuntimeInvocationContractAlignmentTests(unittest.TestCase):
    def test_supported_modes_match_contract(self) -> None:
        from parametron_freecad.runtime import invocation

        for mode in SUPPORTED_ENGINE_INVOCATION_MODES:
            with self.subTest(mode=mode):
                if mode == "execute":
                    request = invocation.EngineRuntimeInvocation(
                        mode="execute",
                        execution=_make_execution_invocation(invocation),
                    )
                    with mock.patch.object(
                        invocation, "run_execution_entrypoint", return_value=None
                    ) as run_execution, mock.patch.object(
                        invocation, "run_observation_entrypoint"
                    ) as run_observation:
                        invocation.run_engine_invocation(request)

                    run_execution.assert_called_once()
                    run_observation.assert_not_called()
                    continue

                request = invocation.EngineRuntimeInvocation(
                    mode="observe",
                    observation=_make_observation_invocation(invocation),
                )
                with mock.patch.object(
                    invocation, "run_execution_entrypoint"
                ) as run_execution, mock.patch.object(
                    invocation, "run_observation_entrypoint", return_value=None
                ) as run_observation:
                    invocation.run_engine_invocation(request)

                run_observation.assert_called_once()
                run_execution.assert_not_called()

    def test_planned_unsupported_combined_mode_matches_contract(self) -> None:
        from parametron_freecad.runtime import invocation

        self.assertEqual(PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES, ("combined",))

        with mock.patch.object(
            invocation, "run_execution_entrypoint"
        ) as run_execution, mock.patch.object(
            invocation, "run_observation_entrypoint"
        ) as run_observation, self.assertRaises(
            invocation.EngineInvocationRequestError
        ) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(mode="combined")  # type: ignore[arg-type]
            )

        self.assertEqual(str(excinfo.exception), COMBINED_INVOCATION_UNSUPPORTED_MESSAGE)
        run_execution.assert_not_called()
        run_observation.assert_not_called()

    def test_unknown_mode_not_in_contract_raises_before_delegation(self) -> None:
        from parametron_freecad.runtime import invocation

        unknown_mode = "export"
        self.assertNotIn(unknown_mode, SUPPORTED_ENGINE_INVOCATION_MODES)
        self.assertNotIn(unknown_mode, PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES)

        with mock.patch.object(
            invocation, "run_execution_entrypoint"
        ) as run_execution, mock.patch.object(
            invocation, "run_observation_entrypoint"
        ) as run_observation, self.assertRaises(
            invocation.EngineInvocationRequestError
        ) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(mode=unknown_mode)  # type: ignore[arg-type]
            )

        self.assertEqual(
            str(excinfo.exception),
            f"unsupported runtime invocation mode: {unknown_mode}",
        )
        run_execution.assert_not_called()
        run_observation.assert_not_called()

    def test_request_dataclass_fields_match_contract(self) -> None:
        from parametron_freecad.runtime.invocation import (
            EngineRuntimeInvocation,
            ExecutionInvocation,
            ObservationInvocation,
        )

        def field_names(cls) -> tuple[str, ...]:
            return tuple(field.name for field in fields(cls))

        self.assertEqual(field_names(EngineRuntimeInvocation), ENGINE_RUNTIME_INVOCATION_FIELDS)
        self.assertEqual(field_names(ExecutionInvocation), EXECUTION_INVOCATION_FIELDS)
        self.assertEqual(field_names(ObservationInvocation), OBSERVATION_INVOCATION_FIELDS)


class RuntimeInvocationBoundaryTests(unittest.TestCase):
    def test_invocation_module_does_not_expose_out_of_scope_runtime_apis(self) -> None:
        from parametron_freecad.runtime import invocation

        public_names = set(invocation.__all__)
        forbidden_exact_names = {
            "run_observation_cli",
            "run_combined_invocation",
            "CombinedInvocation",
            "load_verification_file",
            "load_parametron_verification_json",
            "compute_working_copy_sha256",
            "observe_component",
            "observe_components",
            "VerificationDecision",
            "run_verification_decision",
            "evaluate_checks",
            "compare_expected_observed",
            "make_verification_decision",
            "run_capture",
            "run_gui",
            "capture_gui",
            "capture_view",
        }

        self.assertTrue(public_names.isdisjoint(forbidden_exact_names))
        for forbidden_fragment in [
            "cli",
            "component",
            "evaluate",
            "decision",
            "compare",
            "expected",
            "gui",
            "capture",
        ]:
            self.assertFalse(
                any(forbidden_fragment in name.lower() for name in public_names),
                forbidden_fragment,
            )

    def test_invocation_all_does_not_expose_combined_or_verification_public_api(self) -> None:
        from parametron_freecad.runtime import invocation

        public_names = set(invocation.__all__)
        for forbidden_name in [
            "run_combined_invocation",
            "CombinedInvocation",
            "VerificationDecision",
            "run_verification_decision",
            "evaluate_checks",
            "compare_expected_observed",
            "run_capture",
            "run_gui",
        ]:
            self.assertNotIn(forbidden_name, public_names)
            self.assertFalse(hasattr(invocation, forbidden_name), forbidden_name)


class RuntimeInvocationReloadCompatibilityTests(unittest.TestCase):
    """Regression coverage for entrypoint module reload sensitivity.

    After importing invocation, replacing the entrypoints module in sys.modules
    (simulating a reload) must not strand the dispatch on the stale original
    callable.  Invocation-level patch points (monkeypatching the invocation
    module's own attribute) must still take priority over the current module.
    """

    _ENTRYPOINTS_MODULE = "parametron_freecad.runtime.entrypoints"

    def _make_execution_request(self):
        from parametron_freecad.runtime import invocation
        return invocation.EngineRuntimeInvocation(
            mode="execute",
            execution=invocation.ExecutionInvocation(
                working_copy=Path("/fake/work"),
                manifest_path=Path("/fake/work/export_manifest_v1.json"),
                result_path=Path("/fake/work/result.json"),
            ),
        )

    def _make_observation_request(self):
        from parametron_freecad.runtime import invocation
        return invocation.EngineRuntimeInvocation(
            mode="observe",
            observation=invocation.ObservationInvocation(
                document=object(),
                verification_data={"schemaVersion": "1.0"},
                working_copy_path="/fake/work",
                working_copy_sha256="abc123",
                output_directory="/fake/out",
            ),
        )

    def test_execute_uses_current_entrypoints_module_after_reload(self) -> None:
        """After the entrypoints module is replaced in sys.modules, dispatch uses
        the new module's callable, not the stale function captured at import time."""
        from parametron_freecad.runtime import invocation

        calls: list[str] = []

        def fake_run_execution(**kwargs):
            calls.append("execute_from_reloaded")

        # Simulate reload: replace the entrypoints module with a fake that has
        # a different run_execution_entrypoint.
        fake_module = types.ModuleType(self._ENTRYPOINTS_MODULE)
        fake_module.run_execution_entrypoint = fake_run_execution  # type: ignore[attr-defined]

        original_module = sys.modules.get(self._ENTRYPOINTS_MODULE)
        try:
            sys.modules[self._ENTRYPOINTS_MODULE] = fake_module
            invocation.run_engine_invocation(self._make_execution_request())
        finally:
            if original_module is not None:
                sys.modules[self._ENTRYPOINTS_MODULE] = original_module
            else:
                sys.modules.pop(self._ENTRYPOINTS_MODULE, None)

        self.assertEqual(calls, ["execute_from_reloaded"])

    def test_observe_uses_current_entrypoints_module_after_reload(self) -> None:
        """After entrypoints reload, observe dispatch uses the new module's callable."""
        from parametron_freecad.runtime import invocation

        calls: list[str] = []

        def fake_run_observation(*args, **kwargs):
            calls.append("observe_from_reloaded")

        fake_module = types.ModuleType(self._ENTRYPOINTS_MODULE)
        fake_module.run_observation_entrypoint = fake_run_observation  # type: ignore[attr-defined]
        # Observation error check also uses the module — provide the original class.
        from parametron_freecad.runtime.entrypoints import ObservationEntrypointError
        fake_module.ObservationEntrypointError = ObservationEntrypointError  # type: ignore[attr-defined]

        original_module = sys.modules.get(self._ENTRYPOINTS_MODULE)
        try:
            sys.modules[self._ENTRYPOINTS_MODULE] = fake_module
            invocation.run_engine_invocation(self._make_observation_request())
        finally:
            if original_module is not None:
                sys.modules[self._ENTRYPOINTS_MODULE] = original_module
            else:
                sys.modules.pop(self._ENTRYPOINTS_MODULE, None)

        self.assertEqual(calls, ["observe_from_reloaded"])

    def test_invocation_level_execution_patch_is_honored(self) -> None:
        """Patching run_execution_entrypoint on the invocation module takes
        priority over the current entrypoints module callable."""
        from parametron_freecad.runtime import invocation

        calls: list[str] = []

        def patched_execution(**kwargs):
            calls.append("patched_execute")

        with mock.patch.object(invocation, "run_execution_entrypoint", patched_execution):
            invocation.run_engine_invocation(self._make_execution_request())

        self.assertEqual(calls, ["patched_execute"])

    def test_invocation_level_observation_patch_is_honored(self) -> None:
        """Patching run_observation_entrypoint on the invocation module takes
        priority over the current entrypoints module callable."""
        from parametron_freecad.runtime import invocation

        calls: list[str] = []

        def patched_observation(*args, **kwargs):
            calls.append("patched_observe")

        with mock.patch.object(invocation, "run_observation_entrypoint", patched_observation):
            invocation.run_engine_invocation(self._make_observation_request())

        self.assertEqual(calls, ["patched_observe"])

    def test_invocation_level_execution_patch_excludes_current_module_lookup(self) -> None:
        """When invocation-level patch is active, the current entrypoints module
        callable is NOT called, even if it differs from the original."""
        from parametron_freecad.runtime import invocation

        current_module_calls: list[str] = []

        def current_module_fn(**kwargs):
            current_module_calls.append("current_module")

        def invocation_level_patch(**kwargs):
            pass  # invocation-level patch; current module must not be called

        fake_module = types.ModuleType(self._ENTRYPOINTS_MODULE)
        fake_module.run_execution_entrypoint = current_module_fn  # type: ignore[attr-defined]

        original_module = sys.modules.get(self._ENTRYPOINTS_MODULE)
        try:
            sys.modules[self._ENTRYPOINTS_MODULE] = fake_module
            with mock.patch.object(invocation, "run_execution_entrypoint", invocation_level_patch):
                invocation.run_engine_invocation(self._make_execution_request())
        finally:
            if original_module is not None:
                sys.modules[self._ENTRYPOINTS_MODULE] = original_module
            else:
                sys.modules.pop(self._ENTRYPOINTS_MODULE, None)

        self.assertEqual(current_module_calls, [])

    def test_execution_error_wrapping_preserved_after_reload(self) -> None:
        """Error wrapping from the stale ExecutionEntrypointError class still works
        after the entrypoints module is replaced in sys.modules."""
        from parametron_freecad.runtime import invocation
        from parametron_freecad.runtime.entrypoints import ExecutionEntrypointError

        original_error = ExecutionEntrypointError("stale error class error")

        def fail_execution(**kwargs):
            raise original_error

        with mock.patch.object(
            invocation, "run_execution_entrypoint", fail_execution
        ), self.assertRaises(invocation.EngineInvocationExecutionError) as excinfo:
            invocation.run_engine_invocation(self._make_execution_request())

        self.assertIs(excinfo.exception.__cause__, original_error)

    def test_observation_error_wrapping_preserved_after_reload(self) -> None:
        """Error wrapping from the stale ObservationEntrypointError class still works."""
        from parametron_freecad.runtime import invocation
        from parametron_freecad.runtime.entrypoints import ObservationEntrypointError

        original_error = ObservationEntrypointError("stale observation error")

        def fail_observation(*args, **kwargs):
            raise original_error

        with mock.patch.object(
            invocation, "run_observation_entrypoint", fail_observation
        ), self.assertRaises(invocation.EngineInvocationObservationError) as excinfo:
            invocation.run_engine_invocation(self._make_observation_request())

        self.assertIs(excinfo.exception.__cause__, original_error)


def _make_execution_invocation(invocation_module):
    return invocation_module.ExecutionInvocation(
        working_copy=Path("/fake/work"),
        manifest_path=Path("/fake/work/export_manifest_v1.json"),
        result_path=Path("/fake/work/result.json"),
    )


def _make_observation_invocation(invocation_module):
    return invocation_module.ObservationInvocation(
        document=object(),
        verification_data={"schemaVersion": "1.0"},
        working_copy_path="/fake/work",
        working_copy_sha256="abc123",
        output_directory="/fake/out",
    )


if __name__ == "__main__":
    unittest.main()
