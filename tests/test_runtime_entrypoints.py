from __future__ import annotations

import builtins
import copy
import hashlib
import importlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from parametron_freecad.common.paths import WORKING_COPY_DIR_NAME
from parametron_freecad.execution.manifest_loader import LoadedManifest
from parametron_freecad.execution.manifest_validation import (
    ManifestDiagnostic,
    ManifestValidationResult,
)
from parametron_freecad.runtime.reference_traversal_output import (
    RawReferenceTraversalEdge as CanonicalReferenceTraversalEdge,
    RawReferenceTraversalNode as CanonicalReferenceTraversalNode,
)


class RuntimeEntrypointImportSafetyTests(unittest.TestCase):
    def test_entrypoint_module_imports_without_freecad_modules(self) -> None:
        guarded_names = {"FreeCAD", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        for name in [
            "parametron_freecad.runtime.entrypoints",
            *guarded_names,
        ]:
            sys.modules.pop(name, None)

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in guarded_names:
                raise AssertionError(f"{name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module("parametron_freecad.runtime.entrypoints")

        self.assertTrue(hasattr(module, "run_execution_entrypoint"))
        self.assertTrue(hasattr(module, "run_observation_entrypoint"))
        self.assertTrue(hasattr(module, "run_document_observation_entrypoint"))
        self.assertTrue(hasattr(module, "ExecutionEntrypointError"))
        self.assertTrue(hasattr(module, "FreeCADUnavailableEntrypointError"))
        self.assertTrue(hasattr(module, "ObservationEntrypointError"))
        self.assertIn("run_document_observation_entrypoint", module.__all__)
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("Import", sys.modules)
        self.assertNotIn("TechDrawGui", sys.modules)

    def test_entrypoint_import_does_not_expose_verification_decision_api(self) -> None:
        module = importlib.import_module("parametron_freecad.runtime.entrypoints")

        public_names = set(module.__all__)
        self.assertNotIn("run_verification_decision_entrypoint", public_names)
        self.assertNotIn("VerificationDecisionEntrypointError", public_names)
        self.assertFalse(any("decision" in name.lower() for name in public_names))


class RuntimeExecutionEntrypointTests(unittest.TestCase):
    def _make_manifest_data(self) -> dict:
        return {
            "schemaVersion": "1.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [
                {"target": "Box.Length", "value": 10.0, "valueKind": "scalar"},
            ],
            "outputs": [
                {"id": "part", "format": "step", "path": "exports/part.step"},
                {"id": "report", "format": "csv", "path": "exports/report.csv"},
                {"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"},
            ],
        }

    def _assert_failed_result(
        self,
        result_path: Path,
        *,
        stage: str,
        category: str = "execution",
        code: str = "runtime_failure",
        substring: str | None = None,
    ) -> None:
        self.assertTrue(result_path.exists())
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(payload["status"], "failed")
        self.assertNotIn("artifacts", payload)
        failure = payload["failure"]
        self.assertEqual(failure["boundary"], "execution_entrypoint")
        self.assertEqual(failure["category"], category)
        self.assertEqual(failure["code"], code)
        self.assertEqual(failure["stage"], stage)
        self.assertEqual(failure["message"], " ".join(failure["message"].split()))
        self.assertNotIn("Traceback", failure["message"])
        if substring is not None:
            self.assertIn(substring, failure["message"])

    def _valid_manifest_patches(
        self,
        entrypoints,
        *,
        working_copy: Path,
        manifest_path: Path,
        source_path: Path,
        manifest_data: dict | None = None,
    ):
        loaded_manifest = LoadedManifest(
            path=manifest_path,
            data=manifest_data if manifest_data is not None else self._make_manifest_data(),
        )
        return (
            mock.patch.object(
                entrypoints,
                "load_export_manifest_v1",
                return_value=loaded_manifest,
            ),
            mock.patch.object(
                entrypoints,
                "validate_export_manifest_v1",
                return_value=ManifestValidationResult(diagnostics=()),
            ),
            mock.patch.object(
                entrypoints,
                "resolve_source_document_path",
                return_value=source_path,
            ),
        )

    def test_execution_entrypoint_orchestrates_phase_1_pipeline_in_order(self) -> None:
        from parametron_freecad.runtime import entrypoints

        calls: list[tuple] = []
        working_copy = Path("/tmp/working-copy").resolve()
        manifest_path = working_copy / "export_manifest_v1.json"
        result_path = working_copy / "result.json"
        source_path = working_copy / "model.FCStd"
        freecad_module = object()
        document = object()
        manifest_data = self._make_manifest_data()
        loaded_manifest = LoadedManifest(path=manifest_path, data=manifest_data)

        def fake_load(path):
            calls.append(("load", path))
            return loaded_manifest

        def fake_validate(data):
            calls.append(("validate", data))
            return ManifestValidationResult(diagnostics=())

        def fake_resolve(working, source_document):
            calls.append(("resolve-source", working, source_document))
            return source_path

        @contextmanager
        def fake_opened_freecad_document(received_freecad_module, received_source_path):
            calls.append(("open", received_freecad_module, received_source_path))
            yield entrypoints.OpenedDocument(
                path=received_source_path,
                document=document,
                document_name="FakeDoc",
            )
            calls.append(("close",))

        def fake_apply(received_document, assignments):
            calls.append(("assign", received_document, assignments))

        def fake_recompute(received_document):
            calls.append(("recompute", received_document))

        def fake_save(received_document):
            calls.append(("save", received_document))

        def fake_export_step(received_document, outputs, *, working_copy):
            calls.append(("step", received_document, outputs, working_copy))

        def fake_export_csv(received_document, outputs, *, working_copy):
            calls.append(("csv", received_document, outputs, working_copy))

        def fake_export_pdf(received_document, outputs, *, working_copy):
            calls.append(("pdf", received_document, outputs, working_copy))

        def fake_write_result(received_result_path, outputs):
            calls.append(("result", received_result_path, outputs))

        dependencies = entrypoints._ExecutionEntrypointDependencies(
            apply_parameter_assignments=fake_apply,
            recompute_document=fake_recompute,
            save_document=fake_save,
            export_step_artifacts=fake_export_step,
            export_csv_artifacts=fake_export_csv,
            export_pdf_artifacts=fake_export_pdf,
            opened_freecad_document=fake_opened_freecad_document,
            write_success_result=fake_write_result,
        )

        with mock.patch.object(entrypoints, "load_export_manifest_v1", side_effect=fake_load), mock.patch.object(
            entrypoints, "validate_export_manifest_v1", side_effect=fake_validate
        ), mock.patch.object(
            entrypoints, "resolve_source_document_path", side_effect=fake_resolve
        ):
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=result_path,
                freecad_module=freecad_module,
                _dependencies=dependencies,
            )

        self.assertEqual(
            calls,
            [
                ("load", manifest_path),
                ("validate", manifest_data),
                ("resolve-source", working_copy, "model.FCStd"),
                ("open", freecad_module, source_path),
                ("assign", document, manifest_data["parameterAssignments"]),
                ("recompute", document),
                ("save", document),
                ("step", document, manifest_data["outputs"], working_copy),
                ("csv", document, manifest_data["outputs"], working_copy),
                ("pdf", document, manifest_data["outputs"], working_copy),
                ("close",),
                ("result", result_path, manifest_data["outputs"]),
            ],
        )

    def test_zero_derived_outputs_still_save_and_observe_then_write_empty_artifacts(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / "model.FCStd"
            source.write_bytes(b"prepared working copy")
            output = working / "output"
            output.mkdir()
            request = working / "observation.json"
            request.write_text("{}", encoding="utf-8")
            result = working / "result.json"
            document = object()
            calls: list[str] = []

            @contextmanager
            def opened(module, path):
                self.assertIsNotNone(module)
                self.assertEqual(path, source)
                calls.append("open")
                try:
                    yield entrypoints.OpenedDocument(path, document, "Doc")
                finally:
                    calls.append("close")

            step = mock.Mock(side_effect=lambda *a, **k: calls.append("step"))
            csv = mock.Mock(side_effect=lambda *a, **k: calls.append("csv"))
            pdf = mock.Mock(side_effect=lambda *a, **k: calls.append("pdf"))
            deps = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=lambda received, assignments: (
                    self.assertIs(received, document),
                    self.assertEqual(assignments, []),
                    calls.append("assign"),
                ),
                recompute_document=lambda received: (
                    self.assertIs(received, document), calls.append("recompute")
                ),
                save_document=lambda received: (
                    self.assertIs(received, document), calls.append("save")
                ),
                export_step_artifacts=step,
                export_csv_artifacts=csv,
                export_pdf_artifacts=pdf,
                opened_freecad_document=opened,
                write_success_result=entrypoints.write_success_result,
                run_observation_entrypoint=lambda received, *a, **k: (
                    self.assertIs(received, document), calls.append("observation")
                ),
            )
            manifest_data = self._make_manifest_data()
            manifest_data["parameterAssignments"] = []
            manifest_data["outputs"] = []
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working,
                manifest_path=working / "manifest.json",
                source_path=source,
                manifest_data=manifest_data,
            )
            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints, "load_observation_request", return_value={"observe": {}}
            ):
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=working / "manifest.json",
                    result_path=result,
                    output_directory=output,
                    observation_request_path=request,
                    freecad_module=object(),
                    _dependencies=deps,
                )

            self.assertEqual(
                calls,
                ["open", "assign", "recompute", "save", "step", "csv", "pdf", "observation", "close"],
            )
            for exporter in (step, csv, pdf):
                exporter.assert_called_once_with(document, [], working_copy=working)
            self.assertEqual(
                json.loads(result.read_text(encoding="utf-8"))["artifacts"], []
            )
            self.assertEqual(list(output.iterdir()), [])

    def test_save_failure_is_structured_and_short_circuits_all_later_work(self) -> None:
        from parametron_freecad.execution.document_save import save_document
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / "model.FCStd"
            source.write_bytes(b"prepared working copy")
            result = working / "result.json"
            observation_request = working / "observation.json"
            observation_request.write_text("{}", encoding="utf-8")
            traversal_request = working / "traversal.json"
            traversal_request.write_text("{}", encoding="utf-8")
            events: list[str] = []
            original = RuntimeError("disk full")

            class Document:
                save_calls = 0

                def save(self):
                    self.save_calls += 1
                    events.append("save")
                    raise original

            document = Document()

            @contextmanager
            def opened(*args):
                del args
                events.append("open")
                try:
                    yield entrypoints.OpenedDocument(source, document, "Doc")
                finally:
                    events.append("close")

            later = mock.Mock(side_effect=AssertionError("later operation called"))
            success = mock.Mock(side_effect=AssertionError("success writer called"))
            deps = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=lambda *a: events.append("assign"),
                recompute_document=lambda *a: events.append("recompute"),
                save_document=save_document,
                export_step_artifacts=later,
                export_csv_artifacts=later,
                export_pdf_artifacts=later,
                opened_freecad_document=opened,
                write_success_result=success,
                run_observation_entrypoint=later,
                run_reference_traversal=later,
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working,
                manifest_path=working / "manifest.json",
                source_path=source,
            )
            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints, "load_observation_request", return_value={"observe": {}}
            ), mock.patch.object(
                entrypoints,
                "load_reference_traversal_request",
                return_value=entrypoints.ReferenceTraversalRequest(schema_version="1.0", external_targets=()),
            ), self.assertRaises(
                entrypoints.ExecutionEntrypointError
            ) as caught:
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=working / "manifest.json",
                    result_path=result,
                    output_directory=working,
                    observation_request_path=observation_request,
                    reference_traversal_request_path=traversal_request,
                    freecad_module=object(),
                    _dependencies=deps,
                )

            typed = caught.exception.__cause__
            self.assertIsInstance(typed, entrypoints.DocumentSaveError)
            self.assertIs(typed.__cause__, original)
            self.assertEqual(document.save_calls, 1)
            self.assertEqual(events, ["open", "assign", "recompute", "save", "close"])
            later.assert_not_called()
            success.assert_not_called()
            self._assert_failed_result(
                result,
                stage="document_save",
                category="execution",
                code="runtime_failure",
                substring="document save raised an exception: disk full",
            )

    def test_save_receives_exact_document_opened_from_validated_source(self) -> None:
        from parametron_freecad.runtime import entrypoints

        working = Path("/tmp/prepared-working-copy").resolve()
        source = working / "model.FCStd"
        document = object()
        saved: list[object] = []

        @contextmanager
        def opened(module, path):
            self.assertIsNotNone(module)
            self.assertEqual(path, source)
            yield entrypoints.OpenedDocument(path, document, "Doc")

        deps = entrypoints._ExecutionEntrypointDependencies(
            apply_parameter_assignments=lambda *a: None,
            recompute_document=lambda *a: None,
            save_document=saved.append,
            export_step_artifacts=lambda *a, **k: None,
            export_csv_artifacts=lambda *a, **k: None,
            export_pdf_artifacts=lambda *a, **k: None,
            opened_freecad_document=opened,
            write_success_result=lambda *a: None,
        )
        patches = self._valid_manifest_patches(
            entrypoints,
            working_copy=working,
            manifest_path=working / "manifest.json",
            source_path=source,
        )
        with patches[0], patches[1], patches[2]:
            entrypoints.run_execution_entrypoint(
                working_copy=working,
                manifest_path=working / "manifest.json",
                result_path=working / "result.json",
                freecad_module=object(),
                _dependencies=deps,
            )

        self.assertEqual(len(saved), 1)
        self.assertIs(saved[0], document)

    def test_execution_entrypoint_does_not_call_observation_helpers(self) -> None:
        from parametron_freecad.runtime import entrypoints

        working_copy = Path("/tmp/working-copy").resolve()
        manifest_path = working_copy / "export_manifest_v1.json"
        result_path = working_copy / "result.json"
        source_path = working_copy / "model.FCStd"
        document = object()
        manifest_data = self._make_manifest_data()
        loaded_manifest = LoadedManifest(path=manifest_path, data=manifest_data)

        @contextmanager
        def fake_open(*args, **kwargs):
            del args, kwargs
            yield entrypoints.OpenedDocument(
                path=source_path,
                document=document,
                document_name="FakeDoc",
            )

        dependencies = entrypoints._ExecutionEntrypointDependencies(
            apply_parameter_assignments=lambda *args: None,
            recompute_document=lambda *args: None,
            save_document=lambda *args: None,
            export_step_artifacts=lambda *args, **kwargs: None,
            export_csv_artifacts=lambda *args, **kwargs: None,
            export_pdf_artifacts=lambda *args, **kwargs: None,
            opened_freecad_document=fake_open,
            write_success_result=lambda *args: None,
        )

        with mock.patch.object(
            entrypoints, "load_export_manifest_v1", return_value=loaded_manifest
        ), mock.patch.object(
            entrypoints,
            "validate_export_manifest_v1",
            return_value=ManifestValidationResult(diagnostics=()),
        ), mock.patch.object(
            entrypoints, "resolve_source_document_path", return_value=source_path
        ), mock.patch.object(
            entrypoints, "generate_observed_output"
        ) as generate_observed, mock.patch.object(
            entrypoints, "run_observation_entrypoint"
        ) as run_observation:
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=result_path,
                freecad_module=object(),
                _dependencies=dependencies,
            )

        generate_observed.assert_not_called()
        run_observation.assert_not_called()

    def test_validation_failure_stops_before_freecad_and_result_write(self) -> None:
        from parametron_freecad.runtime import entrypoints

        calls: list[str] = []
        working_copy = Path("/tmp/working-copy").resolve()
        manifest_path = working_copy / "export_manifest_v1.json"
        manifest_data = self._make_manifest_data()
        loaded_manifest = LoadedManifest(path=manifest_path, data=manifest_data)
        invalid = ManifestValidationResult(
            diagnostics=(
                ManifestDiagnostic(
                    code="missing_required_field",
                    path="sourceDocument",
                    message="missing required field 'sourceDocument'",
                ),
            )
        )

        @contextmanager
        def fake_open(*args, **kwargs):
            del args, kwargs
            calls.append("open")
            yield object()

        dependencies = entrypoints._ExecutionEntrypointDependencies(
            apply_parameter_assignments=lambda *args: calls.append("assign"),
            recompute_document=lambda *args: calls.append("recompute"),
            save_document=lambda *args: calls.append("save"),
            export_step_artifacts=lambda *args, **kwargs: calls.append("step"),
            export_csv_artifacts=lambda *args, **kwargs: calls.append("csv"),
            export_pdf_artifacts=lambda *args, **kwargs: calls.append("pdf"),
            opened_freecad_document=fake_open,
            write_success_result=lambda *args: calls.append("result"),
        )

        with mock.patch.object(
            entrypoints, "load_export_manifest_v1", return_value=loaded_manifest
        ), mock.patch.object(
            entrypoints, "validate_export_manifest_v1", return_value=invalid
        ), self.assertRaises(entrypoints.ExecutionEntrypointError):
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=working_copy / "result.json",
                freecad_module=object(),
                _dependencies=dependencies,
            )

        self.assertEqual(calls, [])

    def test_assignment_failure_stops_before_recompute_exports_and_result_write(self) -> None:
        from parametron_freecad.runtime import entrypoints

        calls: list[str] = []
        working_copy = Path("/tmp/working-copy").resolve()
        manifest_path = working_copy / "export_manifest_v1.json"
        source_path = working_copy / "model.FCStd"
        document = object()
        manifest_data = self._make_manifest_data()
        loaded_manifest = LoadedManifest(path=manifest_path, data=manifest_data)

        @contextmanager
        def fake_open(*args, **kwargs):
            del args, kwargs
            calls.append("open")
            yield entrypoints.OpenedDocument(
                path=source_path,
                document=document,
                document_name="FakeDoc",
            )
            calls.append("close")

        def fail_assignment(*args):
            del args
            calls.append("assign")
            raise entrypoints.ParameterAssignmentError("fake assignment failure")

        dependencies = entrypoints._ExecutionEntrypointDependencies(
            apply_parameter_assignments=fail_assignment,
            recompute_document=lambda *args: calls.append("recompute"),
            save_document=lambda *args: calls.append("save"),
            export_step_artifacts=lambda *args, **kwargs: calls.append("step"),
            export_csv_artifacts=lambda *args, **kwargs: calls.append("csv"),
            export_pdf_artifacts=lambda *args, **kwargs: calls.append("pdf"),
            opened_freecad_document=fake_open,
            write_success_result=lambda *args: calls.append("result"),
        )

        with mock.patch.object(
            entrypoints, "load_export_manifest_v1", return_value=loaded_manifest
        ), mock.patch.object(
            entrypoints,
            "validate_export_manifest_v1",
            return_value=ManifestValidationResult(diagnostics=()),
        ), mock.patch.object(
            entrypoints, "resolve_source_document_path", return_value=source_path
        ), self.assertRaises(entrypoints.ExecutionEntrypointError):
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=working_copy / "result.json",
                freecad_module=object(),
                _dependencies=dependencies,
            )

        self.assertEqual(calls, ["open", "assign"])

    def test_step_export_failure_stops_before_later_exports_and_result_write(self) -> None:
        from parametron_freecad.runtime import entrypoints

        calls: list[str] = []
        working_copy = Path("/tmp/working-copy").resolve()
        manifest_path = working_copy / "export_manifest_v1.json"
        source_path = working_copy / "model.FCStd"
        document = object()
        manifest_data = self._make_manifest_data()
        loaded_manifest = LoadedManifest(path=manifest_path, data=manifest_data)

        @contextmanager
        def fake_open(*args, **kwargs):
            del args, kwargs
            calls.append("open")
            yield entrypoints.OpenedDocument(
                path=source_path,
                document=document,
                document_name="FakeDoc",
            )
            calls.append("close")

        def fail_step(*args, **kwargs):
            del args, kwargs
            calls.append("step")
            raise entrypoints.StepArtifactExportError("fake step failure")

        dependencies = entrypoints._ExecutionEntrypointDependencies(
            apply_parameter_assignments=lambda *args: calls.append("assign"),
            recompute_document=lambda *args: calls.append("recompute"),
            save_document=lambda *args: calls.append("save"),
            export_step_artifacts=fail_step,
            export_csv_artifacts=lambda *args, **kwargs: calls.append("csv"),
            export_pdf_artifacts=lambda *args, **kwargs: calls.append("pdf"),
            opened_freecad_document=fake_open,
            write_success_result=lambda *args: calls.append("result"),
        )

        with mock.patch.object(
            entrypoints, "load_export_manifest_v1", return_value=loaded_manifest
        ), mock.patch.object(
            entrypoints,
            "validate_export_manifest_v1",
            return_value=ManifestValidationResult(diagnostics=()),
        ), mock.patch.object(
            entrypoints, "resolve_source_document_path", return_value=source_path
        ), self.assertRaises(entrypoints.ExecutionEntrypointError):
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=working_copy / "result.json",
                freecad_module=object(),
                _dependencies=dependencies,
            )

        self.assertEqual(calls, ["open", "assign", "recompute", "save", "step"])

    def test_manifest_loading_failure_writes_failed_result(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            manifest_path = working_copy / "export_manifest_v1.json"
            result_path = working_copy / "result.json"
            original = entrypoints.ManifestLoadError("fake load boom")

            with mock.patch.object(
                entrypoints,
                "load_export_manifest_v1",
                side_effect=original,
            ), self.assertRaises(entrypoints.ExecutionEntrypointError) as ctx:
                entrypoints.run_execution_entrypoint(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    freecad_module=object(),
                )

            self.assertIs(ctx.exception.__cause__, original)
            self.assertEqual(str(ctx.exception), "fake load boom")
            self._assert_failed_result(
                result_path,
                stage="manifest_loading",
                substring="fake load boom",
            )

    def test_freecad_unavailable_failure_writes_failed_result(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            manifest_path = working_copy / "export_manifest_v1.json"
            result_path = working_copy / "result.json"
            source_path = working_copy / "model.FCStd"

            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working_copy,
                manifest_path=manifest_path,
                source_path=source_path,
            )
            with patches[0], patches[1], patches[2], self.assertRaises(
                entrypoints.FreeCADUnavailableEntrypointError
            ) as ctx:
                entrypoints.run_execution_entrypoint(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    freecad_module=None,
                )

            self.assertEqual(str(ctx.exception), "FreeCAD module is not available")
            self._assert_failed_result(
                result_path,
                category="freecad_unavailable",
                code="freecad_unavailable",
                stage="freecad_resolution",
                substring="FreeCAD module is not available",
            )

    def test_parameter_assignment_failure_writes_failed_result(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            manifest_path = working_copy / "export_manifest_v1.json"
            result_path = working_copy / "result.json"
            source_path = working_copy / "model.FCStd"
            original = entrypoints.ParameterAssignmentError("fake assignment boom")

            @contextmanager
            def fake_open(*args, **kwargs):
                del args, kwargs
                yield entrypoints.OpenedDocument(
                    path=source_path,
                    document=object(),
                    document_name="FakeDoc",
                )

            dependencies = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=mock.Mock(side_effect=original),
                recompute_document=mock.Mock(),
                save_document=mock.Mock(),
                export_step_artifacts=mock.Mock(),
                export_csv_artifacts=mock.Mock(),
                export_pdf_artifacts=mock.Mock(),
                opened_freecad_document=fake_open,
                write_success_result=mock.Mock(),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working_copy,
                manifest_path=manifest_path,
                source_path=source_path,
            )

            with patches[0], patches[1], patches[2], self.assertRaises(
                entrypoints.ExecutionEntrypointError
            ) as ctx:
                entrypoints.run_execution_entrypoint(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            self.assertIs(ctx.exception.__cause__, original)
            self.assertEqual(str(ctx.exception), "fake assignment boom")
            self._assert_failed_result(
                result_path,
                stage="parameter_assignment",
                substring="fake assignment boom",
            )

    def test_recompute_failure_writes_failed_result(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            manifest_path = working_copy / "export_manifest_v1.json"
            result_path = working_copy / "result.json"
            source_path = working_copy / "model.FCStd"
            original = entrypoints.DocumentRecomputeError("fake recompute boom")

            @contextmanager
            def fake_open(*args, **kwargs):
                del args, kwargs
                yield entrypoints.OpenedDocument(
                    path=source_path,
                    document=object(),
                    document_name="FakeDoc",
                )

            dependencies = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=mock.Mock(),
                recompute_document=mock.Mock(side_effect=original),
                save_document=mock.Mock(),
                export_step_artifacts=mock.Mock(),
                export_csv_artifacts=mock.Mock(),
                export_pdf_artifacts=mock.Mock(),
                opened_freecad_document=fake_open,
                write_success_result=mock.Mock(),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working_copy,
                manifest_path=manifest_path,
                source_path=source_path,
            )

            with patches[0], patches[1], patches[2], self.assertRaises(
                entrypoints.ExecutionEntrypointError
            ) as ctx:
                entrypoints.run_execution_entrypoint(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            self.assertIs(ctx.exception.__cause__, original)
            self.assertEqual(str(ctx.exception), "fake recompute boom")
            self._assert_failed_result(
                result_path,
                stage="recompute",
                substring="fake recompute boom",
            )

    def test_artifact_export_failure_writes_failed_result(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            manifest_path = working_copy / "export_manifest_v1.json"
            result_path = working_copy / "result.json"
            source_path = working_copy / "model.FCStd"
            original = entrypoints.StepArtifactExportError("fake step boom")

            @contextmanager
            def fake_open(*args, **kwargs):
                del args, kwargs
                yield entrypoints.OpenedDocument(
                    path=source_path,
                    document=object(),
                    document_name="FakeDoc",
                )

            dependencies = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=mock.Mock(),
                recompute_document=mock.Mock(),
                save_document=mock.Mock(),
                export_step_artifacts=mock.Mock(side_effect=original),
                export_csv_artifacts=mock.Mock(),
                export_pdf_artifacts=mock.Mock(),
                opened_freecad_document=fake_open,
                write_success_result=mock.Mock(),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working_copy,
                manifest_path=manifest_path,
                source_path=source_path,
            )

            with patches[0], patches[1], patches[2], self.assertRaises(
                entrypoints.ExecutionEntrypointError
            ) as ctx:
                entrypoints.run_execution_entrypoint(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            self.assertIs(ctx.exception.__cause__, original)
            self.assertEqual(str(ctx.exception), "fake step boom")
            self._assert_failed_result(
                result_path,
                stage="artifact_export",
                substring="fake step boom",
            )

    def test_result_write_error_does_not_emit_recursive_failure_result(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            manifest_path = working_copy / "export_manifest_v1.json"
            result_path = working_copy / "result.json"
            source_path = working_copy / "model.FCStd"
            original = entrypoints.ResultWriteError("fake result write boom")

            @contextmanager
            def fake_open(*args, **kwargs):
                del args, kwargs
                yield entrypoints.OpenedDocument(
                    path=source_path,
                    document=object(),
                    document_name="FakeDoc",
                )

            dependencies = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=mock.Mock(),
                recompute_document=mock.Mock(),
                save_document=mock.Mock(),
                export_step_artifacts=mock.Mock(),
                export_csv_artifacts=mock.Mock(),
                export_pdf_artifacts=mock.Mock(),
                opened_freecad_document=fake_open,
                write_success_result=mock.Mock(side_effect=original),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working_copy,
                manifest_path=manifest_path,
                source_path=source_path,
            )

            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints,
                "write_failure_result",
            ) as write_failure, self.assertRaises(entrypoints.ExecutionEntrypointError) as ctx:
                entrypoints.run_execution_entrypoint(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            self.assertIs(ctx.exception.__cause__, original)
            self.assertEqual(str(ctx.exception), "fake result write boom")
            write_failure.assert_not_called()
            self.assertFalse(result_path.exists())

    def test_failure_result_write_error_does_not_mask_original_failure(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            manifest_path = working_copy / "export_manifest_v1.json"
            result_path = working_copy / "result.json"
            source_path = working_copy / "model.FCStd"
            original = entrypoints.ParameterAssignmentError("original assignment boom")

            @contextmanager
            def fake_open(*args, **kwargs):
                del args, kwargs
                yield entrypoints.OpenedDocument(
                    path=source_path,
                    document=object(),
                    document_name="FakeDoc",
                )

            dependencies = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=mock.Mock(side_effect=original),
                recompute_document=mock.Mock(),
                save_document=mock.Mock(),
                export_step_artifacts=mock.Mock(),
                export_csv_artifacts=mock.Mock(),
                export_pdf_artifacts=mock.Mock(),
                opened_freecad_document=fake_open,
                write_success_result=mock.Mock(),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working_copy,
                manifest_path=manifest_path,
                source_path=source_path,
            )

            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints,
                "write_failure_result",
                side_effect=OSError("failure result write boom"),
            ), self.assertRaises(entrypoints.ExecutionEntrypointError) as ctx:
                entrypoints.run_execution_entrypoint(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            self.assertIs(ctx.exception.__cause__, original)
            self.assertEqual(str(ctx.exception), "original assignment boom")
            self.assertFalse(result_path.exists())


class HeadlessExecuteAdapterEntrypointTests(unittest.TestCase):
    def _make_execute_paths(self, tmp_dir: str) -> tuple[Path, Path, Path]:
        working = Path(tmp_dir) / WORKING_COPY_DIR_NAME
        working.mkdir()
        manifest = working / "export_manifest_v1.json"
        manifest.write_text(
            '{"schemaVersion":"1.0","sourceDocument":"model.FCStd",'
            '"parameterAssignments":[],"outputs":[]}',
            encoding="utf-8",
        )
        (working / "model.FCStd").write_bytes(b"")
        return working, manifest, working / "result.json"

    def _execute_argv(self, working: Path, manifest: Path, result: Path) -> list[str]:
        return [
            "execute",
            "--working-copy",
            str(working),
            "--manifest",
            str(manifest),
            "--result",
            str(result),
        ]

    def test_headless_execute_delegates_to_runtime_entrypoint_and_maps_success(self) -> None:
        from parametron_freecad.runtime import entrypoints, headless

        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result = self._make_execute_paths(tmp_dir)
            fake_freecad = object()
            stdout = io.StringIO()
            stderr = io.StringIO()

            with mock.patch.object(
                headless, "run_execution_entrypoint"
            ) as run_entrypoint, mock.patch.object(
                entrypoints,
                "run_observation_entrypoint",
                side_effect=AssertionError("execute CLI must not observe"),
            ) as run_observation, mock.patch.object(
                entrypoints,
                "run_document_observation_entrypoint",
                side_effect=AssertionError("execute CLI must not open observation documents"),
            ) as run_document_observation:
                exit_code = headless.main(
                    argv=self._execute_argv(working, manifest, result),
                    stdout=stdout,
                    stderr=stderr,
                    freecad_module=fake_freecad,
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        run_entrypoint.assert_called_once()
        run_observation.assert_not_called()
        run_document_observation.assert_not_called()
        kwargs = run_entrypoint.call_args.kwargs
        self.assertEqual(kwargs["working_copy"], working.resolve())
        self.assertEqual(kwargs["manifest_path"], manifest.resolve())
        self.assertEqual(kwargs["result_path"], result.resolve())
        self.assertIs(kwargs["freecad_module"], fake_freecad)

    def test_headless_execute_runtime_failure_maps_to_exit_70_and_prefix(self) -> None:
        from parametron_freecad.runtime import headless

        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result = self._make_execute_paths(tmp_dir)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with mock.patch.object(
                headless,
                "run_execution_entrypoint",
                side_effect=headless.ExecutionEntrypointError("fake runtime failure"),
            ):
                exit_code = headless.main(
                    argv=self._execute_argv(working, manifest, result),
                    stdout=stdout,
                    stderr=stderr,
                    freecad_module=object(),
                )

        self.assertEqual(exit_code, headless.EXECUTION_FAILURE_EXIT_CODE)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            stderr.getvalue(),
            f"{headless.EXECUTION_FAILURE_MESSAGE_PREFIX}fake runtime failure\n",
        )

    def test_headless_forwards_reference_traversal_request_to_entrypoint(self) -> None:
        from parametron_freecad.runtime import headless

        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result = self._make_execute_paths(tmp_dir)
            output = working / "output"
            output.mkdir()
            request = working / "parametron.reference-traversal-request.json"
            request.write_text('{"schemaVersion":"1.0","externalTargets":[]}', encoding="utf-8")
            observation = working / "parametron.verification.json"
            observation.write_text("{}", encoding="utf-8")

            with mock.patch.object(
                headless, "run_execution_entrypoint"
            ) as run_entrypoint:
                exit_code = headless.main(
                    argv=[
                        *self._execute_argv(working, manifest, result),
                        "--output-dir",
                        str(output),
                        "--observation-request",
                        str(observation),
                        "--reference-traversal-request",
                        str(request),
                    ],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                    freecad_module=object(),
                )

        self.assertEqual(exit_code, 0)
        kwargs = run_entrypoint.call_args.kwargs
        self.assertEqual(kwargs["output_directory"], output.resolve())
        self.assertEqual(kwargs["observation_request_path"], observation.resolve())
        self.assertEqual(
            kwargs["reference_traversal_request_path"], request.resolve()
        )

    def test_headless_execute_freecad_unavailable_maps_to_exit_2(self) -> None:
        from parametron_freecad.runtime import headless

        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result = self._make_execute_paths(tmp_dir)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with mock.patch.object(
                headless,
                "run_execution_entrypoint",
                side_effect=headless.FreeCADUnavailableEntrypointError(
                    "FreeCAD module is not available"
                ),
            ):
                exit_code = headless.main(
                    argv=self._execute_argv(working, manifest, result),
                    stdout=stdout,
                    stderr=stderr,
                    freecad_module=None,
                )

        self.assertEqual(exit_code, headless.FREECAD_UNAVAILABLE_EXIT_CODE)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), f"{headless.FREECAD_UNAVAILABLE_MESSAGE}\n")

    def test_headless_invalid_arguments_fail_before_runtime_entrypoint(self) -> None:
        from parametron_freecad.runtime import entrypoints, headless

        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.object(
            headless, "run_execution_entrypoint"
        ) as run_entrypoint, mock.patch.object(
            headless,
            "import_module",
            side_effect=AssertionError("invalid execute args must not resolve FreeCAD"),
        ) as import_module, mock.patch.object(
            entrypoints,
            "run_observation_entrypoint",
            side_effect=AssertionError("invalid execute args must not observe"),
        ) as run_observation:
            exit_code = headless.main(
                argv=["execute", "--working-copy", "/does/not/exist"],
                stdout=stdout,
                stderr=stderr,
                freecad_module=object(),
            )

        self.assertEqual(exit_code, headless.ARGUMENT_ERROR_EXIT_CODE)
        self.assertTrue(stderr.getvalue().startswith(headless.INVALID_ARGUMENTS_MESSAGE_PREFIX))
        run_entrypoint.assert_not_called()
        import_module.assert_not_called()
        run_observation.assert_not_called()

    def test_headless_still_rejects_observation_only_cli_mode(self) -> None:
        from parametron_freecad.runtime import headless

        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.object(headless, "run_execution_entrypoint") as run_entrypoint:
            exit_code = headless.main(
                argv=["observe"],
                stdout=stdout,
                stderr=stderr,
                freecad_module=object(),
            )

        self.assertEqual(exit_code, headless.ARGUMENT_ERROR_EXIT_CODE)
        self.assertIn("unknown command: observe", stderr.getvalue())
        run_entrypoint.assert_not_called()

    def test_headless_still_rejects_combined_execute_observe_mode(self) -> None:
        from parametron_freecad.runtime import headless

        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result = self._make_execute_paths(tmp_dir)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with mock.patch.object(headless, "run_execution_entrypoint") as run_entrypoint:
                exit_code = headless.main(
                    argv=[
                        *self._execute_argv(working, manifest, result),
                        "--observe",
                    ],
                    stdout=stdout,
                    stderr=stderr,
                    freecad_module=object(),
                )

        self.assertEqual(exit_code, headless.ARGUMENT_ERROR_EXIT_CODE)
        self.assertIn("unrecognized arguments: --observe", stderr.getvalue())
        run_entrypoint.assert_not_called()


class ReferenceTraversalRequestEntrypointTests(unittest.TestCase):
    def _manifest_data(self) -> dict:
        return {
            "schemaVersion": "1.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [],
            "outputs": [],
        }

    def _valid_manifest_patches(
        self,
        entrypoints,
        *,
        working_copy: Path,
        manifest_path: Path,
        source_path: Path,
    ):
        loaded = LoadedManifest(path=manifest_path, data=self._manifest_data())
        return (
            mock.patch.object(
                entrypoints, "load_export_manifest_v1", return_value=loaded
            ),
            mock.patch.object(
                entrypoints,
                "validate_export_manifest_v1",
                return_value=ManifestValidationResult(diagnostics=()),
            ),
            mock.patch.object(
                entrypoints,
                "resolve_source_document_path",
                return_value=source_path,
            ),
        )

    def _assert_failed_result(
        self,
        result_path: Path,
        *,
        stage: str,
        substring: str,
    ) -> None:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(payload["status"], "failed")
        self.assertNotIn("artifacts", payload)
        failure = payload["failure"]
        self.assertEqual(failure["boundary"], "execution_entrypoint")
        self.assertEqual(failure["category"], "execution")
        self.assertEqual(failure["code"], "runtime_failure")
        self.assertEqual(failure["stage"], stage)
        self.assertIn(substring, failure["message"])
        self.assertNotIn("Traceback", failure["message"])

    def _dependencies(
        self,
        entrypoints,
        calls: list[str],
        *,
        run_traversal=None,
        run_observation=None,
        write_traversal_output=None,
    ):
        @contextmanager
        def opened(*args):
            del args
            calls.append("open")
            try:
                yield entrypoints.OpenedDocument(
                    path=Path("model.FCStd"),
                    document=object(),
                    document_name="Doc",
                )
            finally:
                calls.append("close")

        if run_traversal is None:

            def run_traversal(*args, **kwargs):
                del args, kwargs
                calls.append("traversal")
                return entrypoints.ReferenceTraversalExecutionResult(
                    status="succeeded",
                    nodes=(),
                    edges=(),
                    diagnostics=(),
                )

        if write_traversal_output is None:

            def write_traversal_output(*args, **kwargs):
                del args, kwargs
                calls.append("traversal-output")

        return entrypoints._ExecutionEntrypointDependencies(
            apply_parameter_assignments=lambda *args: calls.append("assign"),
            recompute_document=lambda *args: calls.append("recompute"),
            save_document=lambda *args: calls.append("save"),
            export_step_artifacts=lambda *args, **kwargs: calls.append("step"),
            export_csv_artifacts=lambda *args, **kwargs: calls.append("csv"),
            export_pdf_artifacts=lambda *args, **kwargs: calls.append("pdf"),
            opened_freecad_document=opened,
            write_success_result=lambda *args: calls.append("result"),
            run_observation_entrypoint=run_observation,
            run_reference_traversal=run_traversal,
            write_reference_traversal_output_atomically=write_traversal_output,
        )

    def test_request_is_loaded_exactly_once_before_freecad_and_document_work(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints
        from parametron_freecad.runtime.reference_traversal_request import (
            ReferenceTraversalRequest,
        )

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            manifest = working / "manifest.json"
            source = working / "model.FCStd"
            request = working / "request.json"
            result = working / "result.json"
            output = working / "output"
            calls: list[str] = []
            dependencies = self._dependencies(entrypoints, calls)
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working,
                manifest_path=manifest,
                source_path=source,
            )

            def load(received_path):
                self.assertEqual(received_path, request)
                calls.append("load-traversal-request")
                return ReferenceTraversalRequest(schema_version="1.0", external_targets=())

            def resolve_freecad():
                calls.append("resolve-freecad")
                return object()

            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints,
                "load_reference_traversal_request",
                side_effect=load,
            ) as loader:
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=result,
                    output_directory=output,
                    reference_traversal_request_path=request,
                    resolve_freecad_module=resolve_freecad,
                    _dependencies=dependencies,
                )

        loader.assert_called_once_with(request)
        self.assertEqual(calls[0:3], [
            "load-traversal-request",
            "resolve-freecad",
            "open",
        ])
        self.assertEqual(
            calls,
            [
                "load-traversal-request",
                "resolve-freecad",
                "open",
                "assign",
                "recompute",
                "save",
                "step",
                "csv",
                "pdf",
                "traversal",
                "traversal-output",
                "close",
                "result",
            ],
        )

    def test_absent_request_does_not_call_loader(self) -> None:
        from parametron_freecad.runtime import entrypoints

        working = Path("/tmp/working-copy").resolve()
        manifest = working / "manifest.json"
        source = working / "model.FCStd"
        calls: list[str] = []
        dependencies = self._dependencies(entrypoints, calls)
        patches = self._valid_manifest_patches(
            entrypoints,
            working_copy=working,
            manifest_path=manifest,
            source_path=source,
        )

        with patches[0] as load_manifest, patches[1] as validate_manifest, patches[2] as resolve_source, mock.patch.object(
            entrypoints, "load_reference_traversal_request"
        ) as loader:
            entrypoints.run_execution_entrypoint(
                working_copy=working,
                manifest_path=manifest,
                result_path=working / "result.json",
                output_directory=working / "output",
                freecad_module=object(),
                _dependencies=dependencies,
            )

        loader.assert_not_called()
        load_manifest.assert_called_once_with(manifest)
        validate_manifest.assert_called_once_with(self._manifest_data())
        resolve_source.assert_called_once_with(working, "model.FCStd")
        self.assertEqual(
            calls,
            ["open", "assign", "recompute", "save", "step", "csv", "pdf", "close", "result"],
        )

    def test_succeeded_and_partial_traversal_run_after_exports_before_observation(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints

        for status in ("succeeded", "partial"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                working = Path(tmp)
                manifest = working / "manifest.json"
                source = working / "model.FCStd"
                source.write_bytes(b"source")
                request_path = working / "traversal-request.json"
                observation_path = working / "observation-request.json"
                output = working / "output"
                result = working / "result.json"
                calls: list[str] = []
                normalized_request = entrypoints.ReferenceTraversalRequest(
                    schema_version="1.0", external_targets=()
                )

                def run_traversal(document, request, **kwargs):
                    del document
                    self.assertIs(request, normalized_request)
                    self.assertEqual(kwargs["working_copy"], working)
                    self.assertEqual(kwargs["source_document"], "model.FCStd")
                    self.assertEqual(kwargs["source_document_path"], source)
                    calls.append("traversal")
                    return entrypoints.ReferenceTraversalExecutionResult(
                        status=status,
                        nodes=(),
                        edges=(),
                        diagnostics=(),
                    )

                def run_observation(*args, **kwargs):
                    del args, kwargs
                    calls.append("observation")

                def write_traversal_output(working_copy, output_path, **kwargs):
                    self.assertEqual(working_copy, working)
                    self.assertEqual(
                        output_path,
                        output / "prm.reference-traversal.json",
                    )
                    self.assertEqual(
                        kwargs["boundary"], "reference_traversal_entrypoint"
                    )
                    self.assertEqual(kwargs["operation"], "reference_traversal")
                    self.assertEqual(kwargs["status"], status)
                    self.assertEqual(kwargs["source_document"], "model.FCStd")
                    self.assertEqual(kwargs["nodes"], ())
                    self.assertEqual(kwargs["edges"], ())
                    self.assertEqual(kwargs["diagnostics"], ())
                    calls.append("traversal-output")

                dependencies = self._dependencies(
                    entrypoints,
                    calls,
                    run_traversal=run_traversal,
                    run_observation=run_observation,
                    write_traversal_output=write_traversal_output,
                )
                patches = self._valid_manifest_patches(
                    entrypoints,
                    working_copy=working,
                    manifest_path=manifest,
                    source_path=source,
                )
                with patches[0], patches[1], patches[2], mock.patch.object(
                    entrypoints,
                    "load_reference_traversal_request",
                    return_value=normalized_request,
                ), mock.patch.object(
                    entrypoints,
                    "load_observation_request",
                    return_value={"observe": {}},
                ):
                    entrypoints.run_execution_entrypoint(
                        working_copy=working,
                        manifest_path=manifest,
                        result_path=result,
                        output_directory=output,
                        observation_request_path=observation_path,
                        reference_traversal_request_path=request_path,
                        freecad_module=object(),
                        _dependencies=dependencies,
                    )

                self.assertEqual(
                    calls,
                    [
                        "open",
                        "assign",
                        "recompute",
                        "save",
                        "step",
                        "csv",
                        "pdf",
                        "traversal",
                        "traversal-output",
                        "observation",
                        "close",
                        "result",
                    ],
                )

    def test_failed_typed_result_preserves_exports_and_skips_observation(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            manifest = working / "manifest.json"
            source = working / "model.FCStd"
            source.write_bytes(b"source")
            result = working / "result.json"
            calls: list[str] = []

            def run_traversal(*args, **kwargs):
                del args, kwargs
                calls.append("traversal")
                return entrypoints.ReferenceTraversalExecutionResult(
                    status="failed",
                    nodes=(),
                    edges=(),
                    diagnostics=(),
                )

            dependencies = self._dependencies(
                entrypoints,
                calls,
                run_traversal=run_traversal,
                run_observation=lambda *args, **kwargs: calls.append("observation"),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working,
                manifest_path=manifest,
                source_path=source,
            )
            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints,
                "load_reference_traversal_request",
                return_value=entrypoints.ReferenceTraversalRequest(schema_version="1.0", external_targets=()),
            ), mock.patch.object(
                entrypoints, "load_observation_request", return_value={"observe": {}}
            ), self.assertRaisesRegex(
                entrypoints.ExecutionEntrypointError,
                "reference traversal returned failed status",
            ):
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=result,
                    output_directory=working / "output",
                    observation_request_path=working / "observation.json",
                    reference_traversal_request_path=working / "traversal.json",
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            self.assertEqual(
                calls,
                ["open", "assign", "recompute", "save", "step", "csv", "pdf", "traversal", "close"],
            )
            self._assert_failed_result(
                result,
                stage="reference_traversal",
                substring="reference traversal returned failed status",
            )

    def test_canonical_edge_identity_conflict_is_contained_and_chained(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            manifest = working / "manifest.json"
            source_path = working / "model.FCStd"
            source_path.write_bytes(b"source")
            result = working / "result.json"
            calls: list[str] = []
            source = CanonicalReferenceTraversalNode(
                kind="object", state="resolved", document_path="model.FCStd",
                object_name="Source",
            )
            target = CanonicalReferenceTraversalNode(
                kind="object", state="resolved", document_path="refs/a.FCStd",
                object_name="Target",
            )
            resolved = CanonicalReferenceTraversalEdge(
                source, target, "external_document_reference", "resolved",
                "Parts", "App::PropertyXLinkList",
            )
            conflicting = CanonicalReferenceTraversalEdge(
                source, target, "external_document_reference", "missing",
                "Parts", "App::PropertyXLinkList",
            )
            with self.assertRaises(
                entrypoints.ReferenceTraversalExecutionError
            ) as original_caught:
                entrypoints.ReferenceTraversalExecutionResult(
                    status="succeeded", nodes=(source, target),
                    edges=(resolved, conflicting), diagnostics=(),
                )
            original = original_caught.exception

            def run_traversal(*args, **kwargs):
                del args, kwargs
                calls.append("traversal")
                raise original

            dependencies = self._dependencies(
                entrypoints,
                calls,
                run_traversal=run_traversal,
                run_observation=lambda *args, **kwargs: calls.append("observation"),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working,
                manifest_path=manifest,
                source_path=source_path,
            )
            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints,
                "load_reference_traversal_request",
                return_value=entrypoints.ReferenceTraversalRequest(
                    schema_version="1.0", external_targets=()
                ),
            ), self.assertRaises(entrypoints.ExecutionEntrypointError) as caught:
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=result,
                    output_directory=working / "output",
                    reference_traversal_request_path=working / "traversal.json",
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            self.assertIs(caught.exception.__cause__, original)
            self.assertIsInstance(original.__cause__, ValueError)
            self.assertNotIn("observation", calls)
            self._assert_failed_result(
                result,
                stage="reference_traversal",
                substring=(
                    "duplicate canonical edge identity has conflicting raw evidence"
                ),
            )

    def test_canonical_node_identity_conflict_is_contained_and_chained(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            manifest = working / "manifest.json"
            source_path = working / "model.FCStd"
            source_path.write_bytes(b"source")
            result = working / "result.json"
            output_directory = working / "output"
            calls: list[str] = []
            resolved = CanonicalReferenceTraversalNode(
                kind="object", state="resolved", document_path="model.FCStd",
                object_name="Source", label="Source label",
            )
            conflicting = CanonicalReferenceTraversalNode(
                kind="object", state="missing", document_path="model.FCStd",
                object_name="Source", label="Source label",
            )
            with self.assertRaises(
                entrypoints.ReferenceTraversalExecutionError
            ) as original_caught:
                entrypoints.ReferenceTraversalExecutionResult(
                    status="succeeded", nodes=(resolved, conflicting),
                    edges=(), diagnostics=(),
                )
            original = original_caught.exception

            def run_traversal(*args, **kwargs):
                del args, kwargs
                calls.append("traversal")
                raise original

            dependencies = self._dependencies(
                entrypoints,
                calls,
                run_traversal=run_traversal,
                run_observation=lambda *args, **kwargs: calls.append("observation"),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working,
                manifest_path=manifest,
                source_path=source_path,
            )
            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints,
                "load_reference_traversal_request",
                return_value=entrypoints.ReferenceTraversalRequest(
                    schema_version="1.0", external_targets=()
                ),
            ), self.assertRaises(entrypoints.ExecutionEntrypointError) as caught:
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=result,
                    output_directory=output_directory,
                    reference_traversal_request_path=working / "traversal.json",
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            self.assertIs(caught.exception.__cause__, original)
            self.assertIsInstance(original.__cause__, ValueError)
            self.assertNotIn("observation", calls)
            self.assertNotIn("traversal-output", calls)
            self.assertFalse(
                (output_directory / "prm.reference-traversal.json").exists()
            )
            self._assert_failed_result(
                result,
                stage="reference_traversal",
                substring=(
                    "duplicate canonical node identity has conflicting raw evidence"
                ),
            )

    def test_output_write_failure_is_controlled_and_skips_observation(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            manifest = working / "manifest.json"
            source = working / "model.FCStd"
            source.write_bytes(b"source")
            result = working / "result.json"
            missing_output = working / "missing-output"
            calls: list[str] = []
            dependencies = self._dependencies(
                entrypoints,
                calls,
                run_observation=lambda *args, **kwargs: calls.append("observation"),
                write_traversal_output=(
                    entrypoints.write_reference_traversal_output_atomically
                ),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working,
                manifest_path=manifest,
                source_path=source,
            )

            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints,
                "load_reference_traversal_request",
                return_value=entrypoints.ReferenceTraversalRequest(schema_version="1.0", external_targets=()),
            ), mock.patch.object(
                entrypoints, "load_observation_request", return_value={"observe": {}}
            ), self.assertRaises(entrypoints.ExecutionEntrypointError) as caught:
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=result,
                    output_directory=missing_output,
                    observation_request_path=working / "observation.json",
                    reference_traversal_request_path=working / "traversal.json",
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            self.assertIsInstance(
                caught.exception.__cause__,
                entrypoints.ReferenceTraversalOutputWriteError,
            )
            self.assertEqual(
                calls,
                ["open", "assign", "recompute", "save", "step", "csv", "pdf", "traversal", "close"],
            )
            self.assertFalse(missing_output.exists())
            self._assert_failed_result(
                result,
                stage="reference_traversal_output_containment",
                substring="failed to atomically write reference traversal output file",
            )

    def test_real_atomic_writer_emits_canonical_traversal_file(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            manifest = working / "manifest.json"
            source = working / "model.FCStd"
            source.write_bytes(b"source")
            output = working / "outputs"
            output.mkdir()
            calls: list[str] = []
            dependencies = self._dependencies(
                entrypoints,
                calls,
                write_traversal_output=(
                    entrypoints.write_reference_traversal_output_atomically
                ),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working,
                manifest_path=manifest,
                source_path=source,
            )

            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints,
                "load_reference_traversal_request",
                return_value=entrypoints.ReferenceTraversalRequest(schema_version="1.0", external_targets=()),
            ):
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=working / "result.json",
                    output_directory=output,
                    reference_traversal_request_path=working / "traversal.json",
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            traversal_path = output / "prm.reference-traversal.json"
            self.assertEqual(
                json.loads(traversal_path.read_text(encoding="utf-8")),
                {
                    "boundary": "reference_traversal_entrypoint",
                    "diagnostics": [],
                    "edges": [],
                    "kind": "raw_reference_traversal",
                    "nodes": [],
                    "operation": "reference_traversal",
                    "schemaVersion": "1.0",
                    "sourceDocument": "model.FCStd",
                    "status": "succeeded",
                },
            )
            self.assertEqual(traversal_path.read_bytes()[-1:], b"\n")

    def test_output_failure_classes_use_exact_stable_code_and_stages(self) -> None:
        from parametron_freecad.runtime import entrypoints

        cases = (
            ("containment", True, "reference_traversal_output_containment"),
            ("serialization", False, "reference_traversal_output_write"),
            ("write", False, "reference_traversal_output_write"),
            ("replacement", False, "reference_traversal_output_write"),
        )
        for label, is_containment, expected_stage in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                working = Path(tmp)
                manifest = working / "manifest.json"
                source = working / "model.FCStd"
                source.write_bytes(b"source")
                output = working / "output"
                output.mkdir()
                result = working / "result.json"
                original = RuntimeError(f"{label} cause")
                writer_error = entrypoints.ReferenceTraversalOutputWriteError(
                    f"{label} emission failed"
                )
                writer_error._is_containment_failure = is_containment

                def fail_output(*args, **kwargs):
                    del args, kwargs
                    raise writer_error from original

                dependencies = self._dependencies(
                    entrypoints,
                    [],
                    write_traversal_output=fail_output,
                )
                patches = self._valid_manifest_patches(
                    entrypoints,
                    working_copy=working,
                    manifest_path=manifest,
                    source_path=source,
                )

                with patches[0], patches[1], patches[2], mock.patch.object(
                    entrypoints,
                    "load_reference_traversal_request",
                    return_value=entrypoints.ReferenceTraversalRequest(
                        schema_version="1.0", external_targets=()
                    ),
                ), self.assertRaises(entrypoints.ExecutionEntrypointError) as caught:
                    entrypoints.run_execution_entrypoint(
                        working_copy=working,
                        manifest_path=manifest,
                        result_path=result,
                        output_directory=output,
                        reference_traversal_request_path=working / "request.json",
                        freecad_module=object(),
                        _dependencies=dependencies,
                    )

                self.assertIs(caught.exception.__cause__, writer_error)
                self.assertIs(writer_error.__cause__, original)
                payload = json.loads(result.read_text(encoding="utf-8"))
                self.assertEqual(payload["failure"]["code"], "runtime_failure")
                self.assertEqual(payload["failure"]["stage"], expected_stage)
                self.assertEqual(payload["failure"]["message"], str(writer_error))

    def test_malformed_request_fails_before_freecad_and_writes_failed_result(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            manifest = working / "manifest.json"
            source = working / "model.FCStd"
            request = working / "request.json"
            result = working / "result.json"
            output = working / "output"
            calls: list[str] = []
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working,
                manifest_path=manifest,
                source_path=source,
            )
            request_error = entrypoints.ReferenceTraversalRequestError(
                "request contains unknown field"
            )

            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints,
                "load_reference_traversal_request",
                side_effect=request_error,
            ) as loader, self.assertRaises(
                entrypoints.ExecutionEntrypointError
            ) as caught:
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=result,
                    output_directory=output,
                    reference_traversal_request_path=request,
                    resolve_freecad_module=lambda: calls.append("freecad"),
                    _dependencies=self._dependencies(entrypoints, calls),
                )

            loader.assert_called_once_with(request)
            self.assertIs(caught.exception.__cause__, request_error)
            self.assertEqual(calls, ["traversal-output"])
            self._assert_failed_result(
                result,
                stage="request_validation",
                substring="request contains unknown field",
            )

    def test_malformed_request_emits_defined_raw_failure_without_freecad(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            manifest = working / "manifest.json"
            source = working / "model.FCStd"
            request = working / "request.json"
            request.write_text('{"schemaVersion":"1.0","externalTargets":[],"extra":true}', encoding="utf-8")
            result = working / "result.json"
            output = working / "output"
            output.mkdir()
            calls: list[str] = []
            dependencies = self._dependencies(
                entrypoints,
                calls,
                write_traversal_output=(
                    entrypoints.write_reference_traversal_output_atomically
                ),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working,
                manifest_path=manifest,
                source_path=source,
            )

            with patches[0], patches[1], patches[2], self.assertRaises(
                entrypoints.ExecutionEntrypointError
            ) as caught:
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=result,
                    output_directory=output,
                    reference_traversal_request_path=request,
                    resolve_freecad_module=lambda: calls.append("freecad"),
                    _dependencies=dependencies,
                )

            self.assertIsInstance(
                caught.exception.__cause__, entrypoints.ReferenceTraversalRequestError
            )
            self.assertEqual(calls, [])
            payload = json.loads(
                (output / "prm.reference-traversal.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["schemaVersion"], "1.0")
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["sourceDocument"], "model.FCStd")
            self.assertEqual(payload["nodes"], [])
            self.assertEqual(payload["edges"], [])
            self.assertEqual(
                payload["diagnostics"],
                [
                    {
                        "sequence": 0,
                        "severity": "error",
                        "code": "malformed_traversal_request",
                        "message": "request contains unknown field(s): 'extra'",
                        "stage": "request_validation",
                    }
                ],
            )
            self.assertNotIn(str(working), payload["diagnostics"][0]["message"])
            self._assert_failed_result(
                result,
                stage="request_validation",
                substring="request contains unknown field",
            )

    def test_request_path_requires_output_directory_at_entrypoint(self) -> None:
        from parametron_freecad.runtime import entrypoints

        working = Path("/tmp/working-copy").resolve()
        manifest = working / "manifest.json"
        source = working / "model.FCStd"
        request = working / "request.json"
        patches = self._valid_manifest_patches(
            entrypoints,
            working_copy=working,
            manifest_path=manifest,
            source_path=source,
        )

        with patches[0], patches[1], patches[2], mock.patch.object(
            entrypoints, "load_reference_traversal_request"
        ) as loader, self.assertRaisesRegex(
            entrypoints.ExecutionEntrypointError,
            "reference traversal request requires an output directory",
        ):
            entrypoints.run_execution_entrypoint(
                working_copy=working,
                manifest_path=manifest,
                result_path=None,
                reference_traversal_request_path=request,
                freecad_module=object(),
            )

        loader.assert_not_called()

    def test_document_open_failure_uses_stable_top_level_code_and_stage(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            manifest = working / "manifest.json"
            source = working / "model.FCStd"
            source.write_bytes(b"source")
            result = working / "result.json"
            output = working / "output"
            output.mkdir()
            calls: list[str] = []
            original = entrypoints.DocumentLifecycleError(
                "FreeCAD failed to open document"
            )

            @contextmanager
            def fail_open(*args):
                del args
                calls.append("open")
                raise original
                yield

            dependencies = entrypoints._ExecutionEntrypointDependencies(
                opened_freecad_document=fail_open,
                run_reference_traversal=lambda *args, **kwargs: calls.append(
                    "traversal"
                ),
                write_reference_traversal_output_atomically=(
                    lambda *args, **kwargs: calls.append("traversal-output")
                ),
                write_success_result=lambda *args: calls.append("result"),
            )
            patches = self._valid_manifest_patches(
                entrypoints,
                working_copy=working,
                manifest_path=manifest,
                source_path=source,
            )

            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints,
                "load_reference_traversal_request",
                return_value=entrypoints.ReferenceTraversalRequest(schema_version="1.0", external_targets=()),
            ), self.assertRaises(entrypoints.ExecutionEntrypointError) as caught:
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=result,
                    output_directory=output,
                    reference_traversal_request_path=working / "request.json",
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            self.assertIs(caught.exception.__cause__, original)
            self.assertEqual(calls, ["open"])
            payload = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(
                payload["failure"],
                {
                    "boundary": "execution_entrypoint",
                    "category": "execution",
                    "code": "runtime_failure",
                    "message": "FreeCAD failed to open document",
                    "stage": "document_open",
                },
            )
            self.assertFalse(
                (output / "prm.reference-traversal.json").exists()
            )

    def test_traversal_preserves_declared_exports_and_success_artifacts(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            manifest = working / "manifest.json"
            source = working / "model.FCStd"
            source.write_bytes(b"source")
            output = working / "output"
            output.mkdir()
            outputs = [
                {"id": "Part", "format": "step", "path": "out/part.step"},
                {"id": "Sheet", "format": "csv", "path": "out/data.csv"},
                {"id": "Page", "format": "pdf", "path": "out/page.pdf"},
            ]
            manifest_data = {
                **self._manifest_data(),
                "outputs": outputs,
            }
            loaded = LoadedManifest(path=manifest, data=manifest_data)
            calls: list[tuple[str, object]] = []

            @contextmanager
            def opened(*args):
                del args
                yield entrypoints.OpenedDocument(
                    path=source, document=object(), document_name="Doc"
                )

            dependencies = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=lambda *args: None,
                recompute_document=lambda *args: None,
                save_document=lambda *args: None,
                export_step_artifacts=lambda document, received, **kwargs: calls.append(
                    ("step", received)
                ),
                export_csv_artifacts=lambda document, received, **kwargs: calls.append(
                    ("csv", received)
                ),
                export_pdf_artifacts=lambda document, received, **kwargs: calls.append(
                    ("pdf", received)
                ),
                opened_freecad_document=opened,
                run_reference_traversal=lambda *args, **kwargs: (
                    entrypoints.ReferenceTraversalExecutionResult(
                        status="succeeded", nodes=(), edges=(), diagnostics=()
                    )
                ),
                write_reference_traversal_output_atomically=(
                    lambda *args, **kwargs: calls.append(("traversal-output", kwargs))
                ),
                write_success_result=lambda path, received: calls.append(
                    ("result", received)
                ),
            )

            with mock.patch.object(
                entrypoints, "load_export_manifest_v1", return_value=loaded
            ), mock.patch.object(
                entrypoints,
                "validate_export_manifest_v1",
                return_value=ManifestValidationResult(diagnostics=()),
            ), mock.patch.object(
                entrypoints, "resolve_source_document_path", return_value=source
            ), mock.patch.object(
                entrypoints,
                "load_reference_traversal_request",
                return_value=entrypoints.ReferenceTraversalRequest(schema_version="1.0", external_targets=()),
            ):
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=working / "result.json",
                    output_directory=output,
                    reference_traversal_request_path=working / "request.json",
                    freecad_module=object(),
                    _dependencies=dependencies,
                )

            self.assertEqual(
                calls,
                [
                    ("step", outputs),
                    ("csv", outputs),
                    ("pdf", outputs),
                    ("traversal-output", mock.ANY),
                    ("result", outputs),
                ],
            )


