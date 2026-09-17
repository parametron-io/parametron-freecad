"""Unit tests for parametron_freecad.execution.visibility.

Uses fakes/test doubles only. No FreeCAD import is required or performed.
Real-FreeCAD hide/unhide behavior against the committed PartDesign fixture
is covered separately in ``tests/test_visibility_real_fixtures.py``.
"""

from __future__ import annotations

import unittest
from typing import Any


def _mutation(object_name: Any, visible: Any) -> dict[str, Any]:
    return {"object": object_name, "visible": visible}


class _FakeDocument:
    """Fake FreeCAD document that resolves objects from a pre-populated dict."""

    def __init__(self) -> None:
        self._objects: dict[str, Any] = {}

    def getObject(self, name: str) -> Any:
        return self._objects.get(name)


class _FakeTarget:
    """Fake native object supporting the App::PropertyBool Visibility contract.

    ``Visibility`` is intentionally left unset until the production code
    assigns it, so tests can prove with ``hasattr`` that no synthetic value
    was ever written. Deliberately does not define ``ViewObject`` or any
    GUI-specific visibility surface: the production consumer must never
    require one.
    """

    def __init__(
        self,
        properties: list[str] | None = None,
        property_types: dict[str, str] | None = None,
    ) -> None:
        self._properties = list(properties) if properties is not None else ["Visibility"]
        self._property_types = (
            dict(property_types) if property_types is not None else {"Visibility": "App::PropertyBool"}
        )

    @property
    def PropertiesList(self) -> list[str]:
        return self._properties

    def getTypeIdOfProperty(self, name: str) -> str:
        return self._property_types[name]


class _RecordingTarget:
    """Fake native object that records the order of Visibility writes."""

    PropertiesList = ["Visibility"]

    def __init__(self, order: list[str], name: str) -> None:
        object.__setattr__(self, "_order", order)
        object.__setattr__(self, "_name", name)

    def getTypeIdOfProperty(self, name: str) -> str:
        return "App::PropertyBool"

    def __setattr__(self, name: str, value: object) -> None:
        if name == "Visibility":
            object.__getattribute__(self, "_order").append(object.__getattribute__(self, "_name"))
        object.__setattr__(self, name, value)


class _NoGuiTarget:
    """Fake native object that fails loudly if any GUI surface is touched.

    Defines ``ViewObject`` as a property that raises AssertionError on
    access, so any accidental access by the production consumer causes a
    test failure rather than silently succeeding.
    """

    PropertiesList = ["Visibility"]

    def __init__(self) -> None:
        self._visibility: Any = None

    def getTypeIdOfProperty(self, name: str) -> str:
        return "App::PropertyBool"

    @property
    def ViewObject(self) -> Any:
        raise AssertionError("target.ViewObject must not be accessed during visibility mutation")

    @property
    def Visibility(self) -> Any:
        return self._visibility

    @Visibility.setter
    def Visibility(self, value: Any) -> None:
        self._visibility = value


class PublicApiTests(unittest.TestCase):
    def test_apply_visibility_mutations_is_exported(self) -> None:
        from parametron_freecad.execution import visibility

        self.assertIn("apply_visibility_mutations", visibility.__all__)

    def test_error_classes_are_exported(self) -> None:
        from parametron_freecad.execution import visibility

        for name in [
            "VisibilityMutationError",
            "VisibilityNativeOperationError",
            "VisibilityTargetNotFoundError",
            "UnsupportedVisibilityTargetError",
        ]:
            with self.subTest(name=name):
                self.assertIn(name, visibility.__all__)

    def test_error_hierarchy(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityMutationError,
            VisibilityNativeOperationError,
            VisibilityTargetNotFoundError,
            UnsupportedVisibilityTargetError,
        )

        self.assertTrue(issubclass(VisibilityMutationError, ValueError))
        self.assertTrue(issubclass(VisibilityTargetNotFoundError, VisibilityMutationError))
        self.assertTrue(issubclass(UnsupportedVisibilityTargetError, VisibilityMutationError))
        self.assertTrue(issubclass(VisibilityNativeOperationError, VisibilityMutationError))

    def test_error_hierarchy_is_visibility_specific(self) -> None:
        from parametron_freecad.execution.suppression import SuppressionMutationError
        from parametron_freecad.execution.visibility import VisibilityMutationError

        self.assertFalse(issubclass(VisibilityMutationError, SuppressionMutationError))
        self.assertFalse(issubclass(SuppressionMutationError, VisibilityMutationError))

    def test_import_does_not_require_freecad(self) -> None:
        import sys

        sys.modules.pop("parametron_freecad.execution.visibility", None)
        import parametron_freecad.execution.visibility  # noqa: F401

        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)


