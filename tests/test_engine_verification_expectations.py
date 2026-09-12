"""Tests for Engine verification expectation compatibility classifier.

Coverage:
 1. Import safety and public API
 2. Minimal Engine verification shape compatibility
 3. Runtime-context metadata compatibility
 4. Runtime-context reference compatibility
 5. Document-backed metadata compatibility
 6. Document-backed reference compatibility
 7. Parameter compatibility with explicit observation context
 8. Component expectations are unsupported
 9. Unknown category diagnostics
10. Malformed root/surface diagnostics
11. Strict helper behavior
12. Deterministic ordering
13. Input non-mutation
14. Existing runtime behavior regression
"""

from __future__ import annotations

import builtins
import copy
import importlib
import sys
import types
import unittest
from unittest import mock

import parametron_freecad.observation.engine_verification_expectations as eve

_MODULE = "parametron_freecad.observation.engine_verification_expectations"

validate = eve.validate_engine_verification_expectations
require = eve.require_engine_verification_expectations_compatible
Compatibility = eve.EngineVerificationExpectationCompatibility
Diagnostic = eve.EngineVerificationExpectationDiagnostic
CompatibilityError = eve.EngineVerificationExpectationCompatibilityError


def _minimal_payload() -> dict:
    """Canonical minimal Engine verification shape for classifier input."""
    return {
        "schemaVersion": "1.0",
        "observe": {
            "components": False,
            "parameters": False,
            "metadata": True,
            "references": True,
        },
        "observationContext": {
            "parameters": [],
        },
        "expected": {
            "components": [],
            "parameters": [],
            "metadata": [{"key": "working_copy_sha256"}],
            "references": [{"kind": "working_copy_path"}],
        },
        "checks": {
            "components": {"enabled": False},
            "parameters": {"enabled": False},
            "metadata": {"enabled": True},
            "references": {"enabled": True},
        },
    }


def _mixed_incompatible_payload() -> dict:
    """Payload with issues across all surfaces to test diagnostic ordering."""
    return {
        "observe": {
            "components": True,
            "parameters": True,
            "metadata": True,
            "references": True,
            "unknownObserve": True,
        },
        "checks": {
            "components": {"enabled": True},
            "parameters": {"enabled": True},
            "metadata": {"enabled": True},
            "references": {"enabled": True},
            "unknownChecks": True,
        },
        "expected": {
            "components": [{"id": "c1"}],
            "parameters": [{"id": "unmatched"}],
            "metadata": [{"key": "some-key"}],
            "references": [{"kind": "constraint"}],
            "unknownExpected": [],
        },
        "observationContext": {
            "parameters": [
                {"id": "b1", "name": "N1"},
            ]
        },
    }


# ===========================================================================
# 1. Import safety and public API
# ===========================================================================


