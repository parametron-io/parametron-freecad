"""Permanent coverage for Task 3 strict schema 2.0 manifest validation.

Task 2 (../tests/test_manifest_v2_contract.py) locked the schema 2.0 metadata
shapes. This module locks the Task 3 validation behavior layered on that
metadata: exact version dispatch, V1 closure, strict V2 structural/semantic
validation, and mutation-boundary conflict checks. It intentionally does not
exercise any native FreeCAD mutation behavior (suppression/visibility/deletion
execution, recompute, save) — that remains future scope.
"""

from __future__ import annotations

import copy
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import parametron_freecad.execution.manifest_validation as mv
from parametron_freecad.execution.manifest_loader import LoadedManifest

MINIMAL_V1 = {
    "schemaVersion": "1.0",
    "sourceDocument": "model.FCStd",
    "parameterAssignments": [],
    "outputs": [],
}

MINIMAL_V2 = {
    "schemaVersion": "2.0",
    "sourceDocument": "model.FCStd",
    "parameterAssignments": [],
    "outputs": [],
}


def _v2(**overrides):
    data = dict(MINIMAL_V2)
    data.update(overrides)
    return data


FULL_V2_POSITIVE = {
    "schemaVersion": "2.0",
    "sourceDocument": "model.FCStd",
    "parameterAssignments": [],
    "assemblyMutations": {
        "suppression": [{"object": "AsmA", "suppressed": True}],
        "visibility": [{"object": "AsmB", "visible": False}],
        "deletion": [{"object": "AsmC"}],
    },
    "partMutations": {
        "suppression": [{"object": "Pad", "suppressed": False}],
        "visibility": [{"object": "Body", "visible": True}],
        "deletion": [{"object": "Chamfer"}],
    },
    "outputs": [],
}


class TestVersionDispatchMatrix(unittest.TestCase):
    """`validate_export_manifest` dispatches on the exact schemaVersion value."""

    def test_1_0_dispatches_to_v1(self):
        result = mv.validate_export_manifest(MINIMAL_V1)
        self.assertTrue(result.is_valid)

    def test_1_0_dispatch_matches_direct_v1_call(self):
        self.assertEqual(
            mv.validate_export_manifest(MINIMAL_V1),
            mv.validate_export_manifest_v1(MINIMAL_V1),
        )

    def test_2_0_dispatches_to_v2(self):
        result = mv.validate_export_manifest(MINIMAL_V2)
        self.assertTrue(result.is_valid)

    def test_2_0_dispatch_matches_direct_v2_call(self):
        self.assertEqual(
            mv.validate_export_manifest(MINIMAL_V2),
            mv.validate_export_manifest_v2(MINIMAL_V2),
        )

    def test_missing_schema_version_rejected(self):
        data = {k: v for k, v in MINIMAL_V1.items() if k != "schemaVersion"}
        result = mv.validate_export_manifest(data)
        self.assertFalse(result.is_valid)
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD, "schemaVersion")],
        )

    def test_null_schema_version_rejected(self):
        result = mv.validate_export_manifest(_v2(schemaVersion=None))
        self.assertFalse(result.is_valid)
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_INVALID_FIELD_TYPE, "schemaVersion")],
        )

    def test_integer_schema_version_rejected(self):
        result = mv.validate_export_manifest(_v2(schemaVersion=2))
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_INVALID_FIELD_TYPE, "schemaVersion")],
        )

    def test_float_schema_version_rejected(self):
        result = mv.validate_export_manifest(_v2(schemaVersion=2.0))
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_INVALID_FIELD_TYPE, "schemaVersion")],
        )

    def test_stringified_short_form_rejected(self):
        result = mv.validate_export_manifest(_v2(schemaVersion="2"))
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_INVALID_SCHEMA_VERSION, "schemaVersion")],
        )

    def test_whitespace_padded_version_not_trimmed(self):
        result = mv.validate_export_manifest(_v2(schemaVersion=" 2.0 "))
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_INVALID_SCHEMA_VERSION, "schemaVersion")],
        )

    def test_unsupported_version_rejected(self):
        result = mv.validate_export_manifest(_v2(schemaVersion="3.0"))
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_INVALID_SCHEMA_VERSION, "schemaVersion")],
        )

    def test_v_prefixed_version_rejected(self):
        result = mv.validate_export_manifest(_v2(schemaVersion="v2"))
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_INVALID_SCHEMA_VERSION, "schemaVersion")],
        )

    def test_no_fallback_for_unsupported_version(self):
        # An unsupported version must not silently fall back to V1 or V2
        # validation; it must short-circuit with exactly one diagnostic.
        result = mv.validate_export_manifest(_v2(schemaVersion="3.0"))
        self.assertEqual(len(result.diagnostics), 1)

    def test_dispatch_on_non_mapping_falls_back_to_v1_root_diagnostic(self):
        result = mv.validate_export_manifest([])
        self.assertEqual(result, mv.validate_export_manifest_v1([]))


