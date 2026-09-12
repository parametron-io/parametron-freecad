"""Tests for parametron_freecad.execution.manifest_loader strict loading contract."""

from __future__ import annotations

import json
import tempfile
import types
import unittest
from pathlib import Path


class TestImportSafety(unittest.TestCase):
    """Loader module must import under ordinary Python without FreeCAD."""

    def test_import_succeeds_without_freecad(self):
        import parametron_freecad.execution.manifest_loader  # noqa: F401

    def test_module_is_a_module(self):
        import parametron_freecad.execution.manifest_loader as ml

        self.assertIsInstance(ml, types.ModuleType)

    def test_no_freecad_in_sys_modules_after_import(self):
        import sys

        import parametron_freecad.execution.manifest_loader  # noqa: F401

        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_public_names_present(self):
        import parametron_freecad.execution.manifest_loader as ml

        for name in (
            "LoadedManifest",
            "ManifestLoadError",
            "ManifestFileError",
            "ManifestDecodeError",
            "ManifestDuplicateKeyError",
            "ManifestRootTypeError",
            "load_export_manifest_v1",
        ):
            self.assertTrue(hasattr(ml, name), f"Missing public name: {name}")


class _LoaderBase(unittest.TestCase):
    """Common setUp for tests that write temporary manifests."""

    def setUp(self):
        import parametron_freecad.execution.manifest_loader as ml

        self.ml = ml
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name: str, content: str) -> Path:
        p = self.tmp / name
        p.write_text(content, encoding="utf-8")
        return p

    def _load(self, name: str, content: str) -> object:
        p = self._write(name, content)
        return self.ml.load_export_manifest_v1(p)


class TestSuccessfulLoad(_LoaderBase):
    """Loader returns LoadedManifest for valid JSON object roots."""

    def test_returns_loaded_manifest_instance(self):
        result = self._load("m.json", '{"schemaVersion": "1.0"}')
        self.assertIsInstance(result, self.ml.LoadedManifest)

    def test_path_is_resolved(self):
        p = self._write("m.json", '{"schemaVersion": "1.0"}')
        result = self.ml.load_export_manifest_v1(p)
        self.assertEqual(result.path, p.resolve())

    def test_path_is_path_object(self):
        result = self._load("m.json", '{"schemaVersion": "1.0"}')
        self.assertIsInstance(result.path, Path)

    def test_data_contains_root_object(self):
        result = self._load("m.json", '{"key": "value"}')
        self.assertEqual(result.data, {"key": "value"})

    def test_data_is_mapping(self):
        from collections.abc import Mapping

        result = self._load("m.json", '{"x": 1}')
        self.assertIsInstance(result.data, Mapping)

    def test_string_scalar_preserved(self):
        result = self._load("m.json", '{"s": "hello"}')
        self.assertIsInstance(result.data["s"], str)
        self.assertEqual(result.data["s"], "hello")

    def test_integer_scalar_preserved(self):
        result = self._load("m.json", '{"n": 42}')
        self.assertIsInstance(result.data["n"], int)
        self.assertEqual(result.data["n"], 42)

    def test_float_scalar_preserved(self):
        result = self._load("m.json", '{"f": 3.14}')
        self.assertIsInstance(result.data["f"], float)
        self.assertAlmostEqual(result.data["f"], 3.14)

    def test_boolean_true_preserved(self):
        result = self._load("m.json", '{"b": true}')
        self.assertIs(result.data["b"], True)

    def test_boolean_false_preserved(self):
        result = self._load("m.json", '{"b": false}')
        self.assertIs(result.data["b"], False)

    def test_null_becomes_none(self):
        result = self._load("m.json", '{"n": null}')
        self.assertIsNone(result.data["n"])

    def test_array_order_preserved(self):
        result = self._load("m.json", '{"items": [3, 1, 4, 1, 5, 9]}')
        self.assertEqual(result.data["items"], [3, 1, 4, 1, 5, 9])

    def test_array_string_order_preserved(self):
        result = self._load("m.json", '{"items": ["c", "a", "b"]}')
        self.assertEqual(result.data["items"], ["c", "a", "b"])

    def test_nested_object_loads(self):
        result = self._load("m.json", '{"outer": {"inner": 1}}')
        self.assertEqual(result.data["outer"], {"inner": 1})

    def test_empty_object_loads(self):
        result = self._load("m.json", "{}")
        self.assertEqual(result.data, {})

    def test_path_accepts_string(self):
        p = self._write("m.json", '{"x": 1}')
        result = self.ml.load_export_manifest_v1(str(p))
        self.assertIsInstance(result, self.ml.LoadedManifest)


