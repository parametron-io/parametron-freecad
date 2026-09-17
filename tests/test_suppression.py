"""Unit tests for parametron_freecad.execution.suppression.

Uses fakes/test doubles only. No FreeCAD import is required or performed.
Real-FreeCAD suppression/unsuppression behavior against the committed
PartDesign fixture is covered separately in
``tests/test_suppression_real_fixtures.py``.
"""

from __future__ import annotations

import unittest
from typing import Any


def _mutation(object_name: Any, suppressed: Any) -> dict[str, Any]:
    return {"object": object_name, "suppressed": suppressed}


class _FakeDocument:
    """Fake FreeCAD document that resolves objects from a pre-populated dict."""

    def __init__(self) -> None:
        self._objects: dict[str, Any] = {}

    def getObject(self, name: str) -> Any:
        return self._objects.get(name)


class _FakeTarget:
    """Fake native object supporting the App::PropertyBool Suppressed contract.

    ``Suppressed`` is intentionally left unset until the production code
    assigns it, so tests can prove with ``hasattr`` that no synthetic value
    was ever written.
    """

    def __init__(
        self,
        properties: list[str] | None = None,
        property_types: dict[str, str] | None = None,
    ) -> None:
        self._properties = list(properties) if properties is not None else ["Suppressed"]
        self._property_types = (
            dict(property_types) if property_types is not None else {"Suppressed": "App::PropertyBool"}
        )

    @property
    def PropertiesList(self) -> list[str]:
        return self._properties

    def getTypeIdOfProperty(self, name: str) -> str:
        return self._property_types[name]


class _RecordingTarget:
    """Fake native object that records the order of Suppressed writes."""

    PropertiesList = ["Suppressed"]

    def __init__(self, order: list[str], name: str) -> None:
        object.__setattr__(self, "_order", order)
        object.__setattr__(self, "_name", name)

    def getTypeIdOfProperty(self, name: str) -> str:
        return "App::PropertyBool"

    def __setattr__(self, name: str, value: object) -> None:
        if name == "Suppressed":
            object.__getattribute__(self, "_order").append(object.__getattribute__(self, "_name"))
        object.__setattr__(self, name, value)


class PublicApiTests(unittest.TestCase):
    def test_apply_suppression_mutations_is_exported(self) -> None:
        from parametron_freecad.execution import suppression

        self.assertIn("apply_suppression_mutations", suppression.__all__)

    def test_error_classes_are_exported(self) -> None:
        from parametron_freecad.execution import suppression

        for name in [
            "SuppressionMutationError",
            "SuppressionNativeOperationError",
            "SuppressionTargetNotFoundError",
            "UnsupportedSuppressionTargetError",
        ]:
            with self.subTest(name=name):
                self.assertIn(name, suppression.__all__)

    def test_error_hierarchy(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionMutationError,
            SuppressionNativeOperationError,
            SuppressionTargetNotFoundError,
            UnsupportedSuppressionTargetError,
        )

        self.assertTrue(issubclass(SuppressionMutationError, ValueError))
        self.assertTrue(issubclass(SuppressionTargetNotFoundError, SuppressionMutationError))
        self.assertTrue(issubclass(UnsupportedSuppressionTargetError, SuppressionMutationError))
        self.assertTrue(issubclass(SuppressionNativeOperationError, SuppressionMutationError))

    def test_import_does_not_require_freecad(self) -> None:
        import sys

        sys.modules.pop("parametron_freecad.execution.suppression", None)
        import parametron_freecad.execution.suppression  # noqa: F401

        self.assertNotIn("FreeCAD", sys.modules)


