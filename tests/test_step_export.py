from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.execution.step_export import (
    StepArtifactExportError,
    export_step_artifacts,
)


class _FakeDocument:
    def __init__(self, objects_by_name: dict[str, object]) -> None:
        self._objects_by_name = dict(objects_by_name)
        self.get_object_calls: list[str] = []

    def getObject(self, name: str) -> object | None:
        self.get_object_calls.append(name)
        return self._objects_by_name.get(name)

    @property
    def Objects(self):
        raise AssertionError("STEP export must not access document.Objects")


class _RecordingExporter:
    def __init__(self) -> None:
        self.calls: list[tuple[list[object], str]] = []

    def export(self, objects: list[object], path: str) -> None:
        self.calls.append((objects, path))


class StepExportImportSafetyTests(unittest.TestCase):
    def test_module_import_does_not_import_freecad_or_import_eagerly(self) -> None:
        module_name = "parametron_freecad.execution.step_export"
        original_import = __import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"FreeCAD", "Import"}:
                raise AssertionError(f"{name} should not be imported at module import time")
            return original_import(name, globals, locals, fromlist, level)

        previous = sys.modules.pop(module_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(module_name, previous)
            if previous is not None
            else sys.modules.pop(module_name, None)
        )

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module(module_name)

        self.assertIsNotNone(module)
        self.assertEqual(module.StepArtifactExportError.__name__, "StepArtifactExportError")


