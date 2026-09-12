from __future__ import annotations

import builtins
import importlib
import sys
import unittest
from unittest import mock

from parametron_freecad.execution.document_save import (
    DocumentSaveError,
    save_document,
)


class _FakeDocument:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.save_calls = 0

    def save(self) -> None:
        self.save_calls += 1
        if self.error is not None:
            raise self.error

    def recompute(self) -> None:
        raise AssertionError("save helper must not recompute")

    def saveAs(self, path: str) -> None:
        del path
        raise AssertionError("save helper must not choose another path")


class DocumentSaveTests(unittest.TestCase):
    def test_module_import_does_not_require_freecad_or_export_modules(self) -> None:
        module_name = "parametron_freecad.execution.document_save"
        guarded_names = {"FreeCAD", "Import", "TechDrawGui"}
        original_import = builtins.__import__
        previous = sys.modules.pop(module_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(module_name, previous)
            if previous is not None
            else sys.modules.pop(module_name, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name.split(".", maxsplit=1)[0] in guarded_names:
                raise AssertionError(f"{name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module(module_name)

        self.assertTrue(callable(module.save_document))

    def test_save_document_calls_save_exactly_once_and_returns_none(self) -> None:
        document = _FakeDocument()

        result = save_document(document)

        self.assertIsNone(result)
        self.assertEqual(document.save_calls, 1)

    def test_missing_and_non_callable_save_raise_deterministic_error(self) -> None:
        class NonCallableSaveDocument:
            save = "not callable"

        for document in (object(), NonCallableSaveDocument()):
            with self.subTest(document=type(document).__name__), self.assertRaises(
                DocumentSaveError
            ) as caught:
                save_document(document)

            self.assertEqual(
                str(caught.exception),
                "document does not provide a callable save method",
            )

    def test_save_exception_is_wrapped_and_preserves_original_cause(self) -> None:
        original = RuntimeError("native persistence failed")
        document = _FakeDocument(original)

        with self.assertRaises(DocumentSaveError) as caught:
            save_document(document)

        self.assertEqual(document.save_calls, 1)
        self.assertEqual(
            str(caught.exception),
            "document save raised an exception: native persistence failed",
        )
        self.assertIs(caught.exception.__cause__, original)


if __name__ == "__main__":
    unittest.main()
