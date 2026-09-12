"""Tests for requested reference observation under ordinary Python."""

from __future__ import annotations

import copy
import importlib
import io
import sys
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock


MODULE_NAME = "parametron_freecad.observation.reference_observation"
EXPECTED_OBSERVED_FIELDS = ("kind", "name")


def _import_module():
    return importlib.import_module(MODULE_NAME)


def _verification(requests, enabled=True):
    """Build a minimal verification_data dict with expected.references."""
    return {
        "observe": {"references": enabled},
        "expected": {"references": requests},
    }


def _request(kind="constraint", name="Sketch001"):
    """Build a minimal reference request entry."""
    return {"kind": kind, "name": name}


class FakeObject:
    """Minimal fake document object."""
    pass


class FakeDocument:
    """Fake FreeCAD document that tracks getObject calls and blocks Label/Objects access."""

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


class FailingDocument:
    """Document that asserts if getObject is called — used for disabled-observation tests."""

    def getObject(self, name):
        raise AssertionError("getObject must not be called when observation is disabled")


# ---------------------------------------------------------------------------
# Section 1 — Import safety and public API
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

    def test_observe_requested_references_is_callable(self):
        from parametron_freecad.observation.reference_observation import (
            observe_requested_references,
        )
        self.assertTrue(callable(observe_requested_references))

    def test_all_typed_errors_are_exposed(self):
        from parametron_freecad.observation.reference_observation import (
            ReferenceObservationDocumentError,
            ReferenceObservationError,
            ReferenceObservationReferenceNotFoundError,
            ReferenceObservationRequestError,
        )
        for cls in (
            ReferenceObservationDocumentError,
            ReferenceObservationReferenceNotFoundError,
            ReferenceObservationRequestError,
        ):
            with self.subTest(cls=cls.__name__):
                self.assertTrue(issubclass(cls, ReferenceObservationError), cls.__name__)

    def test_base_error_inherits_from_value_error(self):
        from parametron_freecad.observation.reference_observation import ReferenceObservationError
        self.assertTrue(issubclass(ReferenceObservationError, ValueError))

    def test_public_error_hierarchy(self):
        from parametron_freecad.observation.reference_observation import (
            ReferenceObservationDocumentError,
            ReferenceObservationError,
            ReferenceObservationReferenceNotFoundError,
            ReferenceObservationRequestError,
        )
        self.assertTrue(issubclass(ReferenceObservationRequestError, ReferenceObservationError))
        self.assertTrue(issubclass(ReferenceObservationDocumentError, ReferenceObservationError))
        self.assertTrue(issubclass(ReferenceObservationReferenceNotFoundError, ReferenceObservationError))


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _ReferenceObservationTestCase(unittest.TestCase):
    def setUp(self):
        self.ro = _import_module()

    def observe(self, document, verification_data):
        return self.ro.observe_requested_references(document, verification_data)

    def assertRequestError(self, verification_data):
        with self.assertRaises(self.ro.ReferenceObservationRequestError) as cm:
            self.observe(FakeDocument(), verification_data)
        self.assertTrue(str(cm.exception))


# ---------------------------------------------------------------------------
# Section 2 — Disabled or absent reference observation
# ---------------------------------------------------------------------------


class TestDisabledReferenceObservation(_ReferenceObservationTestCase):
    def test_missing_observe_returns_empty_tuple(self):
        self.assertEqual(self.observe(FailingDocument(), {}), ())

    def test_missing_observe_references_returns_empty_tuple(self):
        self.assertEqual(self.observe(FailingDocument(), {"observe": {}}), ())

    def test_false_observe_references_returns_empty_tuple(self):
        data = {"observe": {"references": False}}
        self.assertEqual(self.observe(FailingDocument(), data), ())

    def test_none_observe_references_returns_empty_tuple(self):
        data = {"observe": {"references": None}}
        self.assertEqual(self.observe(FailingDocument(), data), ())

    def test_zero_observe_references_returns_empty_tuple(self):
        data = {"observe": {"references": 0}}
        self.assertEqual(self.observe(FailingDocument(), data), ())

    def test_empty_string_observe_references_returns_empty_tuple(self):
        data = {"observe": {"references": ""}}
        self.assertEqual(self.observe(FailingDocument(), data), ())

    def test_disabled_does_not_call_get_object(self):
        for data in (
            {},
            {"observe": {}},
            {"observe": {"references": False}},
            {"observe": {"references": None}},
        ):
            with self.subTest(data=data):
                self.assertEqual(self.observe(FailingDocument(), data), ())

    def test_disabled_ignores_malformed_expected(self):
        for data in (
            {"observe": {"references": False}},
            {"observe": {"references": False}, "expected": None},
            {"observe": {"references": False}, "expected": {"references": "bad"}},
            {"observe": {"references": False}, "expected": {"references": 42}},
        ):
            with self.subTest(data=data):
                self.assertEqual(self.observe(FailingDocument(), data), ())