class ExactTargetLookupTests(unittest.TestCase):
    def test_object_string_passed_unchanged_to_get_object(self) -> None:
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        calls: list[str] = []

        class RecordingDocument:
            def getObject(self, name: str) -> Any:
                calls.append(name)
                return _FakeTarget()

        apply_visibility_mutations(RecordingDocument(), [_mutation("Exact.Name-123", False)])

        self.assertEqual(calls, ["Exact.Name-123"])

    def test_exact_lookup_succeeds(self) -> None:
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        doc = _FakeDocument()
        target = _FakeTarget()
        doc._objects["Feature"] = target

        apply_visibility_mutations(doc, [_mutation("Feature", False)])

        self.assertIs(target.Visibility, False)

    def test_missing_target_raises_target_not_found_error(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityTargetNotFoundError,
            apply_visibility_mutations,
        )

        with self.assertRaises(VisibilityTargetNotFoundError):
            apply_visibility_mutations(_FakeDocument(), [_mutation("Missing", False)])

    def test_target_not_found_message_identifies_index_and_object(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityTargetNotFoundError,
            apply_visibility_mutations,
        )

        doc = _FakeDocument()
        doc._objects["A"] = _FakeTarget()

        try:
            apply_visibility_mutations(doc, [_mutation("A", False), _mutation("Gone", False)])
            self.fail("expected VisibilityTargetNotFoundError")
        except VisibilityTargetNotFoundError as exc:
            self.assertIn("visibility[1]", str(exc))
            self.assertIn("Gone", str(exc))


class NoFallbackLookupRegressionTests(unittest.TestCase):
    """Verify visibility execution never falls back to non-exact lookup."""

    class _StrictDocument:
        """Fake document that raises AssertionError if Objects is accessed."""

        def __init__(self, objects: dict[str, Any]) -> None:
            self._objects = objects
            self.get_object_calls: list[str] = []

        @property
        def Objects(self) -> None:
            raise AssertionError("document.Objects must not be accessed during visibility mutation")

        def getObject(self, name: str) -> Any:
            self.get_object_calls.append(name)
            return self._objects.get(name)

    def test_missing_target_does_not_enumerate_document_objects(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityTargetNotFoundError,
            apply_visibility_mutations,
        )

        doc = self._StrictDocument({})
        with self.assertRaises(VisibilityTargetNotFoundError):
            apply_visibility_mutations(doc, [_mutation("Label-Like-Name", False)])

        self.assertIn("Label-Like-Name", doc.get_object_calls)

    def test_case_variant_name_is_not_resolved(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityTargetNotFoundError,
            apply_visibility_mutations,
        )

        doc = self._StrictDocument({"Feature": _FakeTarget()})
        with self.assertRaises(VisibilityTargetNotFoundError):
            apply_visibility_mutations(doc, [_mutation("feature", False)])

    def test_alias_or_label_name_is_not_resolved(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityTargetNotFoundError,
            apply_visibility_mutations,
        )

        doc = self._StrictDocument({"MutationBody": _FakeTarget()})
        with self.assertRaises(VisibilityTargetNotFoundError):
            apply_visibility_mutations(doc, [_mutation("Body", False)])


