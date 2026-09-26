"""Raw reference traversal output schema 1.0."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Sequence

from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.runtime.reference_traversal_output_contract import (
    REFERENCE_TRAVERSAL_OUTPUT_KIND_RAW_REFERENCE_TRAVERSAL,
    REFERENCE_TRAVERSAL_DEFINED_STATES,
    REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS,
    RawReferenceTraversalDiagnostic,
    ReferenceTraversalOutputContractError,
    build_reference_traversal_semantic_node_identity_key,
    order_reference_traversal_diagnostics,
)

REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION = "1.0"
REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS = (
    "documentPath", "kind", "id", "objectName", "objectType", "label", "state", "diagnostic"
)
REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS = (
    "source", "target", "kind", "sourceProperty", "referenceMechanism", "state", "diagnostic"
)


@dataclass(frozen=True, slots=True)
class RawReferenceTraversalNode:
    kind: str
    state: str
    document_path: str
    object_name: str | None = None
    object_type: str | None = None
    label: str | None = None
    diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class RawReferenceTraversalEdge:
    source: RawReferenceTraversalNode
    target: RawReferenceTraversalNode
    kind: str
    state: str
    source_property: str | None = None
    reference_mechanism: str | None = None
    diagnostic: str | None = None


def _optional(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ReferenceTraversalOutputContractError(
            f"{field_name} must be a non-empty string when provided"
        )
    return value


def _required(value: object, field_name: str) -> str:
    result = _optional(value, field_name)
    if result is None:
        raise ReferenceTraversalOutputContractError(
            f"{field_name} must be a non-empty string"
        )
    return result


def _state(value: object) -> str:
    result = _required(value, "state")
    if result not in REFERENCE_TRAVERSAL_DEFINED_STATES:
        raise ReferenceTraversalOutputContractError("state is not defined")
    return result


def build_reference_traversal_node_identity_key(
    node: RawReferenceTraversalNode,
) -> tuple[str, ...]:
    if not isinstance(node, RawReferenceTraversalNode):
        raise ReferenceTraversalOutputContractError(
            "node must be a RawReferenceTraversalNode"
        )
    return build_reference_traversal_semantic_node_identity_key(
        kind=node.kind,
        document_path=node.document_path,
        object_name=node.object_name,
    )


def build_reference_traversal_node_id(
    node: RawReferenceTraversalNode,
) -> str:
    identity_key = build_reference_traversal_node_identity_key(node)
    preimage = dumps_canonical(identity_key).encode("utf-8")
    return f"{node.kind}:{hashlib.sha256(preimage).hexdigest()}"


def build_reference_traversal_edge_identity_key(
    edge: RawReferenceTraversalEdge,
) -> tuple[tuple[str, ...], tuple[str, ...], str, str | None, str | None]:
    if not isinstance(edge, RawReferenceTraversalEdge):
        raise ReferenceTraversalOutputContractError(
            "edge must be a RawReferenceTraversalEdge"
        )
    kind = _required(edge.kind, "kind")
    if kind not in REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS:
        raise ReferenceTraversalOutputContractError("edge kind is not defined")
    return (
        build_reference_traversal_node_identity_key(edge.source),
        build_reference_traversal_node_identity_key(edge.target),
        kind,
        _optional(edge.source_property, "sourceProperty"),
        _optional(edge.reference_mechanism, "referenceMechanism"),
    )


def _optional_order(value: str | None) -> tuple[int, str]:
    return (0, "") if value is None else (1, value)


def _node_order(node: RawReferenceTraversalNode) -> tuple[Any, ...]:
    _state(node.state)
    return (
        node.document_path,
        node.kind,
        build_reference_traversal_node_id(node),
        _optional_order(node.object_name),
        _optional_order(_optional(node.object_type, "objectType")),
        _optional_order(_optional(node.label, "label")),
        node.state,
        _optional_order(_optional(node.diagnostic, "diagnostic")),
    )


def _edge_order(edge: RawReferenceTraversalEdge) -> tuple[Any, ...]:
    _state(edge.state)
    return (
        build_reference_traversal_node_id(edge.source),
        build_reference_traversal_node_id(edge.target),
        edge.kind,
        _optional_order(_optional(edge.source_property, "sourceProperty")),
        _optional_order(_optional(edge.reference_mechanism, "referenceMechanism")),
        edge.state,
        _optional_order(_optional(edge.diagnostic, "diagnostic")),
    )


def _deduplicate_edges(
    edges: Sequence[RawReferenceTraversalEdge],
) -> tuple[RawReferenceTraversalEdge, ...]:
    unique: dict[tuple[Any, ...], RawReferenceTraversalEdge] = {}
    for edge in edges:
        key = build_reference_traversal_edge_identity_key(edge)
        previous = unique.get(key)
        if previous is not None and previous != edge:
            raise ReferenceTraversalOutputContractError(
                "duplicate canonical edge identity has conflicting raw evidence"
            )
        unique[key] = edge
    return tuple(sorted(unique.values(), key=_edge_order))


def _deduplicate_nodes(
    nodes: Sequence[RawReferenceTraversalNode],
) -> tuple[RawReferenceTraversalNode, ...]:
    unique: dict[tuple[str, ...], RawReferenceTraversalNode] = {}
    for node in nodes:
        key = build_reference_traversal_node_identity_key(node)
        previous = unique.get(key)
        if previous is not None and previous != node:
            raise ReferenceTraversalOutputContractError(
                "duplicate canonical node identity has conflicting raw evidence"
            )
        unique[key] = node
    return tuple(sorted(unique.values(), key=_node_order))


def _deduplicate_diagnostics(
    diagnostics: Sequence[RawReferenceTraversalDiagnostic],
) -> tuple[RawReferenceTraversalDiagnostic, ...]:
    return order_reference_traversal_diagnostics(tuple(dict.fromkeys(diagnostics)))


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
    for name, value in (
        ("boundary", boundary),
        ("operation", operation),
        ("status", status),
        ("sourceDocument", source_document),
    ):
        if not isinstance(value, str) or not value:
            raise ReferenceTraversalOutputContractError(
                f"{name} must be a non-empty string"
            )
    ordered_nodes = _deduplicate_nodes(nodes)
    ordered_edges = _deduplicate_edges(edges)
    ordered_diagnostics = _deduplicate_diagnostics(diagnostics)
    return {
        "schemaVersion": REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
        "kind": REFERENCE_TRAVERSAL_OUTPUT_KIND_RAW_REFERENCE_TRAVERSAL,
        "boundary": boundary,
        "operation": operation,
        "status": status,
        "sourceDocument": source_document,
        "nodes": [
            {
                "sequence": sequence,
                "id": build_reference_traversal_node_id(node),
                "kind": node.kind,
                "state": node.state,
                "documentPath": node.document_path,
                "objectName": node.object_name,
                "objectType": _optional(node.object_type, "objectType"),
                "label": _optional(node.label, "label"),
                "diagnostic": _optional(node.diagnostic, "diagnostic"),
            }
            for sequence, node in enumerate(ordered_nodes)
        ],
        "edges": [
            {
                "sequence": sequence,
                "source": build_reference_traversal_node_id(edge.source),
                "target": build_reference_traversal_node_id(edge.target),
                "kind": edge.kind,
                "sourceProperty": _optional(edge.source_property, "sourceProperty"),
                "referenceMechanism": _optional(
                    edge.reference_mechanism, "referenceMechanism"
                ),
                "state": edge.state,
                "diagnostic": _optional(edge.diagnostic, "diagnostic"),
            }
            for sequence, edge in enumerate(ordered_edges)
        ],
        "diagnostics": [
            {
                "sequence": sequence,
                "severity": diagnostic.severity,
                "code": diagnostic.code,
                "message": diagnostic.message,
                "stage": diagnostic.stage,
            }
            for sequence, diagnostic in enumerate(ordered_diagnostics)
        ],
    }


def serialize_reference_traversal_output(**kwargs: Any) -> bytes:
    return dumps_canonical(
        build_reference_traversal_output_payload(**kwargs)
    ).encode("utf-8")


__all__ = [
    "REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION",
    "REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS",
    "REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS",
    "RawReferenceTraversalEdge",
    "RawReferenceTraversalNode",
    "build_reference_traversal_edge_identity_key",
    "build_reference_traversal_node_id",
    "build_reference_traversal_node_identity_key",
    "build_reference_traversal_output_payload",
    "serialize_reference_traversal_output",
]