class TestV1ClosureRegression(unittest.TestCase):
    """Canonical V1 permits optional target mutations and rejects schema 2.0."""

    def test_v1_accepts_required_core_without_mutations(self):
        self.assertTrue(mv.validate_export_manifest_v1(MINIMAL_V1).is_valid)

    def test_v1_accepts_optional_assembly_mutations(self):
        data = {**MINIMAL_V1, "assemblyMutations": {}}
        result = mv.validate_export_manifest_v1(data)
        self.assertTrue(result.is_valid, result.diagnostics)

    def test_v1_accepts_optional_part_mutations(self):
        data = {**MINIMAL_V1, "partMutations": {}}
        result = mv.validate_export_manifest_v1(data)
        self.assertTrue(result.is_valid, result.diagnostics)

    def test_v1_rejects_schema_2_0(self):
        data = {**MINIMAL_V1, "schemaVersion": "2.0"}
        result = mv.validate_export_manifest_v1(data)
        self.assertFalse(result.is_valid)
        self.assertIn(mv.DIAGNOSTIC_INVALID_SCHEMA_VERSION, [d.code for d in result.diagnostics])

    def test_v1_unaffected_by_v2_presence_snapshot(self):
        # Same fixture/behavior as pre-Task-3: unknown fields sorted lexically,
        # missing fields in contract order, unchanged diagnostic codes.
        data = {"zzz": 1, "aaa": 2}
        result = mv.validate_export_manifest_v1(data)
        missing = [d.path for d in result.diagnostics if d.code == mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD]
        unknown = [d.path for d in result.diagnostics if d.code == mv.DIAGNOSTIC_UNKNOWN_FIELD]
        self.assertEqual(
            missing, ["schemaVersion", "sourceDocument", "parameterAssignments", "outputs"]
        )
        self.assertEqual(unknown, ["aaa", "zzz"])


class TestMinimalV2Acceptance(unittest.TestCase):
    def test_minimal_v2_passes_direct_v2_validator(self):
        self.assertTrue(mv.validate_export_manifest_v2(MINIMAL_V2).is_valid)

    def test_minimal_v2_passes_generic_dispatch(self):
        self.assertTrue(mv.validate_export_manifest(MINIMAL_V2).is_valid)


class TestSparseMutationSections(unittest.TestCase):
    def test_empty_part_mutations_object_is_valid(self):
        self.assertTrue(mv.validate_export_manifest_v2(_v2(partMutations={})).is_valid)

    def test_empty_assembly_mutations_object_is_valid(self):
        self.assertTrue(mv.validate_export_manifest_v2(_v2(assemblyMutations={})).is_valid)

    def test_sparse_suppression_only_is_valid(self):
        data = _v2(partMutations={"suppression": []})
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)

    def test_sparse_visibility_only_is_valid(self):
        data = _v2(assemblyMutations={"visibility": []})
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)

    def test_sparse_deletion_only_is_valid(self):
        data = _v2(partMutations={"deletion": []})
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)

    def test_neither_mutation_section_present_is_valid(self):
        self.assertTrue(mv.validate_export_manifest_v2(MINIMAL_V2).is_valid)


class TestFullV2PositiveMatrix(unittest.TestCase):
    def test_full_positive_manifest_is_valid(self):
        result = mv.validate_export_manifest_v2(FULL_V2_POSITIVE)
        self.assertTrue(result.is_valid, msg=[(d.code, d.path) for d in result.diagnostics])

    def test_full_positive_manifest_passes_generic_dispatch(self):
        self.assertTrue(mv.validate_export_manifest(FULL_V2_POSITIVE).is_valid)

    def test_suppression_and_visibility_on_same_object_is_valid(self):
        data = _v2(
            assemblyMutations={
                "suppression": [{"object": "X", "suppressed": True}],
                "visibility": [{"object": "X", "visible": True}],
            }
        )
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)


class TestMutationSectionTypeValidation(unittest.TestCase):
    INVALID_SECTION_VALUES = (None, [], "", 1, True)

    def test_assembly_mutations_rejects_invalid_types(self):
        for bad in self.INVALID_SECTION_VALUES:
            with self.subTest(bad=bad):
                result = mv.validate_export_manifest_v2(_v2(assemblyMutations=bad))
                self.assertEqual(
                    [(d.code, d.path) for d in result.diagnostics],
                    [(mv.DIAGNOSTIC_INVALID_MUTATION_SECTION_TYPE, "assemblyMutations")],
                )

    def test_part_mutations_rejects_invalid_types(self):
        for bad in self.INVALID_SECTION_VALUES:
            with self.subTest(bad=bad):
                result = mv.validate_export_manifest_v2(_v2(partMutations=bad))
                self.assertEqual(
                    [(d.code, d.path) for d in result.diagnostics],
                    [(mv.DIAGNOSTIC_INVALID_MUTATION_SECTION_TYPE, "partMutations")],
                )


