"""Unit tests for parametron_freecad.execution.metadata_mutation.

Uses fakes/test doubles only. No FreeCAD import is required or performed.
Real-FreeCAD metadata mutation evidence is covered separately by the opt-in
fixture/proof work.
"""

from __future__ import annotations

import copy
import math
import unittest
from typing import Any


def _entry(
    object_name: Any = "MetadataBody",
    property_name: Any = "material",
    value: Any = "steel",
    value_kind: Any = "string",
) -> dict[str, Any]:
    return {
        "object": object_name,
        "property": property_name,
        "value": value,
        "valueKind": value_kind,
    }


def _identity_store(name: str, value: Any) -> Any:
    return value


class _FakeDocument:
    """Fake FreeCAD document that resolves objects from a pre-populated dict."""

    def __init__(self, objects: dict[str, Any] | None = None) -> None:
        self._objects = dict(objects or {})
        self.get_object_calls: list[str] = []

    def getObject(self, name: str) -> Any:
        self.get_object_calls.append(name)
        return self._objects.get(name)


class _FakeTarget:
    """Fake native object with controllable native property behavior."""

    def __init__(
        self,
        *,
        properties: list[str] | None = None,
        property_types: dict[str, str] | None = None,
        values: dict[str, Any] | None = None,
        read_only: tuple[str, ...] | list[str] = (),
        write_errors: dict[str, BaseException] | None = None,
        read_errors: dict[str, BaseException] | None = None,
        store: Any = None,
    ) -> None:
        object.__setattr__(self, "_properties", list(properties or []))
        object.__setattr__(self, "_property_types", dict(property_types or {}))
        object.__setattr__(self, "_values", dict(values or {}))
        object.__setattr__(self, "_read_only", set(read_only))
        object.__setattr__(self, "_write_errors", dict(write_errors or {}))
        object.__setattr__(self, "_read_errors", dict(read_errors or {}))
        object.__setattr__(self, "_store", store or _identity_store)
        object.__setattr__(self, "_writes", [])

    @property
    def Label(self) -> str:
        raise AssertionError("target.Label must not be accessed")

    @property
    def PropertiesList(self) -> list[str]:
        return list(self._properties)

    def getTypeIdOfProperty(self, name: str) -> str:
        return self._property_types[name]

    def __getattr__(self, name: str) -> Any:
        read_errors = object.__getattribute__(self, "_read_errors")
        if name in read_errors:
            raise read_errors[name]
        values = object.__getattribute__(self, "_values")
        if name in values:
            return values[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        property_types = object.__getattribute__(self, "_property_types")
        if name.startswith("_") and name not in property_types:
            object.__setattr__(self, name, value)
            return
        write_errors = object.__getattribute__(self, "_write_errors")
        if name in write_errors:
            raise write_errors[name]
        read_only = object.__getattribute__(self, "_read_only")
        if name in read_only:
            raise AttributeError(f"Object attribute '{name}' is read-only")
        object.__getattribute__(self, "_writes").append((name, value))
        store = object.__getattribute__(self, "_store")
        values = object.__getattribute__(self, "_values")
        values[name] = store(name, value)


def _target(
    native_type: str,
    property_name: str = "value",
    stored_value: Any = "initial",
    **kwargs: Any,
) -> _FakeTarget:
    return _FakeTarget(
        properties=[property_name],
        property_types={property_name: native_type},
        values={property_name: stored_value},
        **kwargs,
    )


class _TargetWithoutPropertiesList:
    def getTypeIdOfProperty(self, name: str) -> str:
        return "App::PropertyString"


class _TargetWithoutTypeInspector:
    PropertiesList = ["material"]


class _TargetWithNonCallableTypeInspector:
    PropertiesList = ["material"]
    getTypeIdOfProperty = "not callable"


class _TargetWithRaisingPropertiesList:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    @property
    def PropertiesList(self) -> list[str]:
        raise self.error

    def getTypeIdOfProperty(self, name: str) -> str:
        return "App::PropertyString"


class _TargetWithRaisingTypeInspector:
    PropertiesList = ["material"]

    def __init__(self, error: BaseException) -> None:
        self.error = error

    def getTypeIdOfProperty(self, name: str) -> str:
        raise self.error


class _DocumentWithoutGetObject:
    pass


class _DocumentWithNonCallableGetObject:
    getObject = "not callable"


class _FailingDocument:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def getObject(self, name: str) -> Any:
        raise self.error


class PublicApiTests(unittest.TestCase):
    def test_apply_metadata_mutations_is_exported(self) -> None:
        from parametron_freecad.execution import metadata_mutation

        self.assertIn("apply_metadata_mutations", metadata_mutation.__all__)

    def test_error_classes_are_exported(self) -> None:
        from parametron_freecad.execution import metadata_mutation

        names = [
            "MetadataMutationDocumentError",
            "MetadataMutationError",
            "MetadataMutationNativeWriteError",
            "MetadataMutationNotWritableError",
            "MetadataMutationObjectNotFoundError",
            "MetadataMutationPropertyInspectionError",
            "MetadataMutationPropertyNotFoundError",
            "MetadataMutationUnsupportedPropertyTypeError",
            "MetadataMutationValueError",
            "MetadataMutationValueKindMismatchError",
            "MetadataMutationVerificationError",
        ]

        for name in names:
            with self.subTest(name=name):
                self.assertIn(name, metadata_mutation.__all__)

    def test_error_hierarchy(self) -> None:
        from parametron_freecad.execution import metadata_mutation

        self.assertTrue(issubclass(metadata_mutation.MetadataMutationError, ValueError))
        for name in [
            "MetadataMutationDocumentError",
            "MetadataMutationNativeWriteError",
            "MetadataMutationNotWritableError",
            "MetadataMutationObjectNotFoundError",
            "MetadataMutationPropertyInspectionError",
            "MetadataMutationPropertyNotFoundError",
            "MetadataMutationUnsupportedPropertyTypeError",
            "MetadataMutationValueError",
            "MetadataMutationValueKindMismatchError",
            "MetadataMutationVerificationError",
        ]:
            with self.subTest(name=name):
                self.assertTrue(
                    issubclass(
                        getattr(metadata_mutation, name),
                        metadata_mutation.MetadataMutationError,
                    )
                )

    def test_import_does_not_require_freecad(self) -> None:
        import sys

        sys.modules.pop("parametron_freecad.execution.metadata_mutation", None)
        import parametron_freecad.execution.metadata_mutation  # noqa: F401

        self.assertNotIn("FreeCAD", sys.modules)


_SUPPORTED_NATIVE_TYPE_CASES = (
    ("App::PropertyString", "string", "steel", "steel"),
    ("App::PropertyBool", "boolean", True, True),
    ("App::PropertyBool", "boolean", False, False),
    ("App::PropertyFloat", "number", 3.5, 3.5),
    ("App::PropertyFloatConstraint", "number", 2.25, 2.25),
    ("App::PropertyInteger", "integer", 7, 7),
    ("App::PropertyIntegerConstraint", "integer", 9, 9),
)


class SupportedNativeTypeTests(unittest.TestCase):
    def test_all_supported_native_types_accept_their_value_kind(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            apply_metadata_mutations,
        )

        for (
            native_type,
            value_kind,
            requested,
            expected,
        ) in _SUPPORTED_NATIVE_TYPE_CASES:
            with self.subTest(
                native_type=native_type,
                value_kind=value_kind,
                requested=requested,
            ):
                target = _target(native_type, "value", "initial")
                document = _FakeDocument({"MetadataBody": target})

                apply_metadata_mutations(
                    document,
                    [
                        _entry(
                            property_name="value",
                            value=requested,
                            value_kind=value_kind,
                        )
                    ],
                )

                self.assertEqual(target._writes, [("value", expected)])
                self.assertEqual(target._values["value"], expected)
                self.assertIs(type(target._values["value"]), type(expected))

    def test_supported_value_kinds_are_exactly_the_approved_four(self) -> None:
        from parametron_freecad.execution.manifest_contract import (
            SUPPORTED_METADATA_VALUE_KINDS,
        )

        self.assertEqual(
            SUPPORTED_METADATA_VALUE_KINDS,
            ("string", "boolean", "number", "integer"),
        )


class ExactAddressingTests(unittest.TestCase):
    def test_exact_object_name_is_passed_unchanged_to_get_object(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            apply_metadata_mutations,
        )

        target = _target("App::PropertyString", "material", "old")
        document = _FakeDocument({"Metadata Body.001": target})

        apply_metadata_mutations(
            document,
            [_entry(object_name="Metadata Body.001")],
        )

        self.assertEqual(document.get_object_calls, ["Metadata Body.001"])

    def test_case_variant_object_is_not_resolved(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationObjectNotFoundError,
            apply_metadata_mutations,
        )

        target = _target("App::PropertyString", "material", "old")
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationObjectNotFoundError):
            apply_metadata_mutations(
                document,
                [_entry(object_name="metadatabody")],
            )

        self.assertEqual(document.get_object_calls, ["metadatabody"])

    def test_exact_property_name_is_required(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationPropertyNotFoundError,
            apply_metadata_mutations,
        )

        target = _target("App::PropertyString", "material", "old")
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationPropertyNotFoundError):
            apply_metadata_mutations(
                document,
                [_entry(property_name="Material")],
            )

        self.assertEqual(target._writes, [])

    def test_whitespace_property_name_is_not_resolved(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationPropertyNotFoundError,
            apply_metadata_mutations,
        )

        target = _target("App::PropertyString", "material", "old")
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationPropertyNotFoundError):
            apply_metadata_mutations(
                document,
                [_entry(property_name=" material ")],
            )

        self.assertEqual(target._writes, [])

    def test_display_label_is_never_accessed(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            apply_metadata_mutations,
        )

        target = _target("App::PropertyString", "material", "old")
        document = _FakeDocument({"MetadataBody": target})

        apply_metadata_mutations(document, [_entry()])

        self.assertEqual(target._values["material"], "steel")


