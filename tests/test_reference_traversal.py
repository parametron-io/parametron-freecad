from __future__ import annotations

import builtins
import importlib
import inspect
import sys
import unittest
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from unittest import mock

from parametron_freecad.runtime import reference_traversal as traversal
from parametron_freecad.runtime.reference_traversal_output_contract import (
    RawReferenceTraversalDiagnostic,
    RawReferenceTraversalEdge,
    RawReferenceTraversalNode,
)
from parametron_freecad.runtime.reference_traversal_request import (
    ReferenceTraversalExternalTarget,
    ReferenceTraversalRequest,
)
from parametron_freecad.runtime.reference_traversal_output import (
    RawReferenceTraversalEdge as CanonicalReferenceTraversalEdge,
    RawReferenceTraversalNode as CanonicalReferenceTraversalNode,
    build_reference_traversal_node_id,
    build_reference_traversal_output_payload,
    serialize_reference_traversal_output,
)


class _TraversalObject:
    def __init__(
        self, name, *, label=None, type_id="PartDesign::Feature", properties=()
    ):
        self.Name = name
        self.Label = label
        self.TypeId = type_id
        self._properties = dict(properties)
        self.PropertiesList = [name for name, _ in properties]
        self.Document = None
        self.property_reads = 0

    def getTypeIdOfProperty(self, name):
        return self._properties[name][0]

    def getPropertyByName(self, name):
        self.property_reads += 1
        return self._properties[name][1]


class _TraversalDocument:
    def __init__(self, objects=(), *, label="Assembly label"):
        self.Label = label
        self.Objects = list(objects)
        for value in self.Objects:
            value.Document = self


