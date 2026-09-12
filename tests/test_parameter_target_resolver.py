"""Unit tests for parametron_freecad.execution.parameter_target_resolver."""

from __future__ import annotations

import unittest
from typing import Any


# ---------------------------------------------------------------------------
# Shared fake helpers
# ---------------------------------------------------------------------------


class _StrictFakeDocument:
    """Fake document that records getObject calls.

    Raises AssertionError if document.Objects is accessed so that tests can
    verify the resolver never falls back to an Objects-list scan.
    """

    def __init__(self, objects: dict[str, Any] | None = None) -> None:
        self._objects: dict[str, Any] = objects or {}
        self.get_object_calls: list[str] = []

    @property
    def Objects(self) -> None:
        raise AssertionError(
            "document.Objects must not be accessed by the resolver"
        )

    def getObject(self, name: str) -> Any:
        self.get_object_calls.append(name)
        return self._objects.get(name)


class _StrictFakeObject:
    """Fake object that raises AssertionError if Label is accessed.

    Verifies the resolver never inspects object.Label for name matching.
    """

    @property
    def Label(self) -> None:
        raise AssertionError(
            "object.Label must not be accessed by the resolver"
        )


# ---------------------------------------------------------------------------
# 1. Module import safety
# ---------------------------------------------------------------------------


