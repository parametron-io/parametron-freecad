"""Unit tests for parametron_freecad.execution.post_mutation_validity.

Uses fakes/test doubles only. No FreeCAD import is required or performed.
Real-FreeCAD post-mutation validity and dependency evidence against the
committed PartDesign fixture (and a test-owned empty Body) is covered
separately in ``tests/test_post_mutation_validity_real_fixtures.py``.
"""

from __future__ import annotations

import unittest
from typing import Any


class _FakeDocument:
    """Fake FreeCAD document that resolves objects from a pre-populated dict."""

    def __init__(self) -> None:
        self._objects: dict[str, Any] = {}

    def getObject(self, name: str) -> Any:
        return self._objects.get(name)


class _FakeShape:
    """Fake native Shape supporting isNull/isValid/Solids by default."""

    def __init__(
        self,
        *,
        is_null: bool = False,
        is_valid: bool = True,
        solids: Any = (),
    ) -> None:
        self._is_null = is_null
        self._is_valid = is_valid
        self.Solids = solids

    def isNull(self) -> bool:
        return self._is_null

    def isValid(self) -> bool:
        return self._is_valid


class _FakeBody:
    """Fake native PartDesign::Body target."""

    def __init__(self, *, shape: Any = None, in_list: Any = (), out_list: Any = ()) -> None:
        self.Shape = shape if shape is not None else _FakeShape()
        self.InList = list(in_list)
        self.OutList = list(out_list)

    def isDerivedFrom(self, type_id: str) -> bool:
        return type_id == "PartDesign::Body"


class _FakeRelated:
    def __init__(self, name: str) -> None:
        self.Name = name


class PublicApiTests(unittest.TestCase):
    def test_functions_are_exported(self) -> None:
        from parametron_freecad.execution import post_mutation_validity

        for name in ["inspect_post_mutation_validity", "inspect_native_dependencies"]:
            with self.subTest(name=name):
                self.assertIn(name, post_mutation_validity.__all__)

    def test_error_classes_are_exported(self) -> None:
        from parametron_freecad.execution import post_mutation_validity

        for name in [
            "PostMutationValidityError",
            "NativeValidityEvidenceUnavailableError",
            "NativeValidityInspectionError",
            "InvalidNativeCadStateError",
        ]:
            with self.subTest(name=name):
                self.assertIn(name, post_mutation_validity.__all__)

    def test_evidence_classes_are_exported(self) -> None:
        from parametron_freecad.execution import post_mutation_validity

        for name in ["NativeShapeHealthEvidence", "NativeDependencyEvidence"]:
            with self.subTest(name=name):
                self.assertIn(name, post_mutation_validity.__all__)

    def test_error_hierarchy(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            InvalidNativeCadStateError,
            NativeValidityEvidenceUnavailableError,
            NativeValidityInspectionError,
            PostMutationValidityError,
        )

        self.assertTrue(issubclass(PostMutationValidityError, ValueError))
        self.assertTrue(
            issubclass(NativeValidityEvidenceUnavailableError, PostMutationValidityError)
        )
        self.assertTrue(
            issubclass(NativeValidityInspectionError, PostMutationValidityError)
        )
        self.assertTrue(issubclass(InvalidNativeCadStateError, PostMutationValidityError))

    def test_import_does_not_require_freecad(self) -> None:
        import sys

        sys.modules.pop("parametron_freecad.execution.post_mutation_validity", None)
        import parametron_freecad.execution.post_mutation_validity  # noqa: F401

        self.assertNotIn("FreeCAD", sys.modules)