class NativeCapabilityRequirementTests(unittest.TestCase):
    def test_visibility_absent_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.visibility import (
            UnsupportedVisibilityTargetError,
            apply_visibility_mutations,
        )

        doc = _FakeDocument()
        doc._objects["Sketch"] = _FakeTarget(properties=["Placement", "Suppressed"])

        with self.assertRaises(UnsupportedVisibilityTargetError):
            apply_visibility_mutations(doc, [_mutation("Sketch", False)])

    def test_visibility_absent_does_not_synthesize_property(self) -> None:
        from parametron_freecad.execution.visibility import (
            UnsupportedVisibilityTargetError,
            apply_visibility_mutations,
        )

        doc = _FakeDocument()
        target = _FakeTarget(properties=["Placement"])
        doc._objects["Sketch"] = target

        with self.assertRaises(UnsupportedVisibilityTargetError):
            apply_visibility_mutations(doc, [_mutation("Sketch", False)])

        self.assertFalse(hasattr(target, "Visibility"))

    def test_properties_list_attribute_missing_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.visibility import (
            UnsupportedVisibilityTargetError,
            apply_visibility_mutations,
        )

        class TargetWithoutPropertiesList:
            pass

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetWithoutPropertiesList()

        with self.assertRaises(UnsupportedVisibilityTargetError):
            apply_visibility_mutations(doc, [_mutation("Feature", False)])

    def test_get_type_id_attribute_missing_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.visibility import (
            UnsupportedVisibilityTargetError,
            apply_visibility_mutations,
        )

        class TargetWithoutTypeInspection:
            PropertiesList = ["Visibility"]

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetWithoutTypeInspection()

        with self.assertRaises(UnsupportedVisibilityTargetError):
            apply_visibility_mutations(doc, [_mutation("Feature", False)])

    def test_get_type_id_non_callable_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.visibility import (
            UnsupportedVisibilityTargetError,
            apply_visibility_mutations,
        )

        class TargetWithNonCallableTypeInspection:
            PropertiesList = ["Visibility"]
            getTypeIdOfProperty = "not-callable"

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetWithNonCallableTypeInspection()

        with self.assertRaises(UnsupportedVisibilityTargetError):
            apply_visibility_mutations(doc, [_mutation("Feature", False)])

    def test_wrong_property_type_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.visibility import (
            UnsupportedVisibilityTargetError,
            apply_visibility_mutations,
        )

        doc = _FakeDocument()
        doc._objects["Feature"] = _FakeTarget(
            properties=["Visibility"],
            property_types={"Visibility": "App::PropertyString"},
        )

        with self.assertRaises(UnsupportedVisibilityTargetError):
            apply_visibility_mutations(doc, [_mutation("Feature", False)])

    def test_wrong_property_type_does_not_write_visibility(self) -> None:
        from parametron_freecad.execution.visibility import (
            UnsupportedVisibilityTargetError,
            apply_visibility_mutations,
        )

        doc = _FakeDocument()
        target = _FakeTarget(
            properties=["Visibility"],
            property_types={"Visibility": "App::PropertyString"},
        )
        doc._objects["Feature"] = target

        with self.assertRaises(UnsupportedVisibilityTargetError):
            apply_visibility_mutations(doc, [_mutation("Feature", False)])

        self.assertFalse(hasattr(target, "Visibility"))


class RequestedStateApplicationTests(unittest.TestCase):
    def test_requested_false_sets_native_visibility_false(self) -> None:
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        doc = _FakeDocument()
        target = _FakeTarget()
        doc._objects["Feature"] = target

        apply_visibility_mutations(doc, [_mutation("Feature", False)])

        self.assertIs(target.Visibility, False)

    def test_requested_true_sets_native_visibility_true(self) -> None:
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        doc = _FakeDocument()
        target = _FakeTarget()
        doc._objects["Feature"] = target

        apply_visibility_mutations(doc, [_mutation("Feature", True)])

        self.assertIs(target.Visibility, True)