class RuntimeObservationEntrypointTests(unittest.TestCase):
    class FakeObject:
        def __init__(self, **properties):
            for name, value in properties.items():
                setattr(self, name, value)

    class FakeDocument:
        Name = "FakeDoc"

        def __init__(self):
            self._objects = {
                "Spreadsheet": RuntimeObservationEntrypointTests.FakeObject(
                    Length=10.0,
                    Count=5,
                ),
                "Doc": RuntimeObservationEntrypointTests.FakeObject(Author="Jane"),
                "Sketch001": RuntimeObservationEntrypointTests.FakeObject(),
            }
            self.calls: list[str] = []

        @property
        def Objects(self):  # noqa: N802 - mimic FreeCAD attribute name
            raise AssertionError("document.Objects must not be accessed")

        @property
        def Label(self):  # noqa: N802 - mimic FreeCAD attribute name
            raise AssertionError("document Label lookup must not be used")

        def getObject(self, name):  # noqa: N802 - mimic FreeCAD method name
            self.calls.append(name)
            return self._objects.get(name)

    class FakeFreeCAD:
        def __init__(self, document):
            self.document = document
            self.opened_paths: list[str] = []
            self.closed_names: list[str] = []

        def openDocument(self, path):  # noqa: N802 - mimic FreeCAD method name
            self.opened_paths.append(path)
            return self.document

        def closeDocument(self, name):  # noqa: N802 - mimic FreeCAD method name
            self.closed_names.append(name)

    def _verification_data(self, *, include_components: bool = False) -> dict:
        data = {
            "observe": {"parameters": True, "metadata": True, "references": True},
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
        if include_components:
            data["observe"]["components"] = True
        return data

    def _make_working_copy(self, tmp_dir: str) -> tuple[Path, Path]:
        working_copy = Path(tmp_dir) / WORKING_COPY_DIR_NAME
        working_copy.mkdir()
        source_path = working_copy / "model.FCStd"
        source_path.write_text("fake FreeCAD document", encoding="utf-8")
        return working_copy, source_path

    def test_observation_entrypoint_delegates_to_observed_output_helper(self) -> None:
        from parametron_freecad.runtime import entrypoints

        document = object()
        verification_data = {"schemaVersion": "1.0", "requested": {"parameters": []}}
        working_copy = Path("/tmp/work")
        output_directory = Path("/tmp/out")

        with mock.patch.object(entrypoints, "generate_observed_output") as generate:
            result = entrypoints.run_observation_entrypoint(
                document,
                verification_data,
                working_copy_path=working_copy,
                working_copy_sha256="abc123",
                output_directory=output_directory,
            )

        self.assertIsNone(result)
        generate.assert_called_once_with(
            document,
            verification_data,
            working_copy_path=working_copy,
            working_copy_sha256="abc123",
            output_directory=output_directory,
        )

    def test_observation_entrypoint_does_not_inspect_document_objects(self) -> None:
        from parametron_freecad.runtime import entrypoints

        class DocumentSentinel:
            @property
            def Objects(self):  # noqa: N802 - mimic FreeCAD attribute name
                raise AssertionError("observation entrypoint must not inspect Objects")

        with mock.patch.object(entrypoints, "generate_observed_output") as generate:
            entrypoints.run_observation_entrypoint(
                DocumentSentinel(),
                {},
                working_copy_path="/tmp/work",
                working_copy_sha256="abc123",
                output_directory="/tmp/out",
            )

        generate.assert_called_once()

    def test_observation_entrypoint_does_not_load_verification_or_compute_sha256(
        self,
    ) -> None:
        from parametron_freecad.observation import verification_loader
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            working_copy = Path(tmp_dir) / WORKING_COPY_DIR_NAME
            working_copy.mkdir()
            caller_sha256 = "8" * 64

            def fail_if_verification_loaded(*args, **kwargs):
                del args, kwargs
                raise AssertionError(
                    "observation entrypoint must not load verification files"
                )

            with mock.patch.object(
                verification_loader,
                "load_parametron_verification_v1",
                side_effect=fail_if_verification_loaded,
            ):
                entrypoints.run_observation_entrypoint(
                    self.FakeDocument(),
                    self._verification_data(include_components=True),
                    working_copy_path=working_copy,
                    working_copy_sha256=caller_sha256,
                    output_directory=output_directory,
                )

            observed_path = output_directory / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))

        self.assertEqual(decoded["workingCopy"]["sha256"], caller_sha256)
        self.assertNotIn("components", decoded["observation"])

    def test_observation_entrypoint_does_not_call_execution_entrypoint(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            working_copy = Path(tmp_dir) / WORKING_COPY_DIR_NAME
            working_copy.mkdir()

            with mock.patch.object(
                entrypoints,
                "run_execution_entrypoint",
                side_effect=AssertionError(
                    "observation entrypoint must not call execution entrypoint"
                ),
            ) as run_execution:
                entrypoints.run_observation_entrypoint(
                    self.FakeDocument(),
                    self._verification_data(),
                    working_copy_path=working_copy,
                    working_copy_sha256="7" * 64,
                    output_directory=output_directory,
                )

        run_execution.assert_not_called()

    def test_observation_entrypoint_preserves_phase_2_requested_scope_output(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            working_copy = Path(tmp_dir) / WORKING_COPY_DIR_NAME
            working_copy.mkdir()
            document = self.FakeDocument()
            verification_data = self._verification_data(include_components=True)
            original_verification_data = copy.deepcopy(verification_data)
            caller_sha256 = "f" * 64

            entrypoints.run_observation_entrypoint(
                document,
                verification_data,
                working_copy_path=working_copy,
                working_copy_sha256=caller_sha256,
                output_directory=output_directory,
            )

            observed_path = output_directory / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))

            self.assertTrue(observed_path.exists())
            self.assertEqual(decoded["schemaVersion"], "1.0")
            self.assertEqual(decoded["workingCopy"]["path"], str(working_copy))
            self.assertEqual(decoded["workingCopy"]["sha256"], caller_sha256)
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

        self.assertEqual(verification_data, original_verification_data)

    def test_observation_entrypoint_repeated_run_is_byte_stable(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            working_copy = Path(tmp_dir) / WORKING_COPY_DIR_NAME
            working_copy.mkdir()
            document = self.FakeDocument()
            verification_data = self._verification_data()
            kwargs = {
                "working_copy_path": working_copy,
                "working_copy_sha256": "a" * 64,
                "output_directory": output_directory,
            }

            entrypoints.run_observation_entrypoint(
                document,
                verification_data,
                **kwargs,
            )
            observed_path = output_directory / "prm.observed.json"
            first = observed_path.read_bytes()

            entrypoints.run_observation_entrypoint(
                document,
                verification_data,
                **kwargs,
            )
            second = observed_path.read_bytes()

        self.assertEqual(first, second)

    def test_observation_entrypoint_wraps_observed_output_error_with_cause(self) -> None:
        from parametron_freecad.runtime import entrypoints

        original = entrypoints.ObservedOutputError("fake observed output failure")

        with mock.patch.object(
            entrypoints, "generate_observed_output", side_effect=original
        ), self.assertRaises(entrypoints.ObservationEntrypointError) as excinfo:
            entrypoints.run_observation_entrypoint(
                object(),
                {},
                working_copy_path="/tmp/work",
                working_copy_sha256="abc123",
                output_directory="/tmp/out",
            )

        self.assertEqual(str(excinfo.exception), "fake observed output failure")
        self.assertIs(excinfo.exception.__cause__, original)

    def test_document_observation_entrypoint_opens_observes_writes_and_closes(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, source_path = self._make_working_copy(tmp_dir)
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            document = self.FakeDocument()
            freecad = self.FakeFreeCAD(document)
            observed_documents = []

            def spy_observation_entrypoint(received_document, *args, **kwargs):
                observed_documents.append((received_document, args, kwargs))
                return entrypoints.run_observation_entrypoint(
                    received_document,
                    *args,
                    **kwargs,
                )

            dependencies = entrypoints._DocumentObservationEntrypointDependencies(
                opened_freecad_document=entrypoints.opened_freecad_document,
                run_observation_entrypoint=spy_observation_entrypoint,
            )

            entrypoints.run_document_observation_entrypoint(
                working_copy=working_copy,
                source_document="model.FCStd",
                verification_data=self._verification_data(),
                working_copy_path=working_copy,
                working_copy_sha256="a" * 64,
                output_directory=output_directory,
                freecad_module=freecad,
                _dependencies=dependencies,
            )

            observed_path = output_directory / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))

        self.assertEqual(freecad.opened_paths, [str(source_path.resolve())])
        self.assertEqual(freecad.closed_names, ["FakeDoc"])
        self.assertEqual(len(observed_documents), 1)
        self.assertIs(observed_documents[0][0], document)
        self.assertEqual(decoded["schemaVersion"], "1.0")
        self.assertEqual(decoded["workingCopy"]["path"], str(working_copy))
        self.assertEqual(decoded["workingCopy"]["sha256"], "a" * 64)
        self.assertEqual(
            list(decoded["observation"].keys()),
            ["metadata", "parameters", "references"],
        )
        self.assertEqual(
            [item["id"] for item in decoded["observation"]["parameters"]],
            ["p.length", "p.count"],
        )
        self.assertEqual(decoded["observation"]["metadata"][0]["id"], "m.author")
        self.assertEqual(decoded["observation"]["references"][0]["name"], "Sketch001")

    def test_document_observation_entrypoint_resolves_freecad_at_runtime(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, source_path = self._make_working_copy(tmp_dir)
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            freecad = self.FakeFreeCAD(self.FakeDocument())
            resolver_calls = []

            def resolve_freecad_module():
                resolver_calls.append("resolve")
                return freecad

            entrypoints.run_document_observation_entrypoint(
                working_copy=working_copy,
                source_document=Path("model.FCStd"),
                verification_data={"observe": {"parameters": False}},
                working_copy_path=working_copy,
                working_copy_sha256="b" * 64,
                output_directory=output_directory,
                resolve_freecad_module=resolve_freecad_module,
            )

            observed_path = output_directory / "prm.observed.json"
            observed_path_exists = observed_path.exists()

        self.assertEqual(resolver_calls, ["resolve"])
        self.assertEqual(freecad.opened_paths, [str(source_path.resolve())])
        self.assertEqual(freecad.closed_names, ["FakeDoc"])
        self.assertTrue(observed_path_exists)

    def test_document_observation_entrypoint_freecad_unavailable_fails_without_output(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, _source_path = self._make_working_copy(tmp_dir)
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()

            with self.assertRaises(entrypoints.ObservationEntrypointError) as excinfo:
                entrypoints.run_document_observation_entrypoint(
                    working_copy=working_copy,
                    source_document="model.FCStd",
                    verification_data={"observe": {"parameters": False}},
                    working_copy_path=working_copy,
                    working_copy_sha256="c" * 64,
                    output_directory=output_directory,
                    resolve_freecad_module=lambda: None,
                )

            observed_path = output_directory / "prm.observed.json"
            observed_path_exists = observed_path.exists()

        self.assertEqual(str(excinfo.exception), "FreeCAD module is not available")
        self.assertIsNone(excinfo.exception.__cause__)
        self.assertFalse(observed_path_exists)

    def test_document_observation_entrypoint_wraps_source_path_failure_with_cause(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir) / WORKING_COPY_DIR_NAME
            working_copy.mkdir()
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            freecad = self.FakeFreeCAD(self.FakeDocument())

            with self.assertRaises(entrypoints.ObservationEntrypointError) as excinfo:
                entrypoints.run_document_observation_entrypoint(
                    working_copy=working_copy,
                    source_document="missing.FCStd",
                    verification_data={"observe": {"parameters": False}},
                    working_copy_path=working_copy,
                    working_copy_sha256="d" * 64,
                    output_directory=output_directory,
                    freecad_module=freecad,
                )

            observed_path = output_directory / "prm.observed.json"
            observed_path_exists = observed_path.exists()

        self.assertIsInstance(
            excinfo.exception.__cause__,
            entrypoints.SourceDocumentPathError,
        )
        self.assertEqual(freecad.opened_paths, [])
        self.assertEqual(freecad.closed_names, [])
        self.assertFalse(observed_path_exists)

    def test_document_observation_entrypoint_does_not_load_verification_or_compute_sha256(
        self,
    ) -> None:
        from parametron_freecad.observation import verification_loader
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, source_path = self._make_working_copy(tmp_dir)
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            document = self.FakeDocument()
            freecad = self.FakeFreeCAD(document)
            caller_sha256 = "9" * 64

            def fail_if_verification_loaded(*args, **kwargs):
                del args, kwargs
                raise AssertionError(
                    "document observation entrypoint must not load verification files"
                )

            with mock.patch.object(
                verification_loader,
                "load_parametron_verification_v1",
                side_effect=fail_if_verification_loaded,
            ):
                entrypoints.run_document_observation_entrypoint(
                    working_copy=working_copy,
                    source_document="model.FCStd",
                    verification_data=self._verification_data(include_components=True),
                    working_copy_path=working_copy,
                    working_copy_sha256=caller_sha256,
                    output_directory=output_directory,
                    freecad_module=freecad,
                )

            observed_path = output_directory / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))

        self.assertEqual(freecad.opened_paths, [str(source_path.resolve())])
        self.assertEqual(freecad.closed_names, ["FakeDoc"])
        self.assertEqual(decoded["workingCopy"]["sha256"], caller_sha256)
        self.assertNotIn("components", decoded["observation"])

    def test_document_observation_entrypoint_closes_on_observation_failure(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, _source_path = self._make_working_copy(tmp_dir)
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            freecad = self.FakeFreeCAD(self.FakeDocument())

            with self.assertRaises(entrypoints.ObservationEntrypointError) as excinfo:
                entrypoints.run_document_observation_entrypoint(
                    working_copy=working_copy,
                    source_document="model.FCStd",
                    verification_data={"observe": {"parameters": True}},
                    working_copy_path=working_copy,
                    working_copy_sha256="e" * 64,
                    output_directory=output_directory,
                    freecad_module=freecad,
                )

            observed_path = output_directory / "prm.observed.json"
            observed_path_exists = observed_path.exists()

        self.assertEqual(freecad.closed_names, ["FakeDoc"])
        self.assertIsInstance(excinfo.exception.__cause__, entrypoints.ObservedOutputError)
        self.assertFalse(observed_path_exists)

    def test_document_observation_entrypoint_does_not_call_execution_entrypoint(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, _source_path = self._make_working_copy(tmp_dir)
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            freecad = self.FakeFreeCAD(self.FakeDocument())

            with mock.patch.object(
                entrypoints,
                "run_execution_entrypoint",
                side_effect=AssertionError(
                    "document observation entrypoint must not call execution entrypoint"
                ),
            ) as run_execution:
                entrypoints.run_document_observation_entrypoint(
                    working_copy=working_copy,
                    source_document="model.FCStd",
                    verification_data=self._verification_data(),
                    working_copy_path=working_copy,
                    working_copy_sha256="6" * 64,
                    output_directory=output_directory,
                    freecad_module=freecad,
                )

        run_execution.assert_not_called()

    def test_document_observation_entrypoint_observed_output_has_no_verification_decision(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, _source_path = self._make_working_copy(tmp_dir)
            output_directory = Path(tmp_dir) / "observed"
            output_directory.mkdir()
            freecad = self.FakeFreeCAD(self.FakeDocument())

            entrypoints.run_document_observation_entrypoint(
                working_copy=working_copy,
                source_document="model.FCStd",
                verification_data=self._verification_data(include_components=True),
                working_copy_path=working_copy,
                working_copy_sha256="5" * 64,
                output_directory=output_directory,
                freecad_module=freecad,
            )

            observed_path = output_directory / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))

        self.assertNotIn("decision", decoded)
        self.assertNotIn("verification", decoded)
        self.assertNotIn("checks", decoded)
        self.assertNotIn("components", decoded["observation"])


class EngineCompatibilityEntrypointTests(unittest.TestCase):
    """Engine manifest compatibility boundary is hooked into run_execution_entrypoint."""

    def _engine_manifest_no_params(self) -> dict:
        return {
            "schemaVersion": "1.0",
            "planHash": "test-plan-hash",
            "adapter": "freecad",
            "product": {"id": "Box"},
            "inputs": {"sourceModel": "input/box.FCStd"},
            "values": {},
            "parameterAssignments": [],
            "outputs": [{"type": "step", "filename": "Box.step", "object": "Body"}],
        }

    def _engine_manifest_with_name_params(self) -> dict:
        return {
            "schemaVersion": "1.0",
            "planHash": "test-plan-hash",
            "adapter": "freecad",
            "product": {"id": "Box"},
            "inputs": {"sourceModel": "input/box.FCStd"},
            "values": {"length": 35},
            "parameterAssignments": [
                {"name": "length", "value": 35, "type": "number", "unit": "mm"},
            ],
            "outputs": [{"type": "step", "filename": "Box.step", "object": "Body"}],
        }

    def _fake_dependencies(self, calls: list) -> object:
        from parametron_freecad.runtime import entrypoints
        from contextlib import contextmanager

        @contextmanager
        def fake_open(*args, **kwargs):
            calls.append("open")
            yield entrypoints.OpenedDocument(
                path=Path("/tmp/model.FCStd"),
                document=object(),
                document_name="FakeDoc",
            )
            calls.append("close")

        return entrypoints._ExecutionEntrypointDependencies(
            apply_parameter_assignments=lambda *a: calls.append("assign"),
            recompute_document=lambda *a: calls.append("recompute"),
            save_document=lambda *a: calls.append("save"),
            export_step_artifacts=lambda *a, **k: calls.append("step"),
            export_csv_artifacts=lambda *a, **k: calls.append("csv"),
            export_pdf_artifacts=lambda *a, **k: calls.append("pdf"),
            opened_freecad_document=fake_open,
            write_success_result=lambda *a: calls.append("result"),
        )

    def test_engine_name_only_param_raises_execution_entrypoint_error(self) -> None:
        from parametron_freecad.runtime import entrypoints

        working_copy = Path("/tmp/wc")
        manifest_path = working_copy / "export_manifest_v1.json"
        manifest_data = self._engine_manifest_with_name_params()
        loaded = LoadedManifest(path=manifest_path, data=manifest_data)

        with mock.patch.object(
            entrypoints, "load_export_manifest_v1", return_value=loaded
        ), self.assertRaises(entrypoints.ExecutionEntrypointError):
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=working_copy / "result.json",
                freecad_module=object(),
                _dependencies=self._fake_dependencies([]),
            )

    def test_legacy_engine_shape_fails_canonical_validation_without_translation(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints

        working_copy = Path("/tmp/wc")
        manifest_path = working_copy / "export_manifest_v1.json"
        loaded = LoadedManifest(
            path=manifest_path, data=self._engine_manifest_with_name_params()
        )

        with mock.patch.object(
            entrypoints, "load_export_manifest_v1", return_value=loaded
        ), self.assertRaises(entrypoints.ExecutionEntrypointError) as excinfo:
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=working_copy / "result.json",
                freecad_module=object(),
                _dependencies=self._fake_dependencies([]),
            )

        self.assertIsNone(excinfo.exception.__cause__)
        self.assertIn("manifest validation failed", str(excinfo.exception).lower())

    def test_engine_name_only_param_rejected_before_freecad_document_open(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints

        calls: list[str] = []
        working_copy = Path("/tmp/wc")
        manifest_path = working_copy / "export_manifest_v1.json"
        loaded = LoadedManifest(
            path=manifest_path, data=self._engine_manifest_with_name_params()
        )

        with mock.patch.object(
            entrypoints, "load_export_manifest_v1", return_value=loaded
        ), self.assertRaises(entrypoints.ExecutionEntrypointError):
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=working_copy / "result.json",
                freecad_module=object(),
                _dependencies=self._fake_dependencies(calls),
            )

        self.assertNotIn("open", calls)

    def test_engine_name_only_param_rejected_before_parameter_assignment(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints

        calls: list[str] = []
        working_copy = Path("/tmp/wc")
        manifest_path = working_copy / "export_manifest_v1.json"
        loaded = LoadedManifest(
            path=manifest_path, data=self._engine_manifest_with_name_params()
        )

        with mock.patch.object(
            entrypoints, "load_export_manifest_v1", return_value=loaded
        ), self.assertRaises(entrypoints.ExecutionEntrypointError):
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=working_copy / "result.json",
                freecad_module=object(),
                _dependencies=self._fake_dependencies(calls),
            )

        self.assertNotIn("assign", calls)

    def test_engine_name_only_param_rejected_before_recompute_export_result(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints

        calls: list[str] = []
        working_copy = Path("/tmp/wc")
        manifest_path = working_copy / "export_manifest_v1.json"
        loaded = LoadedManifest(
            path=manifest_path, data=self._engine_manifest_with_name_params()
        )

        with mock.patch.object(
            entrypoints, "load_export_manifest_v1", return_value=loaded
        ), self.assertRaises(entrypoints.ExecutionEntrypointError):
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=working_copy / "result.json",
                freecad_module=object(),
                _dependencies=self._fake_dependencies(calls),
            )

        for side_effect in ("recompute", "step", "csv", "pdf", "result"):
            self.assertNotIn(side_effect, calls)

    def test_internal_manifest_not_rejected_by_normalization_boundary(self) -> None:
        from parametron_freecad.runtime import entrypoints

        calls: list[str] = []
        working_copy = Path("/tmp/wc")
        manifest_path = working_copy / "export_manifest_v1.json"
        source_path = working_copy / "model.FCStd"
        internal_data = {
            "schemaVersion": "1.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [
                {"target": "Box.Length", "value": 10.0, "valueKind": "scalar"},
            ],
            "outputs": [
                {"id": "part", "format": "step", "path": "exports/part.step"},
            ],
        }
        loaded = LoadedManifest(path=manifest_path, data=internal_data)

        with mock.patch.object(
            entrypoints, "load_export_manifest_v1", return_value=loaded
        ), mock.patch.object(
            entrypoints,
            "validate_export_manifest_v1",
            return_value=ManifestValidationResult(diagnostics=()),
        ), mock.patch.object(
            entrypoints, "resolve_source_document_path", return_value=source_path
        ):
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=working_copy / "result.json",
                freecad_module=object(),
                _dependencies=self._fake_dependencies(calls),
            )

        self.assertIn("open", calls)
        self.assertIn("assign", calls)
        self.assertIn("recompute", calls)
        self.assertIn("result", calls)


