"""Tests for parametron_freecad.execution.manifest_validation diagnostics."""

from __future__ import annotations

import sys
import types
import unittest

import parametron_freecad.execution.manifest_validation as mv

MINIMAL_VALID = {
    "schemaVersion": "1.0",
    "sourceDocument": "model.FCStd",
    "parameterAssignments": [],
    "outputs": [],
}


def _validate(data):
    return mv.validate_export_manifest_v1(data)


PUBLIC_DIAGNOSTIC_CODE_CONSTANTS = (
    "DIAGNOSTIC_MISSING_REQUIRED_FIELD",
    "DIAGNOSTIC_UNKNOWN_FIELD",
    "DIAGNOSTIC_INVALID_SCHEMA_VERSION",
    "DIAGNOSTIC_INVALID_FIELD_TYPE",
    "DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENTS_TYPE",
    "DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_TYPE",
    "DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD",
    "DIAGNOSTIC_UNKNOWN_PARAMETER_ASSIGNMENT_FIELD",
    "DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE",
    "DIAGNOSTIC_INVALID_OUTPUTS_TYPE",
    "DIAGNOSTIC_INVALID_OUTPUT_TYPE",
    "DIAGNOSTIC_MISSING_OUTPUT_FIELD",
    "DIAGNOSTIC_UNKNOWN_OUTPUT_FIELD",
    "DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE",
    "DIAGNOSTIC_UNSUPPORTED_OUTPUT_FORMAT",
)


class TestImportSafety(unittest.TestCase):
    """Validation module must import under ordinary Python without FreeCAD."""

    def test_import_succeeds_without_freecad(self):
        import parametron_freecad.execution.manifest_validation  # noqa: F401

    def test_module_is_a_module(self):
        import parametron_freecad.execution.manifest_validation as m

        self.assertIsInstance(m, types.ModuleType)

    def test_no_freecad_in_sys_modules_after_import(self):
        import parametron_freecad.execution.manifest_validation  # noqa: F401

        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_public_api_names_present(self):
        for name in (
            "validate_export_manifest_v1",
            "ManifestDiagnostic",
            "ManifestValidationResult",
        ):
            self.assertTrue(hasattr(mv, name), f"Missing public name: {name}")

    def test_diagnostic_code_constants_present(self):
        for name in PUBLIC_DIAGNOSTIC_CODE_CONSTANTS:
            self.assertTrue(hasattr(mv, name), f"Missing constant: {name}")

    def test_public_diagnostic_code_set_snapshot(self):
        self.assertEqual(
            {getattr(mv, name) for name in PUBLIC_DIAGNOSTIC_CODE_CONSTANTS},
            {
                "invalid_field_type",
                "invalid_output_field_type",
                "invalid_output_type",
                "invalid_outputs_type",
                "invalid_parameter_assignment_field_type",
                "invalid_parameter_assignment_type",
                "invalid_parameter_assignments_type",
                "invalid_schema_version",
                "missing_output_field",
                "missing_parameter_assignment_field",
                "missing_required_field",
                "unknown_field",
                "unknown_output_field",
                "unknown_parameter_assignment_field",
                "unsupported_output_format",
            },
        )


class TestValidMinimalManifest(unittest.TestCase):
    """A minimal valid manifest must pass validation with no diagnostics."""

    def test_result_is_valid(self):
        self.assertTrue(_validate(MINIMAL_VALID).is_valid)

    def test_diagnostics_are_empty_tuple(self):
        self.assertEqual(_validate(MINIMAL_VALID).diagnostics, ())

    def test_diagnostics_are_tuple(self):
        self.assertIsInstance(_validate(MINIMAL_VALID).diagnostics, tuple)

    def test_result_type_is_manifest_validation_result(self):
        self.assertIsInstance(_validate(MINIMAL_VALID), mv.ManifestValidationResult)

    def test_no_exception_raised(self):
        _validate(MINIMAL_VALID)


