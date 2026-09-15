"""Permanent Task 2 contract tests for schema 2.0 manifest metadata.

These tests lock the schema 2.0 *metadata/type* surface added to
``parametron_freecad.execution.manifest_contract``. They do not exercise
Task 3 behavior (schema dispatch, mutation parsing, conflict validation,
runtime mutation execution) — those remain deliberately unimplemented and
this module asserts that they stay unimplemented.
"""

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
    """schema 1.0 remains permanently closed and unchanged by Task 2."""

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
            ("schemaVersion", "sourceDocument", "parameterAssignments", "outputs"),
        )

    def test_v1_top_level_fields_is_tuple_of_four(self):
        self.assertIsInstance(self.mc.TOP_LEVEL_FIELDS, tuple)
        self.assertEqual(len(self.mc.TOP_LEVEL_FIELDS), 4)

    def test_v1_contract_object_is_exactly_four_field(self):
        contract = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        self.assertEqual(contract.top_level_fields, self.mc.TOP_LEVEL_FIELDS)
        self.assertEqual(len(contract.top_level_fields), 4)

    def test_v1_contract_does_not_expose_assembly_mutations_field(self):
        self.assertNotIn("assemblyMutations", self.mc.TOP_LEVEL_FIELDS)

    def test_v1_contract_does_not_expose_part_mutations_field(self):
        self.assertNotIn("partMutations", self.mc.TOP_LEVEL_FIELDS)

    def test_v1_contract_dataclass_has_no_mutation_attributes(self):
        contract = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        self.assertFalse(hasattr(contract, "assembly_mutations"))
        self.assertFalse(hasattr(contract, "part_mutations"))
        self.assertFalse(hasattr(contract, "assembly_mutations_field"))
        self.assertFalse(hasattr(contract, "part_mutations_field"))

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


class TestV2SchemaVersion(unittest.TestCase):
    """schema 2.0 version constant is exact and distinct from the V1 default."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_v2_schema_version_constant_exact(self):
        self.assertEqual(self.mc.EXPORT_MANIFEST_SCHEMA_VERSION_V2, "2.0")

    def test_v2_contract_schema_version_matches_constant(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V2_CONTRACT.schema_version,
            self.mc.EXPORT_MANIFEST_SCHEMA_VERSION_V2,
        )

    def test_v2_does_not_replace_v1_default_schema_constant(self):
        self.assertEqual(self.mc.EXPORT_MANIFEST_SCHEMA_VERSION, "1.0")
        self.assertNotEqual(
            self.mc.EXPORT_MANIFEST_SCHEMA_VERSION,
            self.mc.EXPORT_MANIFEST_SCHEMA_VERSION_V2,
        )

    def test_v1_contract_schema_version_still_1_0_after_v2_addition(self):
        self.assertEqual(self.mc.EXPORT_MANIFEST_V1_CONTRACT.schema_version, "1.0")


class TestV2TopLevelFields(unittest.TestCase):
    """Exact required/optional/allowed top-level V2 fields, order included."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_required_top_level_fields_exact(self):
        self.assertEqual(
            self.mc.V2_REQUIRED_TOP_LEVEL_FIELDS,
            ("schemaVersion", "sourceDocument", "parameterAssignments", "outputs"),
        )

    def test_optional_top_level_fields_exact(self):
        self.assertEqual(
            self.mc.V2_OPTIONAL_TOP_LEVEL_FIELDS,
            ("assemblyMutations", "partMutations"),
        )

    def test_all_top_level_fields_exact_order(self):
        self.assertEqual(
            self.mc.V2_TOP_LEVEL_FIELDS,
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
            self.mc.V2_TOP_LEVEL_FIELDS,
            self.mc.V2_REQUIRED_TOP_LEVEL_FIELDS + self.mc.V2_OPTIONAL_TOP_LEVEL_FIELDS,
        )

    def test_required_fields_are_tuple(self):
        self.assertIsInstance(self.mc.V2_REQUIRED_TOP_LEVEL_FIELDS, tuple)

    def test_optional_fields_are_tuple(self):
        self.assertIsInstance(self.mc.V2_OPTIONAL_TOP_LEVEL_FIELDS, tuple)

    def test_all_fields_are_tuple(self):
        self.assertIsInstance(self.mc.V2_TOP_LEVEL_FIELDS, tuple)

    def test_required_top_level_fields_reuse_v1_top_level_fields_object(self):
        # The contract intentionally reuses TOP_LEVEL_FIELDS as the V2 required set.
        self.assertIs(self.mc.V2_REQUIRED_TOP_LEVEL_FIELDS, self.mc.TOP_LEVEL_FIELDS)

    def test_v2_contract_required_fields_match_module_constant(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V2_CONTRACT.required_top_level_fields,
            self.mc.V2_REQUIRED_TOP_LEVEL_FIELDS,
        )

    def test_v2_contract_optional_fields_match_module_constant(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V2_CONTRACT.optional_top_level_fields,
            self.mc.V2_OPTIONAL_TOP_LEVEL_FIELDS,
        )

    def test_v2_contract_all_top_level_fields_match_module_constant(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V2_CONTRACT.top_level_fields,
            self.mc.V2_TOP_LEVEL_FIELDS,
        )

    def test_individual_mutation_field_name_constants(self):
        self.assertEqual(self.mc.FIELD_ASSEMBLY_MUTATIONS, "assemblyMutations")
        self.assertEqual(self.mc.FIELD_PART_MUTATIONS, "partMutations")


