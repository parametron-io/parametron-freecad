"""Unit tests for parametron_freecad.execution.parameter_assignment."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any


def _make_assignment(
    target: str,
    value: Any,
    value_kind: str = "scalar",
) -> dict[str, Any]:
    """Build a minimal valid assignment dict for testing."""
    return {"target": target, "value": value, "valueKind": value_kind}


class _FakeDocument:
    """Fake FreeCAD document that resolves objects from a pre-populated dict."""

    def __init__(self) -> None:
        self._objects: dict[str, Any] = {}

    def getObject(self, name: str) -> Any:
        return self._objects.get(name)


class PublicApiTests(unittest.TestCase):
    def test_apply_parameter_assignments_is_exported(self) -> None:
        from parametron_freecad.execution import parameter_assignment
        self.assertIn("apply_parameter_assignments", parameter_assignment.__all__)

    def test_error_classes_are_exported(self) -> None:
        from parametron_freecad.execution import parameter_assignment
        for name in [
            "ParameterAssignmentError",
            "ParameterObjectNotFoundError",
            "ParameterPropertyAssignmentError",
            "ParameterTargetError",
        ]:
            with self.subTest(name=name):
                self.assertIn(name, parameter_assignment.__all__)

    def test_error_hierarchy(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterAssignmentError,
            ParameterObjectNotFoundError,
            ParameterPropertyAssignmentError,
            ParameterTargetError,
        )
        self.assertTrue(issubclass(ParameterAssignmentError, ValueError))
        self.assertTrue(issubclass(ParameterTargetError, ParameterAssignmentError))
        self.assertTrue(issubclass(ParameterObjectNotFoundError, ParameterAssignmentError))
        self.assertTrue(issubclass(ParameterPropertyAssignmentError, ParameterAssignmentError))

    def test_import_does_not_require_freecad(self) -> None:
        import sys
        sys.modules.pop("parametron_freecad.execution.parameter_assignment", None)
        import parametron_freecad.execution.parameter_assignment  # noqa: F401
        self.assertNotIn("FreeCAD", sys.modules)


class SuccessfulAssignmentTests(unittest.TestCase):
    def test_single_assignment_applies_value(self) -> None:
        from parametron_freecad.execution.parameter_assignment import apply_parameter_assignments

        doc = _FakeDocument()
        obj = SimpleNamespace()
        doc._objects["Box"] = obj

        apply_parameter_assignments(doc, [_make_assignment("Box.Length", 100.0)])

        self.assertEqual(obj.Length, 100.0)

    def test_assignments_to_different_objects_both_applied(self) -> None:
        from parametron_freecad.execution.parameter_assignment import apply_parameter_assignments

        doc = _FakeDocument()
        box = SimpleNamespace()
        sphere = SimpleNamespace()
        doc._objects["Box"] = box
        doc._objects["Sphere"] = sphere

        apply_parameter_assignments(doc, [
            _make_assignment("Box.Length", 10.0),
            _make_assignment("Sphere.Radius", 5.0),
        ])

        self.assertEqual(box.Length, 10.0)
        self.assertEqual(sphere.Radius, 5.0)

    def test_empty_assignments_succeeds(self) -> None:
        from parametron_freecad.execution.parameter_assignment import apply_parameter_assignments

        apply_parameter_assignments(_FakeDocument(), [])

    def test_empty_assignments_does_not_call_get_object(self) -> None:
        from parametron_freecad.execution.parameter_assignment import apply_parameter_assignments

        calls: list[str] = []

        class RecordingDoc:
            def getObject(self, name: str) -> None:
                calls.append(name)
                return None

        apply_parameter_assignments(RecordingDoc(), [])

        self.assertEqual(calls, [])


class ManifestOrderTests(unittest.TestCase):
    def test_multiple_assignments_to_same_object_applied_in_manifest_order(self) -> None:
        from parametron_freecad.execution.parameter_assignment import apply_parameter_assignments

        order: list[str] = []

        class RecordingObject:
            def __setattr__(self, name: str, value: object) -> None:
                order.append(name)
                object.__setattr__(self, name, value)

        doc = _FakeDocument()
        doc._objects["Box"] = RecordingObject()

        apply_parameter_assignments(doc, [
            _make_assignment("Box.Length", 10.0),
            _make_assignment("Box.Width", 20.0),
            _make_assignment("Box.Height", 30.0),
        ])

        self.assertEqual(order, ["Length", "Width", "Height"])

    def test_assignments_across_objects_applied_in_manifest_order(self) -> None:
        from parametron_freecad.execution.parameter_assignment import apply_parameter_assignments

        order: list[tuple[str, str]] = []

        class RecordingDoc:
            def __init__(self) -> None:
                self._objects: dict[str, Any] = {}

            def getObject(self, name: str) -> Any:
                return self._objects.get(name)

        class RecordingObject:
            def __init__(self, tag: str) -> None:
                object.__setattr__(self, "_tag", tag)

            def __setattr__(self, name: str, value: object) -> None:
                if not name.startswith("_"):
                    order.append((object.__getattribute__(self, "_tag"), name))
                object.__setattr__(self, name, value)

        doc = RecordingDoc()
        doc._objects["A"] = RecordingObject("A")
        doc._objects["B"] = RecordingObject("B")

        apply_parameter_assignments(doc, [
            _make_assignment("A.X", 1),
            _make_assignment("B.Y", 2),
            _make_assignment("A.Z", 3),
        ])

        self.assertEqual(order, [("A", "X"), ("B", "Y"), ("A", "Z")])


class ScalarPassThroughTests(unittest.TestCase):
    def _apply_single(self, target: str, value: Any) -> Any:
        from parametron_freecad.execution.parameter_assignment import apply_parameter_assignments

        doc = _FakeDocument()
        obj = SimpleNamespace()
        object_name, prop_name = target.split(".", 1)
        doc._objects[object_name] = obj

        apply_parameter_assignments(doc, [_make_assignment(target, value)])

        return getattr(obj, prop_name)

    def test_string_assigned_exactly(self) -> None:
        result = self._apply_single("Part.Label", "hello")
        self.assertEqual(result, "hello")
        self.assertIsInstance(result, str)

    def test_int_assigned_exactly(self) -> None:
        result = self._apply_single("Part.Count", 42)
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)

    def test_float_assigned_exactly(self) -> None:
        result = self._apply_single("Part.Size", 3.14)
        self.assertAlmostEqual(result, 3.14)
        self.assertIsInstance(result, float)

    def test_bool_true_assigned_exactly(self) -> None:
        result = self._apply_single("Part.Visible", True)
        self.assertIs(result, True)

    def test_bool_false_assigned_exactly(self) -> None:
        result = self._apply_single("Part.Hidden", False)
        self.assertIs(result, False)

    def test_none_assigned_exactly(self) -> None:
        result = self._apply_single("Part.Ref", None)
        self.assertIsNone(result)

    def test_value_kind_field_is_not_interpreted(self) -> None:
        from parametron_freecad.execution.parameter_assignment import apply_parameter_assignments

        unusual_kinds = ("expression", "alias", "spreadsheet", "constraint", "unknown")

        for kind in unusual_kinds:
            with self.subTest(kind=kind):
                doc = _FakeDocument()
                obj = SimpleNamespace()
                doc._objects["Box"] = obj

                apply_parameter_assignments(doc, [
                    _make_assignment("Box.Val", 99.0, value_kind=kind),
                ])

                self.assertEqual(obj.Val, 99.0)


class TargetParsingErrorTests(unittest.TestCase):
    def _apply(self, target: str) -> None:
        from parametron_freecad.execution.parameter_assignment import apply_parameter_assignments

        apply_parameter_assignments(_FakeDocument(), [_make_assignment(target, 1.0)])

    def test_no_dot_raises_target_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import ParameterTargetError

        with self.assertRaises(ParameterTargetError):
            self._apply("Length")

    def test_multiple_dots_raises_target_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import ParameterTargetError

        with self.assertRaises(ParameterTargetError):
            self._apply("Box.Shape.Length")

    def test_empty_object_name_raises_target_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import ParameterTargetError

        with self.assertRaises(ParameterTargetError):
            self._apply(".Length")

    def test_empty_property_name_raises_target_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import ParameterTargetError

        with self.assertRaises(ParameterTargetError):
            self._apply("Box.")

    def test_target_error_includes_assignment_index(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterTargetError,
            apply_parameter_assignments,
        )

        doc = _FakeDocument()
        doc._objects["Box"] = SimpleNamespace()

        try:
            apply_parameter_assignments(doc, [
                _make_assignment("Box.Length", 1.0),
                _make_assignment("BadTarget", 2.0),
            ])
            self.fail("expected ParameterTargetError")
        except ParameterTargetError as exc:
            self.assertIn("assignment[1]", str(exc))

    def test_target_error_includes_target_string(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterTargetError,
            apply_parameter_assignments,
        )

        try:
            apply_parameter_assignments(_FakeDocument(), [_make_assignment("BadTarget", 1.0)])
            self.fail("expected ParameterTargetError")
        except ParameterTargetError as exc:
            self.assertIn("BadTarget", str(exc))

    def test_target_error_message_has_no_traceback_text(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterTargetError,
            apply_parameter_assignments,
        )

        try:
            apply_parameter_assignments(_FakeDocument(), [_make_assignment("BadTarget", 1.0)])
            self.fail("expected ParameterTargetError")
        except ParameterTargetError as exc:
            self.assertNotIn("Traceback", str(exc))


class MissingObjectTests(unittest.TestCase):
    def test_get_object_returns_none_raises_object_not_found_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterObjectNotFoundError,
            apply_parameter_assignments,
        )

        with self.assertRaises(ParameterObjectNotFoundError):
            apply_parameter_assignments(
                _FakeDocument(),
                [_make_assignment("Missing.Prop", 1.0)],
            )

    def test_object_not_found_error_includes_assignment_index(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterObjectNotFoundError,
            apply_parameter_assignments,
        )

        doc = _FakeDocument()
        doc._objects["Box"] = SimpleNamespace()

        try:
            apply_parameter_assignments(doc, [
                _make_assignment("Box.Length", 1.0),
                _make_assignment("Missing.Prop", 2.0),
            ])
            self.fail("expected ParameterObjectNotFoundError")
        except ParameterObjectNotFoundError as exc:
            self.assertIn("assignment[1]", str(exc))

    def test_object_not_found_error_includes_target_string(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterObjectNotFoundError,
            apply_parameter_assignments,
        )

        try:
            apply_parameter_assignments(
                _FakeDocument(),
                [_make_assignment("Missing.Prop", 1.0)],
            )
            self.fail("expected ParameterObjectNotFoundError")
        except ParameterObjectNotFoundError as exc:
            self.assertIn("Missing.Prop", str(exc))

    def test_object_not_found_error_has_no_traceback_text(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterObjectNotFoundError,
            apply_parameter_assignments,
        )

        try:
            apply_parameter_assignments(
                _FakeDocument(),
                [_make_assignment("Missing.Prop", 1.0)],
            )
            self.fail("expected ParameterObjectNotFoundError")
        except ParameterObjectNotFoundError as exc:
            self.assertNotIn("Traceback", str(exc))

    def test_get_object_exception_wraps_in_object_not_found_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterObjectNotFoundError,
            apply_parameter_assignments,
        )

        class FailingGetObject:
            def getObject(self, name: str) -> None:
                raise RuntimeError("internal resolve failure")

        with self.assertRaises(ParameterObjectNotFoundError):
            apply_parameter_assignments(
                FailingGetObject(),
                [_make_assignment("Box.Length", 1.0)],
            )

    def test_get_object_exception_is_chained(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterObjectNotFoundError,
            apply_parameter_assignments,
        )
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        original = RuntimeError("internal resolve failure")

        class FailingGetObject:
            def getObject(self, name: str) -> None:
                raise original

        try:
            apply_parameter_assignments(
                FailingGetObject(),
                [_make_assignment("Box.Length", 1.0)],
            )
            self.fail("expected ParameterObjectNotFoundError")
        except ParameterObjectNotFoundError as exc:
            self.assertNotIsInstance(exc, ParameterAccessError)
            self.assertIs(exc.__cause__, original)


class DocumentWithoutGetObjectTests(unittest.TestCase):
    def test_document_without_get_object_raises_parameter_assignment_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterAssignmentError,
            apply_parameter_assignments,
        )
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        class NoGetObject:
            pass

        with self.assertRaises(ParameterAssignmentError) as cm:
            apply_parameter_assignments(NoGetObject(), [])
        self.assertNotIsInstance(cm.exception, ParameterAccessError)

    def test_document_with_non_callable_get_object_raises_parameter_assignment_error(
        self,
    ) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterAssignmentError,
            apply_parameter_assignments,
        )
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        class NonCallableGetObject:
            getObject = "not_callable"

        with self.assertRaises(ParameterAssignmentError) as cm:
            apply_parameter_assignments(NonCallableGetObject(), [])
        self.assertNotIsInstance(cm.exception, ParameterAccessError)

    def test_error_is_deterministic_and_has_no_traceback_text(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterAssignmentError,
            apply_parameter_assignments,
        )

        class NoGetObject:
            pass

        try:
            apply_parameter_assignments(NoGetObject(), [])
            self.fail("expected ParameterAssignmentError")
        except ParameterAssignmentError as exc:
            self.assertNotIn("Traceback", str(exc))


class PropertyAssignmentFailureTests(unittest.TestCase):
    def _make_rejecting_object(self) -> object:
        class RejectingObject:
            def __setattr__(self, name: str, value: object) -> None:
                raise AttributeError(f"read-only: {name}")

        return RejectingObject()

    def test_setattr_failure_raises_property_assignment_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterPropertyAssignmentError,
            apply_parameter_assignments,
        )

        doc = _FakeDocument()
        doc._objects["Box"] = self._make_rejecting_object()

        with self.assertRaises(ParameterPropertyAssignmentError):
            apply_parameter_assignments(doc, [_make_assignment("Box.Length", 1.0)])

    def test_property_error_includes_assignment_index(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterPropertyAssignmentError,
            apply_parameter_assignments,
        )

        doc = _FakeDocument()
        doc._objects["Box"] = SimpleNamespace()
        doc._objects["Sphere"] = self._make_rejecting_object()

        try:
            apply_parameter_assignments(doc, [
                _make_assignment("Box.Length", 1.0),
                _make_assignment("Sphere.Radius", 5.0),
            ])
            self.fail("expected ParameterPropertyAssignmentError")
        except ParameterPropertyAssignmentError as exc:
            self.assertIn("assignment[1]", str(exc))

    def test_property_error_includes_target_string(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterPropertyAssignmentError,
            apply_parameter_assignments,
        )

        doc = _FakeDocument()
        doc._objects["Sphere"] = self._make_rejecting_object()

        try:
            apply_parameter_assignments(doc, [_make_assignment("Sphere.Radius", 5.0)])
            self.fail("expected ParameterPropertyAssignmentError")
        except ParameterPropertyAssignmentError as exc:
            self.assertIn("Sphere.Radius", str(exc))

    def test_property_error_has_no_traceback_text(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterPropertyAssignmentError,
            apply_parameter_assignments,
        )

        doc = _FakeDocument()
        doc._objects["Box"] = self._make_rejecting_object()

        try:
            apply_parameter_assignments(doc, [_make_assignment("Box.Length", 1.0)])
            self.fail("expected ParameterPropertyAssignmentError")
        except ParameterPropertyAssignmentError as exc:
            self.assertNotIn("Traceback", str(exc))

    def test_original_exception_is_chained(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterPropertyAssignmentError,
            apply_parameter_assignments,
        )
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        original = AttributeError("read-only")

        class FailingObject:
            def __setattr__(self, name: str, value: object) -> None:
                raise original

        doc = _FakeDocument()
        doc._objects["Box"] = FailingObject()

        try:
            apply_parameter_assignments(doc, [_make_assignment("Box.Length", 1.0)])
            self.fail("expected ParameterPropertyAssignmentError")
        except ParameterPropertyAssignmentError as exc:
            self.assertNotIsInstance(exc, ParameterAccessError)
            self.assertIs(exc.__cause__, original)


class NonStringTargetTests(unittest.TestCase):
    """Verify that non-string assignment targets route through ParameterTargetError."""

    def _apply(self, target: Any) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            apply_parameter_assignments,
        )
        apply_parameter_assignments(
            _FakeDocument(),
            [{"target": target, "value": 1.0, "valueKind": "scalar"}],
        )

    def test_none_target_raises_target_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import ParameterTargetError

        with self.assertRaises(ParameterTargetError):
            self._apply(None)

    def test_int_target_raises_target_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import ParameterTargetError

        with self.assertRaises(ParameterTargetError):
            self._apply(123)

    def test_dict_target_raises_target_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import ParameterTargetError

        with self.assertRaises(ParameterTargetError):
            self._apply({})

    def test_non_string_target_is_assignment_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterAssignmentError,
        )

        with self.assertRaises(ParameterAssignmentError):
            self._apply(None)

    def test_non_string_target_error_has_no_traceback_text(self) -> None:
        from parametron_freecad.execution.parameter_assignment import ParameterTargetError

        try:
            self._apply(None)
            self.fail("expected ParameterTargetError")
        except ParameterTargetError as exc:
            self.assertNotIn("Traceback", str(exc))


class EarlierAssignmentPreservationTests(unittest.TestCase):
    """Verify that successful assignments before a failure remain applied."""

    def test_earlier_assignments_remain_applied_after_target_failure(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterTargetError,
            apply_parameter_assignments,
        )

        doc = _FakeDocument()
        obj = SimpleNamespace()
        doc._objects["Box"] = obj

        try:
            apply_parameter_assignments(doc, [
                _make_assignment("Box.Length", 10.0),
                _make_assignment("BadTarget", 20.0),
            ])
            self.fail("expected ParameterTargetError")
        except ParameterTargetError:
            pass

        self.assertEqual(obj.Length, 10.0)

    def test_later_assignments_not_applied_after_failure(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterTargetError,
            apply_parameter_assignments,
        )

        doc = _FakeDocument()
        box = SimpleNamespace()
        sphere = SimpleNamespace()
        doc._objects["Box"] = box
        doc._objects["Sphere"] = sphere

        try:
            apply_parameter_assignments(doc, [
                _make_assignment("Box.Length", 10.0),
                _make_assignment("BadTarget", 20.0),
                _make_assignment("Sphere.Radius", 5.0),
            ])
            self.fail("expected ParameterTargetError")
        except ParameterTargetError:
            pass

        self.assertFalse(hasattr(sphere, "Radius"))


class NoLabelLookupAssignmentRegressionTests(unittest.TestCase):
    """Verify assignment execution never falls back to Label-based object lookup."""

    class _StrictFakeDocument:
        """Fake document that raises AssertionError if Objects is accessed."""

        def __init__(self, objects: dict) -> None:
            self._objects = objects
            self.get_object_calls: list[str] = []

        @property
        def Objects(self) -> None:
            raise AssertionError(
                "document.Objects must not be accessed during assignment"
            )

        def getObject(self, name: str) -> Any:
            self.get_object_calls.append(name)
            return self._objects.get(name)

    def test_missing_object_raises_object_not_found_not_assertion_error(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterObjectNotFoundError,
            apply_parameter_assignments,
        )

        doc = self._StrictFakeDocument({})
        with self.assertRaises(ParameterObjectNotFoundError):
            apply_parameter_assignments(
                doc,
                [_make_assignment("DisplayLabel.Length", 1.0)],
            )

    def test_document_objects_not_accessed_on_missing_object(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterObjectNotFoundError,
            apply_parameter_assignments,
        )

        doc = self._StrictFakeDocument({})
        # Should raise ParameterObjectNotFoundError, NOT AssertionError.
        with self.assertRaises(ParameterObjectNotFoundError):
            apply_parameter_assignments(
                doc,
                [_make_assignment("AnyName.Prop", 1.0)],
            )

    def test_get_object_called_with_exact_target_object_name(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            ParameterObjectNotFoundError,
            apply_parameter_assignments,
        )

        doc = self._StrictFakeDocument({})
        try:
            apply_parameter_assignments(
                doc,
                [_make_assignment("ExactName.Prop", 1.0)],
            )
        except ParameterObjectNotFoundError:
            pass

        self.assertIn("ExactName", doc.get_object_calls)


class SpreadsheetLikeTargetAssignmentTests(unittest.TestCase):
    """Verify that spreadsheet-like two-segment targets are treated as ordinary."""

    def test_spreadsheet_a1_treated_as_ordinary_assignment(self) -> None:
        from parametron_freecad.execution.parameter_assignment import (
            apply_parameter_assignments,
        )

        doc = _FakeDocument()
        obj = SimpleNamespace()
        doc._objects["Spreadsheet"] = obj

        apply_parameter_assignments(
            doc,
            [_make_assignment("Spreadsheet.A1", "hello")],
        )

        self.assertEqual(obj.A1, "hello")

    def test_spreadsheet_target_uses_get_object_not_cell_api(self) -> None:
        # Fake object has no cell/alias API — assignment must use setattr only.
        from parametron_freecad.execution.parameter_assignment import (
            apply_parameter_assignments,
        )

        doc = _FakeDocument()
        obj = SimpleNamespace()
        doc._objects["Spreadsheet"] = obj

        apply_parameter_assignments(
            doc,
            [_make_assignment("Spreadsheet.B2", 42)],
        )

        self.assertEqual(obj.B2, 42)


if __name__ == "__main__":
    unittest.main()
