"""Unit tests for parametron_freecad.execution.deletion.

Uses fakes/test doubles only. No FreeCAD import is required or performed.
Real-FreeCAD deletion behavior against the committed PartDesign fixture is
covered separately in ``tests/test_deletion_real_fixtures.py``.
"""

from __future__ import annotations

import unittest
from typing import Any


def _mutation(object_name: Any) -> dict[str, Any]:
    return {"object": object_name}


class _FakeShape:
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
    """Fake native PartDesign::Body target for document-level validity."""

    def __init__(
        self,
        name: str,
        *,
        shape: Any = None,
        in_list: Any = (),
        out_list: Any = (),
    ) -> None:
        self.Name = name
        self.Shape = shape if shape is not None else _FakeShape()
        self.InList = list(in_list)
        self.OutList = list(out_list)

    def isDerivedFrom(self, type_id: str) -> bool:
        return type_id == "PartDesign::Body"


class _FakeRelated:
    def __init__(self, name: str) -> None:
        self.Name = name


class _FakeTarget:
    """Fake native object supporting InList/OutList for dependency inspection."""

    def __init__(self, name: str, *, in_list: Any = (), out_list: Any = ()) -> None:
        self.Name = name
        self.InList = list(in_list)
        self.OutList = list(out_list)

    def isDerivedFrom(self, type_id: str) -> bool:
        return False


class _FakeDocument:
    """Fake FreeCAD document with exact getObject/removeObject/recompute/Objects.

    ``removeObject`` actually removes the target from the backing store, and
    a healthy default ``PartDesign::Body`` (``HealthyBody``) is always present
    so that recompute + document-level validity can succeed by default. Tests
    that need to prove validity/recompute failure override the relevant
    pieces explicitly.
    """

    def __init__(self, *, include_healthy_body: bool = True) -> None:
        self._objects: dict[str, Any] = {}
        self.remove_object_calls: list[str] = []
        self.recompute_calls: int = 0
        if include_healthy_body:
            self._objects["HealthyBody"] = _FakeBody("HealthyBody")

    def add(self, target: Any) -> None:
        self._objects[target.Name] = target

    def getObject(self, name: str) -> Any:
        return self._objects.get(name)

    def removeObject(self, name: str) -> None:
        self.remove_object_calls.append(name)
        self._objects.pop(name, None)

    def recompute(self) -> None:
        self.recompute_calls += 1

    @property
    def Objects(self) -> list[Any]:
        return list(self._objects.values())


class PublicApiTests(unittest.TestCase):
    def test_apply_deletion_mutations_is_exported(self) -> None:
        from parametron_freecad.execution import deletion

        self.assertIn("apply_deletion_mutations", deletion.__all__)

    def test_error_classes_are_exported(self) -> None:
        from parametron_freecad.execution import deletion

        for name in [
            "DeletionMutationError",
            "DeletionNativeOperationError",
            "DeletionTargetNotFoundError",
            "DeletionValidityError",
            "UnsafeDeletionTargetError",
        ]:
            with self.subTest(name=name):
                self.assertIn(name, deletion.__all__)

    def test_error_hierarchy(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionMutationError,
            DeletionNativeOperationError,
            DeletionTargetNotFoundError,
            DeletionValidityError,
            UnsafeDeletionTargetError,
        )

        self.assertTrue(issubclass(DeletionMutationError, ValueError))
        self.assertTrue(issubclass(DeletionTargetNotFoundError, DeletionMutationError))
        self.assertTrue(issubclass(UnsafeDeletionTargetError, DeletionMutationError))
        self.assertTrue(issubclass(DeletionNativeOperationError, DeletionMutationError))
        self.assertTrue(issubclass(DeletionValidityError, DeletionMutationError))

    def test_import_does_not_require_freecad(self) -> None:
        import sys

        sys.modules.pop("parametron_freecad.execution.deletion", None)
        import parametron_freecad.execution.deletion  # noqa: F401

        self.assertNotIn("FreeCAD", sys.modules)