# ---------------------------------------------------------------------------
# Section 3 — Reads requests from expected.references only
# ---------------------------------------------------------------------------


class TestRequestSourceConstraint(_ReferenceObservationTestCase):
    def test_requests_come_from_expected_references_not_observation_context(self):
        obj = FakeObject()
        document = FakeDocument({"Sketch001": obj})
        data = {
            "observe": {"references": True},
            "expected": {"references": [_request("constraint", "Sketch001")]},
            "observationContext": {"references": [{"kind": "ignored", "name": "OtherObj"}]},
        }

        result = self.observe(document, data)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Sketch001")
        self.assertEqual(document.calls, ["Sketch001"])

    def test_observation_context_references_alone_raises_request_error(self):
        data = {
            "observe": {"references": True},
            "observationContext": {"references": [_request()]},
        }
        with self.assertRaises(self.ro.ReferenceObservationRequestError):
            self.observe(FakeDocument(), data)

    def test_conflicting_observation_context_references_are_ignored(self):
        obj_a = FakeObject()
        document = FakeDocument({"ObjA": obj_a})
        data = {
            "observe": {"references": True},
            "expected": {"references": [_request("part", "ObjA")]},
            "observationContext": {"references": [
                {"kind": "assembly", "name": "ObjDecoy"},
            ]},
        }

        result = self.observe(document, data)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "ObjA")
        self.assertEqual(document.calls, ["ObjA"])


# ---------------------------------------------------------------------------
# Section 4 — Successful observation output
# ---------------------------------------------------------------------------


class TestSuccessfulObservation(_ReferenceObservationTestCase):
    def test_return_type_is_tuple(self):
        obj = FakeObject()
        document = FakeDocument({"Sketch001": obj})
        result = self.observe(document, _verification([_request()]))
        self.assertIsInstance(result, tuple)

    def test_output_order_matches_request_order(self):
        obj_a = FakeObject()
        obj_b = FakeObject()
        document = FakeDocument({"PartA": obj_a, "PartB": obj_b})
        data = _verification([
            _request("part", "PartA"),
            _request("assembly", "PartB"),
        ])

        result = self.observe(document, data)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "PartA")
        self.assertEqual(result[1]["name"], "PartB")

    def test_each_entry_has_exactly_kind_and_name(self):
        obj = FakeObject()
        document = FakeDocument({"Sketch001": obj})
        result = self.observe(document, _verification([_request()]))
        self.assertEqual(tuple(result[0].keys()), EXPECTED_OBSERVED_FIELDS)

    def test_kind_and_name_copied_exactly_from_request(self):
        obj = FakeObject()
        document = FakeDocument({"Sketch001": obj})
        result = self.observe(document, _verification([_request("constraint", "Sketch001")]))
        self.assertEqual(result[0]["kind"], "constraint")
        self.assertEqual(result[0]["name"], "Sketch001")

    def test_multiple_references_in_order_full_content(self):
        obj_a = FakeObject()
        obj_b = FakeObject()
        obj_c = FakeObject()
        document = FakeDocument({
            "Sketch001": obj_a,
            "Body001": obj_b,
            "Part001": obj_c,
        })
        data = _verification([
            _request("constraint", "Sketch001"),
            _request("body", "Body001"),
            _request("part", "Part001"),
        ])

        result = self.observe(document, data)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        self.assertEqual(
            result,
            (
                {"kind": "constraint", "name": "Sketch001"},
                {"kind": "body", "name": "Body001"},
                {"kind": "part", "name": "Part001"},
            ),
        )
        self.assertEqual(document.calls, ["Sketch001", "Body001", "Part001"])

    def test_unusual_kind_is_copied_unchanged(self):
        """kind is not validated, normalized, or inferred."""
        obj = FakeObject()
        document = FakeDocument({"Obj": obj})
        data = _verification([_request("some-unusual-kind/with/slashes", "Obj")])

        result = self.observe(document, data)

        self.assertEqual(result[0]["kind"], "some-unusual-kind/with/slashes")

    def test_whitespace_name_passed_exactly_to_get_object(self):
        """name is not trimmed or otherwise changed."""
        obj = FakeObject()
        document = FakeDocument({" Sketch001 ": obj})
        data = _verification([_request("constraint", " Sketch001 ")])

        result = self.observe(document, data)

        self.assertEqual(result[0]["name"], " Sketch001 ")
        self.assertEqual(document.calls, [" Sketch001 "])

    def test_case_sensitive_name_passed_exactly_to_get_object(self):
        obj_lower = FakeObject()
        document = FakeDocument({"sketch001": obj_lower})
        data = _verification([_request("constraint", "sketch001")])

        result = self.observe(document, data)

        self.assertEqual(result[0]["name"], "sketch001")
        self.assertEqual(document.calls, ["sketch001"])


