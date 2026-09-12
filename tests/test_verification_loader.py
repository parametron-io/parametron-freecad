"""Tests for parametron_freecad.observation.verification_loader strict loading contract."""

from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from collections.abc import Mapping
from pathlib import Path
from unittest import mock


MODULE_NAME = "parametron_freecad.observation.verification_loader"


class TestImportSafety(unittest.TestCase):
    """Loader module must import under ordinary Python without FreeCAD."""

    def test_import_succeeds_without_freecad(self):
        import parametron_freecad.observation.verification_loader  # noqa: F401

    def test_module_is_a_module(self):
        import parametron_freecad.observation.verification_loader as vl

        self.assertIsInstance(vl, types.ModuleType)

    def test_no_freecad_in_sys_modules_after_import(self):
        import parametron_freecad.observation.verification_loader  # noqa: F401

        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_freecad_import_not_attempted(self):
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad"}

        def guarded_import(name, *args, **kwargs):
            if name in guarded_names:
                raise AssertionError(f"{name} must not be imported by the loader")
            return real_import(name, *args, **kwargs)

        real_import = __import__
        previous = sys.modules.pop(MODULE_NAME, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = __import__(MODULE_NAME)

        self.assertIsInstance(module, types.ModuleType)

    def test_public_names_present(self):
        import parametron_freecad.observation.verification_loader as vl

        for name in (
            "LoadedVerificationContract",
            "VerificationLoadError",
            "VerificationFileError",
            "VerificationDecodeError",
            "VerificationDuplicateKeyError",
            "VerificationRootTypeError",
            "load_parametron_verification_v1",
        ):
            self.assertTrue(hasattr(vl, name), f"Missing public name: {name}")


class TestPublicApiExports(unittest.TestCase):
    """__all__ must contain exactly the expected public symbols."""

    def setUp(self):
        import parametron_freecad.observation.verification_loader as vl

        self.vl = vl

    def test_all_contains_exactly_expected_symbols(self):
        expected = {
            "LoadedVerificationContract",
            "VerificationDecodeError",
            "VerificationDuplicateKeyError",
            "VerificationFileError",
            "VerificationLoadError",
            "VerificationRootTypeError",
            "load_parametron_verification_v1",
        }
        self.assertEqual(set(self.vl.__all__), expected)


class TestErrorClassHierarchy(unittest.TestCase):
    """Error subclass relationships must be stable."""

    def setUp(self):
        import parametron_freecad.observation.verification_loader as vl

        self.vl = vl

    def test_verification_load_error_is_value_error(self):
        self.assertTrue(issubclass(self.vl.VerificationLoadError, ValueError))

    def test_verification_file_error_is_verification_load_error(self):
        self.assertTrue(
            issubclass(self.vl.VerificationFileError, self.vl.VerificationLoadError)
        )

    def test_verification_decode_error_is_verification_load_error(self):
        self.assertTrue(
            issubclass(self.vl.VerificationDecodeError, self.vl.VerificationLoadError)
        )

    def test_verification_duplicate_key_error_is_verification_load_error(self):
        self.assertTrue(
            issubclass(
                self.vl.VerificationDuplicateKeyError, self.vl.VerificationLoadError
            )
        )

    def test_verification_root_type_error_is_verification_load_error(self):
        self.assertTrue(
            issubclass(self.vl.VerificationRootTypeError, self.vl.VerificationLoadError)
        )


class _LoaderBase(unittest.TestCase):
    """Common setUp for tests that write temporary verification files."""

    def setUp(self):
        import parametron_freecad.observation.verification_loader as vl

        self.vl = vl
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
        return self.vl.load_parametron_verification_v1(p)


class TestSuccessfulLoad(_LoaderBase):
    """Loader returns LoadedVerificationContract for valid JSON object roots."""

    _REPRESENTATIVE_JSON = json.dumps({
        "schemaVersion": "1.0",
        "observe": ["parameters"],
        "expected": {
            "parameters": [
                {
                    "id": "p.length",
                    "name": "Length",
                    "type": "number",
                    "unit": "mm",
                    "value": 42.5,
                }
            ]
        },
        "checks": {
            "parameters": {
                "enabled": True,
            }
        },
    })

    def test_returns_loaded_verification_contract_instance(self):
        result = self._load("v.json", self._REPRESENTATIVE_JSON)
        self.assertIsInstance(result, self.vl.LoadedVerificationContract)

    def test_path_is_resolved(self):
        p = self._write("v.json", self._REPRESENTATIVE_JSON)
        result = self.vl.load_parametron_verification_v1(p)
        self.assertEqual(result.path, p.resolve())

    def test_path_is_path_object(self):
        result = self._load("v.json", self._REPRESENTATIVE_JSON)
        self.assertIsInstance(result.path, Path)

    def test_data_is_mapping(self):
        result = self._load("v.json", self._REPRESENTATIVE_JSON)
        self.assertIsInstance(result.data, Mapping)

    def test_data_contains_root_object(self):
        result = self._load("v.json", '{"key": "value"}')
        self.assertEqual(result.data, {"key": "value"})

    def test_nested_objects_preserved(self):
        result = self._load("v.json", '{"outer": {"inner": 1}}')
        self.assertEqual(result.data["outer"], {"inner": 1})

    def test_scalar_string_preserved(self):
        result = self._load("v.json", '{"s": "hello"}')
        self.assertEqual(result.data["s"], "hello")
        self.assertIsInstance(result.data["s"], str)

    def test_scalar_integer_preserved(self):
        result = self._load("v.json", '{"n": 42}')
        self.assertEqual(result.data["n"], 42)
        self.assertIsInstance(result.data["n"], int)

    def test_scalar_float_preserved(self):
        result = self._load("v.json", '{"f": 3.14}')
        self.assertAlmostEqual(result.data["f"], 3.14)
        self.assertIsInstance(result.data["f"], float)

    def test_scalar_true_preserved(self):
        result = self._load("v.json", '{"b": true}')
        self.assertIs(result.data["b"], True)

    def test_scalar_false_preserved(self):
        result = self._load("v.json", '{"b": false}')
        self.assertIs(result.data["b"], False)

    def test_null_becomes_none(self):
        result = self._load("v.json", '{"n": null}')
        self.assertIsNone(result.data["n"])

    def test_array_order_preserved(self):
        result = self._load("v.json", '{"items": ["a", 2, 3.5, true, false, null]}')
        self.assertEqual(result.data["items"], ["a", 2, 3.5, True, False, None])

    def test_ordered_array_of_objects_preserved(self):
        result = self._load(
            "v.json",
            '{"ordered": [{"id": "first"}, {"id": "second"}]}',
        )
        self.assertEqual(result.data["ordered"][0]["id"], "first")
        self.assertEqual(result.data["ordered"][1]["id"], "second")

    def test_empty_object_loads(self):
        result = self._load("v.json", "{}")
        self.assertEqual(result.data, {})

    def test_path_accepts_string(self):
        p = self._write("v.json", '{"x": 1}')
        result = self.vl.load_parametron_verification_v1(str(p))
        self.assertIsInstance(result, self.vl.LoadedVerificationContract)

    def test_representative_payload_loads_fully(self):
        result = self._load("v.json", self._REPRESENTATIVE_JSON)
        self.assertEqual(result.data["schemaVersion"], "1.0")
        self.assertEqual(result.data["observe"], ["parameters"])
        params = result.data["expected"]["parameters"]
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0]["id"], "p.length")
        self.assertAlmostEqual(params[0]["value"], 42.5)
        self.assertIs(result.data["checks"]["parameters"]["enabled"], True)


