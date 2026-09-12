"""Tests for requested metadata observation under ordinary Python."""

from __future__ import annotations

import copy
import importlib
import io
import math
import sys
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock


MODULE_NAME = "parametron_freecad.observation.metadata_observation"
EXPECTED_OBSERVED_FIELDS = ("id", "key", "ownerId", "value", "valueKind")


def _import_module():
    return importlib.import_module(MODULE_NAME)


def _verification(requests, enabled=True, observation_context_metadata=None):
    data = {
        "observe": {"metadata": enabled},
        "expected": {"metadata": requests},
    }
    if observation_context_metadata is not None:
        data["observationContext"] = {"metadata": observation_context_metadata}
    return data


def _request(meta_id="m.title", key="Title", owner_id="Part001"):
    return {"id": meta_id, "key": key, "ownerId": owner_id}


class FakeOwner:
    def __init__(self, **properties):
        object.__setattr__(self, "read_names", [])
        for name, value in properties.items():
            object.__setattr__(self, name, value)

    def __getattribute__(self, name):
        if not name.startswith("_") and name != "read_names":
            object.__getattribute__(self, "read_names").append(name)
        return object.__getattribute__(self, name)


class RaisingOwner:
    def __getattr__(self, name):
        raise RuntimeError(f"cannot read {name}")


class FakeDocument:
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


class NoGetObjectDocument:
    pass


class NonCallableGetObjectDocument:
    getObject = "not callable"


class FailingDocument:
    def getObject(self, name):
        raise AssertionError("getObject must not be called")


# ---------------------------------------------------------------------------
# Section 1 - Import safety and public API
# ---------------------------------------------------------------------------


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

    def test_observe_requested_metadata_is_exposed(self):
        from parametron_freecad.observation.metadata_observation import (
            observe_requested_metadata,
        )
        self.assertTrue(callable(observe_requested_metadata))

    def test_all_typed_errors_are_exposed(self):
        from parametron_freecad.observation.metadata_observation import (
            MetadataObservationDocumentError,
            MetadataObservationError,
            MetadataObservationOwnerNotFoundError,
            MetadataObservationPropertyError,
            MetadataObservationRequestError,
            MetadataObservationValueError,
        )
        for cls in (
            MetadataObservationDocumentError,
            MetadataObservationOwnerNotFoundError,
            MetadataObservationPropertyError,
            MetadataObservationRequestError,
            MetadataObservationValueError,
        ):
            self.assertTrue(issubclass(cls, MetadataObservationError), cls.__name__)

    def test_base_error_inherits_from_value_error(self):
        from parametron_freecad.observation.metadata_observation import MetadataObservationError
        self.assertTrue(issubclass(MetadataObservationError, ValueError))

    def test_public_errors_inherit_from_base(self):
        from parametron_freecad.observation.metadata_observation import (
            MetadataObservationDocumentError,
            MetadataObservationError,
            MetadataObservationOwnerNotFoundError,
            MetadataObservationPropertyError,
            MetadataObservationRequestError,
            MetadataObservationValueError,
        )
        subclasses = (
            MetadataObservationDocumentError,
            MetadataObservationOwnerNotFoundError,
            MetadataObservationPropertyError,
            MetadataObservationRequestError,
            MetadataObservationValueError,
        )
        for cls in subclasses:
            with self.subTest(cls=cls.__name__):
                self.assertTrue(issubclass(cls, MetadataObservationError))


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _MetadataObservationTestCase(unittest.TestCase):
    def setUp(self):
        self.mo = _import_module()

    def observe(self, document, verification_data):
        return self.mo.observe_requested_metadata(document, verification_data)

    def assertRequestError(self, verification_data):
        with self.assertRaises(self.mo.MetadataObservationRequestError) as cm:
            self.observe(FakeDocument(), verification_data)
        self.assertTrue(str(cm.exception))


# ---------------------------------------------------------------------------
# Section 2 - Disabled or absent metadata observation
# ---------------------------------------------------------------------------