class TestValidManifestWithAssignmentsAndOutputs(unittest.TestCase):
    """Valid manifests with assignments and outputs produce no diagnostics."""

    def _full(self):
        return {
            "schemaVersion": "1.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [
                {"target": "Part.Width", "value": "100mm", "valueKind": "str"},
                {"target": "Part.Height", "value": 42, "valueKind": "int"},
                {"target": "Part.Scale", "value": 1.5, "valueKind": "float"},
                {"target": "Part.Visible", "value": True, "valueKind": "bool"},
                {"target": "Part.Override", "value": None, "valueKind": "null"},
            ],
            "outputs": [
                {"id": "s", "format": "step", "path": "out/model.step"},
                {"id": "c", "format": "csv", "path": "out/params.csv"},
                {"id": "p", "format": "pdf", "path": "out/report.pdf"},
            ],
        }

    def test_full_manifest_is_valid(self):
        self.assertTrue(_validate(self._full()).is_valid)

    def test_full_manifest_no_diagnostics(self):
        self.assertEqual(_validate(self._full()).diagnostics, ())

    def _assignments(self, items):
        return {**MINIMAL_VALID, "parameterAssignments": items}

    def _outputs(self, items):
        return {**MINIMAL_VALID, "outputs": items}

    def test_string_value_accepted(self):
        data = self._assignments([{"target": "p", "value": "hello", "valueKind": "str"}])
        self.assertTrue(_validate(data).is_valid)

    def test_int_value_accepted(self):
        data = self._assignments([{"target": "p", "value": 42, "valueKind": "int"}])
        self.assertTrue(_validate(data).is_valid)

    def test_float_value_accepted(self):
        data = self._assignments([{"target": "p", "value": 3.14, "valueKind": "float"}])
        self.assertTrue(_validate(data).is_valid)

    def test_bool_true_value_accepted(self):
        data = self._assignments([{"target": "p", "value": True, "valueKind": "bool"}])
        self.assertTrue(_validate(data).is_valid)

    def test_bool_false_value_accepted(self):
        data = self._assignments([{"target": "p", "value": False, "valueKind": "bool"}])
        self.assertTrue(_validate(data).is_valid)

    def test_null_value_accepted(self):
        data = self._assignments([{"target": "p", "value": None, "valueKind": "null"}])
        self.assertTrue(_validate(data).is_valid)

    def test_csv_format_accepted(self):
        data = self._outputs([{"id": "o", "format": "csv", "path": "out.csv"}])
        self.assertTrue(_validate(data).is_valid)

    def test_pdf_format_accepted(self):
        data = self._outputs([{"id": "o", "format": "pdf", "path": "out.pdf"}])
        self.assertTrue(_validate(data).is_valid)

    def test_step_format_accepted(self):
        data = self._outputs([{"id": "o", "format": "step", "path": "out.step"}])
        self.assertTrue(_validate(data).is_valid)


class TestRootValidation(unittest.TestCase):
    """Root-level structural validation."""

    def test_list_root_is_invalid(self):
        self.assertFalse(_validate([]).is_valid)

    def test_list_root_single_diagnostic(self):
        self.assertEqual(len(_validate([]).diagnostics), 1)

    def test_list_root_diagnostic_code(self):
        self.assertEqual(_validate([]).diagnostics[0].code, mv.DIAGNOSTIC_INVALID_FIELD_TYPE)

    def test_list_root_diagnostic_path_is_root_sentinel(self):
        self.assertEqual(_validate([]).diagnostics[0].path, mv.ROOT_PATH)

    def test_string_root_is_invalid(self):
        self.assertFalse(_validate("not a dict").is_valid)

    def test_integer_root_is_invalid(self):
        self.assertFalse(_validate(42).is_valid)

    def test_none_root_is_invalid(self):
        self.assertFalse(_validate(None).is_valid)

    def test_non_mapping_root_stops_further_validation(self):
        self.assertEqual(len(_validate([]).diagnostics), 1)

    def test_empty_dict_has_four_missing_field_diagnostics(self):
        missing = [
            d for d in _validate({}).diagnostics
            if d.code == mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD
        ]
        self.assertEqual(len(missing), 4)

    def test_missing_fields_follow_contract_order(self):
        missing = [
            d for d in _validate({}).diagnostics
            if d.code == mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD
        ]
        self.assertEqual(
            [d.path for d in missing],
            ["schemaVersion", "sourceDocument", "parameterAssignments", "outputs"],
        )

    def test_unknown_fields_are_sorted_lexically(self):
        data = {
            **MINIMAL_VALID,
            "zzz": 1,
            "aaa": 2,
            "mmm": 3,
        }
        unknown = [
            d for d in _validate(data).diagnostics
            if d.code == mv.DIAGNOSTIC_UNKNOWN_FIELD
        ]
        self.assertEqual([d.path for d in unknown], ["aaa", "mmm", "zzz"])

    def test_unknown_field_diagnostic_path_is_field_name(self):
        data = {**MINIMAL_VALID, "extra": True}
        unknown = [
            d for d in _validate(data).diagnostics
            if d.code == mv.DIAGNOSTIC_UNKNOWN_FIELD
        ]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0].path, "extra")

    def test_missing_required_fields_appear_before_unknown_fields(self):
        data = {"extra": 1}  # missing all four required, one unknown
        codes = [d.code for d in _validate(data).diagnostics]
        last_missing = max(
            i for i, c in enumerate(codes)
            if c == mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD
        )
        first_unknown = min(
            i for i, c in enumerate(codes)
            if c == mv.DIAGNOSTIC_UNKNOWN_FIELD
        )
        self.assertLess(last_missing, first_unknown)

    def test_missing_single_required_field_produces_one_missing_diagnostic(self):
        data = {
            "sourceDocument": "m.FCStd",
            "parameterAssignments": [],
            "outputs": [],
        }
        missing = [
            d for d in _validate(data).diagnostics
            if d.code == mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD
        ]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].path, "schemaVersion")