class TestLoadedRecordImmutability(_LoaderBase):
    """LoadedVerificationContract must be immutable."""

    def _loaded(self):
        return self._load("v.json", '{"x": 1}')

    def test_path_attribute_is_read_only(self):
        loaded = self._loaded()
        with self.assertRaises((AttributeError, TypeError)):
            loaded.path = Path("/other/path")

    def test_data_attribute_is_read_only(self):
        loaded = self._loaded()
        with self.assertRaises((AttributeError, TypeError)):
            loaded.data = {"new": "value"}

    def test_new_attribute_cannot_be_set(self):
        loaded = self._loaded()
        with self.assertRaises((AttributeError, TypeError)):
            loaded.extra = "surprise"


class TestFileReadFailures(_LoaderBase):
    """Missing or unreadable paths raise VerificationFileError."""

    def test_missing_file_raises_verification_file_error(self):
        missing = self.tmp / "nonexistent.json"
        with self.assertRaises(self.vl.VerificationFileError):
            self.vl.load_parametron_verification_v1(missing)

    def test_missing_file_error_is_verification_load_error(self):
        missing = self.tmp / "nonexistent.json"
        with self.assertRaises(self.vl.VerificationLoadError):
            self.vl.load_parametron_verification_v1(missing)

    def test_missing_file_error_has_cause(self):
        missing = self.tmp / "nonexistent.json"
        try:
            self.vl.load_parametron_verification_v1(missing)
        except self.vl.VerificationFileError as exc:
            self.assertIsNotNone(exc.__cause__)
        else:
            self.fail("VerificationFileError was not raised")

    def test_missing_file_error_message_contains_path(self):
        missing = self.tmp / "nonexistent.json"
        try:
            self.vl.load_parametron_verification_v1(missing)
        except self.vl.VerificationFileError as exc:
            self.assertIn(str(missing.resolve()), str(exc))
        else:
            self.fail("VerificationFileError was not raised")

    def test_directory_path_raises_verification_file_error(self):
        with self.assertRaises(self.vl.VerificationFileError):
            self.vl.load_parametron_verification_v1(self.tmp)

    def test_directory_path_error_is_verification_load_error(self):
        with self.assertRaises(self.vl.VerificationLoadError):
            self.vl.load_parametron_verification_v1(self.tmp)


