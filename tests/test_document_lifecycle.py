from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class ImportSafetyTests(unittest.TestCase):
    def test_import_does_not_require_freecad(self) -> None:
        original_import = __import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "FreeCAD":
                raise AssertionError("FreeCAD should not be imported")
            return original_import(name, globals, locals, fromlist, level)

        module_name = "parametron_freecad.runtime.document_lifecycle"
        sys.modules.pop(module_name, None)
        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module(module_name)

        self.assertIsNotNone(module)

    def test_freecad_not_in_sys_modules_after_import(self) -> None:
        sys.modules.pop("parametron_freecad.runtime.document_lifecycle", None)
        import parametron_freecad.runtime.document_lifecycle  # noqa: F401

        self.assertNotIn("FreeCAD", sys.modules)

    def test_public_api_is_complete(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (  # noqa: F401
            DocumentCloseError,
            DocumentLifecycleError,
            DocumentOpenError,
            OpenedDocument,
            SourceDocumentPathError,
            close_freecad_document,
            open_freecad_document,
            opened_freecad_document,
            resolve_source_document_path,
        )


class OpenedDocumentTests(unittest.TestCase):
    def _make_fake_doc(self, name: str = "TestDoc") -> object:
        doc = mock.Mock()
        doc.Name = name
        return doc

    def test_stores_path_document_and_name(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import OpenedDocument

        path = Path("/tmp/model.FCStd")
        doc = self._make_fake_doc("MyDoc")

        opened = OpenedDocument(path=path, document=doc, document_name="MyDoc")

        self.assertEqual(opened.path, path)
        self.assertIs(opened.document, doc)
        self.assertEqual(opened.document_name, "MyDoc")

    def test_is_immutable(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import OpenedDocument

        opened = OpenedDocument(
            path=Path("/tmp/model.FCStd"),
            document=object(),
            document_name="MyDoc",
        )

        with self.assertRaises((AttributeError, TypeError)):
            opened.path = Path("/tmp/other.FCStd")  # type: ignore[misc]

    def test_document_name_is_string(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import OpenedDocument

        opened = OpenedDocument(
            path=Path("/tmp/model.FCStd"),
            document=object(),
            document_name="StableDoc",
        )

        self.assertIsInstance(opened.document_name, str)


class ResolveSourceDocumentPathTests(unittest.TestCase):
    def create_symlink_or_skip(self, target: Path, link_path: Path) -> None:
        try:
            link_path.symlink_to(target)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is unavailable on this platform")

    def test_relative_path_resolves_inside_working_copy(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            resolve_source_document_path,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            model = working_copy / "model.FCStd"
            model.write_text("fake", encoding="utf-8")

            result = resolve_source_document_path(working_copy, "model.FCStd")

            self.assertEqual(result, model.resolve())
            self.assertTrue(result.is_absolute())

    def test_nested_relative_path_resolves_inside_working_copy(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            resolve_source_document_path,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            nested = working_copy / "models" / "parts"
            nested.mkdir(parents=True)
            model = nested / "assembly.FCStd"
            model.write_text("fake", encoding="utf-8")

            result = resolve_source_document_path(working_copy, "models/parts/assembly.FCStd")

            self.assertEqual(result, model.resolve())

    def test_returned_path_is_absolute(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            resolve_source_document_path,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            model = working_copy / "model.FCStd"
            model.write_text("fake", encoding="utf-8")

            result = resolve_source_document_path(working_copy, "model.FCStd")

            self.assertTrue(result.is_absolute())

    def test_absolute_path_inside_working_copy_is_accepted(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            resolve_source_document_path,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            model = working_copy / "model.FCStd"
            model.write_text("fake", encoding="utf-8")

            result = resolve_source_document_path(working_copy, str(model))

            self.assertEqual(result, model.resolve())

    def test_traversal_outside_working_copy_is_rejected(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            SourceDocumentPathError,
            resolve_source_document_path,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working_copy = root / "project"
            working_copy.mkdir()
            outside = root / "outside.FCStd"
            outside.write_text("fake", encoding="utf-8")

            with self.assertRaises(SourceDocumentPathError):
                resolve_source_document_path(working_copy, "../outside.FCStd")

    def test_absolute_path_outside_working_copy_is_rejected(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            SourceDocumentPathError,
            resolve_source_document_path,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working_copy = root / "project"
            working_copy.mkdir()
            outside = root / "outside.FCStd"
            outside.write_text("fake", encoding="utf-8")

            with self.assertRaises(SourceDocumentPathError):
                resolve_source_document_path(working_copy, str(outside))

    def test_symlink_escaping_working_copy_is_rejected(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            SourceDocumentPathError,
            resolve_source_document_path,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working_copy = root / "project"
            working_copy.mkdir()
            outside = root / "outside.FCStd"
            outside.write_text("fake", encoding="utf-8")
            link = working_copy / "link.FCStd"
            self.create_symlink_or_skip(Path("..") / "outside.FCStd", link)

            with self.assertRaises(SourceDocumentPathError):
                resolve_source_document_path(working_copy, "link.FCStd")

    def test_missing_source_document_is_rejected(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            SourceDocumentPathError,
            resolve_source_document_path,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)

            with self.assertRaises(SourceDocumentPathError):
                resolve_source_document_path(working_copy, "nonexistent.FCStd")

    def test_directory_source_document_is_rejected(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            SourceDocumentPathError,
            resolve_source_document_path,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            subdir = working_copy / "subdir"
            subdir.mkdir()

            with self.assertRaises(SourceDocumentPathError):
                resolve_source_document_path(working_copy, "subdir")

    def test_error_is_subclass_of_document_lifecycle_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentLifecycleError,
            SourceDocumentPathError,
        )

        self.assertTrue(issubclass(SourceDocumentPathError, DocumentLifecycleError))
        self.assertTrue(issubclass(DocumentLifecycleError, ValueError))


class _FakeDocument:
    def __init__(self, name: str = "TestDoc") -> None:
        self.Name = name


class _FakeFreeCAD:
    def __init__(self, doc_name: str = "TestDoc") -> None:
        self._doc_name = doc_name
        self.open_calls: list[str] = []
        self.close_calls: list[str] = []

    def openDocument(self, path: str) -> _FakeDocument:
        self.open_calls.append(path)
        return _FakeDocument(self._doc_name)

    def closeDocument(self, name: str) -> None:
        self.close_calls.append(name)


class OpenFreeCADDocumentTests(unittest.TestCase):
    def _make_temp_file(self, tmp_dir: str, name: str = "model.FCStd") -> Path:
        path = Path(tmp_dir) / name
        path.write_text("fake", encoding="utf-8")
        return path

    def test_calls_open_document_exactly_once(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import open_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            fake = _FakeFreeCAD()

            open_freecad_document(fake, path)

            self.assertEqual(len(fake.open_calls), 1)

    def test_passes_str_resolved_path_to_open_document(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import open_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            fake = _FakeFreeCAD()

            open_freecad_document(fake, path)

            self.assertEqual(fake.open_calls[0], str(path.resolve()))

    def test_returned_opened_document_path_equals_resolved_source_path(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import open_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            fake = _FakeFreeCAD()

            result = open_freecad_document(fake, path)

            self.assertEqual(result.path, path.resolve())

    def test_returned_opened_document_is_fake_document(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import open_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            fake = _FakeFreeCAD("MyDoc")

            result = open_freecad_document(fake, path)

            self.assertIsInstance(result.document, _FakeDocument)

    def test_returned_document_name_equals_fake_document_name(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import open_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            fake = _FakeFreeCAD("MyDoc")

            result = open_freecad_document(fake, path)

            self.assertEqual(result.document_name, "MyDoc")

    def test_missing_open_document_attribute_raises_document_open_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentOpenError,
            open_freecad_document,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)

            class NoOpenDocument:
                pass

            with self.assertRaises(DocumentOpenError):
                open_freecad_document(NoOpenDocument(), path)

    def test_non_callable_open_document_raises_document_open_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentOpenError,
            open_freecad_document,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)

            class NonCallableOpenDocument:
                openDocument = "not_callable"

            with self.assertRaises(DocumentOpenError):
                open_freecad_document(NonCallableOpenDocument(), path)

    def test_open_document_raising_exception_converts_to_document_open_error(
        self,
    ) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentOpenError,
            open_freecad_document,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)

            class FailingFreeCAD:
                def openDocument(self, path: str) -> None:
                    raise RuntimeError("FreeCAD internal error")

            with self.assertRaises(DocumentOpenError):
                open_freecad_document(FailingFreeCAD(), path)

    def test_original_exception_is_chained_to_document_open_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentOpenError,
            open_freecad_document,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            original = RuntimeError("original cause")

            class FailingFreeCAD:
                def openDocument(self, p: str) -> None:
                    raise original

            try:
                open_freecad_document(FailingFreeCAD(), path)
                self.fail("expected DocumentOpenError")
            except DocumentOpenError as exc:
                self.assertIs(exc.__cause__, original)

    def test_document_without_name_attribute_raises_document_open_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentOpenError,
            open_freecad_document,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)

            class NoNameDoc:
                pass

            class FreeCADNoName:
                def openDocument(self, p: str) -> NoNameDoc:
                    return NoNameDoc()

            with self.assertRaises(DocumentOpenError):
                open_freecad_document(FreeCADNoName(), path)

    def test_document_with_empty_name_raises_document_open_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentOpenError,
            open_freecad_document,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)

            class FreeCADEmptyName:
                def openDocument(self, p: str) -> _FakeDocument:
                    return _FakeDocument("")

            with self.assertRaises(DocumentOpenError):
                open_freecad_document(FreeCADEmptyName(), path)

    def test_document_with_non_string_name_raises_document_open_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentOpenError,
            open_freecad_document,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)

            class IntNameDoc:
                Name = 42

            class FreeCADIntName:
                def openDocument(self, p: str) -> IntNameDoc:
                    return IntNameDoc()

            with self.assertRaises(DocumentOpenError):
                open_freecad_document(FreeCADIntName(), path)

    def test_document_open_error_is_subclass_of_document_lifecycle_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentLifecycleError,
            DocumentOpenError,
        )

        self.assertTrue(issubclass(DocumentOpenError, DocumentLifecycleError))


class CloseFreeCADDocumentTests(unittest.TestCase):
    def _make_opened(self, name: str = "TestDoc") -> object:
        from parametron_freecad.runtime.document_lifecycle import OpenedDocument

        return OpenedDocument(
            path=Path("/tmp/model.FCStd"),
            document=_FakeDocument(name),
            document_name=name,
        )

    def test_calls_close_document_exactly_once(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import close_freecad_document

        fake = _FakeFreeCAD()
        opened = self._make_opened("TestDoc")

        close_freecad_document(fake, opened)

        self.assertEqual(len(fake.close_calls), 1)

    def test_passes_document_name_to_close_document(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import close_freecad_document

        fake = _FakeFreeCAD()
        opened = self._make_opened("MyDoc")

        close_freecad_document(fake, opened)

        self.assertEqual(fake.close_calls[0], "MyDoc")

    def test_does_not_call_open_document(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import close_freecad_document

        fake = _FakeFreeCAD()
        opened = self._make_opened()

        close_freecad_document(fake, opened)

        self.assertEqual(fake.open_calls, [])

    def test_missing_close_document_attribute_raises_document_close_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentCloseError,
            close_freecad_document,
        )

        class NoCloseDocument:
            pass

        opened = self._make_opened()

        with self.assertRaises(DocumentCloseError):
            close_freecad_document(NoCloseDocument(), opened)

    def test_non_callable_close_document_raises_document_close_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentCloseError,
            close_freecad_document,
        )

        class NonCallableClose:
            closeDocument = "not_callable"

        opened = self._make_opened()

        with self.assertRaises(DocumentCloseError):
            close_freecad_document(NonCallableClose(), opened)

    def test_close_document_raising_exception_converts_to_document_close_error(
        self,
    ) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentCloseError,
            close_freecad_document,
        )

        class FailingClose:
            def closeDocument(self, name: str) -> None:
                raise RuntimeError("FreeCAD close error")

        opened = self._make_opened()

        with self.assertRaises(DocumentCloseError):
            close_freecad_document(FailingClose(), opened)

    def test_original_exception_is_chained_to_document_close_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentCloseError,
            close_freecad_document,
        )

        original = RuntimeError("original close cause")

        class FailingClose:
            def closeDocument(self, name: str) -> None:
                raise original

        opened = self._make_opened()

        try:
            close_freecad_document(FailingClose(), opened)
            self.fail("expected DocumentCloseError")
        except DocumentCloseError as exc:
            self.assertIs(exc.__cause__, original)

    def test_document_close_error_is_subclass_of_document_lifecycle_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentCloseError,
            DocumentLifecycleError,
        )

        self.assertTrue(issubclass(DocumentCloseError, DocumentLifecycleError))


class OpenedFreeCADDocumentContextManagerTests(unittest.TestCase):
    def _make_temp_file(self, tmp_dir: str, name: str = "model.FCStd") -> Path:
        path = Path(tmp_dir) / name
        path.write_text("fake", encoding="utf-8")
        return path

    def test_yields_opened_document(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            OpenedDocument,
            opened_freecad_document,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            fake = _FakeFreeCAD("TestDoc")

            with opened_freecad_document(fake, path) as doc:
                self.assertIsInstance(doc, OpenedDocument)

    def test_opens_document_before_yield(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import opened_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            fake = _FakeFreeCAD()

            with opened_freecad_document(fake, path):
                self.assertEqual(len(fake.open_calls), 1)

    def test_closes_document_after_normal_exit(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import opened_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            fake = _FakeFreeCAD()

            with opened_freecad_document(fake, path):
                pass

            self.assertEqual(len(fake.close_calls), 1)

    def test_closes_with_correct_document_name(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import opened_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            fake = _FakeFreeCAD("NamedDoc")

            with opened_freecad_document(fake, path):
                pass

            self.assertEqual(fake.close_calls[0], "NamedDoc")

    def test_closes_document_after_exception_inside_block(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import opened_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            fake = _FakeFreeCAD()

            with self.assertRaises(ValueError):
                with opened_freecad_document(fake, path):
                    raise ValueError("block error")

            self.assertEqual(len(fake.close_calls), 1)

    def test_propagates_original_exception_from_block(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import opened_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)
            fake = _FakeFreeCAD()
            original = ValueError("block error")

            try:
                with opened_freecad_document(fake, path):
                    raise original
                self.fail("expected ValueError")
            except ValueError as exc:
                self.assertIs(exc, original)

    def test_open_failure_does_not_call_close(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentOpenError,
            opened_freecad_document,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)

            class FailingOpen:
                close_calls: list[str] = []

                def openDocument(self, p: str) -> None:
                    raise RuntimeError("open failed")

                def closeDocument(self, name: str) -> None:
                    self.close_calls.append(name)

            failing = FailingOpen()

            with self.assertRaises(DocumentOpenError):
                with opened_freecad_document(failing, path):
                    pass

            self.assertEqual(failing.close_calls, [])

    def test_close_failure_on_normal_exit_raises_document_close_error(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            DocumentCloseError,
            opened_freecad_document,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._make_temp_file(tmp_dir)

            class FailingClose:
                def openDocument(self, p: str) -> _FakeDocument:
                    return _FakeDocument("TestDoc")

                def closeDocument(self, name: str) -> None:
                    raise RuntimeError("close failed")

            with self.assertRaises(DocumentCloseError):
                with opened_freecad_document(FailingClose(), path):
                    pass


class NoSideEffectsTests(unittest.TestCase):
    def test_lifecycle_operations_do_not_create_result_json(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import opened_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "model.FCStd"
            path.write_text("fake", encoding="utf-8")
            fake = _FakeFreeCAD()

            with opened_freecad_document(fake, path):
                pass

            self.assertFalse((Path(tmp_dir) / "result.json").exists())

    def test_lifecycle_operations_do_not_create_step_files(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import opened_freecad_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "model.FCStd"
            path.write_text("fake", encoding="utf-8")
            fake = _FakeFreeCAD()

            with opened_freecad_document(fake, path):
                pass

            step_files = list(Path(tmp_dir).glob("**/*.step")) + list(
                Path(tmp_dir).glob("**/*.STEP")
            )
            self.assertEqual(step_files, [])

    def test_resolve_does_not_create_files_in_working_copy(self) -> None:
        from parametron_freecad.runtime.document_lifecycle import (
            resolve_source_document_path,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            model = working_copy / "model.FCStd"
            model.write_text("fake", encoding="utf-8")
            files_before = set(working_copy.iterdir())

            resolve_source_document_path(working_copy, "model.FCStd")

            files_after = set(working_copy.iterdir())
            self.assertEqual(files_before, files_after)


if __name__ == "__main__":
    unittest.main()