class NativeResolutionFailureTests(unittest.TestCase):
    def test_missing_object_raises_object_not_found(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationObjectNotFoundError,
            apply_metadata_mutations,
        )

        with self.assertRaises(MetadataMutationObjectNotFoundError):
            apply_metadata_mutations(_FakeDocument(), [_entry(object_name="Missing")])

    def test_object_not_found_message_identifies_entry(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationObjectNotFoundError,
            apply_metadata_mutations,
        )

        document = _FakeDocument()
        document._objects["MetadataBody"] = _target(
            "App::PropertyString", "material", "old"
        )

        try:
            apply_metadata_mutations(
                document,
                [_entry(), _entry(object_name="Gone", property_name="revision")],
            )
            self.fail("expected MetadataMutationObjectNotFoundError")
        except MetadataMutationObjectNotFoundError as exc:
            message = str(exc)
            self.assertIn("metadata[1]", message)
            self.assertIn("Gone", message)
            self.assertIn("revision", message)

    def test_missing_object_does_not_read_or_write_properties(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationObjectNotFoundError,
            apply_metadata_mutations,
        )

        document = _FakeDocument()

        with self.assertRaises(MetadataMutationObjectNotFoundError):
            apply_metadata_mutations(document, [_entry(object_name="Missing")])

        self.assertEqual(document.get_object_calls, ["Missing"])

    def test_document_without_get_object_raises_document_error(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationDocumentError,
            apply_metadata_mutations,
        )

        with self.assertRaises(MetadataMutationDocumentError):
            apply_metadata_mutations(_DocumentWithoutGetObject(), [_entry()])

    def test_non_callable_get_object_raises_document_error(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationDocumentError,
            apply_metadata_mutations,
        )

        with self.assertRaises(MetadataMutationDocumentError):
            apply_metadata_mutations(
                _DocumentWithNonCallableGetObject(),
                [_entry()],
            )

    def test_get_object_exception_raises_document_error_with_native_cause(
        self,
    ) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationDocumentError,
            apply_metadata_mutations,
        )

        original = RuntimeError("lookup failed")
        document = _FailingDocument(original)

        with self.assertRaises(MetadataMutationDocumentError) as cm:
            apply_metadata_mutations(document, [_entry()])

        self.assertIs(cm.exception.__cause__, original)