class ImportSafetyTests(unittest.TestCase):
    def test_module_imports_under_ordinary_python(self) -> None:
        import parametron_freecad.execution.parameter_target_resolver  # noqa: F401

    def test_import_does_not_require_freecad(self) -> None:
        import sys
        sys.modules.pop(
            "parametron_freecad.execution.parameter_target_resolver", None
        )
        import parametron_freecad.execution.parameter_target_resolver  # noqa: F401
        self.assertNotIn("FreeCAD", sys.modules)

    def test_all_exposes_expected_public_symbols(self) -> None:
        from parametron_freecad.execution import parameter_target_resolver

        expected = {
            "ParsedParameterTarget",
            "ResolvedParameterTarget",
            "ParameterTargetResolutionError",
            "ParameterTargetSyntaxError",
            "UnsupportedParameterTargetError",
            "ParameterTargetObjectNotFoundError",
            "ParameterTargetDocumentError",
            "parse_parameter_target",
            "resolve_parameter_target",
        }
        actual = set(parameter_target_resolver.__all__)
        missing = expected - actual
        self.assertFalse(missing, f"Missing from __all__: {missing}")

    def test_all_symbols_are_importable(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (  # noqa: F401
            ParameterTargetDocumentError,
            ParameterTargetObjectNotFoundError,
            ParameterTargetResolutionError,
            ParameterTargetSyntaxError,
            ParsedParameterTarget,
            ResolvedParameterTarget,
            UnsupportedParameterTargetError,
            parse_parameter_target,
            resolve_parameter_target,
        )


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class ErrorHierarchyTests(unittest.TestCase):
    def test_base_error_is_value_error(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetResolutionError,
        )
        self.assertTrue(issubclass(ParameterTargetResolutionError, ValueError))

    def test_syntax_error_is_subclass_of_base(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetResolutionError,
            ParameterTargetSyntaxError,
        )
        self.assertTrue(
            issubclass(ParameterTargetSyntaxError, ParameterTargetResolutionError)
        )

    def test_unsupported_error_is_subclass_of_base(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetResolutionError,
            UnsupportedParameterTargetError,
        )
        self.assertTrue(
            issubclass(UnsupportedParameterTargetError, ParameterTargetResolutionError)
        )

    def test_object_not_found_error_is_subclass_of_base(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetObjectNotFoundError,
            ParameterTargetResolutionError,
        )
        self.assertTrue(
            issubclass(
                ParameterTargetObjectNotFoundError, ParameterTargetResolutionError
            )
        )

    def test_document_error_is_subclass_of_base(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetDocumentError,
            ParameterTargetResolutionError,
        )
        self.assertTrue(
            issubclass(ParameterTargetDocumentError, ParameterTargetResolutionError)
        )


# ---------------------------------------------------------------------------
# 2. Successful parsing
# ---------------------------------------------------------------------------


class SuccessfulParsingTests(unittest.TestCase):
    def _parse(self, target: str):
        from parametron_freecad.execution.parameter_target_resolver import (
            parse_parameter_target,
        )
        return parse_parameter_target(target)

    def test_simple_target_parses(self) -> None:
        result = self._parse("Box.Length")
        self.assertEqual(result.object_name, "Box")
        self.assertEqual(result.property_name, "Length")

    def test_original_field_preserved(self) -> None:
        result = self._parse("Box.Length")
        self.assertEqual(result.original, "Box.Length")

    def test_object_name_case_preserved(self) -> None:
        result = self._parse("BODY.Width")
        self.assertEqual(result.object_name, "BODY")

    def test_property_name_case_preserved(self) -> None:
        result = self._parse("Body.WIDTH")
        self.assertEqual(result.property_name, "WIDTH")

    def test_part001_height(self) -> None:
        result = self._parse("Part001.Height")
        self.assertEqual(result.object_name, "Part001")
        self.assertEqual(result.property_name, "Height")

    def test_underscore_names(self) -> None:
        result = self._parse("Obj_with_underscores.CustomProp")
        self.assertEqual(result.object_name, "Obj_with_underscores")
        self.assertEqual(result.property_name, "CustomProp")

    def test_unicode_preserved(self) -> None:
        result = self._parse("Ürün.Genişlik")
        self.assertEqual(result.object_name, "Ürün")
        self.assertEqual(result.property_name, "Genişlik")

    def test_leading_whitespace_in_object_name_not_trimmed(self) -> None:
        # Implementation accepts any non-empty segment — no silent normalization.
        result = self._parse(" Box.Length")
        self.assertEqual(result.object_name, " Box")
        self.assertEqual(result.property_name, "Length")

    def test_trailing_whitespace_in_property_name_not_trimmed(self) -> None:
        result = self._parse("Box.Length ")
        self.assertEqual(result.object_name, "Box")
        self.assertEqual(result.property_name, "Length ")

    def test_parsed_target_is_immutable(self) -> None:
        result = self._parse("Box.Length")
        with self.assertRaises(Exception):
            result.object_name = "Changed"  # type: ignore[misc]

    def test_spreadsheet_like_target_parses_as_ordinary_object_property(self) -> None:
        # "Spreadsheet.A1" has exactly one dot — must be treated as an
        # ordinary object-property pair, not as a spreadsheet cell reference.
        result = self._parse("Spreadsheet.A1")
        self.assertEqual(result.object_name, "Spreadsheet")
        self.assertEqual(result.property_name, "A1")


# ---------------------------------------------------------------------------
# 3. Malformed target rejection
# ---------------------------------------------------------------------------


class MalformedTargetRejectionTests(unittest.TestCase):
    def _parse(self, target: Any):
        from parametron_freecad.execution.parameter_target_resolver import (
            parse_parameter_target,
        )
        return parse_parameter_target(target)

    def _assert_raises_resolution_error(self, target: Any) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetResolutionError,
        )
        with self.assertRaises(ParameterTargetResolutionError):
            self._parse(target)

    # Non-string targets

    def test_none_raises_resolution_error(self) -> None:
        self._assert_raises_resolution_error(None)

    def test_int_raises_resolution_error(self) -> None:
        self._assert_raises_resolution_error(123)

    def test_dict_raises_resolution_error(self) -> None:
        self._assert_raises_resolution_error({})

    def test_none_raises_syntax_error(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetSyntaxError,
        )
        with self.assertRaises(ParameterTargetSyntaxError):
            self._parse(None)

    def test_int_raises_syntax_error(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetSyntaxError,
        )
        with self.assertRaises(ParameterTargetSyntaxError):
            self._parse(123)

    # Structurally invalid strings

    def test_empty_string_raises_resolution_error(self) -> None:
        self._assert_raises_resolution_error("")

    def test_no_dot_raises_resolution_error(self) -> None:
        self._assert_raises_resolution_error("Length")

    def test_empty_object_segment_raises_resolution_error(self) -> None:
        self._assert_raises_resolution_error(".Length")

    def test_empty_property_segment_raises_resolution_error(self) -> None:
        self._assert_raises_resolution_error("Box.")

    def test_two_dots_raises_resolution_error(self) -> None:
        self._assert_raises_resolution_error("Box.Shape.Length")

    def test_sketch_constraint_value_raises_resolution_error(self) -> None:
        self._assert_raises_resolution_error("Sketch.ConstraintName.Value")

    # Error message quality

    def test_non_string_error_message_is_non_empty_and_has_no_traceback(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetResolutionError,
        )
        try:
            self._parse(None)
            self.fail("expected ParameterTargetResolutionError")
        except ParameterTargetResolutionError as exc:
            msg = str(exc)
            self.assertGreater(len(msg), 0)
            self.assertNotIn("Traceback", msg)

    def test_no_dot_error_message_has_no_traceback(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetResolutionError,
        )
        try:
            self._parse("Length")
            self.fail("expected ParameterTargetResolutionError")
        except ParameterTargetResolutionError as exc:
            self.assertNotIn("Traceback", str(exc))

    def test_two_dots_error_message_has_no_traceback(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetResolutionError,
        )
        try:
            self._parse("Box.Shape.Length")
            self.fail("expected ParameterTargetResolutionError")
        except ParameterTargetResolutionError as exc:
            self.assertNotIn("Traceback", str(exc))