class TestDisabledMetadataObservation(_MetadataObservationTestCase):
    def test_missing_observe_returns_empty_tuple(self):
        self.assertEqual(self.observe(FailingDocument(), {}), ())

    def test_observe_not_a_mapping_returns_empty_tuple(self):
        for value in (None, True, "string", 42, []):
            with self.subTest(value=value):
                self.assertEqual(self.observe(FailingDocument(), {"observe": value}), ())

    def test_missing_observe_metadata_returns_empty_tuple(self):
        self.assertEqual(self.observe(FailingDocument(), {"observe": {}}), ())

    def test_false_observe_metadata_returns_empty_tuple(self):
        data = {"observe": {"metadata": False}}
        self.assertEqual(self.observe(FailingDocument(), data), ())

    def test_none_observe_metadata_returns_empty_tuple(self):
        data = {"observe": {"metadata": None}}
        self.assertEqual(self.observe(FailingDocument(), data), ())

    def test_falsy_observe_metadata_returns_empty_tuple(self):
        for value in (0, [], {}, ""):
            with self.subTest(value=repr(value)):
                data = {"observe": {"metadata": value}}
                self.assertEqual(self.observe(FailingDocument(), data), ())

    def test_disabled_does_not_call_get_object(self):
        for data in (
            {},
            {"observe": {}},
            {"observe": {"metadata": False}},
            {"observe": {"metadata": None}},
        ):
            with self.subTest(data=data):
                self.assertEqual(self.observe(FailingDocument(), data), ())


# ---------------------------------------------------------------------------
# Section 3 - Reads requests from expected.metadata only
# ---------------------------------------------------------------------------


class TestRequestsFromExpectedMetadata(_MetadataObservationTestCase):
    def test_requests_come_from_expected_metadata_not_observation_context(self):
        owner = FakeOwner(Title="Bracket")
        document = FakeDocument({"Part001": owner})
        data = _verification(
            requests=[_request("m.title", "Title", "Part001")],
            observation_context_metadata=[{"id": "ignored", "key": "OtherKey", "ownerId": "OtherObj"}],
        )

        result = self.observe(document, data)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "m.title")
        self.assertEqual(result[0]["key"], "Title")
        self.assertEqual(result[0]["ownerId"], "Part001")
        self.assertEqual(document.calls, ["Part001"])

    def test_observation_context_metadata_is_ignored_when_present(self):
        owner = FakeOwner(X=1)
        document = FakeDocument({"ObjA": owner})
        data = _verification(
            requests=[_request("m.x", "X", "ObjA")],
            observation_context_metadata=[
                {"id": "m.decoy", "key": "Decoy", "ownerId": "ObjDecoy"},
                {"id": "m.decoy2", "key": "Decoy2", "ownerId": "ObjDecoy2"},
            ],
        )

        result = self.observe(document, data)

        self.assertEqual(len(result), 1)
        self.assertEqual(document.calls, ["ObjA"])


# ---------------------------------------------------------------------------
# Section 4 - Successful observation output
# ---------------------------------------------------------------------------


