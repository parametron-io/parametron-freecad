"""Tests for deterministic observation ordering under ordinary Python."""

from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from unittest import mock


MODULE_NAME = "parametron_freecad.observation.observation_ordering"


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


# ---------------------------------------------------------------------------
# Section 1 — Import safety
# ---------------------------------------------------------------------------


class TestImportSafety(unittest.TestCase):
    def test_import_succeeds_without_freecad(self):
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad"}

        def guarded_import(name, *args, **kwargs):
            if name in guarded_names:
                raise AssertionError(f"{name} must not be imported")
            return real_import(name, *args, **kwargs)

        real_import = __import__
        previous = sys.modules.pop(MODULE_NAME, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_module()

        self.assertIsInstance(module, types.ModuleType)
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_no_freecad_in_sys_modules_after_import(self):
        _import_module()
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_order_observation_payload_is_callable(self):
        module = _import_module()
        self.assertTrue(callable(module.order_observation_payload))


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _OrderingTestCase(unittest.TestCase):
    def setUp(self):
        self.mod = _import_module()

    def order(self, payload):
        return self.mod.order_observation_payload(payload)


# ---------------------------------------------------------------------------
# Section 2 — Category ordering
# ---------------------------------------------------------------------------


class TestCategoryOrdering(_OrderingTestCase):
    def test_mixed_input_order_emits_contract_order(self):
        payload = {
            "references": [_reference_item()],
            "components": [_component_item()],
            "metadata": [_metadata_item()],
            "parameters": [_parameter_item()],
        }

        result = self.order(payload)

        self.assertEqual(
            list(result.keys()),
            ["parameters", "metadata", "references", "components"],
        )


# ---------------------------------------------------------------------------
# Section 3 — Missing categories are omitted
# ---------------------------------------------------------------------------


class TestMissingCategories(_OrderingTestCase):
    def test_missing_categories_are_omitted(self):
        payload = {"references": [_reference_item()]}

        result = self.order(payload)

        self.assertEqual(list(result.keys()), ["references"])
        self.assertNotIn("parameters", result)
        self.assertNotIn("metadata", result)
        self.assertNotIn("components", result)

    def test_empty_payload_returns_empty_mapping(self):
        result = self.order({})
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# Section 4 — Unknown top-level categories are ignored
# ---------------------------------------------------------------------------


class TestUnknownCategories(_OrderingTestCase):
    def test_unknown_top_level_category_is_ignored(self):
        payload = {
            "parameters": [_parameter_item()],
            "unexpected": [{"whatever": 1}],
            "constraints": "ignored",
        }

        result = self.order(payload)

        self.assertEqual(list(result.keys()), ["parameters"])
        self.assertNotIn("unexpected", result)
        self.assertNotIn("constraints", result)


# ---------------------------------------------------------------------------
# Section 5–8 — Item field ordering, per category
# ---------------------------------------------------------------------------


class TestItemFieldOrdering(_OrderingTestCase):
    def test_parameter_item_field_order(self):
        result = self.order({"parameters": [_parameter_item()]})
        self.assertEqual(
            tuple(result["parameters"][0].keys()),
            ("id", "name", "groupId", "value", "valueKind"),
        )

    def test_metadata_item_field_order(self):
        result = self.order({"metadata": [_metadata_item()]})
        self.assertEqual(
            tuple(result["metadata"][0].keys()),
            ("id", "key", "ownerId", "value", "valueKind"),
        )

    def test_reference_item_field_order(self):
        result = self.order({"references": [_reference_item()]})
        self.assertEqual(
            tuple(result["references"][0].keys()),
            ("kind", "name"),
        )

    def test_component_item_field_order(self):
        result = self.order({"components": [_component_item()]})
        self.assertEqual(
            tuple(result["components"][0].keys()),
            ("id", "kind", "name", "parentId"),
        )

    def test_item_values_preserved_during_reorder(self):
        result = self.order({"parameters": [_parameter_item()]})
        self.assertEqual(
            result["parameters"][0],
            {
                "id": "p.length",
                "name": "Length",
                "groupId": "Spreadsheet",
                "value": 10.0,
                "valueKind": "number",
            },
        )


# ---------------------------------------------------------------------------
# Section 9 — Per-category item order preservation
# ---------------------------------------------------------------------------


class TestItemOrderPreservation(_OrderingTestCase):
    def test_parameter_items_keep_supplied_sequence(self):
        first = dict(_parameter_item(), id="p.a")
        second = dict(_parameter_item(), id="p.b")
        third = dict(_parameter_item(), id="p.c")

        result = self.order({"parameters": [first, second, third]})

        self.assertEqual(
            [item["id"] for item in result["parameters"]],
            ["p.a", "p.b", "p.c"],
        )


# ---------------------------------------------------------------------------
# Section 10 — Category values converted to tuple
# ---------------------------------------------------------------------------


class TestCategoryTupleConversion(_OrderingTestCase):
    def test_list_category_returns_tuple(self):
        result = self.order({"parameters": [_parameter_item()]})
        self.assertIsInstance(result["parameters"], tuple)

    def test_generator_category_returns_tuple(self):
        payload = {"parameters": (item for item in [_parameter_item()])}
        result = self.order(payload)
        self.assertIsInstance(result["parameters"], tuple)
        self.assertEqual(len(result["parameters"]), 1)

    def test_empty_category_returns_empty_tuple(self):
        result = self.order({"parameters": []})
        self.assertEqual(result["parameters"], ())


# ---------------------------------------------------------------------------
# Section 11 — Unknown item fields are ignored
# ---------------------------------------------------------------------------


class TestUnknownItemFields(_OrderingTestCase):
    def test_extra_item_fields_are_not_emitted(self):
        item = dict(_parameter_item(), extra="ignored", another=123)

        result = self.order({"parameters": [item]})

        self.assertEqual(
            tuple(result["parameters"][0].keys()),
            ("id", "name", "groupId", "value", "valueKind"),
        )
        self.assertNotIn("extra", result["parameters"][0])
        self.assertNotIn("another", result["parameters"][0])


# ---------------------------------------------------------------------------
# Section 12 — Input mutation protection
# ---------------------------------------------------------------------------


class TestInputMutationProtection(_OrderingTestCase):
    def test_top_level_and_item_mappings_are_not_mutated(self):
        payload = {
            "references": [_reference_item()],
            "metadata": [_metadata_item()],
            "parameters": [dict(_parameter_item(), extra="ignored")],
            "components": [_component_item()],
        }
        before = copy.deepcopy(payload)

        self.order(payload)

        self.assertEqual(payload, before)

    def test_returned_items_are_new_mappings(self):
        item = _parameter_item()
        payload = {"parameters": [item]}

        result = self.order(payload)

        self.assertIsNot(result["parameters"][0], item)


# ---------------------------------------------------------------------------
# Section 13 — Malformed top-level input
# ---------------------------------------------------------------------------


class TestMalformedTopLevel(_OrderingTestCase):
    def test_non_mapping_top_level_raises_typed_error(self):
        for value in (None, 42, "string", b"bytes", [], (), True, object()):
            with self.subTest(value=value):
                with self.assertRaises(self.mod.ObservationOrderingRequestError):
                    self.order(value)


# ---------------------------------------------------------------------------
# Section 14 — Malformed category values
# ---------------------------------------------------------------------------


class TestMalformedCategoryValues(_OrderingTestCase):
    def test_string_category_value_raises(self):
        with self.assertRaises(self.mod.ObservationOrderingRequestError):
            self.order({"parameters": "not-a-list"})

    def test_bytes_category_value_raises(self):
        with self.assertRaises(self.mod.ObservationOrderingRequestError):
            self.order({"parameters": b"not-a-list"})

    def test_scalar_category_value_raises(self):
        for value in (42, None, True, 3.14, object()):
            with self.subTest(value=value):
                with self.assertRaises(self.mod.ObservationOrderingRequestError):
                    self.order({"parameters": value})

    def test_mapping_category_value_raises(self):
        with self.assertRaises(self.mod.ObservationOrderingRequestError):
            self.order({"parameters": {"id": "p.length"}})


# ---------------------------------------------------------------------------
# Section 15 — Malformed category items
# ---------------------------------------------------------------------------


class TestMalformedCategoryItems(_OrderingTestCase):
    def test_non_mapping_item_raises(self):
        for item in ("string", 42, None, ["list"], object()):
            with self.subTest(item=item):
                with self.assertRaises(self.mod.ObservationOrderingRequestError):
                    self.order({"parameters": [item]})


# ---------------------------------------------------------------------------
# Section 16 — Missing required fields
# ---------------------------------------------------------------------------


class TestMissingRequiredFields(_OrderingTestCase):
    def test_parameter_missing_field_raises(self):
        item = _parameter_item()
        del item["value"]
        with self.assertRaises(self.mod.ObservationOrderingRequestError):
            self.order({"parameters": [item]})

    def test_metadata_missing_field_raises(self):
        item = _metadata_item()
        del item["ownerId"]
        with self.assertRaises(self.mod.ObservationOrderingRequestError):
            self.order({"metadata": [item]})

    def test_reference_missing_field_raises(self):
        item = _reference_item()
        del item["kind"]
        with self.assertRaises(self.mod.ObservationOrderingRequestError):
            self.order({"references": [item]})

    def test_component_missing_field_raises(self):
        item = _component_item()
        del item["parentId"]
        with self.assertRaises(self.mod.ObservationOrderingRequestError):
            self.order({"components": [item]})


# ---------------------------------------------------------------------------
# Section 17 — Deterministic error class
# ---------------------------------------------------------------------------


class TestDeterministicErrorClass(_OrderingTestCase):
    def test_request_error_hierarchy(self):
        self.assertTrue(
            issubclass(
                self.mod.ObservationOrderingRequestError,
                self.mod.ObservationOrderingError,
            )
        )
        self.assertTrue(
            issubclass(self.mod.ObservationOrderingError, ValueError)
        )

    def test_malformed_failures_use_public_typed_error(self):
        malformed_payloads = (
            "not-a-mapping",
            {"parameters": "not-a-list"},
            {"parameters": [object()]},
            {"parameters": [{"id": "p.length"}]},
        )
        for payload in malformed_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(self.mod.ObservationOrderingError):
                    self.order(payload)


if __name__ == "__main__":
    unittest.main()
