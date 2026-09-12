from __future__ import annotations

import builtins
import importlib
import sys
import unittest
from unittest import mock

from parametron_freecad.execution.document_recompute import (
    DocumentRecomputeError,
    recompute_document,
)


class _FakeDocument:
    def __init__(self) -> None:
        self.recompute_calls = 0
        self.save_calls = 0
        self.save_as_calls = 0

    def recompute(self) -> None:
        self.recompute_calls += 1

    def save(self) -> None:
        self.save_calls += 1

    def saveAs(self, path: str) -> None:
        del path
        self.save_as_calls += 1


class DocumentRecomputeTests(unittest.TestCase):
    def test_module_imports_without_freecad_dependency(self) -> None:
        module_name = "parametron_freecad.execution.document_recompute"
        original_module = sys.modules.pop(module_name, None)
        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "FreeCAD":
                raise AssertionError("document_recompute must not import FreeCAD")
            return original_import(name, globals, locals, fromlist, level)

        try:
            with mock.patch("builtins.__import__", side_effect=guarded_import):
                module = importlib.import_module(module_name)
        finally:
            sys.modules.pop(module_name, None)
            if original_module is not None:
                sys.modules[module_name] = original_module

        self.assertTrue(callable(module.recompute_document))
        self.assertEqual(module.recompute_document.__name__, "recompute_document")
        self.assertTrue(issubclass(module.DocumentRecomputeError, ValueError))
        self.assertEqual(module.DocumentRecomputeError.__name__, "DocumentRecomputeError")

    def test_recompute_document_calls_recompute_exactly_once_and_returns_none(self) -> None:
        document = _FakeDocument()

        result = recompute_document(document)

        self.assertIsNone(result)
        self.assertEqual(document.recompute_calls, 1)
        self.assertEqual(document.save_calls, 0)
        self.assertEqual(document.save_as_calls, 0)

    def test_recompute_document_missing_recompute_raises_deterministic_error(self) -> None:
        with self.assertRaises(DocumentRecomputeError) as ctx:
            recompute_document(object())

        self.assertEqual(
            str(ctx.exception),
            "document does not provide a callable recompute method",
        )

    def test_recompute_document_non_callable_recompute_raises_deterministic_error(self) -> None:
        class NonCallableRecomputeDocument:
            recompute = "not callable"

        with self.assertRaises(DocumentRecomputeError) as ctx:
            recompute_document(NonCallableRecomputeDocument())

        self.assertEqual(
            str(ctx.exception),
            "document does not provide a callable recompute method",
        )

    def test_recompute_document_converts_recompute_exception_to_deterministic_error(self) -> None:
        class ExplodingDocument(_FakeDocument):
            def recompute(self) -> None:
                self.recompute_calls += 1
                raise RuntimeError("boom")

        document = ExplodingDocument()

        with self.assertRaises(DocumentRecomputeError) as ctx:
            recompute_document(document)

        self.assertEqual(document.recompute_calls, 1)
        self.assertEqual(
            str(ctx.exception),
            "document recompute raised an exception: boom",
        )
        self.assertEqual(document.save_calls, 0)
        self.assertEqual(document.save_as_calls, 0)

    def test_recompute_document_does_not_call_save_apis_when_present(self) -> None:
        class SaveGuardDocument(_FakeDocument):
            def save(self) -> None:
                raise AssertionError("save must not be called during recompute")

            def saveAs(self, path: str) -> None:
                del path
                raise AssertionError("saveAs must not be called during recompute")

        document = SaveGuardDocument()

        recompute_document(document)

        self.assertEqual(document.recompute_calls, 1)
