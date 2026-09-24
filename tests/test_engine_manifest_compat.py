"""Tests for parametron_freecad.execution.engine_manifest_compat compatibility boundary."""

from __future__ import annotations

import builtins
import copy
import importlib
import inspect
import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import parametron_freecad.execution.engine_manifest_compat as emc
from parametron_freecad.execution.manifest_loader import LoadedManifest
from parametron_freecad.execution.manifest_validation import validate_export_manifest_v1

# Historical input retained only for the still-used rehearsal compatibility API.
# This is not part of the current Engine-generated input corpus.
LEGACY_EXAMPLE = '''
{
  "schemaVersion": "1.0",
  "planHash": "349e2081f19cd8676b56d12a1507e98b466bb0de342c8138766610a0964632f5",
  "adapter": "freecad",
  "product": {
    "id": "Box"
  },
  "inputs": {
    "sourceModel": "input/box.FCStd"
  },
  "values": {
    "height": 42,
    "length": 35,
    "width": 53
  },
  "parameterAssignments": [
    {
      "name": "length",
      "value": 35,
      "type": "number",
      "unit": "mm"
    },
    {
      "name": "width",
      "value": 53,
      "type": "number",
      "unit": "mm"
    },
    {
      "name": "height",
      "value": 42,
      "type": "number",
      "unit": "mm"
    }
  ],
  "outputs": [
    {
      "type": "step",
      "filename": "Box.step",
      "object": "Body"
    }
  ]
}
'''


# ---------------------------------------------------------------------------
# Canonical payload helpers
# ---------------------------------------------------------------------------


def _internal_manifest() -> dict:
    return {
        "schemaVersion": "1.0",
        "sourceDocument": "box.FCStd",
        "parameterAssignments": [
            {"target": "Body.Length", "value": 35, "valueKind": "number"},
        ],
        "outputs": [
            {"id": "Body", "format": "step", "path": "Box.step"},
        ],
    }


def _engine_manifest_no_params() -> dict:
    return {
        "schemaVersion": "1.0",
        "planHash": "example-plan-hash",
        "adapter": "freecad",
        "product": {"id": "Box"},
        "inputs": {"sourceModel": "input/box.FCStd"},
        "values": {},
        "parameterAssignments": [],
        "outputs": [
            {"type": "step", "filename": "Box.step", "object": "Body"},
        ],
    }


def _engine_manifest_with_params() -> dict:
    return {
        "schemaVersion": "1.0",
        "planHash": "349e2081f19cd8676b56d12a1507e98b466bb0de342c8138766610a0964632f5",
        "adapter": "freecad",
        "product": {"id": "Box"},
        "inputs": {"sourceModel": "input/box.FCStd"},
        "values": {"height": 42, "length": 35, "width": 53},
        "parameterAssignments": [
            {"name": "length", "value": 35, "type": "number", "unit": "mm"},
            {"name": "width", "value": 53, "type": "number", "unit": "mm"},
            {"name": "height", "value": 42, "type": "number", "unit": "mm"},
        ],
        "outputs": [
            {"type": "step", "filename": "Box.step", "object": "Body"},
        ],
    }


# ---------------------------------------------------------------------------
# 1. Import safety
# ---------------------------------------------------------------------------