class StepExportHelperTests(unittest.TestCase):
    def _working_copy(self, tmp_dir: str) -> Path:
        working_copy = Path(tmp_dir) / "_working"
        working_copy.mkdir()
        return working_copy

    def create_symlink_or_skip(self, target: Path, link_path: Path) -> None:
        try:
            link_path.symlink_to(target)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is unavailable on this platform")

    def test_empty_outputs_are_accepted_and_do_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exporter = _RecordingExporter()

            export_step_artifacts(
                _FakeDocument({}),
                [],
                working_copy=working_copy,
                import_module=exporter,
            )

            self.assertEqual(exporter.calls, [])

    def test_non_step_outputs_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)

            class _ExplodingExporter:
                def export(self, objects, path) -> None:
                    raise AssertionError("non-step outputs must not be exported")

            export_step_artifacts(
                _FakeDocument({}),
                [
                    {"id": "report", "format": "csv", "path": "report.csv"},
                    {"id": "drawing", "format": "pdf", "path": "drawing.pdf"},
                ],
                working_copy=working_copy,
                import_module=_ExplodingExporter(),
            )

    def test_step_outputs_are_exported_in_manifest_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "artifacts").mkdir()
            (working_copy / "nested").mkdir()
            body_object = object()
            pad_object = object()
            document = _FakeDocument({"Body": body_object, "Pad": pad_object})
            exporter = _RecordingExporter()

            export_step_artifacts(
                document,
                [
                    {"id": "csv-report", "format": "csv", "path": "ignored.csv"},
                    {"id": "Body", "format": "step", "path": "artifacts/a.step"},
                    {"id": "drawing", "format": "pdf", "path": "ignored.pdf"},
                    {"id": "Pad", "format": "step", "path": "nested/b.step"},
                ],
                working_copy=working_copy,
                import_module=exporter,
            )

            self.assertEqual(document.get_object_calls, ["Body", "Pad"])
            self.assertEqual(len(exporter.calls), 2)
            self.assertEqual(
                [call[1] for call in exporter.calls],
                [
                    str((working_copy / "artifacts" / "a.step").resolve()),
                    str((working_copy / "nested" / "b.step").resolve()),
                ],
            )
            self.assertEqual(exporter.calls[0][0], [body_object])
            self.assertEqual(exporter.calls[1][0], [pad_object])

    def test_relative_step_output_paths_resolve_against_working_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()
            exporter = _RecordingExporter()

            export_step_artifacts(
                _FakeDocument({"part": "Body"}),
                [{"id": "part", "format": "step", "path": "exports/part.step"}],
                working_copy=working_copy,
                import_module=exporter,
            )

            self.assertEqual(
                exporter.calls,
                [(["Body"], str((working_copy / "exports" / "part.step").resolve()))],
            )

    def test_absolute_step_output_path_inside_working_copy_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            exporter = _RecordingExporter()
            output_path = exports_dir / "part.step"

            export_step_artifacts(
                _FakeDocument({"part": "Body"}),
                [{"id": "part", "format": "step", "path": str(output_path)}],
                working_copy=working_copy,
                import_module=exporter,
            )

            self.assertEqual(exporter.calls, [(["Body"], str(output_path.resolve()))])

    def test_relative_traversal_outside_working_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)

            with self.assertRaisesRegex(
                StepArtifactExportError,
                r"^STEP output path escapes working copy \(id='part'\): ",
            ) as ctx:
                export_step_artifacts(
                    _FakeDocument({"part": object()}),
                    [{"id": "part", "format": "step", "path": "../outside.step"}],
                    working_copy=working_copy,
                    import_module=_RecordingExporter(),
                )

            self.assertNotIn("Traceback", str(ctx.exception))

    def test_absolute_path_outside_working_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            outside_path = Path(tmp_dir) / "outside.step"

            with self.assertRaisesRegex(
                StepArtifactExportError,
                r"^STEP output path escapes working copy \(id='part'\): ",
            ):
                export_step_artifacts(
                    _FakeDocument({"part": object()}),
                    [{"id": "part", "format": "step", "path": str(outside_path)}],
                    working_copy=working_copy,
                    import_module=_RecordingExporter(),
                )

    def test_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            outside_dir = Path(tmp_dir) / "outside"
            outside_dir.mkdir()
            link_dir = working_copy / "exports"
            self.create_symlink_or_skip(outside_dir, link_dir)

            with self.assertRaisesRegex(
                StepArtifactExportError,
                r"^STEP output path escapes working copy \(id='part'\): ",
            ):
                export_step_artifacts(
                    _FakeDocument({"part": object()}),
                    [{"id": "part", "format": "step", "path": "exports/part.step"}],
                    working_copy=working_copy,
                    import_module=_RecordingExporter(),
                )

    def test_missing_output_parent_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)

            with self.assertRaisesRegex(
                StepArtifactExportError,
                r"^STEP output parent directory does not exist \(id='part'\): ",
            ):
                export_step_artifacts(
                    _FakeDocument({"part": object()}),
                    [{"id": "part", "format": "step", "path": "missing/part.step"}],
                    working_copy=working_copy,
                    import_module=_RecordingExporter(),
                )

    def test_output_parent_that_is_a_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            parent_file = working_copy / "exports"
            parent_file.write_text("not a directory", encoding="utf-8")

            with self.assertRaisesRegex(
                StepArtifactExportError,
                r"^STEP output parent path is not a directory \(id='part'\): ",
            ):
                export_step_artifacts(
                    _FakeDocument({"part": object()}),
                    [{"id": "part", "format": "step", "path": "exports/part.step"}],
                    working_copy=working_copy,
                    import_module=_RecordingExporter(),
                )

    def test_injected_exporter_is_used_without_importing_import_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()
            exporter = _RecordingExporter()

            with mock.patch(
                "importlib.import_module",
                side_effect=AssertionError("Import should not be imported when exporter is injected"),
            ):
                export_step_artifacts(
                    _FakeDocument({"part": "Body"}),
                    [{"id": "part", "format": "step", "path": "exports/part.step"}],
                    working_copy=working_copy,
                    import_module=exporter,
                )

            self.assertEqual(len(exporter.calls), 1)

    def test_import_module_is_loaded_lazily_when_not_injected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()
            exporter = _RecordingExporter()

            with mock.patch("importlib.import_module", return_value=exporter) as patched:
                export_step_artifacts(
                    _FakeDocument({"part": "Body"}),
                    [{"id": "part", "format": "step", "path": "exports/part.step"}],
                    working_copy=working_copy,
                )

            patched.assert_called_once_with("Import")
            self.assertEqual(len(exporter.calls), 1)

    def test_missing_import_module_becomes_deterministic_step_export_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            with mock.patch(
                "importlib.import_module",
                side_effect=ImportError("No module named Import"),
            ):
                with self.assertRaisesRegex(
                    StepArtifactExportError,
                    r"^FreeCAD Import module is not available: No module named Import$",
                ) as ctx:
                    export_step_artifacts(
                        _FakeDocument({"part": "Body"}),
                        [{"id": "part", "format": "step", "path": "exports/part.step"}],
                        working_copy=working_copy,
                    )

            self.assertNotIn("Traceback", str(ctx.exception))

    def test_missing_callable_export_function_becomes_deterministic_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            with self.assertRaisesRegex(
                StepArtifactExportError,
                r"^STEP exporter does not provide a callable export function \(id='part'\)$",
            ) as ctx:
                export_step_artifacts(
                    _FakeDocument({"part": "Body"}),
                    [{"id": "part", "format": "step", "path": "exports/part.step"}],
                    working_copy=working_copy,
                    import_module=object(),
                )

            self.assertNotIn("Traceback", str(ctx.exception))

    def test_exporter_exceptions_become_deterministic_step_export_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            class _ExplodingExporter:
                def export(self, objects, path) -> None:
                    del objects, path
                    raise ValueError("boom")

            with self.assertRaisesRegex(
                StepArtifactExportError,
                r"^STEP export raised an exception \(id='part'\): boom$",
            ) as ctx:
                export_step_artifacts(
                    _FakeDocument({"part": "Body"}),
                    [{"id": "part", "format": "step", "path": "exports/part.step"}],
                    working_copy=working_copy,
                    import_module=_ExplodingExporter(),
                )

            message = str(ctx.exception)
            self.assertNotIn("Traceback", message)
            self.assertNotIn("ValueError", message)

    def test_export_step_artifacts_exports_exact_selected_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "outputs").mkdir()
            body_object = object()
            document = _FakeDocument({"Body": body_object})
            exporter = _RecordingExporter()

            export_step_artifacts(
                document,
                [{"id": "Body", "format": "step", "path": "outputs/body.step"}],
                working_copy=working_copy,
                import_module=exporter,
            )

            self.assertEqual(document.get_object_calls, ["Body"])
            self.assertEqual(len(exporter.calls), 1)
            self.assertEqual(exporter.calls[0][0], [body_object])

    def test_export_step_artifacts_allows_repeated_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "outputs").mkdir()
            body_object = object()
            document = _FakeDocument({"Body": body_object})
            exporter = _RecordingExporter()

            export_step_artifacts(
                document,
                [
                    {"id": "Body", "format": "step", "path": "outputs/primary.step"},
                    {"id": "Body", "format": "step", "path": "outputs/archive.step"},
                ],
                working_copy=working_copy,
                import_module=exporter,
            )

            self.assertEqual(document.get_object_calls, ["Body", "Body"])
            self.assertEqual([call[0] for call in exporter.calls], [[body_object], [body_object]])
            self.assertEqual(
                [Path(call[1]).name for call in exporter.calls], ["primary.step", "archive.step"]
            )

    def test_export_step_artifacts_rejects_missing_selected_object_and_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "outputs").mkdir()
            document = _FakeDocument({"Body": object()})
            exporter = _RecordingExporter()

            with self.assertRaisesRegex(StepArtifactExportError, "Missing"):
                export_step_artifacts(
                    document,
                    [
                        {"id": "Missing", "format": "step", "path": "outputs/missing.step"},
                        {"id": "Body", "format": "step", "path": "outputs/body.step"},
                    ],
                    working_copy=working_copy,
                    import_module=exporter,
                )

            self.assertEqual(document.get_object_calls, ["Missing"])
            self.assertEqual(exporter.calls, [])

    def test_export_step_artifacts_wraps_get_object_exception(self) -> None:
        class _ExplodingDocument:
            def getObject(self, name):
                raise RuntimeError(f"lookup boom for {name}")

            @property
            def Objects(self):
                raise AssertionError("STEP export must not access document.Objects")

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "outputs").mkdir()
            exporter = _RecordingExporter()
            with self.assertRaisesRegex(
                StepArtifactExportError, r"getObject raised an exception.*Body.*lookup boom for Body"
            ) as ctx:
                export_step_artifacts(
                    _ExplodingDocument(),
                    [{"id": "Body", "format": "step", "path": "outputs/body.step"}],
                    working_copy=working_copy,
                    import_module=exporter,
                )
            self.assertNotIn("Traceback", str(ctx.exception))
            self.assertEqual(exporter.calls, [])

    def test_export_step_artifacts_requires_callable_get_object(self) -> None:
        for document in (object(), type("NoLookup", (), {"getObject": None})(), type("BadLookup", (), {"getObject": "not-callable"})()):
            with self.subTest(document=type(document).__name__), tempfile.TemporaryDirectory() as tmp_dir:
                working_copy = self._working_copy(tmp_dir)
                (working_copy / "outputs").mkdir()
                with self.assertRaisesRegex(StepArtifactExportError, "callable getObject.*Body"):
                    export_step_artifacts(
                        document,
                        [{"id": "Body", "format": "step", "path": "outputs/body.step"}],
                        working_copy=working_copy,
                        import_module=_RecordingExporter(),
                    )

    def test_export_step_artifacts_exact_name_has_no_case_or_label_fallback(self) -> None:
        class _NamedObject:
            Name = "Body001"
            Label = "Body"

        for selector in ("body", "Body"):
            with self.subTest(selector=selector), tempfile.TemporaryDirectory() as tmp_dir:
                working_copy = self._working_copy(tmp_dir)
                (working_copy / "outputs").mkdir()
                document = _FakeDocument({"Body001": _NamedObject()})
                with self.assertRaisesRegex(StepArtifactExportError, selector):
                    export_step_artifacts(
                        document,
                        [{"id": selector, "format": "step", "path": "outputs/body.step"}],
                        working_copy=working_copy,
                        import_module=_RecordingExporter(),
                    )
                self.assertEqual(document.get_object_calls, [selector])


if __name__ == "__main__":
    unittest.main()