class TestFileReadFailures(_LoaderBase):
    """Missing or unreadable paths raise ManifestFileError."""

    def test_missing_file_raises_manifest_file_error(self):
        missing = self.tmp / "nonexistent.json"
        with self.assertRaises(self.ml.ManifestFileError):
            self.ml.load_export_manifest_v1(missing)

    def test_missing_file_error_is_manifest_load_error(self):
        missing = self.tmp / "nonexistent.json"
        with self.assertRaises(self.ml.ManifestLoadError):
            self.ml.load_export_manifest_v1(missing)

    def test_directory_path_raises_manifest_file_error(self):
        with self.assertRaises(self.ml.ManifestFileError):
            self.ml.load_export_manifest_v1(self.tmp)

    def test_directory_path_error_is_manifest_load_error(self):
        with self.assertRaises(self.ml.ManifestLoadError):
            self.ml.load_export_manifest_v1(self.tmp)

    def test_missing_file_error_has_cause(self):
        missing = self.tmp / "nonexistent.json"
        try:
            self.ml.load_export_manifest_v1(missing)
        except self.ml.ManifestFileError as exc:
            self.assertIsNotNone(exc.__cause__)
        else:
            self.fail("ManifestFileError was not raised")


class TestMalformedJson(_LoaderBase):
    """Malformed JSON raises ManifestDecodeError."""

    def test_empty_file_raises_manifest_decode_error(self):
        with self.assertRaises(self.ml.ManifestDecodeError):
            self._load("m.json", "")

    def test_truncated_json_raises_manifest_decode_error(self):
        with self.assertRaises(self.ml.ManifestDecodeError):
            self._load("m.json", '{"key": ')

    def test_trailing_comma_raises_manifest_decode_error(self):
        with self.assertRaises(self.ml.ManifestDecodeError):
            self._load("m.json", '{"key": 1,}')

    def test_single_quote_raises_manifest_decode_error(self):
        with self.assertRaises(self.ml.ManifestDecodeError):
            self._load("m.json", "{'key': 1}")

    def test_decode_error_is_manifest_load_error(self):
        with self.assertRaises(self.ml.ManifestLoadError):
            self._load("m.json", "not json at all")

    def test_decode_error_message_contains_line(self):
        try:
            self._load("m.json", '{"key":\n BAD}')
        except self.ml.ManifestDecodeError as exc:
            self.assertIn("line", str(exc))
        else:
            self.fail("ManifestDecodeError was not raised")

    def test_decode_error_message_contains_column(self):
        try:
            self._load("m.json", '{"key":\n BAD}')
        except self.ml.ManifestDecodeError as exc:
            self.assertIn("column", str(exc))
        else:
            self.fail("ManifestDecodeError was not raised")

    def test_decode_error_message_contains_char_position(self):
        try:
            self._load("m.json", '{"key":\n BAD}')
        except self.ml.ManifestDecodeError as exc:
            self.assertIn("char", str(exc))
        else:
            self.fail("ManifestDecodeError was not raised")

    def test_decode_error_has_cause(self):
        try:
            self._load("m.json", "not json")
        except self.ml.ManifestDecodeError as exc:
            self.assertIsNotNone(exc.__cause__)
        else:
            self.fail("ManifestDecodeError was not raised")


