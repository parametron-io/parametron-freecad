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


def _native_type_for_value(value):
    if type(value) is bool:
        return "App::PropertyBool"
    if type(value) is int:
        return "App::PropertyInteger"
    if type(value) is float:
        return "App::PropertyFloat"
    return "App::PropertyString"


class _NativeOwner:
    def __init__(self, values=None, *, native_types=None, type_error=None):
        self.values = dict(values or {})
        self.native_types = dict(native_types or {})
        self.type_error = type_error

    @property
    def PropertiesList(self):
        return tuple(self.values)

    def getTypeIdOfProperty(self, name):
        if self.type_error is not None:
            raise self.type_error
        return self.native_types.get(
            name,
            _native_type_for_value(self.values.get(name)),
        )

    def __getattr__(self, name):
        try:
            return self.values[name]
        except KeyError:
            raise AttributeError(name)


class _NoTypeInspectorOwner:
    PropertiesList = ("Title",)

    def __getattr__(self, name):
        if name == "Title":
            return "x"
        raise AttributeError(name)


class _NonPropertyOwner:
    PropertiesList = ()

    def getTypeIdOfProperty(self, name):
        raise AssertionError("non-property attributes must not be type-inspected")

    def __getattr__(self, name):
        if name == "Name":
            return "Body"
        raise AttributeError(name)


