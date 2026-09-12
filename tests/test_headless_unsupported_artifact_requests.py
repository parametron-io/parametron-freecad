from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from parametron_freecad.common.paths import WORKING_COPY_DIR_NAME
from parametron_freecad.runtime import headless


class _FakeDocument:
    def __init__(
        self,
        *,
        objects: dict[str, object] | None = None,
        document_objects: list[object] | None = None,
    ) -> None:
        self.Name = "ParametronTestDoc"
        self._objects = objects if objects is not None else {}
        self._document_objects = document_objects if document_objects is not None else []
        self.events: list[str] = []

    def getObject(self, name: str) -> object | None:
        self.events.append(f"getObject:{name}")
        return self._objects.get(name)

    def recompute(self) -> None:
        self.events.append("recompute")

    def save(self) -> None:
        self.events.append("save")

    @property
    def Objects(self) -> list[object]:
        self.events.append("Objects")
        return self._document_objects


class _FakeFreeCAD:
    def __init__(self, document: object | None = None) -> None:
        self.document = document if document is not None else _FakeDocument()
        self.open_calls: list[str] = []
        self.close_calls: list[str] = []

    def openDocument(self, path: str) -> object:
        self.open_calls.append(path)
        return self.document

    def closeDocument(self, name: str) -> None:
        events = getattr(self.document, "events", None)
        if events is not None:
            events.append(f"close:{name}")
        self.close_calls.append(name)


class _FakeSpreadsheet:
    def __init__(self, content: object = None) -> None:
        self.Content = {} if content is None else content