class EmptyCollectionTests(unittest.TestCase):
    def test_empty_mutations_succeeds(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        apply_deletion_mutations(_FakeDocument(), [])

    def test_empty_mutations_performs_no_get_object(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        calls: list[str] = []

        class RecordingDocument:
            def getObject(self, name: str) -> None:
                calls.append(name)
                return None

        apply_deletion_mutations(RecordingDocument(), [])
        self.assertEqual(calls, [])

    def test_empty_mutations_performs_no_remove_object(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        class RecordingDocument:
            def removeObject(self, name: str) -> None:
                raise AssertionError("removeObject must not be called for empty input")

        apply_deletion_mutations(RecordingDocument(), [])

    def test_empty_mutations_performs_no_recompute(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        class RecordingDocument:
            def recompute(self) -> None:
                raise AssertionError("recompute must not be called for empty input")

        apply_deletion_mutations(RecordingDocument(), [])

    def test_empty_mutations_does_not_require_get_object_or_remove_object(self) -> None:
        # Empty input must not even require document operations to exist,
        # since no lookup or removal happens.
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        class BareDocument:
            pass

        apply_deletion_mutations(BareDocument(), [])

    def test_empty_mutations_performs_no_validity_inspection(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        class RecordingDocument:
            @property
            def Objects(self) -> list[Any]:
                raise AssertionError("Objects must not be accessed for empty input")

        apply_deletion_mutations(RecordingDocument(), [])


class DocumentOperationAvailabilityTests(unittest.TestCase):
    def test_missing_get_object_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        class NoGetObject:
            def removeObject(self, name: str) -> None:
                pass

        with self.assertRaises(DeletionNativeOperationError):
            apply_deletion_mutations(NoGetObject(), [_mutation("A")])

    def test_non_callable_get_object_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        class NonCallableGetObject:
            getObject = "not_callable"

            def removeObject(self, name: str) -> None:
                pass

        with self.assertRaises(DeletionNativeOperationError):
            apply_deletion_mutations(NonCallableGetObject(), [_mutation("A")])

    def test_failing_get_object_access_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        class FailingGetObjectAccess:
            @property
            def getObject(self) -> Any:
                raise RuntimeError("access failure")

            def removeObject(self, name: str) -> None:
                pass

        with self.assertRaises(DeletionNativeOperationError):
            apply_deletion_mutations(FailingGetObjectAccess(), [_mutation("A")])

    def test_missing_remove_object_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        class NoRemoveObject:
            def getObject(self, name: str) -> Any:
                return _FakeTarget(name)

        with self.assertRaises(DeletionNativeOperationError):
            apply_deletion_mutations(NoRemoveObject(), [_mutation("A")])

    def test_non_callable_remove_object_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        class NonCallableRemoveObject:
            removeObject = "not_callable"

            def getObject(self, name: str) -> Any:
                return _FakeTarget(name)

        with self.assertRaises(DeletionNativeOperationError):
            apply_deletion_mutations(NonCallableRemoveObject(), [_mutation("A")])

    def test_failing_remove_object_access_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        class FailingRemoveObjectAccess:
            def getObject(self, name: str) -> Any:
                return _FakeTarget(name)

            @property
            def removeObject(self) -> Any:
                raise RuntimeError("access failure")

        with self.assertRaises(DeletionNativeOperationError):
            apply_deletion_mutations(FailingRemoveObjectAccess(), [_mutation("A")])

    def test_document_operation_check_happens_before_any_lookup(self) -> None:
        # getObject/removeObject availability is validated once up front, so
        # a document missing removeObject fails even before iterating targets.
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        calls: list[str] = []

        class NoRemoveObjectRecordingGetObject:
            def getObject(self, name: str) -> Any:
                calls.append(name)
                return _FakeTarget(name)

        with self.assertRaises(DeletionNativeOperationError):
            apply_deletion_mutations(
                NoRemoveObjectRecordingGetObject(), [_mutation("A")]
            )
        self.assertEqual(calls, [])


class ExactLookupTests(unittest.TestCase):
    def test_object_string_passed_unchanged_to_get_object(self) -> None:
        # Multiple internal lookups occur (pre-delete resolution, dependency
        # inspection resolution, post-removal confirmation); every one of
        # them must receive the exact caller-supplied string, never a
        # case-normalized, whitespace-trimmed, or otherwise altered variant.
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        calls: list[str] = []

        class RecordingDocument(_FakeDocument):
            def getObject(self, name: str) -> Any:
                calls.append(name)
                return super().getObject(name)

        doc = RecordingDocument()
        doc.add(_FakeTarget("Exact.Name-123"))

        apply_deletion_mutations(doc, [_mutation("Exact.Name-123")])

        self.assertIn("Exact.Name-123", calls)
        self.assertNotIn("exact.name-123", calls)
        self.assertTrue(all(call in ("Exact.Name-123", "HealthyBody") for call in calls))

    def test_missing_target_raises_target_not_found_error(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionTargetNotFoundError,
            apply_deletion_mutations,
        )

        with self.assertRaises(DeletionTargetNotFoundError):
            apply_deletion_mutations(_FakeDocument(), [_mutation("Missing")])

    def test_target_not_found_message_identifies_index_and_object(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionTargetNotFoundError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("A"))

        try:
            apply_deletion_mutations(doc, [_mutation("A"), _mutation("Gone")])
            self.fail("expected DeletionTargetNotFoundError")
        except DeletionTargetNotFoundError as exc:
            self.assertIn("deletion[1]", str(exc))
            self.assertIn("Gone", str(exc))

    def test_missing_target_performs_no_removal(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionTargetNotFoundError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        with self.assertRaises(DeletionTargetNotFoundError):
            apply_deletion_mutations(doc, [_mutation("Missing")])
        self.assertEqual(doc.remove_object_calls, [])

    def test_get_object_exception_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        class FailingGetObject:
            def getObject(self, name: str) -> None:
                raise RuntimeError("internal resolve failure")

            def removeObject(self, name: str) -> None:
                pass

        with self.assertRaises(DeletionNativeOperationError):
            apply_deletion_mutations(FailingGetObject(), [_mutation("A")])

    def test_get_object_exception_is_chained(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        original = RuntimeError("internal resolve failure")

        class FailingGetObject:
            def getObject(self, name: str) -> None:
                raise original

            def removeObject(self, name: str) -> None:
                pass

        try:
            apply_deletion_mutations(FailingGetObject(), [_mutation("A")])
            self.fail("expected DeletionNativeOperationError")
        except DeletionNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)


class NoFallbackLookupRegressionTests(unittest.TestCase):
    """Deletion execution never falls back to non-exact lookup."""

    def test_case_variant_name_is_not_resolved(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionTargetNotFoundError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("Feature"))
        with self.assertRaises(DeletionTargetNotFoundError):
            apply_deletion_mutations(doc, [_mutation("feature")])

    def test_alias_or_label_name_is_not_resolved(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionTargetNotFoundError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("Chamfer001"))
        with self.assertRaises(DeletionTargetNotFoundError):
            apply_deletion_mutations(doc, [_mutation("TerminalChamfer")])


class DependencyInspectionTests(unittest.TestCase):
    def test_in_list_dependents_reject_deletion(self) -> None:
        from parametron_freecad.execution.deletion import (
            UnsafeDeletionTargetError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("BaseSketch", in_list=[_FakeRelated("IntermediatePad")]))

        with self.assertRaises(UnsafeDeletionTargetError):
            apply_deletion_mutations(doc, [_mutation("BaseSketch")])

    def test_rejection_identifies_index_and_object(self) -> None:
        from parametron_freecad.execution.deletion import (
            UnsafeDeletionTargetError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("A"))
        doc.add(_FakeTarget("BaseSketch", in_list=[_FakeRelated("IntermediatePad")]))

        try:
            apply_deletion_mutations(doc, [_mutation("A"), _mutation("BaseSketch")])
            self.fail("expected UnsafeDeletionTargetError")
        except UnsafeDeletionTargetError as exc:
            self.assertIn("deletion[1]", str(exc))
            self.assertIn("BaseSketch", str(exc))

    def test_dependent_names_are_visible_in_diagnostic(self) -> None:
        from parametron_freecad.execution.deletion import (
            UnsafeDeletionTargetError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("BaseSketch", in_list=[_FakeRelated("IntermediatePad")]))

        try:
            apply_deletion_mutations(doc, [_mutation("BaseSketch")])
            self.fail("expected UnsafeDeletionTargetError")
        except UnsafeDeletionTargetError as exc:
            self.assertIn("IntermediatePad", str(exc))

    def test_multiple_dependents_are_all_visible_and_deterministic(self) -> None:
        from parametron_freecad.execution.deletion import (
            UnsafeDeletionTargetError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(
            _FakeTarget(
                "Shared",
                in_list=[_FakeRelated("Zulu"), _FakeRelated("Alpha")],
            )
        )

        try:
            apply_deletion_mutations(doc, [_mutation("Shared")])
            self.fail("expected UnsafeDeletionTargetError")
        except UnsafeDeletionTargetError as exc:
            message = str(exc)
            self.assertIn("Alpha", message)
            self.assertIn("Zulu", message)
            self.assertLess(message.index("Alpha"), message.index("Zulu"))

    def test_unsafe_rejection_performs_no_removal(self) -> None:
        from parametron_freecad.execution.deletion import (
            UnsafeDeletionTargetError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("BaseSketch", in_list=[_FakeRelated("IntermediatePad")]))

        with self.assertRaises(UnsafeDeletionTargetError):
            apply_deletion_mutations(doc, [_mutation("BaseSketch")])
        self.assertEqual(doc.remove_object_calls, [])

    def test_unsafe_rejection_performs_no_recompute(self) -> None:
        from parametron_freecad.execution.deletion import (
            UnsafeDeletionTargetError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("BaseSketch", in_list=[_FakeRelated("IntermediatePad")]))

        with self.assertRaises(UnsafeDeletionTargetError):
            apply_deletion_mutations(doc, [_mutation("BaseSketch")])
        self.assertEqual(doc.recompute_calls, 0)

    def test_unsafe_rejection_performs_no_validity_inspection(self) -> None:
        from parametron_freecad.execution.deletion import (
            UnsafeDeletionTargetError,
            apply_deletion_mutations,
        )

        class TrackingDocument(_FakeDocument):
            @property
            def Objects(self) -> list[Any]:
                raise AssertionError("Objects must not be accessed after unsafe rejection")

        doc = TrackingDocument()
        doc.add(_FakeTarget("BaseSketch", in_list=[_FakeRelated("IntermediatePad")]))

        with self.assertRaises(UnsafeDeletionTargetError):
            apply_deletion_mutations(doc, [_mutation("BaseSketch")])

    def test_out_list_alone_does_not_block_deletion(self) -> None:
        # Outgoing dependency evidence (OutList) must not by itself be
        # treated as a reason to cascade, repair, or reject deletion.
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        doc = _FakeDocument()
        doc.add(_FakeTarget("Feature", out_list=[_FakeRelated("SomeDependency")]))

        apply_deletion_mutations(doc, [_mutation("Feature")])
        self.assertEqual(doc.remove_object_calls, ["Feature"])

    def test_empty_in_list_allows_deletion(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        doc = _FakeDocument()
        doc.add(_FakeTarget("SafeDeleteMarker"))

        apply_deletion_mutations(doc, [_mutation("SafeDeleteMarker")])
        self.assertEqual(doc.remove_object_calls, ["SafeDeleteMarker"])

    def test_dependency_evidence_unavailable_fails_closed(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        class TargetWithoutInList:
            Name = "Feature"
            OutList: list[Any] = []

            def isDerivedFrom(self, type_id: str) -> bool:
                return False

        doc = _FakeDocument()
        doc.add(TargetWithoutInList())

        with self.assertRaises(DeletionNativeOperationError):
            apply_deletion_mutations(doc, [_mutation("Feature")])
        self.assertEqual(doc.remove_object_calls, [])

    def test_dependency_inspection_exception_is_chained(self) -> None:
        # The immediate cause is the post-mutation-validity classification
        # (NativeValidityInspectionError); that classification's own cause
        # preserves the original native exception. Both links matter: the
        # original exception must not be dropped anywhere in the chain.
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityInspectionError,
        )

        original = RuntimeError("InList access failed")

        class TargetInListRaises:
            Name = "Feature"
            OutList: list[Any] = []

            @property
            def InList(self) -> Any:
                raise original

            def isDerivedFrom(self, type_id: str) -> bool:
                return False

        doc = _FakeDocument()
        doc.add(TargetInListRaises())

        try:
            apply_deletion_mutations(doc, [_mutation("Feature")])
            self.fail("expected DeletionNativeOperationError")
        except DeletionNativeOperationError as exc:
            self.assertIsInstance(exc.__cause__, NativeValidityInspectionError)
            self.assertIs(exc.__cause__.__cause__, original)


class NativeRemovalTests(unittest.TestCase):
    def test_remove_object_receives_exact_requested_name(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        doc = _FakeDocument()
        doc.add(_FakeTarget("Exact.Name-123"))

        apply_deletion_mutations(doc, [_mutation("Exact.Name-123")])
        self.assertEqual(doc.remove_object_calls, ["Exact.Name-123"])

    def test_remove_object_invoked_exactly_once(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        doc = _FakeDocument()
        doc.add(_FakeTarget("A"))

        apply_deletion_mutations(doc, [_mutation("A")])
        self.assertEqual(len(doc.remove_object_calls), 1)

    def test_remove_object_exception_raises_native_operation_error(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        original = RuntimeError("native removal failed")

        class FailingRemoveDocument(_FakeDocument):
            def removeObject(self, name: str) -> None:
                raise original

        doc = FailingRemoveDocument()
        doc.add(_FakeTarget("A"))

        try:
            apply_deletion_mutations(doc, [_mutation("A")])
            self.fail("expected DeletionNativeOperationError")
        except DeletionNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_remove_object_exception_message_identifies_index_and_object(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        class FailingRemoveDocument(_FakeDocument):
            def removeObject(self, name: str) -> None:
                raise RuntimeError("boom")

        doc = FailingRemoveDocument()
        doc.add(_FakeTarget("Widget"))

        try:
            apply_deletion_mutations(doc, [_mutation("Widget")])
            self.fail("expected DeletionNativeOperationError")
        except DeletionNativeOperationError as exc:
            self.assertIn("deletion[0]", str(exc))
            self.assertIn("Widget", str(exc))


class PostRemovalConfirmationTests(unittest.TestCase):
    def test_target_actually_absent_continues(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        doc = _FakeDocument()
        doc.add(_FakeTarget("A"))

        # Does not raise: removeObject genuinely removes the object from the
        # backing store, so the post-removal lookup returns None.
        apply_deletion_mutations(doc, [_mutation("A")])

    def test_post_removal_lookup_failure_raises_native_operation_error(self) -> None:
        # Fails exactly the lookup that happens for a name after it has
        # actually been removed, regardless of how many lookups happen
        # before removal (pre-delete resolution, dependency inspection).
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        original = RuntimeError("post-removal lookup failed")

        class FailingConfirmationLookupDocument(_FakeDocument):
            def __init__(self) -> None:
                super().__init__()
                self._removed_names: set[str] = set()

            def removeObject(self, name: str) -> None:
                super().removeObject(name)
                self._removed_names.add(name)

            def getObject(self, name: str) -> Any:
                if name in self._removed_names:
                    raise original
                return super().getObject(name)

        doc = FailingConfirmationLookupDocument()
        doc.add(_FakeTarget("A"))

        try:
            apply_deletion_mutations(doc, [_mutation("A")])
            self.fail("expected DeletionNativeOperationError")
        except DeletionNativeOperationError as exc:
            self.assertIs(exc.__cause__, original)

    def test_target_still_resolving_after_removal_raises_native_operation_error(
        self,
    ) -> None:
        # A successful removeObject call alone is not proof of deletion: if
        # the object still resolves afterward, this must be treated as a
        # controlled native-operation failure.
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        class StubbornDocument(_FakeDocument):
            def removeObject(self, name: str) -> None:
                self.remove_object_calls.append(name)
                # Deliberately does not remove the object from the backing
                # store, simulating removeObject "succeeding" without effect.

        doc = StubbornDocument()
        doc.add(_FakeTarget("A"))

        with self.assertRaises(DeletionNativeOperationError):
            apply_deletion_mutations(doc, [_mutation("A")])

    def test_target_still_resolving_message_identifies_index_and_object(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionNativeOperationError,
            apply_deletion_mutations,
        )

        class StubbornDocument(_FakeDocument):
            def removeObject(self, name: str) -> None:
                self.remove_object_calls.append(name)

        doc = StubbornDocument()
        doc.add(_FakeTarget("Ghost"))

        try:
            apply_deletion_mutations(doc, [_mutation("Ghost")])
            self.fail("expected DeletionNativeOperationError")
        except DeletionNativeOperationError as exc:
            self.assertIn("deletion[0]", str(exc))
            self.assertIn("Ghost", str(exc))


class RecomputeAndValidityTests(unittest.TestCase):
    def test_successful_removal_invokes_recompute_before_validity(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        events: list[str] = []

        class ObservingDocument(_FakeDocument):
            def removeObject(self, name: str) -> None:
                events.append("removeObject")
                super().removeObject(name)

            def recompute(self) -> None:
                events.append("recompute")
                super().recompute()

            @property
            def Objects(self) -> list[Any]:
                events.append("validity")
                return super().Objects

        doc = ObservingDocument()
        doc.add(_FakeTarget("A"))

        apply_deletion_mutations(doc, [_mutation("A")])
        self.assertEqual(events, ["removeObject", "recompute", "validity"])

    def test_full_sequence_is_observed_in_order(self) -> None:
        # Proves the intended macro-sequence: exact lookup(s) precede
        # removeObject; a post-removal exact lookup for the same name
        # happens strictly between removeObject and recompute; recompute
        # happens strictly before document-level validity inspection.
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        events: list[tuple[str, ...]] = []

        class ObservingDocument(_FakeDocument):
            def getObject(self, name: str) -> Any:
                events.append(("getObject", name))
                return super().getObject(name)

            def removeObject(self, name: str) -> None:
                events.append(("removeObject", name))
                super().removeObject(name)

            def recompute(self) -> None:
                events.append(("recompute",))
                super().recompute()

            @property
            def Objects(self) -> list[Any]:
                events.append(("validity",))
                return super().Objects

        doc = ObservingDocument()
        doc.add(_FakeTarget("A"))

        apply_deletion_mutations(doc, [_mutation("A")])

        remove_index = events.index(("removeObject", "A"))
        recompute_index = events.index(("recompute",))
        validity_index = events.index(("validity",))

        lookups_before_remove = [
            event for event in events[:remove_index] if event == ("getObject", "A")
        ]
        self.assertTrue(lookups_before_remove)

        lookups_between_remove_and_recompute = [
            event
            for event in events[remove_index + 1 : recompute_index]
            if event == ("getObject", "A")
        ]
        self.assertEqual(lookups_between_remove_and_recompute, [("getObject", "A")])

        self.assertLess(recompute_index, validity_index)

    def test_recompute_failure_raises_validity_error(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionValidityError,
            apply_deletion_mutations,
        )

        class FailingRecomputeDocument(_FakeDocument):
            def recompute(self) -> None:
                raise RuntimeError("recompute exploded")

        doc = FailingRecomputeDocument()
        doc.add(_FakeTarget("A"))

        with self.assertRaises(DeletionValidityError):
            apply_deletion_mutations(doc, [_mutation("A")])

    def test_recompute_failure_cause_chain_preserved(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionValidityError,
            apply_deletion_mutations,
        )
        from parametron_freecad.execution.document_recompute import (
            DocumentRecomputeError,
        )

        class FailingRecomputeDocument(_FakeDocument):
            def recompute(self) -> None:
                raise RuntimeError("recompute exploded")

        doc = FailingRecomputeDocument()
        doc.add(_FakeTarget("A"))

        try:
            apply_deletion_mutations(doc, [_mutation("A")])
            self.fail("expected DeletionValidityError")
        except DeletionValidityError as exc:
            self.assertIsInstance(exc.__cause__, DocumentRecomputeError)

    def test_recompute_failure_skips_validity_inspection(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionValidityError,
            apply_deletion_mutations,
        )

        class FailingRecomputeDocument(_FakeDocument):
            def recompute(self) -> None:
                raise RuntimeError("recompute exploded")

            @property
            def Objects(self) -> list[Any]:
                raise AssertionError("validity inspection must not run after recompute failure")

        doc = FailingRecomputeDocument()
        doc.add(_FakeTarget("A"))

        with self.assertRaises(DeletionValidityError):
            apply_deletion_mutations(doc, [_mutation("A")])

    def test_recompute_failure_does_not_restore_removed_object(self) -> None:
        # The consumer is destructive: removal already happened before
        # recompute ran, and there is no rollback.
        from parametron_freecad.execution.deletion import (
            DeletionValidityError,
            apply_deletion_mutations,
        )

        class FailingRecomputeDocument(_FakeDocument):
            def recompute(self) -> None:
                raise RuntimeError("recompute exploded")

        doc = FailingRecomputeDocument()
        doc.add(_FakeTarget("A"))

        with self.assertRaises(DeletionValidityError):
            apply_deletion_mutations(doc, [_mutation("A")])
        self.assertIsNone(doc.getObject("A"))

    def test_invalid_post_delete_body_raises_validity_error(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionValidityError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument(include_healthy_body=False)
        doc.add(_FakeTarget("A"))
        doc.add(
            _FakeBody("InvalidBody", shape=_FakeShape(is_null=True, is_valid=True))
        )

        with self.assertRaises(DeletionValidityError):
            apply_deletion_mutations(doc, [_mutation("A")])

    def test_invalid_post_delete_state_cause_chain_preserved(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionValidityError,
            apply_deletion_mutations,
        )
        from parametron_freecad.execution.post_mutation_validity import (
            InvalidNativeCadStateError,
        )

        doc = _FakeDocument(include_healthy_body=False)
        doc.add(_FakeTarget("A"))
        doc.add(
            _FakeBody("InvalidBody", shape=_FakeShape(is_null=True, is_valid=True))
        )

        try:
            apply_deletion_mutations(doc, [_mutation("A")])
            self.fail("expected DeletionValidityError")
        except DeletionValidityError as exc:
            self.assertIsInstance(exc.__cause__, InvalidNativeCadStateError)

    def test_invalid_post_delete_state_does_not_restore_removed_object(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionValidityError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument(include_healthy_body=False)
        doc.add(_FakeTarget("A"))
        doc.add(
            _FakeBody("InvalidBody", shape=_FakeShape(is_null=True, is_valid=True))
        )

        with self.assertRaises(DeletionValidityError):
            apply_deletion_mutations(doc, [_mutation("A")])
        self.assertIsNone(doc.getObject("A"))

    def test_unavailable_validity_evidence_raises_validity_error(self) -> None:
        # Zero supported PartDesign Bodies means required evidence is
        # unavailable, which must fail closed rather than report success.
        from parametron_freecad.execution.deletion import (
            DeletionValidityError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument(include_healthy_body=False)
        doc.add(_FakeTarget("A"))

        with self.assertRaises(DeletionValidityError):
            apply_deletion_mutations(doc, [_mutation("A")])

    def test_unavailable_validity_evidence_cause_chain_preserved(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionValidityError,
            apply_deletion_mutations,
        )
        from parametron_freecad.execution.post_mutation_validity import (
            NativeValidityEvidenceUnavailableError,
        )

        doc = _FakeDocument(include_healthy_body=False)
        doc.add(_FakeTarget("A"))

        try:
            apply_deletion_mutations(doc, [_mutation("A")])
            self.fail("expected DeletionValidityError")
        except DeletionValidityError as exc:
            self.assertIsInstance(exc.__cause__, NativeValidityEvidenceUnavailableError)


class MultipleEntriesOrderingTests(unittest.TestCase):
    def test_caller_order_is_preserved_for_non_lexical_sequence(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        doc = _FakeDocument()
        doc.add(_FakeTarget("C"))
        doc.add(_FakeTarget("A"))
        doc.add(_FakeTarget("B"))

        apply_deletion_mutations(
            doc, [_mutation("C"), _mutation("A"), _mutation("B")]
        )
        self.assertEqual(doc.remove_object_calls, ["C", "A", "B"])

    def test_each_successful_entry_completes_full_cycle_before_next_begins(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        events: list[str] = []

        class ObservingDocument(_FakeDocument):
            def removeObject(self, name: str) -> None:
                events.append(f"remove:{name}")
                super().removeObject(name)

            def recompute(self) -> None:
                events.append("recompute")
                super().recompute()

            @property
            def Objects(self) -> list[Any]:
                events.append("validity")
                return super().Objects

        doc = ObservingDocument()
        doc.add(_FakeTarget("A"))
        doc.add(_FakeTarget("B"))

        apply_deletion_mutations(doc, [_mutation("A"), _mutation("B")])
        self.assertEqual(
            events,
            [
                "remove:A",
                "recompute",
                "validity",
                "remove:B",
                "recompute",
                "validity",
            ],
        )

    def test_earlier_successful_deletion_remains_applied_after_later_failure(
        self,
    ) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionTargetNotFoundError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("A"))

        with self.assertRaises(DeletionTargetNotFoundError):
            apply_deletion_mutations(doc, [_mutation("A"), _mutation("Missing")])

        self.assertIsNone(doc.getObject("A"))
        self.assertEqual(doc.remove_object_calls, ["A"])

    def test_later_entries_not_attempted_after_earlier_failure(self) -> None:
        from parametron_freecad.execution.deletion import (
            DeletionTargetNotFoundError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("B"))

        with self.assertRaises(DeletionTargetNotFoundError):
            apply_deletion_mutations(doc, [_mutation("Missing"), _mutation("B")])

        self.assertIsNotNone(doc.getObject("B"))
        self.assertEqual(doc.remove_object_calls, [])

    def test_unsafe_middle_entry_leaves_target_intact_while_preserving_earlier_success(
        self,
    ) -> None:
        from parametron_freecad.execution.deletion import (
            UnsafeDeletionTargetError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("SafeDeleteMarker"))
        doc.add(_FakeTarget("BaseSketch", in_list=[_FakeRelated("IntermediatePad")]))
        doc.add(_FakeTarget("Never"))

        with self.assertRaises(UnsafeDeletionTargetError):
            apply_deletion_mutations(
                doc,
                [
                    _mutation("SafeDeleteMarker"),
                    _mutation("BaseSketch"),
                    _mutation("Never"),
                ],
            )

        self.assertIsNone(doc.getObject("SafeDeleteMarker"))
        self.assertIsNotNone(doc.getObject("BaseSketch"))
        self.assertIsNotNone(doc.getObject("Never"))
        self.assertEqual(doc.remove_object_calls, ["SafeDeleteMarker"])

    def test_no_hidden_sorting_of_multiple_entries(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        doc = _FakeDocument()
        for name in ("Zulu", "Mike", "Alpha"):
            doc.add(_FakeTarget(name))

        apply_deletion_mutations(
            doc, [_mutation("Zulu"), _mutation("Mike"), _mutation("Alpha")]
        )
        self.assertEqual(doc.remove_object_calls, ["Zulu", "Mike", "Alpha"])

    def test_no_hidden_deduplication_of_duplicate_entries(self) -> None:
        # Not policy for duplicates beyond proving the consumer does not
        # silently collapse caller-repeated entries: the second occurrence
        # of the same object naturally fails as missing since it was already
        # removed by the first occurrence.
        from parametron_freecad.execution.deletion import (
            DeletionTargetNotFoundError,
            apply_deletion_mutations,
        )

        doc = _FakeDocument()
        doc.add(_FakeTarget("A"))

        with self.assertRaises(DeletionTargetNotFoundError):
            apply_deletion_mutations(doc, [_mutation("A"), _mutation("A")])
        self.assertEqual(doc.remove_object_calls, ["A"])


class InputImmutabilityTests(unittest.TestCase):
    def test_mutation_mapping_is_not_mutated(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        doc = _FakeDocument()
        doc.add(_FakeTarget("A"))
        mutation = {"object": "A"}
        snapshot = dict(mutation)

        apply_deletion_mutations(doc, [mutation])

        self.assertEqual(mutation, snapshot)

    def test_mutations_sequence_is_not_reordered(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        doc = _FakeDocument()
        doc.add(_FakeTarget("A"))
        doc.add(_FakeTarget("B"))
        mutations = [_mutation("B"), _mutation("A")]
        before = list(mutations)

        apply_deletion_mutations(doc, mutations)

        self.assertEqual(mutations, before)

    def test_no_policy_fields_injected_into_caller_mapping(self) -> None:
        from parametron_freecad.execution.deletion import apply_deletion_mutations

        doc = _FakeDocument()
        doc.add(_FakeTarget("A"))
        mutation = {"object": "A"}

        apply_deletion_mutations(doc, [mutation])

        self.assertEqual(set(mutation.keys()), {"object"})


if __name__ == "__main__":
    unittest.main()