class TestSuccessfulObservation(_MetadataObservationTestCase):
    def test_return_type_is_tuple(self):
        owner = FakeOwner(Title="Part")
        document = FakeDocument({"Part001": owner})
        data = _verification([_request("m.title", "Title", "Part001")])

        result = self.observe(document, data)

        self.assertIsInstance(result, tuple)

    def test_output_order_matches_request_order(self):
        owner_a = FakeOwner(Color="red")
        owner_b = FakeOwner(Mass=7)
        document = FakeDocument({"ObjA": owner_a, "ObjB": owner_b})
        data = _verification([
            _request("m.color", "Color", "ObjA"),
            _request("m.mass", "Mass", "ObjB"),
        ])

        result = self.observe(document, data)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "m.color")
        self.assertEqual(result[1]["id"], "m.mass")

    def test_each_entry_has_exactly_the_required_fields(self):
        owner = FakeOwner(Title="x")
        document = FakeDocument({"Part001": owner})
        data = _verification([_request()])

        result = self.observe(document, data)

        self.assertEqual(tuple(result[0].keys()), EXPECTED_OBSERVED_FIELDS)

    def test_id_key_owner_id_copied_from_request(self):
        owner = FakeOwner(MyKey="value")
        document = FakeDocument({"Assembly001": owner})
        data = _verification([_request("m.custom", "MyKey", "Assembly001")])

        result = self.observe(document, data)

        self.assertEqual(result[0]["id"], "m.custom")
        self.assertEqual(result[0]["key"], "MyKey")
        self.assertEqual(result[0]["ownerId"], "Assembly001")

    def test_value_read_from_getattr_on_owner(self):
        owner = FakeOwner(Title="Bracket")
        document = FakeDocument({"Part001": owner})
        data = _verification([_request("m.title", "Title", "Part001")])

        result = self.observe(document, data)

        self.assertEqual(result[0]["value"], "Bracket")

    def test_value_kind_derived_from_observed_runtime_value(self):
        owner = FakeOwner(Name="beam", Count=3, Weight=1.5, Active=True)
        document = FakeDocument({"Obj": owner})
        data = _verification([
            _request("m.name", "Name", "Obj"),
            _request("m.count", "Count", "Obj"),
            _request("m.weight", "Weight", "Obj"),
            _request("m.active", "Active", "Obj"),
        ])

        result = self.observe(document, data)

        self.assertEqual(result[0]["valueKind"], "string")
        self.assertEqual(result[1]["valueKind"], "integer")
        self.assertEqual(result[2]["valueKind"], "number")
        self.assertEqual(result[3]["valueKind"], "boolean")

    def test_multiple_entries_full_content(self):
        part = FakeOwner(Material="steel")
        assembly = FakeOwner(IsLocked=False)
        document = FakeDocument({"Part001": part, "Assembly001": assembly})
        data = _verification([
            _request("m.material", "Material", "Part001"),
            _request("m.locked", "IsLocked", "Assembly001"),
        ])

        result = self.observe(document, data)

        self.assertEqual(result, (
            {
                "id": "m.material",
                "key": "Material",
                "ownerId": "Part001",
                "value": "steel",
                "valueKind": "string",
            },
            {
                "id": "m.locked",
                "key": "IsLocked",
                "ownerId": "Assembly001",
                "value": False,
                "valueKind": "boolean",
            },
        ))


# ---------------------------------------------------------------------------
# Section 5 - Value-kind mapping
# ---------------------------------------------------------------------------


class TestValueKindMapping(_MetadataObservationTestCase):
    def _observe_single_kind(self, value, key="Val", owner_id="Obj"):
        document = FakeDocument({owner_id: FakeOwner(**{key: value})})
        data = _verification([_request("m.v", key, owner_id)])
        result = self.observe(document, data)
        return result[0]["valueKind"]

    def test_bool_maps_to_boolean(self):
        self.assertEqual(self._observe_single_kind(True), "boolean")
        self.assertEqual(self._observe_single_kind(False), "boolean")

    def test_int_excluding_bool_maps_to_integer(self):
        self.assertEqual(self._observe_single_kind(0), "integer")
        self.assertEqual(self._observe_single_kind(42), "integer")
        self.assertEqual(self._observe_single_kind(-7), "integer")

    def test_finite_float_maps_to_number(self):
        self.assertEqual(self._observe_single_kind(3.14), "number")
        self.assertEqual(self._observe_single_kind(0.0), "number")
        self.assertEqual(self._observe_single_kind(-1.5), "number")

    def test_str_maps_to_string(self):
        self.assertEqual(self._observe_single_kind("hello"), "string")
        self.assertEqual(self._observe_single_kind(""), "string")

    def test_true_is_not_treated_as_integer(self):
        kind = self._observe_single_kind(True)
        self.assertEqual(kind, "boolean")
        self.assertNotEqual(kind, "integer")

    def test_false_is_not_treated_as_integer(self):
        kind = self._observe_single_kind(False)
        self.assertEqual(kind, "boolean")
        self.assertNotEqual(kind, "integer")


