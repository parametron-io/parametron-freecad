"""Tests for requested parameter observation under ordinary Python."""

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


MODULE_NAME = "parametron_freecad.observation.parameter_observation"
EXPECTED_OBSERVED_FIELDS = ("id", "name", "groupId", "value", "valueKind")


def _import_module():
    return importlib.import_module(MODULE_NAME)


def _verification(bindings, enabled=True):
    return {
        "observe": {"parameters": enabled},
        "observationContext": {"parameters": bindings},
    }


def _binding(param_id="p.length", name="Length", group_name="Spreadsheet"):
    return {"id": param_id, "name": name, "groupName": group_name}


class FakeObject:
    def __init__(self, **properties):
        object.__setattr__(self, "read_names", [])
        for name, value in properties.items():
            object.__setattr__(self, name, value)

    def __getattribute__(self, name):
        if not name.startswith("_") and name != "read_names":
            object.__getattribute__(self, "read_names").append(name)
        return object.__getattribute__(self, name)


class RaisingObject:
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


class DocumentWithoutGetObject:
    pass


class DocumentWithNonCallableGetObject:
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

    def test_public_names_can_be_imported(self):
        from parametron_freecad.observation.parameter_observation import (
            ParameterObservationDocumentError,
            ParameterObservationError,
            ParameterObservationObjectNotFoundError,
            ParameterObservationPropertyError,
            ParameterObservationRequestError,
            ParameterObservationValueError,
            observe_requested_parameters,
        )

        self.assertTrue(issubclass(ParameterObservationDocumentError, ParameterObservationError))
        self.assertTrue(issubclass(ParameterObservationObjectNotFoundError, ParameterObservationError))
        self.assertTrue(issubclass(ParameterObservationPropertyError, ParameterObservationError))
        self.assertTrue(issubclass(ParameterObservationRequestError, ParameterObservationError))
        self.assertTrue(issubclass(ParameterObservationValueError, ParameterObservationError))
        self.assertTrue(callable(observe_requested_parameters))


class _ObservationTestCase(unittest.TestCase):
    def setUp(self):
        self.po = _import_module()

    def observe(self, document, verification_data):
        return self.po.observe_requested_parameters(document, verification_data)

    def assertRequestError(self, verification_data):
        with self.assertRaises(self.po.ParameterObservationRequestError) as cm:
            self.observe(FakeDocument(), verification_data)
        self.assertTrue(str(cm.exception))


class TestDisabledParameterObservation(_ObservationTestCase):
    def test_missing_observe_returns_empty_tuple(self):
        self.assertEqual(self.observe(FakeDocument(), {}), ())

    def test_missing_observe_parameters_returns_empty_tuple(self):
        self.assertEqual(self.observe(FakeDocument(), {"observe": {}}), ())

    def test_false_observe_parameters_returns_empty_tuple(self):
        data = {"observe": {"parameters": False}}
        self.assertEqual(self.observe(FakeDocument(), data), ())

    def test_falsy_observe_parameters_return_empty_tuple(self):
        for value in (None, 0, [], {}):
            with self.subTest(value=value):
                data = {"observe": {"parameters": value}}
                self.assertEqual(self.observe(FakeDocument(), data), ())

    def test_disabled_observation_ignores_malformed_observation_context(self):
        malformed_contexts = (
            {},
            {"observationContext": None},
            {"observationContext": {"parameters": "not bindings"}},
            {"observationContext": {"parameters": [{"bad": object()}]}},
        )
        for extra in malformed_contexts:
            with self.subTest(extra=extra):
                data = {"observe": {"parameters": False}, **extra}
                self.assertEqual(self.observe(DocumentWithoutGetObject(), data), ())


class TestEnabledParameterObservation(_ObservationTestCase):
    def test_valid_bindings_return_tuple_in_request_order_with_exact_fields(self):
        first = FakeObject(Length=42)
        second = FakeObject(Name="beam")
        document = FakeDocument({"Spreadsheet": first, "MetaGroup": second})
        data = _verification([
            _binding("p.length", "Length", "Spreadsheet"),
            _binding("p.name", "Name", "MetaGroup"),
        ])

        result = self.observe(document, data)

        self.assertIsInstance(result, tuple)
        self.assertEqual(document.calls, ["Spreadsheet", "MetaGroup"])
        self.assertEqual([tuple(item.keys()) for item in result], [EXPECTED_OBSERVED_FIELDS] * 2)
        self.assertEqual(
            result,
            (
                {
                    "id": "p.length",
                    "name": "Length",
                    "groupId": "Spreadsheet",
                    "value": 42,
                    "valueKind": "integer",
                },
                {
                    "id": "p.name",
                    "name": "Name",
                    "groupId": "MetaGroup",
                    "value": "beam",
                    "valueKind": "string",
                },
            ),
        )

    def test_supported_value_kinds_are_derived_deterministically(self):
        document = FakeDocument({
            "Params": FakeObject(
                IsEnabled=True,
                Count=7,
                Width=3.5,
                Title="bracket",
            )
        })
        data = _verification([
            _binding("p.enabled", "IsEnabled", "Params"),
            _binding("p.count", "Count", "Params"),
            _binding("p.width", "Width", "Params"),
            _binding("p.title", "Title", "Params"),
        ])

        result = self.observe(document, data)

        self.assertEqual([item["valueKind"] for item in result], [
            "boolean",
            "integer",
            "number",
            "string",
        ])
        self.assertIs(result[0]["value"], True)
        self.assertNotEqual(result[0]["valueKind"], "integer")