class NativeCapabilityFailureTests(unittest.TestCase):
    def test_missing_property_raises_property_not_found(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationPropertyNotFoundError,
            apply_metadata_mutations,
        )

        target = _target("App::PropertyString", "material", "old")
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationPropertyNotFoundError):
            apply_metadata_mutations(
                document,
                [_entry(property_name="supplier")],
            )

    def test_missing_property_is_not_created(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationPropertyNotFoundError,
            apply_metadata_mutations,
        )

        target = _target("App::PropertyString", "material", "old")
        document = _FakeDocument({"MetadataBody": target})
        properties_before = list(target.PropertiesList)

        with self.assertRaises(MetadataMutationPropertyNotFoundError):
            apply_metadata_mutations(
                document,
                [_entry(property_name="supplier", value="ACME")],
            )

        self.assertEqual(target.PropertiesList, properties_before)
        self.assertNotIn("supplier", target._values)
        self.assertFalse(hasattr(target, "supplier"))
        self.assertEqual(target._writes, [])

    def test_unsupported_native_type_raises_unsupported_property_type(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationUnsupportedPropertyTypeError,
            apply_metadata_mutations,
        )

        target = _target("App::PropertyLength", "measured_length", 12.0)
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationUnsupportedPropertyTypeError) as cm:
            apply_metadata_mutations(
                document,
                [
                    _entry(
                        property_name="measured_length",
                        value=15.0,
                        value_kind="number",
                    )
                ],
            )

        self.assertIn("App::PropertyLength", str(cm.exception))
        self.assertEqual(target._writes, [])

    def test_unsupported_quantity_family_types_fail_deterministically(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationUnsupportedPropertyTypeError,
            apply_metadata_mutations,
        )

        for native_type in (
            "App::PropertyDistance",
            "App::PropertyAngle",
            "App::PropertyQuantity",
        ):
            with self.subTest(native_type=native_type):
                target = _target(native_type, "value", 1.0)
                document = _FakeDocument({"MetadataBody": target})

                with self.assertRaises(MetadataMutationUnsupportedPropertyTypeError):
                    apply_metadata_mutations(
                        document,
                        [
                            _entry(
                                property_name="value",
                                value=2.0,
                                value_kind="number",
                            )
                        ],
                    )

                self.assertEqual(target._writes, [])

    def test_value_kind_native_type_mismatch_raises_mismatch_error(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationValueKindMismatchError,
            apply_metadata_mutations,
        )

        target = _target("App::PropertyInteger", "revision", 7)
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationValueKindMismatchError) as cm:
            apply_metadata_mutations(
                document,
                [
                    _entry(
                        property_name="revision",
                        value="seven",
                        value_kind="string",
                    )
                ],
            )

        message = str(cm.exception)
        self.assertIn("'string'", message)
        self.assertIn("'integer'", message)
        self.assertIn("App::PropertyInteger", message)
        self.assertEqual(target._writes, [])

    def test_mismatch_does_not_write_before_failing(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationValueKindMismatchError,
            apply_metadata_mutations,
        )

        target = _target("App::PropertyFloat", "mass", 1.0)
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationValueKindMismatchError):
            apply_metadata_mutations(
                document,
                [_entry(property_name="mass", value=7, value_kind="integer")],
            )

        self.assertEqual(target._writes, [])
        self.assertEqual(target._values["mass"], 1.0)


