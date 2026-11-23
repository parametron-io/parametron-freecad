"""Import-safety tests for the GUI-free capture core."""

from __future__ import annotations

import ast
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import parametron_freecad.capture as capture
from parametron_freecad.capture import (
    CaptureConfirmationRequiredError,
    CaptureContractError,
    CaptureDecisionError,
    CaptureDiscoveryDocumentError,
    CaptureDiscoveryError,
    CaptureDiscoveryInspectionError,
    CaptureDriftError,
    CaptureError,
    CaptureFingerprintError,
    CaptureIdPolicyError,
    CaptureNamePolicyError,
    CaptureOrchestrationError,
    CapturePreflightError,
    CaptureProjectError,
    CaptureSourceError,
    CaptureUnsavedDocumentError,
    CaptureWriteError,
    SemanticMapConfirmationRequiredError,
    SemanticMapContractError,
    SemanticMapDecodeError,
    SemanticMapError,
    SemanticMapIdentityError,
    SemanticMapSelectionError,
    SemanticMapWriteError,
)

_GUARDED_ROOTS = {"FreeCAD", "FreeCADGui", "Part", "freecad"}
_CAPTURE_PACKAGE_DIR = Path(capture.__file__).resolve().parent


class CaptureImportSafetyTests(unittest.TestCase):
    def test_importing_capture_does_not_import_freecad(self) -> None:
        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            root = name.split(".", 1)[0]
            if root in _GUARDED_ROOTS:
                raise AssertionError(f"{name} must not be imported")
            return real_import(name, *args, **kwargs)

        for module_name in tuple(sys.modules):
            if module_name == "parametron_freecad.capture" or module_name.startswith(
                "parametron_freecad.capture."
            ):
                sys.modules.pop(module_name, None)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module("parametron_freecad.capture")

        self.assertIsInstance(module, types.ModuleType)
        for guarded in _GUARDED_ROOTS:
            self.assertNotIn(guarded, sys.modules)

    def test_capture_sources_do_not_import_freecad_modules(self) -> None:
        for source_path in sorted(_CAPTURE_PACKAGE_DIR.glob("*.py")):
            with self.subTest(source=source_path.name):
                tree = ast.parse(
                    source_path.read_text(encoding="utf-8"),
                    filename=str(source_path),
                )
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertNotIn(
                                alias.name.split(".", 1)[0],
                                _GUARDED_ROOTS,
                                f"{source_path.name} imports {alias.name}",
                            )
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        self.assertNotIn(
                            node.module.split(".", 1)[0],
                            _GUARDED_ROOTS,
                            f"{source_path.name} imports from {node.module}",
                        )

    def test_error_classes_are_distinct_and_typed(self) -> None:
        self.assertTrue(issubclass(CaptureContractError, CaptureError))
        self.assertTrue(issubclass(CaptureNamePolicyError, CaptureError))
        self.assertTrue(issubclass(CaptureIdPolicyError, CaptureError))
        self.assertTrue(issubclass(CaptureDiscoveryError, ValueError))
        self.assertTrue(
            issubclass(CaptureDiscoveryDocumentError, CaptureDiscoveryError)
        )
        self.assertTrue(
            issubclass(CaptureDiscoveryInspectionError, CaptureDiscoveryError)
        )
        self.assertFalse(issubclass(CaptureWriteError, CaptureError))
        self.assertTrue(issubclass(CaptureWriteError, OSError))
        self.assertTrue(issubclass(CaptureOrchestrationError, ValueError))
        self.assertTrue(issubclass(CaptureProjectError, CaptureOrchestrationError))
        self.assertTrue(issubclass(CaptureSourceError, CaptureOrchestrationError))
        self.assertTrue(issubclass(CaptureUnsavedDocumentError, CaptureSourceError))
        self.assertTrue(issubclass(CaptureDecisionError, CaptureOrchestrationError))
        self.assertTrue(issubclass(CaptureDriftError, CaptureOrchestrationError))
        self.assertTrue(
            issubclass(
                CaptureConfirmationRequiredError,
                CaptureOrchestrationError,
            )
        )
        self.assertTrue(issubclass(CapturePreflightError, CaptureOrchestrationError))
        self.assertFalse(issubclass(CaptureFingerprintError, CaptureOrchestrationError))
        self.assertTrue(issubclass(CaptureFingerprintError, OSError))
        self.assertTrue(issubclass(SemanticMapError, ValueError))
        self.assertTrue(issubclass(SemanticMapContractError, SemanticMapError))
        self.assertTrue(issubclass(SemanticMapSelectionError, SemanticMapError))
        self.assertTrue(issubclass(SemanticMapDecodeError, SemanticMapError))
        self.assertTrue(issubclass(SemanticMapIdentityError, SemanticMapError))
        self.assertTrue(
            issubclass(
                SemanticMapConfirmationRequiredError,
                SemanticMapError,
            )
        )
        self.assertFalse(issubclass(SemanticMapWriteError, SemanticMapError))
        self.assertTrue(issubclass(SemanticMapWriteError, OSError))

    def test_public_surface_is_available(self) -> None:
        for name in (
            "CaptureContractError",
            "CaptureConfirmationRequiredError",
            "CaptureDecisionError",
            "CaptureDecisions",
            "CaptureDiscovery",
            "CaptureDiscoveryDocumentError",
            "CaptureDiscoveryError",
            "CaptureDiscoveryInspectionError",
            "CaptureDocument",
            "CaptureDriftEntry",
            "CaptureDriftError",
            "CaptureError",
            "CaptureFingerprintError",
            "CaptureIdPolicyError",
            "CaptureNamePolicyError",
            "CaptureOrchestrationError",
            "CaptureOutputPlan",
            "CapturePreflightError",
            "CaptureProjectContext",
            "CaptureProjectError",
            "CaptureSourceError",
            "CaptureUnsavedDocumentError",
            "CaptureWriteError",
            "CaptureWriteSummary",
            "ComponentCandidate",
            "ComponentDecision",
            "DiscoveryDiagnostic",
            "DocumentEvidence",
            "ENGINE_BIN_ENVIRONMENT",
            "EnginePreflightResult",
            "EnginePreflightRunner",
            "FINGERPRINT_PREFIX",
            "FeatureCandidate",
            "FeatureDecision",
            "MappingDiffEntry",
            "MetadataCandidate",
            "MetadataDecision",
            "PROJECT_MAPPING_FILENAME",
            "PROJECT_MAPPING_VERSION",
            "ParameterCandidate",
            "ParameterDecision",
            "ParameterGroupCandidate",
            "ParameterGroupDecision",
            "ProjectModel",
            "PropertyEvidence",
            "SEMANTIC_MAP_FILENAME",
            "SEMANTIC_MAP_SCHEMA_VERSION",
            "SemanticMapConfirmationRequiredError",
            "SemanticMapContractError",
            "SemanticMapDecodeError",
            "SemanticMapDiffEntry",
            "SemanticMapError",
            "SemanticMapIdentityError",
            "SemanticMapSelectionError",
            "SemanticMapUpdatePlan",
            "SemanticMapWriteError",
            "SemanticMapWriteResult",
            "SemanticParameterTypeSelection",
            "TargetabilityEvidence",
            "build_capture_document",
            "build_semantic_map",
            "canonical_capture_bytes",
            "canonical_capture_text",
            "canonical_semantic_map_bytes",
            "canonical_semantic_map_text",
            "derive_capture_id",
            "detect_capture_drift",
            "diff_mappings",
            "discover_capture_candidates",
            "document_fingerprint",
            "freecad_semantic_map_template",
            "generate_component_id",
            "generate_feature_id",
            "generate_group_owned_parameter_id",
            "generate_metadata_id",
            "generate_parameter_group_id",
            "generate_parameter_id",
            "generate_relationship_id",
            "load_project_context",
            "plan_capture_outputs",
            "plan_semantic_map_update",
            "resolve_model_by_path",
            "resolve_model_source_path",
            "resolve_selected_model",
            "update_semantic_map",
            "validate_capture_document",
            "validate_semantic_map",
            "verify_active_source",
            "write_capture_document",
            "write_capture_outputs",
            "write_semantic_map",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(capture, name), f"missing public name: {name}")


if __name__ == "__main__":
    unittest.main()