# ---------------------------------------------------------------------------
# Section 6 - Unsupported observed values
# ---------------------------------------------------------------------------


class TestUnsupportedObservedValues(_MetadataObservationTestCase):
    def _assert_value_error(self, value, key="Val", owner_id="Obj"):
        document = FakeDocument({owner_id: FakeOwner(**{key: value})})
        data = _verification([_request("m.v", key, owner_id)])
        with self.assertRaises(self.mo.MetadataObservationValueError):
            self.observe(document, data)

    def test_none_is_unsupported(self):
        self._assert_value_error(None)

    def test_list_is_unsupported(self):
        self._assert_value_error([1, 2, 3])

    def test_dict_is_unsupported(self):
        self._assert_value_error({"a": 1})

    def test_tuple_is_unsupported(self):
        self._assert_value_error((1, 2))

    def test_arbitrary_object_is_unsupported(self):
        self._assert_value_error(object())

    def test_nan_is_unsupported(self):
        self._assert_value_error(float("nan"))

    def test_positive_inf_is_unsupported(self):
        self._assert_value_error(float("inf"))

    def test_negative_inf_is_unsupported(self):
        self._assert_value_error(float("-inf"))

    def test_unsupported_values_raise_not_coerce(self):
        for value in (None, [1], {"a": 1}, (1,)):
            with self.subTest(value=type(value).__name__):
                document = FakeDocument({"Obj": FakeOwner(Val=value)})
                data = _verification([_request("m.v", "Val", "Obj")])
                with self.assertRaises(self.mo.MetadataObservationValueError):
                    self.observe(document, data)


# ---------------------------------------------------------------------------
# Section 7 - Malformed request data
# ---------------------------------------------------------------------------


class TestMalformedRequestData(_MetadataObservationTestCase):
    def test_missing_expected_raises_request_error(self):
        self.assertRequestError({"observe": {"metadata": True}})

    def test_non_mapping_expected_raises_request_error(self):
        for value in (None, [], "string", 42):
            with self.subTest(value=value):
                self.assertRequestError({"observe": {"metadata": True}, "expected": value})

    def test_missing_expected_metadata_raises_request_error(self):
        self.assertRequestError({"observe": {"metadata": True}, "expected": {}})

    def test_non_iterable_expected_metadata_raises_request_error(self):
        self.assertRequestError({"observe": {"metadata": True}, "expected": {"metadata": 7}})

    def test_string_expected_metadata_raises_request_error(self):
        self.assertRequestError({"observe": {"metadata": True}, "expected": {"metadata": "abc"}})

    def test_bytes_expected_metadata_raises_request_error(self):
        self.assertRequestError({"observe": {"metadata": True}, "expected": {"metadata": b"abc"}})

    def test_entry_not_mapping_raises_request_error(self):
        self.assertRequestError(_verification(["not a mapping"]))

    def test_missing_id_raises_request_error(self):
        self.assertRequestError(_verification([{"key": "Title", "ownerId": "Part001"}]))

    def test_missing_key_raises_request_error(self):
        self.assertRequestError(_verification([{"id": "m.title", "ownerId": "Part001"}]))

    def test_missing_owner_id_raises_request_error(self):
        self.assertRequestError(_verification([{"id": "m.title", "key": "Title"}]))

    def test_non_string_id_raises_request_error(self):
        self.assertRequestError(_verification([{"id": 1, "key": "Title", "ownerId": "Part001"}]))

    def test_non_string_key_raises_request_error(self):
        self.assertRequestError(_verification([{"id": "m.title", "key": None, "ownerId": "Part001"}]))

    def test_non_string_owner_id_raises_request_error(self):
        self.assertRequestError(_verification([{"id": "m.title", "key": "Title", "ownerId": object()}]))

    def test_unknown_fields_are_tolerated(self):
        owner = FakeOwner(Title="x")
        document = FakeDocument({"Part001": owner})
        request = _request()
        request["unknownField"] = "some_value"
        request["anotherUnknown"] = 99
        data = _verification([request])
        result = self.observe(document, data)
        self.assertEqual(len(result), 1)

    def test_invalid_expected_value_kind_does_not_block_observation(self):
        owner = FakeOwner(Count=5)
        document = FakeDocument({"Obj": owner})
        request = {"id": "m.count", "key": "Count", "ownerId": "Obj", "valueKind": "invalid_kind"}
        data = _verification([request])
        result = self.observe(document, data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["value"], 5)
        self.assertEqual(result[0]["valueKind"], "integer")

    def test_absent_expected_value_and_value_kind_do_not_block_observation(self):
        owner = FakeOwner(X=42)
        document = FakeDocument({"ObjA": owner})
        request = {"id": "m.x", "key": "X", "ownerId": "ObjA"}
        data = _verification([request])
        result = self.observe(document, data)
        self.assertEqual(result[0]["value"], 42)