class ExactTargetLookupTests(unittest.TestCase):
    def test_object_string_passed_unchanged_to_get_object(self) -> None:
        from parametron_freecad.execution.suppression import apply_suppression_mutations

        calls: list[str] = []

        class RecordingDocument:
            def getObject(self, name: str) -> Any:
                calls.append(name)
                return _FakeTarget()

        apply_suppression_mutations(RecordingDocument(), [_mutation("Exact.Name-123", True)])

        self.assertEqual(calls, ["Exact.Name-123"])

    def test_exact_lookup_succeeds(self) -> None:
        from parametron_freecad.execution.suppression import apply_suppression_mutations

        doc = _FakeDocument()
        target = _FakeTarget()
        doc._objects["Feature"] = target

        apply_suppression_mutations(doc, [_mutation("Feature", True)])

        self.assertIs(target.Suppressed, True)

    def test_missing_target_raises_target_not_found_error(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionTargetNotFoundError,
            apply_suppression_mutations,
        )

        with self.assertRaises(SuppressionTargetNotFoundError):
            apply_suppression_mutations(_FakeDocument(), [_mutation("Missing", True)])

    def test_target_not_found_message_identifies_index_and_object(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionTargetNotFoundError,
            apply_suppression_mutations,
        )

        doc = _FakeDocument()
        doc._objects["A"] = _FakeTarget()

        try:
            apply_suppression_mutations(doc, [_mutation("A", True), _mutation("Gone", True)])
            self.fail("expected SuppressionTargetNotFoundError")
        except SuppressionTargetNotFoundError as exc:
            self.assertIn("suppression[1]", str(exc))
            self.assertIn("Gone", str(exc))


class NoFallbackLookupRegressionTests(unittest.TestCase):
    """Verify suppression execution never falls back to non-exact lookup."""

    class _StrictDocument:
        """Fake document that raises AssertionError if Objects is accessed."""

        def __init__(self, objects: dict[str, Any]) -> None:
            self._objects = objects
            self.get_object_calls: list[str] = []

        @property
        def Objects(self) -> None:
            raise AssertionError("document.Objects must not be accessed during suppression")

        def getObject(self, name: str) -> Any:
            self.get_object_calls.append(name)
            return self._objects.get(name)

    def test_missing_target_does_not_enumerate_document_objects(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionTargetNotFoundError,
            apply_suppression_mutations,
        )

        doc = self._StrictDocument({})
        with self.assertRaises(SuppressionTargetNotFoundError):
            apply_suppression_mutations(doc, [_mutation("Label-Like-Name", True)])

        self.assertIn("Label-Like-Name", doc.get_object_calls)

    def test_case_variant_name_is_not_resolved(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionTargetNotFoundError,
            apply_suppression_mutations,
        )

        doc = self._StrictDocument({"Feature": _FakeTarget()})
        with self.assertRaises(SuppressionTargetNotFoundError):
            apply_suppression_mutations(doc, [_mutation("feature", True)])

    def test_alias_or_label_name_is_not_resolved(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionTargetNotFoundError,
            apply_suppression_mutations,
        )

        doc = self._StrictDocument({"Chamfer001": _FakeTarget()})
        with self.assertRaises(SuppressionTargetNotFoundError):
            apply_suppression_mutations(doc, [_mutation("TerminalChamfer", True)])