class TestMalformedJson(_LoaderBase):
    """Malformed JSON raises VerificationDecodeError."""

    def test_truncated_object_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("v.json", "{")

    def test_truncated_key_value_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("v.json", '{"schemaVersion": "1.0",')

    def test_empty_file_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("v.json", "")

    def test_trailing_comma_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("v.json", '{"key": 1,}')

    def test_single_quote_string_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("v.json", "{'key': 1}")

    def test_plain_text_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("v.json", "not json at all")

    def test_decode_error_is_verification_load_error(self):
        with self.assertRaises(self.vl.VerificationLoadError):
            self._load("v.json", "{")

    def test_decode_error_has_cause(self):
        try:
            self._load("v.json", "{")
        except self.vl.VerificationDecodeError as exc:
            self.assertIsNotNone(exc.__cause__)
        else:
            self.fail("VerificationDecodeError was not raised")

    def test_decode_error_message_contains_line(self):
        try:
            self._load("v.json", '{"key":\n BAD}')
        except self.vl.VerificationDecodeError as exc:
            self.assertIn("line", str(exc))
        else:
            self.fail("VerificationDecodeError was not raised")

    def test_decode_error_message_contains_column(self):
        try:
            self._load("v.json", '{"key":\n BAD}')
        except self.vl.VerificationDecodeError as exc:
            self.assertIn("column", str(exc))
        else:
            self.fail("VerificationDecodeError was not raised")

    def test_decode_error_message_contains_char_position(self):
        try:
            self._load("v.json", '{"key":\n BAD}')
        except self.vl.VerificationDecodeError as exc:
            self.assertIn("char", str(exc))
        else:
            self.fail("VerificationDecodeError was not raised")


class TestNonJsonConstantRejection(_LoaderBase):
    """NaN, Infinity, and -Infinity are rejected as VerificationDecodeError."""

    def test_nan_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("v.json", '{"value": NaN}')

    def test_infinity_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("v.json", '{"value": Infinity}')

    def test_negative_infinity_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("v.json", '{"value": -Infinity}')

    def test_nan_is_verification_load_error(self):
        with self.assertRaises(self.vl.VerificationLoadError):
            self._load("v.json", '{"value": NaN}')

    def test_infinity_is_verification_load_error(self):
        with self.assertRaises(self.vl.VerificationLoadError):
            self._load("v.json", '{"value": Infinity}')

    def test_negative_infinity_is_verification_load_error(self):
        with self.assertRaises(self.vl.VerificationLoadError):
            self._load("v.json", '{"value": -Infinity}')

    def test_nan_decode_error_has_cause(self):
        try:
            self._load("v.json", '{"value": NaN}')
        except self.vl.VerificationDecodeError as exc:
            self.assertIsNotNone(exc.__cause__)
        else:
            self.fail("VerificationDecodeError was not raised for NaN")

    def test_nan_error_message_mentions_constant(self):
        try:
            self._load("v.json", '{"value": NaN}')
        except self.vl.VerificationDecodeError as exc:
            self.assertIn("NaN", str(exc))
        else:
            self.fail("VerificationDecodeError was not raised for NaN")

    def test_infinity_error_message_mentions_constant(self):
        try:
            self._load("v.json", '{"value": Infinity}')
        except self.vl.VerificationDecodeError as exc:
            self.assertIn("Infinity", str(exc))
        else:
            self.fail("VerificationDecodeError was not raised for Infinity")

    def test_negative_infinity_error_message_mentions_constant(self):
        try:
            self._load("v.json", '{"value": -Infinity}')
        except self.vl.VerificationDecodeError as exc:
            self.assertIn("Infinity", str(exc))
        else:
            self.fail("VerificationDecodeError was not raised for -Infinity")

    def test_nan_in_nested_object_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("v.json", '{"outer": {"inner": NaN}}')

    def test_nan_in_array_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("v.json", '{"items": [NaN, 1, 2]}')