class AppLevelOnlyBehaviorTests(unittest.TestCase):
    def test_visibility_mutation_does_not_access_view_object(self) -> None:
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        doc = _FakeDocument()
        target = _NoGuiTarget()
        doc._objects["Feature"] = target

        apply_visibility_mutations(doc, [_mutation("Feature", False)])

        self.assertIs(target.Visibility, False)

    def test_freecadgui_module_is_never_imported(self) -> None:
        import sys

        from parametron_freecad.execution.visibility import apply_visibility_mutations

        doc = _FakeDocument()
        doc._objects["Feature"] = _FakeTarget()

        apply_visibility_mutations(doc, [_mutation("Feature", True)])

        self.assertNotIn("FreeCADGui", sys.modules)


class SuppressionIndependenceTests(unittest.TestCase):
    """Proves a visibility mutation never touches a target's Suppressed state."""

    def test_visibility_mutation_does_not_modify_suppressed(self) -> None:
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        class _TargetWithBothProperties:
            PropertiesList = ["Visibility", "Suppressed"]

            def __init__(self) -> None:
                self.Suppressed = True

            def getTypeIdOfProperty(self, name: str) -> str:
                return "App::PropertyBool"

        doc = _FakeDocument()
        target = _TargetWithBothProperties()
        doc._objects["Feature"] = target

        apply_visibility_mutations(doc, [_mutation("Feature", False)])

        self.assertIs(target.Visibility, False)
        self.assertIs(target.Suppressed, True)

    def test_visibility_mutation_does_not_call_suppression_consumer(self) -> None:
        import parametron_freecad.execution.suppression as suppression_module
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        original = suppression_module.apply_suppression_mutations
        calls: list[Any] = []

        def _tracking(*args: Any, **kwargs: Any) -> Any:
            calls.append((args, kwargs))
            return original(*args, **kwargs)

        suppression_module.apply_suppression_mutations = _tracking
        try:
            doc = _FakeDocument()
            doc._objects["Feature"] = _FakeTarget()
            apply_visibility_mutations(doc, [_mutation("Feature", True)])
        finally:
            suppression_module.apply_suppression_mutations = original

        self.assertEqual(calls, [])


class OrderingAndFailFastTests(unittest.TestCase):
    def test_multiple_entries_applied_in_caller_provided_order(self) -> None:
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        order: list[str] = []
        doc = _FakeDocument()
        doc._objects["C"] = _RecordingTarget(order, "C")
        doc._objects["A"] = _RecordingTarget(order, "A")
        doc._objects["B"] = _RecordingTarget(order, "B")

        apply_visibility_mutations(doc, [
            _mutation("C", False),
            _mutation("A", True),
            _mutation("B", False),
        ])

        self.assertEqual(order, ["C", "A", "B"])

    def test_earlier_successful_mutations_remain_applied_after_later_failure(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityTargetNotFoundError,
            apply_visibility_mutations,
        )

        doc = _FakeDocument()
        a = _FakeTarget()
        doc._objects["A"] = a

        try:
            apply_visibility_mutations(doc, [
                _mutation("A", False),
                _mutation("Missing", False),
            ])
            self.fail("expected VisibilityTargetNotFoundError")
        except VisibilityTargetNotFoundError:
            pass

        self.assertIs(a.Visibility, False)

    def test_later_mutations_not_applied_after_earlier_failure(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityTargetNotFoundError,
            apply_visibility_mutations,
        )

        doc = _FakeDocument()
        b = _FakeTarget()
        doc._objects["B"] = b

        try:
            apply_visibility_mutations(doc, [
                _mutation("Missing", False),
                _mutation("B", False),
            ])
            self.fail("expected VisibilityTargetNotFoundError")
        except VisibilityTargetNotFoundError:
            pass

        self.assertFalse(hasattr(b, "Visibility"))

    def test_no_rollback_of_earlier_mutations_across_unsupported_failure(self) -> None:
        # No rollback semantics are part of this contract: an unsupported
        # capability failure on a later entry must not undo an earlier
        # successful native write.
        from parametron_freecad.execution.visibility import (
            UnsupportedVisibilityTargetError,
            apply_visibility_mutations,
        )

        doc = _FakeDocument()
        good = _FakeTarget()
        bad = _FakeTarget(properties=["Placement"])
        doc._objects["Good"] = good
        doc._objects["Bad"] = bad

        try:
            apply_visibility_mutations(doc, [
                _mutation("Good", False),
                _mutation("Bad", False),
            ])
            self.fail("expected UnsupportedVisibilityTargetError")
        except UnsupportedVisibilityTargetError:
            pass

        self.assertIs(good.Visibility, False)