# ---------------------------------------------------------------------------
# Section 5 — Resolution policy: getObject only, no fallbacks
# ---------------------------------------------------------------------------


class TestResolutionPolicy(_ReferenceObservationTestCase):
    def test_get_object_is_called_with_exact_name(self):
        obj = FakeObject()
        document = FakeDocument({"ExactName": obj})
        self.observe(document, _verification([_request("part", "ExactName")]))
        self.assertEqual(document.calls, ["ExactName"])

    def test_objects_in_document_objects_but_get_object_returns_none_raises_not_found(self):
        """document.Objects is not used as fallback when getObject returns None."""

        class DocumentWithObjectsButGetObjectReturnsNone:
            @property
            def Objects(self):
                obj = FakeObject()
                return [obj]

            def getObject(self, name):
                return None

        with self.assertRaises(self.ro.ReferenceObservationReferenceNotFoundError):
            self.observe(
                DocumentWithObjectsButGetObjectReturnsNone(),
                _verification([_request("constraint", "Sketch001")]),
            )

    def test_label_match_does_not_satisfy_name_lookup(self):
        """An object with a matching Label but getObject returns None still raises not found."""

        class LabelOnlyDocument:
            @property
            def Objects(self):
                raise AssertionError("Objects must not be accessed")

            def getObject(self, name):
                return None

        with self.assertRaises(self.ro.ReferenceObservationReferenceNotFoundError):
            self.observe(
                LabelOnlyDocument(),
                _verification([_request("constraint", "Sketch001")]),
            )

    def test_exact_names_recorded_in_get_object_calls(self):
        obj_a = FakeObject()
        obj_b = FakeObject()
        document = FakeDocument({"Alpha": obj_a, "Beta": obj_b})
        data = _verification([
            _request("part", "Alpha"),
            _request("body", "Beta"),
        ])

        self.observe(document, data)

        self.assertEqual(document.calls, ["Alpha", "Beta"])


# ---------------------------------------------------------------------------
# Section 6 — Request validation failures
# ---------------------------------------------------------------------------


class TestRequestValidationErrors(_ReferenceObservationTestCase):
    def test_verification_data_not_a_mapping_raises_request_error(self):
        for value in (None, 42, "string", [], True):
            with self.subTest(value=value):
                with self.assertRaises(self.ro.ReferenceObservationRequestError):
                    self.ro.observe_requested_references(FakeDocument(), value)

    def test_observe_not_a_mapping_raises_request_error(self):
        for value in (None, "string", 42, True, []):
            with self.subTest(value=value):
                self.assertRequestError({"observe": value, "expected": {"references": [_request()]}})

    def test_missing_expected_raises_request_error(self):
        self.assertRequestError({"observe": {"references": True}})

    def test_non_mapping_expected_raises_request_error(self):
        for value in (None, [], "string", 42):
            with self.subTest(value=value):
                self.assertRequestError({"observe": {"references": True}, "expected": value})

    def test_missing_expected_references_raises_request_error(self):
        self.assertRequestError({"observe": {"references": True}, "expected": {}})

    def test_non_iterable_expected_references_raises_request_error(self):
        self.assertRequestError({"observe": {"references": True}, "expected": {"references": 7}})

    def test_string_expected_references_raises_request_error(self):
        self.assertRequestError({"observe": {"references": True}, "expected": {"references": "abc"}})

    def test_bytes_expected_references_raises_request_error(self):
        self.assertRequestError({"observe": {"references": True}, "expected": {"references": b"abc"}})

    def test_entry_not_mapping_raises_request_error(self):
        self.assertRequestError(_verification(["not a mapping"]))

    def test_missing_kind_raises_request_error(self):
        self.assertRequestError(_verification([{"name": "Sketch001"}]))

    def test_missing_name_raises_request_error(self):
        self.assertRequestError(_verification([{"kind": "constraint"}]))

    def test_non_string_kind_raises_request_error(self):
        for value in (None, 42, True, [], {}):
            with self.subTest(value=value):
                self.assertRequestError(_verification([{"kind": value, "name": "Sketch001"}]))

    def test_non_string_name_raises_request_error(self):
        for value in (None, 42, True, [], {}):
            with self.subTest(value=value):
                self.assertRequestError(_verification([{"kind": "constraint", "name": value}]))

    def test_request_errors_are_subclasses_of_reference_observation_error(self):
        self.assertTrue(issubclass(
            self.ro.ReferenceObservationRequestError,
            self.ro.ReferenceObservationError,
        ))