class ReferenceTraversalBoundaryTests(unittest.TestCase):
    def _request(self) -> ReferenceTraversalRequest:
        return ReferenceTraversalRequest(schema_version="1.0", external_targets=())

    def _mapped_request(self, *targets) -> ReferenceTraversalRequest:
        return ReferenceTraversalRequest(
            schema_version="1.0", external_targets=tuple(targets)
        )

    def _mapping(
        self,
        target="ExternalTarget",
        *,
        source="Source",
        property_name="Link",
        mechanism="App::PropertyXLink",
        path="references/external.FCStd",
    ) -> ReferenceTraversalExternalTarget:
        return ReferenceTraversalExternalTarget(
            source_object_name=source,
            source_property=property_name,
            reference_mechanism=mechanism,
            target_object_name=target,
            target_document_path=path,
        )

    def _kwargs(self) -> dict:
        return {
            "working_copy": Path("/runtime/root"),
            "source_document": "assembly.FCStd",
            "source_document_path": Path("/runtime/root/assembly.FCStd"),
        }

    def _result(self, status: str = "succeeded") -> traversal.ReferenceTraversalExecutionResult:
        return traversal.ReferenceTraversalExecutionResult(
            status=status,
            nodes=(
                CanonicalReferenceTraversalNode(

                    kind="document",
                    state="resolved",
                    document_path="assembly.FCStd",
                ),
            ),
            edges=(),
            diagnostics=(),
        )

    def test_public_exports_are_exact(self) -> None:
        self.assertEqual(
            set(traversal.__all__),
            {
                "REFERENCE_TRAVERSAL_EXECUTION_STATUSES",
                "ReferenceTraversalExecutionError",
                "ReferenceTraversalExecutionResult",
                "run_reference_traversal",
            },
        )

    def test_callable_signature_is_exact(self) -> None:
        signature = inspect.signature(traversal.run_reference_traversal)
        self.assertEqual(
            tuple(signature.parameters),
            (
                "document",
                "request",
                "working_copy",
                "source_document",
                "source_document_path",
            ),
        )
        self.assertEqual(
            signature.parameters["working_copy"].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertEqual(
            signature.parameters["source_document"].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertEqual(
            signature.parameters["source_document_path"].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )

    def test_result_has_only_approved_immutable_fields(self) -> None:
        result = self._result()
        self.assertEqual(
            tuple(field.name for field in fields(result)),
            ("status", "nodes", "edges", "diagnostics"),
        )
        with self.assertRaises(FrozenInstanceError):
            result.status = "failed"  # type: ignore[misc]

    def test_status_vocabulary_is_exact_and_each_status_is_representable(self) -> None:
        self.assertEqual(
            traversal.REFERENCE_TRAVERSAL_EXECUTION_STATUSES,
            ("succeeded", "partial", "failed"),
        )
        for status in traversal.REFERENCE_TRAVERSAL_EXECUTION_STATUSES:
            with self.subTest(status=status):
                self.assertEqual(self._result(status).status, status)

    def test_supported_reference_property_type_ids_match_runtime_probe(self) -> None:
        self.assertEqual(
            traversal._SUPPORTED_REFERENCE_PROPERTY_TYPE_IDS,
            (
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
            ),
        )

    def test_external_path_probe_matrix_covers_every_supported_mechanism(self) -> None:
        link_types = traversal._SUPPORTED_REFERENCE_PROPERTY_TYPE_IDS[:16]
        xlink_types = traversal._SUPPORTED_REFERENCE_PROPERTY_TYPE_IDS[16:]
        matrix = {
            mechanism: {
                "resolved": "cross_document_assignment_rejected",
                "missing": "no_target_identity",
                "unresolved": "no_target_identity",
                "originalPath": None,
                "relocationStablePath": None,
            }
            for mechanism in link_types
        }
        matrix.update(
            {
                mechanism: {
                    "resolved": "object_shape_plus_resolved_absolute_FileName",
                    "missing": "no_target_identity",
                    "unresolved": "no_target_identity",
                    "originalPath": None,
                    "relocationStablePath": None,
                }
                for mechanism in xlink_types
            }
        )

        self.assertEqual(tuple(matrix), traversal._SUPPORTED_REFERENCE_PROPERTY_TYPE_IDS)
        self.assertTrue(
            all(evidence["originalPath"] is None for evidence in matrix.values())
        )
        self.assertTrue(
            all(
                evidence["relocationStablePath"] is None
                for evidence in matrix.values()
            )
        )
        self.assertEqual(len(link_types), 16)
        self.assertEqual(len(xlink_types), 5)

    def test_partial_and_failed_evidence_return_through_result(self) -> None:
        diagnostic = RawReferenceTraversalDiagnostic(
            severity="error",
            code="reference_unavailable",
            message="target could not be resolved",
            stage="traversal",
        )
        source = CanonicalReferenceTraversalNode("object", "resolved", "assembly.FCStd", "Source")
        target = CanonicalReferenceTraversalNode("object", "unresolved", "assembly.FCStd", "Target")
        edge = CanonicalReferenceTraversalEdge(
            source=source,
            target=target,
            kind="external_document_reference",
            state="unresolved",
            diagnostic="target could not be resolved",
        )
        for status in ("partial", "failed"):
            with self.subTest(status=status):
                result = traversal.ReferenceTraversalExecutionResult(
                    status=status,
                    nodes=(source, target),
                    edges=(edge,),
                    diagnostics=(diagnostic,),
                )
                with mock.patch.object(
                    traversal, "_execute_reference_traversal", return_value=result
                ):
                    returned = traversal.run_reference_traversal(
                        object(), self._request(), **self._kwargs()
                    )
                self.assertIs(returned, result)

    def test_canonical_raw_node_tuple_is_representable(self) -> None:
        node = CanonicalReferenceTraversalNode(
            kind="object",
            state="resolved",
            document_path="assembly.FCStd",
            object_name="Bolt",
            object_type="PartDesign::Feature",
        )
        result = traversal.ReferenceTraversalExecutionResult(
            status="succeeded", nodes=(node,), edges=(), diagnostics=()
        )
        self.assertIs(result.nodes[0], node)

    def test_typed_result_canonicalizes_canonical_missing_unresolved_evidence(self) -> None:
        missing = CanonicalReferenceTraversalNode(
            kind="object", state="missing", document_path="refs/a.FCStd",
            object_name="A",
        )
        unresolved = CanonicalReferenceTraversalNode(
            kind="object", state="unresolved", document_path="refs/b.FCStd",
            object_name="B",
        )
        missing_edge = CanonicalReferenceTraversalEdge(
            source=missing, target=unresolved,
            kind="external_document_reference", state="missing",
            source_property="A", reference_mechanism="App::PropertyXLinkList",
        )
        unresolved_edge = CanonicalReferenceTraversalEdge(
            source=unresolved, target=missing,
            kind="external_document_reference", state="unresolved",
            source_property="B", reference_mechanism="App::PropertyXLinkList",
        )
        forward = traversal.ReferenceTraversalExecutionResult(
            status="succeeded", nodes=(missing, unresolved),
            edges=(missing_edge, unresolved_edge), diagnostics=(),
        )
        reverse = traversal.ReferenceTraversalExecutionResult(
            status="succeeded", nodes=(unresolved, missing),
            edges=(unresolved_edge, missing_edge), diagnostics=(),
        )
        self.assertEqual(reverse, forward)

    def test_canonical_equal_edges_collapse_for_every_evidence_state(self) -> None:
        source = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source",
        )
        for state in ("resolved", "missing", "unresolved"):
            with self.subTest(state=state):
                target = CanonicalReferenceTraversalNode(
                    kind="object", state=state, document_path="refs/part.FCStd",
                    object_name="Target",
                )
                edge = CanonicalReferenceTraversalEdge(
                    source=source, target=target,
                    kind="external_document_reference", state=state,
                    source_property="Parts",
                    reference_mechanism="App::PropertyXLinkList",
                )
                result = traversal.ReferenceTraversalExecutionResult(
                    status="succeeded", nodes=(source, target),
                    edges=(edge, edge), diagnostics=(),
                )
                self.assertEqual(result.edges, (edge,))

    def test_canonical_duplicates_separated_by_other_evidence_collapse(self) -> None:
        source = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source",
        )
        first_target = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="refs/a.FCStd",
            object_name="A",
        )
        second_target = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="refs/b.FCStd",
            object_name="B",
        )
        first = CanonicalReferenceTraversalEdge(
            source, first_target, "external_document_reference", "resolved",
            "Parts", "App::PropertyXLinkList",
        )
        second = CanonicalReferenceTraversalEdge(
            source, second_target, "external_document_reference", "resolved",
            "Parts", "App::PropertyXLinkList",
        )
        result = traversal.ReferenceTraversalExecutionResult(
            status="succeeded", nodes=(source, first_target, second_target),
            edges=(first, second, first), diagnostics=(),
        )
        self.assertEqual(len(result.edges), 2)
        self.assertEqual(set(result.edges), {first, second})

    def test_canonical_complete_identity_preserves_every_distinct_component(self) -> None:
        source_a = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="SourceA",
        )
        source_b = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="SourceB",
        )
        source_other_document = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="other.FCStd",
            object_name="SourceA",
        )
        target_a = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="refs/a.FCStd",
            object_name="Target",
        )
        target_b = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="refs/b.FCStd",
            object_name="Target",
        )
        edges = (
            CanonicalReferenceTraversalEdge(source_a, target_a, "external_document_reference", "resolved", "First", "App::PropertyXLink"),
            CanonicalReferenceTraversalEdge(source_b, target_a, "external_document_reference", "resolved", "First", "App::PropertyXLink"),
            CanonicalReferenceTraversalEdge(source_other_document, target_a, "external_document_reference", "resolved", "First", "App::PropertyXLink"),
            CanonicalReferenceTraversalEdge(source_a, target_b, "external_document_reference", "resolved", "First", "App::PropertyXLink"),
            CanonicalReferenceTraversalEdge(source_a, target_a, "external_document_reference", "resolved", "Second", "App::PropertyXLink"),
            CanonicalReferenceTraversalEdge(source_a, target_a, "external_document_reference", "resolved", "First", "App::PropertyXLinkSub"),
            CanonicalReferenceTraversalEdge(source_a, target_a, "document_internal_reference", "resolved", "First", "App::PropertyXLink"),
        )
        result = traversal.ReferenceTraversalExecutionResult(
            status="succeeded",
            nodes=(source_a, source_b, source_other_document, target_a, target_b),
            edges=tuple(reversed(edges)), diagnostics=(),
        )
        self.assertEqual(len(result.edges), len(edges))
        self.assertEqual(set(result.edges), set(edges))

    def test_canonical_identity_conflict_fails_deterministically_with_chaining(self) -> None:
        source = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source",
        )
        target = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="refs/a.FCStd",
            object_name="Target",
        )
        resolved = CanonicalReferenceTraversalEdge(
            source, target, "external_document_reference", "resolved",
            "Parts", "App::PropertyXLinkList",
        )
        conflicting = CanonicalReferenceTraversalEdge(
            source, target, "external_document_reference", "missing",
            "Parts", "App::PropertyXLinkList",
        )
        source_with_conflicting_label = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source", label="different evidence",
        )
        conflicting_endpoint = CanonicalReferenceTraversalEdge(
            source_with_conflicting_label, target,
            "external_document_reference", "resolved",
            "Parts", "App::PropertyXLinkList",
        )
        for edges in (
            (resolved, conflicting),
            (conflicting, resolved),
            (resolved, conflicting_endpoint),
        ):
            with self.assertRaisesRegex(
                traversal.ReferenceTraversalExecutionError,
                "duplicate canonical edge identity has conflicting raw evidence",
            ) as caught:
                traversal.ReferenceTraversalExecutionResult(
                    status="succeeded", nodes=(source, target),
                    edges=edges, diagnostics=(),
                )
            self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_canonical_equal_nodes_collapse_for_every_evidence_state(self) -> None:
        for state in ("resolved", "missing", "unresolved"):
            with self.subTest(state=state):
                node = CanonicalReferenceTraversalNode(
                    kind="object", state=state, document_path="assembly.FCStd",
                    object_name="Source", object_type="Part::Feature",
                    label="Source label",
                )
                duplicate = CanonicalReferenceTraversalNode(
                    kind="object", state=state, document_path="assembly.FCStd",
                    object_name="Source", object_type="Part::Feature",
                    label="Source label",
                )
                result = traversal.ReferenceTraversalExecutionResult(
                    status="succeeded", nodes=(node, duplicate),
                    edges=(), diagnostics=(),
                )
                self.assertEqual(result.nodes, (node,))

    def test_canonical_node_duplicates_and_one_conflict_fail_deterministically(
        self,
    ) -> None:
        first_target = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="refs/a.FCStd",
            object_name="A",
        )
        second_target = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="refs/b.FCStd",
            object_name="B",
        )
        conflicting_second_target = CanonicalReferenceTraversalNode(
            kind="object", state="missing", document_path="refs/b.FCStd",
            object_name="B",
        )
        for nodes in (
            (first_target, second_target, first_target, conflicting_second_target),
            (conflicting_second_target, first_target, second_target, first_target),
        ):
            with self.subTest(nodes=nodes), self.assertRaisesRegex(
                traversal.ReferenceTraversalExecutionError,
                "duplicate canonical node identity has conflicting raw evidence",
            ) as caught:
                traversal.ReferenceTraversalExecutionResult(
                    status="succeeded", nodes=nodes, edges=(), diagnostics=(),
                )
            self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_canonical_node_identity_conflict_fails_deterministically_with_chaining(
        self,
    ) -> None:
        resolved = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source", object_type="Part::Feature",
            label="Source label",
        )
        conflicting_state = CanonicalReferenceTraversalNode(
            kind="object", state="missing", document_path="assembly.FCStd",
            object_name="Source", object_type="Part::Feature",
            label="Source label",
        )
        conflicting_object_type = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source", object_type="Part::Box",
            label="Source label",
        )
        conflicting_label = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source", object_type="Part::Feature",
            label="different evidence",
        )
        conflicting_diagnostic = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source", object_type="Part::Feature",
            label="Source label", diagnostic="unexpected",
        )
        for nodes in (
            (resolved, conflicting_state),
            (conflicting_state, resolved),
            (resolved, conflicting_object_type),
            (resolved, conflicting_label),
            (resolved, conflicting_diagnostic),
        ):
            with self.subTest(nodes=nodes), self.assertRaisesRegex(
                traversal.ReferenceTraversalExecutionError,
                "duplicate canonical node identity has conflicting raw evidence",
            ) as caught:
                traversal.ReferenceTraversalExecutionResult(
                    status="succeeded", nodes=nodes, edges=(), diagnostics=(),
                )
            self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_canonical_non_conflicting_nodes_retain_canonical_ordering(self) -> None:
        document = CanonicalReferenceTraversalNode(
            kind="document", state="resolved", document_path="assembly.FCStd",
        )
        source = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source",
        )
        target = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="refs/a.FCStd",
            object_name="Target",
        )
        expected = (document, source, target)
        for nodes in (
            (document, source, target),
            (target, source, document),
            (source, target, document),
        ):
            with self.subTest(nodes=nodes):
                forward = traversal.ReferenceTraversalExecutionResult(
                    status="succeeded", nodes=nodes, edges=(), diagnostics=(),
                )
                self.assertEqual(forward.nodes, expected)

    def test_canonical_node_sequence_assigned_only_after_dedup_and_conflict_enforcement(
        self,
    ) -> None:
        node = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source",
        )
        duplicate = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source",
        )
        other = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Other",
        )
        result = traversal.ReferenceTraversalExecutionResult(
            status="succeeded", nodes=(node, other, duplicate),
            edges=(), diagnostics=(),
        )
        self.assertEqual(result.nodes, (node, other))
        payload = build_reference_traversal_output_payload(
            boundary="reference_traversal_entrypoint",
            operation="reference_traversal",
            status=result.status,
            source_document="assembly.FCStd",
            nodes=result.nodes,
            edges=result.edges,
            diagnostics=result.diagnostics,
        )
        self.assertEqual([entry["sequence"] for entry in payload["nodes"]], [0, 1])
        self.assertEqual(len(payload["nodes"]), 2)

    def test_canonical_exact_duplicate_diagnostics_collapse_before_ordering(self) -> None:
        node = CanonicalReferenceTraversalNode(
            kind="document", state="resolved", document_path="assembly.FCStd"
        )
        first = RawReferenceTraversalDiagnostic(
            severity="warning", code="z", message="same", stage="discovery"
        )
        second = RawReferenceTraversalDiagnostic(
            severity="warning", code="a", message="distinct", stage="discovery"
        )
        results = tuple(
            traversal.ReferenceTraversalExecutionResult(
                status="partial", nodes=(node,), edges=(), diagnostics=diagnostics
            )
            for diagnostics in (
                (first, second, first),
                (second, first, first),
            )
        )
        self.assertEqual(results[0].diagnostics, (second, first))
        self.assertEqual(results[1].diagnostics, (second, first))

        emitted = tuple(
            serialize_reference_traversal_output(
                boundary="reference_traversal_entrypoint",
                operation="reference_traversal",
                status=result.status,
                source_document="assembly.FCStd",
                nodes=result.nodes,
                edges=result.edges,
                diagnostics=(first, *result.diagnostics),
            )
            for result in results
        )
        self.assertEqual(emitted[0], emitted[1])
        self.assertEqual(emitted[0].count(b'"code":"z"'), 1)

    def test_canonical_post_dedup_sequences_and_bytes_are_deterministic(self) -> None:
        source = CanonicalReferenceTraversalNode(
            kind="object", state="resolved", document_path="assembly.FCStd",
            object_name="Source",
        )
        targets = tuple(
            CanonicalReferenceTraversalNode(
                kind="object", state="resolved", document_path=f"refs/{name}.FCStd",
                object_name=name,
            )
            for name in ("A", "B")
        )
        edges = tuple(
            CanonicalReferenceTraversalEdge(
                source, target, "external_document_reference", "resolved",
                "Parts", "App::PropertyXLinkList",
            )
            for target in targets
        )
        emitted = []
        for raw_edges in ((edges[0], edges[1], edges[0]), (edges[1], edges[0], edges[1])):
            result = traversal.ReferenceTraversalExecutionResult(
                status="succeeded", nodes=(source, *targets),
                edges=raw_edges, diagnostics=(),
            )
            emitted.append(serialize_reference_traversal_output(
                boundary="reference_traversal_entrypoint",
                operation="reference_traversal", status=result.status,
                source_document="assembly.FCStd", nodes=result.nodes,
                edges=result.edges, diagnostics=result.diagnostics,
            ))
            payload = build_reference_traversal_output_payload(
                boundary="reference_traversal_entrypoint",
                operation="reference_traversal", status=result.status,
                source_document="assembly.FCStd", nodes=result.nodes,
                edges=result.edges, diagnostics=result.diagnostics,
            )
            self.assertEqual([edge["sequence"] for edge in payload["edges"]], [0, 1])
        self.assertEqual(emitted[0], emitted[1])

    def test_real_document_discovery_returns_resolved_source_root(self) -> None:
        document = type("Document", (), {"Label": "Assembly label"})()

        result = traversal.run_reference_traversal(
            document, self._request(), **self._kwargs()
        )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(
            result.nodes,
            (
                CanonicalReferenceTraversalNode(
                    kind="document",
                    state="resolved",
                    document_path="assembly.FCStd",
                    label="Assembly label",
                ),
            ),
        )
        self.assertEqual(result.edges, ())
        self.assertEqual(result.diagnostics, ())

    def test_document_discovery_preserves_canonical_nested_source_path(self) -> None:
        kwargs = self._kwargs()
        kwargs["source_document"] = "nested/design/assembly.FCStd"

        result = traversal.run_reference_traversal(
            type("Document", (), {"Label": ""})(), self._request(), **kwargs
        )

        self.assertEqual(result.nodes[0].document_path, "nested/design/assembly.FCStd")
        self.assertIsNone(result.nodes[0].label)

    def test_root_only_excludes_unrelated_and_empty_link_objects(self) -> None:
        unrelated = _TraversalObject("Unrelated")
        empty_source = _TraversalObject(
            "EmptySource",
            properties=(("Link", ("App::PropertyLink", None)),),
        )
        document = _TraversalDocument((unrelated, empty_source))

        result = traversal.run_reference_traversal(
            document, self._request(), **self._kwargs()
        )

        self.assertEqual([node.kind for node in result.nodes], ["document"])
        self.assertEqual(result.edges, ())

    def test_unrecognized_property_mechanism_is_ignored_without_value_read(self) -> None:
        source = _TraversalObject(
            "Source",
            properties=(("Text", ("App::PropertyString", "Target")),),
        )

        result = traversal.run_reference_traversal(
            _TraversalDocument((source,)), self._request(), **self._kwargs()
        )

        self.assertEqual([node.kind for node in result.nodes], ["document"])
        self.assertEqual(result.edges, ())
        self.assertEqual(result.diagnostics, ())
        self.assertEqual(source.property_reads, 0)
        self.assertEqual(
            traversal._RECOGNIZED_UNSUPPORTED_REFERENCE_PROPERTY_TYPE_IDS, ()
        )

    def test_unsupported_value_shape_returns_one_exact_partial_diagnostic(self) -> None:
        source = _TraversalObject(
            "Source", label="must not leak", type_id="Runtime::MustNotLeak",
            properties=(("Link", ("App::PropertyLink", "Target")),),
        )
        document = _TraversalDocument((source,))
        document.FileName = "/runtime/must-not-leak.FCStd"

        result = traversal.run_reference_traversal(
            document, self._request(), **self._kwargs()
        )

        self.assertEqual(result.status, "partial")
        self.assertEqual([node.kind for node in result.nodes], ["document"])
        self.assertEqual(result.edges, ())
        self.assertEqual(
            result.diagnostics,
            (
                RawReferenceTraversalDiagnostic(
                    severity="warning",
                    code="unsupported_reference_value_shape",
                    message='["Source","Link","App::PropertyLink"]',
                    stage="reference_discovery",
                ),
            ),
        )
        self.assertEqual(source.property_reads, 1)
        rendered = result.diagnostics[0].message
        for excluded in (
            "must not leak", "Runtime::MustNotLeak", "/runtime/", "FileName"
        ):
            self.assertNotIn(excluded, rendered)

    def test_mapped_unsupported_shape_emits_no_inferred_missing_evidence(self) -> None:
        source = _TraversalObject(
            "Source",
            properties=(("Link", ("App::PropertyXLink", "ExternalTarget")),),
        )

        result = traversal.run_reference_traversal(
            _TraversalDocument((source,)),
            self._mapped_request(self._mapping()),
            **self._kwargs(),
        )

        self.assertEqual(result.status, "partial")
        self.assertEqual([node.kind for node in result.nodes], ["document"])
        self.assertEqual(result.edges, ())
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["unsupported_reference_value_shape"],
        )

    def test_structurally_unsupported_container_does_not_partially_extract(self) -> None:
        target = _TraversalObject("Target")
        source = _TraversalObject(
            "Source",
            properties=(("Links", ("App::PropertyLinkList", [target, "bad"])),),
        )

        result = traversal.run_reference_traversal(
            _TraversalDocument((source, target)), self._request(), **self._kwargs()
        )

        self.assertEqual(result.status, "partial")
        self.assertEqual([node.kind for node in result.nodes], ["document"])
        self.assertEqual(result.edges, ())
        self.assertEqual(len(result.diagnostics), 1)

    def test_distinct_unsupported_coordinates_are_canonically_ordered(self) -> None:
        first = _TraversalObject(
            "ZSource",
            properties=(
                ("BLink", ("App::PropertyLink", "bad")),
                ("CLinks", ("App::PropertyLinkList", ["bad-a", "bad-b"])),
            ),
        )
        second = _TraversalObject(
            "ASource",
            properties=(("ALink", ("App::PropertyXLink", {"bad": True})),),
        )
        expected = (
            '["ASource","ALink","App::PropertyXLink"]',
            '["ZSource","BLink","App::PropertyLink"]',
            '["ZSource","CLinks","App::PropertyLinkList"]',
        )
        observed = []
        for objects, properties, link_values in (
            ((first, second), ["BLink", "CLinks"], ["bad-a", "bad-b"]),
            ((second, first), ["CLinks", "BLink"], ["bad-b", "bad-a"]),
        ):
            first.PropertiesList = properties
            first._properties["CLinks"] = (
                "App::PropertyLinkList", link_values
            )
            result = traversal.run_reference_traversal(
                _TraversalDocument(objects), self._request(), **self._kwargs()
            )
            observed.append(tuple(diagnostic.message for diagnostic in result.diagnostics))
        self.assertEqual(observed, [expected, expected])

    def test_internal_reference_emits_only_source_and_target_endpoints(self) -> None:
        target = _TraversalObject("Target", label="Target label")
        source = _TraversalObject("Source", label="Source label")
        source._properties = {"Link": ("App::PropertyLink", target)}
        source.PropertiesList = ["Link"]
        unrelated = _TraversalObject("Unrelated")
        document = _TraversalDocument((unrelated, target, source))

        result = traversal.run_reference_traversal(
            document, self._request(), **self._kwargs()
        )

        self.assertEqual(
            [(node.kind, node.object_name) for node in result.nodes],
            [("document", None), ("object", "Source"), ("object", "Target")],
        )
        self.assertEqual(len(result.edges), 1)
        edge = result.edges[0]
        self.assertEqual(edge.source.object_name, "Source")
        self.assertEqual(edge.target.object_name, "Target")
        self.assertEqual(edge.source_property, "Link")
        self.assertEqual(edge.reference_mechanism, "App::PropertyLink")

    def test_multiple_relationships_are_order_independent_and_deduplicated(self) -> None:
        first_target = _TraversalObject("FirstTarget")
        second_target = _TraversalObject("SecondTarget")
        source = _TraversalObject("Source")
        source._properties = {
            "Targets": (
                "App::PropertyLinkList",
                [second_target, first_target, second_target],
            ),
            "Primary": ("App::PropertyLink", first_target),
        }
        source.PropertiesList = ["Targets", "Primary"]
        forward = _TraversalDocument((second_target, source, first_target))
        first = traversal.run_reference_traversal(
            forward, self._request(), **self._kwargs()
        )

        source.PropertiesList.reverse()
        source._properties["Targets"] = (
            "App::PropertyLinkList",
            [first_target, second_target, second_target],
        )
        forward.Objects.reverse()
        second = traversal.run_reference_traversal(
            forward, self._request(), **self._kwargs()
        )

        self.assertEqual(first, second)
        self.assertEqual(
            [node.object_name for node in first.nodes],
            [None, "SecondTarget", "FirstTarget", "Source"],
        )
        self.assertEqual(
            [(edge.source_property, edge.target.object_name) for edge in first.edges],
            [
                ("Targets", "SecondTarget"),
                ("Primary", "FirstTarget"),
                ("Targets", "FirstTarget"),
            ],
        )

    def test_internal_reference_has_exact_canonical_identity_and_provenance(self) -> None:
        target = _TraversalObject("Target", type_id="Part::Feature")
        source = _TraversalObject("Source", type_id="App::FeaturePython")
        source._properties = {
            "Support": ("App::PropertyLinkSub", (target, ("Face1",)))
        }
        source.PropertiesList = ["Support"]
        result = traversal.run_reference_traversal(
            _TraversalDocument((source, target)), self._request(), **self._kwargs()
        )
        payload = build_reference_traversal_output_payload(
            boundary="reference_traversal_entrypoint",
            operation="reference_traversal",
            status=result.status,
            source_document="assembly.FCStd",
            nodes=result.nodes,
            edges=result.edges,
        )

        source_node = next(node for node in result.nodes if node.object_name == "Source")
        target_node = next(node for node in result.nodes if node.object_name == "Target")
        edge_payload = payload["edges"][0]
        self.assertEqual(
            edge_payload["source"], build_reference_traversal_node_id(source_node)
        )
        self.assertEqual(
            edge_payload["target"], build_reference_traversal_node_id(target_node)
        )
        self.assertEqual(edge_payload["sourceProperty"], "Support")
        self.assertEqual(edge_payload["referenceMechanism"], "App::PropertyLinkSub")
        self.assertEqual(source_node.object_type, "App::FeaturePython")
        self.assertEqual(target_node.object_type, "Part::Feature")

    def test_distinct_participating_sources_are_preserved(self) -> None:
        target = _TraversalObject("SharedTarget")
        first = _TraversalObject("FirstSource")
        second = _TraversalObject("SecondSource")
        first._properties = {"Link": ("App::PropertyLink", target)}
        second._properties = {"Support": ("App::PropertyLink", target)}
        first.PropertiesList = ["Link"]
        second.PropertiesList = ["Support"]

        result = traversal.run_reference_traversal(
            _TraversalDocument((second, target, first)),
            self._request(),
            **self._kwargs(),
        )

        self.assertEqual(
            [node.object_name for node in result.nodes],
            [None, "SecondSource", "SharedTarget", "FirstSource"],
        )
        self.assertEqual(
            [(edge.source.object_name, edge.source_property) for edge in result.edges],
            [("SecondSource", "Support"), ("FirstSource", "Link")],
        )

    def test_external_target_does_not_fabricate_internal_object_evidence(self) -> None:
        external_target = _TraversalObject("ExternalTarget")
        _TraversalDocument((external_target,), label="External")
        source = _TraversalObject("Source")
        source._properties = {"Link": ("App::PropertyXLink", external_target)}
        source.PropertiesList = ["Link"]

        result = traversal.run_reference_traversal(
            _TraversalDocument((source,)), self._request(), **self._kwargs()
        )

        self.assertEqual([node.kind for node in result.nodes], ["document"])
        self.assertEqual(result.edges, ())

    def test_empty_canonical_mapping_preserves_internal_output_exactly(self) -> None:
        target = _TraversalObject("Target")
        source = _TraversalObject("Source")
        source._properties = {"Link": ("App::PropertyLink", target)}
        source.PropertiesList = ["Link"]
        document = _TraversalDocument((source, target))
        unmapped = traversal.run_reference_traversal(
            document, self._request(), **self._kwargs()
        )
        mapped = traversal.run_reference_traversal(
            document, self._mapped_request(), **self._kwargs()
        )
        self.assertEqual(mapped, unmapped)

    def test_mapped_resolved_external_target_uses_complete_coordinate(self) -> None:
        external = _TraversalObject(
            "ExternalTarget", label="Observed label", type_id="PartDesign::Body"
        )
        external_document = _TraversalDocument((external,), label="External")
        external_document.FileName = "/runtime/relocated/external.FCStd"
        source = _TraversalObject("Source")
        source._properties = {"Link": ("App::PropertyXLink", external)}
        source.PropertiesList = ["Link"]
        result = traversal.run_reference_traversal(
            _TraversalDocument((source,)),
            self._mapped_request(self._mapping()),
            **self._kwargs(),
        )
        external_node = next(
            node for node in result.nodes if node.document_path.startswith("references/")
        )
        self.assertEqual(external_node.object_name, "ExternalTarget")
        self.assertEqual(external_node.object_type, "PartDesign::Body")
        self.assertEqual(external_node.label, "Observed label")
        self.assertNotIn("/runtime/", repr(result))
        edge = result.edges[0]
        self.assertEqual(edge.source.object_name, "Source")
        self.assertEqual(edge.target, external_node)
        self.assertEqual(edge.kind, "external_document_reference")
        self.assertEqual(edge.state, "resolved")
        self.assertEqual(edge.source_property, "Link")
        self.assertEqual(edge.reference_mechanism, "App::PropertyXLink")

    def test_complete_coordinate_prevents_partial_mapping(self) -> None:
        external = _TraversalObject("ExternalTarget")
        _TraversalDocument((external,))
        source = _TraversalObject("Source")
        source._properties = {"Actual": ("App::PropertyXLink", external)}
        source.PropertiesList = ["Actual"]
        result = traversal.run_reference_traversal(
            _TraversalDocument((source,)),
            self._mapped_request(self._mapping(property_name="Other")),
            **self._kwargs(),
        )
        self.assertEqual([node.kind for node in result.nodes], ["document"])
        self.assertEqual(result.edges, ())

    def test_missing_single_target_emits_null_unavailable_evidence(self) -> None:
        source = _TraversalObject("Source")
        source._properties = {"Link": ("App::PropertyXLink", None)}
        source.PropertiesList = ["Link"]
        result = traversal.run_reference_traversal(
            _TraversalDocument((source,)),
            self._mapped_request(self._mapping()),
            **self._kwargs(),
        )
        target = next(node for node in result.nodes if node.document_path.startswith("references/"))
        self.assertEqual(target.state, "missing")
        self.assertIsNone(target.label)
        self.assertIsNone(target.object_type)
        self.assertIsNone(target.diagnostic)
        self.assertEqual(result.edges[0].state, "missing")

    def test_empty_and_partial_external_lists_emit_missing_and_resolved(self) -> None:
        mappings = (
            self._mapping("Body", property_name="Parts", mechanism="App::PropertyXLinkList", path="refs/body.FCStd"),
            self._mapping("Wheel", property_name="Parts", mechanism="App::PropertyXLinkList", path="refs/wheel.FCStd"),
        )
        for observed, states in (([], {"Body": "missing", "Wheel": "missing"}),):
            source = _TraversalObject("Source")
            source._properties = {"Parts": ("App::PropertyXLinkList", observed)}
            source.PropertiesList = ["Parts"]
            result = traversal.run_reference_traversal(
                _TraversalDocument((source,)), self._mapped_request(*mappings), **self._kwargs()
            )
            self.assertEqual({edge.target.object_name: edge.state for edge in result.edges}, states)

        body = _TraversalObject("Body")
        _TraversalDocument((body,))
        source = _TraversalObject("Source")
        source._properties = {"Parts": ("App::PropertyXLinkList", [body])}
        source.PropertiesList = ["Parts"]
        result = traversal.run_reference_traversal(
            _TraversalDocument((source,)), self._mapped_request(*mappings), **self._kwargs()
        )
        self.assertEqual(
            {edge.target.object_name: edge.state for edge in result.edges},
            {"Body": "resolved", "Wheel": "missing"},
        )

    def test_absent_source_property_and_mechanism_mismatch_emit_no_mapping(self) -> None:
        cases = (
            _TraversalDocument(()),
            _TraversalDocument((_TraversalObject("Source"),)),
            _TraversalDocument((_TraversalObject("Source", properties=(("Link", ("App::PropertyLink", None)),)),)),
        )
        for document in cases:
            with self.subTest(document=document):
                result = traversal.run_reference_traversal(
                    document, self._mapped_request(self._mapping()), **self._kwargs()
                )
                self.assertEqual([node.kind for node in result.nodes], ["document"])
                self.assertEqual(result.edges, ())

    def test_same_name_external_candidates_fail_deterministically_with_chaining(self) -> None:
        first = _TraversalObject("ExternalTarget")
        second = _TraversalObject("ExternalTarget")
        _TraversalDocument((first,))
        _TraversalDocument((second,))
        source = _TraversalObject("Source")
        source._properties = {"Parts": ("App::PropertyXLinkList", [second, first])}
        source.PropertiesList = ["Parts"]
        mapping = self._mapping(mechanism="App::PropertyXLinkList", property_name="Parts")
        for value in ([first, second], [second, first]):
            source._properties["Parts"] = ("App::PropertyXLinkList", value)
            with self.assertRaisesRegex(
                traversal.ReferenceTraversalExecutionError,
                "ambiguous_reference_target",
            ) as caught:
                traversal.run_reference_traversal(
                    _TraversalDocument((source,)), self._mapped_request(mapping), **self._kwargs()
                )
            self.assertIsInstance(caught.exception.__cause__, ValueError)
            self.assertFalse(hasattr(caught.exception, "diagnostics"))
            self.assertEqual(
                str(caught.exception.__cause__),
                'ambiguous_reference_target: '
                '["Source","Parts","App::PropertyXLinkList","ExternalTarget"]',
            )

    def test_direct_conflicting_mapping_is_controlled_at_typed_boundary(self) -> None:
        request = self._mapped_request(
            self._mapping(path="refs/a.FCStd"),
            self._mapping(path="refs/b.FCStd"),
        )
        with self.assertRaisesRegex(
            traversal.ReferenceTraversalExecutionError,
            "conflicting target identities",
        ) as caught:
            traversal.run_reference_traversal(
                _TraversalDocument(()), request, **self._kwargs()
            )
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_mapped_output_is_order_relocation_and_byte_stable(self) -> None:
        first = _TraversalObject("Body")
        second = _TraversalObject("Wheel")
        external_document = _TraversalDocument((first, second))
        source = _TraversalObject("Source")
        source._properties = {"Parts": ("App::PropertyXLinkList", [second, first])}
        source.PropertiesList = ["Parts"]
        mappings = (
            self._mapping("Wheel", property_name="Parts", mechanism="App::PropertyXLinkList", path="refs/wheel.FCStd"),
            self._mapping("Body", property_name="Parts", mechanism="App::PropertyXLinkList", path="refs/body.FCStd"),
        )
        payloads = []
        for filename, values, request_values in (
            ("/runtime/a/external.FCStd", [second, first], mappings),
            ("/relocated/b/external.FCStd", [first, second], tuple(reversed(mappings))),
        ):
            external_document.FileName = filename
            source._properties["Parts"] = ("App::PropertyXLinkList", values)
            result = traversal.run_reference_traversal(
                _TraversalDocument((source,)), self._mapped_request(*request_values), **self._kwargs()
            )
            payloads.append(build_reference_traversal_output_payload(
                boundary="reference_traversal_entrypoint", operation="reference_traversal",
                status=result.status, source_document="assembly.FCStd",
                nodes=result.nodes, edges=result.edges,
            ))
        self.assertEqual(payloads[0], payloads[1])
        self.assertNotIn("/runtime/a", repr(payloads[0]))
        self.assertNotIn("/relocated/b", repr(payloads[0]))

    def test_mapped_external_ids_are_used_by_edge_endpoints(self) -> None:
        source = _TraversalObject("Source")
        source._properties = {"Link": ("App::PropertyXLink", None)}
        source.PropertiesList = ["Link"]
        result = traversal.run_reference_traversal(
            _TraversalDocument((source,)), self._mapped_request(self._mapping()), **self._kwargs()
        )
        payload = build_reference_traversal_output_payload(
            boundary="reference_traversal_entrypoint", operation="reference_traversal",
            status=result.status, source_document="assembly.FCStd",
            nodes=result.nodes, edges=result.edges,
        )
        target = next(node for node in result.nodes if node.document_path.startswith("references/"))
        self.assertEqual(payload["edges"][0]["target"], build_reference_traversal_node_id(target))

    def test_internal_result_preserves_exact_available_raw_evidence(self) -> None:
        target = _TraversalObject("Target", label="", type_id="")
        source = _TraversalObject(
            "Source", label="Source label", type_id="App::FeaturePython"
        )
        source._properties = {"Support": ("App::PropertyLink", target)}
        source.PropertiesList = ["Support"]

        result = traversal.run_reference_traversal(
            _TraversalDocument((source, target), label="Document label"),
            self._request(),
            **self._kwargs(),
        )

        source_node = next(node for node in result.nodes if node.object_name == "Source")
        target_node = next(node for node in result.nodes if node.object_name == "Target")
        document_node = next(node for node in result.nodes if node.kind == "document")
        edge = result.edges[0]
        self.assertEqual(document_node.document_path, "assembly.FCStd")
        self.assertEqual(document_node.label, "Document label")
        self.assertEqual(
            (source_node.document_path, source_node.label, source_node.object_type),
            ("assembly.FCStd", "Source label", "App::FeaturePython"),
        )
        self.assertEqual(
            (target_node.document_path, target_node.label, target_node.object_type),
            ("assembly.FCStd", None, None),
        )
        self.assertEqual(
            (
                edge.source,
                edge.target,
                edge.kind,
                edge.state,
                edge.source_property,
                edge.reference_mechanism,
                edge.diagnostic,
            ),
            (
                source_node,
                target_node,
                "document_internal_reference",
                "resolved",
                "Support",
                "App::PropertyLink",
                None,
            ),
        )
        self.assertEqual(result.diagnostics, ())

    def test_self_and_mutual_internal_cycles_terminate_with_finite_evidence(self) -> None:
        first = _TraversalObject("First")
        second = _TraversalObject("Second")
        first._properties = {
            "Self": ("App::PropertyLink", first),
            "Other": ("App::PropertyLink", second),
        }
        second._properties = {"Back": ("App::PropertyLink", first)}
        first.PropertiesList = ["Self", "Other"]
        second.PropertiesList = ["Back"]

        result = traversal.run_reference_traversal(
            _TraversalDocument((first, second)), self._request(), **self._kwargs()
        )

        self.assertEqual(len(result.nodes), 3)
        self.assertEqual(len(result.edges), 3)
        self.assertEqual(
            {
                (
                    edge.source.object_name,
                    edge.target.object_name,
                    edge.source_property,
                )
                for edge in result.edges
            },
            {
                ("First", "First", "Self"),
                ("First", "Second", "Other"),
                ("Second", "First", "Back"),
            },
        )

    def test_repeated_semantic_source_object_is_traversed_once(self) -> None:
        target = _TraversalObject("Target")
        source = _TraversalObject("Source")
        source._properties = {"Link": ("App::PropertyLink", target)}
        source.PropertiesList = ["Link"]
        document = _TraversalDocument((source, target))
        document.Objects = [source, target, source]

        result = traversal.run_reference_traversal(
            document, self._request(), **self._kwargs()
        )

        self.assertEqual(source.property_reads, 1)
        self.assertEqual(len(result.nodes), 3)
        self.assertEqual(len(result.edges), 1)

    def test_shared_target_and_multiple_outgoing_cardinality_is_preserved(self) -> None:
        shared = _TraversalObject("Shared")
        other = _TraversalObject("Other")
        first = _TraversalObject("First")
        second = _TraversalObject("Second")
        first._properties = {
            "SharedLink": ("App::PropertyLink", shared),
            "OtherLink": ("App::PropertyLink", other),
        }
        second._properties = {"SharedLink": ("App::PropertyLink", shared)}
        first.PropertiesList = ["SharedLink", "OtherLink"]
        second.PropertiesList = ["SharedLink"]

        result = traversal.run_reference_traversal(
            _TraversalDocument((shared, second, other, first)),
            self._request(),
            **self._kwargs(),
        )

        shared_nodes = [node for node in result.nodes if node.object_name == "Shared"]
        incoming_shared = [
            edge for edge in result.edges if edge.target.object_name == "Shared"
        ]
        outgoing_first = [
            edge for edge in result.edges if edge.source.object_name == "First"
        ]
        self.assertEqual(len(shared_nodes), 1)
        self.assertEqual(len(incoming_shared), 2)
        self.assertEqual(len(outgoing_first), 2)

    def test_invalid_result_inputs_use_only_public_execution_error(self) -> None:
        cases = (
            {"status": "unknown", "nodes": (), "edges": (), "diagnostics": ()},
            {"status": "succeeded", "nodes": [], "edges": (), "diagnostics": ()},
            {"status": "succeeded", "nodes": (), "edges": (object(),), "diagnostics": ()},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(
                traversal.ReferenceTraversalExecutionError
            ) as caught:
                traversal.ReferenceTraversalExecutionResult(**kwargs)  # type: ignore[arg-type]
            self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_raw_python_stack_trace_is_rejected_from_diagnostics(self) -> None:
        diagnostic = RawReferenceTraversalDiagnostic(
            severity="error",
            code="freecad_failure",
            message=(
                "Traceback (most recent call last):\n"
                '  File "/tmp/runtime.py", line 4, in traverse\n'
                "RuntimeError: boom"
            ),
            stage="reference_traversal",
        )

        with self.assertRaisesRegex(
            traversal.ReferenceTraversalExecutionError,
            "must not contain an uncontracted raw stack trace",
        ) as caught:
            traversal.ReferenceTraversalExecutionResult(
                status="failed",
                nodes=(),
                edges=(),
                diagnostics=(diagnostic,),
            )

        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_callable_delegates_all_runtime_context_without_writing(self) -> None:
        document = object()
        request = self._request()
        expected = self._result()
        with mock.patch.object(
            traversal, "_execute_reference_traversal", return_value=expected
        ) as implementation, mock.patch(
            "builtins.open", side_effect=AssertionError("must not write files")
        ):
            actual = traversal.run_reference_traversal(
                document, request, **self._kwargs()
            )
        self.assertIs(actual, expected)
        implementation.assert_called_once_with(
            document,
            request,
            working_copy=Path("/runtime/root"),
            source_document="assembly.FCStd",
            source_document_path=Path("/runtime/root/assembly.FCStd"),
        )

    def test_implementation_failure_is_chained_through_single_public_error(self) -> None:
        original = RuntimeError("FreeCAD traversal failed")
        with mock.patch.object(
            traversal, "_execute_reference_traversal", side_effect=original
        ), self.assertRaises(traversal.ReferenceTraversalExecutionError) as caught:
            traversal.run_reference_traversal(
                object(), self._request(), **self._kwargs()
            )
        self.assertIs(caught.exception.__cause__, original)

    def test_invalid_callable_inputs_are_chained_execution_errors(self) -> None:
        cases = (
            (None, self._request(), self._kwargs()),
            (object(), object(), self._kwargs()),
            (object(), self._request(), {**self._kwargs(), "source_document": ""}),
        )
        for document, request, kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(
                traversal.ReferenceTraversalExecutionError
            ) as caught:
                traversal.run_reference_traversal(document, request, **kwargs)
            self.assertIsInstance(caught.exception.__cause__, ValueError)


class ReferenceTraversalImportSafetyTests(unittest.TestCase):
    def test_module_imports_without_freecad_or_runtime_side_effects(self) -> None:
        module_name = "parametron_freecad.runtime.reference_traversal"
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__
        previous = sys.modules.pop(module_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(module_name, previous)
            if previous is not None
            else sys.modules.pop(module_name, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name.split(".", maxsplit=1)[0] in guarded_names:
                raise AssertionError("boundary must not import FreeCAD")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import), mock.patch(
            "builtins.open", side_effect=AssertionError("import must not open files")
        ):
            imported = importlib.import_module(module_name)

        self.assertTrue(hasattr(imported, "run_reference_traversal"))
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


if __name__ == "__main__":
    unittest.main()