class HealthyShapeEvidenceTests(unittest.TestCase):
    def test_healthy_body_returns_shape_health_evidence(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeShapeHealthEvidence,
            inspect_post_mutation_validity,
        )

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(
            shape=_FakeShape(is_null=False, is_valid=True, solids=[object(), object()])
        )

        evidence = inspect_post_mutation_validity(doc, "Body")

        self.assertEqual(
            evidence,
            NativeShapeHealthEvidence(
                object_name="Body", is_null=False, is_valid=True, solid_count=2
            ),
        )

    def test_evidence_is_immutable(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeShapeHealthEvidence,
        )

        evidence = NativeShapeHealthEvidence(
            object_name="Body", is_null=False, is_valid=True, solid_count=1
        )
        with self.assertRaises(AttributeError):
            evidence.solid_count = 5  # type: ignore[misc]

    def test_zero_solid_count_is_not_rejected(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_post_mutation_validity,
        )

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(
            shape=_FakeShape(is_null=False, is_valid=True, solids=[])
        )

        evidence = inspect_post_mutation_validity(doc, "Body")
        self.assertEqual(evidence.solid_count, 0)

    def test_multi_solid_count_is_not_rejected(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_post_mutation_validity,
        )

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(
            shape=_FakeShape(is_null=False, is_valid=True, solids=[object()] * 5)
        )

        evidence = inspect_post_mutation_validity(doc, "Body")
        self.assertEqual(evidence.solid_count, 5)

    def test_object_name_is_requested_name_not_native_name(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_post_mutation_validity,
        )

        doc = _FakeDocument()
        doc._objects["RequestedName"] = _FakeBody()

        evidence = inspect_post_mutation_validity(doc, "RequestedName")
        self.assertEqual(evidence.object_name, "RequestedName")