class TestSchemaVersionValidation(unittest.TestCase):
    """schemaVersion field validation."""

    def _with_version(self, version):
        return {**MINIMAL_VALID, "schemaVersion": version}

    def test_exact_version_1_0_is_accepted(self):
        self.assertTrue(_validate(self._with_version("1.0")).is_valid)

    def test_missing_schema_version_produces_missing_field_diagnostic(self):
        data = {
            "sourceDocument": "m.FCStd",
            "parameterAssignments": [],
            "outputs": [],
        }
        codes = [d.code for d in _validate(data).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD, codes)

    def test_float_schema_version_produces_invalid_type(self):
        codes = [d.code for d in _validate(self._with_version(1.0)).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_INVALID_FIELD_TYPE, codes)

    def test_integer_schema_version_produces_invalid_type(self):
        codes = [d.code for d in _validate(self._with_version(1)).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_INVALID_FIELD_TYPE, codes)

    def test_float_schema_version_not_accepted(self):
        self.assertFalse(_validate(self._with_version(1.0)).is_valid)

    def test_unsupported_version_string_produces_invalid_schema_version(self):
        codes = [d.code for d in _validate(self._with_version("1.1")).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_INVALID_SCHEMA_VERSION, codes)

    def test_whitespace_padded_version_not_normalized(self):
        codes = [d.code for d in _validate(self._with_version(" 1.0 ")).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_INVALID_SCHEMA_VERSION, codes)

    def test_empty_string_version_produces_invalid_schema_version(self):
        codes = [d.code for d in _validate(self._with_version("")).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_INVALID_SCHEMA_VERSION, codes)

    def test_invalid_schema_version_diagnostic_path(self):
        diags = [
            d for d in _validate(self._with_version("2.0")).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_SCHEMA_VERSION
        ]
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].path, "schemaVersion")

    def test_non_string_type_diagnostic_path(self):
        diags = [
            d for d in _validate(self._with_version(99)).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_FIELD_TYPE
        ]
        paths = [d.path for d in diags]
        self.assertIn("schemaVersion", paths)


class TestSourceDocumentValidation(unittest.TestCase):
    """sourceDocument field validation."""

    def _with_source(self, value):
        return {**MINIMAL_VALID, "sourceDocument": value}

    def test_valid_string_accepted(self):
        self.assertTrue(_validate(self._with_source("model.FCStd")).is_valid)

    def test_path_like_string_accepted(self):
        self.assertTrue(_validate(self._with_source("/some/path/model.FCStd")).is_valid)

    def test_whitespace_only_string_accepted(self):
        # Implementation rejects only empty string, not whitespace-only
        self.assertTrue(_validate(self._with_source("   ")).is_valid)

    def test_nonexistent_path_accepted_as_string(self):
        self.assertTrue(_validate(self._with_source("/nonexistent/path.FCStd")).is_valid)

    def test_missing_source_document_produces_missing_required_field(self):
        data = {
            "schemaVersion": "1.0",
            "parameterAssignments": [],
            "outputs": [],
        }
        codes = [d.code for d in _validate(data).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD, codes)

    def test_missing_source_document_path(self):
        data = {
            "schemaVersion": "1.0",
            "parameterAssignments": [],
            "outputs": [],
        }
        missing = [
            d for d in _validate(data).diagnostics
            if d.code == mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD
        ]
        self.assertIn("sourceDocument", [d.path for d in missing])

    def test_non_string_source_document_produces_invalid_type(self):
        codes = [d.code for d in _validate(self._with_source(123)).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_INVALID_FIELD_TYPE, codes)

    def test_none_source_document_produces_invalid_type(self):
        codes = [d.code for d in _validate(self._with_source(None)).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_INVALID_FIELD_TYPE, codes)

    def test_empty_string_source_document_produces_invalid_type(self):
        codes = [d.code for d in _validate(self._with_source("")).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_INVALID_FIELD_TYPE, codes)

    def test_invalid_source_document_diagnostic_path(self):
        diags = [
            d for d in _validate(self._with_source(None)).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_FIELD_TYPE
        ]
        paths = [d.path for d in diags]
        self.assertIn("sourceDocument", paths)