# ---------------------------------------------------------------------------
# Section 7 — Document access failures
# ---------------------------------------------------------------------------


class TestDocumentAccessErrors(_ReferenceObservationTestCase):
    def test_missing_get_object_raises_document_error(self):
        with self.assertRaises(self.ro.ReferenceObservationDocumentError):
            self.observe(DocumentWithoutGetObject(), _verification([_request()]))

    def test_non_callable_get_object_raises_document_error(self):
        with self.assertRaises(self.ro.ReferenceObservationDocumentError):
            self.observe(DocumentWithNonCallableGetObject(), _verification([_request()]))

    def test_get_object_raises_converted_to_document_error(self):
        document = FakeDocument(exc=RuntimeError("document failure"))
        with self.assertRaises(self.ro.ReferenceObservationDocumentError) as cm:
            self.observe(document, _verification([_request()]))
        self.assertIsInstance(cm.exception.__cause__, RuntimeError)

    def test_document_errors_are_subclasses_of_reference_observation_error(self):
        self.assertTrue(issubclass(
            self.ro.ReferenceObservationDocumentError,
            self.ro.ReferenceObservationError,
        ))

    def test_document_error_message_is_non_empty(self):
        try:
            self.observe(DocumentWithoutGetObject(), _verification([_request()]))
        except self.ro.ReferenceObservationDocumentError as exc:
            self.assertTrue(str(exc))
        else:
            self.fail("Expected ReferenceObservationDocumentError")


# ---------------------------------------------------------------------------
# Section 8 — Missing reference failures
# ---------------------------------------------------------------------------


class TestMissingReferenceErrors(_ReferenceObservationTestCase):
    def test_get_object_none_raises_not_found_error(self):
        document = FakeDocument({})
        with self.assertRaises(self.ro.ReferenceObservationReferenceNotFoundError):
            self.observe(document, _verification([_request()]))

    def test_not_found_error_is_subclass_of_reference_observation_error(self):
        self.assertTrue(issubclass(
            self.ro.ReferenceObservationReferenceNotFoundError,
            self.ro.ReferenceObservationError,
        ))

    def test_not_found_error_message_contains_name(self):
        document = FakeDocument({})
        try:
            self.observe(document, _verification([_request("constraint", "Sketch001")]))
        except self.ro.ReferenceObservationReferenceNotFoundError as exc:
            self.assertIn("Sketch001", str(exc))
        else:
            self.fail("Expected ReferenceObservationReferenceNotFoundError")

    def test_not_found_error_message_is_non_empty(self):
        document = FakeDocument({})
        try:
            self.observe(document, _verification([_request()]))
        except self.ro.ReferenceObservationReferenceNotFoundError as exc:
            self.assertTrue(str(exc))
        else:
            self.fail("Expected ReferenceObservationReferenceNotFoundError")


# ---------------------------------------------------------------------------
# Section 9 — No side effects
# ---------------------------------------------------------------------------