class TestClosedMutationCollectionSet(unittest.TestCase):
    UNKNOWN_COLLECTIONS = ("parameters", "properties", "keep", "actions", "targets", "unknown")

    def test_each_unknown_collection_rejected_in_assembly(self):
        for name in self.UNKNOWN_COLLECTIONS:
            with self.subTest(name=name):
                result = mv.validate_export_manifest_v2(_v2(assemblyMutations={name: []}))
                self.assertIn(
                    (mv.DIAGNOSTIC_UNKNOWN_MUTATION_COLLECTION, f"assemblyMutations.{name}"),
                    [(d.code, d.path) for d in result.diagnostics],
                )

    def test_each_unknown_collection_rejected_in_part(self):
        for name in self.UNKNOWN_COLLECTIONS:
            with self.subTest(name=name):
                result = mv.validate_export_manifest_v2(_v2(partMutations={name: []}))
                self.assertIn(
                    (mv.DIAGNOSTIC_UNKNOWN_MUTATION_COLLECTION, f"partMutations.{name}"),
                    [(d.code, d.path) for d in result.diagnostics],
                )

    def test_multiple_unknown_collections_ordered_lexically(self):
        data = _v2(assemblyMutations={"zzz": [], "aaa": [], "mmm": []})
        result = mv.validate_export_manifest_v2(data)
        unknown_paths = [
            d.path for d in result.diagnostics
            if d.code == mv.DIAGNOSTIC_UNKNOWN_MUTATION_COLLECTION
        ]
        self.assertEqual(
            unknown_paths,
            ["assemblyMutations.aaa", "assemblyMutations.mmm", "assemblyMutations.zzz"],
        )


class TestCollectionTypeValidation(unittest.TestCase):
    INVALID_COLLECTION_VALUES = (None, {}, "", 1, True)

    def test_suppression_rejects_non_array_values(self):
        for bad in self.INVALID_COLLECTION_VALUES:
            with self.subTest(bad=bad):
                data = _v2(assemblyMutations={"suppression": bad})
                result = mv.validate_export_manifest_v2(data)
                self.assertEqual(
                    [(d.code, d.path) for d in result.diagnostics],
                    [(mv.DIAGNOSTIC_INVALID_MUTATION_COLLECTION_TYPE, "assemblyMutations.suppression")],
                )

    def test_visibility_rejects_non_array_values(self):
        for bad in self.INVALID_COLLECTION_VALUES:
            with self.subTest(bad=bad):
                data = _v2(assemblyMutations={"visibility": bad})
                result = mv.validate_export_manifest_v2(data)
                self.assertEqual(
                    [(d.code, d.path) for d in result.diagnostics],
                    [(mv.DIAGNOSTIC_INVALID_MUTATION_COLLECTION_TYPE, "assemblyMutations.visibility")],
                )

    def test_deletion_rejects_non_array_values(self):
        for bad in self.INVALID_COLLECTION_VALUES:
            with self.subTest(bad=bad):
                data = _v2(partMutations={"deletion": bad})
                result = mv.validate_export_manifest_v2(data)
                self.assertEqual(
                    [(d.code, d.path) for d in result.diagnostics],
                    [(mv.DIAGNOSTIC_INVALID_MUTATION_COLLECTION_TYPE, "partMutations.deletion")],
                )

    def test_empty_array_remains_valid_for_each_collection(self):
        for name in ("suppression", "visibility", "deletion"):
            with self.subTest(name=name):
                data = _v2(assemblyMutations={name: []})
                self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)


class TestSuppressionEntryValidation(unittest.TestCase):
    def _entries(self, entries):
        return _v2(assemblyMutations={"suppression": entries})

    def test_valid_true(self):
        data = self._entries([{"object": "Pad", "suppressed": True}])
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)

    def test_valid_false(self):
        data = self._entries([{"object": "Pad", "suppressed": False}])
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)

    def test_non_object_entry_rejected(self):
        for bad in ("string", 1, True, None, [], 1.5):
            with self.subTest(bad=bad):
                data = self._entries([bad])
                result = mv.validate_export_manifest_v2(data)
                self.assertIn(
                    (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_TYPE, "assemblyMutations.suppression[0]"),
                    [(d.code, d.path) for d in result.diagnostics],
                )

    def test_missing_object_rejected(self):
        data = self._entries([{"suppressed": True}])
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            (mv.DIAGNOSTIC_MISSING_MUTATION_ENTRY_FIELD, "assemblyMutations.suppression[0]"),
            [(d.code, d.path) for d in result.diagnostics],
        )

    def test_missing_suppressed_rejected(self):
        data = self._entries([{"object": "Pad"}])
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            (mv.DIAGNOSTIC_MISSING_MUTATION_ENTRY_FIELD, "assemblyMutations.suppression[0]"),
            [(d.code, d.path) for d in result.diagnostics],
        )

    def test_unknown_field_rejected(self):
        data = self._entries([{"object": "Pad", "suppressed": True, "extra": 1}])
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            (mv.DIAGNOSTIC_UNKNOWN_MUTATION_ENTRY_FIELD, "assemblyMutations.suppression[0].extra"),
            [(d.code, d.path) for d in result.diagnostics],
        )

    def test_object_non_string_rejected(self):
        for bad in (1, True, None, [], {}, 1.5):
            with self.subTest(bad=bad):
                data = self._entries([{"object": bad, "suppressed": True}])
                result = mv.validate_export_manifest_v2(data)
                self.assertIn(
                    (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE, "assemblyMutations.suppression[0].object"),
                    [(d.code, d.path) for d in result.diagnostics],
                )

    def test_object_empty_string_rejected(self):
        data = self._entries([{"object": "", "suppressed": True}])
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE, "assemblyMutations.suppression[0].object"),
            [(d.code, d.path) for d in result.diagnostics],
        )

    def test_suppressed_strict_bool_rejects_numeric_and_string_and_container_values(self):
        for bad in (0, 1, "true", "false", None, [], {}):
            with self.subTest(bad=bad):
                data = self._entries([{"object": "Pad", "suppressed": bad}])
                result = mv.validate_export_manifest_v2(data)
                self.assertIn(
                    (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE, "assemblyMutations.suppression[0].suppressed"),
                    [(d.code, d.path) for d in result.diagnostics],
                )