# ---------------------------------------------------------------------------
# 4. Unsupported family / Phase 1 boundary
# ---------------------------------------------------------------------------


class UnsupportedFamilyBoundaryTests(unittest.TestCase):
    def _parse(self, target: str):
        from parametron_freecad.execution.parameter_target_resolver import (
            parse_parameter_target,
        )
        return parse_parameter_target(target)

    def _resolve(self, doc: Any, target: str):
        from parametron_freecad.execution.parameter_target_resolver import (
            resolve_parameter_target,
        )
        return resolve_parameter_target(doc, target)

    def test_three_segment_target_is_rejected(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetResolutionError,
        )
        with self.assertRaises(ParameterTargetResolutionError):
            self._parse("Sketch.ConstraintName.Value")

    def test_spreadsheet_a1_resolves_as_ordinary_object_property(self) -> None:
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Spreadsheet": fake_obj})
        result = self._resolve(doc, "Spreadsheet.A1")
        self.assertEqual(result.object_name, "Spreadsheet")
        self.assertEqual(result.property_name, "A1")
        self.assertIs(result.object, fake_obj)

    def test_spreadsheet_a1_does_not_access_document_objects_list(self) -> None:
        # _StrictFakeDocument.Objects raises AssertionError if accessed.
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Spreadsheet": fake_obj})
        # Must not raise AssertionError.
        self._resolve(doc, "Spreadsheet.A1")

    def test_spreadsheet_a1_does_not_inspect_object_label(self) -> None:
        # _StrictFakeObject.Label raises AssertionError if accessed.
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Spreadsheet": fake_obj})
        # Must not raise AssertionError.
        self._resolve(doc, "Spreadsheet.A1")

    def test_spreadsheet_a1_calls_get_object_with_spreadsheet_name(self) -> None:
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Spreadsheet": fake_obj})
        self._resolve(doc, "Spreadsheet.A1")
        self.assertEqual(doc.get_object_calls, ["Spreadsheet"])


# ---------------------------------------------------------------------------
# 5. getObject-only object resolution
# ---------------------------------------------------------------------------