class TestParameterAssignmentsContainer(unittest.TestCase):
    """parameterAssignments container-level validation."""

    def _with_assignments(self, value):
        return {**MINIMAL_VALID, "parameterAssignments": value}

    def test_empty_list_is_valid(self):
        self.assertTrue(_validate(self._with_assignments([])).is_valid)

    def test_dict_produces_invalid_type_diagnostic(self):
        codes = [
            d.code for d in _validate(self._with_assignments({"not": "a list"})).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENTS_TYPE, codes)

    def test_invalid_type_diagnostic_path(self):
        diags = [
            d for d in _validate(self._with_assignments("string")).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENTS_TYPE
        ]
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].path, "parameterAssignments")

    def test_missing_produces_missing_required_field(self):
        data = {
            "schemaVersion": "1.0",
            "sourceDocument": "model.FCStd",
            "outputs": [],
        }
        paths = [
            d.path for d in _validate(data).diagnostics
            if d.code == mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD
        ]
        self.assertIn("parameterAssignments", paths)

    def test_non_mapping_item_produces_invalid_assignment_type(self):
        codes = [d.code for d in _validate(self._with_assignments(["not an object"])).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_TYPE, codes)

    def test_non_mapping_first_item_path(self):
        diags = [
            d for d in _validate(self._with_assignments(["not an object"])).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_TYPE
        ]
        self.assertEqual(diags[0].path, "parameterAssignments[0]")

    def test_non_mapping_second_item_path(self):
        valid = {"target": "p", "value": "v", "valueKind": "str"}
        diags = [
            d for d in _validate(self._with_assignments([valid, "invalid"])).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_TYPE
        ]
        self.assertEqual(diags[0].path, "parameterAssignments[1]")


