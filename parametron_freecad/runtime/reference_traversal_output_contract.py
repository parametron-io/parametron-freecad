"""Raw reference traversal output contract for Phase 1 headless runtime."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from parametron_freecad.common.canonical_json import dumps_canonical

REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION = "1.0"
REFERENCE_TRAVERSAL_OUTPUT_KIND_RAW_REFERENCE_TRAVERSAL = "raw_reference_traversal"
REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_ROOT = "working_copy"
REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_POLICY = "working_copy_child"
REFERENCE_TRAVERSAL_OUTPUT_PATH_PARENT_POLICY = "existing_directory"

REFERENCE_TRAVERSAL_FIELD_SCHEMA_VERSION = "schemaVersion"
REFERENCE_TRAVERSAL_FIELD_KIND = "kind"
REFERENCE_TRAVERSAL_FIELD_BOUNDARY = "boundary"
REFERENCE_TRAVERSAL_FIELD_OPERATION = "operation"
REFERENCE_TRAVERSAL_FIELD_STATUS = "status"
REFERENCE_TRAVERSAL_FIELD_SOURCE_DOCUMENT = "sourceDocument"
REFERENCE_TRAVERSAL_FIELD_NODES = "nodes"
REFERENCE_TRAVERSAL_FIELD_EDGES = "edges"
REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS = "diagnostics"

REFERENCE_TRAVERSAL_NODE_FIELD_SEQUENCE = "sequence"
REFERENCE_TRAVERSAL_NODE_FIELD_ID = "id"
REFERENCE_TRAVERSAL_NODE_FIELD_KIND = "kind"
REFERENCE_TRAVERSAL_NODE_FIELD_STATE = "state"
REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH = "documentPath"
REFERENCE_TRAVERSAL_NODE_FIELD_OBJECT_NAME = "objectName"
REFERENCE_TRAVERSAL_NODE_FIELD_LABEL = "label"
REFERENCE_TRAVERSAL_NODE_FIELD_DIAGNOSTIC = "diagnostic"

REFERENCE_TRAVERSAL_EDGE_FIELD_SEQUENCE = "sequence"
REFERENCE_TRAVERSAL_EDGE_FIELD_SOURCE = "source"
REFERENCE_TRAVERSAL_EDGE_FIELD_TARGET = "target"
REFERENCE_TRAVERSAL_EDGE_FIELD_KIND = "kind"
REFERENCE_TRAVERSAL_EDGE_FIELD_STATE = "state"
REFERENCE_TRAVERSAL_EDGE_FIELD_DIAGNOSTIC = "diagnostic"

REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL = "document_internal"
REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT = "external_document"
REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE = "external_file"

REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES = (
    REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL,
    REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT,
    REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE,
)

REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE = (
    "document_internal_reference"
)
REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE = (
    "external_document_reference"
)
REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE = "external_file_reference"

REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT = "document"
REFERENCE_TRAVERSAL_NODE_KIND_OBJECT = "object"
REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT = "external_document"
REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE = "external_file"

REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS = (
    REFERENCE_TRAVERSAL_NODE_FIELD_KIND,
    REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH,
    REFERENCE_TRAVERSAL_NODE_FIELD_OBJECT_NAME,
)

REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND = MappingProxyType(
    {
        REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT: (
            REFERENCE_TRAVERSAL_NODE_FIELD_KIND,
            REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH,
        ),
        REFERENCE_TRAVERSAL_NODE_KIND_OBJECT: (
            REFERENCE_TRAVERSAL_NODE_FIELD_KIND,
            REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH,
            REFERENCE_TRAVERSAL_NODE_FIELD_OBJECT_NAME,
        ),
        REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT: (
            REFERENCE_TRAVERSAL_NODE_FIELD_KIND,
            REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH,
        ),
        REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE: (
            REFERENCE_TRAVERSAL_NODE_FIELD_KIND,
            REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH,
        ),
    }
)

REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS = (
    REFERENCE_TRAVERSAL_NODE_FIELD_ID,
    REFERENCE_TRAVERSAL_NODE_FIELD_STATE,
    REFERENCE_TRAVERSAL_NODE_FIELD_LABEL,
    REFERENCE_TRAVERSAL_NODE_FIELD_DIAGNOSTIC,
    REFERENCE_TRAVERSAL_NODE_FIELD_SEQUENCE,
)

REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS = (
    "sourceSemanticNodeIdentityKey",
    "targetSemanticNodeIdentityKey",
    REFERENCE_TRAVERSAL_EDGE_FIELD_KIND,
)

REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_EXCLUDED_FIELDS = (
    REFERENCE_TRAVERSAL_EDGE_FIELD_SOURCE,
    REFERENCE_TRAVERSAL_EDGE_FIELD_TARGET,
    REFERENCE_TRAVERSAL_EDGE_FIELD_STATE,
    REFERENCE_TRAVERSAL_EDGE_FIELD_DIAGNOSTIC,
    REFERENCE_TRAVERSAL_EDGE_FIELD_SEQUENCE,
)

REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS = (
    REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
    REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
    REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
)

REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS = "timestamps"
REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_REQUEST_IDS = "request_ids"
REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_ACTORS = "actors"
REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_PROCESS_RUNTIME_IDENTITIES = (
    "process_runtime_identities"
)
REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS = (
    "temporary_absolute_paths"
)
REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER = (
    "incidental_enumeration_order"
)

REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS = (
    REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS,
    REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_REQUEST_IDS,
    REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_ACTORS,
    REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_PROCESS_RUNTIME_IDENTITIES,
    REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS,
    REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER,
)

REFERENCE_TRAVERSAL_INTERNAL_REFERENCE_EDGE_KINDS = (
    REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
)

REFERENCE_TRAVERSAL_EXTERNAL_REFERENCE_EDGE_KINDS = (
    REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
    REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
)

REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_SEQUENCE = "sequence"
REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_SEVERITY = "severity"
REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_CODE = "code"
REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_MESSAGE = "message"
REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_STAGE = "stage"

REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR = "error"
REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_WARNING = "warning"
REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_MALFORMED_REQUEST = (
    "malformed_traversal_request"
)
REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_UNSUPPORTED_REFERENCE_VALUE_SHAPE = (
    "unsupported_reference_value_shape"
)
REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION = "request_validation"
REFERENCE_TRAVERSAL_STAGE_REFERENCE_DISCOVERY = "reference_discovery"

REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS = (
    REFERENCE_TRAVERSAL_FIELD_SOURCE_DOCUMENT,
    f"{REFERENCE_TRAVERSAL_FIELD_NODES}[].{REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH}",
)

REFERENCE_TRAVERSAL_EMITTED_IDENTIFIER_FIELDS = (
    f"{REFERENCE_TRAVERSAL_FIELD_NODES}[].{REFERENCE_TRAVERSAL_NODE_FIELD_ID}",
    f"{REFERENCE_TRAVERSAL_FIELD_EDGES}[].{REFERENCE_TRAVERSAL_EDGE_FIELD_SOURCE}",
    f"{REFERENCE_TRAVERSAL_FIELD_EDGES}[].{REFERENCE_TRAVERSAL_EDGE_FIELD_TARGET}",
)

REFERENCE_TRAVERSAL_EMITTED_OBJECT_NAME_FIELDS = (
    f"{REFERENCE_TRAVERSAL_FIELD_NODES}[].{REFERENCE_TRAVERSAL_NODE_FIELD_OBJECT_NAME}",
)

REFERENCE_TRAVERSAL_EMITTED_LABEL_FIELDS = (
    f"{REFERENCE_TRAVERSAL_FIELD_NODES}[].{REFERENCE_TRAVERSAL_NODE_FIELD_LABEL}",
)

REFERENCE_TRAVERSAL_EMITTED_INLINE_DIAGNOSTIC_FIELDS = (
    f"{REFERENCE_TRAVERSAL_FIELD_NODES}[].{REFERENCE_TRAVERSAL_NODE_FIELD_DIAGNOSTIC}",
    f"{REFERENCE_TRAVERSAL_FIELD_EDGES}[].{REFERENCE_TRAVERSAL_EDGE_FIELD_DIAGNOSTIC}",
)

REFERENCE_TRAVERSAL_EMITTED_STRUCTURED_DIAGNOSTIC_FIELDS = (
    f"{REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS}[].{REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_SEVERITY}",
    f"{REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS}[].{REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_CODE}",
    f"{REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS}[].{REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_MESSAGE}",
    f"{REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS}[].{REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_STAGE}",
)

REFERENCE_TRAVERSAL_EMITTED_RAW_EVIDENCE_FIELDS = (
    *REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS,
    *REFERENCE_TRAVERSAL_EMITTED_IDENTIFIER_FIELDS,
    *REFERENCE_TRAVERSAL_EMITTED_OBJECT_NAME_FIELDS,
    *REFERENCE_TRAVERSAL_EMITTED_LABEL_FIELDS,
    *REFERENCE_TRAVERSAL_EMITTED_INLINE_DIAGNOSTIC_FIELDS,
    *REFERENCE_TRAVERSAL_EMITTED_STRUCTURED_DIAGNOSTIC_FIELDS,
)

REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE = "objectType"
REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY = "sourceProperty"
REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM = (
    "referenceMechanism"
)

REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS = (
    REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE,
    REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY,
    REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM,
)

REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS = MappingProxyType(
    {
        REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE: "nodes[].objectType",
        REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY: (
            "edges[].sourceProperty"
        ),
        REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM: (
            "edges[].referenceMechanism"
        ),
    }
)

REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT = "reference_traversal_entrypoint"
REFERENCE_TRAVERSAL_BOUNDARY_ENGINE_INVOCATION = "engine_invocation"

REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL = "reference_traversal"

REFERENCE_TRAVERSAL_STATUS_SUCCEEDED = "succeeded"
REFERENCE_TRAVERSAL_STATUS_PARTIAL = "partial"
REFERENCE_TRAVERSAL_STATUS_FAILED = "failed"

REFERENCE_TRAVERSAL_STATE_RESOLVED = "resolved"
REFERENCE_TRAVERSAL_STATE_MISSING = "missing"
REFERENCE_TRAVERSAL_STATE_UNRESOLVED = "unresolved"
REFERENCE_TRAVERSAL_STATE_SKIPPED = "skipped"
REFERENCE_TRAVERSAL_STATE_FAILED = "failed"

REFERENCE_TRAVERSAL_DEFINED_STATES = (
    REFERENCE_TRAVERSAL_STATE_RESOLVED,
    REFERENCE_TRAVERSAL_STATE_MISSING,
    REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
    REFERENCE_TRAVERSAL_STATE_SKIPPED,
    REFERENCE_TRAVERSAL_STATE_FAILED,
)

REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS = (
    REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH,
    REFERENCE_TRAVERSAL_NODE_FIELD_KIND,
    REFERENCE_TRAVERSAL_NODE_FIELD_ID,
    REFERENCE_TRAVERSAL_NODE_FIELD_OBJECT_NAME,
    REFERENCE_TRAVERSAL_NODE_FIELD_LABEL,
    REFERENCE_TRAVERSAL_NODE_FIELD_STATE,
    REFERENCE_TRAVERSAL_NODE_FIELD_DIAGNOSTIC,
)

REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS = (
    REFERENCE_TRAVERSAL_EDGE_FIELD_SOURCE,
    REFERENCE_TRAVERSAL_EDGE_FIELD_TARGET,
    REFERENCE_TRAVERSAL_EDGE_FIELD_KIND,
    REFERENCE_TRAVERSAL_EDGE_FIELD_STATE,
    REFERENCE_TRAVERSAL_EDGE_FIELD_DIAGNOSTIC,
)

REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS = (
    REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE,
)

REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS = (
    REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY,
    REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM,
)

REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS = (
    *REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS[:4],
    *REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS,
    *REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS[4:],
)

REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS = (
    *REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS[:3],
    *REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS,
    *REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS[3:],
)

REFERENCE_TRAVERSAL_DIAGNOSTIC_ORDER_FIELDS = (
    REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_STAGE,
    REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_SEVERITY,
    REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_CODE,
    REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_MESSAGE,
)

REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES = (
    REFERENCE_TRAVERSAL_STATE_MISSING,
    REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
)

REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_NODE = "node"
REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_EDGE = "edge"
REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_ORDER = (
    REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_NODE,
    REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_EDGE,
)


class ReferenceTraversalOutputContractError(ValueError):
    """Raised when raw reference traversal output cannot be built."""


@dataclass(frozen=True, slots=True)
class RawReferenceTraversalNode:
    id: str
    kind: str
    state: str
    document_path: str | None = None
    object_name: str | None = None
    label: str | None = None
    diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class RawReferenceTraversalEdge:
    source: str
    target: str
    kind: str
    state: str
    diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class RawReferenceTraversalDiagnostic:
    severity: str
    code: str
    message: str
    stage: str | None = None


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReferenceTraversalOutputContractError(
            f"{field_name} must be a non-empty string"
        )
    return value


def _require_optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ReferenceTraversalOutputContractError(
            f"{field_name} must be a non-empty string when provided"
        )
    return value


def _require_defined_traversal_state(value: object, field_name: str) -> str:
    state = _require_non_empty_string(value, field_name)
    if state not in REFERENCE_TRAVERSAL_DEFINED_STATES:
        allowed = ", ".join(REFERENCE_TRAVERSAL_DEFINED_STATES)
        raise ReferenceTraversalOutputContractError(
            f"{field_name} must be one of: {allowed}"
        )
    return state


def build_reference_traversal_semantic_node_identity_contract() -> dict[str, Any]:
    """Return deterministic semantic node identity contract metadata.

    Path values described here are already-canonical contract inputs. This
    helper neither performs nor proves path canonicalization.
    """
    return {
        "supportedNodeKinds": list(
            REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND
        ),
        "identityFieldsByNodeKind": {
            kind: list(fields)
            for kind, fields in (
                REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND.items()
            )
        },
        "identityFieldOrder": list(
            REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS
        ),
        "excludedFields": list(
            REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS
        ),
        "pathInputPolicy": (
            "documentPath must already be canonical and contract-relative; "
            "this helper does not prove or perform canonicalization"
        ),
        "normalizationPerformed": False,
        "filesystemInspected": False,
        "generatedIdentifierFormula": False,
        "engineNormalizationPerformed": False,
        "pdmIdentityProduced": False,
    }


def build_reference_traversal_semantic_node_identity_key(
    *,
    kind: str,
    document_path: str,
    object_name: str | None = None,
) -> tuple[str, ...]:
    """Return the ordered semantic identity key for one documented node kind."""
    kind_value = _require_non_empty_string(kind, "kind")
    if kind_value not in REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND:
        allowed = ", ".join(
            REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND
        )
        raise ReferenceTraversalOutputContractError(
            f"kind must be one of: {allowed}"
        )

    document_path_value = _require_non_empty_string(
        document_path, "documentPath"
    )
    if kind_value == REFERENCE_TRAVERSAL_NODE_KIND_OBJECT:
        object_name_value = _require_non_empty_string(
            object_name, "objectName"
        )
        return (kind_value, document_path_value, object_name_value)

    if object_name is not None:
        raise ReferenceTraversalOutputContractError(
            f"objectName must be absent for {kind_value} nodes"
        )
    return (kind_value, document_path_value)


def _require_semantic_node_identity_key(
    value: object, field_name: str
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ReferenceTraversalOutputContractError(
            f"{field_name} must be a semantic node identity tuple"
        )
    if not value:
        raise ReferenceTraversalOutputContractError(
            f"{field_name} must be a non-empty semantic node identity tuple"
        )
    for component in value:
        if not isinstance(component, str) or not component:
            raise ReferenceTraversalOutputContractError(
                f"{field_name} components must be non-empty strings"
            )

    kind = value[0]
    fields = REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND.get(kind)
    if fields is None:
        allowed = ", ".join(
            REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND
        )
        raise ReferenceTraversalOutputContractError(
            f"{field_name} kind must be one of: {allowed}"
        )
    if len(value) != len(fields):
        raise ReferenceTraversalOutputContractError(
            f"{field_name} for {kind} must contain {len(fields)} components"
        )
    return value


def build_reference_traversal_semantic_edge_identity_contract() -> dict[str, Any]:
    """Return deterministic semantic edge identity contract metadata.

    Property/reference-mechanism-sensitive identity is deferred because the raw
    edge contract does not yet carry that provenance. Supporting it requires a
    deliberate compatible or versioned raw evidence contract change.
    """
    return {
        "identityComponents": list(
            REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS
        ),
        "supportedEdgeKinds": list(
            REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS
        ),
        "excludedRawEdgeFields": list(
            REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_EXCLUDED_FIELDS
        ),
        "semanticNodeIdentityKeys": {
            "source": "follows semantic node identity contract",
            "target": "follows semantic node identity contract",
        },
        "directed": True,
        "reverseEdgeIsDistinct": True,
        "inputBehavior": {
            "preservesAcceptedStringsExactly": True,
            "normalizationPerformed": False,
            "filesystemInspected": False,
        },
        "deduplication": {
            "key": list(REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS),
            "duplicateCondition": "all_identity_components_equal",
            "outputOrder": list(
                REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS
            ),
            "rawStateOrDiagnosticMerged": False,
            "representativeRawEdgeSelected": False,
        },
        "generatedSerializedEdgeIdentifier": False,
        "rawPayloadShapeChanged": False,
        "rawPayloadEdgesDeduplicated": False,
        "performsRealFreecadTraversal": False,
        "engineNormalizationPerformed": False,
        "pdmIdentityProduced": False,
        "propertyOrReferenceMechanismSensitiveIdentity": {
            "supported": False,
            "provenancePresentInRawEdgeContract": False,
            "deferred": True,
            "futureRequirement": (
                "A deliberate compatible or versioned raw evidence contract "
                "change must approve provenance fields before semantic edge "
                "identity may be extended."
            ),
            "helperClaimsPropertySensitiveDeduplication": False,
        },
    }


def build_reference_traversal_semantic_edge_identity_key(
    *,
    source_node_key: tuple[str, ...],
    target_node_key: tuple[str, ...],
    kind: str,
) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    """Return the directed semantic identity key for one documented edge kind."""
    source_value = _require_semantic_node_identity_key(
        source_node_key, "sourceNodeKey"
    )
    target_value = _require_semantic_node_identity_key(
        target_node_key, "targetNodeKey"
    )
    kind_value = _require_non_empty_string(kind, "kind")
    if kind_value not in REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS:
        allowed = ", ".join(
            REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS
        )
        raise ReferenceTraversalOutputContractError(
            f"kind must be one of: {allowed}"
        )
    return (source_value, target_value, kind_value)


def _require_semantic_edge_identity_key(
    value: object,
) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    if not isinstance(value, tuple) or len(value) != 3:
        raise ReferenceTraversalOutputContractError(
            "semantic edge identity key must be a three-component tuple"
        )
    return build_reference_traversal_semantic_edge_identity_key(
        source_node_key=value[0],
        target_node_key=value[1],
        kind=value[2],
    )


def deduplicate_reference_traversal_semantic_edge_identity_keys(
    identity_keys: Sequence[
        tuple[tuple[str, ...], tuple[str, ...], str]
    ],
) -> tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...]:
    """Return validated unique semantic edge keys in deterministic order."""
    if isinstance(identity_keys, (str, bytes)) or not isinstance(
        identity_keys, Sequence
    ):
        raise ReferenceTraversalOutputContractError(
            "identityKeys must be a sequence of semantic edge identity tuples"
        )
    validated = (
        _require_semantic_edge_identity_key(identity_key)
        for identity_key in identity_keys
    )
    return tuple(sorted(set(validated)))


def _optional_string_order_value(
    value: object, field_name: str
) -> tuple[int, str]:
    if value is None:
        return (0, "")
    return (1, _require_optional_string(value, field_name) or "")


def _require_node_sequence(value: object) -> Sequence[RawReferenceTraversalNode]:
    if isinstance(value, (str, bytes)):
        raise ReferenceTraversalOutputContractError(
            "nodes must be a sequence of RawReferenceTraversalNode"
        )
    if not isinstance(value, Sequence):
        raise ReferenceTraversalOutputContractError(
            "nodes must be a sequence of RawReferenceTraversalNode"
        )
    for node in value:
        if not isinstance(node, RawReferenceTraversalNode):
            raise ReferenceTraversalOutputContractError(
                "nodes must be a sequence of RawReferenceTraversalNode"
            )
    return value


def _require_edge_sequence(value: object) -> Sequence[RawReferenceTraversalEdge]:
    if isinstance(value, (str, bytes)):
        raise ReferenceTraversalOutputContractError(
            "edges must be a sequence of RawReferenceTraversalEdge"
        )
    if not isinstance(value, Sequence):
        raise ReferenceTraversalOutputContractError(
            "edges must be a sequence of RawReferenceTraversalEdge"
        )
    for edge in value:
        if not isinstance(edge, RawReferenceTraversalEdge):
            raise ReferenceTraversalOutputContractError(
                "edges must be a sequence of RawReferenceTraversalEdge"
            )
    return value


def _require_diagnostic_sequence(
    value: object,
) -> Sequence[RawReferenceTraversalDiagnostic]:
    if isinstance(value, (str, bytes)):
        raise ReferenceTraversalOutputContractError(
            "diagnostics must be a sequence of RawReferenceTraversalDiagnostic"
        )
    if not isinstance(value, Sequence):
        raise ReferenceTraversalOutputContractError(
            "diagnostics must be a sequence of RawReferenceTraversalDiagnostic"
        )
    for diagnostic in value:
        if not isinstance(diagnostic, RawReferenceTraversalDiagnostic):
            raise ReferenceTraversalOutputContractError(
                "diagnostics must be a sequence of RawReferenceTraversalDiagnostic"
            )
    return value


def build_reference_traversal_node_order_key(
    node: RawReferenceTraversalNode,
) -> tuple[tuple[int, str], str, str, tuple[int, str], tuple[int, str], str, tuple[int, str]]:
    """Return the validated total-order key for one raw traversal node."""
    if not isinstance(node, RawReferenceTraversalNode):
        raise ReferenceTraversalOutputContractError(
            "node must be a RawReferenceTraversalNode"
        )
    return (
        _optional_string_order_value(node.document_path, "documentPath"),
        _require_non_empty_string(node.kind, "kind"),
        _require_non_empty_string(node.id, "id"),
        _optional_string_order_value(node.object_name, "objectName"),
        _optional_string_order_value(node.label, "label"),
        _require_defined_traversal_state(node.state, "state"),
        _optional_string_order_value(node.diagnostic, "diagnostic"),
    )


def build_reference_traversal_edge_order_key(
    edge: RawReferenceTraversalEdge,
) -> tuple[str, str, str, str, tuple[int, str]]:
    """Return the validated total-order key for one raw traversal edge."""
    if not isinstance(edge, RawReferenceTraversalEdge):
        raise ReferenceTraversalOutputContractError(
            "edge must be a RawReferenceTraversalEdge"
        )
    return (
        _require_non_empty_string(edge.source, "source"),
        _require_non_empty_string(edge.target, "target"),
        _require_non_empty_string(edge.kind, "kind"),
        _require_defined_traversal_state(edge.state, "state"),
        _optional_string_order_value(edge.diagnostic, "diagnostic"),
    )


def build_reference_traversal_diagnostic_order_key(
    diagnostic: RawReferenceTraversalDiagnostic,
) -> tuple[tuple[int, str], str, str, str]:
    """Return the validated total-order key for one structured diagnostic."""
    if not isinstance(diagnostic, RawReferenceTraversalDiagnostic):
        raise ReferenceTraversalOutputContractError(
            "diagnostic must be a RawReferenceTraversalDiagnostic"
        )
    return (
        _optional_string_order_value(diagnostic.stage, "stage"),
        _require_non_empty_string(diagnostic.severity, "severity"),
        _require_non_empty_string(diagnostic.code, "code"),
        _require_non_empty_string(diagnostic.message, "message"),
    )


def build_reference_traversal_unresolved_entry_order_key(
    entry: RawReferenceTraversalNode | RawReferenceTraversalEdge,
) -> tuple[
    int,
    tuple[
        tuple[int, str] | str,
        ...,
    ],
]:
    """Return the mixed total-order key for missing or unresolved raw evidence."""
    if isinstance(entry, RawReferenceTraversalNode):
        entry_type = REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_NODE
        nested_key = build_reference_traversal_node_order_key(entry)
    elif isinstance(entry, RawReferenceTraversalEdge):
        entry_type = REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_EDGE
        nested_key = build_reference_traversal_edge_order_key(entry)
    else:
        raise ReferenceTraversalOutputContractError(
            "entry must be a RawReferenceTraversalNode or RawReferenceTraversalEdge"
        )

    state = _require_defined_traversal_state(entry.state, "state")
    if state not in REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES:
        allowed = ", ".join(REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES)
        raise ReferenceTraversalOutputContractError(
            f"entry state must be one of: {allowed}"
        )
    return (
        REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_ORDER.index(entry_type),
        nested_key,
    )


def order_reference_traversal_nodes(
    nodes: Sequence[RawReferenceTraversalNode],
) -> tuple[RawReferenceTraversalNode, ...]:
    """Return raw traversal nodes in contract-defined deterministic order."""
    node_sequence = _require_node_sequence(nodes)
    return tuple(
        sorted(node_sequence, key=build_reference_traversal_node_order_key)
    )


def order_reference_traversal_edges(
    edges: Sequence[RawReferenceTraversalEdge],
) -> tuple[RawReferenceTraversalEdge, ...]:
    """Return raw traversal edges in contract-defined deterministic order."""
    edge_sequence = _require_edge_sequence(edges)
    return tuple(
        sorted(edge_sequence, key=build_reference_traversal_edge_order_key)
    )


def order_reference_traversal_diagnostics(
    diagnostics: Sequence[RawReferenceTraversalDiagnostic],
) -> tuple[RawReferenceTraversalDiagnostic, ...]:
    """Return structured diagnostics in contract-defined deterministic order."""
    diagnostic_sequence = _require_diagnostic_sequence(diagnostics)
    return tuple(
        sorted(
            diagnostic_sequence,
            key=build_reference_traversal_diagnostic_order_key,
        )
    )


def order_reference_traversal_unresolved_entries(
    entries: Sequence[
        RawReferenceTraversalNode | RawReferenceTraversalEdge
    ],
) -> tuple[RawReferenceTraversalNode | RawReferenceTraversalEdge, ...]:
    """Sort missing or unresolved node/edge evidence without deduplication."""
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
        raise ReferenceTraversalOutputContractError(
            "entries must be a sequence of RawReferenceTraversalNode or RawReferenceTraversalEdge"
        )
    return tuple(
        sorted(
            entries,
            key=build_reference_traversal_unresolved_entry_order_key,
        )
    )


def build_reference_traversal_total_ordering_contract() -> dict[str, Any]:
    """Return fresh metadata describing raw traversal total ordering."""
    return {
        "nodeOrderFields": list(REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS),
        "edgeOrderFields": list(REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS),
        "diagnosticOrderFields": list(
            REFERENCE_TRAVERSAL_DIAGNOSTIC_ORDER_FIELDS
        ),
        "optionalStringOrder": "None before every provided string",
        "unresolvedEntries": {
            "acceptedStates": list(
                REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES
            ),
            "typeOrder": list(
                REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_ORDER
            ),
            "interpretation": (
                "existing node or edge evidence, not a payload collection"
            ),
        },
        "sorting": {
            "preservesDuplicateRawEvidence": True,
            "normalizationPerformed": False,
            "deduplicationPerformed": False,
            "filesystemInspected": False,
        },
        "payloadSchemaChanged": False,
        "performsRealFreecadTraversal": False,
        "implementsTraversalWriter": False,
        "implementsRuntimeWiring": False,
        "engineNormalizationPerformed": False,
        "pdmBehaviorProduced": {
            "identity": False,
            "persistence": False,
            "graph": False,
            "whereUsed": False,
        },
    }


def build_reference_traversal_ordering_extension_contract() -> dict[str, Any]:
    """Return fresh metadata defining inactive future provenance placement."""
    return {
        "phase1Order": {
            "nodeFields": list(REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS),
            "edgeFields": list(REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS),
        },
        "extensionOnlyFields": {
            "nodeFields": list(
                REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS
            ),
            "edgeFields": list(
                REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS
            ),
        },
        "deliberateFutureOrder": {
            "nodeFields": list(
                REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS
            ),
            "edgeFields": list(
                REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS
            ),
            "preservesPhase1RelativeOrder": True,
            "insertionPositions": {
                REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE: (
                    "after objectName and before label"
                ),
                REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY: (
                    "after kind and before referenceMechanism"
                ),
                REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM: (
                    "after sourceProperty and before state"
                ),
            },
            "futureOptionalStringOrder": (
                "None before every provided string when active ordering "
                "helpers are approved"
            ),
            "unknownFutureFieldPolicy": (
                "Every unknown future field requires explicit reviewed "
                "placement before participating in ordering."
            ),
            "incidentalOrderIsNotContractOrder": [
                "dataclass declaration order",
                "mapping insertion order",
                "FreeCAD enumeration order",
                "runtime discovery order",
            ],
        },
        "activation": {
            "definedFutureOrderIsActive": False,
            "currentRawSchemaOrPayloadFieldsChanged": False,
            "provenanceFieldsActive": False,
            "provenanceFieldsSerialized": False,
            "currentNodeOrEdgeOrderKeyHelpersApplyExtendedOrder": False,
            "requiredApproval": (
                "Explicit compatible or versioned schema contract approval "
                "is required before activation."
            ),
        },
        "compatibility": {
            "schemaVersion": REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
            "semanticEdgeIdentityComponents": list(
                REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS
            ),
            "semanticEdgeIdentityRemainsThreeComponent": True,
            "semanticEdgeIdentityAndDeduplicationProvenanceInsensitive": True,
            "payloadBuilderBehaviorChanged": False,
            "serializationBehaviorChanged": False,
        },
        "performedBehavior": {
            "realFreecadTraversal": False,
            "normalization": False,
            "filesystemInspection": False,
            "traversalWriter": False,
            "runtimeWiring": False,
            "engineNormalization": False,
            "pdmBehavior": False,
        },
    }


def _coerce_path_argument(value: str | Path, field_name: str) -> Path:
    try:
        return Path(value).expanduser()
    except TypeError as exc:
        raise ReferenceTraversalOutputContractError(
            f"{field_name} must be a path-like value"
        ) from exc


def _resolve_working_copy_root(working_copy: str | Path) -> Path:
    candidate = _coerce_path_argument(working_copy, "working_copy").resolve(
        strict=False
    )
    if not candidate.is_dir():
        raise ReferenceTraversalOutputContractError(
            "working_copy must resolve to an existing directory"
        )
    return candidate


def _resolve_output_parent(output_path: Path) -> Path:
    parent = output_path.parent.resolve(strict=False)
    if not parent.exists():
        raise ReferenceTraversalOutputContractError(
            "output_path parent must exist"
        )
    if not parent.is_dir():
        raise ReferenceTraversalOutputContractError(
            "output_path parent must be an existing directory"
        )
    return parent


def resolve_reference_traversal_output_path(
    *,
    working_copy: str | Path,
    output_path: str | Path,
) -> Path:
    """Return a contained absolute path for a future traversal output file.

    The helper validates only the file-output safety boundary. Raw traversal
    evidence fields remain caller-provided strings and are not normalized here.
    """
    resolved_working_copy = _resolve_working_copy_root(working_copy)
    output_candidate = _coerce_path_argument(output_path, "output_path")
    if not output_candidate.is_absolute():
        output_candidate = resolved_working_copy / output_candidate

    resolved_parent = _resolve_output_parent(output_candidate)
    resolved_output_path = (
        resolved_parent / output_candidate.name
    ).resolve(strict=False)

    if (
        resolved_output_path != resolved_working_copy
        and resolved_working_copy not in resolved_output_path.parents
    ):
        raise ReferenceTraversalOutputContractError(
            "output_path must resolve inside working_copy"
        )
    if resolved_output_path.is_dir():
        raise ReferenceTraversalOutputContractError(
            "output_path must not be an existing directory"
        )

    return resolved_output_path


def build_reference_traversal_output_containment_contract() -> dict[str, Any]:
    """Return future traversal output file containment semantics."""
    return {
        "containmentRoot": REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_ROOT,
        "containmentPolicy": REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_POLICY,
        "parentPolicy": REFERENCE_TRAVERSAL_OUTPUT_PATH_PARENT_POLICY,
        "workingCopyRequirement": (
            "working_copy must resolve to an existing directory; the exact "
            "supplied directory is the authoritative execution root and its "
            "basename is not prescribed"
        ),
        "relativeOutputPathResolution": "relative_to_working_copy",
        "absoluteOutputPathPolicy": "accepted_only_inside_working_copy",
        "outputParentRequirement": "parent_must_exist_and_be_directory",
        "outputPathRequirement": "output_path_must_not_be_directory",
        "rejectedPaths": [
            "path_traversal_escape",
            "absolute_outside_working_copy",
            "symlink_escape_outside_working_copy",
            "missing_parent",
            "non_directory_parent",
            "existing_directory_output_path",
        ],
        "allowedPaths": [
            "relative_child_inside_working_copy",
            "absolute_child_inside_working_copy",
            "existing_non_directory_file_inside_working_copy",
            "missing_file_with_existing_directory_parent_inside_working_copy",
        ],
        "helperBehavior": {
            "returns": "absolute_resolved_path",
            "writesFiles": False,
            "createsDirectories": False,
            "performsRealFreecadTraversal": False,
            "implementsTraversalWriter": False,
            "implementsRuntimeEntrypointWiring": False,
        },
        "rawEvidencePathPolicy": {
            "fields": list(REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS),
            "normalizedByContainmentHelper": False,
            "usedForContainmentDecisions": False,
            "semantics": (
                "Raw traversal evidence path strings remain caller-provided "
                "evidence for Engine normalization."
            ),
        },
    }


def build_reference_traversal_emitted_raw_evidence_contract() -> dict[str, Any]:
    """Return emitted raw evidence field groups for the traversal contract."""
    return {
        "pathFields": list(REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS),
        "identifierFields": list(REFERENCE_TRAVERSAL_EMITTED_IDENTIFIER_FIELDS),
        "objectNameFields": list(REFERENCE_TRAVERSAL_EMITTED_OBJECT_NAME_FIELDS),
        "labelFields": list(REFERENCE_TRAVERSAL_EMITTED_LABEL_FIELDS),
        "inlineDiagnosticFields": list(
            REFERENCE_TRAVERSAL_EMITTED_INLINE_DIAGNOSTIC_FIELDS
        ),
        "structuredDiagnosticFields": list(
            REFERENCE_TRAVERSAL_EMITTED_STRUCTURED_DIAGNOSTIC_FIELDS
        ),
        "rawEvidenceFields": list(REFERENCE_TRAVERSAL_EMITTED_RAW_EVIDENCE_FIELDS),
    }


def build_reference_traversal_semantic_output_exclusion_contract() -> dict[str, Any]:
    """Return operational-value exclusions for semantic traversal output."""
    semantic_surfaces = [
        "semantic traversal output",
        "semantic node identity",
        "semantic edge identity",
        "semantic hashes or fingerprints",
        "semantic deduplication keys",
        "semantic total ordering",
        "deterministic sequence assignment",
    ]
    excluded_from = [
        "semantic graph identity",
        "semantic node identity",
        "semantic edge identity",
        "hashes or fingerprints of equivalent semantic evidence",
        "deduplication",
        "total ordering",
        "sequence assignment",
    ]

    return {
        "exclusionCategories": list(
            REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS
        ),
        "appliesTo": semantic_surfaces,
        "futureRuntimeAndSerializationRule": (
            "Equivalent semantic reference evidence must remain independent of "
            "the excluded operational values. This defines a rule for future "
            "runtime and serialization work; no semantic hash or fingerprint is "
            "claimed to exist."
        ),
        "exclusions": {
            REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS: {
                "examples": [
                    "request time",
                    "start time",
                    "completion time",
                    "wall-clock time",
                    "generated-at timestamps",
                    "filesystem modification time when merely operational metadata",
                ],
                "excludedFrom": list(excluded_from),
                "timestampFieldAddedToSchema1.0": False,
            },
            REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_REQUEST_IDS: {
                "examples": [
                    "request identifiers",
                    "invocation identifiers",
                    "correlation identifiers",
                    "tracing identifiers",
                    "request-local execution-attempt identifiers",
                ],
                "excludedFrom": list(excluded_from),
                "copiedIntoSemanticGraphIdentifiers": False,
            },
            REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_ACTORS: {
                "examples": [
                    "user identity",
                    "service identity",
                    "caller identity",
                    "operator identity",
                    "audit actor",
                ],
                "excludedFrom": list(excluded_from),
                "belongsInOperationalSurfaces": True,
            },
            REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_PROCESS_RUNTIME_IDENTITIES: {
                "examples": [
                    "process IDs",
                    "thread IDs",
                    "Python id(...) values",
                    "Python object identity",
                    "FreeCAD memory addresses",
                    "FreeCAD runtime object identity valid only for the current process",
                    "random UUIDs",
                    "random identifiers",
                    "database auto-increment identifiers",
                    "database insertion identifiers",
                ],
                "excludedFrom": list(excluded_from),
                "existingRawIdentifierFields": [
                    "nodes[].id",
                    "edges[].source",
                    "edges[].target",
                ],
                "existingRawIdentifierFieldsRemovedOrRenamed": False,
                "existingRawIdentifierFieldsMayUseExcludedIdentity": False,
                "serializedNodeIdFormulaDefined": False,
                "semanticNodeAndEdgeIdentityHelpersChanged": False,
            },
            REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS: {
                "examples": [
                    "absolute working-copy paths",
                    "execution-attempt root paths",
                    "host-specific temporary directories",
                    "temporary output paths",
                    "current-working-directory-dependent paths",
                ],
                "excludedFrom": list(excluded_from),
                "validSemanticPathEvidence": [
                    "canonical contract-relative sourceDocument",
                    "canonical contract-relative nodes[].documentPath",
                ],
                "temporaryAbsoluteFilesystemLocationsAreSemanticIdentity": False,
                "traversalOutputContainmentIsSeparate": True,
                "contractRelativeCanonicalizationIsSeparateFrom": [
                    "filesystem resolution",
                    "Engine normalization",
                ],
                "pathNormalizationOrResolutionPerformed": False,
                "containmentCheckPerformed": False,
                "filesystemInspectionPerformed": False,
                "schemaExtensionPerformed": False,
            },
            REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER: {
                "examples": [
                    "FreeCAD API return order",
                    "document.Objects or equivalent runtime enumeration order",
                    "filesystem directory order",
                    "dictionary or map iteration order",
                    "database insertion order",
                    "set iteration order",
                    "arbitrary discovery order",
                    "caller insertion order not explicitly approved by the contract",
                ],
                "excludedFrom": list(excluded_from),
                "authoritativeOrderingHelpers": [
                    "node total-order helper",
                    "edge total-order helper",
                    "diagnostic total-order helper",
                    "unresolved-entry total-order helper",
                ],
                "orderingAppliedBeforeZeroBasedSequenceAssignment": True,
                "contractDefinedSequenceIsPermittedSerializationEvidence": True,
                "incidentalInputOrderDeterminesFinalOrderOrSequence": False,
                "sortingExecutedByThisHelper": False,
                "existingOrderingKeysChanged": False,
                "futureTraversalRule": (
                    "Collect evidence independently of incidental enumeration "
                    "order, then apply the approved contract ordering."
                ),
            },
        },
        "operationalMetadataPlacement": {
            "permittedConceptualSurfaces": [
                "execution surfaces",
                "runtime trace surfaces",
                "audit surfaces",
                "request/invocation envelopes",
            ],
            "surfacesOrFieldsAdded": False,
            "runtimeTraceContractChanged": False,
            "mustNotUseAsHiddenStorage": [
                "labels",
                "diagnostics",
                "documentPath",
                "identifiers",
                "kinds",
                "states",
                "source fields",
                "target fields",
                "provenance fields",
            ],
            "deterministicTraversalOutcomeDiagnosticsRemainPermitted": True,
            "stackTracePolicyDefined": False,
            "runtimeDiagnosticCollectionImplemented": False,
        },
        "compatibility": {
            "schemaVersion": REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
            "payloadSchemaChanged": False,
            "serializedFieldAdded": False,
            "dataclassChanged": False,
            "semanticNodeIdentityKeyChanged": False,
            "semanticEdgeIdentityKeyChanged": False,
            "deduplicationRuleChanged": False,
            "totalOrderKeyChanged": False,
            "payloadBuilderBehaviorChanged": False,
        },
        "capabilities": {
            "definesSemanticOutputExclusionRules": True,
            "performsRealFreecadTraversal": False,
            "performsRuntimeClassification": False,
            "performsNormalization": False,
            "performsFilesystemInspection": False,
            "performsHashing": False,
            "performsDeduplication": False,
            "performsOrdering": False,
            "performsSerialization": False,
            "performsWriting": False,
            "performsRequestLoading": False,
            "performsRuntimeWiring": False,
            "performsEngineNormalizationOrVerification": False,
            "performsPdmPersistenceOrGraphBehavior": False,
        },
    }


def build_reference_traversal_normalization_contract() -> dict[str, Any]:
    """Return normalization rules without normalizing traversal evidence."""
    node_kind = (
        f"{REFERENCE_TRAVERSAL_FIELD_NODES}[]."
        f"{REFERENCE_TRAVERSAL_NODE_FIELD_KIND}"
    )
    node_state = (
        f"{REFERENCE_TRAVERSAL_FIELD_NODES}[]."
        f"{REFERENCE_TRAVERSAL_NODE_FIELD_STATE}"
    )
    edge_kind = (
        f"{REFERENCE_TRAVERSAL_FIELD_EDGES}[]."
        f"{REFERENCE_TRAVERSAL_EDGE_FIELD_KIND}"
    )
    edge_state = (
        f"{REFERENCE_TRAVERSAL_FIELD_EDGES}[]."
        f"{REFERENCE_TRAVERSAL_EDGE_FIELD_STATE}"
    )
    stable_semantic_fields = [
        REFERENCE_TRAVERSAL_FIELD_KIND,
        REFERENCE_TRAVERSAL_FIELD_BOUNDARY,
        REFERENCE_TRAVERSAL_FIELD_OPERATION,
        REFERENCE_TRAVERSAL_FIELD_STATUS,
        *REFERENCE_TRAVERSAL_EMITTED_IDENTIFIER_FIELDS,
        node_kind,
        node_state,
        *REFERENCE_TRAVERSAL_EMITTED_OBJECT_NAME_FIELDS,
        edge_kind,
        edge_state,
        f"{REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS}[]."
        f"{REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_SEVERITY}",
        f"{REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS}[]."
        f"{REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_CODE}",
        f"{REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS}[]."
        f"{REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_STAGE}",
    ]
    exact_evidence_fields = [
        *REFERENCE_TRAVERSAL_EMITTED_LABEL_FIELDS,
        *REFERENCE_TRAVERSAL_EMITTED_INLINE_DIAGNOSTIC_FIELDS,
        f"{REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS}[]."
        f"{REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_MESSAGE}",
    ]

    return {
        "fieldCategories": {
            "contractRelativePathEvidence": {
                "fields": list(REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS),
                "semanticNodeIdentityDocumentPathUsesSameContract": True,
                "notUsedAs": [
                    "traversal output-file containment",
                    "execution-root filesystem paths",
                    "temporary absolute working-copy paths",
                    "Engine-normalized asset identity",
                ],
            },
            "stableSemanticOrControlledStrings": {
                "currentSerializedFields": [
                    REFERENCE_TRAVERSAL_FIELD_SCHEMA_VERSION,
                    *stable_semantic_fields,
                ],
                "semantics": (
                    "Stable identifiers, selectors, states, kinds, stages, and "
                    "controlled contract tokens follow exact semantic rules."
                ),
            },
            "exactRawDescriptiveOrDiagnosticEvidence": {
                "currentSerializedFields": exact_evidence_fields,
                "preservedExactly": True,
                "semanticIdentityInputs": False,
                "canonicalPathInputs": False,
            },
            "inactiveFutureProvenanceStrings": {
                "requirements": list(
                    REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS
                ),
                "proposedLocations": dict(
                    REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS
                ),
                "active": False,
                "currentSerializedSchemaFields": False,
                "semantics": (
                    "Future object types, source property names, and reference "
                    "mechanisms are stable case-preserving strings when activated."
                ),
            },
        },
        "stringRules": {
            "requiredSemanticValuesAreStrings": True,
            "silentTypeCoercionAllowed": False,
            "requiredValuesMayBeEmpty": False,
            "controlledVocabularyExactAndCaseSensitive": True,
            "stableNamesIdentifiersPropertiesMechanismsCodesStagesPreserveCase": True,
            "caseFoldingPerformed": False,
            "localeSensitiveRewritingPerformed": False,
            "unicodeNormalizationPerformed": False,
            "transliterationPerformed": False,
            "semanticInferenceFromSpellingPerformed": False,
            "surroundingWhitespaceSilentlyRemoved": False,
            "futureInvalidSurroundingWhitespacePolicy": "reject_not_trim",
            "rawLabelsAndDiagnosticTextPreservedExactly": True,
            "conceptOverloadingForbidden": [
                "labels",
                "diagnostics",
                "identifiers",
                "kinds",
                "states",
                "provenance",
            ],
            "runtimeValidationChanged": False,
        },
        "canonicalContractRelativePathRules": {
            "fields": list(REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS),
            "representation": "non-empty contract-root-relative string using / separators",
            "relativeTo": "contract-defined traversal/document root",
            "absoluteFilesystemPathAllowed": False,
            "driveQualifiedAllowed": False,
            "uncOrNetworkRootAllowed": False,
            "leadingRootSeparatorAllowed": False,
            "canonicalSeparator": "/",
            "dotSegmentsAllowed": False,
            "parentSegmentsAllowed": False,
            "emptySegmentsFromRepeatedSeparatorsAllowed": False,
            "lexicalParentEscapeAllowed": False,
            "casePreserved": True,
            "unicodeCodePointsPreservedAsSupplied": True,
            "tildeExpanded": False,
            "environmentVariablesExpanded": False,
            "resolvedAgainstHostCurrentWorkingDirectory": False,
            "resolvedThroughFilesystem": False,
            "symlinksFollowed": False,
            "referencedFileMustExist": False,
            "provesOutputContainment": False,
            "provesWorkingCopyContainment": False,
            "distinctions": [
                "contract-relative path canonicalization != filesystem path resolution",
                "contract-relative path canonicalization != traversal output containment",
                "contract-relative path canonicalization != Engine normalization",
            ],
            "normalizerResolverOrValidatorImplemented": False,
        },
        "destructiveCanonicalizationPreservation": {
            "trigger": (
                "Producing a canonical semantic or path value would change the "
                "spelling or information content of observed raw evidence."
            ),
            "examples": [
                "separator conversion",
                "path-segment removal",
                "whitespace removal",
                "case rewriting",
                "Unicode rewriting",
                "another lossy transformation",
            ],
            "canonicalAndOriginalAreSeparateConcepts": True,
            "originalMayBeSilentlyOverwritten": False,
            "originalMayBeHiddenInUnrelatedExistingField": False,
            "originalRequiresSeparatelyApprovedRawEvidenceLocationOrSurface": True,
            "semanticIdentityUsesOnlyApprovedCanonicalValue": True,
            "labelsOrDiagnosticsUsedAsRawOriginalStorage": False,
        },
        "schemaCompatibilityBoundary": {
            "schemaVersion": REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
            "approvedGeneralPurposeSerializedRawOriginalFieldExists": False,
            "rawOriginalFieldActivatedByThisContract": False,
            "serializingBothFormsRequires": (
                "later explicit compatible or versioned contract-extension decision"
            ),
            "helperSerializesPreservesOrTransformsRuntimeValues": False,
        },
        "capabilities": {
            "definesNormalizationRules": True,
            "performsNormalization": False,
            "validatesRuntimeTraversalValues": False,
            "performsFilesystemInspection": False,
            "performsRealFreecadTraversal": False,
            "changesPayloadSchema": False,
            "addsSerializedField": False,
            "changesIdentityKey": False,
            "changesDeduplicationRule": False,
            "changesOrderingRule": False,
            "implementsWriter": False,
            "implementsRequestLoader": False,
            "implementsRuntimeWiring": False,
            "performsEngineNormalization": False,
            "producesPdmIdentityOrPersistenceBehavior": False,
        },
    }


def build_reference_traversal_reference_distinction_contract() -> dict[str, Any]:
    """Return raw evidence semantics for internal/external reference distinction."""
    return {
        "distinctionFields": [
            f"{REFERENCE_TRAVERSAL_FIELD_NODES}[].{REFERENCE_TRAVERSAL_NODE_FIELD_KIND}",
            f"{REFERENCE_TRAVERSAL_FIELD_EDGES}[].{REFERENCE_TRAVERSAL_EDGE_FIELD_KIND}",
            REFERENCE_TRAVERSAL_FIELD_SOURCE_DOCUMENT,
            f"{REFERENCE_TRAVERSAL_FIELD_NODES}[].{REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH}",
            f"{REFERENCE_TRAVERSAL_FIELD_EDGES}[].{REFERENCE_TRAVERSAL_EDGE_FIELD_SOURCE}",
            f"{REFERENCE_TRAVERSAL_FIELD_EDGES}[].{REFERENCE_TRAVERSAL_EDGE_FIELD_TARGET}",
        ],
        "referenceScopes": {
            REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL: {
                "edgeKind": REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                "nodeKinds": [
                    REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                    REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
                ],
                "semantics": (
                    "An edge/reference contained inside one FreeCAD document. "
                    "The target may be an object, subelement, or document-local "
                    "raw node. No external file or document identity is implied "
                    "by this scope."
                ),
            },
            REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT: {
                "edgeKind": REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
                "nodeKinds": [
                    REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT,
                ],
                "pathEvidenceField": (
                    f"{REFERENCE_TRAVERSAL_FIELD_NODES}[]."
                    f"{REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH}"
                ),
                "semantics": (
                    "An edge/reference from one document to another FreeCAD "
                    "document. External document path evidence is carried as raw "
                    "nodes[].documentPath. This is raw observed evidence, not a "
                    "filesystem containment decision."
                ),
            },
            REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE: {
                "edgeKind": REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
                "nodeKinds": [
                    REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE,
                ],
                "pathEvidenceField": (
                    f"{REFERENCE_TRAVERSAL_FIELD_NODES}[]."
                    f"{REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH}"
                ),
                "semantics": (
                    "An edge/reference from a document or object to a non-FreeCAD "
                    "file resource. External file path evidence is carried as raw "
                    "nodes[].documentPath. This is raw observed evidence, not a "
                    "filesystem containment decision."
                ),
            },
        },
        "definedReferenceScopes": list(REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES),
        "definedNodeKinds": [
            REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
            REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT,
            REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE,
        ],
        "definedEdgeKinds": [
            REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
            REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
            REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
        ],
        "internalReferenceEdgeKinds": list(
            REFERENCE_TRAVERSAL_INTERNAL_REFERENCE_EDGE_KINDS
        ),
        "externalReferenceEdgeKinds": list(
            REFERENCE_TRAVERSAL_EXTERNAL_REFERENCE_EDGE_KINDS
        ),
        "nonSemanticGuarantees": [
            "The payload builder does not validate graph semantics.",
            "Reference scope is not inferred from file extensions, filesystem state, "
            "source/target IDs, or documentPath.",
            "Caller-provided raw evidence strings are not normalized, stripped, or "
            "rewritten by this contract helper.",
        ],
    }


def build_reference_traversal_discovery_semantics_contract() -> dict[str, Any]:
    """Return classification semantics for future runtime reference discovery."""
    path_evidence_field = (
        f"{REFERENCE_TRAVERSAL_FIELD_NODES}[]."
        f"{REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH}"
    )
    return {
        "buildsOn": "build_reference_traversal_reference_distinction_contract",
        "definedReferenceScopes": list(
            REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES
        ),
        "discoverySemantics": {
            REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL: {
                "edgeKind": REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                "sourceNodeKinds": [
                    REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                    REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
                ],
                "targetNodeKinds": [
                    REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                    REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
                ],
                "requirements": [
                    "relationship is observed within one FreeCAD document identity",
                    "source and target are document-local raw nodes",
                    "document or object raw nodes are used as permitted by the existing contract",
                ],
                "doesNotImply": [
                    "another FreeCAD document",
                    "an external file",
                ],
                "notInferredFrom": [
                    "equal raw node IDs",
                    "missing path evidence",
                ],
            },
            REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT: {
                "edgeKind": REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
                "targetNodeKinds": [
                    REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT,
                ],
                "targetPathEvidenceField": path_evidence_field,
                "requirements": [
                    "relationship crosses from the source document to a distinct FreeCAD document",
                    "classification comes from supported runtime relationship evidence",
                    "raw target document path evidence is preserved through documentPath",
                ],
                "notInferredFrom": [
                    "filename extension",
                    "path suffix",
                    "filesystem existence",
                    "string shape",
                ],
            },
            REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE: {
                "edgeKind": REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
                "targetNodeKinds": [
                    REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE,
                ],
                "targetPathEvidenceField": path_evidence_field,
                "requirements": [
                    "target is a non-FreeCAD file or file-backed resource",
                    "classification comes from supported runtime relationship evidence",
                    "raw target path evidence is preserved through documentPath",
                ],
                "notInferredFrom": [
                    "filename extension",
                    "path suffix",
                    "filesystem existence",
                    "string shape",
                ],
            },
        },
        "ambiguousOrUnsupportedMechanismPolicy": (
            "Unsupported or ambiguous runtime mechanisms must not be guessed "
            "into a defined reference scope."
        ),
        "runtimeStatePolicy": (
            "This helper does not decide resolved, missing, unresolved, "
            "skipped, or failed runtime state."
        ),
        "diagnosticPolicy": (
            "This helper does not create diagnostics or failure classifications."
        ),
        "futureRuntimeMechanismPolicy": (
            "Actual supported FreeCAD mechanisms will be enumerated by the "
            "later real-runtime API inspection task."
        ),
        "performsRealFreecadDiscovery": False,
        "enumeratesSupportedRuntimeMechanisms": False,
        "classifiesRuntimeValues": False,
        "payloadSchemaChanged": False,
    }


def build_reference_traversal_runtime_state_semantics_contract() -> dict[str, Any]:
    """Return item-level runtime state semantics for raw traversal evidence."""
    state_semantics = {
        REFERENCE_TRAVERSAL_STATE_RESOLVED: {
            "meaning": (
                "A supported runtime relationship was observed and the runtime "
                "deterministically bound it to concrete target evidence sufficient "
                "for the raw traversal contract."
            ),
            "targetBindingSucceeded": True,
            "absenceEstablished": False,
            "operationAttempted": True,
            "ambiguousOrInsufficientEvidence": False,
            "deliberateNonAttempt": False,
            "runtimeDiagnosticEvidenceExpected": False,
            "doesNotMean": [
                "Engine verification passed",
                "a PDM record exists",
                "durable identity was established",
                "raw evidence paths passed filesystem-containment validation",
                "every downstream dependency was recursively traversed",
            ],
        },
        REFERENCE_TRAVERSAL_STATE_MISSING: {
            "meaning": (
                "The observed reference identifies an expected target or target "
                "location, and runtime evidence establishes that target is absent "
                "or unavailable at traversal time."
            ),
            "targetBindingSucceeded": False,
            "absenceEstablished": True,
            "operationAttempted": True,
            "ambiguousOrInsufficientEvidence": False,
            "deliberateNonAttempt": False,
            "runtimeDiagnosticEvidenceExpected": False,
            "doesNotMean": [
                "evidence is merely incomplete",
                "multiple possible targets are ambiguous",
                "the reference mechanism is unsupported",
                "an exception occurred while attempting traversal",
                "top-level traversal failure",
            ],
        },
        REFERENCE_TRAVERSAL_STATE_UNRESOLVED: {
            "meaning": (
                "A reference relationship or candidate target was observed, but "
                "available runtime evidence is insufficient or ambiguous and cannot "
                "be deterministically bound to one concrete target."
            ),
            "targetBindingSucceeded": False,
            "absenceEstablished": False,
            "operationAttempted": True,
            "ambiguousOrInsufficientEvidence": True,
            "deliberateNonAttempt": False,
            "runtimeDiagnosticEvidenceExpected": False,
            "mustNotGuess": [
                "target",
                "reference scope",
                "document kind",
                "file kind",
                "normalized identity",
            ],
            "doesNotMean": [
                "the target is absent",
                "a runtime exception occurred",
                "resolution was intentionally not attempted",
            ],
        },
        REFERENCE_TRAVERSAL_STATE_SKIPPED: {
            "meaning": (
                "The runtime deliberately made no resolution or traversal attempt "
                "for an observed item under an explicit, deterministic, "
                "contract-approved runtime boundary or traversal rule."
            ),
            "targetBindingSucceeded": False,
            "absenceEstablished": False,
            "operationAttempted": False,
            "ambiguousOrInsufficientEvidence": False,
            "deliberateNonAttempt": True,
            "runtimeDiagnosticEvidenceExpected": True,
            "evidenceRequirement": (
                "Future emitted evidence must provide an explainable reason for "
                "the deliberate non-attempt."
            ),
            "mustNotHide": [
                "ambiguity that belongs to unresolved",
                "established absence that belongs to missing",
                "an attempted operation that raised or failed",
            ],
            "genericFallbackAllowed": False,
            "futureCaseMappingsSelected": False,
        },
        REFERENCE_TRAVERSAL_STATE_FAILED: {
            "meaning": (
                "The runtime attempted the relevant resolution or traversal "
                "operation, but an exception, runtime error, invalid runtime "
                "response, or equivalent operation failure prevented a reliable "
                "result for that item."
            ),
            "targetBindingSucceeded": False,
            "absenceEstablished": False,
            "operationAttempted": True,
            "ambiguousOrInsufficientEvidence": False,
            "deliberateNonAttempt": False,
            "runtimeDiagnosticEvidenceExpected": True,
            "evidenceRequirement": (
                "Future real traversal must emit explainable diagnostic evidence "
                "for the attempted operation failure."
            ),
            "doesNotMean": [
                "the target is established absent",
                "evidence is merely insufficient or ambiguous",
                "the operation was intentionally not attempted",
                "top-level traversal failure",
            ],
        },
    }
    return {
        "stateOrder": list(REFERENCE_TRAVERSAL_DEFINED_STATES),
        "itemStateFields": [
            f"{REFERENCE_TRAVERSAL_FIELD_NODES}[].{REFERENCE_TRAVERSAL_NODE_FIELD_STATE}",
            f"{REFERENCE_TRAVERSAL_FIELD_EDGES}[].{REFERENCE_TRAVERSAL_EDGE_FIELD_STATE}",
        ],
        "stateSemantics": {
            state: state_semantics[state]
            for state in REFERENCE_TRAVERSAL_DEFINED_STATES
        },
        "topLevelStatusBoundary": {
            "field": REFERENCE_TRAVERSAL_FIELD_STATUS,
            "itemStatesDeriveStatus": False,
            "partialVersusFailedAggregationDefined": True,
            "failedItemAutomaticallyMakesTraversalFailed": False,
            "requiredEvidenceCompletenessThresholdsDefined": True,
            "malformedRequestFailureBehaviorChanged": False,
        },
        "helperBehavior": {
            "performsRealFreecadDiscoveryOrClassification": False,
            "enumeratesSupportedFreecadMechanisms": False,
            "createsDiagnostics": False,
            "payloadSchemaChanged": False,
            "serializesOutput": False,
            "engineNormalizationPerformed": False,
            "pdmBehaviorPerformed": False,
        },
    }


def build_reference_traversal_aggregate_status_semantics_contract() -> dict[str, Any]:
    """Return aggregate traversal status semantics without deriving a status."""
    status_semantics = {
        REFERENCE_TRAVERSAL_STATUS_SUCCEEDED: {
            "meaning": (
                "The aggregate traversal operation completed the required, "
                "contract-approved traversal scope and produced reliable raw "
                "evidence."
            ),
            "requirements": [
                "request validation succeeded",
                "the source document was opened sufficiently to perform the requested traversal",
                "all required contract-approved traversal work completed",
                "produced raw evidence is reliable",
            ],
            "validItemOutcomesThatDoNotAutomaticallyReduceStatus": [
                REFERENCE_TRAVERSAL_STATE_MISSING,
                REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
                REFERENCE_TRAVERSAL_STATE_SKIPPED,
            ],
            "skippedItemBoundary": (
                "A skipped item does not reduce aggregate status when the "
                "non-attempt is explicitly permitted by the declared contract "
                "or runtime boundary."
            ),
            "emptyGraphMaySucceed": True,
            "emptyGraphBoundary": (
                "A valid requested traversal that completed and deterministically "
                "found no references may succeed."
            ),
            "mustNotBeSelectedWhen": [
                "a required operation failed and made the requested evidence incomplete",
            ],
            "doesNotImply": [
                "Engine verification success",
                "complete product or PDM knowledge",
                "durable identity",
                "successful downstream normalization",
                "absence of missing, unresolved, or contract-permitted skipped items",
            ],
        },
        REFERENCE_TRAVERSAL_STATUS_PARTIAL: {
            "meaning": (
                "The valid traversal operation produced trustworthy, usable raw "
                "graph evidence but could not complete all required traversal work."
            ),
            "requirements": [
                "request validation succeeded",
                "the source document was opened sufficiently to begin traversal",
                "at least some reliable non-diagnostic graph evidence was retained, such as a trustworthy node or edge observation",
                "one or more required traversal or resolution operations failed, or a traversal-stage failure prevented completion",
                "retained evidence remains independently reliable",
                "incompleteness is explicit",
                "future emitted output is expected to include explainable diagnostic evidence",
            ],
            "failedItemBoundary": (
                "A failed item may contribute to partial when other trustworthy "
                "graph evidence remains; one failed item does not automatically "
                "force top-level failed."
            ),
            "notSelectedMerelyBecause": [
                "an item is missing",
                "an item is unresolved",
                "an item is contract-permitted skipped",
                "warnings or diagnostics are present",
            ],
            "excludedFailures": [
                "malformed or invalid traversal request",
                "source-document open failure",
                "output containment failure that prevents safe traversal-result emission",
                "output-write failure that prevents safe traversal-result emission",
            ],
            "diagnosticEvidenceAloneIsUsableGraphEvidence": False,
            "retainedEvidenceMayBeGuessedOrRewritten": False,
            "retainedEvidenceMayBeTreatedAsComplete": False,
        },
        REFERENCE_TRAVERSAL_STATUS_FAILED: {
            "meaning": (
                "The aggregate traversal operation did not produce a safely "
                "usable partial traversal result."
            ),
            "categories": [
                "malformed or invalid traversal request",
                "source-document open failure",
                "traversal failure before reliable graph evidence was established",
                "systemic or boundary failure that makes retained evidence unreliable",
                "failure where no trustworthy non-diagnostic graph evidence remains",
                "output containment failure that prevents safe traversal-result emission",
                "serialization failure that prevents safe traversal-result emission",
                "output-write failure that prevents safe traversal-result emission",
            ],
            "notSelectedMerelyBecause": [
                "a target is missing",
                "a relationship remains unresolved",
                "a permitted item was skipped",
                "a single item failed",
                "the graph is empty",
            ],
            "decisionBasis": [
                "operation stage",
                "evidence trustworthiness",
                "required-scope completion",
                "safe result availability",
            ],
            "notWorstItemStateAggregation": True,
        },
    }
    return {
        "statusOrder": [
            REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
            REFERENCE_TRAVERSAL_STATUS_PARTIAL,
            REFERENCE_TRAVERSAL_STATUS_FAILED,
        ],
        "statusSemantics": {
            status: status_semantics[status]
            for status in (
                REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
                REFERENCE_TRAVERSAL_STATUS_PARTIAL,
                REFERENCE_TRAVERSAL_STATUS_FAILED,
            )
        },
        "aggregateDecisionRules": {
            "itemStatesDeriveStatus": False,
            "severityMaximumOverItemStates": False,
            "nonReducingItemStates": [
                REFERENCE_TRAVERSAL_STATE_MISSING,
                REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
                REFERENCE_TRAVERSAL_STATE_SKIPPED,
            ],
            "nonReducingSkippedStateRequiresContractPermission": True,
            "failedItemWithOtherTrustworthyEvidenceMayBePartial": True,
            "noTrustworthyGraphEvidenceProducesFailed": True,
            "unusableResultProducesFailed": True,
            "preEvidenceBoundaryFailureProducesFailed": True,
            "completeRequiredScopeProcessingProducesSucceeded": True,
            "partialRequiresUsableRetainedGraphEvidence": True,
            "partialRequiresExplicitIncompleteness": True,
            "diagnosticPresenceOrCountDeterminesStatus": False,
            "nodeOrEdgeCountDeterminesStatus": False,
        },
        "completenessCriteria": {
            "semantic": True,
            "percentageOrNumericThresholdUsed": False,
            "basis": [
                "whether required contract-approved traversal work completed",
                "whether retained evidence is trustworthy",
            ],
        },
        "usableRetainedEvidence": {
            "requiresTrustworthyNonDiagnosticGraphEvidence": True,
            "examples": [
                "trustworthy node observation",
                "trustworthy edge observation",
            ],
            "diagnosticEvidenceAloneIsSufficient": False,
            "mustRemainIndependentlyReliable": True,
        },
        "dimensionSeparation": {
            "itemLevelStateSeparateFromTopLevelStatus": True,
            "failedItemAutomaticallyMakesTraversalFailed": False,
            "emptyGraphAutomaticallyMakesTraversalFailed": False,
        },
        "helperBehavior": {
            "metadataOnly": True,
            "performsRealFreecadTraversal": False,
            "derivesStatusFromRuntimeValues": False,
            "loadsRequests": False,
            "createsDiagnostics": False,
            "writesFiles": False,
            "implementsRuntimeClassificationOrWiring": False,
            "payloadSchemaChanged": False,
            "payloadBuilderBehaviorChanged": False,
            "engineVerificationOrNormalizationPerformed": False,
            "pdmBehaviorPerformed": False,
        },
    }


def build_reference_traversal_object_property_provenance_contract() -> dict[str, Any]:
    """Return raw object/property provenance requirements for future traversal."""
    return {
        "requirementNames": list(
            REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS
        ),
        "requirements": {
            REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE: {
                "semantics": (
                    "Descriptive FreeCAD/runtime object-type evidence observed "
                    "by the raw adapter."
                ),
                "logicalAssociation": "object node",
                "proposedRawEvidenceLocation": (
                    REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS[
                        REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE
                    ]
                ),
                "serializedInCurrentNodeDataclass": False,
            },
            REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY: {
                "semantics": (
                    "Stable source property name through which the relationship "
                    "was observed."
                ),
                "logicalAssociation": "edge observation",
                "separateFrom": [
                    "source object identity",
                    "edge kind",
                ],
                "proposedRawEvidenceLocation": (
                    REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS[
                        REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY
                    ]
                ),
                "serializedInCurrentEdgeDataclass": False,
            },
            REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM: {
                "semantics": (
                    "FreeCAD/runtime mechanism or API surface that exposed the "
                    "relationship."
                ),
                "logicalAssociation": "edge observation",
                "separateFrom": [
                    REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY,
                ],
                "proposedRawEvidenceLocation": (
                    REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS[
                        REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM
                    ]
                ),
                "serializedInCurrentEdgeDataclass": False,
            },
        },
        "distinctEvidenceConcepts": [
            "source object identity",
            REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY,
            REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM,
            "edge kind",
            "target evidence",
            "resolution state",
            "diagnostic evidence",
        ],
        "mustNotOverloadExistingFields": [
            "nodes[].id",
            "edges[].source",
            "edges[].target",
            "nodes[].kind",
            "edges[].kind",
            "nodes[].state",
            "edges[].state",
            "nodes[].label",
            "nodes[].documentPath",
            "nodes[].diagnostic",
            "edges[].diagnostic",
            "diagnostics[].code",
            "diagnostics[].message",
            "diagnostics[].stage",
        ],
        "ownership": {
            "rawAdapterObservedProvenanceRequirements": True,
            "engineNormalizedRecordFields": False,
            "pdmIdentityOrStorageDefined": False,
        },
        "compatibility": {
            "currentSchemaVersion": REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
            "presentInCurrentSchema": False,
            "serializedNodeOrEdgeIdsDefined": False,
            "participatesInSemanticIdentity": False,
            "participatesInDeduplication": False,
            "participatesInOrdering": False,
            "payloadSchemaChanged": False,
            "futureSerializedOutputDecisionRequired": (
                "Adding these requirements to serialized output requires a "
                "later explicit compatible or versioned contract-extension decision."
            ),
        },
        "missingValueEncodingSelected": False,
        "normalizationPerformed": False,
        "proposedLocationsAreActiveSerializedFields": False,
    }


def build_reference_traversal_malformed_request_failure_contract() -> dict[str, Any]:
    """Return deterministic failure semantics for malformed traversal requests."""
    return {
        "classification": REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_MALFORMED_REQUEST,
        "status": REFERENCE_TRAVERSAL_STATUS_FAILED,
        "diagnostic": {
            "severity": REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR,
            "code": REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_MALFORMED_REQUEST,
            "stage": REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION,
        },
        "failurePoint": REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION,
        "successfulTraversalPayloadEmitted": False,
        "realFreecadTraversalAttempted": False,
        "writerBehaviorDecided": False,
        "outputContainmentDecided": False,
        "engineNormalizationDecided": False,
        "pdmBehaviorDecided": False,
        "outOfScope": [
            "real_freecad_traversal",
            "traversal_writer",
            "traversal_output_path_containment",
            "engine_normalization",
            "pdm_persistence_or_query_behavior",
        ],
    }


def _serialize_node(
    sequence: int, node: RawReferenceTraversalNode
) -> dict[str, Any]:
    return {
        REFERENCE_TRAVERSAL_NODE_FIELD_SEQUENCE: sequence,
        REFERENCE_TRAVERSAL_NODE_FIELD_ID: _require_non_empty_string(node.id, "id"),
        REFERENCE_TRAVERSAL_NODE_FIELD_KIND: _require_non_empty_string(node.kind, "kind"),
        REFERENCE_TRAVERSAL_NODE_FIELD_STATE: _require_defined_traversal_state(
            node.state, "state"
        ),
        REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH: _require_optional_string(
            node.document_path, "documentPath"
        ),
        REFERENCE_TRAVERSAL_NODE_FIELD_OBJECT_NAME: _require_optional_string(
            node.object_name, "objectName"
        ),
        REFERENCE_TRAVERSAL_NODE_FIELD_LABEL: _require_optional_string(
            node.label, "label"
        ),
        REFERENCE_TRAVERSAL_NODE_FIELD_DIAGNOSTIC: _require_optional_string(
            node.diagnostic, "diagnostic"
        ),
    }


def _serialize_edge(
    sequence: int, edge: RawReferenceTraversalEdge
) -> dict[str, Any]:
    return {
        REFERENCE_TRAVERSAL_EDGE_FIELD_SEQUENCE: sequence,
        REFERENCE_TRAVERSAL_EDGE_FIELD_SOURCE: _require_non_empty_string(
            edge.source, "source"
        ),
        REFERENCE_TRAVERSAL_EDGE_FIELD_TARGET: _require_non_empty_string(
            edge.target, "target"
        ),
        REFERENCE_TRAVERSAL_EDGE_FIELD_KIND: _require_non_empty_string(edge.kind, "kind"),
        REFERENCE_TRAVERSAL_EDGE_FIELD_STATE: _require_defined_traversal_state(
            edge.state, "state"
        ),
        REFERENCE_TRAVERSAL_EDGE_FIELD_DIAGNOSTIC: _require_optional_string(
            edge.diagnostic, "diagnostic"
        ),
    }


def _serialize_diagnostic(
    sequence: int, diagnostic: RawReferenceTraversalDiagnostic
) -> dict[str, Any]:
    return {
        REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_SEQUENCE: sequence,
        REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_SEVERITY: _require_non_empty_string(
            diagnostic.severity, "severity"
        ),
        REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_CODE: _require_non_empty_string(
            diagnostic.code, "code"
        ),
        REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_MESSAGE: _require_non_empty_string(
            diagnostic.message, "message"
        ),
        REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_STAGE: _require_optional_string(
            diagnostic.stage, "stage"
        ),
    }


def build_reference_traversal_output_payload(
    *,
    boundary: str,
    operation: str,
    status: str,
    source_document: str,
    nodes: Sequence[RawReferenceTraversalNode],
    edges: Sequence[RawReferenceTraversalEdge],
    diagnostics: Sequence[RawReferenceTraversalDiagnostic] = (),
) -> dict[str, Any]:
    """Return the canonical raw reference traversal output payload shape.

    Does not write files or mutate the input sequences or dataclass instances.
    """
    boundary_value = _require_non_empty_string(boundary, "boundary")
    operation_value = _require_non_empty_string(operation, "operation")
    status_value = _require_non_empty_string(status, "status")
    source_document_value = _require_non_empty_string(
        source_document, "sourceDocument"
    )
    node_sequence = order_reference_traversal_nodes(nodes)
    edge_sequence = order_reference_traversal_edges(edges)
    diagnostic_sequence = order_reference_traversal_diagnostics(diagnostics)

    node_payloads: list[dict[str, Any]] = []
    for sequence, node in enumerate(node_sequence):
        node_payloads.append(_serialize_node(sequence, node))

    edge_payloads: list[dict[str, Any]] = []
    for sequence, edge in enumerate(edge_sequence):
        edge_payloads.append(_serialize_edge(sequence, edge))

    diagnostic_payloads: list[dict[str, Any]] = []
    for sequence, diagnostic in enumerate(diagnostic_sequence):
        diagnostic_payloads.append(_serialize_diagnostic(sequence, diagnostic))

    return {
        REFERENCE_TRAVERSAL_FIELD_SCHEMA_VERSION: REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
        REFERENCE_TRAVERSAL_FIELD_KIND: REFERENCE_TRAVERSAL_OUTPUT_KIND_RAW_REFERENCE_TRAVERSAL,
        REFERENCE_TRAVERSAL_FIELD_BOUNDARY: boundary_value,
        REFERENCE_TRAVERSAL_FIELD_OPERATION: operation_value,
        REFERENCE_TRAVERSAL_FIELD_STATUS: status_value,
        REFERENCE_TRAVERSAL_FIELD_SOURCE_DOCUMENT: source_document_value,
        REFERENCE_TRAVERSAL_FIELD_NODES: node_payloads,
        REFERENCE_TRAVERSAL_FIELD_EDGES: edge_payloads,
        REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS: diagnostic_payloads,
    }


def serialize_reference_traversal_output(
    *,
    boundary: str,
    operation: str,
    status: str,
    source_document: str,
    nodes: Sequence[RawReferenceTraversalNode],
    edges: Sequence[RawReferenceTraversalEdge],
    diagnostics: Sequence[RawReferenceTraversalDiagnostic] = (),
) -> bytes:
    """Return canonical UTF-8 traversal bytes with exactly one trailing LF.

    The authoritative payload builder performs validation, ordering, sequence
    assignment, and payload construction. This function does not write files
    or mutate the input sequences or dataclass instances.
    """
    payload = build_reference_traversal_output_payload(
        boundary=boundary,
        operation=operation,
        status=status,
        source_document=source_document,
        nodes=nodes,
        edges=edges,
        diagnostics=diagnostics,
    )
    return dumps_canonical(payload).encode("utf-8")


def build_malformed_reference_traversal_request_payload(
    *,
    boundary: str,
    operation: str,
    source_document: str,
    diagnostic_message: str,
) -> dict[str, Any]:
    """Return a failed raw payload for a caller-validated traversal request value."""
    return build_reference_traversal_output_payload(
        boundary=boundary,
        operation=operation,
        status=REFERENCE_TRAVERSAL_STATUS_FAILED,
        source_document=source_document,
        nodes=(),
        edges=(),
        diagnostics=(
            RawReferenceTraversalDiagnostic(
                severity=REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR,
                code=REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_MALFORMED_REQUEST,
                message=_require_non_empty_string(
                    diagnostic_message, "diagnosticMessage"
                ),
                stage=REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION,
            ),
        ),
    )


__all__ = [
    "REFERENCE_TRAVERSAL_BOUNDARY_ENGINE_INVOCATION",
    "REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT",
    "REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES",
    "REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS",
    "REFERENCE_TRAVERSAL_DEFINED_STATES",
    "REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_MALFORMED_REQUEST",
    "REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_UNSUPPORTED_REFERENCE_VALUE_SHAPE",
    "REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_CODE",
    "REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_MESSAGE",
    "REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_SEQUENCE",
    "REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_SEVERITY",
    "REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_STAGE",
    "REFERENCE_TRAVERSAL_DIAGNOSTIC_ORDER_FIELDS",
    "REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR",
    "REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_WARNING",
    "REFERENCE_TRAVERSAL_EMITTED_IDENTIFIER_FIELDS",
    "REFERENCE_TRAVERSAL_EMITTED_INLINE_DIAGNOSTIC_FIELDS",
    "REFERENCE_TRAVERSAL_EMITTED_LABEL_FIELDS",
    "REFERENCE_TRAVERSAL_EMITTED_OBJECT_NAME_FIELDS",
    "REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS",
    "REFERENCE_TRAVERSAL_EMITTED_RAW_EVIDENCE_FIELDS",
    "REFERENCE_TRAVERSAL_EMITTED_STRUCTURED_DIAGNOSTIC_FIELDS",
    "REFERENCE_TRAVERSAL_EDGE_FIELD_DIAGNOSTIC",
    "REFERENCE_TRAVERSAL_EDGE_FIELD_KIND",
    "REFERENCE_TRAVERSAL_EDGE_FIELD_SEQUENCE",
    "REFERENCE_TRAVERSAL_EDGE_FIELD_SOURCE",
    "REFERENCE_TRAVERSAL_EDGE_FIELD_STATE",
    "REFERENCE_TRAVERSAL_EDGE_FIELD_TARGET",
    "REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE",
    "REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE",
    "REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE",
    "REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS",
    "REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS",
    "REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS",
    "REFERENCE_TRAVERSAL_EXTERNAL_REFERENCE_EDGE_KINDS",
    "REFERENCE_TRAVERSAL_FIELD_BOUNDARY",
    "REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS",
    "REFERENCE_TRAVERSAL_FIELD_EDGES",
    "REFERENCE_TRAVERSAL_FIELD_KIND",
    "REFERENCE_TRAVERSAL_FIELD_NODES",
    "REFERENCE_TRAVERSAL_FIELD_OPERATION",
    "REFERENCE_TRAVERSAL_FIELD_SCHEMA_VERSION",
    "REFERENCE_TRAVERSAL_FIELD_SOURCE_DOCUMENT",
    "REFERENCE_TRAVERSAL_FIELD_STATUS",
    "REFERENCE_TRAVERSAL_INTERNAL_REFERENCE_EDGE_KINDS",
    "REFERENCE_TRAVERSAL_NODE_FIELD_DIAGNOSTIC",
    "REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH",
    "REFERENCE_TRAVERSAL_NODE_FIELD_ID",
    "REFERENCE_TRAVERSAL_NODE_FIELD_KIND",
    "REFERENCE_TRAVERSAL_NODE_FIELD_LABEL",
    "REFERENCE_TRAVERSAL_NODE_FIELD_OBJECT_NAME",
    "REFERENCE_TRAVERSAL_NODE_FIELD_SEQUENCE",
    "REFERENCE_TRAVERSAL_NODE_FIELD_STATE",
    "REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT",
    "REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT",
    "REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE",
    "REFERENCE_TRAVERSAL_NODE_KIND_OBJECT",
    "REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS",
    "REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS",
    "REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS",
    "REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL",
    "REFERENCE_TRAVERSAL_OUTPUT_KIND_RAW_REFERENCE_TRAVERSAL",
    "REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_POLICY",
    "REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_ROOT",
    "REFERENCE_TRAVERSAL_OUTPUT_PATH_PARENT_POLICY",
    "REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION",
    "REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS",
    "REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE",
    "REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM",
    "REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY",
    "REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS",
    "REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL",
    "REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT",
    "REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE",
    "REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_EXCLUDED_FIELDS",
    "REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS",
    "REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS",
    "REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS",
    "REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS",
    "REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND",
    "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_ACTORS",
    "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER",
    "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_PROCESS_RUNTIME_IDENTITIES",
    "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_REQUEST_IDS",
    "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS",
    "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS",
    "REFERENCE_TRAVERSAL_STATE_FAILED",
    "REFERENCE_TRAVERSAL_STATE_MISSING",
    "REFERENCE_TRAVERSAL_STATE_RESOLVED",
    "REFERENCE_TRAVERSAL_STATE_SKIPPED",
    "REFERENCE_TRAVERSAL_STATE_UNRESOLVED",
    "REFERENCE_TRAVERSAL_STATUS_FAILED",
    "REFERENCE_TRAVERSAL_STATUS_PARTIAL",
    "REFERENCE_TRAVERSAL_STATUS_SUCCEEDED",
    "REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION",
    "REFERENCE_TRAVERSAL_STAGE_REFERENCE_DISCOVERY",
    "REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES",
    "REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_EDGE",
    "REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_NODE",
    "REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_ORDER",
    "RawReferenceTraversalDiagnostic",
    "RawReferenceTraversalEdge",
    "RawReferenceTraversalNode",
    "ReferenceTraversalOutputContractError",
    "build_malformed_reference_traversal_request_payload",
    "build_reference_traversal_aggregate_status_semantics_contract",
    "build_reference_traversal_discovery_semantics_contract",
    "build_reference_traversal_diagnostic_order_key",
    "build_reference_traversal_edge_order_key",
    "build_reference_traversal_emitted_raw_evidence_contract",
    "build_reference_traversal_malformed_request_failure_contract",
    "build_reference_traversal_normalization_contract",
    "build_reference_traversal_output_containment_contract",
    "build_reference_traversal_output_payload",
    "build_reference_traversal_ordering_extension_contract",
    "build_reference_traversal_node_order_key",
    "build_reference_traversal_object_property_provenance_contract",
    "build_reference_traversal_reference_distinction_contract",
    "build_reference_traversal_runtime_state_semantics_contract",
    "build_reference_traversal_semantic_edge_identity_contract",
    "build_reference_traversal_semantic_edge_identity_key",
    "build_reference_traversal_semantic_node_identity_contract",
    "build_reference_traversal_semantic_node_identity_key",
    "build_reference_traversal_semantic_output_exclusion_contract",
    "build_reference_traversal_total_ordering_contract",
    "build_reference_traversal_unresolved_entry_order_key",
    "deduplicate_reference_traversal_semantic_edge_identity_keys",
    "order_reference_traversal_edges",
    "order_reference_traversal_diagnostics",
    "order_reference_traversal_nodes",
    "order_reference_traversal_unresolved_entries",
    "resolve_reference_traversal_output_path",
    "serialize_reference_traversal_output",
]