class HeadlessUnsupportedArtifactRequestTests(unittest.TestCase):
    def _run_main(
        self,
        argv: list[str],
        *,
        freecad_module: object,
    ) -> tuple[int, io.StringIO, io.StringIO]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = headless.main(
            argv=argv,
            stdout=stdout,
            stderr=stderr,
            freecad_module=freecad_module,
        )
        return exit_code, stdout, stderr

    def _make_working_copy(
        self,
        tmp_dir: str,
        *,
        outputs: list[dict[str, str]],
    ) -> tuple[Path, Path, Path]:
        working = Path(tmp_dir) / WORKING_COPY_DIR_NAME
        working.mkdir()
        source = working / "model.FCStd"
        source.write_bytes(b"")
        manifest = working / "export_manifest_v1.json"
        manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "sourceDocument": source.name,
                    "parameterAssignments": [],
                    "outputs": outputs,
                }
            ),
            encoding="utf-8",
        )
        return working, manifest, working / "result.json"

    def _execute(
        self,
        tmp_dir: str,
        *,
        outputs: list[dict[str, str]],
        freecad_module: object,
    ) -> tuple[int, io.StringIO, io.StringIO, Path, Path]:
        working, manifest, result_path = self._make_working_copy(
            tmp_dir,
            outputs=outputs,
        )
        exit_code, stdout, stderr = self._run_main(
            [
                "execute",
                "--working-copy",
                str(working),
                "--manifest",
                str(manifest),
                "--result",
                str(result_path),
            ],
            freecad_module=freecad_module,
        )
        return exit_code, stdout, stderr, working, result_path

    def assert_controlled_execute_failure(
        self,
        exit_code: int,
        stdout: io.StringIO,
        stderr: io.StringIO,
        *,
        substring: str,
    ) -> None:
        self.assertEqual(exit_code, headless.EXECUTION_FAILURE_EXIT_CODE)
        self.assertEqual(stdout.getvalue(), "")
        err = stderr.getvalue()
        self.assertTrue(
            err.startswith(headless.EXECUTION_FAILURE_MESSAGE_PREFIX),
            msg=f"stderr {err!r} does not start with execute-failure prefix",
        )
        self.assertIn(substring, err)
        self.assertTrue(err.endswith("\n"), msg=f"stderr {err!r} has no trailing newline")
        self.assertEqual(err.count("\n"), 1, msg=f"stderr {err!r} is not single-line")
        self.assertNotIn("Traceback", err)

    def assert_no_success_outputs(
        self,
        *artifact_paths: Path,
    ) -> None:
        for artifact_path in artifact_paths:
            self.assertFalse(artifact_path.exists(), msg=f"{artifact_path} should not exist")

    def assert_failed_result(
        self,
        result_path: Path,
        *,
        stage: str,
        category: str = "execution",
        code: str = "runtime_failure",
    ) -> None:
        self.assertTrue(result_path.exists(), msg=f"{result_path} should exist")
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(payload["status"], "failed")
        failure = payload["failure"]
        self.assertEqual(failure["boundary"], "execution_entrypoint")
        self.assertEqual(failure["category"], category)
        self.assertEqual(failure["code"], code)
        self.assertEqual(failure["stage"], stage)
        self.assertEqual(failure["message"], " ".join(failure["message"].split()))
        self.assertNotIn("Traceback", failure["message"])

    def test_unsupported_manifest_output_formats_fail_before_document_open_or_export(self) -> None:
        cases = [
            ("stl", "exports/part.stl"),
            ("dxf", "exports/drawing.dxf"),
            ("STEP", "exports/part.step"),
            ("Pdf", "exports/drawing.pdf"),
        ]

        for output_format, output_path in cases:
            with self.subTest(output_format=output_format), tempfile.TemporaryDirectory() as tmp_dir:
                fake_freecad = _FakeFreeCAD()
                outputs = [{"id": "artifact", "format": output_format, "path": output_path}]

                with mock.patch.object(
                    headless,
                    "export_step_artifacts",
                    side_effect=AssertionError("STEP exporter should not be invoked"),
                ) as step_export, mock.patch.object(
                    headless,
                    "export_csv_artifacts",
                    side_effect=AssertionError("CSV exporter should not be invoked"),
                ) as csv_export, mock.patch.object(
                    headless,
                    "export_pdf_artifacts",
                    side_effect=AssertionError("PDF exporter should not be invoked"),
                ) as pdf_export:
                    exit_code, stdout, stderr, working, result_path = self._execute(
                        tmp_dir,
                        outputs=outputs,
                        freecad_module=fake_freecad,
                    )

                self.assert_controlled_execute_failure(
                    exit_code,
                    stdout,
                    stderr,
                    substring=f"unsupported output format '{output_format}'",
                )
                self.assertIn("manifest validation failed", stderr.getvalue())
                self.assertEqual(fake_freecad.open_calls, [])
                self.assertEqual(fake_freecad.close_calls, [])
                step_export.assert_not_called()
                csv_export.assert_not_called()
                pdf_export.assert_not_called()
                self.assert_failed_result(result_path, stage="manifest_validation")
                self.assert_no_success_outputs(working / output_path)

    def test_step_import_module_unavailable_fails_and_closes_before_later_exporters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            doc = _FakeDocument(objects={"part": object()})
            fake_freecad = _FakeFreeCAD(doc)
            with mock.patch.object(
                headless,
                "export_csv_artifacts",
            ) as csv_export, mock.patch.object(
                headless,
                "export_pdf_artifacts",
            ) as pdf_export:
                with mock.patch(
                    "importlib.import_module",
                    side_effect=ImportError("No module named Import"),
                ):
                    exit_code, stdout, stderr, working, result_path = self._execute(
                        tmp_dir,
                        outputs=[{"id": "part", "format": "step", "path": "part.step"}],
                        freecad_module=fake_freecad,
                    )

            self.assert_controlled_execute_failure(
                exit_code,
                stdout,
                stderr,
                substring="FreeCAD Import module is not available: No module named Import",
            )
            self.assertEqual(doc.events, ["recompute", "save", "close:ParametronTestDoc"])
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            csv_export.assert_not_called()
            pdf_export.assert_not_called()
            self.assert_failed_result(result_path, stage="artifact_export")
            self.assert_no_success_outputs(working / "part.step")

    def test_step_export_surface_non_callable_fails_and_closes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            doc = _FakeDocument(objects={"part": object()})
            fake_freecad = _FakeFreeCAD(doc)
            with mock.patch.dict(sys.modules, {"Import": SimpleNamespace(export="nope")}), mock.patch.object(
                headless,
                "export_csv_artifacts",
            ) as csv_export, mock.patch.object(
                headless,
                "export_pdf_artifacts",
            ) as pdf_export:
                exit_code, stdout, stderr, working, result_path = self._execute(
                    tmp_dir,
                    outputs=[{"id": "part", "format": "step", "path": "part.step"}],
                    freecad_module=fake_freecad,
                )

            self.assert_controlled_execute_failure(
                exit_code,
                stdout,
                stderr,
                substring="STEP exporter does not provide a callable export function (id='part')",
            )
            self.assertEqual(doc.events, ["recompute", "save", "getObject:part", "close:ParametronTestDoc"])
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            csv_export.assert_not_called()
            pdf_export.assert_not_called()
            self.assert_failed_result(result_path, stage="artifact_export")
            self.assert_no_success_outputs(working / "part.step")

    def test_step_export_exception_fails_without_artifact_or_later_exporters(self) -> None:
        def failing_export(objects: list[object], path: str) -> None:
            del objects, path
            raise RuntimeError("step boom")

        with tempfile.TemporaryDirectory() as tmp_dir:
            doc = _FakeDocument(objects={"part": object()})
            fake_freecad = _FakeFreeCAD(doc)
            with mock.patch.dict(sys.modules, {"Import": SimpleNamespace(export=failing_export)}), mock.patch.object(
                headless,
                "export_csv_artifacts",
            ) as csv_export, mock.patch.object(
                headless,
                "export_pdf_artifacts",
            ) as pdf_export:
                exit_code, stdout, stderr, working, result_path = self._execute(
                    tmp_dir,
                    outputs=[{"id": "part", "format": "step", "path": "part.step"}],
                    freecad_module=fake_freecad,
                )

            self.assert_controlled_execute_failure(
                exit_code,
                stdout,
                stderr,
                substring="STEP export raised an exception (id='part'): step boom",
            )
            self.assertEqual(doc.events, ["recompute", "save", "getObject:part", "close:ParametronTestDoc"])
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            csv_export.assert_not_called()
            pdf_export.assert_not_called()
            self.assert_failed_result(result_path, stage="artifact_export")
            self.assert_no_success_outputs(working / "part.step")

    def test_step_output_missing_parent_or_escaping_working_fails_before_export_call(self) -> None:
        cases = [
            (
                {"id": "part", "format": "step", "path": "missing/part.step"},
                "STEP output parent directory does not exist (id='part')",
                "missing/part.step",
            ),
            (
                {"id": "part", "format": "step", "path": "../part.step"},
                "STEP output path escapes working copy (id='part')",
                "../part.step",
            ),
        ]

        for output, substring, artifact_path in cases:
            with self.subTest(path=output["path"]), tempfile.TemporaryDirectory() as tmp_dir:
                export = mock.Mock(side_effect=AssertionError("STEP export should not be called"))
                doc = _FakeDocument(objects={"part": object()})
                fake_freecad = _FakeFreeCAD(doc)
                with mock.patch.dict(sys.modules, {"Import": SimpleNamespace(export=export)}), mock.patch.object(
                    headless,
                    "export_csv_artifacts",
                ) as csv_export, mock.patch.object(
                    headless,
                    "export_pdf_artifacts",
                ) as pdf_export:
                    exit_code, stdout, stderr, working, result_path = self._execute(
                        tmp_dir,
                        outputs=[output],
                        freecad_module=fake_freecad,
                    )

                self.assert_controlled_execute_failure(
                    exit_code,
                    stdout,
                    stderr,
                    substring=substring,
                )
                self.assertEqual(doc.events, ["recompute", "save", "getObject:part", "close:ParametronTestDoc"])
                self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
                export.assert_not_called()
                csv_export.assert_not_called()
                pdf_export.assert_not_called()
                self.assert_failed_result(result_path, stage="artifact_export")
                self.assert_no_success_outputs((working / artifact_path).resolve(strict=False))

    def test_csv_unsupported_request_surfaces_fail_and_close_before_pdf(self) -> None:
        class MissingGetObjectDocument:
            Name = "ParametronTestDoc"

            def __init__(self) -> None:
                self.events: list[str] = []

            def recompute(self) -> None:
                self.events.append("recompute")

            def save(self) -> None:
                self.events.append("save")

            @property
            def Objects(self) -> list[object]:
                return []

        class NonCallableGetObjectDocument(MissingGetObjectDocument):
            getObject = "not-callable"

        class RaisingGetObjectDocument(MissingGetObjectDocument):
            def getObject(self, name: str) -> object:
                self.events.append(f"getObject:{name}")
                raise RuntimeError(f"boom for {name}")

        cases = [
            (
                _FakeDocument(),
                {"id": "MissingSheet", "format": "csv", "path": "report.csv"},
                "document.getObject returned no spreadsheet object (id='MissingSheet')",
                "report.csv",
            ),
            (
                _FakeDocument(objects={"Sheet": object()}),
                {"id": "Sheet", "format": "csv", "path": "report.csv"},
                "spreadsheet object does not expose a supported cell data surface (id='Sheet')",
                "report.csv",
            ),
            (
                _FakeDocument(objects={"Sheet": _FakeSpreadsheet(["A1", "value"])}),
                {"id": "Sheet", "format": "csv", "path": "report.csv"},
                "spreadsheet object does not expose a supported cell data surface (id='Sheet')",
                "report.csv",
            ),
            (
                MissingGetObjectDocument(),
                {"id": "Sheet", "format": "csv", "path": "report.csv"},
                "document does not provide a callable getObject (id='Sheet')",
                "report.csv",
            ),
            (
                NonCallableGetObjectDocument(),
                {"id": "Sheet", "format": "csv", "path": "report.csv"},
                "document does not provide a callable getObject (id='Sheet')",
                "report.csv",
            ),
            (
                RaisingGetObjectDocument(),
                {"id": "Sheet", "format": "csv", "path": "report.csv"},
                "document.getObject raised an exception (id='Sheet'): boom for Sheet",
                "report.csv",
            ),
            (
                _FakeDocument(objects={"Sheet": _FakeSpreadsheet({"A1": "ok"})}),
                {"id": "Sheet", "format": "csv", "path": "missing/report.csv"},
                "CSV output parent directory does not exist (id='Sheet')",
                "missing/report.csv",
            ),
            (
                _FakeDocument(objects={"Sheet": _FakeSpreadsheet({"A1": "ok"})}),
                {"id": "Sheet", "format": "csv", "path": "../report.csv"},
                "CSV output path escapes working copy (id='Sheet')",
                "../report.csv",
            ),
        ]

        for doc, output, substring, artifact_path in cases:
            with self.subTest(substring=substring), tempfile.TemporaryDirectory() as tmp_dir:
                fake_freecad = _FakeFreeCAD(doc)
                assignment_patch = (
                    mock.patch.object(
                        headless,
                        "apply_parameter_assignments",
                        return_value=None,
                    )
                    if not callable(getattr(doc, "getObject", None))
                    else mock.patch.dict(sys.modules, {})
                )
                with assignment_patch, mock.patch.object(
                    headless,
                    "export_pdf_artifacts",
                ) as pdf_export:
                    exit_code, stdout, stderr, working, result_path = self._execute(
                        tmp_dir,
                        outputs=[output],
                        freecad_module=fake_freecad,
                    )

                self.assert_controlled_execute_failure(
                    exit_code,
                    stdout,
                    stderr,
                    substring=substring,
                )
                self.assertIn("close:ParametronTestDoc", doc.events)
                self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
                pdf_export.assert_not_called()
                self.assert_failed_result(result_path, stage="artifact_export")
                self.assert_no_success_outputs((working / artifact_path).resolve(strict=False))

    def test_pdf_exporter_and_page_surfaces_fail_and_close(self) -> None:
        class MissingGetObjectDocument:
            Name = "ParametronTestDoc"

            def __init__(self) -> None:
                self.events: list[str] = []

            def recompute(self) -> None:
                self.events.append("recompute")

            def save(self) -> None:
                self.events.append("save")

            @property
            def Objects(self) -> list[object]:
                return []

        class NonCallableGetObjectDocument(MissingGetObjectDocument):
            getObject = "not-callable"

        class RaisingGetObjectDocument(MissingGetObjectDocument):
            def getObject(self, name: str) -> object:
                self.events.append(f"getObject:{name}")
                raise RuntimeError(f"boom for {name}")

        def raising_export_page(page: object, path: str) -> None:
            del page, path
            raise RuntimeError("pdf boom")

        cases = [
            (
                _FakeDocument(objects={"drawing": object()}),
                None,
                "TechDrawGui module is not available: No module named TechDrawGui",
                "drawing.pdf",
                mock.patch(
                    "parametron_freecad.execution.pdf_export.import_module",
                    side_effect=ImportError("No module named TechDrawGui"),
                ),
            ),
            (
                _FakeDocument(objects={"drawing": object()}),
                SimpleNamespace(exportPageAsPdf="nope", export="also-nope"),
                "TechDrawGui exporter provides no supported PDF export function (id='drawing')",
                "drawing.pdf",
                mock.patch.dict(sys.modules, {}),
            ),
            (
                _FakeDocument(objects={"drawing": object()}),
                SimpleNamespace(exportPageAsPdf=raising_export_page),
                "PDF export raised an exception (id='drawing'): pdf boom",
                "drawing.pdf",
                mock.patch.dict(sys.modules, {}),
            ),
            (
                _FakeDocument(),
                SimpleNamespace(exportPageAsPdf=mock.Mock()),
                "document.getObject returned no page object (id='drawing')",
                "drawing.pdf",
                mock.patch.dict(sys.modules, {}),
            ),
            (
                MissingGetObjectDocument(),
                SimpleNamespace(exportPageAsPdf=mock.Mock()),
                "document does not provide a callable getObject (id='drawing')",
                "drawing.pdf",
                mock.patch.dict(sys.modules, {}),
            ),
            (
                NonCallableGetObjectDocument(),
                SimpleNamespace(exportPageAsPdf=mock.Mock()),
                "document does not provide a callable getObject (id='drawing')",
                "drawing.pdf",
                mock.patch.dict(sys.modules, {}),
            ),
            (
                RaisingGetObjectDocument(),
                SimpleNamespace(exportPageAsPdf=mock.Mock()),
                "document.getObject raised an exception (id='drawing'): boom for drawing",
                "drawing.pdf",
                mock.patch.dict(sys.modules, {}),
            ),
            (
                _FakeDocument(objects={"drawing": object()}),
                SimpleNamespace(exportPageAsPdf=mock.Mock()),
                "PDF output parent directory does not exist (id='drawing')",
                "missing/drawing.pdf",
                mock.patch.dict(sys.modules, {}),
            ),
            (
                _FakeDocument(objects={"drawing": object()}),
                SimpleNamespace(exportPageAsPdf=mock.Mock()),
                "PDF output path escapes working copy (id='drawing')",
                "../drawing.pdf",
                mock.patch.dict(sys.modules, {}),
            ),
        ]

        for doc, exporter, substring, output_path, import_patch in cases:
            with self.subTest(substring=substring), tempfile.TemporaryDirectory() as tmp_dir:
                fake_freecad = _FakeFreeCAD(doc)
                module_patch = (
                    mock.patch.dict(sys.modules, {"TechDrawGui": exporter})
                    if exporter is not None
                    else import_patch
                )
                assignment_patch = (
                    mock.patch.object(
                        headless,
                        "apply_parameter_assignments",
                        return_value=None,
                    )
                    if not callable(getattr(doc, "getObject", None))
                    else mock.patch.dict(sys.modules, {})
                )
                with assignment_patch, module_patch:
                    exit_code, stdout, stderr, working, result_path = self._execute(
                        tmp_dir,
                        outputs=[{"id": "drawing", "format": "pdf", "path": output_path}],
                        freecad_module=fake_freecad,
                    )

                self.assert_controlled_execute_failure(
                    exit_code,
                    stdout,
                    stderr,
                    substring=substring,
                )
                self.assertIn("close:ParametronTestDoc", doc.events)
                self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
                self.assert_failed_result(result_path, stage="artifact_export")
                self.assert_no_success_outputs((working / output_path).resolve(strict=False))

    def test_mixed_outputs_stop_after_csv_failure_without_later_pdf_export(self) -> None:
        def step_export(objects: list[object], path: str) -> None:
            del objects
            Path(path).write_text("step artifact\n", encoding="utf-8")

        pdf_export = mock.Mock(side_effect=AssertionError("PDF export should not be called"))

        with tempfile.TemporaryDirectory() as tmp_dir:
            doc = _FakeDocument(objects={"part": object()})
            fake_freecad = _FakeFreeCAD(doc)
            outputs = [
                {"id": "part", "format": "step", "path": "part.step"},
                {"id": "MissingSheet", "format": "csv", "path": "report.csv"},
                {"id": "drawing", "format": "pdf", "path": "drawing.pdf"},
            ]

            with mock.patch.dict(
                sys.modules,
                {
                    "Import": SimpleNamespace(export=step_export),
                    "TechDrawGui": SimpleNamespace(exportPageAsPdf=pdf_export),
                },
            ):
                exit_code, stdout, stderr, working, result_path = self._execute(
                    tmp_dir,
                    outputs=outputs,
                    freecad_module=fake_freecad,
                )

            self.assert_controlled_execute_failure(
                exit_code,
                stdout,
                stderr,
                substring="document.getObject returned no spreadsheet object (id='MissingSheet')",
            )
            self.assertEqual(
                doc.events,
                [
                    "recompute",
                    "save",
                    "getObject:part",
                    "getObject:MissingSheet",
                    "close:ParametronTestDoc",
                ],
            )
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            self.assertTrue((working / "part.step").exists())
            self.assert_failed_result(result_path, stage="artifact_export")
            self.assert_no_success_outputs(
                working / "report.csv",
                working / "drawing.pdf",
            )
            pdf_export.assert_not_called()


    def test_csv_write_failure_produces_controlled_failure_and_closes_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            doc = _FakeDocument(objects={"Sheet": _FakeSpreadsheet({"A1": "x"})})
            fake_freecad = _FakeFreeCAD(doc)
            working, manifest, result_path = self._make_working_copy(
                tmp_dir,
                outputs=[{"id": "Sheet", "format": "csv", "path": "report.csv"}],
            )
            # Place a directory at the output path so open(..., "w") raises OSError.
            (working / "report.csv").mkdir()

            exit_code, stdout, stderr = self._run_main(
                [
                    "execute",
                    "--working-copy",
                    str(working),
                    "--manifest",
                    str(manifest),
                    "--result",
                    str(result_path),
                ],
                freecad_module=fake_freecad,
            )

            self.assert_controlled_execute_failure(
                exit_code,
                stdout,
                stderr,
                substring="CSV file write failed",
            )
            self.assertIn("close:ParametronTestDoc", doc.events)
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            self.assert_failed_result(result_path, stage="artifact_export")


if __name__ == "__main__":
    unittest.main()