class TestParameterAssignmentItem(unittest.TestCase):
    """Parameter assignment item field validation."""

    def _with_assignments(self, items):
        return {**MINIMAL_VALID, "parameterAssignments": items}

    def _valid_item(self, **overrides):
        base = {"target": "Part.Width", "value": "100mm", "valueKind": "str"}
        base.update(overrides)
        return base

    def test_valid_item_produces_no_diagnostics(self):
        result = _validate(self._with_assignments([self._valid_item()]))
        self.assertTrue(result.is_valid)

    def test_missing_target_produces_diagnostic(self):
        item = {"value": "v", "valueKind": "str"}
        codes = [d.code for d in _validate(self._with_assignments([item])).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD, codes)

    def test_missing_value_produces_diagnostic(self):
        item = {"target": "p", "valueKind": "str"}
        codes = [d.code for d in _validate(self._with_assignments([item])).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD, codes)

    def test_missing_value_kind_produces_diagnostic(self):
        item = {"target": "p", "value": "v"}
        codes = [d.code for d in _validate(self._with_assignments([item])).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD, codes)

    def test_missing_all_fields_produces_three_missing_diagnostics(self):
        missing = [
            d for d in _validate(self._with_assignments([{}])).diagnostics
            if d.code == mv.DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD
        ]
        self.assertEqual(len(missing), 3)

    def test_missing_fields_follow_contract_order_target_value_value_kind(self):
        missing = [
            d for d in _validate(self._with_assignments([{}])).diagnostics
            if d.code == mv.DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD
        ]
        self.assertIn("target", missing[0].message)
        self.assertIn("value", missing[1].message)
        self.assertIn("valueKind", missing[2].message)

    def test_missing_field_diagnostic_path_is_item_path(self):
        for d in _validate(self._with_assignments([{}])).diagnostics:
            if d.code == mv.DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD:
                self.assertEqual(d.path, "parameterAssignments[0]")

    def test_unknown_fields_are_sorted_and_have_field_in_path(self):
        item = {**self._valid_item(), "zzz": 1, "aaa": 2}
        unknown = [
            d for d in _validate(self._with_assignments([item])).diagnostics
            if d.code == mv.DIAGNOSTIC_UNKNOWN_PARAMETER_ASSIGNMENT_FIELD
        ]
        self.assertEqual(len(unknown), 2)
        self.assertEqual(unknown[0].path, "parameterAssignments[0].aaa")
        self.assertEqual(unknown[1].path, "parameterAssignments[0].zzz")

    def test_missing_fields_appear_before_unknown_fields(self):
        item = {"extra": 1}  # all required missing, one unknown
        codes = [d.code for d in _validate(self._with_assignments([item])).diagnostics]
        last_missing = max(
            i for i, c in enumerate(codes)
            if c == mv.DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD
        )
        first_unknown = min(
            i for i, c in enumerate(codes)
            if c == mv.DIAGNOSTIC_UNKNOWN_PARAMETER_ASSIGNMENT_FIELD
        )
        self.assertLess(last_missing, first_unknown)

    def test_non_string_target_produces_invalid_field_type(self):
        codes = [
            d.code for d in _validate(self._with_assignments([self._valid_item(target=42)])).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE, codes)

    def test_non_string_target_diagnostic_path(self):
        diags = [
            d for d in _validate(self._with_assignments([self._valid_item(target=42)])).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE
        ]
        self.assertIn("parameterAssignments[0].target", [d.path for d in diags])

    def test_empty_string_target_produces_invalid_field_type(self):
        codes = [
            d.code for d in _validate(self._with_assignments([self._valid_item(target="")])).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE, codes)

    def test_non_string_value_kind_produces_invalid_field_type(self):
        codes = [
            d.code for d in _validate(self._with_assignments([self._valid_item(valueKind=42)])).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE, codes)

    def test_empty_string_value_kind_produces_invalid_field_type(self):
        codes = [
            d.code for d in _validate(self._with_assignments([self._valid_item(valueKind="")])).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE, codes)

    def test_value_kind_diagnostic_path(self):
        diags = [
            d for d in _validate(self._with_assignments([self._valid_item(valueKind=99)])).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE
        ]
        self.assertIn("parameterAssignments[0].valueKind", [d.path for d in diags])

    def test_dict_value_is_rejected(self):
        codes = [
            d.code for d in _validate(
                self._with_assignments([self._valid_item(value={"nested": "obj"})])
            ).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE, codes)

    def test_list_value_is_rejected(self):
        codes = [
            d.code for d in _validate(
                self._with_assignments([self._valid_item(value=[1, 2, 3])])
            ).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE, codes)

    def test_dict_value_diagnostic_path(self):
        diags = [
            d for d in _validate(
                self._with_assignments([self._valid_item(value={"k": "v"})])
            ).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE
        ]
        self.assertIn("parameterAssignments[0].value", [d.path for d in diags])


class TestOutputsContainer(unittest.TestCase):
    """outputs container-level validation."""

    def _with_outputs(self, value):
        return {**MINIMAL_VALID, "outputs": value}

    def test_empty_list_is_valid(self):
        self.assertTrue(_validate(self._with_outputs([])).is_valid)

    def test_dict_produces_invalid_outputs_type_diagnostic(self):
        codes = [
            d.code for d in _validate(self._with_outputs({"not": "a list"})).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_OUTPUTS_TYPE, codes)

    def test_invalid_type_diagnostic_path(self):
        diags = [
            d for d in _validate(self._with_outputs("string")).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_OUTPUTS_TYPE
        ]
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].path, "outputs")

    def test_missing_produces_missing_required_field(self):
        data = {
            "schemaVersion": "1.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [],
        }
        paths = [
            d.path for d in _validate(data).diagnostics
            if d.code == mv.DIAGNOSTIC_MISSING_REQUIRED_FIELD
        ]
        self.assertIn("outputs", paths)

    def test_non_mapping_item_produces_invalid_output_type(self):
        codes = [d.code for d in _validate(self._with_outputs(["not an object"])).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_INVALID_OUTPUT_TYPE, codes)

    def test_non_mapping_first_item_path(self):
        diags = [
            d for d in _validate(self._with_outputs(["not an object"])).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_OUTPUT_TYPE
        ]
        self.assertEqual(diags[0].path, "outputs[0]")

    def test_non_mapping_second_item_path(self):
        valid = {"id": "o", "format": "step", "path": "out.step"}
        diags = [
            d for d in _validate(self._with_outputs([valid, "invalid"])).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_OUTPUT_TYPE
        ]
        self.assertEqual(diags[0].path, "outputs[1]")


