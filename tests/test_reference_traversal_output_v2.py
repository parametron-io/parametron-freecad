from __future__ import annotations

import unittest

from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.runtime.reference_traversal_output_contract import (
    RawReferenceTraversalDiagnostic,
    RawReferenceTraversalEdge,
    RawReferenceTraversalNode,
    serialize_reference_traversal_output,
)
from parametron_freecad.runtime.reference_traversal_output_v2 import (
    RawReferenceTraversalEdgeV2,
    RawReferenceTraversalNodeV2,
    build_reference_traversal_node_id_v2,
    build_reference_traversal_node_identity_key_v2,
    build_reference_traversal_output_payload_v2,
    serialize_reference_traversal_output_v2,
)


class ReferenceTraversalOutputV2Tests(unittest.TestCase):
    def _node(self, **overrides):
        values = {
            "kind": "object",
            "state": "resolved",
            "document_path": "assembly.FCStd",
            "object_name": "Bolt",
            "object_type": "PartDesign::Feature",
            "label": "Bolt label",
        }
        values.update(overrides)
        return RawReferenceTraversalNodeV2(**values)

    def _payload(self, *, nodes=(), edges=(), diagnostics=()):
        return build_reference_traversal_output_payload_v2(
            boundary="reference_traversal_entrypoint",
            operation="reference_traversal",
            status="succeeded",
            source_document="assembly.FCStd",
            nodes=nodes,
            edges=edges,
            diagnostics=diagnostics,
        )

    def test_ascii_and_unicode_node_id_golden_vectors(self) -> None:
        ascii_node = self._node()
        unicode_node = self._node(
            document_path="模型.FCStd", object_name="部品", label=None
        )
        self.assertEqual(
            dumps_canonical(build_reference_traversal_node_identity_key_v2(ascii_node))
            .encode("utf-8"),
            b'["object","assembly.FCStd","Bolt"]\n',
        )
        self.assertEqual(
            build_reference_traversal_node_id_v2(ascii_node),
            "object:ff0fe3e51839e76aa5b17db3b5bd2ebd6fe62c33b048138d7f4d2a095e0d350c",
        )
        self.assertEqual(
            build_reference_traversal_node_id_v2(unicode_node),
            "object:806027d94b239f7198e1b1ba4b79088b749b53f77ab3ae14a37664210354e119",
        )

    def test_payload_has_exact_v2_fields_and_null_provenance(self) -> None:
        node = self._node(object_type=None, label=None)
        payload = self._payload(nodes=(node,))
        self.assertEqual(payload["schemaVersion"], "2.0")
        self.assertEqual(
            tuple(payload["nodes"][0]),
            (
                "sequence", "id", "kind", "state", "documentPath",
                "objectName", "objectType", "label", "diagnostic",
            ),
        )
        self.assertIsNone(payload["nodes"][0]["objectType"])

    def test_provenance_sensitive_edges_are_preserved_and_ordered(self) -> None:
        source = self._node()
        target = self._node(object_name="Nut")
        edges = (
            RawReferenceTraversalEdgeV2(
                source, target, "document_internal_reference", "resolved",
                "Second", "App::PropertyLink",
            ),
            RawReferenceTraversalEdgeV2(
                source, target, "document_internal_reference", "resolved",
                None, None,
            ),
            RawReferenceTraversalEdgeV2(
                source, target, "document_internal_reference", "resolved",
                "First", "App::PropertyLink",
            ),
        )
        payload = self._payload(nodes=(source, target), edges=edges)
        self.assertEqual(
            [(e["sourceProperty"], e["referenceMechanism"]) for e in payload["edges"]],
            [(None, None), ("First", "App::PropertyLink"), ("Second", "App::PropertyLink")],
        )

    def test_equal_complete_edge_identity_collapses(self) -> None:
        source = self._node()
        target = self._node(object_name="Nut")
        edge = RawReferenceTraversalEdgeV2(
            source, target, "document_internal_reference", "resolved",
            "Link", "App::PropertyLink",
        )
        self.assertEqual(len(self._payload(nodes=(source, target), edges=(edge, edge))["edges"]), 1)

    def test_empty_provenance_is_rejected(self) -> None:
        with self.assertRaisesRegex(Exception, "objectType must be a non-empty"):
            self._payload(nodes=(self._node(object_type=""),))

    def test_reordered_inputs_have_repeated_equal_bytes(self) -> None:
        first = self._node()
        second = self._node(object_name="Nut")
        diagnostic_a = RawReferenceTraversalDiagnostic("warning", "b", "B")
        diagnostic_b = RawReferenceTraversalDiagnostic("error", "a", "A")
        kwargs = {
            "boundary": "reference_traversal_entrypoint",
            "operation": "reference_traversal",
            "status": "partial",
            "source_document": "assembly.FCStd",
        }
        forward = serialize_reference_traversal_output_v2(
            **kwargs, nodes=(first, second), edges=(), diagnostics=(diagnostic_a, diagnostic_b)
        )
        reverse = serialize_reference_traversal_output_v2(
            **kwargs, nodes=(second, first), edges=(), diagnostics=(diagnostic_b, diagnostic_a)
        )
        self.assertEqual(forward, reverse)
        self.assertEqual(forward[-1:], b"\n")

    def test_schema_1_serializer_remains_unchanged(self) -> None:
        node = RawReferenceTraversalNode(
            id="legacy", kind="object", state="resolved",
            document_path="assembly.FCStd", object_name="Bolt",
        )
        before = serialize_reference_traversal_output(
            boundary="reference_traversal_entrypoint",
            operation="reference_traversal",
            status="succeeded",
            source_document="assembly.FCStd",
            nodes=(node,), edges=(), diagnostics=(),
        )
        self.assertIn(b'"schemaVersion":"1.0"', before)
        self.assertNotIn(b"objectType", before)
        self.assertEqual(
            tuple(RawReferenceTraversalEdge.__dataclass_fields__),
            ("source", "target", "kind", "state", "diagnostic"),
        )


if __name__ == "__main__":
    unittest.main()