class TestVisibilityEntryValidation(unittest.TestCase):
    def _entries(self, entries):
        return _v2(assemblyMutations={"visibility": entries})

    def test_valid_true(self):
        data = self._entries([{"object": "Body", "visible": True}])
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)

    def test_valid_false(self):
        data = self._entries([{"object": "Body", "visible": False}])
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)

    def test_non_object_entry_rejected(self):
        for bad in ("string", 1, True, None, [], 1.5):
            with self.subTest(bad=bad):
                data = self._entries([bad])
                result = mv.validate_export_manifest_v2(data)
                self.assertIn(
                    (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_TYPE, "assemblyMutations.visibility[0]"),
                    [(d.code, d.path) for d in result.diagnostics],
                )

    def test_missing_object_rejected(self):
        data = self._entries([{"visible": True}])
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            (mv.DIAGNOSTIC_MISSING_MUTATION_ENTRY_FIELD, "assemblyMutations.visibility[0]"),
            [(d.code, d.path) for d in result.diagnostics],
        )

    def test_missing_visible_rejected(self):
        data = self._entries([{"object": "Body"}])
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            (mv.DIAGNOSTIC_MISSING_MUTATION_ENTRY_FIELD, "assemblyMutations.visibility[0]"),
            [(d.code, d.path) for d in result.diagnostics],
        )

    def test_unknown_field_rejected(self):
        data = self._entries([{"object": "Body", "visible": True, "extra": 1}])
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            (mv.DIAGNOSTIC_UNKNOWN_MUTATION_ENTRY_FIELD, "assemblyMutations.visibility[0].extra"),
            [(d.code, d.path) for d in result.diagnostics],
        )

    def test_object_non_string_rejected(self):
        for bad in (1, True, None, [], {}, 1.5):
            with self.subTest(bad=bad):
                data = self._entries([{"object": bad, "visible": True}])
                result = mv.validate_export_manifest_v2(data)
                self.assertIn(
                    (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE, "assemblyMutations.visibility[0].object"),
                    [(d.code, d.path) for d in result.diagnostics],
                )

    def test_object_empty_string_rejected(self):
        data = self._entries([{"object": "", "visible": True}])
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE, "assemblyMutations.visibility[0].object"),
            [(d.code, d.path) for d in result.diagnostics],
        )

    def test_visible_strict_bool_rejects_numeric_and_string_and_container_values(self):
        for bad in (0, 1, "true", "false", None, [], {}):
            with self.subTest(bad=bad):
                data = self._entries([{"object": "Body", "visible": bad}])
                result = mv.validate_export_manifest_v2(data)
                self.assertIn(
                    (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE, "assemblyMutations.visibility[0].visible"),
                    [(d.code, d.path) for d in result.diagnostics],
                )


class TestDeletionEntryValidation(unittest.TestCase):
    def _entries(self, entries):
        return _v2(assemblyMutations={"deletion": entries})

    def test_valid_entry(self):
        data = self._entries([{"object": "Chamfer"}])
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)

    def test_non_object_entry_rejected(self):
        for bad in ("string", 1, True, None, [], 1.5):
            with self.subTest(bad=bad):
                data = self._entries([bad])
                result = mv.validate_export_manifest_v2(data)
                self.assertIn(
                    (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_TYPE, "assemblyMutations.deletion[0]"),
                    [(d.code, d.path) for d in result.diagnostics],
                )

    def test_missing_object_rejected(self):
        data = self._entries([{}])
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            (mv.DIAGNOSTIC_MISSING_MUTATION_ENTRY_FIELD, "assemblyMutations.deletion[0]"),
            [(d.code, d.path) for d in result.diagnostics],
        )

    def test_object_non_string_rejected(self):
        for bad in (1, True, None, [], {}, 1.5):
            with self.subTest(bad=bad):
                data = self._entries([{"object": bad}])
                result = mv.validate_export_manifest_v2(data)
                self.assertIn(
                    (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE, "assemblyMutations.deletion[0].object"),
                    [(d.code, d.path) for d in result.diagnostics],
                )

    def test_object_empty_string_rejected(self):
        data = self._entries([{"object": ""}])
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE, "assemblyMutations.deletion[0].object"),
            [(d.code, d.path) for d in result.diagnostics],
        )

    def test_unknown_field_rejected(self):
        data = self._entries([{"object": "Chamfer", "extra": 1}])
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            (mv.DIAGNOSTIC_UNKNOWN_MUTATION_ENTRY_FIELD, "assemblyMutations.deletion[0].extra"),
            [(d.code, d.path) for d in result.diagnostics],
        )

    def test_forbidden_execution_fields_rejected_as_unknown(self):
        forbidden = (
            "force",
            "cascade",
            "recursive",
            "dependencyPolicy",
            "targetKind",
            "semanticId",
            "action",
        )
        for field_name in forbidden:
            with self.subTest(field_name=field_name):
                data = self._entries([{"object": "Chamfer", field_name: True}])
                result = mv.validate_export_manifest_v2(data)
                self.assertIn(
                    (mv.DIAGNOSTIC_UNKNOWN_MUTATION_ENTRY_FIELD, f"assemblyMutations.deletion[0].{field_name}"),
                    [(d.code, d.path) for d in result.diagnostics],
                )