class ImportSafetyTests(unittest.TestCase):
    def test_module_imports_without_freecad_modules(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        module_name = "parametron_freecad.execution.engine_manifest_compat"
        # Restore sys.modules and the parent package attribute after the test so
        # that downstream tests importing from this module see a consistent class
        # identity. `import A.B.C as name` traverses package attributes, so both
        # sys.modules and the parent attribute must be restored.
        saved_module = sys.modules.get(module_name)
        for name in [module_name, *guarded_names]:
            sys.modules.pop(name, None)

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in guarded_names:
                raise AssertionError(f"{name} must not be imported at module load time")
            return original_import(name, globals, locals, fromlist, level)

        try:
            with mock.patch("builtins.__import__", side_effect=guarded_import):
                module = importlib.import_module(module_name)
        finally:
            parent_pkg = sys.modules.get("parametron_freecad.execution")
            if saved_module is not None:
                sys.modules[module_name] = saved_module
                if parent_pkg is not None:
                    parent_pkg.engine_manifest_compat = saved_module
            else:
                sys.modules.pop(module_name, None)

        self.assertIsInstance(module, types.ModuleType)
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)

    def test_no_freecad_in_sys_modules_after_import(self) -> None:
        import parametron_freecad.execution.engine_manifest_compat  # noqa: F401

        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)

    def test_module_exposes_error_classes_in_all(self) -> None:
        for name in (
            "EngineManifestCompatibilityError",
            "EngineManifestUnsupportedParameterTargetError",
            "EngineManifestUnsupportedOutputTargetError",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(emc, name))
                self.assertIn(name, emc.__all__)

    def test_module_exposes_shape_constants_in_all(self) -> None:
        for name in (
            "MANIFEST_SHAPE_FREECAD_INTERNAL",
            "MANIFEST_SHAPE_ENGINE_GENERATED",
            "MANIFEST_SHAPE_UNKNOWN",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(emc, name))
                self.assertIn(name, emc.__all__)

    def test_module_exposes_public_helpers_in_all(self) -> None:
        for name in (
            "detect_export_manifest_shape",
            "normalize_engine_export_manifest_v1",
            "normalize_loaded_export_manifest_v1",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(emc, name))
                self.assertIn(name, emc.__all__)

    def test_unsupported_parameter_target_error_is_subclass_of_compatibility_error(
        self,
    ) -> None:
        self.assertTrue(
            issubclass(
                emc.EngineManifestUnsupportedParameterTargetError,
                emc.EngineManifestCompatibilityError,
            )
        )

    def test_unsupported_output_target_error_is_subclass_of_compatibility_error(
        self,
    ) -> None:
        self.assertTrue(
            issubclass(
                emc.EngineManifestUnsupportedOutputTargetError,
                emc.EngineManifestCompatibilityError,
            )
        )

    def test_compatibility_error_is_subclass_of_value_error(self) -> None:
        self.assertTrue(issubclass(emc.EngineManifestCompatibilityError, ValueError))

    def test_module_source_does_not_import_freecad(self) -> None:
        source = inspect.getsource(emc)
        self.assertNotIn("import FreeCAD", source)
        self.assertNotIn("import FreeCADGui", source)


# ---------------------------------------------------------------------------
# 2. Shape classification
# ---------------------------------------------------------------------------


