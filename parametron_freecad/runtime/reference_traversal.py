"""Typed runtime boundary for FreeCAD reference traversal execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.runtime.reference_traversal_output_contract import (
    REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_UNSUPPORTED_REFERENCE_VALUE_SHAPE,
    REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_WARNING,
    REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
    REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
    REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
    REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
    REFERENCE_TRAVERSAL_STATE_RESOLVED,
    REFERENCE_TRAVERSAL_STATE_MISSING,
    REFERENCE_TRAVERSAL_STATUS_FAILED,
    REFERENCE_TRAVERSAL_STATUS_PARTIAL,
    REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
    REFERENCE_TRAVERSAL_STAGE_REFERENCE_DISCOVERY,
    RawReferenceTraversalDiagnostic,
    order_reference_traversal_diagnostics,
)
from parametron_freecad.runtime.reference_traversal_request import (
    REFERENCE_TRAVERSAL_REQUEST_SCHEMA_VERSION,
    ReferenceTraversalExternalTarget,
    ReferenceTraversalRequest,
    _external_target_key,
    _normalize_external_target,
    _validate_external_target_conflicts,
)
from parametron_freecad.runtime.reference_traversal_output import (
    RawReferenceTraversalEdge,
    RawReferenceTraversalNode,
    build_reference_traversal_edge_identity_key,
    build_reference_traversal_node_id,
    build_reference_traversal_node_identity_key,
)

REFERENCE_TRAVERSAL_EXECUTION_STATUSES = (
    REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
    REFERENCE_TRAVERSAL_STATUS_PARTIAL,
    REFERENCE_TRAVERSAL_STATUS_FAILED,
)

_SUPPORTED_REFERENCE_PROPERTY_TYPE_IDS = (
    "App::PropertyLink",
    "App::PropertyLinkChild",
    "App::PropertyLinkGlobal",
    "App::PropertyLinkHidden",
    "App::PropertyLinkList",
    "App::PropertyLinkListChild",
    "App::PropertyLinkListGlobal",
    "App::PropertyLinkListHidden",
    "App::PropertyLinkSub",
    "App::PropertyLinkSubChild",
    "App::PropertyLinkSubGlobal",
    "App::PropertyLinkSubHidden",
    "App::PropertyLinkSubList",
    "App::PropertyLinkSubListChild",
    "App::PropertyLinkSubListGlobal",
    "App::PropertyLinkSubListHidden",
    "App::PropertyXLink",
    "App::PropertyXLinkList",
    "App::PropertyXLinkSub",
    "App::PropertyXLinkSubHidden",
    "App::PropertyXLinkSubList",
)
_RECOGNIZED_UNSUPPORTED_REFERENCE_PROPERTY_TYPE_IDS: tuple[str, ...] = ()


class ReferenceTraversalExecutionError(RuntimeError):
    """Raised when traversal cannot produce a valid typed execution result."""


@dataclass(frozen=True, slots=True)
class ReferenceTraversalExecutionResult:
    """Immutable raw runtime evidence returned by reference traversal."""

    status: str
    nodes: tuple[RawReferenceTraversalNode, ...]
    edges: tuple[RawReferenceTraversalEdge, ...]
    diagnostics: tuple[RawReferenceTraversalDiagnostic, ...]

    def __post_init__(self) -> None:
        try:
            _validate_execution_result(self)
            _canonicalize_execution_result(self)
        except ValueError as exc:
            raise ReferenceTraversalExecutionError(str(exc)) from exc


def _validate_execution_result(result: ReferenceTraversalExecutionResult) -> None:
    if result.status not in REFERENCE_TRAVERSAL_EXECUTION_STATUSES:
        raise ValueError(
            "status must use the documented reference traversal vocabulary"
        )
    _require_typed_tuple(
        result.nodes, RawReferenceTraversalNode, "nodes"
    )
    _require_typed_tuple(
        result.edges, RawReferenceTraversalEdge, "edges"
    )
    _require_typed_tuple(
        result.diagnostics,
        RawReferenceTraversalDiagnostic,
        "diagnostics",
    )
    for diagnostic in result.diagnostics:
        if _contains_python_stack_trace(diagnostic.message):
            raise ValueError(
                "diagnostics must not contain an uncontracted raw stack trace"
            )


def _require_typed_tuple(value: object, item_type: type | tuple[type, ...], field_name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{field_name} must be a tuple")
    if not all(isinstance(item, item_type) for item in value):
        raise ValueError(f"{field_name} contains an invalid raw evidence item")


def _canonicalize_execution_result(result: ReferenceTraversalExecutionResult) -> None:
    nodes = tuple(sorted(_deduplicate_nodes(result.nodes), key=_node_order))
    edges = tuple(sorted(_deduplicate_edges(result.edges), key=_edge_order))
    diagnostics = order_reference_traversal_diagnostics(
        tuple(dict.fromkeys(result.diagnostics))
    )
    object.__setattr__(result, "nodes", nodes)
    object.__setattr__(result, "edges", edges)
    object.__setattr__(result, "diagnostics", diagnostics)


def _deduplicate_edges(
    edges: tuple[RawReferenceTraversalEdge, ...],
) -> tuple[RawReferenceTraversalEdge, ...]:
    unique: dict[tuple[Any, ...], RawReferenceTraversalEdge] = {}
    for edge in edges:
        identity = build_reference_traversal_edge_identity_key(edge)
        previous = unique.get(identity)
        if previous is not None and previous != edge:
            raise ValueError(
                "duplicate canonical edge identity has conflicting raw evidence"
            )
        unique[identity] = edge
    return tuple(unique.values())


def _deduplicate_nodes(
    nodes: tuple[RawReferenceTraversalNode, ...],
) -> tuple[RawReferenceTraversalNode, ...]:
    unique: dict[tuple[str, ...], RawReferenceTraversalNode] = {}
    for node in nodes:
        identity = build_reference_traversal_node_identity_key(node)
        previous = unique.get(identity)
        if previous is not None and previous != node:
            raise ValueError(
                "duplicate canonical node identity has conflicting raw evidence"
            )
        unique[identity] = node
    return tuple(unique.values())


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _contains_python_stack_trace(message: object) -> bool:
    if not isinstance(message, str):
        return False
    return "Traceback (most recent call last):" in message


def _optional_observed_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _object_node(value: Any, source_document: str) -> RawReferenceTraversalNode:
    return RawReferenceTraversalNode(
        kind=REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
        state=REFERENCE_TRAVERSAL_STATE_RESOLVED,
        document_path=source_document,
        object_name=_require_non_empty_string(
            getattr(value, "Name", None), "object Name"
        ),
        object_type=_optional_observed_string(getattr(value, "TypeId", None)),
        label=_optional_observed_string(getattr(value, "Label", None)),
    )


def _mapped_external_node(
    mapping: ReferenceTraversalExternalTarget,
    *,
    state: str,
    observed: Any | None = None,
) -> RawReferenceTraversalNode:
    return RawReferenceTraversalNode(
        kind=REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
        state=state,
        document_path=mapping.target_document_path,
        object_name=mapping.target_object_name,
        object_type=(
            _optional_observed_string(getattr(observed, "TypeId", None))
            if observed is not None else None
        ),
        label=(
            _optional_observed_string(getattr(observed, "Label", None))
            if observed is not None else None
        ),
    )


def _is_document_object(value: object) -> bool:
    return hasattr(value, "Name") and hasattr(value, "Document")


def _classify_reference_targets(value: object) -> tuple[bool, tuple[Any, ...]]:
    if value is None:
        return True, ()
    if _is_document_object(value):
        return True, (value,)
    if (
        isinstance(value, tuple)
        and len(value) == 2
        and _is_document_object(value[0])
        and isinstance(value[1], (str, list, tuple))
    ):
        return True, (value[0],)
    if isinstance(value, (list, tuple)):
        targets: list[Any] = []
        for item in value:
            supported, item_targets = _classify_reference_targets(item)
            if not supported:
                return False, ()
            targets.extend(item_targets)
        return True, tuple(targets)
    return False, ()


def _compact_coordinate(*values: str) -> str:
    return dumps_canonical(values).removesuffix("\n")


def _optional_order(value: str | None) -> tuple[int, str]:
    return (0, "") if value is None else (1, value)


def _node_order(node: RawReferenceTraversalNode) -> tuple[Any, ...]:
    return (
        node.document_path,
        node.kind,
        build_reference_traversal_node_id(node),
        _optional_order(node.object_name),
        _optional_order(node.object_type),
        _optional_order(node.label),
        node.state,
        _optional_order(node.diagnostic),
    )


def _edge_order(edge: RawReferenceTraversalEdge) -> tuple[Any, ...]:
    return (
        build_reference_traversal_node_id(edge.source),
        build_reference_traversal_node_id(edge.target),
        edge.kind,
        _optional_order(edge.source_property),
        _optional_order(edge.reference_mechanism),
        edge.state,
        _optional_order(edge.diagnostic),
    )


def _execute_reference_traversal(
    document: Any,
    request: ReferenceTraversalRequest,
    *,
    working_copy: Path,
    source_document: str,
    source_document_path: Path,
) -> ReferenceTraversalExecutionResult:
    """Discover the opened source document as the traversal graph root."""

    del working_copy, source_document_path
    label = getattr(document, "Label", None)
    if not isinstance(label, str) or not label:
        label = None
    source_node = RawReferenceTraversalNode(
        kind=REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
        state=REFERENCE_TRAVERSAL_STATE_RESOLVED,
        document_path=source_document,
        label=label,
    )
    participating_nodes: dict[str, RawReferenceTraversalNode] = {}
    edges_by_identity: dict[tuple[Any, ...], RawReferenceTraversalEdge] = {}
    diagnostics_by_identity: dict[
        tuple[str | None, str, str, str], RawReferenceTraversalDiagnostic
    ] = {}
    visited_source_object_names: set[str] = set()
    mappings_by_property: dict[
        tuple[str, str, str], tuple[ReferenceTraversalExternalTarget, ...]
    ] = {}
    for mapping in getattr(request, "external_targets", ()):
        key = (
            mapping.source_object_name,
            mapping.source_property,
            mapping.reference_mechanism,
        )
        mappings_by_property[key] = (*mappings_by_property.get(key, ()), mapping)

    def retain_node(node: RawReferenceTraversalNode) -> None:
        node_id = build_reference_traversal_node_id(node)
        previous = participating_nodes.get(node_id)
        if previous is not None and previous != node:
            raise ValueError("duplicate object identity has conflicting raw evidence")
        participating_nodes[node_id] = node

    def retain_edge(edge: RawReferenceTraversalEdge) -> None:
        edge_identity = build_reference_traversal_edge_identity_key(edge)
        previous_edge = edges_by_identity.get(edge_identity)
        if previous_edge is not None and previous_edge != edge:
            raise ValueError("duplicate edge identity has conflicting raw evidence")
        edges_by_identity[edge_identity] = edge

    def retain_diagnostic(diagnostic: RawReferenceTraversalDiagnostic) -> None:
        identity = (
            diagnostic.stage,
            diagnostic.severity,
            diagnostic.code,
            diagnostic.message,
        )
        diagnostics_by_identity[identity] = diagnostic

    for source_object in getattr(document, "Objects", ()):
        source_object_name = _require_non_empty_string(
            getattr(source_object, "Name", None), "object Name"
        )
        if source_object_name in visited_source_object_names:
            continue
        visited_source_object_names.add(source_object_name)
        for property_name in getattr(source_object, "PropertiesList", ()):
            mechanism = source_object.getTypeIdOfProperty(property_name)
            if mechanism not in _SUPPORTED_REFERENCE_PROPERTY_TYPE_IDS:
                continue
            property_value = source_object.getPropertyByName(property_name)
            supported_shape, targets = _classify_reference_targets(property_value)
            if not supported_shape:
                retain_diagnostic(
                    RawReferenceTraversalDiagnostic(
                        severity=REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_WARNING,
                        code=(
                            REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_UNSUPPORTED_REFERENCE_VALUE_SHAPE
                        ),
                        message=_compact_coordinate(
                            source_object_name, property_name, mechanism
                        ),
                        stage=REFERENCE_TRAVERSAL_STAGE_REFERENCE_DISCOVERY,
                    )
                )
                continue
            mappings = mappings_by_property.get(
                (source_object_name, property_name, mechanism), ()
            )
            external_by_name: dict[str, list[Any]] = {}
            for target_object in targets:
                if getattr(target_object, "Document", None) is not document:
                    target_name = _require_non_empty_string(
                        getattr(target_object, "Name", None), "external target Name"
                    )
                    external_by_name.setdefault(target_name, []).append(target_object)
            for mapping in mappings:
                candidates = external_by_name.get(mapping.target_object_name, [])
                if len(candidates) > 1:
                    raise ValueError(
                        "ambiguous_reference_target: "
                        f"{_compact_coordinate(*_external_target_key(mapping)[:4])}"
                    )
                state = (
                    REFERENCE_TRAVERSAL_STATE_RESOLVED
                    if candidates else REFERENCE_TRAVERSAL_STATE_MISSING
                )
                source_object_node = _object_node(source_object, source_document)
                target_object_node = _mapped_external_node(
                    mapping,
                    state=state,
                    observed=candidates[0] if candidates else None,
                )
                retain_node(source_object_node)
                retain_node(target_object_node)
                retain_edge(RawReferenceTraversalEdge(
                    source=source_object_node,
                    target=target_object_node,
                    kind=REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
                    state=state,
                    source_property=property_name,
                    reference_mechanism=mechanism,
                ))
            for target_object in targets:
                if getattr(target_object, "Document", None) is not document:
                    continue
                source_object_node = _object_node(source_object, source_document)
                target_object_node = _object_node(target_object, source_document)
                for object_node in (source_object_node, target_object_node):
                    retain_node(object_node)
                edge = RawReferenceTraversalEdge(
                    source=source_object_node,
                    target=target_object_node,
                    kind=REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                    state=REFERENCE_TRAVERSAL_STATE_RESOLVED,
                    source_property=_require_non_empty_string(
                        property_name, "property name"
                    ),
                    reference_mechanism=mechanism,
                )
                retain_edge(edge)

    nodes = tuple(sorted((source_node, *participating_nodes.values()), key=_node_order))
    edges = tuple(sorted(edges_by_identity.values(), key=_edge_order))
    return ReferenceTraversalExecutionResult(
        status=(
            REFERENCE_TRAVERSAL_STATUS_PARTIAL
            if diagnostics_by_identity
            else REFERENCE_TRAVERSAL_STATUS_SUCCEEDED
        ),
        nodes=nodes,
        edges=edges,
        diagnostics=tuple(diagnostics_by_identity.values()),
    )


def run_reference_traversal(
    document: Any,
    request: ReferenceTraversalRequest,
    *,
    working_copy: Path,
    source_document: str,
    source_document_path: Path,
) -> ReferenceTraversalExecutionResult:
    """Execute CAD-native traversal and return typed raw runtime evidence.

    Serialization, file writing, containment enforcement, Engine normalization,
    and PDM behavior are outside this callable.
    """

    try:
        if document is None:
            raise ValueError("document must not be None")
        if not isinstance(request, ReferenceTraversalRequest):
            raise ValueError("request must be a ReferenceTraversalRequest")
        if request.schema_version != REFERENCE_TRAVERSAL_REQUEST_SCHEMA_VERSION:
            raise ValueError("request schema_version is unsupported")
        external_targets = getattr(request, "external_targets", ())
        if not isinstance(external_targets, tuple):
            raise ValueError("request external_targets must be a tuple")
        normalized_targets = tuple(
            _normalize_external_target(
                {
                    "sourceObjectName": value.source_object_name,
                    "sourceProperty": value.source_property,
                    "referenceMechanism": value.reference_mechanism,
                    "targetObjectName": value.target_object_name,
                    "targetDocumentPath": value.target_document_path,
                },
                index,
            )
            for index, value in enumerate(external_targets)
        )
        _validate_external_target_conflicts(
            tuple(sorted(normalized_targets, key=_external_target_key))
        )
        if not isinstance(working_copy, Path):
            raise ValueError("working_copy must be a Path")
        _require_non_empty_string(source_document, "source_document")
        if not isinstance(source_document_path, Path):
            raise ValueError("source_document_path must be a Path")

        result = _execute_reference_traversal(
            document,
            request,
            working_copy=working_copy,
            source_document=source_document,
            source_document_path=source_document_path,
        )
        if not isinstance(result, ReferenceTraversalExecutionResult):
            raise ValueError(
                "traversal implementation must return "
                "ReferenceTraversalExecutionResult"
            )
        return result
    except ReferenceTraversalExecutionError:
        raise
    except Exception as exc:
        raise ReferenceTraversalExecutionError(
            f"reference traversal execution failed: {exc}"
        ) from exc


__all__ = [
    "REFERENCE_TRAVERSAL_EXECUTION_STATUSES",
    "ReferenceTraversalExecutionError",
    "ReferenceTraversalExecutionResult",
    "run_reference_traversal",
]