class TestDuplicateKeyRejection(_LoaderBase):
    """Duplicate JSON object keys at any nesting level raise VerificationDuplicateKeyError."""

    def test_root_duplicate_raises(self):
        with self.assertRaises(self.vl.VerificationDuplicateKeyError):
            self._load("v.json", '{"schemaVersion": "1.0", "schemaVersion": "1.0"}')

    def test_root_duplicate_is_verification_load_error(self):
        with self.assertRaises(self.vl.VerificationLoadError):
            self._load("v.json", '{"schemaVersion": "1.0", "schemaVersion": "1.0"}')

    def test_root_duplicate_key_name_in_message(self):
        try:
            self._load("v.json", '{"dupkey": 1, "dupkey": 2}')
        except self.vl.VerificationDuplicateKeyError as exc:
            self.assertIn("dupkey", str(exc))
        else:
            self.fail("VerificationDuplicateKeyError was not raised")

    def test_root_duplicate_key_stored_on_error(self):
        try:
            self._load("v.json", '{"dupkey": 1, "dupkey": 2}')
        except self.vl.VerificationDuplicateKeyError as exc:
            self.assertEqual(exc.key, "dupkey")
        else:
            self.fail("VerificationDuplicateKeyError was not raised")

    def test_nested_duplicate_raises(self):
        with self.assertRaises(self.vl.VerificationDuplicateKeyError):
            self._load(
                "v.json",
                '{"expected": {"parameters": [], "parameters": []}}',
            )

    def test_nested_duplicate_is_verification_load_error(self):
        with self.assertRaises(self.vl.VerificationLoadError):
            self._load(
                "v.json",
                '{"expected": {"parameters": [], "parameters": []}}',
            )

    def test_nested_duplicate_key_name_in_message(self):
        try:
            self._load("v.json", '{"outer": {"nestdup": 1, "nestdup": 2}}')
        except self.vl.VerificationDuplicateKeyError as exc:
            self.assertIn("nestdup", str(exc))
        else:
            self.fail("VerificationDuplicateKeyError was not raised")

    def test_duplicate_inside_array_object_raises(self):
        with self.assertRaises(self.vl.VerificationDuplicateKeyError):
            self._load("v.json", '{"expected": [{"id": "a", "id": "b"}]}')

    def test_duplicate_inside_array_object_is_verification_load_error(self):
        with self.assertRaises(self.vl.VerificationLoadError):
            self._load("v.json", '{"expected": [{"id": "a", "id": "b"}]}')

    def test_duplicate_inside_array_object_key_name_in_message(self):
        try:
            self._load("v.json", '{"expected": [{"arrdup": 1, "arrdup": 2}]}')
        except self.vl.VerificationDuplicateKeyError as exc:
            self.assertIn("arrdup", str(exc))
        else:
            self.fail("VerificationDuplicateKeyError was not raised")

    def test_duplicate_not_silently_accepted(self):
        raised = False
        try:
            self._load("v.json", '{"a": 1, "a": 99}')
        except self.vl.VerificationDuplicateKeyError:
            raised = True
        self.assertTrue(raised, "Duplicate key was silently accepted")


