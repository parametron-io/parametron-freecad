from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.execution.pdf_export import (
    PdfArtifactExportError,
    export_pdf_artifacts,
)


class _FakeDocument:
    def __init__(self, objects: dict[str, object] | None = None) -> None:
        self._objects = dict(objects or {})
        self.get_object_calls: list[str] = []

    def getObject(self, name: str) -> object | None:
        self.get_object_calls.append(name)
        return self._objects.get(name)


class _ExplodingDocument:
    def getObject(self, name: str) -> object:
        raise AssertionError(f"getObject should not be called for {name!r}")


class _RecordingPdfExporter:
    def __init__(self) -> None:
        self.page_calls: list[tuple[object, str]] = []
        self.export_calls: list[tuple[list[object], str]] = []

    def exportPageAsPdf(self, page: object, path: str) -> None:
        self.page_calls.append((page, path))

    def export(self, pages: list[object], path: str) -> None:
        self.export_calls.append((pages, path))


class PdfExportImportSafetyTests(unittest.TestCase):
    def test_module_import_does_not_require_freecad_or_techdraw(self) -> None:
        module_name = "parametron_freecad.execution.pdf_export"
        guarded_names = {"FreeCAD", "FreeCADGui", "TechDraw", "TechDrawGui", "Qt"}
        original_import = __import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in guarded_names:
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
        self.assertEqual(module.PdfArtifactExportError.__name__, "PdfArtifactExportError")
        self.assertTrue(callable(module.export_pdf_artifacts))