class ShapeClassificationTests(unittest.TestCase):
    def test_internal_manifest_with_source_document_is_internal(self) -> None:
        data = {"schemaVersion": "1.0", "sourceDocument": "box.FCStd"}
        self.assertEqual(
            emc.detect_export_manifest_shape(data),
            emc.MANIFEST_SHAPE_FREECAD_INTERNAL,
        )

    def test_internal_manifest_with_target_in_assignments_is_internal(self) -> None:
        data = {
            "parameterAssignments": [
                {"target": "Body.Length", "value": 10, "valueKind": "scalar"}
            ]
        }
        self.assertEqual(
            emc.detect_export_manifest_shape(data),
            emc.MANIFEST_SHAPE_FREECAD_INTERNAL,
        )

    def test_internal_manifest_with_id_in_outputs_is_internal(self) -> None:
        data = {"outputs": [{"id": "Body", "format": "step", "path": "Box.step"}]}
        self.assertEqual(
            emc.detect_export_manifest_shape(data),
            emc.MANIFEST_SHAPE_FREECAD_INTERNAL,
        )

    def test_internal_manifest_with_format_in_outputs_is_internal(self) -> None:
        data = {"outputs": [{"format": "step", "id": "X", "path": "X.step"}]}
        self.assertEqual(
            emc.detect_export_manifest_shape(data),
            emc.MANIFEST_SHAPE_FREECAD_INTERNAL,
        )

    def test_internal_manifest_with_path_in_outputs_is_internal(self) -> None:
        data = {"outputs": [{"path": "Box.step", "id": "X", "format": "step"}]}
        self.assertEqual(
            emc.detect_export_manifest_shape(data),
            emc.MANIFEST_SHAPE_FREECAD_INTERNAL,
        )

    def test_full_internal_manifest_is_internal(self) -> None:
        self.assertEqual(
            emc.detect_export_manifest_shape(_internal_manifest()),
            emc.MANIFEST_SHAPE_FREECAD_INTERNAL,
        )

    def test_engine_manifest_with_plan_hash_is_engine(self) -> None:
        self.assertEqual(
            emc.detect_export_manifest_shape({"planHash": "abc123"}),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_engine_manifest_with_adapter_is_engine(self) -> None:
        self.assertEqual(
            emc.detect_export_manifest_shape({"adapter": "freecad"}),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_engine_manifest_with_product_is_engine(self) -> None:
        self.assertEqual(
            emc.detect_export_manifest_shape({"product": {"id": "Box"}}),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_engine_manifest_with_values_is_engine(self) -> None:
        self.assertEqual(
            emc.detect_export_manifest_shape({"values": {"length": 35}}),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_engine_manifest_with_inputs_is_engine(self) -> None:
        self.assertEqual(
            emc.detect_export_manifest_shape({"inputs": {"sourceModel": "box.FCStd"}}),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_engine_manifest_with_name_in_assignments_is_engine(self) -> None:
        data = {
            "parameterAssignments": [
                {"name": "length", "value": 35, "type": "number", "unit": "mm"}
            ]
        }
        self.assertEqual(
            emc.detect_export_manifest_shape(data),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_engine_manifest_with_unit_in_assignments_is_engine(self) -> None:
        data = {"parameterAssignments": [{"name": "width", "value": 53, "unit": "mm"}]}
        self.assertEqual(
            emc.detect_export_manifest_shape(data),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_engine_manifest_with_type_in_outputs_is_engine(self) -> None:
        data = {"outputs": [{"type": "step", "filename": "Box.step", "object": "Body"}]}
        self.assertEqual(
            emc.detect_export_manifest_shape(data),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_engine_manifest_with_filename_in_outputs_is_engine(self) -> None:
        data = {"outputs": [{"filename": "Box.step", "type": "step", "object": "Body"}]}
        self.assertEqual(
            emc.detect_export_manifest_shape(data),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_full_engine_manifest_no_params_is_engine(self) -> None:
        self.assertEqual(
            emc.detect_export_manifest_shape(_engine_manifest_no_params()),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_full_engine_manifest_with_params_is_engine(self) -> None:
        self.assertEqual(
            emc.detect_export_manifest_shape(_engine_manifest_with_params()),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_empty_manifest_is_unknown(self) -> None:
        self.assertEqual(
            emc.detect_export_manifest_shape({}),
            emc.MANIFEST_SHAPE_UNKNOWN,
        )

    def test_only_schema_version_is_unknown(self) -> None:
        self.assertEqual(
            emc.detect_export_manifest_shape({"schemaVersion": "1.0"}),
            emc.MANIFEST_SHAPE_UNKNOWN,
        )

    def test_classification_does_not_mutate_input_mapping(self) -> None:
        data = {"adapter": "freecad", "inputs": {"sourceModel": "box.FCStd"}}
        original = copy.deepcopy(data)
        emc.detect_export_manifest_shape(data)
        self.assertEqual(data, original)

    def test_internal_manifest_is_not_classified_as_engine(self) -> None:
        self.assertNotEqual(
            emc.detect_export_manifest_shape(_internal_manifest()),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_engine_manifest_is_not_classified_as_internal(self) -> None:
        self.assertNotEqual(
            emc.detect_export_manifest_shape(_engine_manifest_no_params()),
            emc.MANIFEST_SHAPE_FREECAD_INTERNAL,
        )


# ---------------------------------------------------------------------------
# 3. Internal manifest pass-through preservation
# ---------------------------------------------------------------------------


class InternalManifestPassThroughTests(unittest.TestCase):
    def _loaded(self, data: dict | None = None) -> LoadedManifest:
        return LoadedManifest(
            path=Path("/tmp/export_manifest_v1.json"),
            data=data if data is not None else _internal_manifest(),
        )

    def test_internal_manifest_returned_as_same_object(self) -> None:
        loaded = self._loaded()
        result = emc.normalize_loaded_export_manifest_v1(loaded)
        self.assertIs(result, loaded)

    def test_internal_manifest_no_engine_fields_in_result(self) -> None:
        loaded = self._loaded()
        result = emc.normalize_loaded_export_manifest_v1(loaded)
        for engine_field in ("planHash", "adapter", "product", "values", "inputs"):
            self.assertNotIn(engine_field, result.data)

    def test_internal_manifest_targets_preserved_exactly(self) -> None:
        loaded = self._loaded()
        result = emc.normalize_loaded_export_manifest_v1(loaded)
        self.assertEqual(
            result.data["parameterAssignments"][0]["target"], "Body.Length"
        )

    def test_internal_manifest_output_fields_preserved_exactly(self) -> None:
        loaded = self._loaded()
        result = emc.normalize_loaded_export_manifest_v1(loaded)
        output = result.data["outputs"][0]
        self.assertEqual(output["id"], "Body")
        self.assertEqual(output["format"], "step")
        self.assertEqual(output["path"], "Box.step")

    def test_internal_manifest_passes_validate_export_manifest_v1(self) -> None:
        loaded = self._loaded()
        result = emc.normalize_loaded_export_manifest_v1(loaded)
        validation = validate_export_manifest_v1(result.data)
        self.assertTrue(validation.is_valid, validation.diagnostics)

    def test_internal_manifest_input_not_mutated(self) -> None:
        data = _internal_manifest()
        original = copy.deepcopy(data)
        emc.normalize_loaded_export_manifest_v1(self._loaded(data))
        self.assertEqual(data, original)

    def test_unknown_manifest_returned_as_same_object(self) -> None:
        data = {"schemaVersion": "1.0"}
        loaded = LoadedManifest(path=Path("/tmp/manifest.json"), data=data)
        result = emc.normalize_loaded_export_manifest_v1(loaded)
        self.assertIs(result, loaded)

    def test_empty_manifest_returned_as_same_object(self) -> None:
        loaded = self._loaded({})
        result = emc.normalize_loaded_export_manifest_v1(loaded)
        self.assertIs(result, loaded)


# ---------------------------------------------------------------------------
# 4. Engine manifest deterministic normalization without parameters
# ---------------------------------------------------------------------------


class EngineManifestNoParameterNormalizationTests(unittest.TestCase):
    def _normalized(self) -> dict:
        return emc.normalize_engine_export_manifest_v1(_engine_manifest_no_params())

    def test_source_document_from_inputs_source_model(self) -> None:
        self.assertEqual(self._normalized()["sourceDocument"], "input/box.FCStd")

    def test_schema_version_preserved(self) -> None:
        self.assertEqual(self._normalized()["schemaVersion"], "1.0")

    def test_parameter_assignments_empty_list(self) -> None:
        self.assertEqual(self._normalized()["parameterAssignments"], [])

    def test_output_id_from_object(self) -> None:
        self.assertEqual(self._normalized()["outputs"][0]["id"], "Body")

    def test_output_format_from_type(self) -> None:
        self.assertEqual(self._normalized()["outputs"][0]["format"], "step")

    def test_output_path_from_filename(self) -> None:
        self.assertEqual(self._normalized()["outputs"][0]["path"], "Box.step")

    def test_engine_metadata_not_leaked_in_result(self) -> None:
        result = self._normalized()
        for leaked_field in ("planHash", "adapter", "product", "values", "inputs"):
            self.assertNotIn(leaked_field, result, f"Engine field leaked: {leaked_field}")

    def test_normalized_payload_passes_validate_export_manifest_v1(self) -> None:
        result = self._normalized()
        validation = validate_export_manifest_v1(result)
        self.assertTrue(validation.is_valid, validation.diagnostics)

    def test_output_order_preserved(self) -> None:
        data = {
            **_engine_manifest_no_params(),
            "outputs": [
                {"type": "step", "filename": "Alpha.step", "object": "Alpha"},
                {"type": "step", "filename": "Beta.step", "object": "Beta"},
            ],
        }
        result = emc.normalize_engine_export_manifest_v1(data)
        self.assertEqual(result["outputs"][0]["path"], "Alpha.step")
        self.assertEqual(result["outputs"][1]["path"], "Beta.step")

    def test_input_mapping_not_mutated(self) -> None:
        data = _engine_manifest_no_params()
        original = copy.deepcopy(data)
        emc.normalize_engine_export_manifest_v1(data)
        self.assertEqual(data, original)

    def test_normalize_loaded_manifest_returns_new_loaded_manifest_for_engine_shape(
        self,
    ) -> None:
        data = _engine_manifest_no_params()
        path = Path("/tmp/export_manifest.v1.json")
        loaded = LoadedManifest(path=path, data=data)
        result = emc.normalize_loaded_export_manifest_v1(loaded)
        self.assertIsNot(result, loaded)
        self.assertEqual(result.path, path)

    def test_normalize_loaded_manifest_result_has_internal_shape_fields(self) -> None:
        loaded = LoadedManifest(
            path=Path("/tmp/manifest.json"), data=_engine_manifest_no_params()
        )
        result = emc.normalize_loaded_export_manifest_v1(loaded)
        self.assertIn("sourceDocument", result.data)
        self.assertIn("parameterAssignments", result.data)
        self.assertIn("outputs", result.data)

    def test_normalize_loaded_manifest_result_has_no_engine_metadata_fields(
        self,
    ) -> None:
        loaded = LoadedManifest(
            path=Path("/tmp/manifest.json"), data=_engine_manifest_no_params()
        )
        result = emc.normalize_loaded_export_manifest_v1(loaded)
        for field in ("planHash", "adapter", "product", "values", "inputs"):
            self.assertNotIn(field, result.data)

    def test_normalization_does_not_read_files(self) -> None:
        data = _engine_manifest_no_params()
        with mock.patch(
            "builtins.open",
            side_effect=AssertionError("normalization must not open files"),
        ):
            result = emc.normalize_engine_export_manifest_v1(data)
        self.assertIn("sourceDocument", result)

    def test_normalization_does_not_write_files(self) -> None:
        data = _engine_manifest_no_params()
        with mock.patch(
            "builtins.open",
            side_effect=AssertionError("normalization must not open files"),
        ):
            emc.normalize_engine_export_manifest_v1(data)


# ---------------------------------------------------------------------------
# 5. Engine manifest name-only parameter rejection
# ---------------------------------------------------------------------------


class EngineParameterRejectionTests(unittest.TestCase):
    def _engine_single_param(self) -> dict:
        return {
            "schemaVersion": "1.0",
            "planHash": "test-hash",
            "adapter": "freecad",
            "product": {"id": "Box"},
            "inputs": {"sourceModel": "input/box.FCStd"},
            "values": {"length": 35},
            "parameterAssignments": [
                {"name": "length", "value": 35, "type": "number", "unit": "mm"}
            ],
            "outputs": [{"type": "step", "filename": "Box.step", "object": "Body"}],
        }

    def test_name_only_parameter_raises_unsupported_parameter_target_error(
        self,
    ) -> None:
        with self.assertRaises(emc.EngineManifestUnsupportedParameterTargetError):
            emc.normalize_engine_export_manifest_v1(self._engine_single_param())

    def test_error_is_subclass_of_compatibility_error(self) -> None:
        with self.assertRaises(emc.EngineManifestCompatibilityError):
            emc.normalize_engine_export_manifest_v1(self._engine_single_param())

    def test_error_message_includes_parameter_assignments_index(self) -> None:
        with self.assertRaises(
            emc.EngineManifestUnsupportedParameterTargetError
        ) as excinfo:
            emc.normalize_engine_export_manifest_v1(self._engine_single_param())
        self.assertIn("parameterAssignments[0]", str(excinfo.exception))

    def test_error_message_includes_parameter_name_field(self) -> None:
        with self.assertRaises(
            emc.EngineManifestUnsupportedParameterTargetError
        ) as excinfo:
            emc.normalize_engine_export_manifest_v1(self._engine_single_param())
        self.assertIn("name", str(excinfo.exception))

    def test_error_message_includes_parameter_name_value(self) -> None:
        with self.assertRaises(
            emc.EngineManifestUnsupportedParameterTargetError
        ) as excinfo:
            emc.normalize_engine_export_manifest_v1(self._engine_single_param())
        self.assertIn("length", str(excinfo.exception))

    def test_error_message_references_freecad_target_requirement(self) -> None:
        with self.assertRaises(
            emc.EngineManifestUnsupportedParameterTargetError
        ) as excinfo:
            emc.normalize_engine_export_manifest_v1(self._engine_single_param())
        self.assertIn("FreeCAD", str(excinfo.exception))

    def test_multiple_params_fail_at_first_index(self) -> None:
        data = {
            **self._engine_single_param(),
            "parameterAssignments": [
                {"name": "length", "value": 35, "type": "number", "unit": "mm"},
                {"name": "width", "value": 53, "type": "number", "unit": "mm"},
            ],
        }
        with self.assertRaises(
            emc.EngineManifestUnsupportedParameterTargetError
        ) as excinfo:
            emc.normalize_engine_export_manifest_v1(data)
        self.assertIn("parameterAssignments[0]", str(excinfo.exception))

    def test_input_mapping_not_mutated_on_rejection(self) -> None:
        data = self._engine_single_param()
        original = copy.deepcopy(data)
        try:
            emc.normalize_engine_export_manifest_v1(data)
        except emc.EngineManifestUnsupportedParameterTargetError:
            pass
        self.assertEqual(data, original)

    def test_no_result_returned_on_rejection(self) -> None:
        data = self._engine_single_param()
        result = None
        try:
            result = emc.normalize_engine_export_manifest_v1(data)
        except emc.EngineManifestUnsupportedParameterTargetError:
            pass
        self.assertIsNone(result)

    def test_full_fixture_manifest_with_params_raises(self) -> None:
        data = _engine_manifest_with_params()
        with self.assertRaises(emc.EngineManifestUnsupportedParameterTargetError):
            emc.normalize_engine_export_manifest_v1(data)


# ---------------------------------------------------------------------------
# 6. Engine output normalization boundaries
# ---------------------------------------------------------------------------


class EngineOutputNormalizationTests(unittest.TestCase):
    def _with_output(self, output: dict) -> dict:
        return {
            "schemaVersion": "1.0",
            "planHash": "test-hash",
            "adapter": "freecad",
            "product": {"id": "Box"},
            "inputs": {"sourceModel": "input/box.FCStd"},
            "values": {},
            "parameterAssignments": [],
            "outputs": [output],
        }

    def _normalize_output(self, output: dict) -> dict:
        result = emc.normalize_engine_export_manifest_v1(self._with_output(output))
        return result["outputs"][0]

    def test_step_type_normalizes_to_format_step(self) -> None:
        out = self._normalize_output(
            {"type": "step", "filename": "Box.step", "object": "Body"}
        )
        self.assertEqual(out["format"], "step")

    def test_filename_normalizes_to_path(self) -> None:
        out = self._normalize_output(
            {"type": "step", "filename": "Box.step", "object": "Body"}
        )
        self.assertEqual(out["path"], "Box.step")

    def test_object_normalizes_to_id(self) -> None:
        out = self._normalize_output(
            {"type": "step", "filename": "Box.step", "object": "Body"}
        )
        self.assertEqual(out["id"], "Body")

    def test_missing_type_raises_unsupported_output_target_error(self) -> None:
        with self.assertRaises(emc.EngineManifestUnsupportedOutputTargetError):
            emc.normalize_engine_export_manifest_v1(
                self._with_output({"filename": "Box.step", "object": "Body"})
            )

    def test_missing_filename_raises_compatibility_error(self) -> None:
        with self.assertRaises(emc.EngineManifestCompatibilityError):
            emc.normalize_engine_export_manifest_v1(
                self._with_output({"type": "step", "object": "Body"})
            )

    def test_missing_object_raises_unsupported_output_target_error(self) -> None:
        with self.assertRaises(emc.EngineManifestUnsupportedOutputTargetError):
            emc.normalize_engine_export_manifest_v1(
                self._with_output({"type": "step", "filename": "Box.step"})
            )

    def test_non_string_type_raises_unsupported_output_target_error(self) -> None:
        with self.assertRaises(emc.EngineManifestUnsupportedOutputTargetError):
            emc.normalize_engine_export_manifest_v1(
                self._with_output({"type": 42, "filename": "Box.step", "object": "Body"})
            )

    def test_non_string_filename_raises_compatibility_error(self) -> None:
        with self.assertRaises(emc.EngineManifestCompatibilityError):
            emc.normalize_engine_export_manifest_v1(
                self._with_output({"type": "step", "filename": 42, "object": "Body"})
            )

    def test_non_string_object_raises_unsupported_output_target_error(self) -> None:
        with self.assertRaises(emc.EngineManifestUnsupportedOutputTargetError):
            emc.normalize_engine_export_manifest_v1(
                self._with_output(
                    {"type": "step", "filename": "Box.step", "object": 42}
                )
            )

    def test_unsupported_type_iges_raises_unsupported_output_target_error(self) -> None:
        with self.assertRaises(emc.EngineManifestUnsupportedOutputTargetError):
            emc.normalize_engine_export_manifest_v1(
                self._with_output(
                    {"type": "iges", "filename": "Box.igs", "object": "Body"}
                )
            )

    def test_unsupported_type_obj_raises_unsupported_output_target_error(self) -> None:
        with self.assertRaises(emc.EngineManifestUnsupportedOutputTargetError):
            emc.normalize_engine_export_manifest_v1(
                self._with_output(
                    {"type": "obj", "filename": "Box.obj", "object": "Body"}
                )
            )

    def test_empty_filename_raises_compatibility_error(self) -> None:
        with self.assertRaises(emc.EngineManifestCompatibilityError):
            emc.normalize_engine_export_manifest_v1(
                self._with_output(
                    {"type": "step", "filename": "   ", "object": "Body"}
                )
            )

    def test_empty_object_raises_unsupported_output_target_error(self) -> None:
        with self.assertRaises(emc.EngineManifestUnsupportedOutputTargetError):
            emc.normalize_engine_export_manifest_v1(
                self._with_output(
                    {"type": "step", "filename": "Box.step", "object": "   "}
                )
            )


# ---------------------------------------------------------------------------
# 9. Sanitized fixture shape validation
# ---------------------------------------------------------------------------


class HistoricalCompatibilityExampleTests(unittest.TestCase):
    def _load_fixture(self) -> dict:
        return json.loads(LEGACY_EXAMPLE)

    def test_historical_example_is_available(self) -> None:
        self.assertTrue(LEGACY_EXAMPLE)

    def test_fixture_is_valid_json_object(self) -> None:
        data = self._load_fixture()
        self.assertIsInstance(data, dict)

    def test_fixture_has_engine_root_fields(self) -> None:
        data = self._load_fixture()
        for field in ("schemaVersion", "planHash", "adapter", "product", "inputs", "values"):
            self.assertIn(field, data, f"Missing fixture field: {field}")

    def test_fixture_has_parameter_assignments_and_outputs(self) -> None:
        data = self._load_fixture()
        self.assertIn("parameterAssignments", data)
        self.assertIn("outputs", data)

    def test_fixture_is_classified_as_engine_generated(self) -> None:
        data = self._load_fixture()
        self.assertEqual(
            emc.detect_export_manifest_shape(data),
            emc.MANIFEST_SHAPE_ENGINE_GENERATED,
        )

    def test_fixture_source_model_is_not_an_absolute_local_path(self) -> None:
        data = self._load_fixture()
        source_model = data["inputs"]["sourceModel"]
        self.assertFalse(
            source_model.startswith("/home/"),
            f"Fixture must not contain a local absolute path; got: {source_model!r}",
        )

    def test_fixture_has_representative_parameter_names(self) -> None:
        data = self._load_fixture()
        names = {a["name"] for a in data["parameterAssignments"]}
        self.assertIn("length", names)
        self.assertIn("width", names)
        self.assertIn("height", names)

    def test_fixture_output_references_body_and_step(self) -> None:
        data = self._load_fixture()
        output = data["outputs"][0]
        self.assertEqual(output["object"], "Body")
        self.assertEqual(output["type"], "step")
        self.assertEqual(output["filename"], "Box.step")

    def test_fixture_manifest_raises_on_normalization_due_to_name_only_params(
        self,
    ) -> None:
        data = self._load_fixture()
        with self.assertRaises(emc.EngineManifestUnsupportedParameterTargetError):
            emc.normalize_engine_export_manifest_v1(data)

    def test_fixture_with_params_removed_normalizes_correctly(self) -> None:
        data = self._load_fixture()
        data_no_params = {**data, "parameterAssignments": []}
        result = emc.normalize_engine_export_manifest_v1(data_no_params)
        validation = validate_export_manifest_v1(result)
        self.assertTrue(validation.is_valid, validation.diagnostics)
        self.assertEqual(result["sourceDocument"], data["inputs"]["sourceModel"])


# ---------------------------------------------------------------------------
# 10. Negative scope guards
# ---------------------------------------------------------------------------


class NegativeScopeGuardTests(unittest.TestCase):
    """Prohibited behaviors must be absent from the compatibility boundary."""

    def _single_name_param_data(self) -> dict:
        return {
            "schemaVersion": "1.0",
            "adapter": "freecad",
            "inputs": {"sourceModel": "input/box.FCStd"},
            "values": {},
            "parameterAssignments": [
                {"name": "length", "value": 35, "type": "number", "unit": "mm"}
            ],
            "outputs": [{"type": "step", "filename": "Box.step", "object": "Body"}],
        }

    def test_name_length_not_converted_to_body_length_target(self) -> None:
        data = self._single_name_param_data()
        try:
            result = emc.normalize_engine_export_manifest_v1(data)
        except emc.EngineManifestUnsupportedParameterTargetError:
            return  # correct: rejected without target inference
        for assignment in result.get("parameterAssignments", []):
            target = assignment.get("target", "")
            self.assertNotIn("Body.length", target)
            self.assertNotIn("Body.Length", target)
            self.assertNotIn("Spreadsheet.length", target)
        self.fail("normalization must not produce a result for name-only params")

    def test_name_length_not_converted_to_spreadsheet_length(self) -> None:
        data = self._single_name_param_data()
        try:
            result = emc.normalize_engine_export_manifest_v1(data)
        except emc.EngineManifestUnsupportedParameterTargetError:
            return
        for assignment in result.get("parameterAssignments", []):
            self.assertNotIn("Spreadsheet", assignment.get("target", ""))
        self.fail("must not succeed with name-only params")

    def test_unit_mm_does_not_trigger_unit_conversion(self) -> None:
        # Rejection happens before any value processing; no conversion is attempted.
        data = self._single_name_param_data()
        try:
            result = emc.normalize_engine_export_manifest_v1(data)
        except emc.EngineManifestUnsupportedParameterTargetError:
            return
        for assignment in result.get("parameterAssignments", []):
            self.assertEqual(
                assignment.get("value"),
                35,
                "unit: 'mm' must not convert the scalar value",
            )

    def test_type_number_does_not_trigger_value_type_coercion(self) -> None:
        # type: "number" metadata must not alter the JSON scalar value.
        data = self._single_name_param_data()
        try:
            emc.normalize_engine_export_manifest_v1(data)
        except emc.EngineManifestUnsupportedParameterTargetError:
            return  # correct: rejected without value coercion

    def test_no_freecad_in_sys_modules_after_normalization(self) -> None:
        emc.normalize_engine_export_manifest_v1(_engine_manifest_no_params())
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)

    def test_no_freecad_in_sys_modules_after_rejection(self) -> None:
        try:
            emc.normalize_engine_export_manifest_v1(_engine_manifest_with_params())
        except emc.EngineManifestUnsupportedParameterTargetError:
            pass
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)

    def test_rejection_error_message_does_not_contain_invented_target(self) -> None:
        data = self._single_name_param_data()
        with self.assertRaises(
            emc.EngineManifestUnsupportedParameterTargetError
        ) as excinfo:
            emc.normalize_engine_export_manifest_v1(data)
        msg = str(excinfo.exception)
        self.assertNotIn("Body.length", msg)
        self.assertNotIn("Body.Length", msg)
        self.assertNotIn("Spreadsheet.length", msg)

    def test_normalization_does_not_access_label_lookup(self) -> None:
        # The module must not call any FreeCAD Label lookup in its normalization path.
        source = inspect.getsource(emc)
        self.assertNotIn("getObjectsByLabel", source)
        self.assertNotIn("findObjects", source)

    def test_normalization_does_not_access_document_objects(self) -> None:
        # The module must not access document.Objects.
        source = inspect.getsource(emc)
        self.assertNotIn(".Objects", source)

    def test_existing_validate_export_manifest_v1_is_unchanged_authority(
        self,
    ) -> None:
        # Confirm the existing validator still works as the final authority for
        # normalized internal payloads.
        normalized = emc.normalize_engine_export_manifest_v1(_engine_manifest_no_params())
        result = validate_export_manifest_v1(normalized)
        self.assertTrue(result.is_valid)


if __name__ == "__main__":
    unittest.main()