class InputImmutabilityTests(unittest.TestCase):
    def test_mutation_mapping_is_not_mutated(self) -> None:
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        doc = _FakeDocument()
        doc._objects["A"] = _FakeTarget()
        mutation = {"object": "A", "visible": False}
        snapshot = dict(mutation)

        apply_visibility_mutations(doc, [mutation])

        self.assertEqual(mutation, snapshot)

    def test_mutations_sequence_is_not_reordered(self) -> None:
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        doc = _FakeDocument()
        doc._objects["A"] = _FakeTarget()
        doc._objects["B"] = _FakeTarget()
        mutations = [_mutation("B", False), _mutation("A", True)]
        before = list(mutations)

        apply_visibility_mutations(doc, mutations)

        self.assertEqual(mutations, before)


class EmptyCollectionTests(unittest.TestCase):
    def test_empty_mutations_succeeds(self) -> None:
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        apply_visibility_mutations(_FakeDocument(), [])

    def test_empty_mutations_performs_no_object_lookup(self) -> None:
        from parametron_freecad.execution.visibility import apply_visibility_mutations

        calls: list[str] = []

        class RecordingDocument:
            def getObject(self, name: str) -> None:
                calls.append(name)
                return None

        apply_visibility_mutations(RecordingDocument(), [])

        self.assertEqual(calls, [])


class DocumentAccessFailureTests(unittest.TestCase):
    def test_document_without_get_object_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityNativeOperationError,
            apply_visibility_mutations,
        )

        class NoGetObject:
            pass

        with self.assertRaises(VisibilityNativeOperationError):
            apply_visibility_mutations(NoGetObject(), [])

    def test_document_with_non_callable_get_object_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityNativeOperationError,
            apply_visibility_mutations,
        )

        class NonCallableGetObject:
            getObject = "not_callable"

        with self.assertRaises(VisibilityNativeOperationError):
            apply_visibility_mutations(NonCallableGetObject(), [])


