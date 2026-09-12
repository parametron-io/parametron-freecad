"""Tests for requested-scope observation composition under ordinary Python."""

from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from unittest import mock


MODULE_NAME = "parametron_freecad.observation.requested_scope_observation"


def _import_module():
    return importlib.import_module(MODULE_NAME)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeObject:
    """Minimal fake document object exposing arbitrary properties."""

    def __init__(self, **properties):
        for name, value in properties.items():
            setattr(self, name, value)


class FakeDocument:
    """Fake FreeCAD document that records getObject calls and blocks .Objects/.Label."""

    def __init__(self, objects=None):
        self._objects = dict(objects or {})
        self.calls = []

    @property
    def Objects(self):
        raise AssertionError("document.Objects must not be accessed")

    @property
    def Label(self):
        raise AssertionError("document Label lookup must not be used")

    def getObject(self, name):
        self.calls.append(name)
        return self._objects.get(name)


class FailingDocument:
    """Document that asserts if getObject is called — used for no-access cases."""

    @property
    def Objects(self):
        raise AssertionError("document.Objects must not be accessed")

    def getObject(self, name):
        raise AssertionError(
            "getObject must not be called when no supported category is requested"
        )


# ---------------------------------------------------------------------------
# Verification-data builders
# ---------------------------------------------------------------------------


def _param_binding(param_id="p.length", name="Length", group_name="Spreadsheet"):
    return {"id": param_id, "name": name, "groupName": group_name}


def _metadata_request(metadata_id="m.author", key="Author", owner_id="Doc"):
    return {"id": metadata_id, "key": key, "ownerId": owner_id}


def _reference_request(kind="constraint", name="Sketch001"):
    return {"kind": kind, "name": name}


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

    def test_observe_requested_contract_scope_is_callable(self):
        from parametron_freecad.observation.requested_scope_observation import (
            observe_requested_contract_scope,
        )

        self.assertTrue(callable(observe_requested_contract_scope))


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _ScopeTestCase(unittest.TestCase):
    def setUp(self):
        self.mod = _import_module()

    def observe(self, document, verification_data):
        return self.mod.observe_requested_contract_scope(document, verification_data)


# ---------------------------------------------------------------------------
# Section 2 — Empty or absent observe scope
# ---------------------------------------------------------------------------


class TestEmptyOrAbsentScope(_ScopeTestCase):
    def test_absent_observe_returns_empty_dict(self):
        result = self.observe(FailingDocument(), {})
        self.assertEqual(result, {})

    def test_empty_observe_returns_empty_dict(self):
        result = self.observe(FailingDocument(), {"observe": {}})
        self.assertEqual(result, {})

    def test_all_falsy_categories_return_empty_dict(self):
        data = {
            "observe": {
                "parameters": False,
                "metadata": None,
                "references": 0,
                "components": "",
            }
        }
        result = self.observe(FailingDocument(), data)
        self.assertEqual(result, {})

    def test_empty_cases_do_not_call_get_object(self):
        for data in (
            {},
            {"observe": {}},
            {"observe": {"parameters": False, "metadata": False, "references": False}},
        ):
            with self.subTest(data=data):
                # FailingDocument raises if getObject is reached.
                self.assertEqual(self.observe(FailingDocument(), data), {})


# ---------------------------------------------------------------------------
# Section 3 — Parameters-only request
# ---------------------------------------------------------------------------


class TestParametersOnly(_ScopeTestCase):
    def test_emits_only_parameters(self):
        document = FakeDocument({"Spreadsheet": FakeObject(Length=10.0)})
        data = {
            "observe": {"parameters": True},
            "observationContext": {"parameters": [_param_binding()]},
        }

        result = self.observe(document, data)

        self.assertEqual(list(result.keys()), ["parameters"])
        self.assertNotIn("metadata", result)
        self.assertNotIn("references", result)
        self.assertEqual(
            result["parameters"],
            (
                {
                    "id": "p.length",
                    "name": "Length",
                    "groupId": "Spreadsheet",
                    "value": 10.0,
                    "valueKind": "number",
                },
            ),
        )

    def test_request_order_preserved_for_multiple_bindings(self):
        document = FakeDocument(
            {
                "GroupA": FakeObject(Width=1),
                "GroupB": FakeObject(Height="tall"),
            }
        )
        data = {
            "observe": {"parameters": True},
            "observationContext": {
                "parameters": [
                    _param_binding("p.a", "Width", "GroupA"),
                    _param_binding("p.b", "Height", "GroupB"),
                ]
            },
        }

        result = self.observe(document, data)

        self.assertEqual([p["id"] for p in result["parameters"]], ["p.a", "p.b"])
        self.assertEqual(document.calls, ["GroupA", "GroupB"])


