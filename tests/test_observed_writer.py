"""Tests for the canonical observed JSON writer under ordinary Python.

These tests exercise the public behavior of
``parametron_freecad.observation.observed_writer`` without requiring FreeCAD,
opening documents, or evaluating verification decisions. The writer only takes
already-observed data, applies the observed output contract shape and
deterministic ordering, and serializes canonical JSON.
"""

from __future__ import annotations

import copy
import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


MODULE_NAME = "parametron_freecad.observation.observed_writer"


def _import_module():
    return importlib.import_module(MODULE_NAME)


# ---------------------------------------------------------------------------
# Item builders (contract-aligned, supplied in scrambled field order)
# ---------------------------------------------------------------------------


def _parameter_item():
    # Deliberately supplied out of contract field order.
    return {
        "valueKind": "number",
        "value": 10.0,
        "groupId": "Spreadsheet",
        "name": "Length",
        "id": "p.length",
    }


def _metadata_item():
    return {
        "valueKind": "string",
        "value": "Jane",
        "ownerId": "Doc",
        "key": "Author",
        "id": "m.author",
    }


def _reference_item():
    return {"name": "Sketch001", "kind": "constraint"}


def _component_item():
    return {
        "parentId": "root",
        "name": "Widget",
        "kind": "part",
        "id": "c.widget",
    }


def _full_observation_data():
    """Return a fully populated observation payload in scrambled order."""
    return {
        "references": [_reference_item()],
        "components": [_component_item()],
        "metadata": [_metadata_item()],
        "parameters": [_parameter_item()],
    }


# ---------------------------------------------------------------------------
# Section 1 — Import safety
# ---------------------------------------------------------------------------