class ImportSafetyTests(unittest.TestCase):

    def test_module_imports_without_freecad(self) -> None:
        guarded = {"FreeCAD", "FreeCADGui", "freecad"}
        original_import = builtins.__import__
        original_module = sys.modules.get(_MODULE)

        for name in [_MODULE, *guarded]:
            sys.modules.pop(name, None)

        def _restore():
            if original_module is not None:
                sys.modules[_MODULE] = original_module
            else:
                sys.modules.pop(_MODULE, None)

        self.addCleanup(_restore)

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in guarded:
                raise AssertionError(f"{name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module(_MODULE)

        self.assertIsInstance(module, types.ModuleType)

    def test_no_freecad_in_sys_modules_after_import(self) -> None:
        importlib.import_module(_MODULE)
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_validator_is_callable(self) -> None:
        self.assertTrue(callable(validate))

    def test_strict_helper_is_callable(self) -> None:
        self.assertTrue(callable(require))

    def test_compatibility_is_frozen_dataclass(self) -> None:
        result = validate(_minimal_payload())
        with self.assertRaises((AttributeError, TypeError)):
            result.compatible = False  # type: ignore[misc]

    def test_diagnostic_is_frozen_dataclass(self) -> None:
        result = validate({"observe": {"components": True}, "expected": {}, "checks": {}})
        self.assertTrue(result.diagnostics)
        diag = result.diagnostics[0]
        with self.assertRaises((AttributeError, TypeError)):
            diag.code = "mutated"  # type: ignore[misc]

    def test_compatibility_error_is_value_error_subclass(self) -> None:
        self.assertTrue(issubclass(CompatibilityError, ValueError))

    def test_module_exposes_severity_constants(self) -> None:
        self.assertEqual(eve.SEVERITY_INVALID, "invalid")
        self.assertEqual(eve.SEVERITY_UNSUPPORTED, "unsupported")

    def test_module_does_not_require_runtime_document_handle(self) -> None:
        module = importlib.import_module(_MODULE)
        for name in dir(module):
            self.assertNotIn(
                "freecad",
                name.lower(),
                msg=f"Unexpected FreeCAD-named attribute: {name}",
            )


# ===========================================================================
# 2. Minimal Engine verification shape compatibility
# ===========================================================================


class MinimalEngineShapeCompatibilityTests(unittest.TestCase):

    def setUp(self):
        self.result = validate(_minimal_payload())

    def test_compatible_is_true(self) -> None:
        self.assertTrue(self.result.compatible)

    def test_diagnostics_are_empty(self) -> None:
        self.assertEqual(self.result.diagnostics, ())

    def test_supported_categories_include_metadata(self) -> None:
        self.assertIn("metadata", self.result.supported_categories)

    def test_supported_categories_include_references(self) -> None:
        self.assertIn("references", self.result.supported_categories)

    def test_unsupported_categories_are_empty(self) -> None:
        self.assertEqual(self.result.unsupported_categories, ())

    def test_input_not_mutated(self) -> None:
        payload = _minimal_payload()
        before = copy.deepcopy(payload)
        validate(payload)
        self.assertEqual(payload, before)


# ===========================================================================
# 3. Runtime-context metadata compatibility
# ===========================================================================


class RuntimeContextMetadataCompatibilityTests(unittest.TestCase):

    def _payload(self, entry: dict) -> dict:
        return {
            "observe": {"metadata": True},
            "expected": {"metadata": [entry]},
            "checks": {},
        }

    def test_working_copy_sha256_entry_compatible(self) -> None:
        result = validate(self._payload({"key": "working_copy_sha256"}))
        self.assertTrue(result.compatible)
        self.assertEqual(result.diagnostics, ())

    def test_working_copy_sha256_without_id_compatible(self) -> None:
        entry = {"key": "working_copy_sha256"}
        self.assertNotIn("id", entry)
        self.assertTrue(validate(self._payload(entry)).compatible)

    def test_working_copy_sha256_without_owner_id_compatible(self) -> None:
        entry = {"key": "working_copy_sha256"}
        self.assertNotIn("ownerId", entry)
        self.assertTrue(validate(self._payload(entry)).compatible)

    def test_expected_value_not_required_by_classifier(self) -> None:
        for entry in [
            {"key": "working_copy_sha256"},
            {"key": "working_copy_sha256", "value": "some-sha256"},
            {"key": "working_copy_sha256", "value": None},
        ]:
            with self.subTest(entry=entry):
                self.assertTrue(validate(self._payload(entry)).compatible)

    def test_runtime_context_metadata_in_supported_categories(self) -> None:
        result = validate(self._payload({"key": "working_copy_sha256"}))
        self.assertIn("metadata", result.supported_categories)


# ===========================================================================
# 4. Runtime-context reference compatibility
# ===========================================================================


class RuntimeContextReferenceCompatibilityTests(unittest.TestCase):

    def _payload(self, entry: dict) -> dict:
        return {
            "observe": {"references": True},
            "expected": {"references": [entry]},
            "checks": {},
        }

    def test_working_copy_path_entry_compatible(self) -> None:
        result = validate(self._payload({"kind": "working_copy_path"}))
        self.assertTrue(result.compatible)
        self.assertEqual(result.diagnostics, ())

    def test_working_copy_path_without_name_compatible(self) -> None:
        entry = {"kind": "working_copy_path"}
        self.assertNotIn("name", entry)
        self.assertTrue(validate(self._payload(entry)).compatible)

    def test_expected_path_value_not_interpreted(self) -> None:
        for entry in [
            {"kind": "working_copy_path"},
            {"kind": "working_copy_path", "name": "/some/expected/path.FCStd"},
        ]:
            with self.subTest(entry=entry):
                self.assertTrue(validate(self._payload(entry)).compatible)

    def test_runtime_context_reference_in_supported_categories(self) -> None:
        result = validate(self._payload({"kind": "working_copy_path"}))
        self.assertIn("references", result.supported_categories)


# ===========================================================================
# 5. Document-backed metadata compatibility
# ===========================================================================


class DocumentBackedMetadataCompatibilityTests(unittest.TestCase):

    def _payload(self, entries: list) -> dict:
        return {
            "observe": {"metadata": True},
            "expected": {"metadata": entries},
            "checks": {},
        }

    def test_valid_document_backed_metadata_compatible(self) -> None:
        result = validate(self._payload([
            {"id": "m.title", "key": "Title", "ownerId": "Doc"},
        ]))
        self.assertTrue(result.compatible)
        self.assertEqual(result.diagnostics, ())

    def test_document_backed_metadata_in_supported_categories(self) -> None:
        result = validate(self._payload([
            {"id": "m.title", "key": "Title", "ownerId": "Doc"},
        ]))
        self.assertIn("metadata", result.supported_categories)

    def test_missing_id_incompatible(self) -> None:
        result = validate(self._payload([{"key": "Title", "ownerId": "Doc"}]))
        self.assertFalse(result.compatible)
        self.assertTrue(any("id" in d.path for d in result.diagnostics))

    def test_missing_key_incompatible(self) -> None:
        result = validate(self._payload([{"id": "m.title", "ownerId": "Doc"}]))
        self.assertFalse(result.compatible)
        self.assertTrue(any("key" in d.path for d in result.diagnostics))

    def test_missing_owner_id_incompatible(self) -> None:
        result = validate(self._payload([{"id": "m.title", "key": "Title"}]))
        self.assertFalse(result.compatible)
        self.assertTrue(any("ownerId" in d.path for d in result.diagnostics))

    def test_non_string_id_incompatible(self) -> None:
        result = validate(self._payload([{"id": 123, "key": "Title", "ownerId": "Doc"}]))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.metadata.request_invalid", codes)

    def test_non_string_key_incompatible(self) -> None:
        result = validate(self._payload([{"id": "m.title", "key": 123, "ownerId": "Doc"}]))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.metadata.request_invalid", codes)

    def test_non_string_owner_id_incompatible(self) -> None:
        result = validate(self._payload([{"id": "m.title", "key": "Title", "ownerId": 123}]))
        self.assertFalse(result.compatible)

    def test_non_list_expected_metadata_incompatible(self) -> None:
        result = validate({
            "observe": {"metadata": True},
            "expected": {"metadata": "not-a-list"},
            "checks": {},
        })
        self.assertFalse(result.compatible)
        self.assertTrue(any(d.path == "$.expected.metadata" for d in result.diagnostics))

    def test_non_mapping_metadata_item_incompatible(self) -> None:
        result = validate(self._payload(["not-a-mapping"]))
        self.assertFalse(result.compatible)
        self.assertTrue(any("metadata" in d.path for d in result.diagnostics))

    def test_diagnostic_path_for_missing_id_is_stable(self) -> None:
        result = validate(self._payload([{"key": "Title", "ownerId": "Doc"}]))
        id_diags = [d for d in result.diagnostics if "id" in d.path]
        self.assertTrue(id_diags)
        self.assertEqual(id_diags[0].path, "$.expected.metadata[0].id")


# ===========================================================================
# 6. Document-backed reference compatibility
# ===========================================================================


class DocumentBackedReferenceCompatibilityTests(unittest.TestCase):

    def _payload(self, entries: list) -> dict:
        return {
            "observe": {"references": True},
            "expected": {"references": entries},
            "checks": {},
        }

    def test_valid_document_backed_reference_compatible(self) -> None:
        result = validate(self._payload([{"kind": "constraint", "name": "Sketch001"}]))
        self.assertTrue(result.compatible)
        self.assertEqual(result.diagnostics, ())

    def test_document_backed_reference_in_supported_categories(self) -> None:
        result = validate(self._payload([{"kind": "constraint", "name": "Sketch001"}]))
        self.assertIn("references", result.supported_categories)

    def test_missing_kind_incompatible(self) -> None:
        result = validate(self._payload([{"name": "Sketch001"}]))
        self.assertFalse(result.compatible)
        self.assertTrue(any("kind" in d.path for d in result.diagnostics))

    def test_missing_name_incompatible(self) -> None:
        result = validate(self._payload([{"kind": "constraint"}]))
        self.assertFalse(result.compatible)
        self.assertTrue(any("name" in d.path for d in result.diagnostics))

    def test_non_string_kind_incompatible(self) -> None:
        result = validate(self._payload([{"kind": 123, "name": "Sketch001"}]))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.references.request_invalid", codes)

    def test_non_string_name_incompatible(self) -> None:
        result = validate(self._payload([{"kind": "constraint", "name": 123}]))
        self.assertFalse(result.compatible)

    def test_non_list_expected_references_incompatible(self) -> None:
        result = validate({
            "observe": {"references": True},
            "expected": {"references": "not-a-list"},
            "checks": {},
        })
        self.assertFalse(result.compatible)
        self.assertTrue(any(d.path == "$.expected.references" for d in result.diagnostics))

    def test_non_mapping_reference_item_incompatible(self) -> None:
        result = validate(self._payload(["not-a-mapping"]))
        self.assertFalse(result.compatible)
        self.assertTrue(any("references" in d.path for d in result.diagnostics))

    def test_diagnostic_path_for_missing_name_is_stable(self) -> None:
        result = validate(self._payload([{"kind": "constraint"}]))
        name_diags = [d for d in result.diagnostics if "name" in d.path]
        self.assertTrue(name_diags)
        self.assertEqual(name_diags[0].path, "$.expected.references[0].name")


# ===========================================================================
# 7. Parameter compatibility with explicit observation context
# ===========================================================================


class ParameterCompatibilityTests(unittest.TestCase):

    def _payload(
        self,
        *,
        observe_parameters: bool = True,
        checks_enabled: bool = True,
        expected_parameters: list | None = None,
        context_parameters: list | None = None,
    ) -> dict:
        payload: dict = {
            "observe": {"parameters": observe_parameters},
            "checks": {"parameters": {"enabled": checks_enabled}},
            "expected": {"parameters": expected_parameters or []},
        }
        if context_parameters is not None:
            payload["observationContext"] = {"parameters": context_parameters}
        return payload

    def test_explicit_bindings_with_matching_ids_compatible(self) -> None:
        result = validate(self._payload(
            expected_parameters=[{"id": "p.width"}],
            context_parameters=[{"id": "p.width", "name": "Width", "groupName": "Dims"}],
        ))
        self.assertTrue(result.compatible)
        self.assertEqual(result.diagnostics, ())

    def test_compatible_explicit_params_in_supported_categories(self) -> None:
        result = validate(self._payload(
            expected_parameters=[{"id": "p.width"}],
            context_parameters=[{"id": "p.width", "name": "Width", "groupName": "Dims"}],
        ))
        self.assertIn("parameters", result.supported_categories)

    def test_no_value_comparison_occurs_in_compatible_result(self) -> None:
        result = validate(self._payload(
            expected_parameters=[{"id": "p.width", "value": 42.0}],
            context_parameters=[{"id": "p.width", "name": "Width", "groupName": "Dims"}],
        ))
        self.assertTrue(result.compatible)

    def test_no_unit_conversion_occurs_in_compatible_result(self) -> None:
        result = validate(self._payload(
            expected_parameters=[{"id": "p.w", "value": 10, "unit": "mm"}],
            context_parameters=[{"id": "p.w", "name": "W", "groupName": "G"}],
        ))
        self.assertTrue(result.compatible)

    def test_observe_parameters_true_without_observation_context_incompatible(
        self,
    ) -> None:
        result = validate(self._payload(context_parameters=None))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.parameters.context_missing", codes)

    def test_observe_parameters_true_with_empty_context_incompatible(self) -> None:
        result = validate(self._payload(context_parameters=[]))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.parameters.context_missing", codes)

    def test_unmatched_expected_parameter_id_incompatible(self) -> None:
        result = validate(self._payload(
            expected_parameters=[{"id": "unmatched"}],
            context_parameters=[{"id": "p.width", "name": "Width", "groupName": "Dims"}],
        ))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.parameters.identity_unmapped", codes)

    def test_non_empty_expected_params_without_flags_requires_context(self) -> None:
        result = validate({
            "observe": {"parameters": False},
            "checks": {"parameters": {"enabled": False}},
            "expected": {"parameters": [{"id": "p.x"}]},
        })
        self.assertFalse(result.compatible)

    def test_duplicate_binding_id_incompatible(self) -> None:
        result = validate(self._payload(
            expected_parameters=[{"id": "p.x"}],
            context_parameters=[
                {"id": "p.x", "name": "X", "groupName": "G"},
                {"id": "p.x", "name": "X2", "groupName": "G"},
            ],
        ))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.parameters.binding_duplicate", codes)

    def test_binding_missing_id_produces_binding_invalid(self) -> None:
        result = validate(self._payload(
            expected_parameters=[],
            context_parameters=[{"name": "X", "groupName": "G"}],
        ))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.parameters.binding_invalid", codes)

    def test_binding_missing_name_produces_binding_invalid(self) -> None:
        result = validate(self._payload(
            expected_parameters=[],
            context_parameters=[{"id": "p.x", "groupName": "G"}],
        ))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.parameters.binding_invalid", codes)

    def test_binding_missing_group_name_produces_binding_invalid(self) -> None:
        result = validate(self._payload(
            expected_parameters=[],
            context_parameters=[{"id": "p.x", "name": "X"}],
        ))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.parameters.binding_invalid", codes)

    def test_non_string_binding_id_produces_binding_invalid(self) -> None:
        result = validate(self._payload(
            expected_parameters=[],
            context_parameters=[{"id": 123, "name": "X", "groupName": "G"}],
        ))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.parameters.binding_invalid", codes)

    def test_non_mapping_binding_item_produces_binding_invalid(self) -> None:
        result = validate(self._payload(
            expected_parameters=[],
            context_parameters=["not-a-mapping"],
        ))
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.parameters.binding_invalid", codes)

    def test_non_list_observation_context_parameters_incompatible(self) -> None:
        result = validate({
            "observe": {"parameters": True},
            "checks": {},
            "expected": {},
            "observationContext": {"parameters": "not-a-list"},
        })
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.parameters.context_missing", codes)

    def test_non_list_expected_parameters_produces_invalid_diagnostic(self) -> None:
        result = validate({
            "observe": {"parameters": True},
            "checks": {},
            "expected": {"parameters": "not-a-list"},
        })
        self.assertFalse(result.compatible)
        self.assertTrue(any(d.path == "$.expected.parameters" for d in result.diagnostics))

    def test_diagnostic_path_identifies_binding_field(self) -> None:
        result = validate(self._payload(
            expected_parameters=[],
            context_parameters=[{"id": "p.x", "name": "X"}],
        ))
        paths = [d.path for d in result.diagnostics]
        self.assertIn("$.observationContext.parameters[0].groupName", paths)

    def test_diagnostic_path_identifies_unmapped_parameter_id(self) -> None:
        result = validate(self._payload(
            expected_parameters=[{"id": "missing-id"}],
            context_parameters=[{"id": "p.x", "name": "X", "groupName": "G"}],
        ))
        paths = [d.path for d in result.diagnostics]
        self.assertIn("$.expected.parameters[0].id", paths)


# ===========================================================================
# 8. Component expectations are unsupported/planned
# ===========================================================================


class ComponentUnsupportedTests(unittest.TestCase):

    def test_observe_components_true_incompatible(self) -> None:
        result = validate({"observe": {"components": True}, "expected": {}, "checks": {}})
        self.assertFalse(result.compatible)

    def test_observe_components_true_diagnostic_code(self) -> None:
        result = validate({"observe": {"components": True}, "expected": {}, "checks": {}})
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.components.unsupported", codes)

    def test_checks_components_enabled_true_incompatible(self) -> None:
        result = validate({
            "observe": {},
            "checks": {"components": {"enabled": True}},
            "expected": {},
        })
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.components.unsupported", codes)

    def test_non_empty_expected_components_incompatible(self) -> None:
        result = validate({
            "observe": {},
            "checks": {},
            "expected": {"components": [{"id": "c1", "kind": "part", "name": "Body"}]},
        })
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.components.unsupported", codes)

    def test_components_in_unsupported_categories(self) -> None:
        result = validate({"observe": {"components": True}, "expected": {}, "checks": {}})
        self.assertIn("components", result.unsupported_categories)

    def test_components_not_in_supported_categories(self) -> None:
        result = validate({"observe": {"components": True}, "expected": {}, "checks": {}})
        self.assertNotIn("components", result.supported_categories)

    def test_observe_components_false_produces_no_component_diagnostic(self) -> None:
        result = validate(_minimal_payload())
        self.assertEqual([d for d in result.diagnostics if d.category == "components"], [])

    def test_component_diagnostic_path_references_components(self) -> None:
        result = validate({"observe": {"components": True}, "expected": {}, "checks": {}})
        comp_diags = [d for d in result.diagnostics if d.category == "components"]
        self.assertTrue(comp_diags)
        self.assertIn("components", comp_diags[0].path)


# ===========================================================================
# 9. Unknown category diagnostics
# ===========================================================================


class UnknownCategoryDiagnosticsTests(unittest.TestCase):

    def test_unknown_observe_category_incompatible(self) -> None:
        result = validate({"observe": {"unknownCat": True}, "expected": {}, "checks": {}})
        self.assertFalse(result.compatible)

    def test_unknown_observe_category_code(self) -> None:
        result = validate({"observe": {"unknownCat": True}, "expected": {}, "checks": {}})
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.observe.unknown_category", codes)

    def test_unknown_checks_category_incompatible(self) -> None:
        result = validate({"observe": {}, "checks": {"unknownCat": True}, "expected": {}})
        self.assertFalse(result.compatible)

    def test_unknown_checks_category_code(self) -> None:
        result = validate({"observe": {}, "checks": {"unknownCat": True}, "expected": {}})
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.checks.unknown_category", codes)

    def test_unknown_expected_category_incompatible(self) -> None:
        result = validate({"observe": {}, "checks": {}, "expected": {"unknownCat": []}})
        self.assertFalse(result.compatible)

    def test_unknown_expected_category_code(self) -> None:
        result = validate({"observe": {}, "checks": {}, "expected": {"unknownCat": []}})
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.expected.unknown_category", codes)

    def test_known_categories_classified_alongside_unknowns(self) -> None:
        result = validate({
            "observe": {"metadata": True, "unknownX": True},
            "checks": {},
            "expected": {"metadata": [{"key": "working_copy_sha256"}]},
        })
        self.assertFalse(result.compatible)
        self.assertIn("metadata", result.supported_categories)


# ===========================================================================
# 10. Malformed root/surface diagnostics
# ===========================================================================


class MalformedRootSurfaceTests(unittest.TestCase):

    def test_non_mapping_root_incompatible(self) -> None:
        for bad in ["string", 42, None, [], ()]:
            with self.subTest(bad=bad):
                self.assertFalse(validate(bad).compatible)

    def test_non_mapping_root_produces_root_invalid_code(self) -> None:
        result = validate("not-a-mapping")
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.root.invalid", codes)

    def test_non_mapping_root_path_is_dollar(self) -> None:
        result = validate([])
        diags = [d for d in result.diagnostics if d.code == "engine_verification.root.invalid"]
        self.assertTrue(diags)
        self.assertEqual(diags[0].path, "$")

    def test_non_mapping_observe_produces_observe_invalid_code(self) -> None:
        result = validate({"observe": "bad", "expected": {}, "checks": {}})
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.observe.invalid", codes)

    def test_non_mapping_expected_produces_expected_invalid_code(self) -> None:
        result = validate({"observe": {}, "expected": "bad", "checks": {}})
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.expected.invalid", codes)

    def test_non_mapping_checks_produces_checks_invalid_code(self) -> None:
        result = validate({"observe": {}, "expected": {}, "checks": "bad"})
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.checks.invalid", codes)

    def test_non_mapping_observation_context_produces_invalid_code(self) -> None:
        result = validate({
            "observe": {},
            "expected": {},
            "checks": {},
            "observationContext": "bad",
        })
        self.assertFalse(result.compatible)
        codes = [d.code for d in result.diagnostics]
        self.assertIn("engine_verification.observation_context.invalid", codes)

    def test_validator_does_not_raise_on_malformed_inputs(self) -> None:
        for bad in [
            "string", 42, None, [],
            {"observe": "bad"},
            {"observe": {}, "expected": "bad"},
            {"observe": {}, "expected": {}, "checks": "bad"},
        ]:
            with self.subTest(bad=bad):
                try:
                    result = validate(bad)
                    self.assertFalse(result.compatible)
                except Exception as exc:  # noqa: BLE001
                    self.fail(f"validate raised unexpectedly for {bad!r}: {exc}")


# ===========================================================================
# 11. Strict helper behavior
# ===========================================================================


class StrictHelperTests(unittest.TestCase):

    def test_compatible_payload_returns_none(self) -> None:
        result = require(_minimal_payload())
        self.assertIsNone(result)

    def test_incompatible_payload_raises_compatibility_error(self) -> None:
        with self.assertRaises(CompatibilityError):
            require({"observe": {"components": True}, "expected": {}, "checks": {}})

    def test_error_is_value_error(self) -> None:
        with self.assertRaises(ValueError):
            require({"observe": {"components": True}, "expected": {}, "checks": {}})

    def test_error_carries_compatibility_object(self) -> None:
        with self.assertRaises(CompatibilityError) as ctx:
            require({"observe": {"components": True}, "expected": {}, "checks": {}})
        self.assertIsInstance(ctx.exception.compatibility, Compatibility)

    def test_error_compatibility_is_not_compatible(self) -> None:
        with self.assertRaises(CompatibilityError) as ctx:
            require({"observe": {"components": True}, "expected": {}, "checks": {}})
        self.assertFalse(ctx.exception.compatibility.compatible)

    def test_error_compatibility_has_diagnostics(self) -> None:
        with self.assertRaises(CompatibilityError) as ctx:
            require({"observe": {"components": True}, "expected": {}, "checks": {}})
        self.assertTrue(ctx.exception.compatibility.diagnostics)

    def test_error_message_contains_compatibility_context(self) -> None:
        try:
            require({"observe": {"components": True}, "expected": {}, "checks": {}})
        except CompatibilityError as exc:
            self.assertIn("compatible", str(exc).lower())
        else:
            self.fail("CompatibilityError not raised")

    def test_error_message_contains_no_pass_fail_decision(self) -> None:
        try:
            require({"observe": {"components": True}, "expected": {}, "checks": {}})
        except CompatibilityError as exc:
            msg = str(exc).lower()
            self.assertNotIn("pass", msg)
            self.assertNotIn("fail", msg)
        else:
            self.fail("CompatibilityError not raised")

    def test_repeated_calls_produce_same_error_message(self) -> None:
        payload = {"observe": {"components": True}, "expected": {}, "checks": {}}
        msgs = []
        for _ in range(3):
            try:
                require(payload)
            except CompatibilityError as exc:
                msgs.append(str(exc))
        self.assertEqual(len(set(msgs)), 1)


# ===========================================================================
# 12. Deterministic ordering
# ===========================================================================


class DeterministicOrderingTests(unittest.TestCase):

    def setUp(self):
        self.result = validate(_mixed_incompatible_payload())

    def test_result_is_incompatible(self) -> None:
        self.assertFalse(self.result.compatible)

    def test_diagnostics_tuple_non_empty(self) -> None:
        self.assertTrue(self.result.diagnostics)

    def test_repeated_calls_produce_identical_diagnostic_tuples(self) -> None:
        a = validate(_mixed_incompatible_payload())
        b = validate(_mixed_incompatible_payload())
        self.assertEqual(a.diagnostics, b.diagnostics)

    def test_observe_diagnostics_before_checks_diagnostics(self) -> None:
        paths = [d.path for d in self.result.diagnostics]
        obs_indices = [i for i, p in enumerate(paths) if p.startswith("$.observe.")]
        chk_indices = [i for i, p in enumerate(paths) if p.startswith("$.checks.")]
        if obs_indices and chk_indices:
            self.assertLess(max(obs_indices), min(chk_indices))

    def test_checks_diagnostics_before_expected_diagnostics(self) -> None:
        paths = [d.path for d in self.result.diagnostics]
        chk_indices = [i for i, p in enumerate(paths) if p.startswith("$.checks.")]
        exp_indices = [i for i, p in enumerate(paths) if p.startswith("$.expected.")]
        if chk_indices and exp_indices:
            self.assertLess(max(chk_indices), min(exp_indices))

    def test_expected_diagnostics_before_observation_context_diagnostics(
        self,
    ) -> None:
        paths = [d.path for d in self.result.diagnostics]
        exp_indices = [i for i, p in enumerate(paths) if p.startswith("$.expected.")]
        ctx_indices = [
            i for i, p in enumerate(paths)
            if p.startswith("$.observationContext.")
        ]
        if exp_indices and ctx_indices:
            self.assertLess(max(exp_indices), min(ctx_indices))

    def test_observe_components_before_observe_unknown(self) -> None:
        paths = [d.path for d in self.result.diagnostics]
        idx_comp = next(
            (i for i, p in enumerate(paths) if p == "$.observe.components"), None
        )
        idx_unknown = next(
            (i for i, p in enumerate(paths) if p == "$.observe.unknownObserve"), None
        )
        if idx_comp is not None and idx_unknown is not None:
            self.assertLess(idx_comp, idx_unknown)

    def test_expected_components_before_expected_parameters(self) -> None:
        paths = [d.path for d in self.result.diagnostics]
        idx_comp = next(
            (i for i, p in enumerate(paths) if "expected.components" in p), None
        )
        idx_param = next(
            (i for i, p in enumerate(paths) if "expected.parameters" in p), None
        )
        if idx_comp is not None and idx_param is not None:
            self.assertLess(idx_comp, idx_param)

    def test_expected_metadata_before_expected_references(self) -> None:
        paths = [d.path for d in self.result.diagnostics]
        idx_meta = next(
            (i for i, p in enumerate(paths) if "expected.metadata" in p), None
        )
        idx_ref = next(
            (i for i, p in enumerate(paths) if "expected.references" in p), None
        )
        if idx_meta is not None and idx_ref is not None:
            self.assertLess(idx_meta, idx_ref)

    def test_full_diagnostic_path_order_locked(self) -> None:
        paths = [d.path for d in self.result.diagnostics]
        self.assertEqual(paths, [
            "$.observe.components",
            "$.observe.unknownObserve",
            "$.checks.components.enabled",
            "$.checks.unknownChecks",
            "$.expected.components",
            "$.expected.parameters[0].id",
            "$.expected.metadata[0].id",
            "$.expected.metadata[0].ownerId",
            "$.expected.references[0].name",
            "$.expected.unknownExpected",
            "$.observationContext.parameters[0].groupName",
        ])


# ===========================================================================
# 13. Input non-mutation
# ===========================================================================


class InputNonMutationTests(unittest.TestCase):

    def test_compatible_payload_not_mutated(self) -> None:
        payload = _minimal_payload()
        before = copy.deepcopy(payload)
        validate(payload)
        self.assertEqual(payload, before)

    def test_incompatible_payload_not_mutated(self) -> None:
        payload = _mixed_incompatible_payload()
        before = copy.deepcopy(payload)
        validate(payload)
        self.assertEqual(payload, before)

    def test_strict_helper_compatible_not_mutated(self) -> None:
        payload = _minimal_payload()
        before = copy.deepcopy(payload)
        require(payload)
        self.assertEqual(payload, before)

    def test_strict_helper_incompatible_not_mutated(self) -> None:
        payload = {"observe": {"components": True}, "expected": {}, "checks": {}}
        before = copy.deepcopy(payload)
        try:
            require(payload)
        except CompatibilityError:
            pass
        self.assertEqual(payload, before)

    def test_repeated_calls_produce_identical_results(self) -> None:
        payload = _minimal_payload()
        a = validate(payload)
        b = validate(payload)
        self.assertEqual(a.compatible, b.compatible)
        self.assertEqual(a.diagnostics, b.diagnostics)
        self.assertEqual(a.supported_categories, b.supported_categories)


# ===========================================================================
# 14. Existing runtime behavior regression
# ===========================================================================


class RuntimeBehaviorRegressionTests(unittest.TestCase):

    def test_engine_verification_compat_module_still_importable(self) -> None:
        import parametron_freecad.observation.engine_verification_compat as evc
        self.assertTrue(callable(evc.observe_engine_compatible_requested_scope))

    def test_engine_verification_compat_still_emits_metadata_and_references(
        self,
    ) -> None:
        import parametron_freecad.observation.engine_verification_compat as evc

        class _ForbidDocument:
            @property
            def Objects(self):  # noqa: N802
                raise AssertionError("document.Objects must not be accessed")

        result = evc.observe_engine_compatible_requested_scope(
            _ForbidDocument(),
            {
                "observe": {"metadata": True, "references": True},
                "expected": {
                    "metadata": [{"key": "working_copy_sha256"}],
                    "references": [{"kind": "working_copy_path"}],
                },
            },
            working_copy_path="/test/model.FCStd",
            working_copy_sha256="a" * 64,
        )
        self.assertIn("metadata", result)
        self.assertIn("references", result)

    def test_new_classifier_does_not_emit_verification_decisions(self) -> None:
        result = validate(_minimal_payload())
        self.assertIsInstance(result, Compatibility)
        self.assertFalse(hasattr(result, "pass_fail"))
        self.assertFalse(hasattr(result, "decision"))
        self.assertFalse(hasattr(result, "verdict"))

    def test_new_classifier_does_not_compare_expected_values(self) -> None:
        base = {
            "observe": {"metadata": True},
            "expected": {
                "metadata": [{"id": "m", "key": "K", "ownerId": "O", "value": "A"}],
            },
            "checks": {},
        }
        alt = {
            "observe": {"metadata": True},
            "expected": {
                "metadata": [{"id": "m", "key": "K", "ownerId": "O", "value": "B"}],
            },
            "checks": {},
        }
        result_a = validate(base)
        result_b = validate(alt)
        self.assertEqual(result_a.compatible, result_b.compatible)
        self.assertEqual(result_a.diagnostics, result_b.diagnostics)

    def test_new_classifier_does_not_import_freecad(self) -> None:
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)


if __name__ == "__main__":
    unittest.main()