# ---------------------------------------------------------------------------
# Section 4 — Metadata-only request
# ---------------------------------------------------------------------------


class TestMetadataOnly(_ScopeTestCase):
    def test_emits_only_metadata(self):
        document = FakeDocument({"Doc": FakeObject(Author="Jane")})
        data = {
            "observe": {"metadata": True},
            "expected": {"metadata": [_metadata_request()]},
        }

        result = self.observe(document, data)

        self.assertEqual(list(result.keys()), ["metadata"])
        self.assertNotIn("parameters", result)
        self.assertNotIn("references", result)
        self.assertEqual(
            result["metadata"],
            (
                {
                    "id": "m.author",
                    "key": "Author",
                    "ownerId": "Doc",
                    "value": "Jane",
                    "valueKind": "string",
                },
            ),
        )

    def test_request_order_preserved_for_multiple_entries(self):
        document = FakeDocument(
            {
                "OwnerA": FakeObject(KeyA=1),
                "OwnerB": FakeObject(KeyB=True),
            }
        )
        data = {
            "observe": {"metadata": True},
            "expected": {
                "metadata": [
                    _metadata_request("m.a", "KeyA", "OwnerA"),
                    _metadata_request("m.b", "KeyB", "OwnerB"),
                ]
            },
        }

        result = self.observe(document, data)

        self.assertEqual([m["id"] for m in result["metadata"]], ["m.a", "m.b"])
        self.assertEqual(document.calls, ["OwnerA", "OwnerB"])


# ---------------------------------------------------------------------------
# Section 5 — References-only request
# ---------------------------------------------------------------------------


class TestReferencesOnly(_ScopeTestCase):
    def test_emits_only_references(self):
        document = FakeDocument({"Sketch001": FakeObject()})
        data = {
            "observe": {"references": True},
            "expected": {"references": [_reference_request()]},
        }

        result = self.observe(document, data)

        self.assertEqual(list(result.keys()), ["references"])
        self.assertNotIn("parameters", result)
        self.assertNotIn("metadata", result)
        self.assertEqual(tuple(result["references"][0].keys()), ("kind", "name"))
        self.assertEqual(
            result["references"], ({"kind": "constraint", "name": "Sketch001"},)
        )

    def test_request_order_preserved_for_multiple_references(self):
        document = FakeDocument({"PartA": FakeObject(), "PartB": FakeObject()})
        data = {
            "observe": {"references": True},
            "expected": {
                "references": [
                    _reference_request("part", "PartA"),
                    _reference_request("assembly", "PartB"),
                ]
            },
        }

        result = self.observe(document, data)

        self.assertEqual([r["name"] for r in result["references"]], ["PartA", "PartB"])
        self.assertEqual(document.calls, ["PartA", "PartB"])


# ---------------------------------------------------------------------------
# Section 6 — Mixed supported request emits fixed category order
# ---------------------------------------------------------------------------


class TestFixedCategoryOrder(_ScopeTestCase):
    def _full_document(self):
        return FakeDocument(
            {
                "Spreadsheet": FakeObject(Length=10.0),
                "Doc": FakeObject(Author="Jane"),
                "Sketch001": FakeObject(),
            }
        )

    def _full_data(self):
        # Input mapping order is references, metadata, parameters.
        return {
            "observe": {
                "references": True,
                "metadata": True,
                "parameters": True,
            },
            "observationContext": {"parameters": [_param_binding()]},
            "expected": {
                "metadata": [_metadata_request()],
                "references": [_reference_request()],
            },
        }

    def test_output_key_order_is_fixed(self):
        result = self.observe(self._full_document(), self._full_data())
        self.assertEqual(list(result.keys()), ["parameters", "metadata", "references"])

    def test_all_three_categories_present(self):
        result = self.observe(self._full_document(), self._full_data())
        self.assertEqual(set(result.keys()), {"parameters", "metadata", "references"})
        self.assertEqual(len(result["parameters"]), 1)
        self.assertEqual(len(result["metadata"]), 1)
        self.assertEqual(len(result["references"]), 1)


# ---------------------------------------------------------------------------
# Section 6b — Routed through deterministic ordering (item field order)
# ---------------------------------------------------------------------------