class NativeWriteFailureTests(unittest.TestCase):
    def test_read_only_native_property_raises_not_writable(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationNotWritableError,
            apply_metadata_mutations,
        )

        target = _target(
            "App::PropertyInteger",
            "_ExternalGeoVersion",
            1,
            read_only=("_ExternalGeoVersion",),
        )
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationNotWritableError) as cm:
            apply_metadata_mutations(
                document,
                [
                    _entry(
                        property_name="_ExternalGeoVersion",
                        value=2,
                        value_kind="integer",
                    )
                ],
            )

        self.assertIn("not writable", str(cm.exception))
        self.assertIsInstance(cm.exception.__cause__, AttributeError)
        self.assertEqual(target._writes, [])

    def test_other_native_write_exception_raises_native_write_error(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationNativeWriteError,
            apply_metadata_mutations,
        )

        original = RuntimeError("native write failure")
        target = _target(
            "App::PropertyString",
            "material",
            "old",
            write_errors={"material": original},
        )
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationNativeWriteError) as cm:
            apply_metadata_mutations(document, [_entry()])

        self.assertIs(cm.exception.__cause__, original)
        self.assertIn("write failed", str(cm.exception))

    def test_non_read_only_attribute_error_raises_native_write_error(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationNativeWriteError,
            apply_metadata_mutations,
        )

        original = AttributeError("unexpected native failure")
        target = _target(
            "App::PropertyString",
            "material",
            "old",
            write_errors={"material": original},
        )
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationNativeWriteError) as cm:
            apply_metadata_mutations(document, [_entry()])

        self.assertIs(cm.exception.__cause__, original)

    def test_write_failure_message_identifies_entry(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationNativeWriteError,
            apply_metadata_mutations,
        )

        target = _target(
            "App::PropertyString",
            "material",
            "old",
            write_errors={"material": RuntimeError("boom")},
        )
        document = _FakeDocument({"MetadataBody": target})

        try:
            apply_metadata_mutations(document, [_entry()])
            self.fail("expected MetadataMutationNativeWriteError")
        except MetadataMutationNativeWriteError as exc:
            message = str(exc)
            self.assertIn("metadata[0]", message)
            self.assertIn("MetadataBody", message)
            self.assertIn("material", message)