class TestTransportFilenameCompatibility(unittest.TestCase):
    """V1 and V2 resolve to the same existing transport filename."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_v2_contract_filename_equals_v1_filename_constant(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V2_CONTRACT.filename,
            self.mc.EXPORT_MANIFEST_V1_FILENAME,
        )

    def test_v1_contract_filename_equals_v1_filename_constant(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.filename,
            self.mc.EXPORT_MANIFEST_V1_FILENAME,
        )

    def test_v1_and_v2_contract_filenames_are_identical_string(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.filename,
            self.mc.EXPORT_MANIFEST_V2_CONTRACT.filename,
        )

    def test_filename_is_exact_transport_name(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V2_CONTRACT.filename, "prm.export-manifest.json"
        )

    def test_no_v2_filename_constant_exists(self):
        # The contract must not introduce a separate v2 transport filename;
        # schema version and transport filename are independent concepts.
        for name in dir(self.mc):
            if name.startswith("_"):
                continue
            value = getattr(self.mc, name)
            if isinstance(value, str) and "export_manifest_v2" in value:
                self.fail(f"Unexpected v2 filename-like constant: {name} = {value!r}")

    def test_no_public_name_literally_named_v2_filename(self):
        self.assertFalse(hasattr(self.mc, "EXPORT_MANIFEST_V2_FILENAME"))


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
        v2 = self.mc.EXPORT_MANIFEST_V2_CONTRACT
        self.assertIs(v2.assembly_mutations, v2.part_mutations)

    def test_assembly_and_part_mutations_are_the_module_singleton(self):
        v2 = self.mc.EXPORT_MANIFEST_V2_CONTRACT
        self.assertIs(v2.assembly_mutations, self.mc.TARGET_MUTATION_SECTION_CONTRACT)
        self.assertIs(v2.part_mutations, self.mc.TARGET_MUTATION_SECTION_CONTRACT)

    def test_no_extra_mutation_collections_beyond_the_three(self):
        allowed = {"suppression", "visibility", "deletion"}
        self.assertEqual(set(self.mc.TARGET_MUTATION_SECTION_FIELDS), allowed)


class TestParameterOutputContractReuse(unittest.TestCase):
    """V1 and V2 reuse the exact same parameter-assignment/output metadata."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_v1_and_v2_share_same_parameter_assignment_contract_object(self):
        v1 = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        v2 = self.mc.EXPORT_MANIFEST_V2_CONTRACT
        self.assertIs(v1.parameter_assignment, v2.parameter_assignment)

    def test_v1_and_v2_share_same_output_contract_object(self):
        v1 = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        v2 = self.mc.EXPORT_MANIFEST_V2_CONTRACT
        self.assertIs(v1.output, v2.output)

    def test_v2_parameter_assignment_is_module_singleton(self):
        self.assertIs(
            self.mc.EXPORT_MANIFEST_V2_CONTRACT.parameter_assignment,
            self.mc.PARAMETER_ASSIGNMENT_CONTRACT,
        )

    def test_v2_output_is_module_singleton(self):
        self.assertIs(
            self.mc.EXPORT_MANIFEST_V2_CONTRACT.output, self.mc.OUTPUT_CONTRACT
        )

    def test_parameter_assignment_field_tuple_unchanged(self):
        self.assertEqual(
            self.mc.PARAMETER_ASSIGNMENT_FIELDS, ("target", "value", "valueKind")
        )

    def test_output_field_tuple_unchanged(self):
        self.assertEqual(self.mc.OUTPUT_FIELDS, ("id", "format", "path"))

    def test_supported_output_formats_unchanged(self):
        self.assertEqual(self.mc.SUPPORTED_OUTPUT_FORMATS, ("csv", "pdf", "step"))

    def test_v2_contract_field_name_attributes_match_v1(self):
        v1 = self.mc.EXPORT_MANIFEST_V1_CONTRACT
        v2 = self.mc.EXPORT_MANIFEST_V2_CONTRACT
        self.assertEqual(v1.schema_version_field, v2.schema_version_field)
        self.assertEqual(v1.source_document_field, v2.source_document_field)
        self.assertEqual(v1.parameter_assignments_field, v2.parameter_assignments_field)
        self.assertEqual(v1.outputs_field, v2.outputs_field)


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
        self.assertNotIn("keep", self.mc.V2_TOP_LEVEL_FIELDS)
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
        combined = self.mc.V2_TOP_LEVEL_FIELDS + self.mc.TARGET_MUTATION_SECTION_FIELDS
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
    """New structured V2 metadata is frozen; field collections are tuples."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_export_manifest_v2_contract_rejects_field_mutation(self):
        with self.assertRaises((TypeError, AttributeError, FrozenInstanceError)):
            self.mc.EXPORT_MANIFEST_V2_CONTRACT.schema_version = "mutated"

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

    def test_v2_required_top_level_fields_is_immutable_tuple(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.V2_REQUIRED_TOP_LEVEL_FIELDS[0] = "other"

    def test_v2_optional_top_level_fields_is_immutable_tuple(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.V2_OPTIONAL_TOP_LEVEL_FIELDS[0] = "other"

    def test_v2_top_level_fields_is_immutable_tuple(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.V2_TOP_LEVEL_FIELDS[0] = "other"

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
            "V2_REQUIRED_TOP_LEVEL_FIELDS",
            "V2_OPTIONAL_TOP_LEVEL_FIELDS",
            "V2_TOP_LEVEL_FIELDS",
            "TARGET_MUTATION_SECTION_FIELDS",
            "SUPPRESSION_ENTRY_FIELDS",
            "VISIBILITY_ENTRY_FIELDS",
            "DELETION_ENTRY_FIELDS",
        ):
            with self.subTest(name=name):
                self.assertIsInstance(getattr(self.mc, name), tuple)


class TestTask2Task3Boundary(unittest.TestCase):
    """Task 2 metadata existence must not activate Task 3 V2 validation/runtime."""

    def _v2_mutation_bearing_payload(self):
        return {
            "schemaVersion": "2.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [],
            "outputs": [],
            "assemblyMutations": {
                "suppression": [{"object": "Body.Feature", "suppressed": True}],
                "visibility": [{"object": "Body.Feature", "visible": False}],
                "deletion": [{"object": "Body.Scrap"}],
            },
        }

    def test_v1_validator_does_not_accept_schema_2_0(self):
        import parametron_freecad.execution.manifest_validation as mv

        result = mv.validate_export_manifest_v1(self._v2_mutation_bearing_payload())
        self.assertFalse(result.is_valid)

    def test_v1_validator_flags_schema_2_0_as_invalid_schema_version(self):
        import parametron_freecad.execution.manifest_validation as mv

        result = mv.validate_export_manifest_v1(self._v2_mutation_bearing_payload())
        codes = [d.code for d in result.diagnostics]
        self.assertIn(mv.DIAGNOSTIC_INVALID_SCHEMA_VERSION, codes)

    def test_v1_validator_flags_assembly_mutations_as_unknown_field(self):
        import parametron_freecad.execution.manifest_validation as mv

        result = mv.validate_export_manifest_v1(self._v2_mutation_bearing_payload())
        unknown_paths = [
            d.path for d in result.diagnostics if d.code == mv.DIAGNOSTIC_UNKNOWN_FIELD
        ]
        self.assertIn("assemblyMutations", unknown_paths)

    def test_v2_validation_api_exists_but_runtime_remains_v1_only(self):
        # Task 3 supersedes the Task 2 absence invariant: V2 validation and
        # generic version dispatch now exist as production APIs, but the
        # runtime execution entrypoint still resolves only the V1 validator.
        # See tests/test_manifest_v2_validation.py for full Task 3 coverage.
        import parametron_freecad.execution.manifest_validation as mv
        from parametron_freecad.runtime import entrypoints

        self.assertTrue(callable(getattr(mv, "validate_export_manifest_v2", None)))
        self.assertTrue(callable(getattr(mv, "validate_export_manifest", None)))

        self.assertTrue(hasattr(entrypoints, "validate_export_manifest_v1"))
        self.assertFalse(hasattr(entrypoints, "validate_export_manifest_v2"))
        self.assertFalse(hasattr(entrypoints, "validate_export_manifest"))

    def test_v1_validator_module_has_no_version_dispatch_helper(self):
        import parametron_freecad.execution.manifest_validation as mv

        for name in dir(mv):
            self.assertNotIn("dispatch", name.lower())

    def test_loader_does_not_expose_mutation_parsing(self):
        import parametron_freecad.execution.manifest_loader as ml

        for name in dir(ml):
            lowered = name.lower()
            self.assertNotIn("mutation", lowered)

    def test_loader_still_loads_v2_payload_as_plain_decoded_data(self):
        # The strict loader is schema-agnostic; it must still just decode
        # JSON without interpreting or rejecting v2 mutation sections.
        import json
        import tempfile
        from pathlib import Path

        import parametron_freecad.execution.manifest_loader as ml

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(
                json.dumps(self._v2_mutation_bearing_payload()), encoding="utf-8"
            )
            result = ml.load_export_manifest_v1(path)
        self.assertIn("assemblyMutations", result.data)

    def test_engine_manifest_compat_module_has_no_mutation_normalization(self):
        import parametron_freecad.execution.engine_manifest_compat as emc

        for name in dir(emc):
            lowered = name.lower()
            self.assertNotIn("mutation", lowered)

    def test_runtime_entrypoints_module_source_has_no_v2_symbols(self):
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

    def test_manifest_contract_module_itself_exposes_no_validation_function(self):
        # Task 2 is metadata-only; the contract module must not gain a
        # validation entrypoint of its own.
        import parametron_freecad.execution.manifest_contract as mc

        for name in dir(mc):
            lowered = name.lower()
            self.assertNotIn("validate", lowered)
            self.assertNotIn("execute", lowered)
            self.assertNotIn("apply_mutation", lowered)
            self.assertNotIn("suppress_object", lowered)
            self.assertNotIn("delete_object", lowered)
            self.assertNotIn("set_visibility", lowered)


class TestNoRuntimeBehaviorExposedOnV2Surface(unittest.TestCase):
    """The V2 metadata surface must not expose execution/runtime helpers."""

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

    def test_no_validate_export_manifest_v2(self):
        self._assert_absent("validate_export_manifest_v2")

    def test_no_parse_mutations(self):
        self._assert_absent("parse_mutations")


if __name__ == "__main__":
    unittest.main()