class TestOutputItem(unittest.TestCase):
    """Output item field validation."""

    def _with_outputs(self, items):
        return {**MINIMAL_VALID, "outputs": items}

    def _valid_output(self, **overrides):
        base = {"id": "export1", "format": "step", "path": "out/model.step"}
        base.update(overrides)
        return base

    def test_valid_output_produces_no_diagnostics(self):
        self.assertTrue(_validate(self._with_outputs([self._valid_output()])).is_valid)

    def test_missing_id_produces_diagnostic(self):
        item = {"format": "step", "path": "out.step"}
        codes = [d.code for d in _validate(self._with_outputs([item])).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_MISSING_OUTPUT_FIELD, codes)

    def test_missing_format_produces_diagnostic(self):
        item = {"id": "o", "path": "out.step"}
        codes = [d.code for d in _validate(self._with_outputs([item])).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_MISSING_OUTPUT_FIELD, codes)

    def test_missing_path_produces_diagnostic(self):
        item = {"id": "o", "format": "step"}
        codes = [d.code for d in _validate(self._with_outputs([item])).diagnostics]
        self.assertIn(mv.DIAGNOSTIC_MISSING_OUTPUT_FIELD, codes)

    def test_missing_all_fields_produces_three_missing_diagnostics(self):
        missing = [
            d for d in _validate(self._with_outputs([{}])).diagnostics
            if d.code == mv.DIAGNOSTIC_MISSING_OUTPUT_FIELD
        ]
        self.assertEqual(len(missing), 3)

    def test_missing_fields_follow_contract_order_id_format_path(self):
        missing = [
            d for d in _validate(self._with_outputs([{}])).diagnostics
            if d.code == mv.DIAGNOSTIC_MISSING_OUTPUT_FIELD
        ]
        self.assertIn("id", missing[0].message)
        self.assertIn("format", missing[1].message)
        self.assertIn("path", missing[2].message)

    def test_missing_field_diagnostic_path_is_item_path(self):
        for d in _validate(self._with_outputs([{}])).diagnostics:
            if d.code == mv.DIAGNOSTIC_MISSING_OUTPUT_FIELD:
                self.assertEqual(d.path, "outputs[0]")

    def test_unknown_fields_are_sorted_and_have_field_in_path(self):
        item = {**self._valid_output(), "zzz": 1, "aaa": 2}
        unknown = [
            d for d in _validate(self._with_outputs([item])).diagnostics
            if d.code == mv.DIAGNOSTIC_UNKNOWN_OUTPUT_FIELD
        ]
        self.assertEqual(len(unknown), 2)
        self.assertEqual(unknown[0].path, "outputs[0].aaa")
        self.assertEqual(unknown[1].path, "outputs[0].zzz")

    def test_missing_fields_appear_before_unknown_fields(self):
        item = {"extra": 1}  # all required missing, one unknown
        codes = [d.code for d in _validate(self._with_outputs([item])).diagnostics]
        last_missing = max(
            i for i, c in enumerate(codes)
            if c == mv.DIAGNOSTIC_MISSING_OUTPUT_FIELD
        )
        first_unknown = min(
            i for i, c in enumerate(codes)
            if c == mv.DIAGNOSTIC_UNKNOWN_OUTPUT_FIELD
        )
        self.assertLess(last_missing, first_unknown)

    def test_non_string_id_produces_invalid_field_type(self):
        codes = [
            d.code for d in _validate(self._with_outputs([self._valid_output(id=123)])).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE, codes)

    def test_empty_string_id_produces_invalid_field_type(self):
        codes = [
            d.code for d in _validate(self._with_outputs([self._valid_output(id="")])).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE, codes)

    def test_id_diagnostic_path(self):
        diags = [
            d for d in _validate(self._with_outputs([self._valid_output(id=None)])).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE
        ]
        self.assertIn("outputs[0].id", [d.path for d in diags])

    def test_non_string_format_produces_invalid_field_type(self):
        codes = [
            d.code for d in _validate(self._with_outputs([self._valid_output(format=42)])).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE, codes)

    def test_empty_string_format_produces_unsupported_format(self):
        codes = [
            d.code for d in _validate(self._with_outputs([self._valid_output(format="")])).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_UNSUPPORTED_OUTPUT_FORMAT, codes)

    def test_unsupported_format_stl_produces_diagnostic(self):
        codes = [
            d.code for d in _validate(self._with_outputs([self._valid_output(format="stl")])).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_UNSUPPORTED_OUTPUT_FORMAT, codes)

    def test_wrong_case_step_is_rejected(self):
        self.assertFalse(
            _validate(self._with_outputs([self._valid_output(format="STEP")])).is_valid
        )

    def test_wrong_case_csv_is_rejected(self):
        self.assertFalse(
            _validate(self._with_outputs([self._valid_output(format="CSV")])).is_valid
        )

    def test_wrong_case_pdf_is_rejected(self):
        self.assertFalse(
            _validate(self._with_outputs([self._valid_output(format="PDF")])).is_valid
        )

    def test_unsupported_format_diagnostic_path(self):
        diags = [
            d for d in _validate(self._with_outputs([self._valid_output(format="stl")])).diagnostics
            if d.code == mv.DIAGNOSTIC_UNSUPPORTED_OUTPUT_FORMAT
        ]
        self.assertEqual(diags[0].path, "outputs[0].format")

    def test_non_string_path_field_produces_invalid_field_type(self):
        codes = [
            d.code for d in _validate(self._with_outputs([self._valid_output(path=42)])).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE, codes)

    def test_empty_string_path_field_produces_invalid_field_type(self):
        codes = [
            d.code for d in _validate(self._with_outputs([self._valid_output(path="")])).diagnostics
        ]
        self.assertIn(mv.DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE, codes)

    def test_path_field_diagnostic_path(self):
        diags = [
            d for d in _validate(self._with_outputs([self._valid_output(path=None)])).diagnostics
            if d.code == mv.DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE
        ]
        self.assertIn("outputs[0].path", [d.path for d in diags])