# ---------------------------------------------------------------------------
# Section 8 - Document and owner resolution failures
# ---------------------------------------------------------------------------


class TestDocumentAndOwnerResolution(_MetadataObservationTestCase):
    def test_missing_get_object_raises_document_error(self):
        with self.assertRaises(self.mo.MetadataObservationDocumentError):
            self.observe(NoGetObjectDocument(), _verification([_request()]))

    def test_non_callable_get_object_raises_document_error(self):
        with self.assertRaises(self.mo.MetadataObservationDocumentError):
            self.observe(NonCallableGetObjectDocument(), _verification([_request()]))

    def test_get_object_raises_converted_to_document_error(self):
        document = FakeDocument(exc=RuntimeError("document failure"))
        with self.assertRaises(self.mo.MetadataObservationDocumentError) as cm:
            self.observe(document, _verification([_request()]))
        self.assertIsInstance(cm.exception.__cause__, RuntimeError)

    def test_get_object_returns_none_raises_owner_not_found_error(self):
        document = FakeDocument({})
        with self.assertRaises(self.mo.MetadataObservationOwnerNotFoundError):
            self.observe(document, _verification([_request()]))

    def test_owner_resolution_uses_exact_owner_id(self):
        owner = FakeOwner(Title="x")
        document = FakeDocument({"ExactId": owner})
        data = _verification([_request("m.title", "Title", "ExactId")])

        result = self.observe(document, data)

        self.assertEqual(document.calls, ["ExactId"])
        self.assertEqual(result[0]["value"], "x")

    def test_no_label_lookup_attempted(self):
        owner = FakeOwner(Title="x")
        document = FakeDocument({"ExactId": owner})
        data = _verification([_request("m.title", "Title", "ExactId")])
        self.observe(document, data)

    def test_objects_attribute_not_inspected_as_fallback(self):
        owner = FakeOwner(Title="y")
        document = FakeDocument({"RealId": owner})
        data = _verification([_request("m.title", "Title", "RealId")])
        self.observe(document, data)

    def test_label_match_does_not_satisfy_owner_id_lookup(self):
        class LabeledOwner:
            Label = "Part001"
            Title = "sneaky"

        class DocumentWithLabelOnly:
            @property
            def Objects(self):
                raise AssertionError("Objects must not be accessed")

            def getObject(self, name):
                return None

        with self.assertRaises(self.mo.MetadataObservationOwnerNotFoundError):
            self.observe(DocumentWithLabelOnly(), _verification([_request()]))


# ---------------------------------------------------------------------------
# Section 9 - Property read failures and exact key behavior
# ---------------------------------------------------------------------------