class GetObjectOnlyResolutionTests(unittest.TestCase):
    def _resolve(self, doc: Any, target: str):
        from parametron_freecad.execution.parameter_target_resolver import (
            resolve_parameter_target,
        )
        return resolve_parameter_target(doc, target)

    def test_get_object_called_exactly_once(self) -> None:
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Box": fake_obj})
        self._resolve(doc, "Box.Length")
        self.assertEqual(doc.get_object_calls, ["Box"])

    def test_returned_object_is_from_get_object(self) -> None:
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Box": fake_obj})
        result = self._resolve(doc, "Box.Length")
        self.assertIs(result.object, fake_obj)

    def test_resolved_object_name_matches_target(self) -> None:
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Box": fake_obj})
        result = self._resolve(doc, "Box.Length")
        self.assertEqual(result.object_name, "Box")

    def test_resolved_property_name_matches_target(self) -> None:
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Box": fake_obj})
        result = self._resolve(doc, "Box.Length")
        self.assertEqual(result.property_name, "Length")

    def test_resolved_original_matches_input_target(self) -> None:
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Box": fake_obj})
        result = self._resolve(doc, "Box.Length")
        self.assertEqual(result.original, "Box.Length")

    def test_document_objects_not_accessed(self) -> None:
        # _StrictFakeDocument.Objects raises AssertionError if accessed.
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Box": fake_obj})
        self._resolve(doc, "Box.Length")

    def test_object_label_not_accessed(self) -> None:
        # _StrictFakeObject.Label raises AssertionError if accessed.
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Box": fake_obj})
        self._resolve(doc, "Box.Length")

    def test_resolved_target_is_immutable(self) -> None:
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Box": fake_obj})
        result = self._resolve(doc, "Box.Length")
        with self.assertRaises(Exception):
            result.object_name = "Changed"  # type: ignore[misc]

    def test_get_object_receives_object_name_from_target(self) -> None:
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Part001": fake_obj})
        self._resolve(doc, "Part001.Height")
        self.assertIn("Part001", doc.get_object_calls)


# ---------------------------------------------------------------------------
# 6. Missing or invalid getObject
# ---------------------------------------------------------------------------


class MissingGetObjectTests(unittest.TestCase):
    def _resolve(self, doc: Any, target: str):
        from parametron_freecad.execution.parameter_target_resolver import (
            resolve_parameter_target,
        )
        return resolve_parameter_target(doc, target)

    def test_document_missing_get_object_raises_document_error(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetDocumentError,
        )
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        class NoGetObject:
            pass

        with self.assertRaises(ParameterTargetDocumentError) as cm:
            self._resolve(NoGetObject(), "Box.Length")
        self.assertNotIsInstance(cm.exception, ParameterAccessError)
        self.assertIsInstance(cm.exception.__cause__, ParameterAccessError)

    def test_document_missing_get_object_raises_resolution_error(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetResolutionError,
        )

        class NoGetObject:
            pass

        with self.assertRaises(ParameterTargetResolutionError):
            self._resolve(NoGetObject(), "Box.Length")

    def test_non_callable_get_object_raises_document_error(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetDocumentError,
        )
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        class NonCallableGetObject:
            getObject = "not_callable"

        with self.assertRaises(ParameterTargetDocumentError) as cm:
            self._resolve(NonCallableGetObject(), "Box.Length")
        self.assertNotIsInstance(cm.exception, ParameterAccessError)
        self.assertIsInstance(cm.exception.__cause__, ParameterAccessError)

    def test_get_object_raising_wraps_in_document_error(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetDocumentError,
        )

        class RaisingDoc:
            def getObject(self, name: str) -> None:
                raise RuntimeError("internal failure")

        with self.assertRaises(ParameterTargetDocumentError):
            self._resolve(RaisingDoc(), "Box.Length")

    def test_get_object_raising_chains_original_exception(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetDocumentError,
        )
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        original = RuntimeError("internal failure")

        class RaisingDoc:
            def getObject(self, name: str) -> None:
                raise original

        try:
            self._resolve(RaisingDoc(), "Box.Length")
            self.fail("expected ParameterTargetDocumentError")
        except ParameterTargetDocumentError as exc:
            self.assertNotIsInstance(exc, ParameterAccessError)
            self.assertIs(exc.__cause__, original)

    def test_get_object_returning_none_raises_object_not_found_error(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetObjectNotFoundError,
        )
        from parametron_freecad.runtime.parameter_access import ParameterAccessError

        class ReturnsNone:
            def getObject(self, name: str) -> None:
                return None

        with self.assertRaises(ParameterTargetObjectNotFoundError) as cm:
            self._resolve(ReturnsNone(), "Box.Length")
        self.assertNotIsInstance(cm.exception, ParameterAccessError)
        self.assertIsInstance(cm.exception.__cause__, ParameterAccessError)

    def test_object_not_found_error_is_resolution_error(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetResolutionError,
        )

        class ReturnsNone:
            def getObject(self, name: str) -> None:
                return None

        with self.assertRaises(ParameterTargetResolutionError):
            self._resolve(ReturnsNone(), "Box.Length")

    def test_object_not_found_message_includes_object_name(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetObjectNotFoundError,
        )

        class ReturnsNone:
            def getObject(self, name: str) -> None:
                return None

        try:
            self._resolve(ReturnsNone(), "Box.Length")
            self.fail("expected ParameterTargetObjectNotFoundError")
        except ParameterTargetObjectNotFoundError as exc:
            self.assertIn("Box", str(exc))

    def test_missing_get_object_error_message_has_no_traceback(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetDocumentError,
        )

        class NoGetObject:
            pass

        try:
            self._resolve(NoGetObject(), "Box.Length")
            self.fail("expected ParameterTargetDocumentError")
        except ParameterTargetDocumentError as exc:
            self.assertNotIn("Traceback", str(exc))

    def test_get_object_raise_error_message_has_no_traceback(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetDocumentError,
        )

        class RaisingDoc:
            def getObject(self, name: str) -> None:
                raise RuntimeError("internal failure")

        try:
            self._resolve(RaisingDoc(), "Box.Length")
            self.fail("expected ParameterTargetDocumentError")
        except ParameterTargetDocumentError as exc:
            self.assertNotIn("Traceback", str(exc))

    def test_object_not_found_error_message_has_no_traceback(self) -> None:
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetObjectNotFoundError,
        )

        class ReturnsNone:
            def getObject(self, name: str) -> None:
                return None

        try:
            self._resolve(ReturnsNone(), "Box.Length")
            self.fail("expected ParameterTargetObjectNotFoundError")
        except ParameterTargetObjectNotFoundError as exc:
            self.assertNotIn("Traceback", str(exc))

    def test_no_fallback_attempted_when_get_object_returns_none(self) -> None:
        # Once getObject returns None the resolver must fail immediately —
        # _StrictFakeDocument.Objects raises if any fallback scan is attempted.
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetObjectNotFoundError,
        )
        doc = _StrictFakeDocument({})
        with self.assertRaises(ParameterTargetObjectNotFoundError):
            self._resolve(doc, "Box.Length")