class NativeCapabilityRequirementTests(unittest.TestCase):
    def test_suppressed_absent_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.suppression import (
            UnsupportedSuppressionTargetError,
            apply_suppression_mutations,
        )

        doc = _FakeDocument()
        doc._objects["Sketch"] = _FakeTarget(properties=["Placement", "Visibility"])

        with self.assertRaises(UnsupportedSuppressionTargetError):
            apply_suppression_mutations(doc, [_mutation("Sketch", True)])

    def test_suppressed_absent_does_not_synthesize_property(self) -> None:
        from parametron_freecad.execution.suppression import (
            UnsupportedSuppressionTargetError,
            apply_suppression_mutations,
        )

        doc = _FakeDocument()
        target = _FakeTarget(properties=["Placement"])
        doc._objects["Sketch"] = target

        with self.assertRaises(UnsupportedSuppressionTargetError):
            apply_suppression_mutations(doc, [_mutation("Sketch", True)])

        self.assertFalse(hasattr(target, "Suppressed"))

    def test_properties_list_attribute_missing_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.suppression import (
            UnsupportedSuppressionTargetError,
            apply_suppression_mutations,
        )

        class TargetWithoutPropertiesList:
            pass

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetWithoutPropertiesList()

        with self.assertRaises(UnsupportedSuppressionTargetError):
            apply_suppression_mutations(doc, [_mutation("Feature", True)])

    def test_get_type_id_attribute_missing_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.suppression import (
            UnsupportedSuppressionTargetError,
            apply_suppression_mutations,
        )

        class TargetWithoutTypeInspection:
            PropertiesList = ["Suppressed"]

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetWithoutTypeInspection()

        with self.assertRaises(UnsupportedSuppressionTargetError):
            apply_suppression_mutations(doc, [_mutation("Feature", True)])

    def test_get_type_id_non_callable_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.suppression import (
            UnsupportedSuppressionTargetError,
            apply_suppression_mutations,
        )

        class TargetWithNonCallableTypeInspection:
            PropertiesList = ["Suppressed"]
            getTypeIdOfProperty = "not-callable"

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetWithNonCallableTypeInspection()

        with self.assertRaises(UnsupportedSuppressionTargetError):
            apply_suppression_mutations(doc, [_mutation("Feature", True)])

    def test_wrong_property_type_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.suppression import (
            UnsupportedSuppressionTargetError,
            apply_suppression_mutations,
        )

        doc = _FakeDocument()
        doc._objects["Feature"] = _FakeTarget(
            properties=["Suppressed"],
            property_types={"Suppressed": "App::PropertyString"},
        )

        with self.assertRaises(UnsupportedSuppressionTargetError):
            apply_suppression_mutations(doc, [_mutation("Feature", True)])

    def test_wrong_property_type_does_not_write_suppressed(self) -> None:
        from parametron_freecad.execution.suppression import (
            UnsupportedSuppressionTargetError,
            apply_suppression_mutations,
        )

        doc = _FakeDocument()
        target = _FakeTarget(
            properties=["Suppressed"],
            property_types={"Suppressed": "App::PropertyString"},
        )
        doc._objects["Feature"] = target

        with self.assertRaises(UnsupportedSuppressionTargetError):
            apply_suppression_mutations(doc, [_mutation("Feature", True)])

        self.assertFalse(hasattr(target, "Suppressed"))


class RequestedStateApplicationTests(unittest.TestCase):
    def test_requested_true_sets_native_suppressed_true(self) -> None:
        from parametron_freecad.execution.suppression import apply_suppression_mutations

        doc = _FakeDocument()
        target = _FakeTarget()
        doc._objects["Feature"] = target

        apply_suppression_mutations(doc, [_mutation("Feature", True)])

        self.assertIs(target.Suppressed, True)

    def test_requested_false_sets_native_suppressed_false(self) -> None:
        from parametron_freecad.execution.suppression import apply_suppression_mutations

        doc = _FakeDocument()
        target = _FakeTarget()
        doc._objects["Feature"] = target

        apply_suppression_mutations(doc, [_mutation("Feature", False)])

        self.assertIs(target.Suppressed, False)


class OrderingAndFailFastTests(unittest.TestCase):
    def test_multiple_entries_applied_in_caller_provided_order(self) -> None:
        from parametron_freecad.execution.suppression import apply_suppression_mutations

        order: list[str] = []
        doc = _FakeDocument()
        doc._objects["C"] = _RecordingTarget(order, "C")
        doc._objects["A"] = _RecordingTarget(order, "A")
        doc._objects["B"] = _RecordingTarget(order, "B")

        apply_suppression_mutations(doc, [
            _mutation("C", True),
            _mutation("A", False),
            _mutation("B", True),
        ])

        self.assertEqual(order, ["C", "A", "B"])

    def test_earlier_successful_mutations_remain_applied_after_later_failure(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionTargetNotFoundError,
            apply_suppression_mutations,
        )

        doc = _FakeDocument()
        a = _FakeTarget()
        doc._objects["A"] = a

        try:
            apply_suppression_mutations(doc, [
                _mutation("A", True),
                _mutation("Missing", True),
            ])
            self.fail("expected SuppressionTargetNotFoundError")
        except SuppressionTargetNotFoundError:
            pass

        self.assertIs(a.Suppressed, True)

    def test_later_mutations_not_applied_after_earlier_failure(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionTargetNotFoundError,
            apply_suppression_mutations,
        )

        doc = _FakeDocument()
        b = _FakeTarget()
        doc._objects["B"] = b

        try:
            apply_suppression_mutations(doc, [
                _mutation("Missing", True),
                _mutation("B", True),
            ])
            self.fail("expected SuppressionTargetNotFoundError")
        except SuppressionTargetNotFoundError:
            pass

        self.assertFalse(hasattr(b, "Suppressed"))

    def test_no_rollback_of_earlier_mutations_across_unsupported_failure(self) -> None:
        # No rollback semantics are part of this contract: an unsupported
        # capability failure on a later entry must not undo an earlier
        # successful native write.
        from parametron_freecad.execution.suppression import (
            UnsupportedSuppressionTargetError,
            apply_suppression_mutations,
        )

        doc = _FakeDocument()
        good = _FakeTarget()
        bad = _FakeTarget(properties=["Placement"])
        doc._objects["Good"] = good
        doc._objects["Bad"] = bad

        try:
            apply_suppression_mutations(doc, [
                _mutation("Good", True),
                _mutation("Bad", True),
            ])
            self.fail("expected UnsupportedSuppressionTargetError")
        except UnsupportedSuppressionTargetError:
            pass

        self.assertIs(good.Suppressed, True)