class TestNonObjectRootRejection(_LoaderBase):
    """Non-object JSON roots raise VerificationRootTypeError."""

    def _assert_root_type_error(self, json_text: str):
        with self.assertRaises(self.vl.VerificationRootTypeError):
            self._load("v.json", json_text)

    def _assert_root_is_load_error(self, json_text: str):
        with self.assertRaises(self.vl.VerificationLoadError):
            self._load("v.json", json_text)

    def test_array_root_raises(self):
        self._assert_root_type_error("[]")

    def test_array_root_is_verification_load_error(self):
        self._assert_root_is_load_error("[]")

    def test_string_root_raises(self):
        self._assert_root_type_error('"string"')

    def test_string_root_is_verification_load_error(self):
        self._assert_root_is_load_error('"string"')

    def test_number_root_raises(self):
        self._assert_root_type_error("42")

    def test_number_root_is_verification_load_error(self):
        self._assert_root_is_load_error("42")

    def test_boolean_root_raises(self):
        self._assert_root_type_error("true")

    def test_boolean_root_is_verification_load_error(self):
        self._assert_root_is_load_error("true")

    def test_null_root_raises(self):
        self._assert_root_type_error("null")

    def test_null_root_is_verification_load_error(self):
        self._assert_root_is_load_error("null")


class TestNoSchemaValidationCreep(_LoaderBase):
    """Loader must not perform schema validation — that belongs to a later task."""

    def test_empty_object_loads(self):
        result = self._load("v.json", "{}")
        self.assertIsInstance(result, self.vl.LoadedVerificationContract)

    def test_schema_version_mismatch_still_loads(self):
        result = self._load("v.json", '{"schemaVersion": "2.0"}')
        self.assertIsInstance(result, self.vl.LoadedVerificationContract)

    def test_unknown_top_level_field_still_loads(self):
        result = self._load("v.json", '{"unknown": "field"}')
        self.assertIsInstance(result, self.vl.LoadedVerificationContract)

    def test_unsupported_observe_category_still_loads(self):
        result = self._load("v.json", '{"observe": ["unsupported-category"]}')
        self.assertIsInstance(result, self.vl.LoadedVerificationContract)

    def test_missing_required_fields_still_loads(self):
        result = self._load("v.json", '{"observe": ["parameters"]}')
        self.assertIsInstance(result, self.vl.LoadedVerificationContract)

    def test_extra_unknown_nested_fields_still_loads(self):
        result = self._load(
            "v.json",
            json.dumps({"expected": {"unknownCategory": []}}),
        )
        self.assertIsInstance(result, self.vl.LoadedVerificationContract)


class TestPreservationBehavior(_LoaderBase):
    """Loader preserves list order and all JSON scalar types faithfully."""

    _MIXED_PAYLOAD = json.dumps({
        "values": ["a", 2, 3.5, True, False, None],
        "ordered": [{"id": "first"}, {"id": "second"}],
    })

    def test_mixed_list_values_preserved_in_order(self):
        result = self._load("v.json", self._MIXED_PAYLOAD)
        self.assertEqual(result.data["values"], ["a", 2, 3.5, True, False, None])

    def test_null_in_list_becomes_none(self):
        result = self._load("v.json", self._MIXED_PAYLOAD)
        self.assertIsNone(result.data["values"][5])

    def test_booleans_in_list_remain_booleans(self):
        result = self._load("v.json", self._MIXED_PAYLOAD)
        self.assertIs(result.data["values"][3], True)
        self.assertIs(result.data["values"][4], False)

    def test_float_in_list_remains_float(self):
        result = self._load("v.json", self._MIXED_PAYLOAD)
        self.assertIsInstance(result.data["values"][2], float)
        self.assertAlmostEqual(result.data["values"][2], 3.5)

    def test_integer_in_list_remains_integer(self):
        result = self._load("v.json", self._MIXED_PAYLOAD)
        self.assertIsInstance(result.data["values"][1], int)
        self.assertEqual(result.data["values"][1], 2)

    def test_object_array_order_preserved(self):
        result = self._load("v.json", self._MIXED_PAYLOAD)
        ordered = result.data["ordered"]
        self.assertEqual(ordered[0]["id"], "first")
        self.assertEqual(ordered[1]["id"], "second")

    def test_string_in_list_remains_str(self):
        result = self._load("v.json", self._MIXED_PAYLOAD)
        self.assertIsInstance(result.data["values"][0], str)
        self.assertEqual(result.data["values"][0], "a")


if __name__ == "__main__":
    unittest.main()