class TestNoSideEffects(_ReferenceObservationTestCase):
    def test_success_does_not_mutate_verification_data(self):
        obj = FakeObject()
        document = FakeDocument({"Sketch001": obj})
        data = _verification([_request()])
        before = copy.deepcopy(data)

        self.observe(document, data)

        self.assertEqual(data, before)

    def test_failure_does_not_mutate_verification_data(self):
        data = _verification([_request()])
        before = copy.deepcopy(data)

        with self.assertRaises(self.ro.ReferenceObservationReferenceNotFoundError):
            self.observe(FakeDocument({}), data)

        self.assertEqual(data, before)

    def test_helper_does_not_write_files(self):
        obj = FakeObject()
        document = FakeDocument({"Sketch001": obj})
        data = _verification([_request()])
        with mock.patch("builtins.open", side_effect=AssertionError("must not open files")):
            self.observe(document, data)

    def test_helper_does_not_print_on_success_or_handled_failure(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        obj = FakeObject()
        document = FakeDocument({"Sketch001": obj})

        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.observe(document, _verification([_request()]))
            with self.assertRaises(self.ro.ReferenceObservationReferenceNotFoundError):
                self.observe(FakeDocument({}), _verification([_request()]))

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_helper_only_calls_get_object_on_document(self):
        """No document method other than getObject is called."""

        class StrictDocument:
            def __init__(self):
                self.calls = []

            def getObject(self, name):
                self.calls.append(("getObject", name))
                return FakeObject()

            def __getattr__(self, name):
                raise AssertionError(f"unexpected document method call: {name!r}")

        document = StrictDocument()
        self.observe(document, _verification([_request("part", "Sketch001")]))

        self.assertEqual(document.calls, [("getObject", "Sketch001")])


# ---------------------------------------------------------------------------
# Section 10 — Determinism
# ---------------------------------------------------------------------------


class TestDeterminism(_ReferenceObservationTestCase):
    def test_identical_calls_produce_equal_results(self):
        obj = FakeObject()
        document = FakeDocument({"Sketch001": obj})
        data = _verification([_request()])

        result_a = self.observe(document, data)
        result_b = self.observe(document, data)

        self.assertEqual(result_a, result_b)

    def test_error_messages_are_non_empty(self):
        failures = (
            lambda: self.observe(DocumentWithoutGetObject(), _verification([_request()])),
            lambda: self.observe(FakeDocument({}), _verification([_request()])),
        )
        for failure in failures:
            with self.subTest(failure=failure):
                try:
                    failure()
                except self.ro.ReferenceObservationError as exc:
                    self.assertTrue(str(exc))
                else:
                    self.fail("Expected ReferenceObservationError")

    def test_request_order_is_stable(self):
        obj_a = FakeObject()
        obj_b = FakeObject()
        obj_c = FakeObject()
        document = FakeDocument({"A": obj_a, "B": obj_b, "C": obj_c})
        data = _verification([
            _request("part", "A"),
            _request("assembly", "B"),
            _request("constraint", "C"),
        ])

        result = self.observe(document, data)

        self.assertEqual([r["name"] for r in result], ["A", "B", "C"])
        self.assertEqual(document.calls, ["A", "B", "C"])


# ---------------------------------------------------------------------------
# Section 11 — Shared runtime helper delegation and error non-leakage
# ---------------------------------------------------------------------------


class TestSharedReferenceAccessDelegation(_ReferenceObservationTestCase):
    """Regression coverage proving the shared runtime helper is used without
    leaking its typed errors through the public observation API."""

    def setUp(self):
        super().setUp()
        self.ra = importlib.import_module(
            "parametron_freecad.runtime.reference_access"
        )

    def test_reference_access_errors_are_not_observation_errors(self):
        """The runtime helper error family is distinct from the public one."""
        self.assertFalse(
            issubclass(self.ra.ReferenceAccessError, self.ro.ReferenceObservationError)
        )

    def test_missing_get_object_does_not_leak_reference_access_error(self):
        with self.assertRaises(self.ro.ReferenceObservationDocumentError) as cm:
            self.observe(DocumentWithoutGetObject(), _verification([_request()]))
        self.assertNotIsInstance(cm.exception, self.ra.ReferenceAccessError)
        self.assertTrue(str(cm.exception))

    def test_non_callable_get_object_does_not_leak_reference_access_error(self):
        with self.assertRaises(self.ro.ReferenceObservationDocumentError) as cm:
            self.observe(
                DocumentWithNonCallableGetObject(),
                _verification([_request()]),
            )
        self.assertNotIsInstance(cm.exception, self.ra.ReferenceAccessError)

    def test_raising_get_object_does_not_leak_reference_access_error(self):
        original = RuntimeError("boom")
        document = FakeDocument(exc=original)
        with self.assertRaises(self.ro.ReferenceObservationDocumentError) as cm:
            self.observe(document, _verification([_request()]))
        self.assertNotIsInstance(cm.exception, self.ra.ReferenceAccessError)
        self.assertIs(cm.exception.__cause__, original)

    def test_missing_reference_does_not_leak_reference_access_error(self):
        with self.assertRaises(
            self.ro.ReferenceObservationReferenceNotFoundError
        ) as cm:
            self.observe(FakeDocument({}), _verification([_request()]))
        self.assertNotIsInstance(cm.exception, self.ra.ReferenceAccessError)

    def test_delegation_resolves_via_shared_helper(self):
        obj = FakeObject()
        document = FakeDocument({"Sketch001": obj})
        with mock.patch.object(
            self.ro,
            "resolve_reference_object",
            wraps=self.ro.resolve_reference_object,
        ) as spy:
            self.observe(document, _verification([_request("part", "Sketch001")]))
        spy.assert_called_once_with(document, "Sketch001")


if __name__ == "__main__":
    unittest.main()
