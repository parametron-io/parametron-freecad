from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.execution.csv_export import (
    CsvArtifactExportError,
    export_csv_artifacts,
)


class _FakeSpreadsheet:
    def __init__(self, content) -> None:
        self.Content = content


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


class CsvExportImportSafetyTests(unittest.TestCase):
    def test_module_import_does_not_require_freecad(self) -> None:
        module_name = "parametron_freecad.execution.csv_export"
        original_import = __import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "FreeCAD":
                raise AssertionError("FreeCAD should not be imported at module import time")
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
        self.assertEqual(module.CsvArtifactExportError.__name__, "CsvArtifactExportError")
        self.assertTrue(callable(module.export_csv_artifacts))


class CsvExportHelperTests(unittest.TestCase):
    def _working_copy(self, tmp_dir: str) -> Path:
        working_copy = Path(tmp_dir) / "_working"
        working_copy.mkdir()
        return working_copy

    def create_symlink_or_skip(self, target: Path, link_path: Path) -> None:
        try:
            link_path.symlink_to(target)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is unavailable on this platform")

    def test_non_csv_outputs_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()

            document = _ExplodingDocument()

            export_csv_artifacts(
                document,
                [
                    {"id": "part", "format": "step", "path": "exports/part.step"},
                    {"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"},
                ],
                working_copy=working_copy,
            )

            self.assertEqual(list(exports_dir.iterdir()), [])

    def test_writes_deterministic_csv_from_mapping_like_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            output_path = exports_dir / "report.csv"
            content = {
                "B2": "bottom-right",
                "A2": "cilek",
                "A1": "top-left",
                "C1": None,
                "AA1": 42,
            }
            document = _FakeDocument({"Sheet": _FakeSpreadsheet(content)})

            export_csv_artifacts(
                document,
                [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                working_copy=working_copy,
            )

            expected = (
                ",".join(["top-left"] + [""] * 25 + ["42"]) + "\n"
                + ",".join(["cilek", "bottom-right"] + [""] * 25) + "\n"
            ).encode("utf-8")
            self.assertEqual(output_path.read_bytes(), expected)
            self.assertNotIn(b"\r\n", expected)

    def test_multi_letter_columns_are_ordered_after_z(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            output_path = exports_dir / "columns.csv"
            content = {
                "AB1": "after-aa",
                "AA1": "after-z",
                "A1": "first",
                "Z1": "last-single-letter",
            }
            document = _FakeDocument({"Sheet": _FakeSpreadsheet(content)})

            export_csv_artifacts(
                document,
                [{"id": "Sheet", "format": "csv", "path": "exports/columns.csv"}],
                working_copy=working_copy,
            )

            expected = (
                ",".join(
                    ["first"] + [""] * 24 + ["last-single-letter", "after-z", "after-aa"]
                )
                + "\n"
            ).encode("utf-8")
            self.assertEqual(output_path.read_bytes(), expected)

    def test_empty_spreadsheet_writes_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            output_path = exports_dir / "empty.csv"
            document = _FakeDocument({"Sheet": _FakeSpreadsheet({})})

            export_csv_artifacts(
                document,
                [{"id": "Sheet", "format": "csv", "path": "exports/empty.csv"}],
                working_copy=working_copy,
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), b"")

    def test_existing_file_is_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            output_path = exports_dir / "report.csv"
            output_path.write_text("stale-data\r\n", encoding="utf-8")
            document = _FakeDocument({"Sheet": _FakeSpreadsheet({"A1": "fresh"})})

            export_csv_artifacts(
                document,
                [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                working_copy=working_copy,
            )

            self.assertEqual(output_path.read_bytes(), b"fresh\n")

    def test_manifest_order_controls_getobject_lookup_and_target_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            document = _FakeDocument(
                {
                    "SecondSheet": _FakeSpreadsheet({"A1": "two"}),
                    "FirstSheet": _FakeSpreadsheet({"A1": "one"}),
                }
            )

            export_csv_artifacts(
                document,
                [
                    {"id": "SecondSheet", "format": "csv", "path": "exports/second.csv"},
                    {"id": "FirstSheet", "format": "csv", "path": "exports/first.csv"},
                ],
                working_copy=working_copy,
            )

            self.assertEqual(document.get_object_calls, ["SecondSheet", "FirstSheet"])
            self.assertEqual((exports_dir / "second.csv").read_bytes(), b"two\n")
            self.assertEqual((exports_dir / "first.csv").read_bytes(), b"one\n")

    def test_missing_getobject_surface_fails_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^document does not provide a callable getObject \(id='Sheet'\)$",
            ) as ctx:
                export_csv_artifacts(
                    object(),
                    [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                    working_copy=working_copy,
                )

            self.assertNotIn("Traceback", str(ctx.exception))

    def test_noncallable_getobject_surface_fails_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            class _BadDocument:
                getObject = "not-callable"

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^document does not provide a callable getObject \(id='Sheet'\)$",
            ):
                export_csv_artifacts(
                    _BadDocument(),
                    [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                    working_copy=working_copy,
                )

    def test_getobject_exception_becomes_deterministic_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            class _BadDocument:
                def getObject(self, name: str) -> object:
                    raise RuntimeError(f"boom for {name}")

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^document.getObject raised an exception \(id='Sheet'\): boom for Sheet$",
            ):
                export_csv_artifacts(
                    _BadDocument(),
                    [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                    working_copy=working_copy,
                )

    def test_missing_declared_spreadsheet_object_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()
            document = _FakeDocument({})

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^document.getObject returned no spreadsheet object \(id='MissingSheet'\)$",
            ):
                export_csv_artifacts(
                    document,
                    [{"id": "MissingSheet", "format": "csv", "path": "exports/report.csv"}],
                    working_copy=working_copy,
                )

    def test_missing_content_surface_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()

            class _SpreadsheetWithoutContent:
                pass

            document = _FakeDocument({"Sheet": _SpreadsheetWithoutContent()})

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^spreadsheet object does not expose a supported cell data surface \(id='Sheet'\)$",
            ):
                export_csv_artifacts(
                    document,
                    [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                    working_copy=working_copy,
                )

    def test_non_mapping_content_surface_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            (working_copy / "exports").mkdir()
            document = _FakeDocument({"Sheet": _FakeSpreadsheet(["A1", "x"])})

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^spreadsheet object does not expose a supported cell data surface \(id='Sheet'\)$",
            ):
                export_csv_artifacts(
                    document,
                    [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                    working_copy=working_copy,
                )

    def test_invalid_cell_addresses_are_skipped_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            output_path = exports_dir / "report.csv"
            content = {
                "not-a-cell": "ignored",
                "A0": "ignored",
                "1A": "ignored",
                "B1": "kept",
                "A2": "also-kept",
            }
            document = _FakeDocument({"Sheet": _FakeSpreadsheet(content)})

            export_csv_artifacts(
                document,
                [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                working_copy=working_copy,
            )

            self.assertEqual(output_path.read_bytes(), b",kept\nalso-kept,\n")

    def test_all_invalid_cell_addresses_produce_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            output_path = exports_dir / "report.csv"
            document = _FakeDocument(
                {"Sheet": _FakeSpreadsheet({"A0": "ignored", "invalid": "ignored"})}
            )

            export_csv_artifacts(
                document,
                [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                working_copy=working_copy,
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), b"")

    def test_relative_output_path_inside_working_copy_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            output_path = exports_dir / "report.csv"
            document = _FakeDocument({"Sheet": _FakeSpreadsheet({"A1": "ok"})})

            export_csv_artifacts(
                document,
                [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                working_copy=working_copy,
            )

            self.assertEqual(output_path.read_bytes(), b"ok\n")

    def test_absolute_output_path_inside_working_copy_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            output_path = exports_dir / "report.csv"
            document = _FakeDocument({"Sheet": _FakeSpreadsheet({"A1": "ok"})})

            export_csv_artifacts(
                document,
                [{"id": "Sheet", "format": "csv", "path": str(output_path)}],
                working_copy=working_copy,
            )

            self.assertEqual(output_path.read_bytes(), b"ok\n")

    def test_relative_traversal_outside_working_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^CSV output path escapes working copy \(id='Sheet'\): ",
            ):
                export_csv_artifacts(
                    _FakeDocument({"Sheet": _FakeSpreadsheet({"A1": "x"})}),
                    [{"id": "Sheet", "format": "csv", "path": "../outside.csv"}],
                    working_copy=working_copy,
                )

    def test_absolute_output_path_outside_working_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            outside_path = Path(tmp_dir) / "outside.csv"

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^CSV output path escapes working copy \(id='Sheet'\): ",
            ):
                export_csv_artifacts(
                    _FakeDocument({"Sheet": _FakeSpreadsheet({"A1": "x"})}),
                    [{"id": "Sheet", "format": "csv", "path": str(outside_path)}],
                    working_copy=working_copy,
                )

    def test_missing_output_parent_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^CSV output parent directory does not exist \(id='Sheet'\): ",
            ):
                export_csv_artifacts(
                    _FakeDocument({"Sheet": _FakeSpreadsheet({"A1": "x"})}),
                    [{"id": "Sheet", "format": "csv", "path": "missing/report.csv"}],
                    working_copy=working_copy,
                )

    def test_output_parent_that_is_a_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            parent_file = working_copy / "exports"
            parent_file.write_text("not-a-directory", encoding="utf-8")

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^CSV output parent path is not a directory \(id='Sheet'\): ",
            ):
                export_csv_artifacts(
                    _FakeDocument({"Sheet": _FakeSpreadsheet({"A1": "x"})}),
                    [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                    working_copy=working_copy,
                )

    def test_file_write_failure_raises_deterministic_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            exports_dir = working_copy / "exports"
            exports_dir.mkdir()
            # A directory at the output path makes open(..., "w") raise IsADirectoryError
            # (a subclass of OSError) on POSIX and PermissionError on Windows — both OSError.
            (exports_dir / "report.csv").mkdir()
            document = _FakeDocument({"Sheet": _FakeSpreadsheet({"A1": "x"})})

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^CSV file write failed .+report\.csv",
            ):
                export_csv_artifacts(
                    document,
                    [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                    working_copy=working_copy,
                )

    def test_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = self._working_copy(tmp_dir)
            outside_dir = Path(tmp_dir) / "outside"
            outside_dir.mkdir()
            link_dir = working_copy / "exports"
            self.create_symlink_or_skip(outside_dir, link_dir)

            with self.assertRaisesRegex(
                CsvArtifactExportError,
                r"^CSV output path escapes working copy \(id='Sheet'\): ",
            ):
                export_csv_artifacts(
                    _FakeDocument({"Sheet": _FakeSpreadsheet({"A1": "x"})}),
                    [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}],
                    working_copy=working_copy,
                )


if __name__ == "__main__":
    unittest.main()
