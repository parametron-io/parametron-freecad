"""Canonical rich traversal writer, containment, and atomic failure coverage."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from parametron_freecad.runtime import reference_traversal_output_writer as writer
from parametron_freecad.runtime.reference_traversal_output import (
    RawReferenceTraversalEdge,
    RawReferenceTraversalNode,
    serialize_reference_traversal_output,
)


def _evidence():
    source = RawReferenceTraversalNode(
        kind="object", state="resolved", document_path="assembly.FCStd",
        object_name="Source", object_type="PartDesign::Feature",
    )
    target = RawReferenceTraversalNode(
        kind="object", state="missing", document_path="references/part.FCStd",
        object_name="Target",
    )
    edge = RawReferenceTraversalEdge(
        source=source, target=target, kind="external_document_reference",
        state="missing", source_property="Link",
        reference_mechanism="App::PropertyXLink",
    )
    return {
        "boundary": "reference_traversal_entrypoint",
        "operation": "reference_traversal",
        "status": "partial",
        "source_document": "assembly.FCStd",
        "nodes": (target, source),
        "edges": (edge,),
        "diagnostics": (),
    }


class CanonicalTraversalWriterTests(TestCase):
    def test_direct_writer_emits_rich_schema_one_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evidence.json"
            writer.write_reference_traversal_output(path, **_evidence())
            self.assertEqual(path.read_bytes(), serialize_reference_traversal_output(**_evidence()))
            payload = json.loads(path.read_text())
            self.assertEqual(payload["schemaVersion"], "1.0")
            self.assertEqual(
                next(node for node in payload["nodes"] if node["objectName"] == "Source")["objectType"],
                "PartDesign::Feature",
            )
            self.assertEqual(payload["edges"][0]["sourceProperty"], "Link")
            self.assertEqual(payload["edges"][0]["referenceMechanism"], "App::PropertyXLink")

    def test_atomic_writer_replaces_existing_output_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "prm.reference-traversal.json"
            path.write_bytes(b"old")
            writer.write_reference_traversal_output_atomically(root, path, **_evidence())
            first = path.read_bytes()
            writer.write_reference_traversal_output_atomically(root, path, **_evidence())
            self.assertEqual(path.read_bytes(), first)
            self.assertEqual(first, serialize_reference_traversal_output(**_evidence()))
            self.assertEqual(set(root.iterdir()), {path})

    def test_reordered_equivalent_evidence_has_equal_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = _evidence()
            first, second = root / "first.json", root / "second.json"
            writer.write_reference_traversal_output_atomically(root, first, **evidence)
            writer.write_reference_traversal_output_atomically(
                root, second, **{**evidence, "nodes": tuple(reversed(evidence["nodes"]))}
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_writer_accepts_relative_path_within_exact_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            writer.write_reference_traversal_output_atomically(root, "evidence.json", **_evidence())
            self.assertTrue((root / "evidence.json").is_file())

    def test_writer_rejects_parent_escape_without_side_effects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "working"
            root.mkdir()
            with self.assertRaises(writer.ReferenceTraversalOutputWriteError) as caught:
                writer.write_reference_traversal_output_atomically(root, "../escape.json", **_evidence())
            self.assertTrue(caught.exception._is_containment_failure)
            self.assertFalse((root.parent / "escape.json").exists())
            self.assertEqual(list(root.iterdir()), [])

    def test_writer_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "working"
            outside = Path(temporary) / "outside"
            root.mkdir(); outside.mkdir()
            (root / "link").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(writer.ReferenceTraversalOutputWriteError) as caught:
                writer.write_reference_traversal_output_atomically(root, "link/evidence.json", **_evidence())
            self.assertTrue(caught.exception._is_containment_failure)
            self.assertEqual(list(outside.iterdir()), [])

    def test_conflicting_edge_identity_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = _evidence()
            edge = evidence["edges"][0]
            conflict = RawReferenceTraversalEdge(
                source=edge.source, target=edge.target, kind=edge.kind,
                state="unresolved", source_property=edge.source_property,
                reference_mechanism=edge.reference_mechanism,
            )
            with self.assertRaises(writer.ReferenceTraversalOutputWriteError) as caught:
                writer.write_reference_traversal_output_atomically(
                    root, "evidence.json", **{**evidence, "edges": (edge, conflict)}
                )
            self.assertIn("conflicting raw evidence", str(caught.exception.__cause__))
            self.assertEqual(list(root.iterdir()), [])

    def test_replace_failure_preserves_existing_bytes_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "evidence.json"
            path.write_bytes(b"previous")
            with mock.patch.object(writer.os, "replace", side_effect=OSError("replace failed")):
                with self.assertRaises(writer.ReferenceTraversalOutputWriteError) as caught:
                    writer.write_reference_traversal_output_atomically(root, path, **_evidence())
            self.assertIsInstance(caught.exception.__cause__, OSError)
            self.assertFalse(caught.exception._is_containment_failure)
            self.assertEqual(path.read_bytes(), b"previous")
            self.assertEqual(set(root.iterdir()), {path})

    def test_temporary_file_is_in_resolved_target_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            output.mkdir()
            original = writer.tempfile.mkstemp
            locations = []
            def traced(*args, **kwargs):
                locations.append(kwargs["dir"])
                return original(*args, **kwargs)
            with mock.patch.object(writer.tempfile, "mkstemp", side_effect=traced):
                writer.write_reference_traversal_output_atomically(root, output / "evidence.json", **_evidence())
            self.assertEqual(locations, [output])

    def test_serializer_failure_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "evidence.json"
            path.write_bytes(b"previous")
            with mock.patch.object(writer, "serialize_reference_traversal_output", side_effect=ValueError("invalid")):
                with self.assertRaises(writer.ReferenceTraversalOutputWriteError) as caught:
                    writer.write_reference_traversal_output_atomically(root, path, **_evidence())
            self.assertIsInstance(caught.exception.__cause__, ValueError)
            self.assertEqual(path.read_bytes(), b"previous")
            self.assertEqual(set(root.iterdir()), {path})