class ExactNativeObjectLookupTests(unittest.TestCase):
    def test_document_missing_get_object_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        class NoGetObject:
            pass

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(NoGetObject(), "Body")

    def test_document_with_non_callable_get_object_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        class NonCallableGetObject:
            getObject = "not_callable"

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(NonCallableGetObject(), "Body")

    def test_get_object_raising_raises_inspection_error_with_cause(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityInspectionError,
            inspect_post_mutation_validity,
        )

        original = RuntimeError("internal resolve failure")

        class FailingGetObject:
            def getObject(self, name: str) -> Any:
                raise original

        try:
            inspect_post_mutation_validity(FailingGetObject(), "Body")
            self.fail("expected NativeValidityInspectionError")
        except NativeValidityInspectionError as exc:
            self.assertIs(exc.__cause__, original)

    def test_exact_lookup_returning_none_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(_FakeDocument(), "Missing")

    def test_successful_exact_lookup_receives_unmodified_name(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_post_mutation_validity,
        )

        calls: list[str] = []

        class RecordingDocument:
            def getObject(self, name: str) -> Any:
                calls.append(name)
                return _FakeBody()

        inspect_post_mutation_validity(RecordingDocument(), "Exact.Name-123")
        self.assertEqual(calls, ["Exact.Name-123"])

    def test_diagnostic_identifies_requested_object_name(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        try:
            inspect_post_mutation_validity(_FakeDocument(), "Gone")
            self.fail("expected NativeValidityEvidenceUnavailableError")
        except NativeValidityEvidenceUnavailableError as exc:
            self.assertIn("Gone", str(exc))


class SupportedTargetTypeEvidenceTests(unittest.TestCase):
    def test_missing_is_derived_from_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        class TargetWithoutTypeInspection:
            Shape = _FakeShape()

        doc = _FakeDocument()
        doc._objects["Body"] = TargetWithoutTypeInspection()

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(doc, "Body")

    def test_non_callable_is_derived_from_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        class TargetWithNonCallableTypeInspection:
            isDerivedFrom = "not-callable"
            Shape = _FakeShape()

        doc = _FakeDocument()
        doc._objects["Body"] = TargetWithNonCallableTypeInspection()

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(doc, "Body")

    def test_is_derived_from_raising_raises_inspection_error_with_cause(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityInspectionError,
            inspect_post_mutation_validity,
        )

        original = RuntimeError("type inspection failure")

        class TargetTypeInspectionRaises:
            Shape = _FakeShape()

            def isDerivedFrom(self, type_id: str) -> bool:
                raise original

        doc = _FakeDocument()
        doc._objects["Body"] = TargetTypeInspectionRaises()

        try:
            inspect_post_mutation_validity(doc, "Body")
            self.fail("expected NativeValidityInspectionError")
        except NativeValidityInspectionError as exc:
            self.assertIs(exc.__cause__, original)

    def test_target_not_reporting_body_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        class NotABody:
            Shape = _FakeShape()

            def isDerivedFrom(self, type_id: str) -> bool:
                return False

        doc = _FakeDocument()
        doc._objects["Sketch"] = NotABody()

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(doc, "Sketch")

    def test_supported_partdesign_body_passes_type_check(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_post_mutation_validity,
        )

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody()

        # Does not raise: type evidence is supported and matches.
        inspect_post_mutation_validity(doc, "Body")


class ShapeEvidenceAvailabilityTests(unittest.TestCase):
    def test_missing_shape_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        class BodyWithoutShape:
            def isDerivedFrom(self, type_id: str) -> bool:
                return True

        doc = _FakeDocument()
        doc._objects["Body"] = BodyWithoutShape()

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(doc, "Body")

    def test_none_shape_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        class BodyWithNoneShape:
            Shape = None

            def isDerivedFrom(self, type_id: str) -> bool:
                return True

        doc = _FakeDocument()
        doc._objects["Body"] = BodyWithNoneShape()

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(doc, "Body")

    def test_missing_is_null_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        class ShapeWithoutIsNull:
            def isValid(self) -> bool:
                return True

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=ShapeWithoutIsNull())

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(doc, "Body")

    def test_missing_is_valid_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        class ShapeWithoutIsValid:
            def isNull(self) -> bool:
                return False

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=ShapeWithoutIsValid())

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(doc, "Body")

    def test_missing_solids_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        class ShapeWithoutSolids:
            def isNull(self) -> bool:
                return False

            def isValid(self) -> bool:
                return True

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=ShapeWithoutSolids())

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(doc, "Body")

    def test_non_boolean_is_null_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_post_mutation_validity,
        )

        class ShapeWithNonBooleanIsNull:
            def isNull(self) -> Any:
                return 0

            def isValid(self) -> bool:
                return True

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=ShapeWithNonBooleanIsNull())

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_post_mutation_validity(doc, "Body")

    def test_solids_without_len_raises_inspection_error(self) -> None:
        # len() on an object without __len__ raises TypeError inside the
        # implementation: a native inspection failure (the attribute is
        # present but the operation on it fails), not missing evidence.
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityInspectionError,
            inspect_post_mutation_validity,
        )

        class FakeSolidsWithoutLen:
            pass

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(
            shape=_FakeShape(is_null=False, is_valid=True, solids=FakeSolidsWithoutLen())
        )

        with self.assertRaises(NativeValidityInspectionError):
            inspect_post_mutation_validity(doc, "Body")