class InputImmutabilityTests(unittest.TestCase):
    def test_mutation_mapping_is_not_mutated(self) -> None:
        from parametron_freecad.execution.suppression import apply_suppression_mutations

        doc = _FakeDocument()
        doc._objects["A"] = _FakeTarget()
        mutation = {"object": "A", "suppressed": True}
        snapshot = dict(mutation)

        apply_suppression_mutations(doc, [mutation])

        self.assertEqual(mutation, snapshot)

    def test_mutations_sequence_is_not_reordered(self) -> None:
        from parametron_freecad.execution.suppression import apply_suppression_mutations

        doc = _FakeDocument()
        doc._objects["A"] = _FakeTarget()
        doc._objects["B"] = _FakeTarget()
        mutations = [_mutation("B", True), _mutation("A", False)]
        before = list(mutations)

        apply_suppression_mutations(doc, mutations)

        self.assertEqual(mutations, before)


class EmptyCollectionTests(unittest.TestCase):
    def test_empty_mutations_succeeds(self) -> None:
        from parametron_freecad.execution.suppression import apply_suppression_mutations

        apply_suppression_mutations(_FakeDocument(), [])

    def test_empty_mutations_performs_no_object_lookup(self) -> None:
        from parametron_freecad.execution.suppression import apply_suppression_mutations

        calls: list[str] = []

        class RecordingDocument:
            def getObject(self, name: str) -> None:
                calls.append(name)
                return None

        apply_suppression_mutations(RecordingDocument(), [])

        self.assertEqual(calls, [])


class DocumentAccessFailureTests(unittest.TestCase):
    def test_document_without_get_object_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionNativeOperationError,
            apply_suppression_mutations,
        )

        class NoGetObject:
            pass

        with self.assertRaises(SuppressionNativeOperationError):
            apply_suppression_mutations(NoGetObject(), [])

    def test_document_with_non_callable_get_object_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionNativeOperationError,
            apply_suppression_mutations,
        )

        class NonCallableGetObject:
            getObject = "not_callable"

        with self.assertRaises(SuppressionNativeOperationError):
            apply_suppression_mutations(NonCallableGetObject(), [])


