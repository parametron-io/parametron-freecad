"""Unit tests for shared runtime metadata access helpers."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from unittest import mock


MODULE_NAME = "parametron_freecad.runtime.metadata_access"


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


class _LabelGuardOwner:
    @property
    def Label(self):
        raise AssertionError("owner.Label must not be accessed")


class _RaisingReadOwner:
    def __getattr__(self, name):
        raise RuntimeError(f"cannot read {name}")


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
            "MetadataAccessDocumentError",
            "MetadataAccessError",
            "MetadataAccessOwnerNotFoundError",
            "MetadataAccessPropertyReadError",
            "ResolvedMetadataOwner",
            "read_metadata_value",
            "resolve_metadata_owner",
            "validate_metadata_access_document",
        }

        self.assertEqual(set(module.__all__), expected)
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(hasattr(module, name))

    def test_error_hierarchy(self):
        module = _import_module()

        self.assertTrue(issubclass(module.MetadataAccessError, ValueError))
        self.assertTrue(
            issubclass(
                module.MetadataAccessDocumentError,
                module.MetadataAccessError,
            )
        )
        self.assertTrue(
            issubclass(
                module.MetadataAccessOwnerNotFoundError,
                module.MetadataAccessError,
            )
        )
        self.assertTrue(
            issubclass(
                module.MetadataAccessPropertyReadError,
                module.MetadataAccessError,
            )
        )


class TestResolvedMetadataOwner(unittest.TestCase):
    def test_record_preserves_exact_owner_id_and_handle(self):
        module = _import_module()
        owner = object()

        result = module.ResolvedMetadataOwner(owner_id=" Part 001 ", owner=owner)

        self.assertEqual(result.owner_id, " Part 001 ")
        self.assertIs(result.owner, owner)

    def test_record_is_frozen(self):
        module = _import_module()
        result = module.ResolvedMetadataOwner(owner_id="Part001", owner=object())

        with self.assertRaises(Exception):
            result.owner_id = "Other"  # type: ignore[misc]


class TestDocumentValidation(unittest.TestCase):
    def test_callable_get_object_succeeds(self):
        module = _import_module()

        module.validate_metadata_access_document(_StrictDocument())

    def test_missing_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.MetadataAccessDocumentError) as cm:
            module.validate_metadata_access_document(_NoGetObject())

        self.assertTrue(str(cm.exception))
        self.assertNotIn("Traceback", str(cm.exception))

    def test_non_callable_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.MetadataAccessDocumentError):
            module.validate_metadata_access_document(_NonCallableGetObject())


class TestOwnerResolution(unittest.TestCase):
    def test_resolve_calls_get_object_once_with_exact_owner_id(self):
        module = _import_module()
        owner = _LabelGuardOwner()
        document = _StrictDocument({" Part 001 ": owner})

        result = module.resolve_metadata_owner(document, " Part 001 ")

        self.assertEqual(document.calls, [" Part 001 "])
        self.assertEqual(result.owner_id, " Part 001 ")
        self.assertIs(result.owner, owner)

    def test_resolve_does_not_trim_normalize_lowercase_or_reinterpret_owner_ids(self):
        module = _import_module()
        exact = _LabelGuardOwner()
        document = _StrictDocument({"Part.Owner": exact, "part.owner": object()})

        result = module.resolve_metadata_owner(document, "Part.Owner")

        self.assertEqual(document.calls, ["Part.Owner"])
        self.assertIs(result.owner, exact)

    def test_missing_owner_raises_owner_not_found_error_without_fallback(self):
        module = _import_module()
        document = _StrictDocument({"Display Label": _LabelGuardOwner()})

        with self.assertRaises(module.MetadataAccessOwnerNotFoundError) as cm:
            module.resolve_metadata_owner(document, "ExactOwnerId")

        self.assertEqual(document.calls, ["ExactOwnerId"])
        self.assertTrue(str(cm.exception))

    def test_get_object_exception_raises_document_error_with_original_cause(self):
        module = _import_module()
        original = RuntimeError("document failure")
        document = _StrictDocument(exc=original)

        with self.assertRaises(module.MetadataAccessDocumentError) as cm:
            module.resolve_metadata_owner(document, "Part001")

        self.assertIs(cm.exception.__cause__, original)
        self.assertEqual(document.calls, ["Part001"])

    def test_missing_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.MetadataAccessDocumentError):
            module.resolve_metadata_owner(_NoGetObject(), "Part001")

    def test_non_callable_get_object_raises_document_error(self):
        module = _import_module()

        with self.assertRaises(module.MetadataAccessDocumentError):
            module.resolve_metadata_owner(_NonCallableGetObject(), "Part001")


class TestMetadataValueRead(unittest.TestCase):
    def test_reads_exact_key_and_returns_raw_value(self):
        module = _import_module()
        owner = types.SimpleNamespace()
        value = {"raw": object()}
        setattr(owner, " Title ", value)
        setattr(owner, "title", "wrong")
        before = dict(owner.__dict__)

        result = module.read_metadata_value(owner, " Title ", owner_id="Part001")

        self.assertIs(result, value)
        self.assertEqual(owner.__dict__, before)

    def test_returns_raw_values_unchanged_for_all_kinds(self):
        module = _import_module()
        values = (
            True,
            7,
            3.5,
            "text",
            None,
            ["unchanged"],
            {"k": "v"},
            object(),
        )

        for index, value in enumerate(values):
            with self.subTest(value=repr(value)):
                owner = types.SimpleNamespace()
                setattr(owner, f"Key{index}", value)
                result = module.read_metadata_value(owner, f"Key{index}")
                self.assertIs(result, value)

    def test_missing_attribute_raises_property_read_error(self):
        module = _import_module()

        with self.assertRaises(module.MetadataAccessPropertyReadError) as cm:
            module.read_metadata_value(types.SimpleNamespace(), "Title")

        self.assertIsInstance(cm.exception.__cause__, AttributeError)

    def test_attribute_access_exception_raises_read_error_with_original_cause(self):
        module = _import_module()

        with self.assertRaises(module.MetadataAccessPropertyReadError) as cm:
            module.read_metadata_value(_RaisingReadOwner(), "Title")

        self.assertIsInstance(cm.exception.__cause__, RuntimeError)

    def test_read_does_not_trim_or_normalize_key(self):
        module = _import_module()
        owner = types.SimpleNamespace()
        setattr(owner, "Material", "steel")

        with self.assertRaises(module.MetadataAccessPropertyReadError):
            module.read_metadata_value(owner, "material")

        with self.assertRaises(module.MetadataAccessPropertyReadError):
            module.read_metadata_value(owner, " Material ")


if __name__ == "__main__":
    unittest.main()
