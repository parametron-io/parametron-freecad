"""Canonical schema-1 manifest mutation contract metadata."""

from __future__ import annotations

import subprocess
import sys
import types
import unittest
from dataclasses import FrozenInstanceError


class TestImportSafety(unittest.TestCase):
    """The contract module must import without FreeCAD/GUI or side effects."""

    def test_import_succeeds_without_freecad(self):
        import parametron_freecad.execution.manifest_contract as mc  # noqa: F401

    def test_module_is_a_module(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.assertIsInstance(mc, types.ModuleType)

    def test_no_freecad_in_sys_modules_after_import(self):
        import sys as _sys

        import parametron_freecad.execution.manifest_contract  # noqa: F401

        self.assertNotIn("FreeCAD", _sys.modules)
        self.assertNotIn("FreeCADGui", _sys.modules)
        self.assertNotIn("freecad", _sys.modules)

    def test_subprocess_import_does_not_touch_freecad(self):
        # Independent-process proof: importing the contract module alone must
        # not pull in FreeCAD/FreeCADGui, and must not require a filesystem
        # or runtime host beyond the Python import machinery itself.
        code = (
            "import sys; "
            "import parametron_freecad.execution.manifest_contract as mc; "
            "assert 'FreeCAD' not in sys.modules; "
            "assert 'FreeCADGui' not in sys.modules; "
            "print('OK')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)


class TestV1ClosurePermanent(unittest.TestCase):
    """Schema 1.0 includes optional, closed target-mutation sections."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_v1_filename_constant(self):
        self.assertEqual(self.mc.EXPORT_MANIFEST_V1_FILENAME, "prm.export-manifest.json")

    def test_v1_schema_version_constant(self):
        self.assertEqual(self.mc.EXPORT_MANIFEST_SCHEMA_VERSION, "1.0")

    def test_explicit_v1_alias_constant_exists_and_matches(self):
        self.assertTrue(hasattr(self.mc, "EXPORT_MANIFEST_SCHEMA_VERSION_V1"))
        self.assertEqual(self.mc.EXPORT_MANIFEST_SCHEMA_VERSION_V1, "1.0")
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_SCHEMA_VERSION_V1,
            self.mc.EXPORT_MANIFEST_SCHEMA_VERSION,
        )

    def test_v1_top_level_fields_exact_and_ordered(self):
        self.assertEqual(
            self.mc.TOP_LEVEL_FIELDS,
            ("schemaVersion", "sourceDocument", "parameterAssignments", "outputs", "assemblyMutations", "partMutations"),
        )

    def test_v1_top_level_fields_is_tuple_of_six(self):
        self.assertIsInstance(self.mc.TOP_LEVEL_FIELDS, tuple)
        self.assertEqual(len(self.mc.TOP_LEVEL_FIELDS), 6)

    def test_v1_contract_object_includes_optional_mutations(self):
        contract = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        self.assertEqual(contract.top_level_fields, self.mc.TOP_LEVEL_FIELDS)
        self.assertEqual(len(contract.top_level_fields), 6)

    def test_v1_contract_exposes_assembly_mutations_field(self):
        self.assertIn("assemblyMutations", self.mc.OPTIONAL_TOP_LEVEL_FIELDS)

    def test_v1_contract_exposes_part_mutations_field(self):
        self.assertIn("partMutations", self.mc.OPTIONAL_TOP_LEVEL_FIELDS)

    def test_v1_contract_dataclass_has_mutation_attributes(self):
        contract = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        self.assertTrue(hasattr(contract, "assembly_mutations"))
        self.assertTrue(hasattr(contract, "part_mutations"))
        self.assertTrue(hasattr(contract, "assembly_mutations_field"))
        self.assertTrue(hasattr(contract, "part_mutations_field"))

    def test_v1_contract_schema_version_still_1_0(self):
        self.assertEqual(self.mc.EXPORT_MANIFEST_V1_CONTRACT.schema_version, "1.0")

    def test_v1_contract_filename_unchanged(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.filename, "prm.export-manifest.json"
        )

    def test_v1_public_names_still_present(self):
        for name in (
            "EXPORT_MANIFEST_V1_FILENAME",
            "EXPORT_MANIFEST_SCHEMA_VERSION",
            "EXPORT_MANIFEST_V1_CONTRACT",
            "TOP_LEVEL_FIELDS",
            "FIELD_SCHEMA_VERSION",
            "FIELD_SOURCE_DOCUMENT",
            "FIELD_PARAMETER_ASSIGNMENTS",
            "FIELD_OUTPUTS",
            "ManifestContract",
            "ParameterAssignmentContract",
            "OutputContract",
            "PARAMETER_ASSIGNMENT_CONTRACT",
            "OUTPUT_CONTRACT",
            "SUPPORTED_OUTPUT_FORMATS",
            "supported_output_formats",
        ):
            self.assertTrue(hasattr(self.mc, name), f"Missing public V1 name: {name}")


class TestCanonicalTopLevelFields(unittest.TestCase):
    """Exact required/optional/allowed top-level canonical fields, order included."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_required_top_level_fields_exact(self):
        self.assertEqual(
            self.mc.REQUIRED_TOP_LEVEL_FIELDS,
            ("schemaVersion", "sourceDocument", "parameterAssignments", "outputs"),
        )

    def test_optional_top_level_fields_exact(self):
        self.assertEqual(
            self.mc.OPTIONAL_TOP_LEVEL_FIELDS,
            ("assemblyMutations", "partMutations"),
        )

    def test_all_top_level_fields_exact_order(self):
        self.assertEqual(
            self.mc.TOP_LEVEL_FIELDS,
            (
                "schemaVersion",
                "sourceDocument",
                "parameterAssignments",
                "outputs",
                "assemblyMutations",
                "partMutations",
            ),
        )

    def test_all_top_level_fields_is_required_plus_optional(self):
        self.assertEqual(
            self.mc.TOP_LEVEL_FIELDS,
            self.mc.REQUIRED_TOP_LEVEL_FIELDS + self.mc.OPTIONAL_TOP_LEVEL_FIELDS,
        )

    def test_required_fields_are_tuple(self):
        self.assertIsInstance(self.mc.REQUIRED_TOP_LEVEL_FIELDS, tuple)

    def test_optional_fields_are_tuple(self):
        self.assertIsInstance(self.mc.OPTIONAL_TOP_LEVEL_FIELDS, tuple)

    def test_all_fields_are_tuple(self):
        self.assertIsInstance(self.mc.TOP_LEVEL_FIELDS, tuple)

    def test_required_top_level_fields_reuse_v1_top_level_fields_object(self):
        # Both schemas share the four required core fields.
        self.assertIs(self.mc.REQUIRED_TOP_LEVEL_FIELDS, self.mc.REQUIRED_TOP_LEVEL_FIELDS)

    def test_canonical_contract_required_fields_match_module_constant(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.required_top_level_fields,
            self.mc.REQUIRED_TOP_LEVEL_FIELDS,
        )

    def test_canonical_contract_optional_fields_match_module_constant(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.optional_top_level_fields,
            self.mc.OPTIONAL_TOP_LEVEL_FIELDS,
        )

    def test_canonical_contract_all_top_level_fields_match_module_constant(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.top_level_fields,
            self.mc.TOP_LEVEL_FIELDS,
        )

    def test_individual_mutation_field_name_constants(self):
        self.assertEqual(self.mc.FIELD_ASSEMBLY_MUTATIONS, "assemblyMutations")
        self.assertEqual(self.mc.FIELD_PART_MUTATIONS, "partMutations")


class TestSuppressionMetadata(unittest.TestCase):
    """Exact suppression collection name and entry field shape."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_collection_name_constant(self):
        self.assertEqual(self.mc.MUTATION_COLLECTION_SUPPRESSION, "suppression")

    def test_entry_fields_exact_tuple(self):
        self.assertEqual(self.mc.SUPPRESSION_ENTRY_FIELDS, ("object", "suppressed"))

    def test_entry_fields_is_tuple(self):
        self.assertIsInstance(self.mc.SUPPRESSION_ENTRY_FIELDS, tuple)

    def test_object_field_constant(self):
        self.assertEqual(self.mc.MUTATION_ENTRY_FIELD_OBJECT, "object")

    def test_suppressed_field_constant(self):
        self.assertEqual(self.mc.SUPPRESSION_ENTRY_FIELD_SUPPRESSED, "suppressed")

    def test_contract_object_fields_match_tuple(self):
        contract = self.mc.SUPPRESSION_ENTRY_CONTRACT
        self.assertEqual(contract.fields, self.mc.SUPPRESSION_ENTRY_FIELDS)

    def test_contract_object_field_attributes(self):
        contract = self.mc.SUPPRESSION_ENTRY_CONTRACT
        self.assertEqual(contract.object_field, "object")
        self.assertEqual(contract.suppressed_field, "suppressed")

    def test_forbidden_fields_absent_from_entry(self):
        forbidden = {
            "visible",
            "action",
            "targetKind",
            "semanticId",
            "force",
            "cascade",
            "dependencyPolicy",
        }
        self.assertTrue(forbidden.isdisjoint(set(self.mc.SUPPRESSION_ENTRY_FIELDS)))

    def test_entry_field_count_is_exactly_two(self):
        self.assertEqual(len(self.mc.SUPPRESSION_ENTRY_FIELDS), 2)


class TestVisibilityMetadata(unittest.TestCase):
    """Exact visibility collection name and entry field shape."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_collection_name_constant(self):
        self.assertEqual(self.mc.MUTATION_COLLECTION_VISIBILITY, "visibility")

    def test_entry_fields_exact_tuple(self):
        self.assertEqual(self.mc.VISIBILITY_ENTRY_FIELDS, ("object", "visible"))

    def test_entry_fields_is_tuple(self):
        self.assertIsInstance(self.mc.VISIBILITY_ENTRY_FIELDS, tuple)

    def test_visible_field_constant(self):
        self.assertEqual(self.mc.VISIBILITY_ENTRY_FIELD_VISIBLE, "visible")

    def test_contract_object_fields_match_tuple(self):
        contract = self.mc.VISIBILITY_ENTRY_CONTRACT
        self.assertEqual(contract.fields, self.mc.VISIBILITY_ENTRY_FIELDS)

    def test_contract_object_field_attributes(self):
        contract = self.mc.VISIBILITY_ENTRY_CONTRACT
        self.assertEqual(contract.object_field, "object")
        self.assertEqual(contract.visible_field, "visible")

    def test_visibility_structurally_distinct_from_suppression(self):
        self.assertNotEqual(
            self.mc.VISIBILITY_ENTRY_FIELD_VISIBLE,
            self.mc.SUPPRESSION_ENTRY_FIELD_SUPPRESSED,
        )
        self.assertNotEqual(
            self.mc.VISIBILITY_ENTRY_FIELDS, self.mc.SUPPRESSION_ENTRY_FIELDS
        )

    def test_no_generic_ambiguous_boolean_field_name(self):
        # A generic "state" or "value" boolean field would blur suppression vs
        # visibility semantics; only the named visible/suppressed fields exist.
        forbidden = {"state", "value", "enabled", "hidden"}
        self.assertTrue(forbidden.isdisjoint(set(self.mc.VISIBILITY_ENTRY_FIELDS)))

    def test_no_gui_module_referenced(self):
        import inspect

        source = inspect.getsource(self.mc)
        self.assertNotIn("FreeCADGui", source)
        self.assertNotIn("import FreeCADGui", source)

    def test_entry_field_count_is_exactly_two(self):
        self.assertEqual(len(self.mc.VISIBILITY_ENTRY_FIELDS), 2)


class TestDeletionMetadata(unittest.TestCase):
    """Exact deletion collection name and entry field shape."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_collection_name_constant(self):
        self.assertEqual(self.mc.MUTATION_COLLECTION_DELETION, "deletion")

    def test_entry_fields_exact_tuple(self):
        self.assertEqual(self.mc.DELETION_ENTRY_FIELDS, ("object",))

    def test_entry_fields_is_tuple(self):
        self.assertIsInstance(self.mc.DELETION_ENTRY_FIELDS, tuple)

    def test_entry_field_count_is_exactly_one(self):
        self.assertEqual(len(self.mc.DELETION_ENTRY_FIELDS), 1)

    def test_contract_object_fields_match_tuple(self):
        contract = self.mc.DELETION_ENTRY_CONTRACT
        self.assertEqual(contract.fields, self.mc.DELETION_ENTRY_FIELDS)

    def test_contract_object_field_attribute(self):
        self.assertEqual(self.mc.DELETION_ENTRY_CONTRACT.object_field, "object")

    def test_forbidden_fields_absent_from_entry(self):
        forbidden = {
            "force",
            "cascade",
            "recursive",
            "dependencyPolicy",
            "action",
            "targetKind",
            "semanticId",
        }
        self.assertTrue(forbidden.isdisjoint(set(self.mc.DELETION_ENTRY_FIELDS)))


class TestSharedMutationSectionMetadata(unittest.TestCase):
    """Exact section collection names, ordering, and part/assembly sharing."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_section_fields_exact_order(self):
        self.assertEqual(
            self.mc.TARGET_MUTATION_SECTION_FIELDS,
            ("suppression", "visibility", "deletion"),
        )

    def test_section_fields_is_tuple(self):
        self.assertIsInstance(self.mc.TARGET_MUTATION_SECTION_FIELDS, tuple)

    def test_section_contract_fields_match_tuple(self):
        contract = self.mc.TARGET_MUTATION_SECTION_CONTRACT
        self.assertEqual(contract.fields, self.mc.TARGET_MUTATION_SECTION_FIELDS)

    def test_section_contract_field_name_attributes(self):
        contract = self.mc.TARGET_MUTATION_SECTION_CONTRACT
        self.assertEqual(contract.suppression_field, "suppression")
        self.assertEqual(contract.visibility_field, "visibility")
        self.assertEqual(contract.deletion_field, "deletion")

    def test_section_contract_entry_contracts_are_the_singleton_objects(self):
        contract = self.mc.TARGET_MUTATION_SECTION_CONTRACT
        self.assertIs(contract.suppression_entry, self.mc.SUPPRESSION_ENTRY_CONTRACT)
        self.assertIs(contract.visibility_entry, self.mc.VISIBILITY_ENTRY_CONTRACT)
        self.assertIs(contract.deletion_entry, self.mc.DELETION_ENTRY_CONTRACT)

    def test_assembly_and_part_mutations_share_same_section_contract_object(self):
        canonical = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        self.assertIs(canonical.assembly_mutations, canonical.part_mutations)

    def test_assembly_and_part_mutations_are_the_module_singleton(self):
        canonical = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        self.assertIs(canonical.assembly_mutations, self.mc.TARGET_MUTATION_SECTION_CONTRACT)
        self.assertIs(canonical.part_mutations, self.mc.TARGET_MUTATION_SECTION_CONTRACT)

    def test_no_extra_mutation_collections_beyond_the_three(self):
        allowed = {"suppression", "visibility", "deletion"}
        self.assertEqual(set(self.mc.TARGET_MUTATION_SECTION_FIELDS), allowed)


class TestParameterOutputContractReuse(unittest.TestCase):
    """canonical reuse the exact same parameter-assignment/output metadata."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_v1_and_canonical_share_same_parameter_assignment_contract_object(self):
        v1 = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        canonical = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        self.assertIs(v1.parameter_assignment, canonical.parameter_assignment)

    def test_v1_and_canonical_share_same_output_contract_object(self):
        v1 = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        canonical = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        self.assertIs(v1.output, canonical.output)

    def test_canonical_parameter_assignment_is_module_singleton(self):
        self.assertIs(
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.parameter_assignment,
            self.mc.PARAMETER_ASSIGNMENT_CONTRACT,
        )

    def test_canonical_output_is_module_singleton(self):
        self.assertIs(
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.output, self.mc.OUTPUT_CONTRACT
        )

    def test_parameter_assignment_field_tuple_unchanged(self):
        self.assertEqual(
            self.mc.PARAMETER_ASSIGNMENT_FIELDS, ("target", "value", "valueKind")
        )

    def test_output_field_tuple_unchanged(self):
        self.assertEqual(self.mc.OUTPUT_FIELDS, ("id", "format", "path"))

    def test_supported_output_formats_unchanged(self):
        self.assertEqual(self.mc.SUPPORTED_OUTPUT_FORMATS, ("csv", "pdf", "step"))

    def test_canonical_contract_field_name_attributes_match_v1(self):
        v1 = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        canonical = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        self.assertEqual(v1.schema_version_field, canonical.schema_version_field)
        self.assertEqual(v1.source_document_field, canonical.source_document_field)
        self.assertEqual(v1.parameter_assignments_field, canonical.parameter_assignments_field)
        self.assertEqual(v1.outputs_field, canonical.outputs_field)


class TestForbiddenMutationCollections(unittest.TestCase):
    """No mutation family beyond suppression/visibility/deletion exists."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_no_parameters_mutation_collection(self):
        self.assertNotIn("parameters", self.mc.TARGET_MUTATION_SECTION_FIELDS)

    def test_no_properties_mutation_collection(self):
        self.assertNotIn("properties", self.mc.TARGET_MUTATION_SECTION_FIELDS)

    def test_no_keep_representation_in_any_entry_fields(self):
        all_entry_fields = (
            self.mc.SUPPRESSION_ENTRY_FIELDS
            + self.mc.VISIBILITY_ENTRY_FIELDS
            + self.mc.DELETION_ENTRY_FIELDS
        )
        self.assertNotIn("keep", all_entry_fields)

    def test_no_keep_top_level_or_section_field(self):
        self.assertNotIn("keep", self.mc.TOP_LEVEL_FIELDS)
        self.assertNotIn("keep", self.mc.TARGET_MUTATION_SECTION_FIELDS)

    def test_section_fields_contain_only_the_three_known_families(self):
        self.assertEqual(
            set(self.mc.TARGET_MUTATION_SECTION_FIELDS),
            {"suppression", "visibility", "deletion"},
        )


class TestForbiddenTargetFields(unittest.TestCase):
    """No mutation entry contract exposes any forbidden Task 3+ target field."""

    FORBIDDEN_FIELDS = (
        "targetKind",
        "target_kind",
        "semanticId",
        "semanticID",
        "semantic_id",
        "featureId",
        "componentId",
        "action",
        "force",
        "cascade",
        "recursive",
        "dependencyPolicy",
        "dependency_policy",
    )

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc
        self.all_entry_field_tuples = {
            "suppression": self.mc.SUPPRESSION_ENTRY_FIELDS,
            "visibility": self.mc.VISIBILITY_ENTRY_FIELDS,
            "deletion": self.mc.DELETION_ENTRY_FIELDS,
        }

    def test_no_forbidden_field_in_any_mutation_entry_field_tuple(self):
        for entry_name, fields in self.all_entry_field_tuples.items():
            for forbidden in self.FORBIDDEN_FIELDS:
                with self.subTest(entry=entry_name, forbidden=forbidden):
                    self.assertNotIn(forbidden, fields)

    def test_no_forbidden_field_in_top_level_or_section_fields(self):
        combined = self.mc.TOP_LEVEL_FIELDS + self.mc.TARGET_MUTATION_SECTION_FIELDS
        for forbidden in self.FORBIDDEN_FIELDS:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, combined)

    def test_suppression_entry_contract_has_no_forbidden_attribute(self):
        contract = self.mc.SUPPRESSION_ENTRY_CONTRACT
        for forbidden in self.FORBIDDEN_FIELDS:
            with self.subTest(forbidden=forbidden):
                self.assertFalse(hasattr(contract, forbidden))

    def test_visibility_entry_contract_has_no_forbidden_attribute(self):
        contract = self.mc.VISIBILITY_ENTRY_CONTRACT
        for forbidden in self.FORBIDDEN_FIELDS:
            with self.subTest(forbidden=forbidden):
                self.assertFalse(hasattr(contract, forbidden))

    def test_deletion_entry_contract_has_no_forbidden_attribute(self):
        contract = self.mc.DELETION_ENTRY_CONTRACT
        for forbidden in self.FORBIDDEN_FIELDS:
            with self.subTest(forbidden=forbidden):
                self.assertFalse(hasattr(contract, forbidden))


class TestImmutability(unittest.TestCase):
    """New structured Canonical metadata is frozen; field collections are tuples."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_export_manifest_canonical_contract_rejects_field_mutation(self):
        with self.assertRaises((TypeError, AttributeError, FrozenInstanceError)):
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.schema_version = "mutated"

    def test_target_mutation_section_contract_rejects_field_mutation(self):
        with self.assertRaises((TypeError, AttributeError, FrozenInstanceError)):
            self.mc.TARGET_MUTATION_SECTION_CONTRACT.suppression_field = "mutated"

    def test_suppression_entry_contract_rejects_field_mutation(self):
        with self.assertRaises((TypeError, AttributeError, FrozenInstanceError)):
            self.mc.SUPPRESSION_ENTRY_CONTRACT.object_field = "mutated"

    def test_visibility_entry_contract_rejects_field_mutation(self):
        with self.assertRaises((TypeError, AttributeError, FrozenInstanceError)):
            self.mc.VISIBILITY_ENTRY_CONTRACT.object_field = "mutated"

    def test_deletion_entry_contract_rejects_field_mutation(self):
        with self.assertRaises((TypeError, AttributeError, FrozenInstanceError)):
            self.mc.DELETION_ENTRY_CONTRACT.object_field = "mutated"

    def test_canonical_required_top_level_fields_is_immutable_tuple(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.REQUIRED_TOP_LEVEL_FIELDS[0] = "other"

    def test_canonical_optional_top_level_fields_is_immutable_tuple(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.OPTIONAL_TOP_LEVEL_FIELDS[0] = "other"

    def test_canonical_top_level_fields_is_immutable_tuple(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.TOP_LEVEL_FIELDS[0] = "other"

    def test_target_mutation_section_fields_is_immutable_tuple(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.TARGET_MUTATION_SECTION_FIELDS[0] = "other"

    def test_suppression_entry_fields_is_immutable_tuple(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.SUPPRESSION_ENTRY_FIELDS[0] = "other"

    def test_visibility_entry_fields_is_immutable_tuple(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.VISIBILITY_ENTRY_FIELDS[0] = "other"

    def test_deletion_entry_fields_is_immutable_tuple(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.DELETION_ENTRY_FIELDS[0] = "other"

    def test_all_new_field_collections_are_tuples(self):
        for name in (
            "REQUIRED_TOP_LEVEL_FIELDS",
            "OPTIONAL_TOP_LEVEL_FIELDS",
            "TOP_LEVEL_FIELDS",
            "TARGET_MUTATION_SECTION_FIELDS",
            "SUPPRESSION_ENTRY_FIELDS",
            "VISIBILITY_ENTRY_FIELDS",
            "DELETION_ENTRY_FIELDS",
        ):
            with self.subTest(name=name):
                self.assertIsInstance(getattr(self.mc, name), tuple)


class TestNoRuntimeBehaviorExposedOnCanonicalSurface(unittest.TestCase):
    """The Canonical metadata surface must not expose execution/runtime helpers."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def _assert_absent(self, name: str):
        self.assertFalse(
            hasattr(self.mc, name), f"Contract module must not expose '{name}'"
        )

    def test_no_apply_suppression(self):
        self._assert_absent("apply_suppression")

    def test_no_apply_visibility(self):
        self._assert_absent("apply_visibility")

    def test_no_apply_deletion(self):
        self._assert_absent("apply_deletion")

    def test_no_execute_mutations(self):
        self._assert_absent("execute_mutations")

    def test_no_validate_export_manifest_canonical(self):
        self._assert_absent("validate_export_manifest_canonical")

    def test_no_parse_mutations(self):
        self._assert_absent("parse_mutations")


if __name__ == "__main__":
    unittest.main()