class TestDeterminism(unittest.TestCase):
    """Repeated validation runs must return identical diagnostics."""

    def test_repeated_calls_on_invalid_manifest_equal(self):
        data = {"extra": 1, "schemaVersion": "bad"}
        r1 = _validate(data)
        r2 = _validate(data)
        self.assertEqual(r1.diagnostics, r2.diagnostics)

    def test_repeated_calls_same_length(self):
        data = {"extra": 1}
        self.assertEqual(len(_validate(data).diagnostics), len(_validate(data).diagnostics))

    def test_repeated_calls_same_code_sequence(self):
        data = {
            "schemaVersion": 99,
            "sourceDocument": "",
            "parameterAssignments": "not a list",
            "outputs": [{"format": "stl"}],
        }
        r1 = _validate(data)
        r2 = _validate(data)
        self.assertEqual(
            [d.code for d in r1.diagnostics],
            [d.code for d in r2.diagnostics],
        )

    def test_diagnostic_ordering_stable_across_five_runs(self):
        data = {
            "schemaVersion": "1.0",
            "sourceDocument": "m.FCStd",
            "parameterAssignments": [
                {},
                {"target": "", "value": {}, "valueKind": 0},
            ],
            "outputs": [
                {"id": "", "format": "STEP", "path": None},
            ],
        }
        results = [_validate(data) for _ in range(5)]
        reference = [d.code for d in results[0].diagnostics]
        for r in results[1:]:
            self.assertEqual([d.code for d in r.diagnostics], reference)

    def test_mixed_error_manifest_full_diagnostic_ordering(self):
        data = {
            "schemaVersion": "2.0",
            "sourceDocument": None,
            "parameterAssignments": [
                {
                    "aaa": 1,
                    "target": "",
                    "value": {},
                    "zzz": 2,
                }
            ],
            "outputs": [
                {
                    "aaa": 1,
                    "format": "STEP",
                    "id": "",
                    "zzz": 2,
                }
            ],
            "aaaRoot": 1,
            "zzzRoot": 2,
        }

        self.assertEqual(
            [(d.code, d.path) for d in _validate(data).diagnostics],
            [
                (mv.DIAGNOSTIC_UNKNOWN_FIELD, "aaaRoot"),
                (mv.DIAGNOSTIC_UNKNOWN_FIELD, "zzzRoot"),
                (mv.DIAGNOSTIC_INVALID_SCHEMA_VERSION, "schemaVersion"),
                (mv.DIAGNOSTIC_INVALID_FIELD_TYPE, "sourceDocument"),
                (
                    mv.DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD,
                    "parameterAssignments[0]",
                ),
                (
                    mv.DIAGNOSTIC_UNKNOWN_PARAMETER_ASSIGNMENT_FIELD,
                    "parameterAssignments[0].aaa",
                ),
                (
                    mv.DIAGNOSTIC_UNKNOWN_PARAMETER_ASSIGNMENT_FIELD,
                    "parameterAssignments[0].zzz",
                ),
                (
                    mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE,
                    "parameterAssignments[0].target",
                ),
                (
                    mv.DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE,
                    "parameterAssignments[0].value",
                ),
                (mv.DIAGNOSTIC_MISSING_OUTPUT_FIELD, "outputs[0]"),
                (mv.DIAGNOSTIC_UNKNOWN_OUTPUT_FIELD, "outputs[0].aaa"),
                (mv.DIAGNOSTIC_UNKNOWN_OUTPUT_FIELD, "outputs[0].zzz"),
                (mv.DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE, "outputs[0].id"),
                (mv.DIAGNOSTIC_UNSUPPORTED_OUTPUT_FORMAT, "outputs[0].format"),
            ],
        )

    def test_valid_results_compare_equal(self):
        self.assertEqual(_validate(MINIMAL_VALID), _validate(MINIMAL_VALID))