class NativeOperationFailureTests(unittest.TestCase):
    def test_is_null_raising_raises_inspection_error_with_cause(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityInspectionError,
            inspect_post_mutation_validity,
        )

        original = RuntimeError("isNull failed")

        class ShapeIsNullRaises:
            def isNull(self) -> bool:
                raise original

            def isValid(self) -> bool:
                return True

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=ShapeIsNullRaises())

        try:
            inspect_post_mutation_validity(doc, "Body")
            self.fail("expected NativeValidityInspectionError")
        except NativeValidityInspectionError as exc:
            self.assertIs(exc.__cause__, original)

    def test_is_valid_raising_raises_inspection_error_with_cause(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityInspectionError,
            inspect_post_mutation_validity,
        )

        original = RuntimeError("isValid failed")

        class ShapeIsValidRaises:
            def isNull(self) -> bool:
                return False

            def isValid(self) -> bool:
                raise original

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=ShapeIsValidRaises())

        try:
            inspect_post_mutation_validity(doc, "Body")
            self.fail("expected NativeValidityInspectionError")
        except NativeValidityInspectionError as exc:
            self.assertIs(exc.__cause__, original)

    def test_solids_len_raising_raises_inspection_error_with_cause(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityInspectionError,
            inspect_post_mutation_validity,
        )

        original = RuntimeError("Solids inspection failed")

        class RaisingLenSolids:
            def __len__(self) -> int:
                raise original

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(
            shape=_FakeShape(is_null=False, is_valid=True, solids=RaisingLenSolids())
        )

        try:
            inspect_post_mutation_validity(doc, "Body")
            self.fail("expected NativeValidityInspectionError")
        except NativeValidityInspectionError as exc:
            self.assertIs(exc.__cause__, original)

    def test_diagnostic_is_deterministic_across_repeated_calls(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityInspectionError,
            inspect_post_mutation_validity,
        )

        original = RuntimeError("isValid failed")

        class ShapeIsValidRaises:
            def isNull(self) -> bool:
                return False

            def isValid(self) -> bool:
                raise original

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=ShapeIsValidRaises())

        messages: list[str] = []
        types: list[type] = []
        for _ in range(2):
            try:
                inspect_post_mutation_validity(doc, "Body")
            except NativeValidityInspectionError as exc:
                messages.append(str(exc))
                types.append(type(exc))

        self.assertEqual(messages[0], messages[1])
        self.assertEqual(types[0], types[1])


class ProvenInvalidStateTests(unittest.TestCase):
    def test_null_shape_raises_invalid_state_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            InvalidNativeCadStateError,
            inspect_post_mutation_validity,
        )

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=_FakeShape(is_null=True, is_valid=True))

        with self.assertRaises(InvalidNativeCadStateError):
            inspect_post_mutation_validity(doc, "Body")

    def test_invalid_shape_raises_invalid_state_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            InvalidNativeCadStateError,
            inspect_post_mutation_validity,
        )

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=_FakeShape(is_null=False, is_valid=False))

        with self.assertRaises(InvalidNativeCadStateError):
            inspect_post_mutation_validity(doc, "Body")

    def test_null_shape_message_identifies_object_and_null_state(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            InvalidNativeCadStateError,
            inspect_post_mutation_validity,
        )

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=_FakeShape(is_null=True, is_valid=True))

        try:
            inspect_post_mutation_validity(doc, "Body")
            self.fail("expected InvalidNativeCadStateError")
        except InvalidNativeCadStateError as exc:
            self.assertIn("Body", str(exc))
            self.assertIn("null", str(exc))

    def test_invalid_shape_message_identifies_object_and_invalid_state(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            InvalidNativeCadStateError,
            inspect_post_mutation_validity,
        )

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=_FakeShape(is_null=False, is_valid=False))

        try:
            inspect_post_mutation_validity(doc, "Body")
            self.fail("expected InvalidNativeCadStateError")
        except InvalidNativeCadStateError as exc:
            self.assertIn("Body", str(exc))
            self.assertIn("invalid", str(exc))