# ---------------------------------------------------------------------------
# 9. No Label lookup regression
# ---------------------------------------------------------------------------


class NoLabelLookupRegressionTests(unittest.TestCase):
    def _resolve(self, doc: Any, target: str):
        from parametron_freecad.execution.parameter_target_resolver import (
            resolve_parameter_target,
        )
        return resolve_parameter_target(doc, target)

    def test_label_lookup_not_attempted_when_get_object_returns_none(self) -> None:
        # getObject("DisplayLabel") returns None → must fail without
        # accessing document.Objects or any Label-based fallback surface.
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetObjectNotFoundError,
        )
        doc = _StrictFakeDocument({})
        with self.assertRaises(ParameterTargetObjectNotFoundError):
            self._resolve(doc, "DisplayLabel.Length")

    def test_no_fallback_via_objects_list(self) -> None:
        # _StrictFakeDocument.Objects raises — must never be accessed.
        from parametron_freecad.execution.parameter_target_resolver import (
            ParameterTargetObjectNotFoundError,
        )
        doc = _StrictFakeDocument({})
        with self.assertRaises(ParameterTargetObjectNotFoundError):
            self._resolve(doc, "AnyName.Prop")

    def test_object_label_not_inspected_for_resolved_object(self) -> None:
        # Resolver finds the object via getObject — must not then inspect
        # Label on the returned object. _StrictFakeObject.Label raises if accessed.
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"Box": fake_obj})
        result = self._resolve(doc, "Box.Length")
        self.assertIs(result.object, fake_obj)

    def test_get_object_called_with_name_segment_not_label(self) -> None:
        # Resolver must pass the object_name segment as-is to getObject,
        # not search by Label or any other attribute.
        fake_obj = _StrictFakeObject()
        doc = _StrictFakeDocument({"ExactName": fake_obj})
        result = self._resolve(doc, "ExactName.Prop")
        self.assertEqual(doc.get_object_calls, ["ExactName"])
        self.assertIs(result.object, fake_obj)


if __name__ == "__main__":
    unittest.main()