class TestImmutability(unittest.TestCase):
    """ManifestDiagnostic and ManifestValidationResult must be frozen."""

    def test_manifest_diagnostic_code_cannot_be_reassigned(self):
        d = mv.ManifestDiagnostic(code="x", path="y", message="z")
        with self.assertRaises(AttributeError):
            d.code = "new"

    def test_manifest_diagnostic_path_cannot_be_reassigned(self):
        d = mv.ManifestDiagnostic(code="x", path="y", message="z")
        with self.assertRaises(AttributeError):
            d.path = "new"

    def test_manifest_diagnostic_message_cannot_be_reassigned(self):
        d = mv.ManifestDiagnostic(code="x", path="y", message="z")
        with self.assertRaises(AttributeError):
            d.message = "new"

    def test_manifest_validation_result_diagnostics_cannot_be_reassigned(self):
        r = mv.ManifestValidationResult(diagnostics=())
        with self.assertRaises(AttributeError):
            r.diagnostics = ()

    def test_diagnostics_field_is_tuple(self):
        self.assertIsInstance(_validate(MINIMAL_VALID).diagnostics, tuple)

    def test_non_empty_diagnostics_tuple_is_immutable(self):
        result = _validate({})  # produces 4 missing-field diagnostics
        with self.assertRaises(TypeError):
            result.diagnostics[0] = None  # type: ignore

    def test_manifest_diagnostic_equality_is_value_based(self):
        d1 = mv.ManifestDiagnostic(code="c", path="p", message="m")
        d2 = mv.ManifestDiagnostic(code="c", path="p", message="m")
        self.assertEqual(d1, d2)

    def test_manifest_diagnostic_inequality_on_different_code(self):
        d1 = mv.ManifestDiagnostic(code="a", path="p", message="m")
        d2 = mv.ManifestDiagnostic(code="b", path="p", message="m")
        self.assertNotEqual(d1, d2)


class TestLoaderSeparation(unittest.TestCase):
    """Validation operates on decoded data — no file I/O is required."""

    def test_validate_accepts_plain_dict(self):
        result = mv.validate_export_manifest_v1(MINIMAL_VALID)
        self.assertTrue(result.is_valid)

    def test_validate_accepts_ordered_dict(self):
        from collections import OrderedDict

        data = OrderedDict([
            ("schemaVersion", "1.0"),
            ("sourceDocument", "model.FCStd"),
            ("parameterAssignments", []),
            ("outputs", []),
        ])
        self.assertTrue(mv.validate_export_manifest_v1(data).is_valid)

    def test_validate_does_not_require_filesystem_paths_to_exist(self):
        data = {
            "schemaVersion": "1.0",
            "sourceDocument": "/completely/made/up/path.FCStd",
            "parameterAssignments": [],
            "outputs": [{"id": "o", "format": "step", "path": "/made/up/out.step"}],
        }
        result = mv.validate_export_manifest_v1(data)
        self.assertTrue(result.is_valid)

    def test_validate_returns_manifest_validation_result(self):
        result = mv.validate_export_manifest_v1(MINIMAL_VALID)
        self.assertIsInstance(result, mv.ManifestValidationResult)

    def test_validate_does_not_write_files(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            data = {
                "schemaVersion": "1.0",
                "sourceDocument": "model.FCStd",
                "parameterAssignments": [],
                "outputs": [{"id": "o", "format": "step", "path": "model.step"}],
            }
            mv.validate_export_manifest_v1(data)
            self.assertFalse(os.path.exists(os.path.join(tmp, "model.step")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "result.json")))


if __name__ == "__main__":
    unittest.main()
