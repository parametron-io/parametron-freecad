"""Unit tests for shared runtime reference access helpers."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from unittest import mock


MODULE_NAME = "parametron_freecad.runtime.reference_access"


def _import_module():
    return importlib.import_module(MODULE_NAME)


class _StrictDocument:
    def __init__(self, objects=None, exc=None):
        self._objects = dict(objects or {})
        self._exc = exc
        self.calls = []

    @property
    def Objects(self):
        raise AssertionError("document.Objects must not be accessed")

    @property
    def Label(self):
        raise AssertionError("document Label lookup must not be used")

    def getObject(self, name):
        self.calls.append(name)
        if self._exc is not None:
            raise self._exc
        return self._objects.get(name)


class _LabelGuardReference:
    @property
    def Label(self):
        raise AssertionError("reference.Label must not be accessed")


class _NoGetObject:
    pass


class _NonCallableGetObject:
    getObject = "not callable"


class TestImportSafety(unittest.TestCase):
    def test_import_succeeds_without_freecad(self):
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad"}

        def guarded_import(name, *args, **kwargs):
            if name in guarded_names:
                raise AssertionError(f"{name} must not be imported")
            return real_import(name, *args, **kwargs)

        real_import = __import__
        previous = sys.modules.pop(MODULE_NAME, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_module()

        self.assertIsInstance(module, types.ModuleType)
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_public_api_surface_is_exported(self):
        module = _import_module()
        expected = {
            "ReferenceAccessDocumentError",
            "ReferenceAccessError",
            "ReferenceAccessReferenceNotFoundError",
            "ResolvedReferenceObject",
            "resolve_reference_object",
            "validate_reference_access_document",
        }

        self.assertEqual(set(module.__all__), expected)
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(hasattr(module, name))

    def test_error_hierarchy(self):
        module = _import_module()

        self.assertTrue(issubclass(module.ReferenceAccessError, ValueError))
        self.assertTrue(
            issubclass(
                module.ReferenceAccessDocumentError,
                module.ReferenceAccessError,
            )
        )
        self.assertTrue(
            issubclass(
                module.ReferenceAccessReferenceNotFoundError,
                module.ReferenceAccessError,
            )
        )


class TestResolvedReferenceObject(unittest.TestCase):
    def test_record_preserves_exact_reference_name_and_handle(self):
        module = _import_module()
        reference = object()

        result = module.ResolvedReferenceObject(
            reference_name=" Sketch001 ",
            reference=reference,
        )

        self.assertEqual(result.reference_name, " Sketch001 ")
        self.assertIs(result.reference, reference)

    def test_record_is_frozen(self):
        module = _import_module()
        result = module.ResolvedReferenceObject(
            reference_name="Sketch001",
            reference=object(),
        )

        with self.assertRaises(Exception):
            result.reference_name = "Other"  # type: ignore[misc]


class TestDocumentValidation(unittest.TestCase):
    def test_callable_get_object_succeeds(self):
        module = _import_module()

        module.validate_reference_access_document(_StrictDocument())

    def test_missing_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.ReferenceAccessDocumentError) as cm:
            module.validate_reference_access_document(_NoGetObject())

        self.assertTrue(str(cm.exception))
        self.assertNotIn("Traceback", str(cm.exception))

    def test_non_callable_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.ReferenceAccessDocumentError):
            module.validate_reference_access_document(_NonCallableGetObject())


class TestReferenceResolution(unittest.TestCase):
    def test_resolve_calls_get_object_once_with_exact_name(self):
        module = _import_module()
        reference = _LabelGuardReference()
        document = _StrictDocument({" Sketch001 ": reference})

        result = module.resolve_reference_object(document, " Sketch001 ")

        self.assertEqual(document.calls, [" Sketch001 "])
        self.assertEqual(result.reference_name, " Sketch001 ")
        self.assertIs(result.reference, reference)

    def test_returns_resolved_reference_object_type(self):
        module = _import_module()
        document = _StrictDocument({"Sketch001": _LabelGuardReference()})

        result = module.resolve_reference_object(document, "Sketch001")

        self.assertIsInstance(result, module.ResolvedReferenceObject)

    def test_resolve_does_not_normalize_names(self):
        module = _import_module()
        exact = _LabelGuardReference()
        document = _StrictDocument({"Part.Name": exact, "part.name": object()})

        result = module.resolve_reference_object(document, "Part.Name")

        self.assertEqual(document.calls, ["Part.Name"])
        self.assertIs(result.reference, exact)

    def test_resolve_preserves_unicode_and_dotted_and_spaced_names(self):
        module = _import_module()
        names = (
            " leading-and-trailing ",
            "CaseSensitiveName",
            "casesensitivename",
            "Bödy_Ünïcode_\u00e9",
            "App.Document.Sketch001",
        )

        for name in names:
            with self.subTest(name=name):
                reference = _LabelGuardReference()
                document = _StrictDocument({name: reference})

                result = module.resolve_reference_object(document, name)

                self.assertEqual(document.calls, [name])
                self.assertEqual(result.reference_name, name)
                self.assertIs(result.reference, reference)

    def test_missing_reference_raises_not_found_error_without_fallback(self):
        module = _import_module()
        document = _StrictDocument({"Display Label": _LabelGuardReference()})

        with self.assertRaises(module.ReferenceAccessReferenceNotFoundError) as cm:
            module.resolve_reference_object(document, "ExactName")

        self.assertEqual(document.calls, ["ExactName"])
        self.assertTrue(str(cm.exception))

    def test_get_object_exception_raises_document_error_with_original_cause(self):
        module = _import_module()
        original = RuntimeError("document failure")
        document = _StrictDocument(exc=original)

        with self.assertRaises(module.ReferenceAccessDocumentError) as cm:
            module.resolve_reference_object(document, "Sketch001")

        self.assertIs(cm.exception.__cause__, original)
        self.assertEqual(document.calls, ["Sketch001"])

    def test_missing_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.ReferenceAccessDocumentError):
            module.resolve_reference_object(_NoGetObject(), "Sketch001")

    def test_non_callable_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.ReferenceAccessDocumentError):
            module.resolve_reference_object(_NonCallableGetObject(), "Sketch001")


class TestNegativeBoundaries(unittest.TestCase):
    def test_only_get_object_is_called_on_document(self):
        module = _import_module()

        class StrictDocument:
            def __init__(self):
                self.calls = []

            def getObject(self, name):
                self.calls.append(("getObject", name))
                return _LabelGuardReference()

            def __getattr__(self, name):
                raise AssertionError(f"unexpected document attribute access: {name!r}")

        document = StrictDocument()

        module.resolve_reference_object(document, "Sketch001")

        self.assertEqual(document.calls, [("getObject", "Sketch001")])

    def test_resolution_does_not_inspect_reference_kind_or_attributes(self):
        module = _import_module()

        class GuardedReference:
            def __getattr__(self, name):
                raise AssertionError(f"reference attribute must not be read: {name!r}")

        reference = GuardedReference()
        document = _StrictDocument({"Sketch001": reference})

        result = module.resolve_reference_object(document, "Sketch001")

        self.assertIs(result.reference, reference)

    def test_resolution_does_not_mutate_document_state(self):
        module = _import_module()
        document = _StrictDocument({"Sketch001": _LabelGuardReference()})

        module.resolve_reference_object(document, "Sketch001")

        self.assertEqual(document.calls, ["Sketch001"])
        self.assertEqual(set(document._objects), {"Sketch001"})

    def test_resolution_does_not_write_files(self):
        module = _import_module()
        document = _StrictDocument({"Sketch001": _LabelGuardReference()})

        with mock.patch("builtins.open", side_effect=AssertionError("must not open files")):
            module.resolve_reference_object(document, "Sketch001")


if __name__ == "__main__":
    unittest.main()