class PostWriteVerificationTests(unittest.TestCase):
    def test_float_constraint_clamping_raises_verification_error(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationVerificationError,
            apply_metadata_mutations,
        )

        target = _target(
            "App::PropertyFloatConstraint",
            "tolerance",
            0.1,
            store=lambda name, value: 1.0,
        )
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationVerificationError) as cm:
            apply_metadata_mutations(
                document,
                [
                    _entry(
                        property_name="tolerance",
                        value=99.0,
                        value_kind="number",
                    )
                ],
            )

        message = str(cm.exception)
        self.assertIn("99.0", message)
        self.assertIn("1.0", message)

    def test_integer_overflow_wrap_raises_verification_error(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationVerificationError,
            apply_metadata_mutations,
        )

        target = _target(
            "App::PropertyInteger",
            "revision",
            0,
            store=lambda name, value: -1,
        )
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationVerificationError):
            apply_metadata_mutations(
                document,
                [
                    _entry(
                        property_name="revision",
                        value=2**63 - 1,
                        value_kind="integer",
                    )
                ],
            )

    def test_boolean_numeric_coercion_raises_verification_error(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationVerificationError,
            apply_metadata_mutations,
        )

        target = _target(
            "App::PropertyBool",
            "tagged",
            False,
            store=lambda name, value: 1,
        )
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationVerificationError):
            apply_metadata_mutations(
                document,
                [
                    _entry(
                        property_name="tagged",
                        value=True,
                        value_kind="boolean",
                    )
                ],
            )

    def test_string_read_back_must_be_a_string(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationVerificationError,
            apply_metadata_mutations,
        )

        target = _target(
            "App::PropertyString",
            "material",
            "old",
            store=lambda name, value: 7,
        )
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationVerificationError):
            apply_metadata_mutations(document, [_entry()])

    def test_number_read_back_must_be_a_float(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationVerificationError,
            apply_metadata_mutations,
        )

        target = _target(
            "App::PropertyFloat",
            "mass",
            1.0,
            store=lambda name, value: 3,
        )
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationVerificationError):
            apply_metadata_mutations(
                document,
                [_entry(property_name="mass", value=3.5, value_kind="number")],
            )

    def test_integer_read_back_must_be_an_integer(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationVerificationError,
            apply_metadata_mutations,
        )

        target = _target(
            "App::PropertyInteger",
            "revision",
            0,
            store=lambda name, value: 7.0,
        )
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationVerificationError):
            apply_metadata_mutations(
                document,
                [
                    _entry(
                        property_name="revision",
                        value=7,
                        value_kind="integer",
                    )
                ],
            )

    def test_read_back_failure_raises_verification_error_with_cause(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationVerificationError,
            apply_metadata_mutations,
        )

        original = RuntimeError("read failed")
        target = _target(
            "App::PropertyString",
            "material",
            "old",
            read_errors={"material": original},
        )
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationVerificationError) as cm:
            apply_metadata_mutations(document, [_entry()])

        self.assertIs(cm.exception.__cause__, original)