class ExecuteObservationContractTests(unittest.TestCase):
    def _manifest(self, path: Path) -> LoadedManifest:
        return LoadedManifest(path=path, data={
            "schemaVersion": "1.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [
                {"target": "Box.Length", "value": 42.0, "valueKind": "scalar"}
            ],
            "outputs": [
                {"id": "part", "format": "step", "path": "part.step"},
                {"id": "table", "format": "csv", "path": "table.csv"},
                {"id": "drawing", "format": "pdf", "path": "drawing.pdf"},
            ],
        })

    def _patch_manifest(self, entrypoints, working: Path, source: Path):
        loaded = self._manifest(working / "manifest.json")
        return (
            mock.patch.object(entrypoints, "load_export_manifest_v1", return_value=loaded),
            mock.patch.object(entrypoints, "validate_export_manifest_v1",
                              return_value=ManifestValidationResult(diagnostics=())),
            mock.patch.object(entrypoints, "resolve_source_document_path", return_value=source),
        )

    def test_live_post_mutation_observation_phase_order_and_runtime_digest(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / "model.FCStd"
            source_bytes = b"controlled-fcstd-source\x00\xff"
            source.write_bytes(source_bytes)
            output = working / "output"
            output.mkdir()
            request_path = working / "request.json"
            request_path.write_text("{}", encoding="utf-8")
            result = working / "result.json"
            events: list[str] = []

            class Document:
                length = 1.0
                recomputed = False
                saved = False

            document = Document()

            @contextmanager
            def opened(module, path):
                self.assertIsNotNone(module)
                self.assertEqual(path, source)
                events.append("open")
                yield entrypoints.OpenedDocument(path=path, document=document, document_name="Doc")
                events.append("close")

            def assign(received, assignments):
                self.assertIs(received, document)
                self.assertEqual(assignments[0]["value"], 42.0)
                received.length = 42.0
                events.append("assign")

            def recompute(received):
                received.recomputed = True
                events.append("recompute")

            def exporter(name):
                def run(received, outputs, *, working_copy):
                    self.assertIs(received, document)
                    self.assertEqual(working_copy, working)
                    events.append(name)
                return run

            def observe(received, request, **kwargs):
                self.assertIs(received, document)
                self.assertEqual(received.length, 42.0)
                self.assertTrue(received.recomputed)
                self.assertEqual(events[-3:], ["step", "csv", "pdf"])
                self.assertEqual(request, {"observe": {"metadata": True}})
                self.assertEqual(kwargs["working_copy_path"], working)
                self.assertEqual(kwargs["working_copy_sha256"], hashlib.sha256(source_bytes).hexdigest())
                self.assertEqual(kwargs["output_directory"], output)
                self.assertFalse(result.exists())
                events.append("observation")

            def write_success(path, outputs):
                self.assertEqual(path, result)
                events.append("result")

            dependencies = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=assign,
                recompute_document=recompute,
                save_document=lambda received: (
                    setattr(received, "saved", True), events.append("save")
                ),
                export_step_artifacts=exporter("step"),
                export_csv_artifacts=exporter("csv"),
                export_pdf_artifacts=exporter("pdf"),
                opened_freecad_document=opened,
                write_success_result=write_success,
                run_observation_entrypoint=observe,
            )
            patches = self._patch_manifest(entrypoints, working, source)
            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints, "load_observation_request",
                return_value={"observe": {"metadata": True}},
            ), mock.patch.object(
                entrypoints, "load_reference_traversal_request"
            ) as load_traversal_request:
                entrypoints.run_execution_entrypoint(
                    working_copy=working, manifest_path=working / "manifest.json",
                    result_path=result, output_directory=output,
                    observation_request_path=request_path, freecad_module=object(),
                    _dependencies=dependencies,
                )

            load_traversal_request.assert_not_called()
            self.assertEqual(events, ["open", "assign", "recompute", "save", "step", "csv", "pdf", "observation", "close", "result"])
            self.assertTrue(document.saved)

    def test_digest_changes_only_with_source_bytes_and_request_cannot_override_it(self) -> None:
        from parametron_freecad.runtime import entrypoints

        digests = []
        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / "model.FCStd"
            output = working / "output"
            output.mkdir()
            request = working / "request.json"
            request.write_text("{}", encoding="utf-8")
            document = object()

            @contextmanager
            def opened(*args):
                yield entrypoints.OpenedDocument(path=source, document=document, document_name="Doc")

            deps = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=lambda *args: None,
                recompute_document=lambda *args: None,
                save_document=lambda *args: None,
                export_step_artifacts=lambda *args, **kwargs: None,
                export_csv_artifacts=lambda *args, **kwargs: None,
                export_pdf_artifacts=lambda *args, **kwargs: None,
                opened_freecad_document=opened,
                write_success_result=lambda *args: None,
                run_observation_entrypoint=lambda *args, **kwargs: digests.append(kwargs["working_copy_sha256"]),
            )
            patches = self._patch_manifest(entrypoints, working, source)
            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints, "load_observation_request",
                return_value={"workingCopy": {"sha256": "caller-override"}, "observe": {}},
            ):
                for source_bytes in (b"first", b"second"):
                    source.write_bytes(source_bytes)
                    (output / "unrelated").write_text(str(len(digests)), encoding="utf-8")
                    entrypoints.run_execution_entrypoint(
                        working_copy=working, manifest_path=working / "manifest.json",
                        result_path=working / "result.json", output_directory=output,
                        observation_request_path=request, freecad_module=object(),
                        _dependencies=deps,
                    )
            self.assertEqual(digests, [hashlib.sha256(b"first").hexdigest(), hashlib.sha256(b"second").hexdigest()])
            self.assertTrue(all(len(value) == 64 and value == value.lower() for value in digests))

    def test_execution_only_and_output_directory_alone_do_not_enable_observation(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / "model.FCStd"
            source.write_bytes(b"source")
            output = working / "output"
            output.mkdir()
            calls = []

            @contextmanager
            def opened(*args):
                calls.append("open")
                yield entrypoints.OpenedDocument(path=source, document=object(), document_name="Doc")
                calls.append("close")

            deps = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=lambda *args: calls.append("assign"),
                recompute_document=lambda *args: calls.append("recompute"),
                save_document=lambda *args: calls.append("save"),
                export_step_artifacts=lambda *args, **kwargs: calls.append("step"),
                export_csv_artifacts=lambda *args, **kwargs: calls.append("csv"),
                export_pdf_artifacts=lambda *args, **kwargs: calls.append("pdf"),
                opened_freecad_document=opened,
                write_success_result=lambda *args: calls.append("result"),
                run_observation_entrypoint=lambda *args, **kwargs: self.fail("observation invoked"),
            )
            patches = self._patch_manifest(entrypoints, working, source)
            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints, "load_observation_request"
            ) as load_request, mock.patch.object(Path, "read_bytes", side_effect=AssertionError("source hashed")):
                entrypoints.run_execution_entrypoint(
                    working_copy=working, manifest_path=working / "manifest.json",
                    result_path=working / "result.json", output_directory=output,
                    freecad_module=object(), _dependencies=deps,
                )
            load_request.assert_not_called()
            self.assertEqual(calls, ["open", "assign", "recompute", "save", "step", "csv", "pdf", "close", "result"])
            self.assertFalse((output / "prm.observed.json").exists())

    def test_observation_failures_close_document_write_structured_failure_and_preserve_cause(self) -> None:
        from parametron_freecad.runtime import entrypoints

        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / "model.FCStd"
            source.write_bytes(b"source")
            output = working / "output"
            output.mkdir()
            request = working / "request.json"
            request.write_text("{}", encoding="utf-8")
            result = working / "result.json"
            events = []

            @contextmanager
            def opened(*args):
                events.append("open")
                try:
                    yield entrypoints.OpenedDocument(path=source, document=object(), document_name="Doc")
                finally:
                    events.append("close")

            original = entrypoints.ObservedOutputError("serialization failed")
            observation_error = entrypoints.ObservationEntrypointError(str(original))
            observation_error.__cause__ = original
            deps = entrypoints._ExecutionEntrypointDependencies(
                apply_parameter_assignments=lambda *args: events.append("assign"),
                recompute_document=lambda *args: events.append("recompute"),
                save_document=lambda *args: events.append("save"),
                export_step_artifacts=lambda *args, **kwargs: events.append("step"),
                export_csv_artifacts=lambda *args, **kwargs: events.append("csv"),
                export_pdf_artifacts=lambda *args, **kwargs: events.append("pdf"),
                opened_freecad_document=opened,
                write_success_result=lambda *args: events.append("success"),
                run_observation_entrypoint=mock.Mock(side_effect=observation_error),
            )
            patches = self._patch_manifest(entrypoints, working, source)
            with patches[0], patches[1], patches[2], mock.patch.object(
                entrypoints, "load_observation_request", return_value={"observe": {}}
            ), self.assertRaises(entrypoints.ExecutionEntrypointError) as caught:
                entrypoints.run_execution_entrypoint(
                    working_copy=working, manifest_path=working / "manifest.json",
                    result_path=result, output_directory=output,
                    observation_request_path=request, freecad_module=object(),
                    _dependencies=deps,
                )
            self.assertIs(caught.exception.__cause__, observation_error)
            self.assertIs(observation_error.__cause__, original)
            self.assertEqual(events, ["open", "assign", "recompute", "save", "step", "csv", "pdf", "close"])
            payload = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["failure"]["stage"], "observation")
            self.assertFalse((output / "prm.observed.json").exists())

    def test_request_loading_and_source_hash_failures_are_structured_observation_failures(self) -> None:
        from parametron_freecad.runtime import entrypoints

        for failure_kind in ("load", "hash"):
            with self.subTest(failure_kind=failure_kind), tempfile.TemporaryDirectory() as tmp:
                working = Path(tmp)
                source = working / "model.FCStd"
                source.write_bytes(b"source")
                output = working / "output"
                output.mkdir()
                request = working / "request.json"
                request.write_text("{}", encoding="utf-8")
                result = working / "result.json"
                calls = []
                deps = entrypoints._ExecutionEntrypointDependencies(
                    apply_parameter_assignments=lambda *args: calls.append("assign"),
                    recompute_document=lambda *args: calls.append("recompute"),
                    save_document=lambda *args: calls.append("save"),
                    export_step_artifacts=lambda *args, **kwargs: calls.append("step"),
                    export_csv_artifacts=lambda *args, **kwargs: calls.append("csv"),
                    export_pdf_artifacts=lambda *args, **kwargs: calls.append("pdf"),
                    opened_freecad_document=lambda *args: self.fail("document opened"),
                    write_success_result=lambda *args: calls.append("success"),
                    run_observation_entrypoint=lambda *args, **kwargs: calls.append("observe"),
                )
                patches = self._patch_manifest(entrypoints, working, source)
                loader = mock.patch.object(
                    entrypoints,
                    "load_observation_request",
                    side_effect=(
                        entrypoints.ObservationRequestError("request load failed")
                        if failure_kind == "load"
                        else None
                    ),
                    return_value={"observe": {}},
                )
                hash_patch = (
                    mock.patch.object(Path, "read_bytes", side_effect=OSError("hash failed"))
                    if failure_kind == "hash"
                    else mock.patch.object(Path, "read_bytes", wraps=Path.read_bytes)
                )
                with patches[0], patches[1], patches[2], loader, hash_patch, self.assertRaises(
                    entrypoints.ExecutionEntrypointError
                ) as caught:
                    entrypoints.run_execution_entrypoint(
                        working_copy=working, manifest_path=working / "manifest.json",
                        result_path=result, output_directory=output,
                        observation_request_path=request, freecad_module=object(),
                        _dependencies=deps,
                    )
                self.assertIsInstance(caught.exception.__cause__, entrypoints.ObservationRequestError)
                self.assertEqual(calls, [])
                payload = json.loads(result.read_text(encoding="utf-8"))
                self.assertEqual(payload["failure"]["stage"], "observation")
                self.assertFalse((output / "prm.observed.json").exists())


if __name__ == "__main__":
    unittest.main()