class NativeErrorHandlingTests(unittest.TestCase):
    def test_get_object_exception_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityNativeOperationError,
            apply_visibility_mutations,
        )

        class FailingGetObject:
            def getObject(self, name: str) -> None:
                raise RuntimeError("internal resolve failure")

        with self.assertRaises(VisibilityNativeOperationError):
            apply_visibility_mutations(FailingGetObject(), [_mutation("Feature", False)])

    def test_get_object_exception_is_chained(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityNativeOperationError,
            apply_visibility_mutations,
        )

        original = RuntimeError("internal resolve failure")

        class FailingGetObject:
            def getObject(self, name: str) -> None:
                raise original

        try:
            apply_visibility_mutations(FailingGetObject(), [_mutation("Feature", False)])
            self.fail("expected VisibilityNativeOperationError")
        except VisibilityNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_get_object_failure_message_identifies_index_and_object(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityNativeOperationError,
            apply_visibility_mutations,
        )

        class FailingGetObject:
            def getObject(self, name: str) -> None:
                raise RuntimeError("boom")

        try:
            apply_visibility_mutations(FailingGetObject(), [_mutation("Widget", False)])
            self.fail("expected VisibilityNativeOperationError")
        except VisibilityNativeOperationError as exc:
            self.assertIn("visibility[0]", str(exc))
            self.assertIn("Widget", str(exc))

    def test_properties_list_attribute_error_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.visibility import (
            UnsupportedVisibilityTargetError,
            apply_visibility_mutations,
        )

        class TargetPropertiesListAttributeMissing:
            pass

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetPropertiesListAttributeMissing()

        with self.assertRaises(UnsupportedVisibilityTargetError):
            apply_visibility_mutations(doc, [_mutation("Feature", False)])

    def test_properties_list_generic_error_raises_native_operation_error_with_cause(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityNativeOperationError,
            apply_visibility_mutations,
        )

        original = RuntimeError("properties inspection failure")

        class TargetPropertiesListRaises:
            @property
            def PropertiesList(self) -> list[str]:
                raise original

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetPropertiesListRaises()

        try:
            apply_visibility_mutations(doc, [_mutation("Feature", False)])
            self.fail("expected VisibilityNativeOperationError")
        except VisibilityNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_properties_list_contains_check_error_raises_native_operation_error_with_cause(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityNativeOperationError,
            apply_visibility_mutations,
        )

        original = RuntimeError("contains failure")

        class RaisingContainer:
            def __contains__(self, item: object) -> bool:
                raise original

        class TargetContainsRaises:
            PropertiesList = RaisingContainer()

            def getTypeIdOfProperty(self, name: str) -> str:
                return "App::PropertyBool"

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetContainsRaises()

        try:
            apply_visibility_mutations(doc, [_mutation("Feature", False)])
            self.fail("expected VisibilityNativeOperationError")
        except VisibilityNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_get_type_id_call_error_raises_native_operation_error_with_cause(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityNativeOperationError,
            apply_visibility_mutations,
        )

        original = RuntimeError("type inspection failure")

        class TargetTypeInspectionRaises:
            PropertiesList = ["Visibility"]

            def getTypeIdOfProperty(self, name: str) -> str:
                raise original

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetTypeInspectionRaises()

        try:
            apply_visibility_mutations(doc, [_mutation("Feature", False)])
            self.fail("expected VisibilityNativeOperationError")
        except VisibilityNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_visibility_write_error_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityNativeOperationError,
            apply_visibility_mutations,
        )

        class RejectingTarget:
            PropertiesList = ["Visibility"]

            def getTypeIdOfProperty(self, name: str) -> str:
                return "App::PropertyBool"

            def __setattr__(self, name: str, value: object) -> None:
                raise RuntimeError("read-only native property")

        doc = _FakeDocument()
        doc._objects["Feature"] = RejectingTarget()

        with self.assertRaises(VisibilityNativeOperationError):
            apply_visibility_mutations(doc, [_mutation("Feature", False)])

    def test_visibility_write_error_is_chained(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityNativeOperationError,
            apply_visibility_mutations,
        )

        original = RuntimeError("read-only native property")

        class RejectingTarget:
            PropertiesList = ["Visibility"]

            def getTypeIdOfProperty(self, name: str) -> str:
                return "App::PropertyBool"

            def __setattr__(self, name: str, value: object) -> None:
                raise original

        doc = _FakeDocument()
        doc._objects["Feature"] = RejectingTarget()

        try:
            apply_visibility_mutations(doc, [_mutation("Feature", False)])
            self.fail("expected VisibilityNativeOperationError")
        except VisibilityNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_visibility_write_error_message_identifies_index_and_object(self) -> None:
        from parametron_freecad.execution.visibility import (
            VisibilityNativeOperationError,
            apply_visibility_mutations,
        )

        class RejectingTarget:
            PropertiesList = ["Visibility"]

            def getTypeIdOfProperty(self, name: str) -> str:
                return "App::PropertyBool"

            def __setattr__(self, name: str, value: object) -> None:
                raise RuntimeError("read-only")

        doc = _FakeDocument()
        doc._objects["Good"] = _FakeTarget()
        doc._objects["Bad"] = RejectingTarget()

        try:
            apply_visibility_mutations(doc, [
                _mutation("Good", False),
                _mutation("Bad", True),
            ])
            self.fail("expected VisibilityNativeOperationError")
        except VisibilityNativeOperationError as exc:
            self.assertIn("visibility[1]", str(exc))
            self.assertIn("Bad", str(exc))


if __name__ == "__main__":
    unittest.main()