class TestRoutedThroughOrdering(_ScopeTestCase):
    def _full_document(self):
        return FakeDocument(
            {
                "Spreadsheet": FakeObject(Length=10.0),
                "Doc": FakeObject(Author="Jane"),
                "Sketch001": FakeObject(),
            }
        )

    def _full_data(self):
        return {
            "observe": {
                "references": True,
                "metadata": True,
                "parameters": True,
            },
            "observationContext": {"parameters": [_param_binding()]},
            "expected": {
                "metadata": [_metadata_request()],
                "references": [_reference_request()],
            },
        }

    def test_category_order_is_contract_aligned(self):
        result = self.observe(self._full_document(), self._full_data())
        self.assertEqual(
            list(result.keys()),
            ["parameters", "metadata", "references"],
        )

    def test_parameter_item_field_order_is_contract_aligned(self):
        result = self.observe(self._full_document(), self._full_data())
        self.assertEqual(
            tuple(result["parameters"][0].keys()),
            ("id", "name", "groupId", "value", "valueKind"),
        )

    def test_metadata_item_field_order_is_contract_aligned(self):
        result = self.observe(self._full_document(), self._full_data())
        self.assertEqual(
            tuple(result["metadata"][0].keys()),
            ("id", "key", "ownerId", "value", "valueKind"),
        )

    def test_reference_item_field_order_is_contract_aligned(self):
        result = self.observe(self._full_document(), self._full_data())
        self.assertEqual(
            tuple(result["references"][0].keys()),
            ("kind", "name"),
        )

    def test_categories_returned_as_tuples(self):
        result = self.observe(self._full_document(), self._full_data())
        self.assertIsInstance(result["parameters"], tuple)
        self.assertIsInstance(result["metadata"], tuple)
        self.assertIsInstance(result["references"], tuple)


# ---------------------------------------------------------------------------
# Section 7 — Unrequested helper is not called
# ---------------------------------------------------------------------------


class TestUnrequestedHelperNotCalled(_ScopeTestCase):
    def test_parameters_only_ignores_invalid_metadata_and_references(self):
        document = FakeDocument({"Spreadsheet": FakeObject(Length=10.0)})
        data = {
            "observe": {"parameters": True},
            "observationContext": {"parameters": [_param_binding()]},
            "expected": {
                "metadata": "not-a-list",
                "references": 42,
            },
        }

        result = self.observe(document, data)

        self.assertEqual(list(result.keys()), ["parameters"])

    def test_metadata_only_ignores_invalid_parameters_and_references(self):
        document = FakeDocument({"Doc": FakeObject(Author="Jane")})
        data = {
            "observe": {"metadata": True},
            "observationContext": {"parameters": "not-a-list"},
            "expected": {
                "metadata": [_metadata_request()],
                "references": object(),
            },
        }

        result = self.observe(document, data)

        self.assertEqual(list(result.keys()), ["metadata"])

    def test_references_only_ignores_invalid_parameters_and_metadata(self):
        document = FakeDocument({"Sketch001": FakeObject()})
        data = {
            "observe": {"references": True},
            "observationContext": {"parameters": 99},
            "expected": {
                "metadata": object(),
                "references": [_reference_request()],
            },
        }

        result = self.observe(document, data)

        self.assertEqual(list(result.keys()), ["references"])


# ---------------------------------------------------------------------------
# Section 8 — Unsupported components are ignored
# ---------------------------------------------------------------------------


class TestComponentsIgnored(_ScopeTestCase):
    def test_components_only_returns_empty_dict(self):
        result = self.observe(FailingDocument(), {"observe": {"components": True}})
        self.assertEqual(result, {})
        self.assertNotIn("components", result)

    def test_components_only_does_not_access_document(self):
        # FailingDocument raises on getObject and on .Objects access.
        self.observe(FailingDocument(), {"observe": {"components": True}})

    def test_mixed_components_and_references_emits_only_references(self):
        document = FakeDocument({"Sketch001": FakeObject()})
        data = {
            "observe": {"components": True, "references": True},
            "expected": {"references": [_reference_request()]},
        }

        result = self.observe(document, data)

        self.assertEqual(list(result.keys()), ["references"])
        self.assertNotIn("components", result)


# ---------------------------------------------------------------------------
# Section 9 — No document.Objects fallback or discovery
# ---------------------------------------------------------------------------


class TestNoObjectsFallback(_ScopeTestCase):
    def test_supported_observations_never_access_objects(self):
        document = FakeDocument(
            {
                "Spreadsheet": FakeObject(Length=10.0),
                "Doc": FakeObject(Author="Jane"),
                "Sketch001": FakeObject(),
            }
        )
        data = {
            "observe": {"parameters": True, "metadata": True, "references": True},
            "observationContext": {"parameters": [_param_binding()]},
            "expected": {
                "metadata": [_metadata_request()],
                "references": [_reference_request()],
            },
        }

        # FakeDocument.Objects raises AssertionError if touched.
        result = self.observe(document, data)

        self.assertEqual(set(result.keys()), {"parameters", "metadata", "references"})


# ---------------------------------------------------------------------------
# Section 10 — Existing helper errors propagate unchanged
# ---------------------------------------------------------------------------