class _RaisingReadOwner:
    PropertiesList = ("Title",)

    def __init__(self, error):
        self.error = error
        self.values = {}

    def getTypeIdOfProperty(self, name):
        return "App::PropertyString"

    def __getattr__(self, name):
        raise self.error


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
            "METADATA_NATIVE_VALUE_KINDS",
            "MetadataAccessDocumentError",
            "MetadataAccessError",
            "MetadataAccessOwnerNotFoundError",
            "MetadataAccessPropertyInspectionError",
            "MetadataAccessPropertyNotFoundError",
            "MetadataAccessPropertyReadError",
            "ResolvedMetadataOwner",
            "ResolvedMetadataProperty",
            "UnsupportedMetadataPropertyTypeError",
            "metadata_value_kind_for_native_type",
            "read_metadata_property",
            "read_metadata_value",
            "require_metadata_property",
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
                module.MetadataAccessPropertyNotFoundError,
                module.MetadataAccessError,
            )
        )
        self.assertTrue(
            issubclass(
                module.MetadataAccessPropertyInspectionError,
                module.MetadataAccessError,
            )
        )
        self.assertTrue(
            issubclass(
                module.MetadataAccessPropertyReadError,
                module.MetadataAccessError,
            )
        )
        self.assertTrue(
            issubclass(
                module.UnsupportedMetadataPropertyTypeError,
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
        value = {"raw": object()}
        owner = _NativeOwner({"Title": value, "title": "wrong"})

        result = module.read_metadata_value(owner, "Title", owner_id="Part001")

        self.assertIs(result, value)
        self.assertEqual(owner.values, {"Title": value, "title": "wrong"})

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
                key = f"Key{index}"
                owner = _NativeOwner({key: value})
                result = module.read_metadata_value(owner, key)
                self.assertIs(result, value)

    def test_missing_property_raises_not_found_error(self):
        module = _import_module()

        with self.assertRaises(module.MetadataAccessPropertyNotFoundError):
            module.read_metadata_value(_NativeOwner(), "Title")

    def test_whitespace_key_is_not_an_exact_property(self):
        module = _import_module()
        owner = _NativeOwner({" Title ": "x", "Title": "exact"})

        with self.assertRaises(module.MetadataAccessPropertyNotFoundError):
            module.read_metadata_value(owner, " Title ", owner_id="Part001")
        with self.assertRaises(module.MetadataAccessPropertyNotFoundError):
            module.read_metadata_value(owner, " Title", owner_id="Part001")

    def test_non_property_attribute_is_rejected(self):
        module = _import_module()

        with self.assertRaises(module.MetadataAccessPropertyNotFoundError):
            module.read_metadata_value(_NonPropertyOwner(), "Name")

    def test_property_presence_inspection_failure_raises_inspection_error(self):
        module = _import_module()

        with self.assertRaises(module.MetadataAccessPropertyInspectionError):
            module.read_metadata_value(object(), "Title")

    def test_property_type_inspection_failure_raises_inspection_error(self):
        module = _import_module()

        with self.assertRaises(module.MetadataAccessPropertyInspectionError):
            module.read_metadata_value(_NoTypeInspectorOwner(), "Title")

    def test_property_type_inspection_exception_preserves_cause(self):
        module = _import_module()
        original = RuntimeError("type failure")
        owner = _NativeOwner({"Title": "x"}, type_error=original)

        with self.assertRaises(
            module.MetadataAccessPropertyInspectionError
        ) as cm:
            module.read_metadata_value(owner, "Title")

        self.assertIs(cm.exception.__cause__, original)

    def test_property_read_exception_preserves_cause(self):
        module = _import_module()
        original = RuntimeError("read failure")
        owner = _RaisingReadOwner(original)

        with self.assertRaises(module.MetadataAccessPropertyReadError) as cm:
            module.read_metadata_value(owner, "Title")

        self.assertIs(cm.exception.__cause__, original)

    def test_read_does_not_trim_or_normalize_key(self):
        module = _import_module()
        owner = _NativeOwner({"Material": "steel"})

        with self.assertRaises(module.MetadataAccessPropertyNotFoundError):
            module.read_metadata_value(owner, "material")

        with self.assertRaises(module.MetadataAccessPropertyNotFoundError):
            module.read_metadata_value(owner, " Material ")

    def test_require_metadata_property_returns_native_type_id(self):
        module = _import_module()
        owner = _NativeOwner(
            {"Revision": 7},
            native_types={"Revision": "App::PropertyInteger"},
        )

        self.assertEqual(
            module.require_metadata_property(
                owner,
                "Revision",
                owner_id="Part001",
            ),
            "App::PropertyInteger",
        )


class TestResolvedMetadataProperty(unittest.TestCase):
    def test_read_metadata_property_returns_record(self):
        module = _import_module()
        owner = _NativeOwner(
            {"Revision": 7},
            native_types={"Revision": "App::PropertyInteger"},
        )

        result = module.read_metadata_property(
            owner,
            "Revision",
            owner_id="Part001",
        )

        self.assertEqual(result.property_name, "Revision")
        self.assertEqual(result.native_type_id, "App::PropertyInteger")
        self.assertEqual(result.value_kind, "integer")
        self.assertEqual(result.value, 7)

    def test_record_is_frozen(self):
        module = _import_module()
        result = module.ResolvedMetadataProperty(
            "Revision",
            "App::PropertyInteger",
            "integer",
            7,
        )

        with self.assertRaises(Exception):
            result.value = 8  # type: ignore[misc]


class TestNativeValueKindMapping(unittest.TestCase):
    def test_supported_native_types(self):
        module = _import_module()
        expected = {
            "App::PropertyString": "string",
            "App::PropertyBool": "boolean",
            "App::PropertyFloat": "number",
            "App::PropertyFloatConstraint": "number",
            "App::PropertyInteger": "integer",
            "App::PropertyIntegerConstraint": "integer",
        }

        self.assertEqual(module.METADATA_NATIVE_VALUE_KINDS, expected)
        for native_type, value_kind in expected.items():
            with self.subTest(native_type=native_type):
                self.assertEqual(
                    module.metadata_value_kind_for_native_type(native_type),
                    value_kind,
                )

    def test_unsupported_native_type_raises(self):
        module = _import_module()

        with self.assertRaises(module.UnsupportedMetadataPropertyTypeError):
            module.metadata_value_kind_for_native_type("App::PropertyLength")


if __name__ == "__main__":
    unittest.main()