class TestImportSafety(unittest.TestCase):
    def test_import_does_not_require_freecad_or_touch_filesystem(self):
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad"}
        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            if name in guarded_names:
                raise AssertionError(f"{name} must not be imported")
            return real_import(name, *args, **kwargs)

        def guarded_open(*args, **kwargs):
            raise AssertionError("importing the writer must not open files")

        previous = sys.modules.pop(MODULE_NAME, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            with mock.patch("builtins.open", side_effect=guarded_open):
                module = _import_module()

        self.assertIsInstance(module, types.ModuleType)
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_no_freecad_in_sys_modules_after_import(self):
        _import_module()
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_module_exposes_expected_public_surface(self):
        module = _import_module()
        for name in (
            "ObservedPayloadError",
            "ObservedWriteError",
            "build_observed_payload",
            "observed_json_path",
            "write_observed_json",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(module, name))

        self.assertEqual(
            sorted(module.__all__),
            [
                "ObservedPayloadError",
                "ObservedWriteError",
                "build_observed_payload",
                "observed_json_path",
                "write_observed_json",
            ],
        )

    def test_error_types_have_deterministic_hierarchy(self):
        module = _import_module()
        self.assertTrue(issubclass(module.ObservedPayloadError, ValueError))
        self.assertTrue(issubclass(module.ObservedWriteError, OSError))


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _WriterTestCase(unittest.TestCase):
    def setUp(self):
        self.mod = _import_module()

    def build(self, **kwargs):
        defaults = {
            "working_copy_path": "/work/model.FCStd",
            "working_copy_sha256": "a" * 64,
            "observation_data": _full_observation_data(),
        }
        defaults.update(kwargs)
        return self.mod.build_observed_payload(**defaults)


# ---------------------------------------------------------------------------
# Section 2 — Payload builder shape
# ---------------------------------------------------------------------------


class TestPayloadBuilderShape(_WriterTestCase):
    def test_top_level_shape(self):
        payload = self.build()
        self.assertEqual(
            set(payload.keys()),
            {"schemaVersion", "workingCopy", "observation"},
        )

    def test_schema_version_is_fixed(self):
        payload = self.build()
        self.assertEqual(payload["schemaVersion"], "1.0")

    def test_working_copy_contains_exactly_path_and_sha256(self):
        payload = self.build(
            working_copy_path="/work/model.FCStd",
            working_copy_sha256="b" * 64,
        )
        self.assertEqual(
            set(payload["workingCopy"].keys()),
            {"path", "sha256"},
        )
        self.assertEqual(payload["workingCopy"]["path"], "/work/model.FCStd")
        self.assertEqual(payload["workingCopy"]["sha256"], "b" * 64)

    def test_observation_only_contains_supported_categories(self):
        payload = self.build()
        self.assertTrue(
            set(payload["observation"].keys()).issubset(
                {"parameters", "metadata", "references", "components"}
            )
        )

    def test_path_like_working_copy_path_is_coerced_to_string(self):
        payload = self.build(working_copy_path=Path("/work/model.FCStd"))
        self.assertIsInstance(payload["workingCopy"]["path"], str)
        self.assertEqual(payload["workingCopy"]["path"], "/work/model.FCStd")

    def test_empty_observation_yields_empty_observation_mapping(self):
        payload = self.build(observation_data={})
        self.assertEqual(payload["observation"], {})


# ---------------------------------------------------------------------------
# Section 3 — Observation ordering integration
# ---------------------------------------------------------------------------


class TestObservationOrderingIntegration(_WriterTestCase):
    def test_category_order_follows_contract(self):
        payload = self.build(observation_data=_full_observation_data())
        self.assertEqual(
            list(payload["observation"].keys()),
            ["parameters", "metadata", "references", "components"],
        )

    def test_item_field_order_follows_contract(self):
        payload = self.build(observation_data=_full_observation_data())
        self.assertEqual(
            tuple(payload["observation"]["parameters"][0].keys()),
            ("id", "name", "groupId", "value", "valueKind"),
        )
        self.assertEqual(
            tuple(payload["observation"]["metadata"][0].keys()),
            ("id", "key", "ownerId", "value", "valueKind"),
        )
        self.assertEqual(
            tuple(payload["observation"]["references"][0].keys()),
            ("kind", "name"),
        )
        self.assertEqual(
            tuple(payload["observation"]["components"][0].keys()),
            ("id", "kind", "name", "parentId"),
        )

    def test_item_order_within_category_is_preserved(self):
        first = dict(_parameter_item(), id="p.a")
        second = dict(_parameter_item(), id="p.b")
        third = dict(_parameter_item(), id="p.c")
        payload = self.build(observation_data={"parameters": [first, second, third]})
        self.assertEqual(
            [item["id"] for item in payload["observation"]["parameters"]],
            ["p.a", "p.b", "p.c"],
        )

    def test_unknown_top_level_categories_are_ignored(self):
        payload = self.build(
            observation_data={
                "parameters": [_parameter_item()],
                "unexpected": [{"whatever": 1}],
                "constraints": "ignored",
            }
        )
        self.assertEqual(list(payload["observation"].keys()), ["parameters"])

    def test_unknown_item_fields_are_ignored(self):
        item = dict(_parameter_item(), extra="ignored", another=123)
        payload = self.build(observation_data={"parameters": [item]})
        self.assertEqual(
            tuple(payload["observation"]["parameters"][0].keys()),
            ("id", "name", "groupId", "value", "valueKind"),
        )

    def test_missing_required_item_field_fails_through_writer_boundary(self):
        item = _parameter_item()
        del item["value"]
        with self.assertRaises(self.mod.ObservedPayloadError):
            self.build(observation_data={"parameters": [item]})

    def test_non_mapping_observation_data_fails_through_writer_boundary(self):
        for value in (None, 42, "string", [], object()):
            with self.subTest(value=value):
                with self.assertRaises(self.mod.ObservedPayloadError):
                    self.build(observation_data=value)

    def test_writer_routes_through_order_observation_payload(self):
        observation_data = _full_observation_data()
        real_order = self.mod.order_observation_payload
        with mock.patch.object(
            self.mod,
            "order_observation_payload",
            wraps=real_order,
        ) as spy:
            self.build(observation_data=observation_data)
        spy.assert_called_once_with(observation_data)


# ---------------------------------------------------------------------------
# Section 4 — Canonical file writing
# ---------------------------------------------------------------------------


class TestCanonicalFileWriting(_WriterTestCase):
    def _write(self, path, **kwargs):
        defaults = {
            "working_copy_path": "/work/model.FCStd",
            "working_copy_sha256": "a" * 64,
            "observation_data": _full_observation_data(),
        }
        defaults.update(kwargs)
        self.mod.write_observed_json(path, **defaults)

    def test_bytes_match_dumps_canonical_of_built_payload(self):
        from parametron_freecad.common.canonical_json import dumps_canonical

        observation_data = _full_observation_data()
        payload = self.build(observation_data=observation_data)

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "parametron.observed.json"
            self._write(path, observation_data=observation_data)
            self.assertEqual(
                path.read_bytes(),
                dumps_canonical(payload).encode("utf-8"),
            )

    def test_output_is_utf8_with_single_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "parametron.observed.json"
            self._write(
                path,
                observation_data={
                    "metadata": [
                        dict(_metadata_item(), value="çağrı 東京"),
                    ]
                },
            )
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            self.assertTrue(text.endswith("\n"))
            self.assertFalse(text.endswith("\n\n"))
            self.assertNotIn("\\u", text)

    def test_repeated_writes_with_equivalent_input_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "parametron.observed.json"

            self._write(path, observation_data=_full_observation_data())
            first = path.read_bytes()

            self._write(path, observation_data=_full_observation_data())
            second = path.read_bytes()

            self.assertEqual(first, second)

    def test_existing_output_is_overwritten_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "parametron.observed.json"
            path.write_text("stale data\nwith extra lines\n", encoding="utf-8")

            self._write(path, observation_data={"parameters": [_parameter_item()]})

            text = path.read_text(encoding="utf-8")
            self.assertNotIn("stale", text)
            self.assertTrue(text.startswith("{"))
            self.assertEqual(text.count("\n"), 1)

    def test_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "parametron.observed.json"
            result = self.mod.write_observed_json(
                path,
                working_copy_path="/work/model.FCStd",
                working_copy_sha256="a" * 64,
                observation_data=_full_observation_data(),
            )
            self.assertIsNone(result)

    def test_observed_json_path_uses_contract_filename(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = self.mod.observed_json_path(tmp_dir)
            self.assertEqual(result, Path(tmp_dir) / "parametron.observed.json")


# ---------------------------------------------------------------------------
# Section 5 — Working-copy metadata validation
# ---------------------------------------------------------------------------


class TestWorkingCopyValidation(_WriterTestCase):
    def test_empty_path_fails_deterministically(self):
        with self.assertRaises(self.mod.ObservedPayloadError):
            self.build(working_copy_path="")

    def test_non_path_like_path_fails_deterministically(self):
        for value in (None, 42, object(), ["/work"]):
            with self.subTest(value=value):
                with self.assertRaises(self.mod.ObservedPayloadError):
                    self.build(working_copy_path=value)

    def test_empty_sha256_fails_deterministically(self):
        with self.assertRaises(self.mod.ObservedPayloadError):
            self.build(working_copy_sha256="")

    def test_non_string_sha256_fails_deterministically(self):
        for value in (None, 42, object(), b"a" * 64):
            with self.subTest(value=value):
                with self.assertRaises(self.mod.ObservedPayloadError):
                    self.build(working_copy_sha256=value)

    def test_valid_metadata_round_trips(self):
        payload = self.build(
            working_copy_path="/abs/path/model.FCStd",
            working_copy_sha256="0" * 64,
        )
        self.assertEqual(payload["workingCopy"]["path"], "/abs/path/model.FCStd")
        self.assertEqual(payload["workingCopy"]["sha256"], "0" * 64)


# ---------------------------------------------------------------------------
# Section 6 — Write failure behavior
# ---------------------------------------------------------------------------


class TestWriteFailureBehavior(_WriterTestCase):
    def test_temporary_file_is_created_in_destination_and_atomically_replaces_target(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "parametron.observed.json"
            target.write_text("old-valid\n", encoding="utf-8")
            real_mkstemp = self.mod.tempfile.mkstemp
            created = []

            def recording_mkstemp(**kwargs):
                descriptor, name = real_mkstemp(**kwargs)
                created.append((kwargs, Path(name)))
                return descriptor, name

            with mock.patch.object(self.mod.tempfile, "mkstemp", side_effect=recording_mkstemp):
                self.mod.write_observed_json(
                    target,
                    working_copy_path="/work/model.FCStd",
                    working_copy_sha256="a" * 64,
                    observation_data={"parameters": [_parameter_item()]},
                )
            self.assertEqual(created[0][0]["dir"], target.parent)
            self.assertFalse(created[0][1].exists())
            self.assertNotEqual(target.read_text(encoding="utf-8"), "old-valid\n")

    def test_serialization_failure_preserves_existing_target_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "parametron.observed.json"
            original = b'{"valid":"old"}\n'
            target.write_bytes(original)
            temporary_paths = []
            real_mkstemp = self.mod.tempfile.mkstemp

            def recording_mkstemp(**kwargs):
                descriptor, name = real_mkstemp(**kwargs)
                temporary_paths.append(Path(name))
                return descriptor, name

            with mock.patch.object(self.mod.tempfile, "mkstemp", side_effect=recording_mkstemp), mock.patch.object(
                self.mod, "write_canonical_json", side_effect=ValueError("serialize failed")
            ), self.assertRaises(self.mod.ObservedWriteError) as caught:
                self.mod.write_observed_json(
                    target, working_copy_path="/work/model.FCStd",
                    working_copy_sha256="a" * 64,
                    observation_data={"parameters": [_parameter_item()]},
                )
            self.assertIsInstance(caught.exception.__cause__, ValueError)
            self.assertEqual(target.read_bytes(), original)
            self.assertTrue(all(not path.exists() for path in temporary_paths))

    def test_replacement_failure_preserves_target_and_cleans_complete_temporary(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "parametron.observed.json"
            original = b'{"valid":"old"}\n'
            target.write_bytes(original)
            temporary_paths = []
            real_mkstemp = self.mod.tempfile.mkstemp

            def recording_mkstemp(**kwargs):
                descriptor, name = real_mkstemp(**kwargs)
                temporary_paths.append(Path(name))
                return descriptor, name

            real_replace = Path.replace

            def fail_temporary_replace(path, destination):
                if path in temporary_paths:
                    raise OSError("replace failed")
                return real_replace(path, destination)

            with mock.patch.object(self.mod.tempfile, "mkstemp", side_effect=recording_mkstemp), mock.patch.object(
                Path, "replace", autospec=True, side_effect=fail_temporary_replace
            ), self.assertRaises(self.mod.ObservedWriteError) as caught:
                self.mod.write_observed_json(
                    target, working_copy_path="/work/model.FCStd",
                    working_copy_sha256="a" * 64,
                    observation_data={"parameters": [_parameter_item()]},
                )
            self.assertIsInstance(caught.exception.__cause__, OSError)
            self.assertEqual(target.read_bytes(), original)
            self.assertTrue(all(not path.exists() for path in temporary_paths))

    def test_missing_parent_directory_raises_observed_write_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "missing" / "parametron.observed.json"
            with self.assertRaises(self.mod.ObservedWriteError):
                self.mod.write_observed_json(
                    path,
                    working_copy_path="/work/model.FCStd",
                    working_copy_sha256="a" * 64,
                    observation_data=_full_observation_data(),
                )

    def test_output_path_is_directory_raises_observed_write_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            directory = Path(tmp_dir) / "observed_dir"
            directory.mkdir()
            with self.assertRaises(self.mod.ObservedWriteError):
                self.mod.write_observed_json(
                    directory,
                    working_copy_path="/work/model.FCStd",
                    working_copy_sha256="a" * 64,
                    observation_data=_full_observation_data(),
                )

    def test_payload_errors_are_not_wrapped_as_write_errors(self):
        item = _parameter_item()
        del item["value"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "parametron.observed.json"
            with self.assertRaises(self.mod.ObservedPayloadError):
                self.mod.write_observed_json(
                    path,
                    working_copy_path="/work/model.FCStd",
                    working_copy_sha256="a" * 64,
                    observation_data={"parameters": [item]},
                )
            self.assertFalse(path.exists())


# ---------------------------------------------------------------------------
# Section 7 — Input mutation
# ---------------------------------------------------------------------------


class TestInputMutation(_WriterTestCase):
    def test_build_does_not_mutate_observation_or_items(self):
        observation_data = _full_observation_data()
        before = copy.deepcopy(observation_data)
        self.build(observation_data=observation_data)
        self.assertEqual(observation_data, before)

    def test_write_does_not_mutate_observation_or_items(self):
        observation_data = {
            "parameters": [dict(_parameter_item(), extra="ignored")],
            "references": [_reference_item()],
        }
        before = copy.deepcopy(observation_data)
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "parametron.observed.json"
            self.mod.write_observed_json(
                path,
                working_copy_path="/work/model.FCStd",
                working_copy_sha256="a" * 64,
                observation_data=observation_data,
            )
        self.assertEqual(observation_data, before)

    def test_returned_items_are_new_mappings(self):
        item = _parameter_item()
        payload = self.build(observation_data={"parameters": [item]})
        self.assertIsNot(payload["observation"]["parameters"][0], item)


# ---------------------------------------------------------------------------
# Section 8 — Scope boundary regression
# ---------------------------------------------------------------------------


class _ExplodingDocument:
    """Sentinel that fails loudly if treated like a FreeCAD document."""

    @property
    def Objects(self):  # noqa: N802 - mimic FreeCAD attribute name
        raise AssertionError("writer must not traverse document.Objects")

    def getObject(self, *args, **kwargs):  # noqa: N802
        raise AssertionError("writer must not resolve document objects")

    def recompute(self, *args, **kwargs):
        raise AssertionError("writer must not recompute documents")


class TestScopeBoundary(_WriterTestCase):
    def test_writer_accepts_plain_data_without_any_document(self):
        # The writer takes already-observed mapping data, never a document.
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "parametron.observed.json"
            self.mod.write_observed_json(
                path,
                working_copy_path="/work/model.FCStd",
                working_copy_sha256="a" * 64,
                observation_data=_full_observation_data(),
            )
            self.assertTrue(path.exists())

    def test_no_freecad_import_required_during_write(self):
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad"}
        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            if name in guarded_names:
                raise AssertionError(f"{name} must not be imported")
            return real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "parametron.observed.json"
            with mock.patch("builtins.__import__", side_effect=guarded_import):
                self.mod.write_observed_json(
                    path,
                    working_copy_path="/work/model.FCStd",
                    working_copy_sha256="a" * 64,
                    observation_data=_full_observation_data(),
                )
        self.assertNotIn("FreeCAD", sys.modules)

    def test_exploding_document_in_payload_is_never_traversed(self):
        # A document-like sentinel placed in an unknown category must be ignored
        # rather than traversed; supported-category data still writes cleanly.
        observation_data = {
            "parameters": [_parameter_item()],
            "document": _ExplodingDocument(),
        }
        payload = self.build(observation_data=observation_data)
        self.assertEqual(list(payload["observation"].keys()), ["parameters"])

    def test_payload_contains_no_checks_or_comparison_fields(self):
        payload = self.build(observation_data=_full_observation_data())
        self.assertNotIn("checks", payload)
        self.assertNotIn("result", payload)
        self.assertNotIn("verification", payload)
        for item in payload["observation"]["parameters"]:
            self.assertNotIn("expected", item)
            self.assertNotIn("status", item)


if __name__ == "__main__":
    unittest.main()