class InvalidStatePrecedenceTests(unittest.TestCase):
    """Once native evidence has proved invalidity, later evidence must not mask it.

    A state positively proven invalid by native evidence must remain
    classified as invalid rather than being replaced by an unrelated
    evidence-unavailable or inspection-failure classification produced by
    evidence that is no longer necessary once invalidity is established.
    """

    def test_null_shape_precedes_unavailable_is_valid_evidence(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            InvalidNativeCadStateError,
            inspect_post_mutation_validity,
        )

        class ShapeNullWithoutIsValid:
            def isNull(self) -> bool:
                return True

            # Deliberately no isValid: unavailable once nullity is proven.

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=ShapeNullWithoutIsValid())

        with self.assertRaises(InvalidNativeCadStateError):
            inspect_post_mutation_validity(doc, "Body")

    def test_null_shape_precedes_raising_is_valid_evidence(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            InvalidNativeCadStateError,
            inspect_post_mutation_validity,
        )

        class ShapeNullWithRaisingIsValid:
            def isNull(self) -> bool:
                return True

            def isValid(self) -> bool:
                raise RuntimeError("BRepCheck_Analyzer::Init() - NULL shape")

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=ShapeNullWithRaisingIsValid())

        with self.assertRaises(InvalidNativeCadStateError):
            inspect_post_mutation_validity(doc, "Body")

    def test_null_shape_precedes_unavailable_solids_evidence(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            InvalidNativeCadStateError,
            inspect_post_mutation_validity,
        )

        class ShapeNullWithRaisingIsValidNoSolids:
            def isNull(self) -> bool:
                return True

            def isValid(self) -> bool:
                raise RuntimeError("null shape")

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=ShapeNullWithRaisingIsValidNoSolids())

        with self.assertRaises(InvalidNativeCadStateError):
            inspect_post_mutation_validity(doc, "Body")

    def test_is_valid_false_precedes_unavailable_solids_evidence(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            InvalidNativeCadStateError,
            inspect_post_mutation_validity,
        )

        class ShapeInvalidWithoutSolids:
            def isNull(self) -> bool:
                return False

            def isValid(self) -> bool:
                return False

            # Deliberately no Solids: unavailable once invalidity is proven.

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(shape=ShapeInvalidWithoutSolids())

        with self.assertRaises(InvalidNativeCadStateError):
            inspect_post_mutation_validity(doc, "Body")

    def test_is_valid_false_precedes_raising_solids_evidence(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            InvalidNativeCadStateError,
            inspect_post_mutation_validity,
        )

        class RaisingSolids:
            def __len__(self) -> int:
                raise RuntimeError("Solids inspection failed")

        doc = _FakeDocument()
        doc._objects["Body"] = _FakeBody(
            shape=_FakeShape(is_null=False, is_valid=False, solids=RaisingSolids())
        )

        with self.assertRaises(InvalidNativeCadStateError):
            inspect_post_mutation_validity(doc, "Body")