class TestDuplicateMutationObjects(unittest.TestCase):
    def test_duplicate_suppression_object_rejected(self):
        data = _v2(
            assemblyMutations={
                "suppression": [
                    {"object": "Pad", "suppressed": True},
                    {"object": "Pad", "suppressed": False},
                ]
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_DUPLICATE_MUTATION_OBJECT, "assemblyMutations.suppression[1].object")],
        )

    def test_duplicate_visibility_object_rejected(self):
        data = _v2(
            assemblyMutations={
                "visibility": [
                    {"object": "Body", "visible": True},
                    {"object": "Body", "visible": False},
                ]
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_DUPLICATE_MUTATION_OBJECT, "assemblyMutations.visibility[1].object")],
        )

    def test_duplicate_deletion_object_rejected(self):
        data = _v2(
            assemblyMutations={
                "deletion": [{"object": "Chamfer"}, {"object": "Chamfer"}],
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_DUPLICATE_MUTATION_OBJECT, "assemblyMutations.deletion[1].object")],
        )

    def test_duplicate_diagnostic_message_references_first_occurrence(self):
        data = _v2(
            assemblyMutations={
                "suppression": [
                    {"object": "Pad", "suppressed": True},
                    {"object": "Pad", "suppressed": False},
                ]
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            "assemblyMutations.suppression[0].object",
            result.diagnostics[0].message,
        )


class TestExactNameNoNormalization(unittest.TestCase):
    def test_case_and_whitespace_variants_are_treated_as_distinct_objects(self):
        data = _v2(
            assemblyMutations={
                "suppression": [
                    {"object": "Pad", "suppressed": True},
                    {"object": "pad", "suppressed": True},
                    {"object": " Pad", "suppressed": True},
                    {"object": "Pad ", "suppressed": True},
                ]
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertTrue(result.is_valid, msg=[(d.code, d.path) for d in result.diagnostics])

    def test_case_variant_does_not_trigger_cross_scope_conflict(self):
        data = _v2(
            assemblyMutations={"suppression": [{"object": "Pad", "suppressed": True}]},
            partMutations={"suppression": [{"object": "pad", "suppressed": True}]},
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertTrue(result.is_valid, msg=[(d.code, d.path) for d in result.diagnostics])


class TestSameScopeFamilyConflicts(unittest.TestCase):
    def test_part_suppression_and_deletion_conflict(self):
        data = _v2(
            partMutations={
                "suppression": [{"object": "X", "suppressed": True}],
                "deletion": [{"object": "X"}],
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_MUTATION_FAMILY_CONFLICT, "partMutations.deletion[0].object")],
        )

    def test_assembly_suppression_and_deletion_conflict(self):
        data = _v2(
            assemblyMutations={
                "suppression": [{"object": "X", "suppressed": True}],
                "deletion": [{"object": "X"}],
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_MUTATION_FAMILY_CONFLICT, "assemblyMutations.deletion[0].object")],
        )

    def test_part_visibility_and_deletion_conflict(self):
        data = _v2(
            partMutations={
                "visibility": [{"object": "X", "visible": True}],
                "deletion": [{"object": "X"}],
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_MUTATION_FAMILY_CONFLICT, "partMutations.deletion[0].object")],
        )

    def test_assembly_visibility_and_deletion_conflict(self):
        data = _v2(
            assemblyMutations={
                "visibility": [{"object": "X", "visible": True}],
                "deletion": [{"object": "X"}],
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [(mv.DIAGNOSTIC_MUTATION_FAMILY_CONFLICT, "assemblyMutations.deletion[0].object")],
        )

    def test_part_suppression_and_visibility_coexist(self):
        data = _v2(
            partMutations={
                "suppression": [{"object": "X", "suppressed": True}],
                "visibility": [{"object": "X", "visible": True}],
            }
        )
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)

    def test_assembly_suppression_and_visibility_coexist(self):
        data = _v2(
            assemblyMutations={
                "suppression": [{"object": "X", "suppressed": True}],
                "visibility": [{"object": "X", "visible": True}],
            }
        )
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)