class TestExactAccessBehavior(_ObservationTestCase):
    def test_get_object_uses_exact_group_names_without_label_or_objects_fallback(self):
        exact = FakeObject(Length=12)
        label_only = FakeObject(Length=99)
        document = FakeDocument({"ExactGroup": exact, "Display Label": label_only})
        data = _verification([_binding("p.length", "Length", "ExactGroup")])

        result = self.observe(document, data)

        self.assertEqual(document.calls, ["ExactGroup"])
        self.assertEqual(result[0]["value"], 12)

    def test_missing_exact_group_does_not_fallback_to_label_like_name(self):
        document = FakeDocument({"Display Label": FakeObject(Length=99)})
        data = _verification([_binding("p.length", "Length", "ExactGroup")])

        with self.assertRaises(self.po.ParameterObservationObjectNotFoundError):
            self.observe(document, data)

        self.assertEqual(document.calls, ["ExactGroup"])

    def test_property_name_is_read_exactly_without_normalization(self):
        obj = FakeObject(Length=10, length=20, **{" Length ": 30})
        document = FakeDocument({"Params": obj})

        result = self.observe(document, _verification([
            _binding("p.spaced", " Length ", "Params"),
            _binding("p.lower", "length", "Params"),
        ]))

        self.assertEqual([item["value"] for item in result], [30, 20])
        self.assertEqual(obj.read_names, [" Length ", "length"])


class TestRequestValidationErrors(_ObservationTestCase):
    def test_missing_observation_context_raises_request_error(self):
        self.assertRequestError({"observe": {"parameters": True}})

    def test_non_mapping_observation_context_raises_request_error(self):
        for value in (None, [], "context"):
            with self.subTest(value=value):
                self.assertRequestError({
                    "observe": {"parameters": True},
                    "observationContext": value,
                })

    def test_missing_parameters_raises_request_error(self):
        self.assertRequestError({
            "observe": {"parameters": True},
            "observationContext": {},
        })

    def test_non_iterable_parameters_raises_request_error(self):
        self.assertRequestError({
            "observe": {"parameters": True},
            "observationContext": {"parameters": 7},
        })

    def test_string_or_bytes_parameters_raise_request_error(self):
        for value in ("abc", b"abc"):
            with self.subTest(value=value):
                self.assertRequestError({
                    "observe": {"parameters": True},
                    "observationContext": {"parameters": value},
                })

    def test_binding_entry_not_mapping_raises_request_error(self):
        self.assertRequestError(_verification(["not a mapping"]))

    def test_missing_binding_fields_raise_request_error(self):
        cases = (
            {"name": "Length", "groupName": "Params"},
            {"id": "p.length", "groupName": "Params"},
            {"id": "p.length", "name": "Length"},
        )
        for binding in cases:
            with self.subTest(binding=binding):
                self.assertRequestError(_verification([binding]))

    def test_non_string_binding_fields_raise_request_error(self):
        cases = (
            {"id": 1, "name": "Length", "groupName": "Params"},
            {"id": "p.length", "name": None, "groupName": "Params"},
            {"id": "p.length", "name": "Length", "groupName": object()},
        )
        for binding in cases:
            with self.subTest(binding=binding):
                self.assertRequestError(_verification([binding]))


class TestDocumentAccessErrors(_ObservationTestCase):
    def test_missing_get_object_raises_document_error(self):
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        with self.assertRaises(self.po.ParameterObservationDocumentError) as cm:
            self.observe(DocumentWithoutGetObject(), _verification([_binding()]))
        self.assertNotIsInstance(cm.exception, ParameterAccessError)
        self.assertIsInstance(cm.exception.__cause__, ParameterAccessError)

    def test_non_callable_get_object_raises_document_error(self):
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        with self.assertRaises(self.po.ParameterObservationDocumentError) as cm:
            self.observe(DocumentWithNonCallableGetObject(), _verification([_binding()]))
        self.assertNotIsInstance(cm.exception, ParameterAccessError)
        self.assertIsInstance(cm.exception.__cause__, ParameterAccessError)

    def test_get_object_exception_is_converted_to_document_error(self):
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        document = FakeDocument(exc=RuntimeError("document failure"))
        with self.assertRaises(self.po.ParameterObservationDocumentError) as cm:
            self.observe(document, _verification([_binding()]))
        self.assertNotIsInstance(cm.exception, ParameterAccessError)
        self.assertIsInstance(cm.exception.__cause__, RuntimeError)

    def test_get_object_none_raises_object_not_found_error(self):
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        document = FakeDocument({})
        with self.assertRaises(self.po.ParameterObservationObjectNotFoundError) as cm:
            self.observe(document, _verification([_binding()]))
        self.assertNotIsInstance(cm.exception, ParameterAccessError)
        self.assertIsInstance(cm.exception.__cause__, ParameterAccessError)