class NoPropertyCreationTests(unittest.TestCase):
    def test_successful_write_does_not_change_properties_list(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            apply_metadata_mutations,
        )

        target = _target("App::PropertyString", "material", "old")
        document = _FakeDocument({"MetadataBody": target})
        properties_before = list(target.PropertiesList)

        apply_metadata_mutations(document, [_entry()])

        self.assertEqual(target.PropertiesList, properties_before)
        self.assertEqual(properties_before, ["material"])

    def test_failed_entries_never_add_properties(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationError,
            apply_metadata_mutations,
        )

        scenarios = (
            (
                "missing_property",
                _target("App::PropertyString", "material", "old"),
                _entry(property_name="supplier", value="ACME"),
            ),
            (
                "unsupported_type",
                _target("App::PropertyLength", "measured_length", 1.0),
                _entry(
                    property_name="measured_length",
                    value=2.0,
                    value_kind="number",
                ),
            ),
            (
                "value_kind_mismatch",
                _target("App::PropertyInteger", "revision", 1),
                _entry(property_name="revision", value="two", value_kind="string"),
            ),
            (
                "not_writable",
                _target(
                    "App::PropertyInteger",
                    "revision",
                    1,
                    read_only=("revision",),
                ),
                _entry(property_name="revision", value=2, value_kind="integer"),
            ),
            (
                "post_write_mismatch",
                _target(
                    "App::PropertyFloat",
                    "mass",
                    1.0,
                    store=lambda name, value: 2.0,
                ),
                _entry(property_name="mass", value=3.0, value_kind="number"),
            ),
        )

        for label, target, entry in scenarios:
            with self.subTest(label=label):
                document = _FakeDocument({"MetadataBody": target})
                properties_before = list(target.PropertiesList)

                with self.assertRaises(MetadataMutationError):
                    apply_metadata_mutations(document, [entry])

                self.assertEqual(target.PropertiesList, properties_before)
                self.assertNotIn("supplier", target.PropertiesList)
                self.assertNotIn("new_property", target._values)


def _store_in(order: list[str], name: str) -> Any:
    def store(property_name: str, value: Any) -> Any:
        order.append(name)
        return value

    return store


class OrderingAndFailFastTests(unittest.TestCase):
    def test_multiple_entries_applied_in_caller_provided_order(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            apply_metadata_mutations,
        )

        order: list[str] = []
        document = _FakeDocument(
            {
                "C": _target(
                    "App::PropertyString",
                    "material",
                    "old",
                    store=_store_in(order, "C"),
                ),
                "A": _target(
                    "App::PropertyString",
                    "material",
                    "old",
                    store=_store_in(order, "A"),
                ),
                "B": _target(
                    "App::PropertyString",
                    "material",
                    "old",
                    store=_store_in(order, "B"),
                ),
            }
        )

        apply_metadata_mutations(
            document,
            [
                _entry(object_name="C"),
                _entry(object_name="A"),
                _entry(object_name="B"),
            ],
        )

        self.assertEqual(order, ["C", "A", "B"])

    def test_stops_at_first_failure(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationPropertyNotFoundError,
            apply_metadata_mutations,
        )

        target = _FakeTarget(
            properties=["material"],
            property_types={"material": "App::PropertyString"},
            values={"material": "old"},
        )
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationPropertyNotFoundError):
            apply_metadata_mutations(
                document,
                [
                    _entry(),
                    _entry(property_name="supplier", value="ACME"),
                    _entry(property_name="material", value="late"),
                ],
            )

        self.assertEqual(target._values["material"], "steel")
        self.assertEqual(target._writes, [("material", "steel")])

    def test_earlier_successful_writes_remain_after_later_failure(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationObjectNotFoundError,
            apply_metadata_mutations,
        )

        target = _target("App::PropertyString", "material", "old")
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationObjectNotFoundError):
            apply_metadata_mutations(
                document,
                [_entry(), _entry(object_name="Missing")],
            )

        self.assertEqual(target._values["material"], "steel")

    def test_later_entries_are_not_applied_after_earlier_failure(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationObjectNotFoundError,
            apply_metadata_mutations,
        )

        later = _target("App::PropertyString", "material", "old")
        document = _FakeDocument({"MetadataBody": later})

        with self.assertRaises(MetadataMutationObjectNotFoundError):
            apply_metadata_mutations(
                document,
                [_entry(object_name="Missing"), _entry()],
            )

        self.assertEqual(later._writes, [])
        self.assertEqual(later._values["material"], "old")

    def test_successful_writes_remain_across_verification_failure(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationVerificationError,
            apply_metadata_mutations,
        )

        good = _target("App::PropertyString", "material", "old")
        clamped = _target(
            "App::PropertyFloatConstraint",
            "tolerance",
            0.1,
            store=lambda name, value: 1.0,
        )
        document = _FakeDocument({"MetadataBody": good, "OtherBody": clamped})

        with self.assertRaises(MetadataMutationVerificationError):
            apply_metadata_mutations(
                document,
                [
                    _entry(),
                    _entry(
                        object_name="OtherBody",
                        property_name="tolerance",
                        value=99.0,
                        value_kind="number",
                    ),
                ],
            )

        self.assertEqual(good._values["material"], "steel")