class TestCrossScopeConflicts(unittest.TestCase):
    def _entry(self, family, object_name):
        if family == "deletion":
            return {"object": object_name}
        if family == "suppression":
            return {"object": object_name, "suppressed": True}
        return {"object": object_name, "visible": True}

    def test_cross_scope_family_matrix(self):
        combos = [
            ("suppression", "suppression"),
            ("suppression", "visibility"),
            ("visibility", "deletion"),
            ("deletion", "suppression"),
        ]
        for assembly_family, part_family in combos:
            with self.subTest(assembly=assembly_family, part=part_family):
                data = _v2(
                    assemblyMutations={assembly_family: [self._entry(assembly_family, "X")]},
                    partMutations={part_family: [self._entry(part_family, "X")]},
                )
                result = mv.validate_export_manifest_v2(data)
                self.assertEqual(
                    [(d.code, d.path) for d in result.diagnostics],
                    [
                        (
                            mv.DIAGNOSTIC_CROSS_SCOPE_MUTATION_OBJECT_CONFLICT,
                            f"partMutations.{part_family}[0].object",
                        )
                    ],
                )

    def test_object_in_multiple_families_both_scopes_reports_once(self):
        data = _v2(
            assemblyMutations={
                "suppression": [{"object": "X", "suppressed": True}],
                "visibility": [{"object": "X", "visible": True}],
            },
            partMutations={
                "suppression": [{"object": "X", "suppressed": True}],
                "visibility": [{"object": "X", "visible": True}],
            },
        )
        result = mv.validate_export_manifest_v2(data)
        cross = [
            d for d in result.diagnostics
            if d.code == mv.DIAGNOSTIC_CROSS_SCOPE_MUTATION_OBJECT_CONFLICT
        ]
        self.assertEqual(len(cross), 1)
        self.assertEqual(cross[0].path, "partMutations.suppression[0].object")

    def test_distinct_objects_across_scopes_do_not_conflict(self):
        data = _v2(
            assemblyMutations={"suppression": [{"object": "AsmOnly", "suppressed": True}]},
            partMutations={"suppression": [{"object": "PartOnly", "suppressed": True}]},
        )
        self.assertTrue(mv.validate_export_manifest_v2(data).is_valid)


