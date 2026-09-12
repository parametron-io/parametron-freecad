"""Unit tests for shared runtime parameter access helpers."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from unittest import mock


MODULE_NAME = "parametron_freecad.runtime.parameter_access"


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


class _LabelGuardObject:
    @property
    def Label(self):
        raise AssertionError("object.Label must not be accessed")


class _RaisingReadObject:
    def __getattr__(self, name):
        raise RuntimeError(f"cannot read {name}")


class _RejectingWriteObject:
    def __setattr__(self, name, value):
        raise RuntimeError(f"cannot write {name}")


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
            "ParameterAccessDocumentError",
            "ParameterAccessError",
            "ParameterAccessObjectNotFoundError",
            "ParameterAccessPropertyReadError",
            "ParameterAccessPropertyWriteError",
            "ResolvedParameterObject",
            "read_parameter_property",
            "resolve_parameter_object",
            "validate_parameter_access_document",
            "write_parameter_property",
        }

        self.assertEqual(set(module.__all__), expected)
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(hasattr(module, name))

    def test_error_hierarchy(self):
        module = _import_module()

        self.assertTrue(issubclass(module.ParameterAccessError, ValueError))
        self.assertTrue(
            issubclass(
                module.ParameterAccessDocumentError,
                module.ParameterAccessError,
            )
        )
        self.assertTrue(
            issubclass(
                module.ParameterAccessObjectNotFoundError,
                module.ParameterAccessError,
            )
        )
        self.assertTrue(
            issubclass(
                module.ParameterAccessPropertyReadError,
                module.ParameterAccessError,
            )
        )
        self.assertTrue(
            issubclass(
                module.ParameterAccessPropertyWriteError,
                module.ParameterAccessError,
            )
        )


class TestResolvedParameterObject(unittest.TestCase):
    def test_record_preserves_exact_object_name_and_handle(self):
        module = _import_module()
        obj = object()

        result = module.ResolvedParameterObject(object_name=" Box ", object=obj)

        self.assertEqual(result.object_name, " Box ")
        self.assertIs(result.object, obj)

    def test_record_is_frozen(self):
        module = _import_module()
        result = module.ResolvedParameterObject(object_name="Box", object=object())

        with self.assertRaises(Exception):
            result.object_name = "Other"  # type: ignore[misc]


class TestDocumentValidation(unittest.TestCase):
    def test_callable_get_object_succeeds(self):
        module = _import_module()

        module.validate_parameter_access_document(_StrictDocument())

    def test_missing_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.ParameterAccessDocumentError) as cm:
            module.validate_parameter_access_document(_NoGetObject())

        self.assertTrue(str(cm.exception))
        self.assertNotIn("Traceback", str(cm.exception))

    def test_non_callable_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.ParameterAccessDocumentError):
            module.validate_parameter_access_document(_NonCallableGetObject())


class TestObjectResolution(unittest.TestCase):
    def test_resolve_calls_get_object_once_with_exact_name(self):
        module = _import_module()
        obj = _LabelGuardObject()
        document = _StrictDocument({" Box ": obj})

        result = module.resolve_parameter_object(document, " Box ")

        self.assertEqual(document.calls, [" Box "])
        self.assertEqual(result.object_name, " Box ")
        self.assertIs(result.object, obj)

    def test_resolve_does_not_trim_normalize_lowercase_or_reinterpret_names(self):
        module = _import_module()
        exact = _LabelGuardObject()
        document = _StrictDocument({"Part.Name": exact, "part.name": object()})

        result = module.resolve_parameter_object(document, "Part.Name")

        self.assertEqual(document.calls, ["Part.Name"])
        self.assertIs(result.object, exact)

    def test_missing_object_raises_object_not_found_error_without_fallback(self):
        module = _import_module()
        document = _StrictDocument({"Display Label": _LabelGuardObject()})

        with self.assertRaises(module.ParameterAccessObjectNotFoundError) as cm:
            module.resolve_parameter_object(document, "ExactName")

        self.assertEqual(document.calls, ["ExactName"])
        self.assertTrue(str(cm.exception))

    def test_get_object_exception_raises_document_error_with_original_cause(self):
        module = _import_module()
        original = RuntimeError("document failure")
        document = _StrictDocument(exc=original)

        with self.assertRaises(module.ParameterAccessDocumentError) as cm:
            module.resolve_parameter_object(document, "Box")

        self.assertIs(cm.exception.__cause__, original)
        self.assertEqual(document.calls, ["Box"])

    def test_missing_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.ParameterAccessDocumentError):
            module.resolve_parameter_object(_NoGetObject(), "Box")

    def test_non_callable_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.ParameterAccessDocumentError):
            module.resolve_parameter_object(_NonCallableGetObject(), "Box")


class TestPropertyRead(unittest.TestCase):
    def test_reads_exact_attribute_name_and_returns_raw_value(self):
        module = _import_module()
        obj = types.SimpleNamespace()
        value = {"raw": object()}
        setattr(obj, " Length ", value)
        setattr(obj, "length", "wrong")
        before = dict(obj.__dict__)

        result = module.read_parameter_property(obj, " Length ", object_name="Box")

        self.assertIs(result, value)
        self.assertEqual(obj.__dict__, before)

    def test_missing_attribute_raises_read_error(self):
        module = _import_module()

        with self.assertRaises(module.ParameterAccessPropertyReadError) as cm:
            module.read_parameter_property(types.SimpleNamespace(), "Length")

        self.assertIsInstance(cm.exception.__cause__, AttributeError)

    def test_attribute_access_exception_raises_read_error_with_original_cause(self):
        module = _import_module()

        with self.assertRaises(module.ParameterAccessPropertyReadError) as cm:
            module.read_parameter_property(_RaisingReadObject(), "Length")

        self.assertIsInstance(cm.exception.__cause__, RuntimeError)


class TestPropertyWrite(unittest.TestCase):
    def test_writes_exact_attribute_name_and_raw_value(self):
        module = _import_module()
        obj = types.SimpleNamespace()
        value = {"valueKind": "uninterpreted", "payload": object()}

        module.write_parameter_property(obj, " Length ", value, object_name="Box")

        self.assertIs(getattr(obj, " Length "), value)
        self.assertNotIn("length", obj.__dict__)

    def test_write_does_not_reinterpret_value_types(self):
        module = _import_module()
        values = (True, 7, 3.5, "text", None, ["unchanged"])

        for index, value in enumerate(values):
            with self.subTest(value=value):
                obj = types.SimpleNamespace()
                module.write_parameter_property(obj, f"Prop{index}", value)
                self.assertIs(getattr(obj, f"Prop{index}"), value)

    def test_setattr_failure_raises_write_error_with_original_cause(self):
        module = _import_module()

        with self.assertRaises(module.ParameterAccessPropertyWriteError) as cm:
            module.write_parameter_property(
                _RejectingWriteObject(),
                "Length",
                10,
            )

        self.assertIsInstance(cm.exception.__cause__, RuntimeError)


if __name__ == "__main__":
    unittest.main()