class PdfExportHelperTests(unittest.TestCase):
    def _working_copy(self, tmp_dir: str) -> Path:
        working_copy = Path(tmp_dir) / "_working"
        working_copy.mkdir()
        return working_copy

    def create_symlink_or_skip(self, target: Path, link_path: Path) -> None:
        try:
            link_path.symlink_to(target)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is unavailable on this platform")

    def test_non_pdf_outputs_are_ignored_without_importing_exporter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()

            with mock.patch(
                "parametron_freecad.execution.pdf_export.import_module",
                side_effect=AssertionError("TechDrawGui should not be imported"),
            ):
                export_pdf_artifacts(
                    _ExplodingDocument(),
                    [
                        {"id": "part", "format": "step", "path": "exports/part.step"},
                        {"id": "sheet", "format": "csv", "path": "exports/report.csv"},
                        {"id": "drawing", "format": "PDF", "path": "exports/drawing.pdf"},
                    ],
                    working_copy=working_copy,
                )

            self.assertEqual(list(exports_dir.iterdir()), [])

    def test_only_exact_pdf_outputs_are_exported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            exporter = _RecordingPdfExporter()
            page = object()
            document = _FakeDocument({"drawing": page, "ignored-upper": object()})

            export_pdf_artifacts(
                document,
                [
                    {"id": "sheet", "format": "csv", "path": "exports/report.csv"},
                    {"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"},
                    {"id": "part", "format": "step", "path": "exports/part.step"},
                    {"id": "ignored-upper", "format": "PDF", "path": "exports/upper.pdf"},
                ],
                working_copy=working_copy,
                techdraw_gui_module=exporter,
            )

            self.assertEqual(document.get_object_calls, ["drawing"])
            self.assertEqual(
                exporter.page_calls,
                [(page, str((exports_dir / "drawing.pdf").resolve()))],
            )
            self.assertEqual(exporter.export_calls, [])

    def test_pdf_outputs_are_exported_in_manifest_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            nested_dir = working_copy / "nested"
            exports_dir.mkdir()
            nested_dir.mkdir()
            first_page = object()
            second_page = object()
            exporter = _RecordingPdfExporter()
            document = _FakeDocument({"first": first_page, "second": second_page})

            export_pdf_artifacts(
                document,
                [
                    {"id": "sheet", "format": "csv", "path": "exports/report.csv"},
                    {"id": "first", "format": "pdf", "path": "exports/first.pdf"},
                    {"id": "part", "format": "step", "path": "exports/part.step"},
                    {"id": "second", "format": "pdf", "path": "nested/second.pdf"},
                ],
                working_copy=working_copy,
                techdraw_gui_module=exporter,
            )

            self.assertEqual(document.get_object_calls, ["first", "second"])
            self.assertEqual(
                exporter.page_calls,
                [
                    (first_page, str((exports_dir / "first.pdf").resolve())),
                    (second_page, str((nested_dir / "second.pdf").resolve())),
                ],
            )

    def test_relative_output_path_inside_working_copy_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            exporter = _RecordingPdfExporter()
            page = object()

            export_pdf_artifacts(
                _FakeDocument({"drawing": page}),
                [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                working_copy=working_copy,
                techdraw_gui_module=exporter,
            )

            self.assertEqual(
                exporter.page_calls,
                [(page, str((exports_dir / "drawing.pdf").resolve()))],
            )

    def test_absolute_output_path_inside_working_copy_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            output_path = exports_dir / "drawing.pdf"
            exporter = _RecordingPdfExporter()
            page = object()

            export_pdf_artifacts(
                _FakeDocument({"drawing": page}),
                [{"id": "drawing", "format": "pdf", "path": str(output_path)}],
                working_copy=working_copy,
                techdraw_gui_module=exporter,
            )

            self.assertEqual(exporter.page_calls, [(page, str(output_path.resolve()))])

    def test_relative_traversal_outside_working_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)

            with self.assertRaisesRegex(
                PdfArtifactExportError,
                r"^PDF output path escapes working copy \(id='drawing'\): ",
            ):
                export_pdf_artifacts(
                    _FakeDocument({"drawing": object()}),
                    [{"id": "drawing", "format": "pdf", "path": "../outside.pdf"}],
                    working_copy=working_copy,
                    techdraw_gui_module=_RecordingPdfExporter(),
                )

    def test_absolute_output_path_outside_working_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            outside_path = Path(tmp_dir) / "outside.pdf"

            with self.assertRaisesRegex(
                PdfArtifactExportError,
                r"^PDF output path escapes working copy \(id='drawing'\): ",
            ):
                export_pdf_artifacts(
                    _FakeDocument({"drawing": object()}),
                    [{"id": "drawing", "format": "pdf", "path": str(outside_path)}],
                    working_copy=working_copy,
                    techdraw_gui_module=_RecordingPdfExporter(),
                )

    def test_missing_output_parent_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)

            with self.assertRaisesRegex(
                PdfArtifactExportError,
                r"^PDF output parent directory does not exist \(id='drawing'\): ",
            ):
                export_pdf_artifacts(
                    _FakeDocument({"drawing": object()}),
                    [{"id": "drawing", "format": "pdf", "path": "missing/drawing.pdf"}],
                    working_copy=working_copy,
                    techdraw_gui_module=_RecordingPdfExporter(),
                )

    def test_output_parent_that_is_a_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            parent_file = working_copy / "exports"
            parent_file.write_text("not-a-directory", encoding="utf-8")

            with self.assertRaisesRegex(
                PdfArtifactExportError,
                r"^PDF output parent path is not a directory \(id='drawing'\): ",
            ):
                export_pdf_artifacts(
                    _FakeDocument({"drawing": object()}),
                    [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                    working_copy=working_copy,
                    techdraw_gui_module=_RecordingPdfExporter(),
                )

    def test_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            outside_dir = Path(tmp_dir) / "outside"
            outside_dir.mkdir()
            link_dir = working_copy / "exports"
            self.create_symlink_or_skip(outside_dir, link_dir)

            with self.assertRaisesRegex(
                PdfArtifactExportError,
                r"^PDF output path escapes working copy \(id='drawing'\): ",
            ):
                export_pdf_artifacts(
                    _FakeDocument({"drawing": object()}),
                    [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                    working_copy=working_copy,
                    techdraw_gui_module=_RecordingPdfExporter(),
                )

    def test_missing_getobject_surface_fails_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            with self.assertRaisesRegex(
                PdfArtifactExportError,
                r"^document does not provide a callable getObject \(id='drawing'\)$",
            ) as ctx:
                export_pdf_artifacts(
                    object(),
                    [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                    working_copy=working_copy,
                    techdraw_gui_module=_RecordingPdfExporter(),
                )

            self.assertNotIn("Traceback", str(ctx.exception))

    def test_noncallable_getobject_surface_fails_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            class _BadDocument:
                getObject = "not-callable"

            with self.assertRaisesRegex(
                PdfArtifactExportError,
                r"^document does not provide a callable getObject \(id='drawing'\)$",
            ):
                export_pdf_artifacts(
                    _BadDocument(),
                    [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                    working_copy=working_copy,
                    techdraw_gui_module=_RecordingPdfExporter(),
                )

    def test_getobject_exception_becomes_deterministic_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            class _BadDocument:
                def getObject(self, name: str) -> object:
                    raise RuntimeError(f"boom for {name}")

            with self.assertRaisesRegex(
                PdfArtifactExportError,
                r"^document.getObject raised an exception \(id='drawing'\): boom for drawing$",
            ):
                export_pdf_artifacts(
                    _BadDocument(),
                    [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                    working_copy=working_copy,
                    techdraw_gui_module=_RecordingPdfExporter(),
                )

    def test_missing_declared_page_object_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            with self.assertRaisesRegex(
                PdfArtifactExportError,
                r"^document.getObject returned no page object \(id='drawing'\)$",
            ):
                export_pdf_artifacts(
                    _FakeDocument({}),
                    [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                    working_copy=working_copy,
                    techdraw_gui_module=_RecordingPdfExporter(),
                )

    def test_export_receives_exact_page_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            page = object()
            exporter = _RecordingPdfExporter()

            export_pdf_artifacts(
                _FakeDocument({"drawing": page}),
                [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                working_copy=working_copy,
                techdraw_gui_module=exporter,
            )

            self.assertIs(exporter.page_calls[0][0], page)

    def test_prefers_export_page_as_pdf_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            page = object()
            exporter = _RecordingPdfExporter()

            export_pdf_artifacts(
                _FakeDocument({"drawing": page}),
                [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                working_copy=working_copy,
                techdraw_gui_module=exporter,
            )

            self.assertEqual(len(exporter.page_calls), 1)
            self.assertEqual(exporter.export_calls, [])

    def test_falls_back_to_export_list_api_when_preferred_api_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            page = object()

            class _FallbackOnlyExporter:
                def __init__(self) -> None:
                    self.export_calls: list[tuple[list[object], str]] = []

                def export(self, pages: list[object], path: str) -> None:
                    self.export_calls.append((pages, path))

            exporter = _FallbackOnlyExporter()

            export_pdf_artifacts(
                _FakeDocument({"drawing": page}),
                [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                working_copy=working_copy,
                techdraw_gui_module=exporter,
            )

            self.assertEqual(
                exporter.export_calls,
                [([page], str((exports_dir / "drawing.pdf").resolve()))],
            )

    def test_falls_back_to_export_list_api_when_preferred_api_is_noncallable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            page = object()

            class _NonCallablePreferredExporter:
                def __init__(self) -> None:
                    self.exportPageAsPdf = "not-callable"
                    self.export_calls: list[tuple[list[object], str]] = []

                def export(self, pages: list[object], path: str) -> None:
                    self.export_calls.append((pages, path))

            exporter = _NonCallablePreferredExporter()

            export_pdf_artifacts(
                _FakeDocument({"drawing": page}),
                [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                working_copy=working_copy,
                techdraw_gui_module=exporter,
            )

            self.assertEqual(
                exporter.export_calls,
                [([page], str((exports_dir / "drawing.pdf").resolve()))],
            )

    def test_unsupported_exporter_surface_raises_deterministic_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            with self.assertRaisesRegex(
                PdfArtifactExportError,
                r"^TechDrawGui exporter provides no supported PDF export function "
                r"\(id='drawing'\): tried exportPageAsPdf and export$",
            ):
                export_pdf_artifacts(
                    _FakeDocument({"drawing": object()}),
                    [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                    working_copy=working_copy,
                    techdraw_gui_module=object(),
                )

    def test_exporter_exception_is_converted_to_pdf_artifact_export_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            class _ExplodingExporter:
                def exportPageAsPdf(self, page: object, path: str) -> None:
                    del page, path
                    raise RuntimeError("fake pdf boom")

            with self.assertRaisesRegex(
                PdfArtifactExportError,
                r"^PDF export raised an exception \(id='drawing'\): fake pdf boom$",
            ) as ctx:
                export_pdf_artifacts(
                    _FakeDocument({"drawing": object()}),
                    [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                    working_copy=working_copy,
                    techdraw_gui_module=_ExplodingExporter(),
                )

            self.assertNotIn("Traceback", str(ctx.exception))

    def test_lazy_import_occurs_only_when_pdf_output_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            imported_exporter = _RecordingPdfExporter()
            document = _FakeDocument({"drawing": object()})

            with mock.patch(
                "parametron_freecad.execution.pdf_export.import_module",
                return_value=imported_exporter,
            ) as import_module_mock:
                export_pdf_artifacts(
                    document,
                    [{"id": "sheet", "format": "csv", "path": "exports/report.csv"}],
                    working_copy=working_copy,
                )
                self.assertEqual(import_module_mock.call_count, 0)

                export_pdf_artifacts(
                    document,
                    [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                    working_copy=working_copy,
                )

            self.assertEqual(import_module_mock.call_args_list, [mock.call("TechDrawGui")])
            self.assertEqual(document.get_object_calls, ["drawing"])

    def test_lazy_import_failure_becomes_pdf_artifact_export_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            with mock.patch(
                "parametron_freecad.execution.pdf_export.import_module",
                side_effect=ImportError("No module named TechDrawGui"),
            ):
                with self.assertRaisesRegex(
                    PdfArtifactExportError,
                    r"^TechDrawGui module is not available: No module named TechDrawGui$",
                ):
                    export_pdf_artifacts(
                        _FakeDocument({"drawing": object()}),
                        [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}],
                        working_copy=working_copy,
                    )


if __name__ == "__main__":
    unittest.main()