class TestNonJsonConstantRejection(_LoaderBase):
    """NaN, Infinity, and -Infinity are rejected as ManifestDecodeError."""

    def test_nan_raises_manifest_decode_error(self):
        with self.assertRaises(self.ml.ManifestDecodeError):
            self._load("m.json", '{"value": NaN}')

    def test_infinity_raises_manifest_decode_error(self):
        with self.assertRaises(self.ml.ManifestDecodeError):
            self._load("m.json", '{"value": Infinity}')

    def test_negative_infinity_raises_manifest_decode_error(self):
        with self.assertRaises(self.ml.ManifestDecodeError):
            self._load("m.json", '{"value": -Infinity}')

    def test_nan_is_manifest_load_error(self):
        with self.assertRaises(self.ml.ManifestLoadError):
            self._load("m.json", '{"value": NaN}')

    def test_infinity_is_manifest_load_error(self):
        with self.assertRaises(self.ml.ManifestLoadError):
            self._load("m.json", '{"value": Infinity}')

    def test_negative_infinity_is_manifest_load_error(self):
        with self.assertRaises(self.ml.ManifestLoadError):
            self._load("m.json", '{"value": -Infinity}')

    def test_nan_decode_error_has_cause(self):
        try:
            self._load("m.json", '{"value": NaN}')
        except self.ml.ManifestDecodeError as exc:
            self.assertIsNotNone(exc.__cause__)
        else:
            self.fail("ManifestDecodeError was not raised for NaN")

    def test_nan_error_message_mentions_constant(self):
        try:
            self._load("m.json", '{"value": NaN}')
        except self.ml.ManifestDecodeError as exc:
            self.assertIn("NaN", str(exc))
        else:
            self.fail("ManifestDecodeError was not raised for NaN")

    def test_infinity_error_message_mentions_constant(self):
        try:
            self._load("m.json", '{"value": Infinity}')
        except self.ml.ManifestDecodeError as exc:
            self.assertIn("Infinity", str(exc))
        else:
            self.fail("ManifestDecodeError was not raised for Infinity")

    def test_negative_infinity_error_message_mentions_constant(self):
        try:
            self._load("m.json", '{"value": -Infinity}')
        except self.ml.ManifestDecodeError as exc:
            self.assertIn("Infinity", str(exc))
        else:
            self.fail("ManifestDecodeError was not raised for -Infinity")

    def test_nan_in_nested_object_raises_manifest_decode_error(self):
        with self.assertRaises(self.ml.ManifestDecodeError):
            self._load("m.json", '{"outer": {"inner": NaN}}')

    def test_nan_in_array_raises_manifest_decode_error(self):
        with self.assertRaises(self.ml.ManifestDecodeError):
            self._load("m.json", '{"items": [NaN, 1, 2]}')


