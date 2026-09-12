"""Tests for the direct raw reference traversal output writer.

``parametron_freecad.runtime.reference_traversal_output_writer`` is a
deliberately bounded, non-atomic writer: it calls
``serialize_reference_traversal_output(...)`` exactly once and writes the
returned bytes directly in binary mode. These tests prove that bounded
contract only. They intentionally do not exercise atomic replacement,
execution-root containment integration, runtime/CLI/headless wiring, or real
FreeCAD traversal; those are separate, later Phase 2 tasks.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import pytest

from parametron_freecad.common.paths import WORKING_COPY_DIR_NAME
from parametron_freecad.runtime import reference_traversal_output_contract as contract
from parametron_freecad.runtime.reference_traversal_output_writer import (
    ReferenceTraversalOutputWriteError,
    write_reference_traversal_output,
    write_reference_traversal_output_atomically,
    write_reference_traversal_output_v2_atomically,
)
from parametron_freecad.runtime.reference_traversal_output_v2 import (
    RawReferenceTraversalEdgeV2,
    RawReferenceTraversalNodeV2,
)

WRITER_MODULE_NAME = "parametron_freecad.runtime.reference_traversal_output_writer"


class ReferenceTraversalOutputV2ConflictTests(unittest.TestCase):
    def test_conflicting_equal_identity_evidence_fails_controlled_emission(self) -> None:
        source = RawReferenceTraversalNodeV2(
            kind="object", state="resolved", document_path="model.FCStd",
            object_name="Source",
        )
        target = RawReferenceTraversalNodeV2(
            kind="object", state="resolved", document_path="model.FCStd",
            object_name="Target",
        )
        first = RawReferenceTraversalEdgeV2(
            source, target, "document_internal_reference", "resolved",
            "Link", "App::PropertyLink",
        )
        conflicting = RawReferenceTraversalEdgeV2(
            source, target, "document_internal_reference", "failed",
            "Link", "App::PropertyLink", "read failed",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ReferenceTraversalOutputWriteError) as caught:
                write_reference_traversal_output_v2_atomically(
                    root, root / "parametron.reference-traversal.json",
                    boundary="reference_traversal_entrypoint",
                    operation="reference_traversal",
                    status="partial",
                    source_document="model.FCStd",
                    nodes=(source, target),
                    edges=(first, conflicting),
                )
        self.assertIsInstance(
            caught.exception.__cause__, contract.ReferenceTraversalOutputContractError
        )
        self.assertEqual(
            str(caught.exception.__cause__),
            "duplicate schema-2 edge identity has conflicting raw evidence",
        )


def _list_names(directory) -> set[str]:
    return {entry.name for entry in Path(directory).iterdir()}


class _FailingWriteFile:
    """Wraps a real fdopen()'d file: write() fails but the real fd still closes.

    Models an os.fdopen()-obtained file whose write() call fails, while still
    exercising real fd lifecycle so the test leaves no descriptor leak behind.
    """

    def __init__(self, real_file):
        self._real_file = real_file

    def write(self, data):
        raise OSError("simulated content-write failure")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._real_file.close()
        return False


class _FailingCloseFile:
    """Wraps a real fdopen()'d file: write() succeeds, close() fails afterward."""

    def __init__(self, real_file):
        self._real_file = real_file

    def write(self, data):
        return self._real_file.write(data)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._real_file.close()
        raise OSError("simulated close failure")


# ---------------------------------------------------------------------------
# Fixture builders (contract-aligned raw traversal evidence)
# ---------------------------------------------------------------------------


def _node(**overrides):
    values = {
        "id": "node-alpha",
        "kind": contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
        "state": contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
        "document_path": "assembly.FCStd",
        "object_name": None,
        "label": None,
        "diagnostic": None,
    }
    values.update(overrides)
    return contract.RawReferenceTraversalNode(**values)


def _edge(**overrides):
    values = {
        "source": "node-alpha",
        "target": "node-beta",
        "kind": contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
        "state": contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
        "diagnostic": None,
    }
    values.update(overrides)
    return contract.RawReferenceTraversalEdge(**values)


def _diagnostic(**overrides):
    values = {
        "severity": contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR,
        "code": "alpha_code",
        "message": "Alpha message çağrı",
        "stage": None,
    }
    values.update(overrides)
    return contract.RawReferenceTraversalDiagnostic(**values)


def _node_alpha():
    return _node(
        id="node-alpha",
        kind=contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
        state=contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
        document_path="Sub Dir/assembly çağrı.FCStd",
        object_name=None,
        label=None,
        diagnostic=None,
    )


def _node_beta():
    return _node(
        id="node-beta",
        kind=contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
        state=contract.REFERENCE_TRAVERSAL_STATE_MISSING,
        document_path="assembly çağrı.FCStd",
        object_name="  Body 東京  ",
        label="Label With Spaces",
        diagnostic="Inline diagnostic çağrı",
    )


def _edge_alpha():
    return _edge(
        source="node-alpha",
        target="node-beta",
        kind=contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
        state=contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
        diagnostic=None,
    )


def _edge_beta():
    return _edge(
        source="node-beta",
        target="node-alpha",
        kind=contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
        state=contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
        diagnostic="Edge diagnostic 東京",
    )