class TestPropertyReadFailures(_MetadataObservationTestCase):
    def test_missing_attribute_raises_property_error(self):
        document = FakeDocument({"Obj": FakeOwner(Other=1)})
        with self.assertRaises(self.mo.MetadataObservationPropertyError):
            self.observe(document, _verification([_request("m.x", "Missing", "Obj")]))

    def test_property_getter_exception_converted_to_property_error(self):
        document = FakeDocument({"Obj": RaisingOwner()})
        with self.assertRaises(self.mo.MetadataObservationPropertyError) as cm:
            self.observe(document, _verification([_request("m.x", "Title", "Obj")]))
        self.assertIsInstance(cm.exception.__cause__, RuntimeError)

    def test_exact_key_no_case_normalization(self):
        owner = FakeOwner(Material="steel")
        document = FakeDocument({"Obj": owner})
        with self.assertRaises(self.mo.MetadataObservationPropertyError):
            self.observe(document, _verification([_request("m.mat", "material", "Obj")]))

    def test_exact_key_no_trimming(self):
        owner = FakeOwner(Title="x")
        document = FakeDocument({"Obj": owner})
        with self.assertRaises(self.mo.MetadataObservationPropertyError):
            self.observe(document, _verification([_request("m.title", " Title ", "Obj")]))

    def test_exact_key_matches_correct_attribute(self):
        owner = FakeOwner(**{"Material": "steel", "material": "plastic"})
        document = FakeDocument({"Obj": owner})
        data = _verification([_request("m.mat", "Material", "Obj")])
        result = self.observe(document, data)
        self.assertEqual(result[0]["value"], "steel")


# ---------------------------------------------------------------------------
# Section 10 - Determinism and non-mutation
# ---------------------------------------------------------------------------


class TestDeterminismAndNonMutation(_MetadataObservationTestCase):
    def test_identical_calls_produce_equal_results(self):
        owner = FakeOwner(Title="bracket")
        document = FakeDocument({"Part001": owner})
        data = _verification([_request()])

        result_a = self.observe(document, data)
        result_b = self.observe(document, data)

        self.assertEqual(result_a, result_b)

    def test_request_order_is_stable(self):
        owner_a = FakeOwner(X=1)
        owner_b = FakeOwner(Y=2)
        owner_c = FakeOwner(Z=3)
        document = FakeDocument({"A": owner_a, "B": owner_b, "C": owner_c})
        data = _verification([
            _request("m.x", "X", "A"),
            _request("m.y", "Y", "B"),
            _request("m.z", "Z", "C"),
        ])

        result = self.observe(document, data)

        self.assertEqual([r["id"] for r in result], ["m.x", "m.y", "m.z"])
        self.assertEqual(document.calls, ["A", "B", "C"])

    def test_verification_data_not_mutated_on_success(self):
        owner = FakeOwner(Title="x")
        document = FakeDocument({"Part001": owner})
        data = _verification([_request()])
        before = copy.deepcopy(data)

        self.observe(document, data)

        self.assertEqual(data, before)

    def test_verification_data_not_mutated_on_failure(self):
        data = _verification([_request()])
        before = copy.deepcopy(data)

        with self.assertRaises(self.mo.MetadataObservationOwnerNotFoundError):
            self.observe(FakeDocument({}), data)

        self.assertEqual(data, before)

    def test_owner_attribute_value_not_mutated(self):
        owner = FakeOwner(Title="bracket")
        document = FakeDocument({"Part001": owner})
        data = _verification([_request()])

        self.observe(document, data)

        self.assertEqual(object.__getattribute__(owner, "Title"), "bracket")

    def test_no_files_written(self):
        owner = FakeOwner(Title="x")
        document = FakeDocument({"Part001": owner})
        data = _verification([_request()])
        with mock.patch("builtins.open", side_effect=AssertionError("must not open files")):
            self.observe(document, data)

    def test_helper_does_not_print_on_success_or_handled_failure(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        owner = FakeOwner(Title="x")
        document = FakeDocument({"Part001": owner})

        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.observe(document, _verification([_request()]))
            with self.assertRaises(self.mo.MetadataObservationOwnerNotFoundError):
                self.observe(FakeDocument({}), _verification([_request()]))

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