class InputImmutabilityTests(unittest.TestCase):
    def test_supplied_entries_are_not_modified_on_success(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            apply_metadata_mutations,
        )

        entries = [
            _entry(),
            _entry(property_name="tagged", value=True, value_kind="boolean"),
        ]
        snapshot = copy.deepcopy(entries)
        target = _FakeTarget(
            properties=["material", "tagged"],
            property_types={
                "material": "App::PropertyString",
                "tagged": "App::PropertyBool",
            },
            values={"material": "old", "tagged": False},
        )
        document = _FakeDocument({"MetadataBody": target})

        apply_metadata_mutations(document, entries)

        self.assertEqual(entries, snapshot)
        self.assertEqual(len(entries[0]), 4)
        self.assertEqual(len(entries[1]), 4)

    def test_supplied_entries_are_not_modified_on_failure(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationValueKindMismatchError,
            apply_metadata_mutations,
        )

        entries = [_entry(property_name="revision", value="two", value_kind="string")]
        snapshot = copy.deepcopy(entries)
        target = _target("App::PropertyInteger", "revision", 1)
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationValueKindMismatchError):
            apply_metadata_mutations(document, entries)

        self.assertEqual(entries, snapshot)


class NormalizationTests(unittest.TestCase):
    def test_integral_float_is_normalized_to_int_for_integer(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            apply_metadata_mutations,
        )

        target = _target("App::PropertyInteger", "revision", 0)
        document = _FakeDocument({"MetadataBody": target})

        apply_metadata_mutations(
            document,
            [
                _entry(
                    property_name="revision",
                    value=7.0,
                    value_kind="integer",
                )
            ],
        )

        self.assertEqual(target._writes, [("revision", 7)])
        self.assertIs(type(target._values["revision"]), int)

    def test_integer_is_normalized_to_float_for_number(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            apply_metadata_mutations,
        )

        target = _target("App::PropertyFloat", "mass", 0.0)
        document = _FakeDocument({"MetadataBody": target})

        apply_metadata_mutations(
            document,
            [_entry(property_name="mass", value=7, value_kind="number")],
        )

        self.assertEqual(target._writes, [("mass", 7.0)])
        self.assertIs(type(target._values["mass"]), float)

    def test_integer_input_stays_int_for_integer(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            apply_metadata_mutations,
        )

        target = _target("App::PropertyInteger", "revision", 0)
        document = _FakeDocument({"MetadataBody": target})

        apply_metadata_mutations(
            document,
            [
                _entry(
                    property_name="revision",
                    value=7,
                    value_kind="integer",
                )
            ],
        )

        self.assertEqual(target._writes, [("revision", 7)])
        self.assertIs(type(target._values["revision"]), int)

    def test_float_input_stays_float_for_number(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            apply_metadata_mutations,
        )

        target = _target("App::PropertyFloat", "mass", 0.0)
        document = _FakeDocument({"MetadataBody": target})

        apply_metadata_mutations(
            document,
            [_entry(property_name="mass", value=7.0, value_kind="number")],
        )

        self.assertEqual(target._writes, [("mass", 7.0)])
        self.assertIs(type(target._values["mass"]), float)

    def test_signed_int64_boundaries_are_accepted(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            METADATA_INTEGER_MAX,
            METADATA_INTEGER_MIN,
            apply_metadata_mutations,
        )

        for value in (METADATA_INTEGER_MIN, METADATA_INTEGER_MAX - 1):
            with self.subTest(value=value):
                target = _target("App::PropertyInteger", "revision", 0)
                document = _FakeDocument({"MetadataBody": target})

                apply_metadata_mutations(
                    document,
                    [
                        _entry(
                            property_name="revision",
                            value=value,
                            value_kind="integer",
                        )
                    ],
                )

                self.assertEqual(target._values["revision"], value)
                self.assertIs(type(target._values["revision"]), int)