def _diagnostic_alpha():
    return _diagnostic(
        severity=contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR,
        code="alpha_code",
        message="Alpha message çağrı",
        stage=None,
    )


def _diagnostic_beta():
    return _diagnostic(
        severity="warning",
        code="beta_code",
        message="Beta message 東京",
        stage="reference_scan",
    )


def _kwargs(**overrides):
    kwargs = {
        "boundary": contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
        "operation": contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
        "status": contract.REFERENCE_TRAVERSAL_STATUS_PARTIAL,
        "source_document": "root çağrı.FCStd",
        "nodes": [_node_alpha(), _node_beta()],
        "edges": [_edge_alpha(), _edge_beta()],
        "diagnostics": [_diagnostic_alpha(), _diagnostic_beta()],
    }
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# 1. Public API and import safety
# ---------------------------------------------------------------------------


class ReferenceTraversalOutputWriterImportSafetyTests(unittest.TestCase):
    def test_import_does_not_require_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = __import__

        previous = sys.modules.pop(WRITER_MODULE_NAME, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(WRITER_MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(WRITER_MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module(WRITER_MODULE_NAME)

        self.assertIsInstance(module, types.ModuleType)
        self.assertTrue(hasattr(module, "write_reference_traversal_output"))
        self.assertTrue(hasattr(module, "write_reference_traversal_output_atomically"))
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)

    def test_module_exposes_exact_public_api(self) -> None:
        module = importlib.import_module(WRITER_MODULE_NAME)

        self.assertEqual(
            sorted(module.__all__),
            [
                "ReferenceTraversalOutputWriteError",
                "write_reference_traversal_output",
                "write_reference_traversal_output_atomically",
                "write_reference_traversal_output_v2_atomically",
            ],
        )
        for name in module.__all__:
            self.assertTrue(hasattr(module, name))

    def test_error_type_is_an_oserror(self) -> None:
        module = importlib.import_module(WRITER_MODULE_NAME)
        self.assertTrue(
            issubclass(module.ReferenceTraversalOutputWriteError, OSError)
        )


# ---------------------------------------------------------------------------
# 2. Exact serializer-byte emission
# ---------------------------------------------------------------------------


class ReferenceTraversalOutputWriterByteEmissionTests(unittest.TestCase):
    def test_written_bytes_exactly_match_serializer_output(self) -> None:
        kwargs = _kwargs()
        expected = contract.serialize_reference_traversal_output(**kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "traversal.json"
            write_reference_traversal_output(path, **kwargs)
            actual = path.read_bytes()

        self.assertEqual(actual, expected)

    def test_written_bytes_preserve_non_ascii_utf8_without_bom_or_crlf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "traversal.json"
            write_reference_traversal_output(path, **_kwargs())
            actual = path.read_bytes()

        text = actual.decode("utf-8")
        self.assertIn("çağrı", text)
        self.assertIn("東京", text)
        self.assertFalse(actual.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r\n", actual)
        self.assertTrue(actual.endswith(b"\n"))
        self.assertFalse(actual.endswith(b"\n\n"))


# ---------------------------------------------------------------------------
# 3. Serializer delegation and single call
# ---------------------------------------------------------------------------


class ReferenceTraversalOutputWriterDelegationTests(unittest.TestCase):
    def test_serializer_is_called_exactly_once_with_forwarded_kwargs(self) -> None:
        kwargs = _kwargs()
        real_serialize = contract.serialize_reference_traversal_output
        wrapped = mock.Mock(side_effect=lambda **kw: real_serialize(**kw))

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "traversal.json"
            with mock.patch(
                f"{WRITER_MODULE_NAME}.serialize_reference_traversal_output", wrapped
            ):
                write_reference_traversal_output(path, **kwargs)

        wrapped.assert_called_once_with(**kwargs)

    def test_distinctive_serializer_bytes_pass_through_unchanged(self) -> None:
        distinctive = b"not-json-but-safe-to-write-bytes-\xc3\xa7\xc4\x9f\n"

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "traversal.json"
            with mock.patch(
                f"{WRITER_MODULE_NAME}.serialize_reference_traversal_output",
                return_value=distinctive,
            ) as mocked:
                write_reference_traversal_output(path, **_kwargs())
            actual = path.read_bytes()

        mocked.assert_called_once()
        self.assertEqual(actual, distinctive)


# ---------------------------------------------------------------------------
# 4. Repeated overwrite determinism
# ---------------------------------------------------------------------------


class ReferenceTraversalOutputWriterOverwriteTests(unittest.TestCase):
    def test_repeated_writes_produce_byte_identical_output(self) -> None:
        kwargs = _kwargs()

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "traversal.json"
            write_reference_traversal_output(path, **kwargs)
            first = path.read_bytes()
            write_reference_traversal_output(path, **kwargs)
            second = path.read_bytes()

        self.assertEqual(first, second)

    def test_existing_unrelated_file_contents_are_overwritten(self) -> None:
        kwargs = _kwargs()
        expected = contract.serialize_reference_traversal_output(**kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "traversal.json"
            path.write_bytes(b"stale unrelated bytes")
            write_reference_traversal_output(path, **kwargs)
            actual = path.read_bytes()

        self.assertEqual(actual, expected)


# ---------------------------------------------------------------------------
# 5. Equivalent reordered-input determinism
# ---------------------------------------------------------------------------


class ReferenceTraversalOutputWriterReorderedInputTests(unittest.TestCase):
    def test_equivalent_reordered_inputs_produce_byte_identical_files(self) -> None:
        forward_kwargs = _kwargs()
        reordered_kwargs = _kwargs(
            nodes=[_node_beta(), _node_alpha()],
            edges=[_edge_beta(), _edge_alpha()],
            diagnostics=[_diagnostic_beta(), _diagnostic_alpha()],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            forward_path = Path(tmp_dir) / "forward.json"
            reordered_path = Path(tmp_dir) / "reordered.json"
            write_reference_traversal_output(forward_path, **forward_kwargs)
            write_reference_traversal_output(reordered_path, **reordered_kwargs)
            forward_bytes = forward_path.read_bytes()
            reordered_bytes = reordered_path.read_bytes()

        self.assertEqual(forward_bytes, reordered_bytes)
        self.assertEqual(
            forward_bytes,
            contract.serialize_reference_traversal_output(**forward_kwargs),
        )
        self.assertEqual(
            reordered_bytes,
            contract.serialize_reference_traversal_output(**reordered_kwargs),
        )


# ---------------------------------------------------------------------------
# 6. Caller-input non-mutation
# ---------------------------------------------------------------------------


class ReferenceTraversalOutputWriterInputMutationTests(unittest.TestCase):
    def test_input_sequences_and_dataclass_instances_are_not_mutated(self) -> None:
        nodes = [_node_alpha(), _node_beta()]
        edges = [_edge_alpha(), _edge_beta()]
        diagnostics = [_diagnostic_alpha(), _diagnostic_beta()]
        nodes_snapshot = list(nodes)
        edges_snapshot = list(edges)
        diagnostics_snapshot = list(diagnostics)
        node_field_snapshot = (
            nodes[0].id,
            nodes[0].kind,
            nodes[0].state,
            nodes[0].document_path,
        )
        edge_field_snapshot = (edges[0].source, edges[0].target, edges[0].kind)
        diagnostic_field_snapshot = (diagnostics[0].severity, diagnostics[0].code)

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "traversal.json"
            write_reference_traversal_output(
                path,
                boundary=contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
                operation=contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
                status=contract.REFERENCE_TRAVERSAL_STATUS_PARTIAL,
                source_document="root.FCStd",
                nodes=nodes,
                edges=edges,
                diagnostics=diagnostics,
            )

        self.assertEqual(nodes, nodes_snapshot)
        self.assertEqual(edges, edges_snapshot)
        self.assertEqual(diagnostics, diagnostics_snapshot)
        self.assertEqual(
            (
                nodes[0].id,
                nodes[0].kind,
                nodes[0].state,
                nodes[0].document_path,
            ),
            node_field_snapshot,
        )
        self.assertEqual(
            (edges[0].source, edges[0].target, edges[0].kind), edge_field_snapshot
        )
        self.assertEqual(
            (diagnostics[0].severity, diagnostics[0].code), diagnostic_field_snapshot
        )


# ---------------------------------------------------------------------------
# 7. Serialization/contract failure translation
# ---------------------------------------------------------------------------


class ReferenceTraversalOutputWriterSerializationFailureTests(unittest.TestCase):
    def test_serialization_failure_is_translated_with_chained_cause(self) -> None:
        original = contract.ReferenceTraversalOutputContractError("boom")

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "traversal.json"
            with mock.patch(
                f"{WRITER_MODULE_NAME}.serialize_reference_traversal_output",
                side_effect=original,
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                    write_reference_traversal_output(path, **_kwargs())

            self.assertIs(ctx.exception.__cause__, original)
            self.assertIn(str(path), str(ctx.exception))
            self.assertFalse(path.exists())

    def test_serialization_failure_message_has_no_traceback_or_runtime_noise(
        self,
    ) -> None:
        original = contract.ReferenceTraversalOutputContractError("boom")

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "traversal.json"
            with mock.patch(
                f"{WRITER_MODULE_NAME}.serialize_reference_traversal_output",
                side_effect=original,
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                    write_reference_traversal_output(path, **_kwargs())

        message = str(ctx.exception)
        self.assertNotIn("Traceback", message)
        self.assertNotIn("0x", message)
        self.assertEqual(len(message.splitlines()), 1)


# ---------------------------------------------------------------------------
# 8. File-write failure translation
# ---------------------------------------------------------------------------


class ReferenceTraversalOutputWriterFileWriteFailureTests(unittest.TestCase):
    def test_missing_parent_directory_is_translated_and_not_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "missing-parent" / "traversal.json"

            with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                write_reference_traversal_output(path, **_kwargs())

            self.assertIsInstance(ctx.exception.__cause__, OSError)
            self.assertIn(str(path), str(ctx.exception))
            self.assertFalse(path.parent.exists())

    def test_output_path_referring_to_a_directory_is_translated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "traversal.json"
            path.mkdir()

            with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                write_reference_traversal_output(path, **_kwargs())

            self.assertIsInstance(ctx.exception.__cause__, OSError)
            self.assertIn(str(path), str(ctx.exception))
            self.assertTrue(path.is_dir())


# ---------------------------------------------------------------------------
# 9. Path pass-through boundary (relative paths, no resolver, no containment)
# ---------------------------------------------------------------------------


class ReferenceTraversalOutputWriterPathBoundaryTests(unittest.TestCase):
    def test_writer_module_does_not_bind_output_path_resolver(self) -> None:
        module = importlib.import_module(WRITER_MODULE_NAME)
        self.assertFalse(hasattr(module, "resolve_reference_traversal_output_path"))


def test_relative_output_path_resolves_against_current_working_directory(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    kwargs = _kwargs()

    write_reference_traversal_output(Path("traversal.json"), **kwargs)

    written = tmp_path / "traversal.json"
    assert written.exists()
    assert written.read_bytes() == contract.serialize_reference_traversal_output(
        **kwargs
    )


def test_relative_output_path_with_missing_parent_is_rejected_and_not_created(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    relative_path = Path("missing-dir") / "traversal.json"

    with pytest.raises(ReferenceTraversalOutputWriteError):
        write_reference_traversal_output(relative_path, **_kwargs())

    assert not (tmp_path / "missing-dir").exists()


# ---------------------------------------------------------------------------
# 10. Atomic writer: public API and import-safety boundary
# ---------------------------------------------------------------------------


class AtomicWriterPublicApiTests(unittest.TestCase):
    def test_atomic_writer_is_exported_and_callable(self) -> None:
        module = importlib.import_module(WRITER_MODULE_NAME)
        self.assertTrue(
            hasattr(module, "write_reference_traversal_output_atomically")
        )
        self.assertTrue(
            callable(module.write_reference_traversal_output_atomically)
        )

    def test_resolver_public_name_is_not_exposed_on_module(self) -> None:
        module = importlib.import_module(WRITER_MODULE_NAME)
        self.assertFalse(
            hasattr(module, "resolve_reference_traversal_output_path")
        )

    def test_private_resolver_alias_exists_but_is_excluded_from_all(self) -> None:
        module = importlib.import_module(WRITER_MODULE_NAME)
        self.assertTrue(hasattr(module, "_resolve_output_path"))
        self.assertNotIn("_resolve_output_path", module.__all__)

    def test_atomic_writer_failures_use_the_shared_error_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            with mock.patch(
                f"{WRITER_MODULE_NAME}.serialize_reference_traversal_output",
                side_effect=RuntimeError("boom"),
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError):
                    write_reference_traversal_output_atomically(
                        working_copy, "out.json", **_kwargs()
                    )


# ---------------------------------------------------------------------------
# 11. Atomic writer: resolver delegation and authoritative-root behavior
# ---------------------------------------------------------------------------


class AtomicWriterResolverDelegationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.root = Path(self._tempdir.name).resolve()
        self.working_copy = self.root / WORKING_COPY_DIR_NAME
        self.working_copy.mkdir()
        self.outside = self.root / "outside"
        self.outside.mkdir()

    def test_resolver_is_called_exactly_once_with_forwarded_keyword_arguments(
        self,
    ) -> None:
        wrapped = mock.Mock(
            side_effect=contract.resolve_reference_traversal_output_path
        )
        with mock.patch(f"{WRITER_MODULE_NAME}._resolve_output_path", wrapped):
            write_reference_traversal_output_atomically(
                self.working_copy, "out.json", **_kwargs()
            )
        wrapped.assert_called_once_with(
            working_copy=self.working_copy, output_path="out.json"
        )

    def test_resolver_returned_path_is_the_sole_write_destination(self) -> None:
        redirected = self.working_copy / "redirected.json"
        with mock.patch(
            f"{WRITER_MODULE_NAME}._resolve_output_path", return_value=redirected
        ):
            write_reference_traversal_output_atomically(
                self.working_copy, "requested.json", **_kwargs()
            )
        self.assertTrue(redirected.exists())
        self.assertFalse((self.working_copy / "requested.json").exists())

    def test_relative_output_path_is_not_resolved_against_current_working_directory(
        self,
    ) -> None:
        decoy_cwd = self.root / "decoy-cwd"
        decoy_cwd.mkdir()
        previous_cwd = Path.cwd()
        os.chdir(decoy_cwd)
        try:
            write_reference_traversal_output_atomically(
                self.working_copy, "out.json", **_kwargs()
            )
        finally:
            os.chdir(previous_cwd)

        self.assertTrue((self.working_copy / "out.json").exists())
        self.assertEqual(_list_names(decoy_cwd), set())

    def test_accepts_arbitrary_basename_execution_root(self) -> None:
        arbitrary_root = self.root / "arbitrary-safe-root"
        arbitrary_root.mkdir()

        write_reference_traversal_output_atomically(
            arbitrary_root, "references.json", **_kwargs()
        )

        self.assertTrue((arbitrary_root / "references.json").exists())

    def test_accepts_direct_working_directory_named_underscore_working(
        self,
    ) -> None:
        write_reference_traversal_output_atomically(
            self.working_copy, "references.json", **_kwargs()
        )

        self.assertTrue((self.working_copy / "references.json").exists())

    def test_accepts_nested_execution_id_root_under_working_copy(self) -> None:
        execution_root = self.working_copy / "execution-a"
        execution_root.mkdir()

        write_reference_traversal_output_atomically(
            execution_root, "references.json", **_kwargs()
        )

        self.assertTrue((execution_root / "references.json").exists())
        self.assertFalse((self.working_copy / "references.json").exists())

    def test_nested_execution_root_remains_authoritative_and_does_not_widen(
        self,
    ) -> None:
        execution_root = self.working_copy / "execution-a"
        execution_root.mkdir()
        (self.working_copy / "execution-b").mkdir()

        escaped_absolute = self.working_copy / "escaped.json"
        with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
            write_reference_traversal_output_atomically(
                execution_root, str(escaped_absolute), **_kwargs()
            )

        self.assertIsInstance(
            ctx.exception.__cause__,
            contract.ReferenceTraversalOutputContractError,
        )
        self.assertFalse(escaped_absolute.exists())

    def test_rejects_representative_relative_escape(self) -> None:
        with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
            write_reference_traversal_output_atomically(
                self.working_copy, "../escape.json", **_kwargs()
            )

        self.assertIsInstance(
            ctx.exception.__cause__,
            contract.ReferenceTraversalOutputContractError,
        )
        self.assertFalse((self.root / "escape.json").exists())

    def test_rejects_representative_absolute_escape(self) -> None:
        escaped = self.outside / "escape.json"
        with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
            write_reference_traversal_output_atomically(
                self.working_copy, str(escaped), **_kwargs()
            )

        self.assertIsInstance(
            ctx.exception.__cause__,
            contract.ReferenceTraversalOutputContractError,
        )
        self.assertFalse(escaped.exists())

    def test_does_not_create_missing_execution_root(self) -> None:
        missing_root = self.root / "does-not-exist"
        with self.assertRaises(ReferenceTraversalOutputWriteError):
            write_reference_traversal_output_atomically(
                missing_root, "out.json", **_kwargs()
            )

        self.assertFalse(missing_root.exists())

    def test_does_not_create_missing_destination_parent(self) -> None:
        with self.assertRaises(ReferenceTraversalOutputWriteError):
            write_reference_traversal_output_atomically(
                self.working_copy, "missing-sub/out.json", **_kwargs()
            )

        self.assertFalse((self.working_copy / "missing-sub").exists())


# ---------------------------------------------------------------------------
# 12. Atomic writer: serializer delegation and byte preservation
# ---------------------------------------------------------------------------


class AtomicWriterSerializerDelegationTests(unittest.TestCase):
    def test_serializer_is_called_exactly_once_with_forwarded_kwargs(self) -> None:
        kwargs = _kwargs()
        real_serialize = contract.serialize_reference_traversal_output
        wrapped = mock.Mock(side_effect=lambda **kw: real_serialize(**kw))

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            with mock.patch(
                f"{WRITER_MODULE_NAME}.serialize_reference_traversal_output",
                wrapped,
            ):
                write_reference_traversal_output_atomically(
                    working_copy, "out.json", **kwargs
                )

        wrapped.assert_called_once_with(**kwargs)

    def test_distinctive_serializer_bytes_pass_through_unchanged(self) -> None:
        distinctive = b"atomic-not-json-but-safe-bytes-\xc3\xa7\xc4\x9f\n"

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            path = working_copy / "out.json"
            with mock.patch(
                f"{WRITER_MODULE_NAME}.serialize_reference_traversal_output",
                return_value=distinctive,
            ) as mocked:
                write_reference_traversal_output_atomically(
                    working_copy, "out.json", **_kwargs()
                )
            actual = path.read_bytes()

        mocked.assert_called_once()
        self.assertEqual(actual, distinctive)

    def test_repeated_writes_are_byte_identical(self) -> None:
        kwargs = _kwargs()

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            write_reference_traversal_output_atomically(
                working_copy, "out.json", **kwargs
            )
            first = target.read_bytes()
            write_reference_traversal_output_atomically(
                working_copy, "out.json", **kwargs
            )
            second = target.read_bytes()

        self.assertEqual(first, second)

    def test_caller_input_sequences_and_dataclasses_are_not_mutated(self) -> None:
        nodes = [_node_alpha(), _node_beta()]
        edges = [_edge_alpha(), _edge_beta()]
        diagnostics = [_diagnostic_alpha(), _diagnostic_beta()]
        nodes_snapshot = list(nodes)
        edges_snapshot = list(edges)
        diagnostics_snapshot = list(diagnostics)

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            write_reference_traversal_output_atomically(
                working_copy,
                "out.json",
                boundary=contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
                operation=contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
                status=contract.REFERENCE_TRAVERSAL_STATUS_PARTIAL,
                source_document="root.FCStd",
                nodes=nodes,
                edges=edges,
                diagnostics=diagnostics,
            )

        self.assertEqual(nodes, nodes_snapshot)
        self.assertEqual(edges, edges_snapshot)
        self.assertEqual(diagnostics, diagnostics_snapshot)


# ---------------------------------------------------------------------------
# 13. Atomic writer: temporary-file placement and replacement ordering
# ---------------------------------------------------------------------------


class AtomicWriterTemporaryFilePlacementTests(unittest.TestCase):
    def test_temporary_file_is_created_in_resolved_target_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            recorded_dirs: list[object] = []
            real_mkstemp = tempfile.mkstemp

            def spy_mkstemp(*args, **kwargs):
                recorded_dirs.append(kwargs.get("dir"))
                return real_mkstemp(*args, **kwargs)

            with mock.patch(
                f"{WRITER_MODULE_NAME}.tempfile.mkstemp", side_effect=spy_mkstemp
            ):
                write_reference_traversal_output_atomically(
                    working_copy, "out.json", **_kwargs()
                )

        self.assertEqual(len(recorded_dirs), 1)
        self.assertEqual(Path(recorded_dirs[0]), target.parent)

    def test_replacement_source_is_temp_path_and_destination_is_resolved_target(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            real_replace = os.replace
            calls: list[tuple[Path, Path]] = []

            def spy_replace(src, dst):
                calls.append((Path(src), Path(dst)))
                self.assertTrue(Path(src).exists())
                self.assertEqual(Path(src).parent, target.parent)
                self.assertNotEqual(Path(src), target)
                return real_replace(src, dst)

            with mock.patch(
                f"{WRITER_MODULE_NAME}.os.replace", side_effect=spy_replace
            ):
                write_reference_traversal_output_atomically(
                    working_copy, "out.json", **_kwargs()
                )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], target)

    def test_serialize_mkstemp_and_replace_occur_in_order(self) -> None:
        order: list[str] = []
        real_serialize = contract.serialize_reference_traversal_output
        real_mkstemp = tempfile.mkstemp
        real_replace = os.replace

        def spy_serialize(**kwargs):
            order.append("serialize")
            return real_serialize(**kwargs)

        def spy_mkstemp(*args, **kwargs):
            order.append("mkstemp")
            return real_mkstemp(*args, **kwargs)

        def spy_replace(src, dst):
            order.append("replace")
            return real_replace(src, dst)

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            with mock.patch(
                f"{WRITER_MODULE_NAME}.serialize_reference_traversal_output",
                side_effect=spy_serialize,
            ), mock.patch(
                f"{WRITER_MODULE_NAME}.tempfile.mkstemp", side_effect=spy_mkstemp
            ), mock.patch(
                f"{WRITER_MODULE_NAME}.os.replace", side_effect=spy_replace
            ):
                write_reference_traversal_output_atomically(
                    working_copy, "out.json", **_kwargs()
                )

        self.assertEqual(order, ["serialize", "mkstemp", "replace"])

    def test_destination_is_not_replaced_until_content_write_succeeds(
        self,
    ) -> None:
        real_fdopen = os.fdopen
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            target.write_bytes(b"stale-preexisting-bytes")

            def failing_fdopen(fd, mode):
                return _FailingWriteFile(real_fdopen(fd, mode))

            with mock.patch(
                f"{WRITER_MODULE_NAME}.os.fdopen", side_effect=failing_fdopen
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError):
                    write_reference_traversal_output_atomically(
                        working_copy, "out.json", **_kwargs()
                    )

            self.assertEqual(target.read_bytes(), b"stale-preexisting-bytes")


# ---------------------------------------------------------------------------
# 14. Atomic writer: successful replacement and cleanup
# ---------------------------------------------------------------------------


class AtomicWriterSuccessfulReplacementTests(unittest.TestCase):
    def test_missing_destination_is_created_with_exact_bytes(self) -> None:
        kwargs = _kwargs()
        expected = contract.serialize_reference_traversal_output(**kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            write_reference_traversal_output_atomically(
                working_copy, "out.json", **kwargs
            )
            self.assertEqual(target.read_bytes(), expected)

    def test_existing_destination_is_atomically_replaced_with_exact_bytes(
        self,
    ) -> None:
        kwargs = _kwargs()
        expected = contract.serialize_reference_traversal_output(**kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            target.write_bytes(b"stale unrelated bytes")
            write_reference_traversal_output_atomically(
                working_copy, "out.json", **kwargs
            )
            self.assertEqual(target.read_bytes(), expected)

    def test_repeated_writes_remain_deterministic(self) -> None:
        kwargs = _kwargs()

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            write_reference_traversal_output_atomically(
                working_copy, "out.json", **kwargs
            )
            first = target.read_bytes()
            write_reference_traversal_output_atomically(
                working_copy, "out.json", **kwargs
            )
            second = target.read_bytes()
            self.assertEqual(first, second)

    def test_no_operation_owned_temporary_file_remains_after_success(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            write_reference_traversal_output_atomically(
                working_copy, "out.json", **_kwargs()
            )
            self.assertEqual(_list_names(working_copy), {"out.json"})

    def test_unrelated_sibling_files_are_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            sibling = working_copy / "sibling.txt"
            sibling.write_text("keep me", encoding="utf-8")
            write_reference_traversal_output_atomically(
                working_copy, "out.json", **_kwargs()
            )
            self.assertEqual(sibling.read_text(encoding="utf-8"), "keep me")

    def test_writer_does_not_create_any_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            write_reference_traversal_output_atomically(
                working_copy, "out.json", **_kwargs()
            )
            for entry in working_copy.iterdir():
                self.assertFalse(entry.is_dir())


# ---------------------------------------------------------------------------
# 15. Atomic writer: pre-replacement failure preservation
# ---------------------------------------------------------------------------


class AtomicWriterPreReplacementFailureTests(unittest.TestCase):
    def _assert_no_leftover_temp_files(self, working_copy, known_names) -> None:
        self.assertEqual(_list_names(working_copy), known_names)

    def test_resolver_failure_preserves_state_and_chains_cause(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            missing_working_copy = root / "does-not-exist"
            with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                write_reference_traversal_output_atomically(
                    missing_working_copy, "out.json", **_kwargs()
                )
            self.assertIsInstance(
                ctx.exception.__cause__,
                contract.ReferenceTraversalOutputContractError,
            )
            self.assertFalse(missing_working_copy.exists())
            self.assertEqual(_list_names(root), set())

    def test_serializer_failure_preserves_existing_destination_and_chains_cause(
        self,
    ) -> None:
        original = contract.ReferenceTraversalOutputContractError("boom")
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            target.write_bytes(b"preexisting-bytes")
            with mock.patch(
                f"{WRITER_MODULE_NAME}.serialize_reference_traversal_output",
                side_effect=original,
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                    write_reference_traversal_output_atomically(
                        working_copy, "out.json", **_kwargs()
                    )
            self.assertIs(ctx.exception.__cause__, original)
            self.assertEqual(target.read_bytes(), b"preexisting-bytes")
            self._assert_no_leftover_temp_files(working_copy, {"out.json"})

    def test_mkstemp_failure_preserves_existing_destination_and_chains_cause(
        self,
    ) -> None:
        original = OSError("mkstemp boom")
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            target.write_bytes(b"preexisting-bytes")
            with mock.patch(
                f"{WRITER_MODULE_NAME}.tempfile.mkstemp", side_effect=original
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                    write_reference_traversal_output_atomically(
                        working_copy, "out.json", **_kwargs()
                    )
            self.assertIs(ctx.exception.__cause__, original)
            self.assertEqual(target.read_bytes(), b"preexisting-bytes")
            self._assert_no_leftover_temp_files(working_copy, {"out.json"})

    def test_fdopen_failure_closes_descriptor_and_removes_temp_file(self) -> None:
        original = OSError("fdopen boom")
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            target.write_bytes(b"preexisting-bytes")
            with mock.patch(
                f"{WRITER_MODULE_NAME}.os.fdopen", side_effect=original
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                    write_reference_traversal_output_atomically(
                        working_copy, "out.json", **_kwargs()
                    )
            self.assertIs(ctx.exception.__cause__, original)
            self.assertEqual(target.read_bytes(), b"preexisting-bytes")
            self._assert_no_leftover_temp_files(working_copy, {"out.json"})

    def test_content_write_failure_preserves_destination_and_removes_temp_file(
        self,
    ) -> None:
        real_fdopen = os.fdopen
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            target.write_bytes(b"preexisting-bytes")

            def failing_fdopen(fd, mode):
                return _FailingWriteFile(real_fdopen(fd, mode))

            with mock.patch(
                f"{WRITER_MODULE_NAME}.os.fdopen", side_effect=failing_fdopen
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                    write_reference_traversal_output_atomically(
                        working_copy, "out.json", **_kwargs()
                    )
            self.assertIsInstance(ctx.exception.__cause__, OSError)
            self.assertEqual(target.read_bytes(), b"preexisting-bytes")
            self._assert_no_leftover_temp_files(working_copy, {"out.json"})

    def test_close_failure_preserves_destination_and_removes_temp_file(
        self,
    ) -> None:
        real_fdopen = os.fdopen
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            target.write_bytes(b"preexisting-bytes")

            def failing_close_fdopen(fd, mode):
                return _FailingCloseFile(real_fdopen(fd, mode))

            with mock.patch(
                f"{WRITER_MODULE_NAME}.os.fdopen", side_effect=failing_close_fdopen
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                    write_reference_traversal_output_atomically(
                        working_copy, "out.json", **_kwargs()
                    )
            self.assertIsInstance(ctx.exception.__cause__, OSError)
            self.assertEqual(target.read_bytes(), b"preexisting-bytes")
            self._assert_no_leftover_temp_files(working_copy, {"out.json"})

    def test_replace_failure_preserves_destination_and_removes_temp_file(
        self,
    ) -> None:
        original = OSError("replace boom")
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            target.write_bytes(b"preexisting-bytes")
            with mock.patch(
                f"{WRITER_MODULE_NAME}.os.replace", side_effect=original
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                    write_reference_traversal_output_atomically(
                        working_copy, "out.json", **_kwargs()
                    )
            self.assertIs(ctx.exception.__cause__, original)
            self.assertEqual(target.read_bytes(), b"preexisting-bytes")
            self._assert_no_leftover_temp_files(working_copy, {"out.json"})


# ---------------------------------------------------------------------------
# 16. Atomic writer: cleanup-failure precedence
# ---------------------------------------------------------------------------


class AtomicWriterCleanupFailurePrecedenceTests(unittest.TestCase):
    def test_cleanup_failure_does_not_mask_the_primary_replace_failure(
        self,
    ) -> None:
        primary = OSError("replace boom")
        cleanup = OSError("cleanup boom")
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            target = working_copy / "out.json"
            target.write_bytes(b"preexisting-bytes")
            with mock.patch(
                f"{WRITER_MODULE_NAME}.os.replace", side_effect=primary
            ), mock.patch.object(Path, "unlink", side_effect=cleanup):
                with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                    write_reference_traversal_output_atomically(
                        working_copy, "out.json", **_kwargs()
                    )
            self.assertIs(ctx.exception.__cause__, primary)
            self.assertIsNot(ctx.exception.__cause__, cleanup)
            self.assertEqual(target.read_bytes(), b"preexisting-bytes")

    def test_successful_write_never_invokes_cleanup_paths(self) -> None:
        # In the inspected implementation, descriptor/temporary_path are only
        # ever non-None in `finally` when a primary exception has already
        # been caught, so a cleanup-only failure (primary_error is None) is
        # unreachable through the public API. This proves cleanup is skipped
        # entirely on success, which is the contract that branch protects.
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            with mock.patch.object(
                Path, "unlink", side_effect=AssertionError("unlink must not run")
            ) as unlink_mock, mock.patch(
                f"{WRITER_MODULE_NAME}.os.close",
                side_effect=AssertionError("close must not run"),
            ) as close_mock:
                write_reference_traversal_output_atomically(
                    working_copy, "out.json", **_kwargs()
                )
            unlink_mock.assert_not_called()
            close_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 17. Atomic writer: error-message boundary
# ---------------------------------------------------------------------------


class AtomicWriterErrorMessageBoundaryTests(unittest.TestCase):
    def test_failure_message_includes_destination_and_excludes_payload_and_noise(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            requested = "out.json"
            with mock.patch(
                f"{WRITER_MODULE_NAME}.serialize_reference_traversal_output",
                side_effect=RuntimeError("boom"),
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError) as ctx:
                    write_reference_traversal_output_atomically(
                        working_copy,
                        requested,
                        **_kwargs(source_document="distinctive-secret-payload.FCStd"),
                    )
            message = str(ctx.exception)
            self.assertIn(requested, message)
            self.assertNotIn("distinctive-secret-payload.FCStd", message)
            self.assertNotIn("Traceback", message)
            self.assertNotIn("0x", message)
            self.assertEqual(len(message.splitlines()), 1)

    def test_failures_share_the_common_writer_error_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy = Path(tmp_dir)
            with mock.patch(
                f"{WRITER_MODULE_NAME}._resolve_output_path",
                side_effect=contract.ReferenceTraversalOutputContractError("boom"),
            ):
                with self.assertRaises(ReferenceTraversalOutputWriteError):
                    write_reference_traversal_output_atomically(
                        working_copy, "out.json", **_kwargs()
                    )


# ---------------------------------------------------------------------------
# 18. Atomic writer: private failure-phase classification
# ---------------------------------------------------------------------------


class AtomicWriterFailurePhaseTests(unittest.TestCase):
    def _assert_phase(self, error, *, containment: bool, original) -> None:
        self.assertEqual(error._is_containment_failure, containment)
        self.assertIs(error.__cause__, original)

    def test_containment_contract_failure_is_marked_as_containment(self) -> None:
        original = contract.ReferenceTraversalOutputContractError("escape")
        with tempfile.TemporaryDirectory() as tmp_dir, mock.patch(
            f"{WRITER_MODULE_NAME}._resolve_output_path", side_effect=original
        ):
            with self.assertRaises(ReferenceTraversalOutputWriteError) as caught:
                write_reference_traversal_output_atomically(
                    Path(tmp_dir), "out.json", **_kwargs()
                )

        self._assert_phase(caught.exception, containment=True, original=original)

    def test_serialization_contract_failure_is_marked_as_write(self) -> None:
        original = contract.ReferenceTraversalOutputContractError("serialize")
        with tempfile.TemporaryDirectory() as tmp_dir, mock.patch(
            f"{WRITER_MODULE_NAME}.serialize_reference_traversal_output",
            side_effect=original,
        ):
            with self.assertRaises(ReferenceTraversalOutputWriteError) as caught:
                write_reference_traversal_output_atomically(
                    Path(tmp_dir), "out.json", **_kwargs()
                )

        self._assert_phase(caught.exception, containment=False, original=original)

    def test_temporary_file_failure_is_marked_as_write(self) -> None:
        original = OSError("temporary file")
        with tempfile.TemporaryDirectory() as tmp_dir, mock.patch(
            f"{WRITER_MODULE_NAME}.tempfile.mkstemp", side_effect=original
        ):
            with self.assertRaises(ReferenceTraversalOutputWriteError) as caught:
                write_reference_traversal_output_atomically(
                    Path(tmp_dir), "out.json", **_kwargs()
                )

        self._assert_phase(caught.exception, containment=False, original=original)

    def test_atomic_replacement_failure_is_marked_as_write(self) -> None:
        original = OSError("replace")
        with tempfile.TemporaryDirectory() as tmp_dir, mock.patch(
            f"{WRITER_MODULE_NAME}.os.replace", side_effect=original
        ):
            with self.assertRaises(ReferenceTraversalOutputWriteError) as caught:
                write_reference_traversal_output_atomically(
                    Path(tmp_dir), "out.json", **_kwargs()
                )

        self._assert_phase(caught.exception, containment=False, original=original)


# ---------------------------------------------------------------------------
# 19. Direct writer: remains independent of containment resolution
# ---------------------------------------------------------------------------


class DirectWriterRemainsIndependentOfContainmentResolverTests(unittest.TestCase):
    def test_direct_writer_does_not_invoke_the_containment_resolver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "traversal.json"
            with mock.patch(
                f"{WRITER_MODULE_NAME}._resolve_output_path"
            ) as resolver:
                write_reference_traversal_output(path, **_kwargs())
            resolver.assert_not_called()


if __name__ == "__main__":
    unittest.main()