class TestDuplicateKeyRejection(_LoaderBase):
    """Duplicate JSON object keys at any nesting level raise ManifestDuplicateKeyError."""

    def test_duplicate_root_key_raises(self):
        with self.assertRaises(self.ml.ManifestDuplicateKeyError):
            self._load("m.json", '{"a": 1, "a": 2}')

    def test_duplicate_root_key_is_manifest_load_error(self):
        with self.assertRaises(self.ml.ManifestLoadError):
            self._load("m.json", '{"a": 1, "a": 2}')

    def test_duplicate_root_key_name_in_message(self):
        try:
            self._load("m.json", '{"dupkey": 1, "dupkey": 2}')
        except self.ml.ManifestDuplicateKeyError as exc:
            self.assertIn("dupkey", str(exc))
        else:
            self.fail("ManifestDuplicateKeyError was not raised")

    def test_duplicate_key_stored_on_error(self):
        try:
            self._load("m.json", '{"dupkey": 1, "dupkey": 2}')
        except self.ml.ManifestDuplicateKeyError as exc:
            self.assertEqual(exc.key, "dupkey")
        else:
            self.fail("ManifestDuplicateKeyError was not raised")

    def test_duplicate_nested_key_raises(self):
        with self.assertRaises(self.ml.ManifestDuplicateKeyError):
            self._load("m.json", '{"outer": {"inner": 1, "inner": 2}}')

    def test_duplicate_nested_key_is_manifest_load_error(self):
        with self.assertRaises(self.ml.ManifestLoadError):
            self._load("m.json", '{"outer": {"inner": 1, "inner": 2}}')

    def test_duplicate_nested_key_name_in_message(self):
        try:
            self._load("m.json", '{"outer": {"nestdup": 1, "nestdup": 2}}')
        except self.ml.ManifestDuplicateKeyError as exc:
            self.assertIn("nestdup", str(exc))
        else:
            self.fail("ManifestDuplicateKeyError was not raised")

    def test_duplicate_key_inside_array_object_raises(self):
        with self.assertRaises(self.ml.ManifestDuplicateKeyError):
            self._load("m.json", '{"items": [{"k": 1, "k": 2}]}')

    def test_duplicate_key_inside_array_object_is_manifest_load_error(self):
        with self.assertRaises(self.ml.ManifestLoadError):
            self._load("m.json", '{"items": [{"k": 1, "k": 2}]}')

    def test_duplicate_key_inside_array_object_name_in_message(self):
        try:
            self._load("m.json", '{"items": [{"arrdup": 1, "arrdup": 2}]}')
        except self.ml.ManifestDuplicateKeyError as exc:
            self.assertIn("arrdup", str(exc))
        else:
            self.fail("ManifestDuplicateKeyError was not raised")

    def test_first_duplicate_wins_detection_not_silently_kept(self):
        # Ensure the loader did not silently accept the duplicate by returning data.
        raised = False
        try:
            self._load("m.json", '{"a": 1, "a": 99}')
        except self.ml.ManifestDuplicateKeyError:
            raised = True
        self.assertTrue(raised, "Duplicate key was silently accepted")


class TestNonObjectRootRejection(_LoaderBase):
    """Non-object JSON roots raise ManifestRootTypeError."""

    def _assert_root_type_error(self, json_text: str):
        with self.assertRaises(self.ml.ManifestRootTypeError):
            self._load("m.json", json_text)

    def _assert_root_type_error_is_load_error(self, json_text: str):
        with self.assertRaises(self.ml.ManifestLoadError):
            self._load("m.json", json_text)

    def test_array_root_raises(self):
        self._assert_root_type_error('[1, 2, 3]')

    def test_array_root_is_manifest_load_error(self):
        self._assert_root_type_error_is_load_error('[1, 2, 3]')

    def test_string_root_raises(self):
        self._assert_root_type_error('"just a string"')

    def test_string_root_is_manifest_load_error(self):
        self._assert_root_type_error_is_load_error('"just a string"')

    def test_number_root_raises(self):
        self._assert_root_type_error('42')

    def test_number_root_is_manifest_load_error(self):
        self._assert_root_type_error_is_load_error('42')

    def test_boolean_root_raises(self):
        self._assert_root_type_error('true')

    def test_boolean_root_is_manifest_load_error(self):
        self._assert_root_type_error_is_load_error('true')

    def test_null_root_raises(self):
        self._assert_root_type_error('null')

    def test_null_root_is_manifest_load_error(self):
        self._assert_root_type_error_is_load_error('null')