class NativeErrorHandlingTests(unittest.TestCase):
    def test_get_object_exception_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionNativeOperationError,
            apply_suppression_mutations,
        )

        class FailingGetObject:
            def getObject(self, name: str) -> None:
                raise RuntimeError("internal resolve failure")

        with self.assertRaises(SuppressionNativeOperationError):
            apply_suppression_mutations(FailingGetObject(), [_mutation("Feature", True)])

    def test_get_object_exception_is_chained(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionNativeOperationError,
            apply_suppression_mutations,
        )

        original = RuntimeError("internal resolve failure")

        class FailingGetObject:
            def getObject(self, name: str) -> None:
                raise original

        try:
            apply_suppression_mutations(FailingGetObject(), [_mutation("Feature", True)])
            self.fail("expected SuppressionNativeOperationError")
        except SuppressionNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_get_object_failure_message_identifies_index_and_object(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionNativeOperationError,
            apply_suppression_mutations,
        )

        class FailingGetObject:
            def getObject(self, name: str) -> None:
                raise RuntimeError("boom")

        try:
            apply_suppression_mutations(FailingGetObject(), [_mutation("Widget", True)])
            self.fail("expected SuppressionNativeOperationError")
        except SuppressionNativeOperationError as exc:
            self.assertIn("suppression[0]", str(exc))
            self.assertIn("Widget", str(exc))

    def test_properties_list_attribute_error_raises_unsupported_target_error(self) -> None:
        from parametron_freecad.execution.suppression import (
            UnsupportedSuppressionTargetError,
            apply_suppression_mutations,
        )

        class TargetPropertiesListAttributeMissing:
            pass

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetPropertiesListAttributeMissing()

        with self.assertRaises(UnsupportedSuppressionTargetError):
            apply_suppression_mutations(doc, [_mutation("Feature", True)])

    def test_properties_list_generic_error_raises_native_operation_error_with_cause(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionNativeOperationError,
            apply_suppression_mutations,
        )

        original = RuntimeError("properties inspection failure")

        class TargetPropertiesListRaises:
            @property
            def PropertiesList(self) -> list[str]:
                raise original

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetPropertiesListRaises()

        try:
            apply_suppression_mutations(doc, [_mutation("Feature", True)])
            self.fail("expected SuppressionNativeOperationError")
        except SuppressionNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_properties_list_contains_check_error_raises_native_operation_error_with_cause(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionNativeOperationError,
            apply_suppression_mutations,
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
            apply_suppression_mutations(doc, [_mutation("Feature", True)])
            self.fail("expected SuppressionNativeOperationError")
        except SuppressionNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_get_type_id_call_error_raises_native_operation_error_with_cause(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionNativeOperationError,
            apply_suppression_mutations,
        )

        original = RuntimeError("type inspection failure")

        class TargetTypeInspectionRaises:
            PropertiesList = ["Suppressed"]

            def getTypeIdOfProperty(self, name: str) -> str:
                raise original

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetTypeInspectionRaises()

        try:
            apply_suppression_mutations(doc, [_mutation("Feature", True)])
            self.fail("expected SuppressionNativeOperationError")
        except SuppressionNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_suppressed_write_error_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionNativeOperationError,
            apply_suppression_mutations,
        )

        class RejectingTarget:
            PropertiesList = ["Suppressed"]

            def getTypeIdOfProperty(self, name: str) -> str:
                return "App::PropertyBool"

            def __setattr__(self, name: str, value: object) -> None:
                raise RuntimeError("read-only native property")

        doc = _FakeDocument()
        doc._objects["Feature"] = RejectingTarget()

        with self.assertRaises(SuppressionNativeOperationError):
            apply_suppression_mutations(doc, [_mutation("Feature", True)])

    def test_suppressed_write_error_is_chained(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionNativeOperationError,
            apply_suppression_mutations,
        )

        original = RuntimeError("read-only native property")

        class RejectingTarget:
            PropertiesList = ["Suppressed"]

            def getTypeIdOfProperty(self, name: str) -> str:
                return "App::PropertyBool"

            def __setattr__(self, name: str, value: object) -> None:
                raise original

        doc = _FakeDocument()
        doc._objects["Feature"] = RejectingTarget()

        try:
            apply_suppression_mutations(doc, [_mutation("Feature", True)])
            self.fail("expected SuppressionNativeOperationError")
        except SuppressionNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_suppressed_write_error_message_identifies_index_and_object(self) -> None:
        from parametron_freecad.execution.suppression import (
            SuppressionNativeOperationError,
            apply_suppression_mutations,
        )

        class RejectingTarget:
            PropertiesList = ["Suppressed"]

            def getTypeIdOfProperty(self, name: str) -> str:
                return "App::PropertyBool"

            def __setattr__(self, name: str, value: object) -> None:
                raise RuntimeError("read-only")

        doc = _FakeDocument()
        doc._objects["Good"] = _FakeTarget()
        doc._objects["Bad"] = RejectingTarget()

        try:
            apply_suppression_mutations(doc, [
                _mutation("Good", True),
                _mutation("Bad", False),
            ])
            self.fail("expected SuppressionNativeOperationError")
        except SuppressionNativeOperationError as exc:
            self.assertIn("suppression[1]", str(exc))
            self.assertIn("Bad", str(exc))


if __name__ == "__main__":
    unittest.main()