class TestHelperErrorsPropagate(_ScopeTestCase):
    def test_parameter_missing_object_propagates_typed_error(self):
        from parametron_freecad.observation.parameter_observation import (
            ParameterObservationObjectNotFoundError,
        )

        document = FakeDocument({})
        data = {
            "observe": {"parameters": True},
            "observationContext": {"parameters": [_param_binding()]},
        }

        with self.assertRaises(ParameterObservationObjectNotFoundError):
            self.observe(document, data)

    def test_metadata_missing_owner_propagates_typed_error(self):
        from parametron_freecad.observation.metadata_observation import (
            MetadataObservationOwnerNotFoundError,
        )

        document = FakeDocument({})
        data = {
            "observe": {"metadata": True},
            "expected": {"metadata": [_metadata_request()]},
        }

        with self.assertRaises(MetadataObservationOwnerNotFoundError):
            self.observe(document, data)

    def test_reference_missing_object_propagates_typed_error(self):
        from parametron_freecad.observation.reference_observation import (
            ReferenceObservationReferenceNotFoundError,
        )

        document = FakeDocument({})
        data = {
            "observe": {"references": True},
            "expected": {"references": [_reference_request()]},
        }

        with self.assertRaises(ReferenceObservationReferenceNotFoundError):
            self.observe(document, data)

    def test_typed_error_is_not_wrapped_in_composition_error(self):
        from parametron_freecad.observation.reference_observation import (
            ReferenceObservationReferenceNotFoundError,
        )

        document = FakeDocument({})
        data = {
            "observe": {"references": True},
            "expected": {"references": [_reference_request()]},
        }

        with self.assertRaises(ReferenceObservationReferenceNotFoundError) as cm:
            self.observe(document, data)

        self.assertNotIsInstance(cm.exception, self.mod.RequestedScopeObservationError)


# ---------------------------------------------------------------------------
# Section 11 — Malformed top-level composition input
# ---------------------------------------------------------------------------


class TestMalformedCompositionInput(_ScopeTestCase):
    def test_non_mapping_verification_data_raises_request_error(self):
        for value in (None, 42, "string", [], True):
            with self.subTest(value=value):
                with self.assertRaises(self.mod.RequestedScopeObservationRequestError):
                    self.observe(FailingDocument(), value)

    def test_non_mapping_observe_raises_request_error(self):
        for value in (None, 42, "string", [], True):
            with self.subTest(value=value):
                with self.assertRaises(self.mod.RequestedScopeObservationRequestError):
                    self.observe(FailingDocument(), {"observe": value})

    def test_composition_request_error_hierarchy(self):
        self.assertTrue(
            issubclass(
                self.mod.RequestedScopeObservationRequestError,
                self.mod.RequestedScopeObservationError,
            )
        )
        self.assertTrue(
            issubclass(self.mod.RequestedScopeObservationError, ValueError)
        )


# ---------------------------------------------------------------------------
# Section 12 — No file writing and no input mutation
# ---------------------------------------------------------------------------


class TestNoFileWriting(_ScopeTestCase):
    def test_helper_does_not_write_files(self):
        document = FakeDocument(
            {
                "Spreadsheet": FakeObject(Length=10.0),
                "Doc": FakeObject(Author="Jane"),
                "Sketch001": FakeObject(),
            }
        )
        data = {
            "observe": {"parameters": True, "metadata": True, "references": True},
            "observationContext": {"parameters": [_param_binding()]},
            "expected": {
                "metadata": [_metadata_request()],
                "references": [_reference_request()],
            },
        }

        with mock.patch("builtins.open", side_effect=AssertionError("must not open files")):
            self.observe(document, data)

    def test_no_files_created_in_temp_dir(self):
        import tempfile
        from pathlib import Path

        document = FakeDocument({"Sketch001": FakeObject()})
        data = {
            "observe": {"references": True},
            "expected": {"references": [_reference_request()]},
        }

        with tempfile.TemporaryDirectory() as tmp:
            self.observe(document, data)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_helper_does_not_mutate_verification_data(self):
        document = FakeDocument(
            {
                "Spreadsheet": FakeObject(Length=10.0),
                "Doc": FakeObject(Author="Jane"),
                "Sketch001": FakeObject(),
            }
        )
        data = {
            "observe": {"parameters": True, "metadata": True, "references": True},
            "observationContext": {"parameters": [_param_binding()]},
            "expected": {
                "metadata": [_metadata_request()],
                "references": [_reference_request()],
            },
        }
        before = copy.deepcopy(data)

        self.observe(document, data)

        self.assertEqual(data, before)


if __name__ == "__main__":
    unittest.main()