class DependencyEvidenceTests(unittest.TestCase):
    def test_exact_target_lookup_receives_unmodified_name(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_native_dependencies,
        )

        calls: list[str] = []

        class RecordingDocument:
            def getObject(self, name: str) -> Any:
                calls.append(name)
                return _FakeBody()

        inspect_native_dependencies(RecordingDocument(), "Exact.Name-123")
        self.assertEqual(calls, ["Exact.Name-123"])

    def test_missing_target_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_native_dependencies,
        )

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_native_dependencies(_FakeDocument(), "Missing")

    def test_empty_relationships_return_empty_tuples(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeDependencyEvidence,
            inspect_native_dependencies,
        )

        doc = _FakeDocument()
        doc._objects["Marker"] = _FakeBody(in_list=[], out_list=[])

        evidence = inspect_native_dependencies(doc, "Marker")
        self.assertEqual(
            evidence,
            NativeDependencyEvidence(
                object_name="Marker",
                dependent_object_names=(),
                dependency_object_names=(),
            ),
        )

    def test_in_list_maps_to_dependents_out_list_maps_to_dependencies(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_native_dependencies,
        )

        doc = _FakeDocument()
        doc._objects["Feature"] = _FakeBody(
            in_list=[_FakeRelated("Consumer")],
            out_list=[_FakeRelated("Dependency")],
        )

        evidence = inspect_native_dependencies(doc, "Feature")
        self.assertEqual(evidence.dependent_object_names, ("Consumer",))
        self.assertEqual(evidence.dependency_object_names, ("Dependency",))

    def test_multiple_relationships_are_sorted_lexically(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_native_dependencies,
        )

        doc = _FakeDocument()
        doc._objects["Feature"] = _FakeBody(
            in_list=[_FakeRelated("Zulu"), _FakeRelated("Alpha"), _FakeRelated("Mike")],
            out_list=[_FakeRelated("Yankee"), _FakeRelated("Bravo")],
        )

        evidence = inspect_native_dependencies(doc, "Feature")
        self.assertEqual(evidence.dependent_object_names, ("Alpha", "Mike", "Zulu"))
        self.assertEqual(evidence.dependency_object_names, ("Bravo", "Yankee"))

    def test_duplicate_related_objects_are_deduplicated(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_native_dependencies,
        )

        doc = _FakeDocument()
        doc._objects["Feature"] = _FakeBody(
            in_list=[_FakeRelated("Same"), _FakeRelated("Same")],
            out_list=[_FakeRelated("Other"), _FakeRelated("Other"), _FakeRelated("Other")],
        )

        evidence = inspect_native_dependencies(doc, "Feature")
        self.assertEqual(evidence.dependent_object_names, ("Same",))
        self.assertEqual(evidence.dependency_object_names, ("Other",))

    def test_input_order_does_not_affect_output(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_native_dependencies,
        )

        doc_a = _FakeDocument()
        doc_a._objects["Feature"] = _FakeBody(
            in_list=[_FakeRelated("Zulu"), _FakeRelated("Alpha")]
        )
        doc_b = _FakeDocument()
        doc_b._objects["Feature"] = _FakeBody(
            in_list=[_FakeRelated("Alpha"), _FakeRelated("Zulu")]
        )

        evidence_a = inspect_native_dependencies(doc_a, "Feature")
        evidence_b = inspect_native_dependencies(doc_b, "Feature")
        self.assertEqual(evidence_a.dependent_object_names, evidence_b.dependent_object_names)

    def test_evidence_tuple_output_is_deterministic_across_repeated_calls(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_native_dependencies,
        )

        doc = _FakeDocument()
        doc._objects["Feature"] = _FakeBody(
            in_list=[_FakeRelated("Zulu"), _FakeRelated("Alpha")],
            out_list=[_FakeRelated("Bravo")],
        )

        first = inspect_native_dependencies(doc, "Feature")
        second = inspect_native_dependencies(doc, "Feature")
        self.assertEqual(first, second)

    def test_missing_in_list_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_native_dependencies,
        )

        class TargetWithoutInList:
            OutList = []

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetWithoutInList()

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_native_dependencies(doc, "Feature")

    def test_missing_out_list_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_native_dependencies,
        )

        class TargetWithoutOutList:
            InList = []

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetWithoutOutList()

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_native_dependencies(doc, "Feature")

    def test_non_iterable_relationship_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_native_dependencies,
        )

        doc = _FakeDocument()
        target = _FakeBody()
        target.InList = 42
        doc._objects["Feature"] = target

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_native_dependencies(doc, "Feature")

    def test_unconstructible_iterator_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_native_dependencies,
        )

        class UniterableInList:
            def __iter__(self):
                raise RuntimeError("cannot construct iterator")

        doc = _FakeDocument()
        target = _FakeBody()
        target.InList = UniterableInList()
        doc._objects["Feature"] = target

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_native_dependencies(doc, "Feature")

    def test_iteration_raising_partway_raises_inspection_error_with_cause(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityInspectionError,
            inspect_native_dependencies,
        )

        original = RuntimeError("iteration failed partway")

        class FailingPartwayIterator:
            def __init__(self) -> None:
                self._yielded = False

            def __iter__(self):
                return self

            def __next__(self):
                if not self._yielded:
                    self._yielded = True
                    return _FakeRelated("First")
                raise original

        doc = _FakeDocument()
        target = _FakeBody()
        target.InList = FailingPartwayIterator()
        doc._objects["Feature"] = target

        try:
            inspect_native_dependencies(doc, "Feature")
            self.fail("expected NativeValidityInspectionError")
        except NativeValidityInspectionError as exc:
            self.assertIs(exc.__cause__, original)

    def test_related_object_missing_name_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_native_dependencies,
        )

        class RelatedWithoutName:
            pass

        doc = _FakeDocument()
        doc._objects["Feature"] = _FakeBody(in_list=[RelatedWithoutName()])

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_native_dependencies(doc, "Feature")

    def test_related_object_empty_name_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_native_dependencies,
        )

        doc = _FakeDocument()
        doc._objects["Feature"] = _FakeBody(in_list=[_FakeRelated("")])

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_native_dependencies(doc, "Feature")

    def test_related_object_non_string_name_raises_unavailable_error(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
            inspect_native_dependencies,
        )

        doc = _FakeDocument()
        doc._objects["Feature"] = _FakeBody(in_list=[_FakeRelated(123)])  # type: ignore[arg-type]

        with self.assertRaises(NativeValidityEvidenceUnavailableError):
            inspect_native_dependencies(doc, "Feature")

    def test_relationship_inspection_raising_raises_inspection_error_with_cause(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityInspectionError,
            inspect_native_dependencies,
        )

        original = RuntimeError("InList access failed")

        class TargetInListRaises:
            OutList = []

            @property
            def InList(self) -> Any:
                raise original

        doc = _FakeDocument()
        doc._objects["Feature"] = TargetInListRaises()

        try:
            inspect_native_dependencies(doc, "Feature")
            self.fail("expected NativeValidityInspectionError")
        except NativeValidityInspectionError as exc:
            self.assertIs(exc.__cause__, original)

    def test_evidence_is_immutable(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            NativeDependencyEvidence,
        )

        evidence = NativeDependencyEvidence(
            object_name="Feature",
            dependent_object_names=(),
            dependency_object_names=(),
        )
        with self.assertRaises(AttributeError):
            evidence.dependent_object_names = ("X",)  # type: ignore[misc]