class ValueRejectionTests(unittest.TestCase):
    def _assert_value_error(
        self, native_type: str, value_kind: str, value: Any
    ) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationValueError,
            apply_metadata_mutations,
        )

        target = _target(native_type, "value", "initial")
        document = _FakeDocument({"MetadataBody": target})

        with self.assertRaises(MetadataMutationValueError):
            apply_metadata_mutations(
                document,
                [
                    _entry(
                        property_name="value",
                        value=value,
                        value_kind=value_kind,
                    )
                ],
            )

        self.assertEqual(target._writes, [])

    def test_non_finite_numbers_are_rejected(self) -> None:
        for value in (math.inf, -math.inf, math.nan):
            with self.subTest(value=value):
                self._assert_value_error("App::PropertyFloat", "number", value)

    def test_unrepresentable_number_is_rejected(self) -> None:
        self._assert_value_error("App::PropertyFloat", "number", 10**400)

    def test_non_integral_values_are_rejected_for_integer(self) -> None:
        for value in (2.5, -2.5, math.inf, math.nan):
            with self.subTest(value=value):
                self._assert_value_error(
                    "App::PropertyInteger",
                    "integer",
                    value,
                )

    def test_int64_overflow_is_rejected(self) -> None:
        for value in (2**63, -(2**63) - 1, float(2**63)):
            with self.subTest(value=value):
                self._assert_value_error(
                    "App::PropertyInteger",
                    "integer",
                    value,
                )

    def test_bool_is_rejected_for_number(self) -> None:
        for value in (True, False):
            with self.subTest(value=value):
                self._assert_value_error(
                    "App::PropertyFloat",
                    "number",
                    value,
                )

    def test_bool_is_rejected_for_integer(self) -> None:
        for value in (True, False):
            with self.subTest(value=value):
                self._assert_value_error(
                    "App::PropertyInteger",
                    "integer",
                    value,
                )

    def test_non_string_is_rejected_for_string(self) -> None:
        for value in (7, True, 1.5, None, ["steel"]):
            with self.subTest(value=value):
                self._assert_value_error(
                    "App::PropertyString",
                    "string",
                    value,
                )

    def test_non_bool_is_rejected_for_boolean(self) -> None:
        for value in (0, 1, 1.0, "true", None):
            with self.subTest(value=value):
                self._assert_value_error(
                    "App::PropertyBool",
                    "boolean",
                    value,
                )

    def test_unsupported_value_kind_is_rejected(self) -> None:
        self._assert_value_error("App::PropertyString", "decimal", "1.5")


class InspectionFailureTests(unittest.TestCase):
    def test_missing_properties_list_raises_inspection_error(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationPropertyInspectionError,
            apply_metadata_mutations,
        )

        document = _FakeDocument({"MetadataBody": _TargetWithoutPropertiesList()})

        with self.assertRaises(MetadataMutationPropertyInspectionError):
            apply_metadata_mutations(document, [_entry()])

    def test_missing_type_inspector_raises_inspection_error(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationPropertyInspectionError,
            apply_metadata_mutations,
        )

        document = _FakeDocument({"MetadataBody": _TargetWithoutTypeInspector()})

        with self.assertRaises(MetadataMutationPropertyInspectionError):
            apply_metadata_mutations(document, [_entry()])

    def test_non_callable_type_inspector_raises_inspection_error(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationPropertyInspectionError,
            apply_metadata_mutations,
        )

        document = _FakeDocument(
            {"MetadataBody": _TargetWithNonCallableTypeInspector()}
        )

        with self.assertRaises(MetadataMutationPropertyInspectionError):
            apply_metadata_mutations(document, [_entry()])

    def test_raising_properties_list_raises_inspection_error_with_cause(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationPropertyInspectionError,
            apply_metadata_mutations,
        )

        original = RuntimeError("properties inspection failed")
        document = _FakeDocument(
            {"MetadataBody": _TargetWithRaisingPropertiesList(original)}
        )

        with self.assertRaises(MetadataMutationPropertyInspectionError) as cm:
            apply_metadata_mutations(document, [_entry()])

        self.assertIs(cm.exception.__cause__, original)

    def test_raising_type_inspector_raises_inspection_error_with_cause(self) -> None:
        from parametron_freecad.execution.metadata_mutation import (
            MetadataMutationPropertyInspectionError,
            apply_metadata_mutations,
        )

        original = RuntimeError("type inspection failed")
        document = _FakeDocument(
            {"MetadataBody": _TargetWithRaisingTypeInspector(original)}
        )

        with self.assertRaises(MetadataMutationPropertyInspectionError) as cm:
            apply_metadata_mutations(document, [_entry()])

        self.assertIs(cm.exception.__cause__, original)


if __name__ == "__main__":
    unittest.main()