class TestDiagnosticOrdering(unittest.TestCase):
    def test_root_missing_fields_precede_unknown_fields(self):
        result = mv.validate_export_manifest_v2({"zzzRoot": 1, "aaaRoot": 2})
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [
                (mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD, "schemaVersion"),
                (mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD, "sourceDocument"),
                (mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD, "parameterAssignments"),
                (mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD, "outputs"),
                (mv.DIAGNOSTIC_UNKNOWN_FIELD, "aaaRoot"),
                (mv.DIAGNOSTIC_UNKNOWN_FIELD, "zzzRoot"),
            ],
        )

    def test_assembly_mutations_validated_before_part_mutations(self):
        # partMutations is inserted before assemblyMutations in the dict to
        # prove ordering is contract-driven, not input-key-order-driven.
        data = _v2(
            partMutations={"suppression": [{"object": "", "suppressed": True}]},
            assemblyMutations={"suppression": [{"object": "", "suppressed": True}]},
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertEqual(
            [d.path for d in result.diagnostics],
            [
                "assemblyMutations.suppression[0].object",
                "partMutations.suppression[0].object",
            ],
        )

    def test_family_order_within_scope_is_suppression_visibility_deletion(self):
        data = _v2(
            assemblyMutations={
                "deletion": [{"object": "", }],
                "suppression": [{"object": "", "suppressed": True}],
                "visibility": [{"object": "", "visible": True}],
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertEqual(
            [d.path for d in result.diagnostics],
            [
                "assemblyMutations.suppression[0].object",
                "assemblyMutations.visibility[0].object",
                "assemblyMutations.deletion[0].object",
            ],
        )

    def test_entries_validated_in_input_array_order(self):
        data = _v2(
            assemblyMutations={
                "deletion": [{"object": "B", "x": 1}, {"object": "A", "y": 1}],
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [
                (mv.DIAGNOSTIC_UNKNOWN_MUTATION_ENTRY_FIELD, "assemblyMutations.deletion[0].x"),
                (mv.DIAGNOSTIC_UNKNOWN_MUTATION_ENTRY_FIELD, "assemblyMutations.deletion[1].y"),
            ],
        )

    def test_unknown_then_type_ordering_within_one_entry(self):
        data = _v2(
            assemblyMutations={
                "suppression": [{"object": "", "suppressed": 0, "extra": 1}],
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertEqual(
            [(d.code, d.path) for d in result.diagnostics],
            [
                (mv.DIAGNOSTIC_UNKNOWN_MUTATION_ENTRY_FIELD, "assemblyMutations.suppression[0].extra"),
                (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE, "assemblyMutations.suppression[0].object"),
                (mv.DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE, "assemblyMutations.suppression[0].suppressed"),
            ],
        )

    def test_compound_conflict_ordering_is_deterministic_across_repeated_calls(self):
        data = _v2(
            assemblyMutations={
                "suppression": [{"object": "X", "suppressed": True}],
                "visibility": [{"object": "Y", "visible": True}],
                "deletion": [{"object": "X"}, {"object": "Y"}],
            },
            partMutations={
                "suppression": [{"object": "X", "suppressed": True}],
            },
        )
        expected = [
            (mv.DIAGNOSTIC_MUTATION_FAMILY_CONFLICT, "assemblyMutations.deletion[0].object"),
            (mv.DIAGNOSTIC_MUTATION_FAMILY_CONFLICT, "assemblyMutations.deletion[1].object"),
            (
                mv.DIAGNOSTIC_CROSS_SCOPE_MUTATION_OBJECT_CONFLICT,
                "partMutations.suppression[0].object",
            ),
        ]
        for _ in range(10):
            result = mv.validate_export_manifest_v2(data)
            self.assertEqual([(d.code, d.path) for d in result.diagnostics], expected)


class TestInputImmutability(unittest.TestCase):
    def _assert_unchanged(self, data):
        before = copy.deepcopy(data)
        mv.validate_export_manifest_v2(data)
        self.assertEqual(data, before)

    def test_valid_full_v2_not_mutated(self):
        self._assert_unchanged(copy.deepcopy(FULL_V2_POSITIVE))

    def test_duplicate_family_failure_not_mutated(self):
        data = _v2(
            assemblyMutations={
                "suppression": [
                    {"object": "Pad", "suppressed": True},
                    {"object": "Pad", "suppressed": False},
                ]
            }
        )
        self._assert_unchanged(data)

    def test_same_scope_conflict_not_mutated(self):
        data = _v2(
            partMutations={
                "suppression": [{"object": "X", "suppressed": True}],
                "deletion": [{"object": "X"}],
            }
        )
        self._assert_unchanged(data)

    def test_cross_scope_conflict_not_mutated(self):
        data = _v2(
            assemblyMutations={"suppression": [{"object": "X", "suppressed": True}]},
            partMutations={"suppression": [{"object": "X", "suppressed": True}]},
        )
        self._assert_unchanged(data)

    def test_unknown_collection_not_mutated(self):
        data = _v2(assemblyMutations={"unknown": []})
        self._assert_unchanged(data)

    def test_no_empty_collections_injected_into_sparse_section(self):
        data = _v2(partMutations={"suppression": []})
        before = copy.deepcopy(data)
        mv.validate_export_manifest_v2(data)
        self.assertEqual(data["partMutations"], before["partMutations"])
        self.assertNotIn("visibility", data["partMutations"])
        self.assertNotIn("deletion", data["partMutations"])


class TestCoreFieldParityWithV1(unittest.TestCase):
    """V2 reuses V1 semantics for sourceDocument/parameterAssignments/outputs."""

    def test_empty_source_document_rejected_same_as_v1(self):
        v1 = mv.validate_export_manifest_v1(_v2_as_v1(sourceDocument=""))
        v2 = mv.validate_export_manifest_v2(_v2(sourceDocument=""))
        self.assertEqual(
            [d.code for d in v1.diagnostics if d.path == "sourceDocument"],
            [d.code for d in v2.diagnostics if d.path == "sourceDocument"],
        )

    def test_non_list_parameter_assignments_rejected_same_as_v1(self):
        v1 = mv.validate_export_manifest_v1(_v2_as_v1(parameterAssignments="bad"))
        v2 = mv.validate_export_manifest_v2(_v2(parameterAssignments="bad"))
        self.assertEqual(
            [d.code for d in v1.diagnostics if d.path == "parameterAssignments"],
            [d.code for d in v2.diagnostics if d.path == "parameterAssignments"],
        )
        self.assertIn(mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENTS_TYPE, [d.code for d in v2.diagnostics])

    def test_unsupported_output_format_rejected_same_as_v1(self):
        v1 = mv.validate_export_manifest_v1(
            _v2_as_v1(outputs=[{"id": "o", "format": "stl", "path": "p"}])
        )
        v2 = mv.validate_export_manifest_v2(
            _v2(outputs=[{"id": "o", "format": "stl", "path": "p"}])
        )
        v1_format_codes = [d.code for d in v1.diagnostics if d.path == "outputs[0].format"]
        v2_format_codes = [d.code for d in v2.diagnostics if d.path == "outputs[0].format"]
        self.assertEqual(v1_format_codes, v2_format_codes)
        self.assertEqual(v1_format_codes, [mv.DIAGNOSTIC_UNSUPPORTED_OUTPUT_FORMAT])

    def test_supported_output_formats_unchanged(self):
        for fmt in ("csv", "pdf", "step"):
            with self.subTest(fmt=fmt):
                data = _v2(outputs=[{"id": "o", "format": fmt, "path": "p"}])
                result = mv.validate_export_manifest_v2(data)
                self.assertNotIn(
                    mv.DIAGNOSTIC_UNSUPPORTED_OUTPUT_FORMAT,
                    [d.code for d in result.diagnostics],
                )


def _v2_as_v1(**overrides):
    data = dict(MINIMAL_V1)
    data.update(overrides)
    return data


class TestRuntimeRemainsV1Only(unittest.TestCase):
    """The runtime execution entrypoint must not gain V2 acceptance."""

    def test_entrypoints_module_imports_only_v1_validator(self):
        from parametron_freecad.runtime import entrypoints

        self.assertTrue(hasattr(entrypoints, "validate_export_manifest_v1"))
        self.assertFalse(hasattr(entrypoints, "validate_export_manifest_v2"))
        self.assertFalse(hasattr(entrypoints, "validate_export_manifest"))

    def test_entrypoints_source_has_no_v2_symbols(self):
        import inspect

        from parametron_freecad.runtime import entrypoints

        source = inspect.getsource(entrypoints)
        for forbidden in (
            "EXPORT_MANIFEST_V2_CONTRACT",
            "assemblyMutations",
            "partMutations",
            "validate_export_manifest_v2",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_real_v1_validator_rejects_v2_mutation_bearing_manifest_before_freecad_open(self):
        """A schema 2.0 mutation-bearing manifest reaches the runtime's real
        (unmocked) V1 validator and is rejected before any document is opened
        or mutated — proving the runtime cannot silently accept-and-ignore V2
        mutations."""
        from parametron_freecad.runtime import entrypoints

        calls: list[str] = []
        working_copy = Path("/tmp/working-copy").resolve()
        manifest_path = working_copy / "export_manifest_v1.json"
        manifest_data = {
            "schemaVersion": "2.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [],
            "outputs": [],
            "assemblyMutations": {
                "suppression": [{"object": "Body.Feature", "suppressed": True}],
                "deletion": [{"object": "Body.Scrap"}],
            },
        }
        loaded_manifest = LoadedManifest(path=manifest_path, data=manifest_data)

        @contextmanager
        def fake_open(*args, **kwargs):
            del args, kwargs
            calls.append("open")
            yield object()

        dependencies = entrypoints._ExecutionEntrypointDependencies(
            apply_parameter_assignments=lambda *args: calls.append("assign"),
            recompute_document=lambda *args: calls.append("recompute"),
            save_document=lambda *args: calls.append("save"),
            export_step_artifacts=lambda *args, **kwargs: calls.append("step"),
            export_csv_artifacts=lambda *args, **kwargs: calls.append("csv"),
            export_pdf_artifacts=lambda *args, **kwargs: calls.append("pdf"),
            opened_freecad_document=fake_open,
            write_success_result=lambda *args: calls.append("result"),
        )

        with mock.patch.object(
            entrypoints, "load_export_manifest_v1", return_value=loaded_manifest
        ), self.assertRaises(entrypoints.ExecutionEntrypointError) as ctx:
            entrypoints.run_execution_entrypoint(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=working_copy / "result.json",
                freecad_module=object(),
                _dependencies=dependencies,
            )

        self.assertEqual(calls, [])
        self.assertIn("manifest validation failed", str(ctx.exception))


class TestImportIsolation(unittest.TestCase):
    """V2 validation is pure structural validation with no FreeCAD dependency."""

    def test_module_imports_without_freecad(self):
        import sys

        import parametron_freecad.execution.manifest_validation  # noqa: F401

        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_validate_export_manifest_v2_is_callable_without_freecad_module_present(self):
        self.assertTrue(mv.validate_export_manifest_v2(MINIMAL_V2).is_valid)


class TestLoaderBoundaryIntegration(unittest.TestCase):
    """Loader duplicate-key rejection is a distinct contract from mutation
    duplicate-object rejection; both must independently hold."""

    def test_loader_rejects_duplicate_json_object_keys_before_mutation_validation(self):
        import tempfile
        from pathlib import Path as _Path

        from parametron_freecad.execution.manifest_loader import (
            ManifestDuplicateKeyError,
            load_export_manifest_v1,
        )

        raw = (
            '{"schemaVersion": "2.0", "sourceDocument": "m.FCStd", '
            '"parameterAssignments": [], "outputs": [], '
            '"assemblyMutations": {"suppression": []}, '
            '"assemblyMutations": {"visibility": []}}'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _Path(tmp) / "manifest.json"
            path.write_text(raw, encoding="utf-8")
            with self.assertRaises(ManifestDuplicateKeyError):
                load_export_manifest_v1(path)

    def test_duplicate_mutation_object_value_is_a_separate_validator_level_contract(self):
        # Distinct from duplicate JSON *keys*: this is a duplicate *value*
        # (the same "object" string) across two array entries within one
        # already-decoded, key-valid collection.
        data = _v2(
            assemblyMutations={
                "deletion": [{"object": "Pad"}, {"object": "Pad"}],
            }
        )
        result = mv.validate_export_manifest_v2(data)
        self.assertIn(
            mv.DIAGNOSTIC_DUPLICATE_MUTATION_OBJECT,
            [d.code for d in result.diagnostics],
        )


if __name__ == "__main__":
    unittest.main()