class TestNoOutputSideEffects(_LoaderBase):
    """Loading a manifest must not write any files."""

    def _minimal_manifest_with_outputs(self) -> str:
        return json.dumps({
            "schemaVersion": "1.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [],
            "outputs": [
                {"id": "out1", "format": "step", "path": "output/model.step"},
                {"id": "out2", "format": "csv", "path": "output/params.csv"},
            ],
        })

    def test_no_result_json_created(self):
        p = self._write("manifest.json", self._minimal_manifest_with_outputs())
        self.ml.load_export_manifest_v1(p)
        self.assertFalse((self.tmp / "result.json").exists())

    def test_no_declared_step_output_created(self):
        p = self._write("manifest.json", self._minimal_manifest_with_outputs())
        self.ml.load_export_manifest_v1(p)
        self.assertFalse((self.tmp / "output" / "model.step").exists())

    def test_no_declared_csv_output_created(self):
        p = self._write("manifest.json", self._minimal_manifest_with_outputs())
        self.ml.load_export_manifest_v1(p)
        self.assertFalse((self.tmp / "output" / "params.csv").exists())

    def test_manifest_file_not_mutated(self):
        original = self._minimal_manifest_with_outputs()
        p = self._write("manifest.json", original)
        self.ml.load_export_manifest_v1(p)
        self.assertEqual(p.read_text(encoding="utf-8"), original)

    def test_no_extra_files_created_in_tmp(self):
        p = self._write("manifest.json", '{"x": 1}')
        files_before = set(self.tmp.iterdir())
        self.ml.load_export_manifest_v1(p)
        files_after = set(self.tmp.iterdir())
        self.assertEqual(files_before, files_after)


class TestNoValidationCreep(_LoaderBase):
    """Loader must not perform full manifest validation — that belongs to a later task."""

    def test_missing_schema_version_still_loads(self):
        result = self._load("m.json", '{"sourceDocument": "model.FCStd"}')
        self.assertIsInstance(result, self.ml.LoadedManifest)

    def test_unsupported_schema_version_still_loads(self):
        result = self._load("m.json", '{"schemaVersion": "99.99"}')
        self.assertIsInstance(result, self.ml.LoadedManifest)

    def test_unknown_top_level_fields_still_loads(self):
        result = self._load("m.json", '{"unknownField": true, "anotherUnknown": []}')
        self.assertIsInstance(result, self.ml.LoadedManifest)

    def test_unsupported_output_format_still_loads(self):
        result = self._load(
            "m.json",
            json.dumps({
                "outputs": [{"id": "x", "format": "stl", "path": "out.stl"}]
            }),
        )
        self.assertIsInstance(result, self.ml.LoadedManifest)

    def test_missing_required_output_fields_still_loads(self):
        result = self._load("m.json", '{"outputs": [{"id": "only_id"}]}')
        self.assertIsInstance(result, self.ml.LoadedManifest)

    def test_missing_source_document_still_loads(self):
        result = self._load("m.json", '{"schemaVersion": "1.0", "outputs": []}')
        self.assertIsInstance(result, self.ml.LoadedManifest)

    def test_empty_object_root_still_loads(self):
        result = self._load("m.json", "{}")
        self.assertIsInstance(result, self.ml.LoadedManifest)


class TestErrorClassHierarchy(unittest.TestCase):
    """Error subclass relationships must be stable."""

    def setUp(self):
        import parametron_freecad.execution.manifest_loader as ml

        self.ml = ml

    def test_manifest_load_error_is_value_error(self):
        self.assertTrue(issubclass(self.ml.ManifestLoadError, ValueError))

    def test_manifest_file_error_is_manifest_load_error(self):
        self.assertTrue(issubclass(self.ml.ManifestFileError, self.ml.ManifestLoadError))

    def test_manifest_decode_error_is_manifest_load_error(self):
        self.assertTrue(issubclass(self.ml.ManifestDecodeError, self.ml.ManifestLoadError))

    def test_manifest_duplicate_key_error_is_manifest_load_error(self):
        self.assertTrue(issubclass(self.ml.ManifestDuplicateKeyError, self.ml.ManifestLoadError))

    def test_manifest_root_type_error_is_manifest_load_error(self):
        self.assertTrue(issubclass(self.ml.ManifestRootTypeError, self.ml.ManifestLoadError))


if __name__ == "__main__":
    unittest.main()
