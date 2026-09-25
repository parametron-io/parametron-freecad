"""Tests for parametron_freecad.execution.manifest_contract Phase 1 contract."""

import types
import unittest


class TestImportSafety(unittest.TestCase):
    """The module must import without FreeCAD present."""

    def test_import_succeeds_without_freecad(self):
        import parametron_freecad.execution.manifest_contract as mc  # noqa: F401

    def test_module_is_a_module(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.assertIsInstance(mc, types.ModuleType)


class TestStableConstants(unittest.TestCase):
    """Filename and schema-version constants must be exact and stable."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_filename_constant(self):
        self.assertEqual(self.mc.EXPORT_MANIFEST_V1_FILENAME, "prm.export-manifest.json")

    def test_schema_version_constant(self):
        self.assertEqual(self.mc.EXPORT_MANIFEST_SCHEMA_VERSION, "1.0")

    def test_filename_is_string(self):
        self.assertIsInstance(self.mc.EXPORT_MANIFEST_V1_FILENAME, str)

    def test_schema_version_is_string(self):
        self.assertIsInstance(self.mc.EXPORT_MANIFEST_SCHEMA_VERSION, str)


class TestTopLevelFieldContract(unittest.TestCase):
    """TOP_LEVEL_FIELDS must be exactly the Phase 1 set, in order, immutable."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_top_level_fields_exact(self):
        self.assertEqual(
            self.mc.TOP_LEVEL_FIELDS,
            ("schemaVersion", "sourceDocument", "parameterAssignments", "outputs", "assemblyMutations", "partMutations"),
        )

    def test_top_level_fields_count(self):
        self.assertEqual(len(self.mc.TOP_LEVEL_FIELDS), 6)

    def test_top_level_fields_is_tuple(self):
        self.assertIsInstance(self.mc.TOP_LEVEL_FIELDS, tuple)

    def test_top_level_fields_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.TOP_LEVEL_FIELDS[0] = "other"

    def test_top_level_fields_no_extra(self):
        allowed = {"schemaVersion", "sourceDocument", "parameterAssignments", "outputs", "assemblyMutations", "partMutations"}
        self.assertEqual(set(self.mc.TOP_LEVEL_FIELDS), allowed)

    def test_individual_field_constants(self):
        self.assertEqual(self.mc.FIELD_SCHEMA_VERSION, "schemaVersion")
        self.assertEqual(self.mc.FIELD_SOURCE_DOCUMENT, "sourceDocument")
        self.assertEqual(self.mc.FIELD_PARAMETER_ASSIGNMENTS, "parameterAssignments")
        self.assertEqual(self.mc.FIELD_OUTPUTS, "outputs")


class TestParameterAssignmentFieldContract(unittest.TestCase):
    """PARAMETER_ASSIGNMENT_FIELDS must be exactly the Phase 1 set, in order, immutable."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_parameter_assignment_fields_exact(self):
        self.assertEqual(
            self.mc.PARAMETER_ASSIGNMENT_FIELDS,
            ("target", "value", "valueKind"),
        )

    def test_parameter_assignment_fields_count(self):
        self.assertEqual(len(self.mc.PARAMETER_ASSIGNMENT_FIELDS), 3)

    def test_parameter_assignment_fields_is_tuple(self):
        self.assertIsInstance(self.mc.PARAMETER_ASSIGNMENT_FIELDS, tuple)

    def test_parameter_assignment_fields_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.PARAMETER_ASSIGNMENT_FIELDS[0] = "other"

    def test_parameter_assignment_fields_no_extra(self):
        allowed = {"target", "value", "valueKind"}
        self.assertEqual(set(self.mc.PARAMETER_ASSIGNMENT_FIELDS), allowed)

    def test_individual_field_constants(self):
        self.assertEqual(self.mc.PARAMETER_ASSIGNMENT_FIELD_TARGET, "target")
        self.assertEqual(self.mc.PARAMETER_ASSIGNMENT_FIELD_VALUE, "value")
        self.assertEqual(self.mc.PARAMETER_ASSIGNMENT_FIELD_VALUE_KIND, "valueKind")


class TestOutputFieldContract(unittest.TestCase):
    """OUTPUT_FIELDS must be exactly the Phase 1 set, in order, immutable."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_output_fields_exact(self):
        self.assertEqual(
            self.mc.OUTPUT_FIELDS,
            ("id", "format", "path"),
        )

    def test_output_fields_count(self):
        self.assertEqual(len(self.mc.OUTPUT_FIELDS), 3)

    def test_output_fields_is_tuple(self):
        self.assertIsInstance(self.mc.OUTPUT_FIELDS, tuple)

    def test_output_fields_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.OUTPUT_FIELDS[0] = "other"

    def test_output_fields_no_extra(self):
        allowed = {"id", "format", "path"}
        self.assertEqual(set(self.mc.OUTPUT_FIELDS), allowed)

    def test_individual_field_constants(self):
        self.assertEqual(self.mc.OUTPUT_FIELD_ID, "id")
        self.assertEqual(self.mc.OUTPUT_FIELD_FORMAT, "format")
        self.assertEqual(self.mc.OUTPUT_FIELD_PATH, "path")


class TestSupportedOutputFormats(unittest.TestCase):
    """Supported formats must be exactly csv/pdf/step, deterministic, no extras."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_supported_formats_exact(self):
        self.assertEqual(self.mc.SUPPORTED_OUTPUT_FORMATS, ("csv", "pdf", "step"))

    def test_supported_formats_count(self):
        self.assertEqual(len(self.mc.SUPPORTED_OUTPUT_FORMATS), 3)

    def test_supported_formats_is_tuple(self):
        self.assertIsInstance(self.mc.SUPPORTED_OUTPUT_FORMATS, tuple)

    def test_supported_formats_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.SUPPORTED_OUTPUT_FORMATS[0] = "other"

    def test_no_unsupported_formats(self):
        unsupported = {"stl", "obj", "dxf", "json", "fcstd", "svg"}
        self.assertTrue(unsupported.isdisjoint(set(self.mc.SUPPORTED_OUTPUT_FORMATS)))

    def test_individual_format_constants(self):
        self.assertEqual(self.mc.OUTPUT_FORMAT_CSV, "csv")
        self.assertEqual(self.mc.OUTPUT_FORMAT_PDF, "pdf")
        self.assertEqual(self.mc.OUTPUT_FORMAT_STEP, "step")

    def test_helper_function_returns_tuple(self):
        result = self.mc.supported_output_formats()
        self.assertIsInstance(result, tuple)

    def test_helper_function_exact_value(self):
        self.assertEqual(self.mc.supported_output_formats(), ("csv", "pdf", "step"))

    def test_helper_function_deterministic(self):
        self.assertEqual(
            self.mc.supported_output_formats(), self.mc.supported_output_formats()
        )

    def test_helper_function_does_not_expose_mutable_state(self):
        result = self.mc.supported_output_formats()
        with self.assertRaises((TypeError, AttributeError)):
            result[0] = "mutated"


class TestFrozenDataclassBehavior(unittest.TestCase):
    """Frozen dataclasses must reject field mutation after construction."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def test_parameter_assignment_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.PARAMETER_ASSIGNMENT_CONTRACT.target_field = "mutated"

    def test_output_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.OUTPUT_CONTRACT.id_field = "mutated"

    def test_manifest_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.filename = "mutated"

    def test_parameter_assignment_contract_fields_match_tuple(self):
        self.assertEqual(
            self.mc.PARAMETER_ASSIGNMENT_CONTRACT.fields,
            self.mc.PARAMETER_ASSIGNMENT_FIELDS,
        )

    def test_parameter_assignment_contract_individual_fields(self):
        c = self.mc.PARAMETER_ASSIGNMENT_CONTRACT
        self.assertEqual(c.target_field, "target")
        self.assertEqual(c.value_field, "value")
        self.assertEqual(c.value_kind_field, "valueKind")

    def test_output_contract_fields_match_tuple(self):
        self.assertEqual(self.mc.OUTPUT_CONTRACT.fields, self.mc.OUTPUT_FIELDS)

    def test_output_contract_individual_fields(self):
        c = self.mc.OUTPUT_CONTRACT
        self.assertEqual(c.id_field, "id")
        self.assertEqual(c.format_field, "format")
        self.assertEqual(c.path_field, "path")

    def test_output_contract_supported_formats(self):
        self.assertEqual(
            self.mc.OUTPUT_CONTRACT.supported_formats, self.mc.SUPPORTED_OUTPUT_FORMATS
        )

    def test_manifest_contract_top_level_fields(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.top_level_fields,
            self.mc.TOP_LEVEL_FIELDS,
        )

    def test_manifest_contract_filename(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.filename,
            self.mc.EXPORT_MANIFEST_V1_FILENAME,
        )

    def test_manifest_contract_schema_version(self):
        self.assertEqual(
            self.mc.EXPORT_MANIFEST_V1_CONTRACT.schema_version,
            self.mc.EXPORT_MANIFEST_SCHEMA_VERSION,
        )


class TestNoRuntimeBehaviorExposed(unittest.TestCase):
    """The contract module must not expose loading, parsing, or execution surfaces."""

    def setUp(self):
        import parametron_freecad.execution.manifest_contract as mc

        self.mc = mc

    def _assert_absent(self, name: str):
        self.assertFalse(
            hasattr(self.mc, name),
            f"Contract module must not expose '{name}'",
        )

    def test_no_load_manifest(self):
        self._assert_absent("load_manifest")

    def test_no_read_manifest(self):
        self._assert_absent("read_manifest")

    def test_no_parse_manifest_file(self):
        self._assert_absent("parse_manifest_file")

    def test_no_validate_manifest(self):
        self._assert_absent("validate_manifest")

    def test_no_execute_manifest(self):
        self._assert_absent("execute_manifest")

    def test_no_export_step(self):
        self._assert_absent("export_step")

    def test_no_export_csv(self):
        self._assert_absent("export_csv")

    def test_no_export_pdf(self):
        self._assert_absent("export_pdf")

    def test_no_write_result(self):
        self._assert_absent("write_result")


if __name__ == "__main__":
    unittest.main()
