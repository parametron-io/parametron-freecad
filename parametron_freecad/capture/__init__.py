"""GUI-free Parametron capture contract core.

This package implements the FreeCAD-free capture authoring core:

* the schema 1.0 ``prm.cad.json`` record model;
* semantic-name and stable-ID policy;
* canonical serialization;
* an atomic writer with an explicit overwrite decision.

It also implements FreeCAD-native capture discovery and the versioned
``prm.semantic-map.json`` template, generator, validator, and merge writer.

It does not import ``FreeCAD``, ``FreeCADGui``, or ``Part``. Project-root
discovery, project mapping, source fingerprinting, drift handling, GUI
surfaces, capture orchestration, and Engine preflight belong to other bounded
capture issues.
"""

from __future__ import annotations

from parametron_freecad.capture.canonical import (
    canonical_capture_bytes,
    canonical_capture_text,
)
from parametron_freecad.capture.discovery import (
    CaptureDiscovery,
    ComponentCandidate,
    DiscoveryDiagnostic,
    DocumentEvidence,
    FeatureCandidate,
    MetadataCandidate,
    ParameterCandidate,
    ParameterGroupCandidate,
    PropertyEvidence,
    TargetabilityEvidence,
    discover_capture_candidates,
)
from parametron_freecad.capture.discovery_errors import (
    CaptureDiscoveryDocumentError,
    CaptureDiscoveryError,
    CaptureDiscoveryInspectionError,
)
from parametron_freecad.capture.errors import (
    CaptureContractError,
    CaptureError,
    CaptureIdPolicyError,
    CaptureNamePolicyError,
    CaptureWriteError,
)
from parametron_freecad.capture.model import (
    Annotations,
    CaptureDocument,
    Component,
    Entities,
    Feature,
    IdentitySource,
    Metadata,
    NamedVersion,
    Parameter,
    ParameterGroup,
    Relationship,
    RootProduct,
    SourceDocument,
    SourceFile,
    Structure,
    StructureNode,
    Targetability,
)
from parametron_freecad.capture.naming import (
    generate_component_id,
    generate_feature_id,
    generate_group_owned_parameter_id,
    generate_metadata_id,
    generate_parameter_group_id,
    generate_parameter_id,
    generate_relationship_id,
    native_key_slug,
    semantic_name_slug,
    validate_explicit_id,
    validate_semantic_name,
)
from parametron_freecad.capture.semantic_map import (
    FREECAD_CAD_SYSTEM_MIN_VERSION,
    FREECAD_SEMANTIC_MAP_TEMPLATE_VERSION,
    SEMANTIC_MAP_FILENAME,
    SEMANTIC_MAP_SCHEMA_VERSION,
    FreeCADSemanticMapSelection,
    SemanticMapConfirmationRequiredError,
    SemanticMapContractError,
    SemanticMapDecodeError,
    SemanticMapDiffEntry,
    SemanticMapError,
    SemanticMapIdentityError,
    SemanticMapSelectionError,
    SemanticMapUpdatePlan,
    SemanticMapWriteError,
    SemanticMapWriteResult,
    SemanticParameterTypeSelection,
    build_semantic_map,
    canonical_semantic_map_bytes,
    canonical_semantic_map_text,
    freecad_semantic_map_template,
    plan_semantic_map_update,
    update_semantic_map,
    validate_semantic_map,
    write_semantic_map,
)
from parametron_freecad.capture.validation import (
    CAPTURE_SCHEMA_VERSION,
    validate_capture_document,
)
from parametron_freecad.capture.writer import (
    CAPTURE_CONTRACT_FILENAME,
    write_capture_document,
)

__all__ = [
    "Annotations",
    "CAPTURE_CONTRACT_FILENAME",
    "CAPTURE_SCHEMA_VERSION",
    "CaptureContractError",
    "CaptureDiscovery",
    "CaptureDiscoveryDocumentError",
    "CaptureDiscoveryError",
    "CaptureDiscoveryInspectionError",
    "CaptureDocument",
    "CaptureError",
    "CaptureIdPolicyError",
    "CaptureNamePolicyError",
    "CaptureWriteError",
    "Component",
    "ComponentCandidate",
    "DiscoveryDiagnostic",
    "DocumentEvidence",
    "Entities",
    "FREECAD_CAD_SYSTEM_MIN_VERSION",
    "FREECAD_SEMANTIC_MAP_TEMPLATE_VERSION",
    "Feature",
    "FeatureCandidate",
    "FreeCADSemanticMapSelection",
    "IdentitySource",
    "Metadata",
    "MetadataCandidate",
    "NamedVersion",
    "Parameter",
    "ParameterCandidate",
    "ParameterGroup",
    "ParameterGroupCandidate",
    "PropertyEvidence",
    "Relationship",
    "RootProduct",
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
    "SourceDocument",
    "SourceFile",
    "Structure",
    "StructureNode",
    "Targetability",
    "TargetabilityEvidence",
    "build_semantic_map",
    "canonical_capture_bytes",
    "canonical_capture_text",
    "canonical_semantic_map_bytes",
    "canonical_semantic_map_text",
    "discover_capture_candidates",
    "freecad_semantic_map_template",
    "generate_component_id",
    "generate_feature_id",
    "generate_group_owned_parameter_id",
    "generate_metadata_id",
    "generate_parameter_group_id",
    "generate_parameter_id",
    "generate_relationship_id",
    "native_key_slug",
    "plan_semantic_map_update",
    "semantic_name_slug",
    "update_semantic_map",
    "validate_capture_document",
    "validate_explicit_id",
    "validate_semantic_map",
    "validate_semantic_name",
    "write_capture_document",
    "write_semantic_map",
]