class TestPropertyAndValueErrors(_ObservationTestCase):
    def test_missing_property_raises_property_error(self):
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        document = FakeDocument({"Params": FakeObject(Other=1)})
        with self.assertRaises(self.po.ParameterObservationPropertyError) as cm:
            self.observe(document, _verification([_binding(name="Length", group_name="Params")]))
        self.assertNotIsInstance(cm.exception, ParameterAccessError)
        self.assertIsInstance(cm.exception.__cause__, AttributeError)

    def test_attribute_access_exception_is_converted_to_property_error(self):
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        document = FakeDocument({"Params": RaisingObject()})
        with self.assertRaises(self.po.ParameterObservationPropertyError) as cm:
            self.observe(document, _verification([_binding(name="Length", group_name="Params")]))
        self.assertNotIsInstance(cm.exception, ParameterAccessError)
        self.assertIsInstance(cm.exception.__cause__, RuntimeError)

    def test_unsupported_values_raise_value_error(self):
        for value in (None, [], {}, (), object()):
            with self.subTest(value=type(value).__name__):
                document = FakeDocument({"Params": FakeObject(Value=value)})
                with self.assertRaises(self.po.ParameterObservationValueError):
                    self.observe(document, _verification([_binding(name="Value", group_name="Params")]))

    def test_non_finite_floats_raise_value_error(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                document = FakeDocument({"Params": FakeObject(Value=value)})
                with self.assertRaises(self.po.ParameterObservationValueError):
                    self.observe(document, _verification([_binding(name="Value", group_name="Params")]))


class TestNoMutationAndNoSideEffects(_ObservationTestCase):
    def test_success_does_not_mutate_verification_data_or_objects(self):
        obj = FakeObject(Length=42)
        document = FakeDocument({"Params": obj})
        data = _verification([_binding(group_name="Params")])
        before_data = copy.deepcopy(data)
        before_object_state = dict(obj.__dict__)

        self.observe(document, data)

        self.assertEqual(data, before_data)
        self.assertEqual(obj.__dict__, before_object_state | {"read_names": ["Length"]})
        self.assertEqual(obj.Length, 42)

    def test_failure_does_not_mutate_verification_data(self):
        data = _verification([_binding(group_name="Missing")])
        before = copy.deepcopy(data)

        with self.assertRaises(self.po.ParameterObservationObjectNotFoundError):
            self.observe(FakeDocument({}), data)

        self.assertEqual(data, before)

    def test_helper_does_not_write_files(self):
        document = FakeDocument({"Params": FakeObject(Length=42)})
        data = _verification([_binding(group_name="Params")])
        with mock.patch("builtins.open", side_effect=AssertionError("must not write files")):
            self.observe(document, data)

    def test_helper_does_not_print_on_success_or_handled_failure(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        success_doc = FakeDocument({"Params": FakeObject(Length=42)})

        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.observe(success_doc, _verification([_binding(group_name="Params")]))
            with self.assertRaises(self.po.ParameterObservationObjectNotFoundError):
                self.observe(FakeDocument({}), _verification([_binding(group_name="Missing")]))

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")


class TestDeterministicDiagnostics(_ObservationTestCase):
    def test_error_messages_are_non_empty(self):
        failures = (
            lambda: self.observe(DocumentWithoutGetObject(), _verification([_binding()])),
            lambda: self.observe(FakeDocument({}), _verification([_binding()])),
            lambda: self.observe(FakeDocument({"Params": FakeObject(Value=math.nan)}), _verification([
                _binding(name="Value", group_name="Params")
            ])),
        )

        for failure in failures:
            with self.subTest(failure=failure):
                try:
                    failure()
                except self.po.ParameterObservationError as exc:
                    self.assertTrue(str(exc))
                else:
                    self.fail("Expected ParameterObservationError")

    def test_identical_failures_have_identical_messages(self):
        def message():
            try:
                self.observe(FakeDocument({}), _verification([_binding(group_name="Missing")]))
            except self.po.ParameterObservationObjectNotFoundError as exc:
                return str(exc)
            self.fail("Expected object not found error")

        self.assertEqual(message(), message())


if __name__ == "__main__":
    unittest.main()