class ReadOnlyBehaviorTests(unittest.TestCase):
    """Proves the inspection functions never perform lifecycle or mutation.

    Unintended operations raise loudly if the production code ever calls
    them; both validity and dependency inspection are exercised.
    """

    class _NoMutationBody:
        def __init__(self) -> None:
            self.Shape = _FakeShape(is_null=False, is_valid=True, solids=[object()])
            self.InList: list[Any] = []
            self.OutList: list[Any] = []

        def isDerivedFrom(self, type_id: str) -> bool:
            return type_id == "PartDesign::Body"

        def recompute(self) -> None:
            raise AssertionError("target.recompute must not be called")

        def save(self) -> None:
            raise AssertionError("target.save must not be called")

        def __setattr__(self, name: str, value: Any) -> None:
            if name in {"Shape", "InList", "OutList"} and name not in self.__dict__:
                object.__setattr__(self, name, value)
                return
            if name in {"Shape", "InList", "OutList"}:
                raise AssertionError(f"target.{name} must not be reassigned")
            object.__setattr__(self, name, value)

    class _NoMutationDocument:
        def __init__(self, target: Any) -> None:
            self._target = target

        def getObject(self, name: str) -> Any:
            return self._target

        def recompute(self) -> None:
            raise AssertionError("document.recompute must not be called")

        def save(self) -> None:
            raise AssertionError("document.save must not be called")

        def saveAs(self, path: str) -> None:
            raise AssertionError("document.saveAs must not be called")

        def close(self) -> None:
            raise AssertionError("document.close must not be called")

        def removeObject(self, name: str) -> None:
            raise AssertionError("document.removeObject must not be called")

    def test_validity_inspection_does_not_mutate_document_or_target(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_post_mutation_validity,
        )

        target = self._NoMutationBody()
        doc = self._NoMutationDocument(target)

        inspect_post_mutation_validity(doc, "Body")

    def test_dependency_inspection_does_not_mutate_document_or_target(self) -> None:
        from parametron_freecad.execution.post_mutation_validity import (
            inspect_native_dependencies,
        )

        target = self._NoMutationBody()
        doc = self._NoMutationDocument(target)

        inspect_native_dependencies(doc, "Body")


if __name__ == "__main__":
    unittest.main()
