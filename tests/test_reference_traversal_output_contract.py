from __future__ import annotations

import builtins
import importlib
import os
import sys
import tempfile
import types
import unittest
from dataclasses import FrozenInstanceError, fields as dataclass_fields, is_dataclass
from pathlib import Path
from unittest import mock

from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.common.paths import WORKING_COPY_DIR_NAME

MODULE_NAME = "parametron_freecad.runtime.reference_traversal_output_contract"


def _import_reference_traversal_output_contract_module():
    return importlib.import_module(MODULE_NAME)


def _node(**overrides):
    contract = _import_reference_traversal_output_contract_module()
    values = {
        "id": "node-a",
        "kind": "document",
        "state": contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
        "document_path": "assembly.FCStd",
        "object_name": "Body",
        "label": "Main Body",
        "diagnostic": "raw node diagnostic",
    }
    values.update(overrides)
    return contract.RawReferenceTraversalNode(**values)


def _edge(**overrides):
    contract = _import_reference_traversal_output_contract_module()
    values = {
        "source": "node-a",
        "target": "node-b",
        "kind": "external_link",
        "state": contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
        "diagnostic": "raw edge diagnostic",
    }
    values.update(overrides)
    return contract.RawReferenceTraversalEdge(**values)


def _diagnostic(**overrides):
    contract = _import_reference_traversal_output_contract_module()
    values = {
        "severity": "warning",
        "code": "raw_reference_warning",
        "message": "raw traversal diagnostic",
        "stage": "reference_scan",
    }
    values.update(overrides)
    return contract.RawReferenceTraversalDiagnostic(**values)


def _build_payload(contract, *, nodes=None, edges=None, diagnostics=None, **overrides):
    kwargs = {
        "boundary": contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
        "operation": contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
        "status": contract.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
        "source_document": "assembly.FCStd",
        "nodes": [_node()],
        "edges": [_edge()],
        "diagnostics": [_diagnostic()],
    }
    if nodes is not None:
        kwargs["nodes"] = nodes
    if edges is not None:
        kwargs["edges"] = edges
    if diagnostics is not None:
        kwargs["diagnostics"] = diagnostics
    kwargs.update(overrides)
    return contract.build_reference_traversal_output_payload(**kwargs)


class ReferenceTraversalOutputContractImportSafetyTests(unittest.TestCase):
    def test_import_succeeds_without_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()

        self.assertIsInstance(module, types.ModuleType)
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)

    def test_serializer_import_and_call_succeeds_without_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()
            result = module.serialize_reference_traversal_output(
                boundary=module.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
                operation=module.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
                status=module.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
                source_document="assembly.FCStd",
                nodes=[module.RawReferenceTraversalNode(
                    id="node-a",
                    kind="document",
                    state=module.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                )],
                edges=[],
                diagnostics=[],
            )

        self.assertIsInstance(result, bytes)
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ReferenceTraversalOutputContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_public_api_exports_expected_names(self) -> None:
        expected_public_api = {
            "REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION",
            "REFERENCE_TRAVERSAL_OUTPUT_KIND_RAW_REFERENCE_TRAVERSAL",
            "REFERENCE_TRAVERSAL_FIELD_SCHEMA_VERSION",
            "REFERENCE_TRAVERSAL_FIELD_KIND",
            "REFERENCE_TRAVERSAL_FIELD_BOUNDARY",
            "REFERENCE_TRAVERSAL_FIELD_OPERATION",
            "REFERENCE_TRAVERSAL_FIELD_STATUS",
            "REFERENCE_TRAVERSAL_FIELD_SOURCE_DOCUMENT",
            "REFERENCE_TRAVERSAL_FIELD_NODES",
            "REFERENCE_TRAVERSAL_FIELD_EDGES",
            "REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS",
            "REFERENCE_TRAVERSAL_NODE_FIELD_SEQUENCE",
            "REFERENCE_TRAVERSAL_NODE_FIELD_ID",
            "REFERENCE_TRAVERSAL_NODE_FIELD_KIND",
            "REFERENCE_TRAVERSAL_NODE_FIELD_STATE",
            "REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH",
            "REFERENCE_TRAVERSAL_NODE_FIELD_OBJECT_NAME",
            "REFERENCE_TRAVERSAL_NODE_FIELD_LABEL",
            "REFERENCE_TRAVERSAL_NODE_FIELD_DIAGNOSTIC",
            "REFERENCE_TRAVERSAL_EDGE_FIELD_SEQUENCE",
            "REFERENCE_TRAVERSAL_EDGE_FIELD_SOURCE",
            "REFERENCE_TRAVERSAL_EDGE_FIELD_TARGET",
            "REFERENCE_TRAVERSAL_EDGE_FIELD_KIND",
            "REFERENCE_TRAVERSAL_EDGE_FIELD_STATE",
            "REFERENCE_TRAVERSAL_EDGE_FIELD_DIAGNOSTIC",
            "REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_SEQUENCE",
            "REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_SEVERITY",
            "REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_CODE",
            "REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_MESSAGE",
            "REFERENCE_TRAVERSAL_DIAGNOSTIC_FIELD_STAGE",
            "REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS",
            "REFERENCE_TRAVERSAL_EMITTED_IDENTIFIER_FIELDS",
            "REFERENCE_TRAVERSAL_EMITTED_OBJECT_NAME_FIELDS",
            "REFERENCE_TRAVERSAL_EMITTED_LABEL_FIELDS",
            "REFERENCE_TRAVERSAL_EMITTED_INLINE_DIAGNOSTIC_FIELDS",
            "REFERENCE_TRAVERSAL_EMITTED_STRUCTURED_DIAGNOSTIC_FIELDS",
            "REFERENCE_TRAVERSAL_EMITTED_RAW_EVIDENCE_FIELDS",
            "REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT",
            "REFERENCE_TRAVERSAL_BOUNDARY_ENGINE_INVOCATION",
            "REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL",
            "REFERENCE_TRAVERSAL_STATUS_SUCCEEDED",
            "REFERENCE_TRAVERSAL_STATUS_PARTIAL",
            "REFERENCE_TRAVERSAL_STATUS_FAILED",
            "REFERENCE_TRAVERSAL_STATE_RESOLVED",
            "REFERENCE_TRAVERSAL_STATE_MISSING",
            "REFERENCE_TRAVERSAL_STATE_UNRESOLVED",
            "REFERENCE_TRAVERSAL_STATE_SKIPPED",
            "REFERENCE_TRAVERSAL_STATE_FAILED",
            "REFERENCE_TRAVERSAL_DEFINED_STATES",
            "REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS",
            "REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS",
            "REFERENCE_TRAVERSAL_DIAGNOSTIC_ORDER_FIELDS",
            "REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES",
            "REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_NODE",
            "REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_EDGE",
            "REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_ORDER",
            "REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL",
            "REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT",
            "REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE",
            "REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES",
            "REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE",
            "REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE",
            "REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE",
            "REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT",
            "REFERENCE_TRAVERSAL_NODE_KIND_OBJECT",
            "REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT",
            "REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE",
            "REFERENCE_TRAVERSAL_INTERNAL_REFERENCE_EDGE_KINDS",
            "REFERENCE_TRAVERSAL_EXTERNAL_REFERENCE_EDGE_KINDS",
            "REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR",
            "REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_WARNING",
            "REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_MALFORMED_REQUEST",
            "REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_UNSUPPORTED_REFERENCE_VALUE_SHAPE",
            "REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION",
            "REFERENCE_TRAVERSAL_STAGE_REFERENCE_DISCOVERY",
            "REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_ROOT",
            "REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_POLICY",
            "REFERENCE_TRAVERSAL_OUTPUT_PATH_PARENT_POLICY",
            "ReferenceTraversalOutputContractError",
            "RawReferenceTraversalNode",
            "RawReferenceTraversalEdge",
            "RawReferenceTraversalDiagnostic",
            "build_reference_traversal_output_payload",
            "build_reference_traversal_emitted_raw_evidence_contract",
            "build_reference_traversal_reference_distinction_contract",
            "build_reference_traversal_malformed_request_failure_contract",
            "build_reference_traversal_output_containment_contract",
            "build_malformed_reference_traversal_request_payload",
            "resolve_reference_traversal_output_path",
            "order_reference_traversal_nodes",
            "order_reference_traversal_edges",
            "build_reference_traversal_node_order_key",
            "build_reference_traversal_edge_order_key",
            "build_reference_traversal_diagnostic_order_key",
            "order_reference_traversal_diagnostics",
            "build_reference_traversal_unresolved_entry_order_key",
            "order_reference_traversal_unresolved_entries",
            "build_reference_traversal_total_ordering_contract",
            "REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS",
            "REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND",
            "REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS",
            "build_reference_traversal_semantic_node_identity_contract",
            "build_reference_traversal_semantic_node_identity_key",
            "REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS",
            "REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_EXCLUDED_FIELDS",
            "REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS",
            "build_reference_traversal_semantic_edge_identity_contract",
            "build_reference_traversal_semantic_edge_identity_key",
            "deduplicate_reference_traversal_semantic_edge_identity_keys",
            "REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE",
            "REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY",
            "REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM",
            "REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS",
            "REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS",
            "build_reference_traversal_discovery_semantics_contract",
            "build_reference_traversal_object_property_provenance_contract",
            "build_reference_traversal_runtime_state_semantics_contract",
            "build_reference_traversal_aggregate_status_semantics_contract",
            "build_reference_traversal_normalization_contract",
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS",
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_REQUEST_IDS",
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_ACTORS",
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_PROCESS_RUNTIME_IDENTITIES",
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS",
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER",
            "REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS",
            "build_reference_traversal_semantic_output_exclusion_contract",
            "serialize_reference_traversal_output",
            "REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS",
            "REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS",
            "REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS",
            "REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS",
            "build_reference_traversal_ordering_extension_contract",
        }

        self.assertEqual(set(self.contract.__all__), expected_public_api)

    def test_seven_new_provenance_and_discovery_exports_added(self) -> None:
        newly_added_exports = {
            "REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE",
            "REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY",
            "REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM",
            "REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS",
            "REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS",
            "build_reference_traversal_discovery_semantics_contract",
            "build_reference_traversal_object_property_provenance_contract",
        }

        self.assertEqual(len(newly_added_exports), 7)
        self.assertTrue(newly_added_exports.issubset(set(self.contract.__all__)))

    def test_eight_new_semantic_output_exclusion_exports_added(self) -> None:
        newly_added_exports = {
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS",
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_REQUEST_IDS",
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_ACTORS",
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_PROCESS_RUNTIME_IDENTITIES",
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS",
            "REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER",
            "REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS",
            "build_reference_traversal_semantic_output_exclusion_contract",
        }

        self.assertEqual(len(newly_added_exports), 8)
        self.assertTrue(newly_added_exports.issubset(set(self.contract.__all__)))
        for name in newly_added_exports:
            self.assertFalse(name.startswith("_"), name)
        self.assertTrue(
            callable(
                self.contract.build_reference_traversal_semantic_output_exclusion_contract
            )
        )

    def test_one_new_serializer_export_added(self) -> None:
        newly_added_exports = {"serialize_reference_traversal_output"}

        self.assertEqual(len(newly_added_exports), 1)
        self.assertTrue(newly_added_exports.issubset(set(self.contract.__all__)))
        for name in newly_added_exports:
            self.assertFalse(name.startswith("_"), name)
        self.assertTrue(callable(self.contract.serialize_reference_traversal_output))

    def test_five_new_ordering_extension_exports_added(self) -> None:
        newly_added_exports = {
            "REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS",
            "REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS",
            "REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS",
            "REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS",
            "build_reference_traversal_ordering_extension_contract",
        }

        self.assertEqual(len(newly_added_exports), 5)
        self.assertTrue(newly_added_exports.issubset(set(self.contract.__all__)))
        for name in newly_added_exports:
            self.assertFalse(name.startswith("_"), name)
            self.assertTrue(hasattr(self.contract, name), name)
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS, tuple
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS, tuple
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS, tuple
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS, tuple
        )
        self.assertTrue(
            callable(
                self.contract.build_reference_traversal_ordering_extension_contract
            )
        )

    def test_public_api_contains_no_private_helper_names(self) -> None:
        for name in self.contract.__all__:
            self.assertFalse(name.startswith("_"), name)

    def test_key_constants_match_contract_values(self) -> None:
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION, "1.0")
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_KIND_RAW_REFERENCE_TRAVERSAL,
            "raw_reference_traversal",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_FIELD_SCHEMA_VERSION,
            "schemaVersion",
        )
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_FIELD_KIND, "kind")
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_FIELD_BOUNDARY, "boundary")
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_FIELD_OPERATION, "operation")
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_FIELD_STATUS, "status")
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_FIELD_SOURCE_DOCUMENT,
            "sourceDocument",
        )
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_FIELD_NODES, "nodes")
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_FIELD_EDGES, "edges")
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS,
            "diagnostics",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
            "reference_traversal_entrypoint",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_BOUNDARY_ENGINE_INVOCATION,
            "engine_invocation",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
            "reference_traversal",
        )
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED, "succeeded")
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATUS_PARTIAL, "partial")
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATUS_FAILED, "failed")
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED, "resolved")
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATE_MISSING, "missing")
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED, "unresolved"
        )
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED, "skipped")
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATE_FAILED, "failed")
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES,
            (
                self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
                self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
                self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED,
                self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES,
            (
                "resolved",
                "missing",
                "unresolved",
                "skipped",
                "failed",
            ),
        )

    def test_node_order_fields_match_contract_priority(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS,
            (
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_DOCUMENT_PATH,
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_KIND,
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_ID,
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_OBJECT_NAME,
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_LABEL,
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_STATE,
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_DIAGNOSTIC,
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS,
            (
                "documentPath",
                "kind",
                "id",
                "objectName",
                "label",
                "state",
                "diagnostic",
            ),
        )

    def test_edge_order_fields_match_contract_priority(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS,
            (
                self.contract.REFERENCE_TRAVERSAL_EDGE_FIELD_SOURCE,
                self.contract.REFERENCE_TRAVERSAL_EDGE_FIELD_TARGET,
                self.contract.REFERENCE_TRAVERSAL_EDGE_FIELD_KIND,
                self.contract.REFERENCE_TRAVERSAL_EDGE_FIELD_STATE,
                self.contract.REFERENCE_TRAVERSAL_EDGE_FIELD_DIAGNOSTIC,
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS,
            (
                "source",
                "target",
                "kind",
                "state",
                "diagnostic",
            ),
        )

    def test_error_type_is_value_error(self) -> None:
        self.assertTrue(
            issubclass(
                self.contract.ReferenceTraversalOutputContractError,
                ValueError,
            )
        )

    def test_raw_items_are_frozen_slot_backed_dataclasses(self) -> None:
        node = _node()
        edge = _edge()
        diagnostic = _diagnostic()

        for item, field_name in (
            (node, "id"),
            (edge, "source"),
            (diagnostic, "message"),
        ):
            with self.subTest(item=type(item).__name__):
                self.assertTrue(is_dataclass(item))
                self.assertFalse(hasattr(item, "__dict__"))
                with self.assertRaises((FrozenInstanceError, AttributeError)):
                    setattr(item, field_name, "changed")

    def test_build_payload_returns_exact_successful_shape(self) -> None:
        nodes = [
            _node(
                id="assembly",
                kind="document",
                state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            ),
            _node(
                id="body",
                kind="object",
                state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                document_path="assembly.FCStd",
                object_name="Body",
                label="Main Body",
                diagnostic="object read",
            ),
        ]
        edges = [
            _edge(
                source="assembly",
                target="body",
                kind="contains",
                state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            ),
            _edge(
                source="body",
                target="external",
                kind="link",
                state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            ),
        ]
        diagnostics = [
            _diagnostic(
                severity="info",
                code="reference_seen",
                message="reference traversal captured raw values",
                stage="reference_traversal",
            )
        ]

        payload = _build_payload(
            self.contract,
            nodes=nodes,
            edges=edges,
            diagnostics=diagnostics,
        )

        self.assertEqual(
            payload,
            {
                "schemaVersion": "1.0",
                "kind": "raw_reference_traversal",
                "boundary": "reference_traversal_entrypoint",
                "operation": "reference_traversal",
                "status": "succeeded",
                "sourceDocument": "assembly.FCStd",
                "nodes": [
                    {
                        "sequence": 0,
                        "id": "assembly",
                        "kind": "document",
                        "state": "resolved",
                        "documentPath": "assembly.FCStd",
                        "objectName": "Body",
                        "label": "Main Body",
                        "diagnostic": "raw node diagnostic",
                    },
                    {
                        "sequence": 1,
                        "id": "body",
                        "kind": "object",
                        "state": "resolved",
                        "documentPath": "assembly.FCStd",
                        "objectName": "Body",
                        "label": "Main Body",
                        "diagnostic": "object read",
                    },
                ],
                "edges": [
                    {
                        "sequence": 0,
                        "source": "assembly",
                        "target": "body",
                        "kind": "contains",
                        "state": "resolved",
                        "diagnostic": "raw edge diagnostic",
                    },
                    {
                        "sequence": 1,
                        "source": "body",
                        "target": "external",
                        "kind": "link",
                        "state": "resolved",
                        "diagnostic": "raw edge diagnostic",
                    },
                ],
                "diagnostics": [
                    {
                        "sequence": 0,
                        "severity": "info",
                        "code": "reference_seen",
                        "message": "reference traversal captured raw values",
                        "stage": "reference_traversal",
                    }
                ],
            },
        )

    def test_nodes_and_edges_are_ordered_before_zero_based_sequencing(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(id="node-c"),
                _node(id="node-a"),
                _node(id="node-b"),
            ],
            edges=[
                _edge(source="node-c", target="node-a"),
                _edge(source="node-a", target="node-b"),
            ],
            diagnostics=[
                _diagnostic(code="third"),
                _diagnostic(code="first"),
                _diagnostic(code="second"),
            ],
        )

        self.assertEqual(
            [(item["sequence"], item["id"]) for item in payload["nodes"]],
            [(0, "node-a"), (1, "node-b"), (2, "node-c")],
        )
        self.assertEqual(
            [
                (item["sequence"], item["source"], item["target"])
                for item in payload["edges"]
            ],
            [(0, "node-a", "node-b"), (1, "node-c", "node-a")],
        )
        self.assertEqual(
            [(item["sequence"], item["code"]) for item in payload["diagnostics"]],
            [(0, "first"), (1, "second"), (2, "third")],
        )

    def test_optional_fields_normalize_to_null_when_omitted(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(document_path=None, object_name=None, label=None, diagnostic=None)],
            edges=[_edge(diagnostic=None)],
            diagnostics=[_diagnostic(stage=None)],
        )

        self.assertIsNone(payload["nodes"][0]["documentPath"])
        self.assertIsNone(payload["nodes"][0]["objectName"])
        self.assertIsNone(payload["nodes"][0]["label"])
        self.assertIsNone(payload["nodes"][0]["diagnostic"])
        self.assertIsNone(payload["edges"][0]["diagnostic"])
        self.assertIsNone(payload["diagnostics"][0]["stage"])

    def test_invalid_top_level_fields_raise_deterministic_errors(self) -> None:
        invalid_cases = (
            ("boundary", "boundary", ""),
            ("boundary", "boundary", 123),
            ("operation", "operation", ""),
            ("operation", "operation", 123),
            ("status", "status", ""),
            ("status", "status", 123),
            ("source_document", "sourceDocument", ""),
            ("source_document", "sourceDocument", 123),
        )

        for argument_name, message_field_name, value in invalid_cases:
            with self.subTest(argument_name=argument_name, value=value):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, **{argument_name: value})

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn(message_field_name, message)

    def test_invalid_sequence_inputs_raise_deterministic_errors(self) -> None:
        invalid_cases = (
            ("nodes", "not-nodes"),
            ("nodes", b"not-nodes"),
            ("nodes", object()),
            ("edges", "not-edges"),
            ("edges", b"not-edges"),
            ("edges", object()),
            ("diagnostics", "not-diagnostics"),
            ("diagnostics", b"not-diagnostics"),
            ("diagnostics", object()),
        )

        for field_name, value in invalid_cases:
            with self.subTest(field_name=field_name, value=value):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, **{field_name: value})

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn(field_name, message)

    def test_wrong_sequence_item_types_raise_deterministic_errors(self) -> None:
        invalid_cases = (
            ("nodes", [object()]),
            ("edges", [object()]),
            ("diagnostics", [object()]),
        )

        for field_name, value in invalid_cases:
            with self.subTest(field_name=field_name):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, **{field_name: value})

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn(field_name, message)

    def test_invalid_required_node_fields_raise_deterministic_errors(self) -> None:
        invalid_cases = (
            ("id", ""),
            ("id", 123),
            ("kind", ""),
            ("kind", 123),
        )

        for field_name, value in invalid_cases:
            with self.subTest(field_name=field_name, value=value):
                node = _node()
                object.__setattr__(node, field_name, value)

                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, nodes=[node])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn(field_name, message)

    def test_malformed_node_state_values_raise_deterministic_errors(self) -> None:
        invalid_states = ("", "   ", None, 123)

        for state in invalid_states:
            with self.subTest(state=state):
                node = _node()
                object.__setattr__(node, "state", state)

                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, nodes=[node])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("state", message)

    def test_invalid_required_edge_fields_raise_deterministic_errors(self) -> None:
        invalid_cases = (
            ("source", ""),
            ("source", 123),
            ("target", ""),
            ("target", 123),
            ("kind", ""),
            ("kind", 123),
        )

        for field_name, value in invalid_cases:
            with self.subTest(field_name=field_name, value=value):
                edge = _edge()
                object.__setattr__(edge, field_name, value)

                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, edges=[edge])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn(field_name, message)

    def test_malformed_edge_state_values_raise_deterministic_errors(self) -> None:
        invalid_states = ("", "   ", None, 123)

        for state in invalid_states:
            with self.subTest(state=state):
                edge = _edge()
                object.__setattr__(edge, "state", state)

                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, edges=[edge])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("state", message)

    def test_invalid_required_diagnostic_fields_raise_deterministic_errors(
        self,
    ) -> None:
        invalid_cases = (
            ("severity", ""),
            ("severity", 123),
            ("code", ""),
            ("code", 123),
            ("message", ""),
            ("message", 123),
        )

        for field_name, value in invalid_cases:
            with self.subTest(field_name=field_name, value=value):
                diagnostic = _diagnostic()
                object.__setattr__(diagnostic, field_name, value)

                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, diagnostics=[diagnostic])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn(field_name, message)

    def test_invalid_optional_node_fields_raise_deterministic_errors(self) -> None:
        invalid_cases = (
            ("document_path", "documentPath", ""),
            ("document_path", "documentPath", 123),
            ("object_name", "objectName", ""),
            ("object_name", "objectName", 123),
            ("label", "label", ""),
            ("label", "label", 123),
            ("diagnostic", "diagnostic", ""),
            ("diagnostic", "diagnostic", 123),
        )

        for field_name, message_field_name, value in invalid_cases:
            with self.subTest(field_name=field_name, value=value):
                node = _node(**{field_name: value})

                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, nodes=[node])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn(message_field_name, message)

    def test_invalid_optional_edge_fields_raise_deterministic_errors(self) -> None:
        for value in ("", 123):
            with self.subTest(value=value):
                edge = _edge(diagnostic=value)

                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, edges=[edge])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("diagnostic", message)

    def test_invalid_optional_diagnostic_fields_raise_deterministic_errors(
        self,
    ) -> None:
        for value in ("", 123):
            with self.subTest(value=value):
                diagnostic = _diagnostic(stage=value)

                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, diagnostics=[diagnostic])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("stage", message)

    def test_defined_resolved_state_vocabulary_is_preserved(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED)],
            edges=[_edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED)],
        )

        self.assertEqual(payload["nodes"][0]["state"], "resolved")
        self.assertEqual(payload["edges"][0]["state"], "resolved")

    def test_defined_missing_node_state_vocabulary_is_preserved(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)],
        )

        self.assertEqual(payload["nodes"][0]["state"], "missing")

    def test_defined_missing_edge_state_vocabulary_is_preserved(self) -> None:
        payload = _build_payload(
            self.contract,
            edges=[_edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)],
        )

        self.assertEqual(payload["edges"][0]["state"], "missing")

    def test_defined_unresolved_node_state_vocabulary_is_accepted(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED)],
        )

        self.assertEqual(payload["nodes"][0]["state"], "unresolved")

    def test_defined_unresolved_edge_state_vocabulary_is_accepted(self) -> None:
        payload = _build_payload(
            self.contract,
            edges=[_edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED)],
        )

        self.assertEqual(payload["edges"][0]["state"], "unresolved")

    def test_unresolved_payload_is_compatible_with_canonical_json(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED)],
            edges=[_edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED)],
        )

        serialized = dumps_canonical(payload)

        self.assertIn('"state":"unresolved"', serialized)
        self.assertEqual(dumps_canonical(payload), serialized)
        self.assertNotIsInstance(
            payload["nodes"][0],
            self.contract.RawReferenceTraversalNode,
        )
        self.assertNotIsInstance(
            payload["edges"][0],
            self.contract.RawReferenceTraversalEdge,
        )

    def test_defined_skipped_node_state_vocabulary_is_accepted(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED)],
        )

        self.assertEqual(payload["nodes"][0]["state"], "skipped")

    def test_defined_skipped_edge_state_vocabulary_is_accepted(self) -> None:
        payload = _build_payload(
            self.contract,
            edges=[_edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED)],
        )

        self.assertEqual(payload["edges"][0]["state"], "skipped")

    def test_defined_failed_node_state_vocabulary_is_accepted(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED)],
        )

        self.assertEqual(payload["nodes"][0]["state"], "failed")

    def test_defined_failed_edge_state_vocabulary_is_accepted(self) -> None:
        payload = _build_payload(
            self.contract,
            edges=[_edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED)],
        )

        self.assertEqual(payload["edges"][0]["state"], "failed")

    def test_skipped_and_failed_states_serialize_exactly_as_provided(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(
                    id="skipped-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED,
                ),
                _node(
                    id="failed-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
                ),
            ],
            edges=[
                _edge(
                    source="skipped-node",
                    target="failed-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED,
                ),
                _edge(
                    source="failed-node",
                    target="external-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
                ),
            ],
        )

        self.assertEqual(
            [(item["sequence"], item["id"], item["state"]) for item in payload["nodes"]],
            [(0, "failed-node", "failed"), (1, "skipped-node", "skipped")],
        )
        self.assertEqual(
            [
                (item["sequence"], item["source"], item["target"], item["state"])
                for item in payload["edges"]
            ],
            [
                (0, "failed-node", "external-node", "failed"),
                (1, "skipped-node", "failed-node", "skipped"),
            ],
        )

    def test_skipped_and_failed_payload_is_compatible_with_canonical_json(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(
                    id="skipped-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED,
                ),
                _node(
                    id="failed-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
                ),
            ],
            edges=[
                _edge(
                    source="skipped-node",
                    target="failed-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED,
                ),
                _edge(
                    source="failed-node",
                    target="external-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
                ),
            ],
        )

        serialized = dumps_canonical(payload)

        self.assertIn('"state":"skipped"', serialized)
        self.assertIn('"state":"failed"', serialized)
        self.assertEqual(dumps_canonical(payload), serialized)
        self.assertNotIsInstance(
            payload["nodes"][0],
            self.contract.RawReferenceTraversalNode,
        )
        self.assertNotIsInstance(
            payload["edges"][0],
            self.contract.RawReferenceTraversalEdge,
        )

    def test_mixed_resolved_and_missing_states_are_ordered_with_sequences(
        self,
    ) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(
                    id="resolved-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                ),
                _node(
                    id="missing-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
                ),
            ],
            edges=[
                _edge(
                    source="resolved-node",
                    target="missing-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                ),
                _edge(
                    source="missing-node",
                    target="external-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
                ),
            ],
        )

        self.assertEqual(
            [(item["sequence"], item["id"], item["state"]) for item in payload["nodes"]],
            [(0, "missing-node", "missing"), (1, "resolved-node", "resolved")],
        )
        self.assertEqual(
            [
                (item["sequence"], item["source"], item["target"], item["state"])
                for item in payload["edges"]
            ],
            [
                (0, "missing-node", "external-node", "missing"),
                (1, "resolved-node", "missing-node", "resolved"),
            ],
        )

    def test_invalid_node_state_vocabulary_raises_deterministic_errors(self) -> None:
        invalid_states = (
            "caller_provided_state",
            "opened",
            "observed",
            "reported",
            "raw_state_from_future_traversal",
            "unknown",
        )

        for state in invalid_states:
            with self.subTest(state=state):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, nodes=[_node(state=state)])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("state", message)
                self.assertIn("resolved", message)
                self.assertIn("missing", message)

    def test_invalid_edge_state_vocabulary_raises_deterministic_errors(self) -> None:
        invalid_states = (
            "caller_provided_state",
            "opened",
            "observed",
            "reported",
            "raw_state_from_future_traversal",
            "unknown",
        )

        for state in invalid_states:
            with self.subTest(state=state):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    _build_payload(self.contract, edges=[_edge(state=state)])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("state", message)
                self.assertIn("resolved", message)
                self.assertIn("missing", message)

    def test_graph_semantics_are_not_validated_yet(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(id="duplicate-node"),
                _node(id="duplicate-node"),
            ],
            edges=[
                _edge(source="missing-source", target="missing-target", kind="link"),
                _edge(source="missing-source", target="missing-target", kind="link"),
            ],
        )

        self.assertEqual(
            [node["id"] for node in payload["nodes"]],
            ["duplicate-node", "duplicate-node"],
        )
        self.assertEqual(
            [(edge["source"], edge["target"], edge["kind"]) for edge in payload["edges"]],
            [
                ("missing-source", "missing-target", "link"),
                ("missing-source", "missing-target", "link"),
            ],
        )

    def test_payload_is_compatible_with_canonical_json(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)],
            edges=[_edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)],
        )

        serialized = dumps_canonical(payload)

        self.assertIn('"kind":"raw_reference_traversal"', serialized)
        self.assertIn('"state":"missing"', serialized)
        self.assertIn('"nodes":[{', serialized)
        self.assertIn('"edges":[{', serialized)
        self.assertIn('"diagnostics":[{', serialized)
        self.assertNotIsInstance(
            payload["nodes"][0],
            self.contract.RawReferenceTraversalNode,
        )
        self.assertNotIsInstance(
            payload["edges"][0],
            self.contract.RawReferenceTraversalEdge,
        )
        self.assertNotIsInstance(
            payload["diagnostics"][0],
            self.contract.RawReferenceTraversalDiagnostic,
        )

    def test_inputs_are_not_mutated(self) -> None:
        nodes = [_node(id="node-a"), _node(id="node-b")]
        edges = [_edge(source="node-a", target="node-b")]
        diagnostics = [_diagnostic(code="raw_reference_warning")]
        before = (list(nodes), list(edges), list(diagnostics))

        _build_payload(
            self.contract,
            nodes=nodes,
            edges=edges,
            diagnostics=diagnostics,
        )

        self.assertEqual((nodes, edges, diagnostics), before)

    def test_repeated_calls_return_equal_independent_payloads(self) -> None:
        nodes = [_node(id="node-a")]
        edges = [_edge(source="node-a", target="node-b")]
        diagnostics = [_diagnostic(code="raw_reference_warning")]

        first = _build_payload(
            self.contract,
            nodes=nodes,
            edges=edges,
            diagnostics=diagnostics,
        )
        second = _build_payload(
            self.contract,
            nodes=nodes,
            edges=edges,
            diagnostics=diagnostics,
        )

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["nodes"], second["nodes"])
        self.assertIsNot(first["edges"], second["edges"])
        self.assertIsNot(first["diagnostics"], second["diagnostics"])

        first["nodes"][0]["id"] = "mutated"
        first["edges"][0]["source"] = "mutated"
        first["diagnostics"][0]["code"] = "mutated"
        self.assertEqual(second["nodes"][0]["id"], "node-a")
        self.assertEqual(second["edges"][0]["source"], "node-a")
        self.assertEqual(second["diagnostics"][0]["code"], "raw_reference_warning")

    def test_order_reference_traversal_nodes_returns_deterministic_order(self) -> None:
        ordered = self.contract.order_reference_traversal_nodes(
            [
                _node(id="node-c"),
                _node(id="node-a"),
                _node(id="node-b"),
            ]
        )

        self.assertEqual(
            [node.id for node in ordered],
            ["node-a", "node-b", "node-c"],
        )
        self.assertIsInstance(ordered, tuple)

    def test_order_reference_traversal_nodes_follows_field_priority(self) -> None:
        priority_cases = (
            ("document_path", "a", "b"),
            ("kind", "a", "b"),
            ("id", "a", "b"),
            ("object_name", "a", "b"),
            ("label", "a", "b"),
            ("state", "failed", "missing"),
            ("diagnostic", "a", "b"),
        )

        for field_name, low, high in priority_cases:
            with self.subTest(field_name=field_name):
                low_node = _node(**{field_name: low})
                high_node = _node(**{field_name: high})

                ordered = self.contract.order_reference_traversal_nodes(
                    [high_node, low_node]
                )

                self.assertEqual(ordered, (low_node, high_node))

    def test_order_reference_traversal_nodes_documentpath_dominates_later_fields(
        self,
    ) -> None:
        earlier_wins = _node(
            document_path="a",
            kind="z",
            id="z",
            object_name="z",
            label="z",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
            diagnostic="z",
        )
        later_loses = _node(
            document_path="b",
            kind="a",
            id="a",
            object_name="a",
            label="a",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
            diagnostic="a",
        )

        ordered = self.contract.order_reference_traversal_nodes(
            [later_loses, earlier_wins]
        )

        self.assertEqual(ordered, (earlier_wins, later_loses))

    def test_order_reference_traversal_nodes_is_case_sensitive(self) -> None:
        upper = _node(kind="Z")
        lower = _node(kind="a")

        ordered = self.contract.order_reference_traversal_nodes([lower, upper])

        self.assertEqual(ordered, (upper, lower))

    def test_order_reference_traversal_nodes_does_not_strip_whitespace(self) -> None:
        leading_space = _node(kind=" b")
        plain = _node(kind="a")

        ordered = self.contract.order_reference_traversal_nodes([plain, leading_space])

        self.assertEqual(ordered, (leading_space, plain))

    def test_order_reference_traversal_nodes_does_not_normalize_paths(self) -> None:
        dotted = _node(document_path="./a.FCStd")
        plain = _node(document_path="a.FCStd")

        ordered = self.contract.order_reference_traversal_nodes([plain, dotted])

        self.assertEqual(ordered, (dotted, plain))
        self.assertEqual(
            [node.document_path for node in ordered],
            ["./a.FCStd", "a.FCStd"],
        )

    def test_order_reference_traversal_nodes_sorts_none_optionals_first(self) -> None:
        optional_fields = ("document_path", "object_name", "label", "diagnostic")

        for field_name in optional_fields:
            with self.subTest(field_name=field_name):
                none_node = _node(**{field_name: None})
                provided_node = _node(**{field_name: "provided"})

                ordered = self.contract.order_reference_traversal_nodes(
                    [provided_node, none_node]
                )

                self.assertEqual(ordered, (none_node, provided_node))

    def test_order_reference_traversal_nodes_is_independent_and_non_mutating(
        self,
    ) -> None:
        nodes = [_node(id="node-b"), _node(id="node-a")]
        snapshot = list(nodes)

        ordered = self.contract.order_reference_traversal_nodes(nodes)

        self.assertEqual(nodes, snapshot)
        self.assertIsInstance(ordered, tuple)
        nodes.append(_node(id="node-c"))
        self.assertEqual([node.id for node in ordered], ["node-a", "node-b"])

    def test_order_reference_traversal_nodes_accepts_tuple_without_mutation(
        self,
    ) -> None:
        nodes = (_node(id="node-b"), _node(id="node-a"))

        ordered = self.contract.order_reference_traversal_nodes(nodes)

        self.assertEqual(nodes, (_node(id="node-b"), _node(id="node-a")))
        self.assertEqual([node.id for node in ordered], ["node-a", "node-b"])

    def test_order_reference_traversal_nodes_repeated_calls_return_equal_results(
        self,
    ) -> None:
        nodes = [_node(id="node-b"), _node(id="node-a")]

        first = self.contract.order_reference_traversal_nodes(nodes)
        second = self.contract.order_reference_traversal_nodes(nodes)

        self.assertEqual(first, second)

    def test_order_reference_traversal_nodes_rejects_invalid_containers_and_items(
        self,
    ) -> None:
        invalid_cases = (
            "not-nodes",
            b"not-nodes",
            object(),
            [object()],
            [_edge()],
        )

        for value in invalid_cases:
            with self.subTest(value=value):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.contract.order_reference_traversal_nodes(value)

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("nodes", message)

    def test_order_reference_traversal_edges_returns_deterministic_order(self) -> None:
        ordered = self.contract.order_reference_traversal_edges(
            [
                _edge(source="node-c"),
                _edge(source="node-a"),
                _edge(source="node-b"),
            ]
        )

        self.assertEqual(
            [edge.source for edge in ordered],
            ["node-a", "node-b", "node-c"],
        )
        self.assertIsInstance(ordered, tuple)

    def test_order_reference_traversal_edges_follows_field_priority(self) -> None:
        priority_cases = (
            ("source", "a", "b"),
            ("target", "a", "b"),
            ("kind", "a", "b"),
            ("state", "failed", "missing"),
            ("diagnostic", "a", "b"),
        )

        for field_name, low, high in priority_cases:
            with self.subTest(field_name=field_name):
                low_edge = _edge(**{field_name: low})
                high_edge = _edge(**{field_name: high})

                ordered = self.contract.order_reference_traversal_edges(
                    [high_edge, low_edge]
                )

                self.assertEqual(ordered, (low_edge, high_edge))

    def test_order_reference_traversal_edges_source_dominates_later_fields(self) -> None:
        earlier_wins = _edge(
            source="a",
            target="z",
            kind="z",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
            diagnostic="z",
        )
        later_loses = _edge(
            source="b",
            target="a",
            kind="a",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
            diagnostic="a",
        )

        ordered = self.contract.order_reference_traversal_edges(
            [later_loses, earlier_wins]
        )

        self.assertEqual(ordered, (earlier_wins, later_loses))

    def test_order_reference_traversal_edges_is_case_sensitive(self) -> None:
        upper = _edge(source="Z")
        lower = _edge(source="a")

        ordered = self.contract.order_reference_traversal_edges([lower, upper])

        self.assertEqual(ordered, (upper, lower))

    def test_order_reference_traversal_edges_does_not_strip_whitespace(self) -> None:
        leading_space = _edge(source=" b")
        plain = _edge(source="a")

        ordered = self.contract.order_reference_traversal_edges([plain, leading_space])

        self.assertEqual(ordered, (leading_space, plain))

    def test_order_reference_traversal_edges_sorts_none_diagnostic_first(self) -> None:
        none_edge = _edge(diagnostic=None)
        provided_edge = _edge(diagnostic="provided")

        ordered = self.contract.order_reference_traversal_edges(
            [provided_edge, none_edge]
        )

        self.assertEqual(ordered, (none_edge, provided_edge))

    def test_order_reference_traversal_edges_is_independent_and_non_mutating(
        self,
    ) -> None:
        edges = [_edge(source="node-b"), _edge(source="node-a")]
        snapshot = list(edges)

        ordered = self.contract.order_reference_traversal_edges(edges)

        self.assertEqual(edges, snapshot)
        self.assertIsInstance(ordered, tuple)
        edges.append(_edge(source="node-c"))
        self.assertEqual([edge.source for edge in ordered], ["node-a", "node-b"])

    def test_order_reference_traversal_edges_accepts_tuple_without_mutation(
        self,
    ) -> None:
        edges = (_edge(source="node-b"), _edge(source="node-a"))

        ordered = self.contract.order_reference_traversal_edges(edges)

        self.assertEqual(edges, (_edge(source="node-b"), _edge(source="node-a")))
        self.assertEqual([edge.source for edge in ordered], ["node-a", "node-b"])

    def test_order_reference_traversal_edges_repeated_calls_return_equal_results(
        self,
    ) -> None:
        edges = [_edge(source="node-b"), _edge(source="node-a")]

        first = self.contract.order_reference_traversal_edges(edges)
        second = self.contract.order_reference_traversal_edges(edges)

        self.assertEqual(first, second)

    def test_order_reference_traversal_edges_rejects_invalid_containers_and_items(
        self,
    ) -> None:
        invalid_cases = (
            "not-edges",
            b"not-edges",
            object(),
            [object()],
            [_node()],
        )

        for value in invalid_cases:
            with self.subTest(value=value):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.contract.order_reference_traversal_edges(value)

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("edges", message)

    def test_build_payload_node_order_matches_order_helper(self) -> None:
        nodes = [
            _node(id="node-c"),
            _node(id="node-a"),
            _node(id="node-b"),
        ]

        payload = _build_payload(self.contract, nodes=nodes)
        expected = self.contract.order_reference_traversal_nodes(nodes)

        self.assertEqual(
            [node["id"] for node in payload["nodes"]],
            [node.id for node in expected],
        )
        self.assertEqual(
            [node["sequence"] for node in payload["nodes"]],
            [0, 1, 2],
        )

    def test_build_payload_edge_order_matches_order_helper(self) -> None:
        edges = [
            _edge(source="node-c", target="node-a"),
            _edge(source="node-a", target="node-b"),
        ]

        payload = _build_payload(self.contract, edges=edges)
        expected = self.contract.order_reference_traversal_edges(edges)

        self.assertEqual(
            [(edge["source"], edge["target"]) for edge in payload["edges"]],
            [(edge.source, edge.target) for edge in expected],
        )
        self.assertEqual(
            [edge["sequence"] for edge in payload["edges"]],
            [0, 1],
        )

    def test_build_payload_orders_diagnostics_deterministically_before_sequencing(
        self,
    ) -> None:
        caller_diagnostics = [
            _diagnostic(code="zebra"),
            _diagnostic(code="alpha"),
            _diagnostic(code="mid"),
        ]
        snapshot = list(caller_diagnostics)

        payload = _build_payload(
            self.contract,
            diagnostics=caller_diagnostics,
        )

        self.assertEqual(
            [(item["sequence"], item["code"]) for item in payload["diagnostics"]],
            [(0, "alpha"), (1, "mid"), (2, "zebra")],
        )
        self.assertEqual(caller_diagnostics, snapshot)

    def test_build_payload_diagnostic_order_matches_order_helper(self) -> None:
        diagnostics = [
            _diagnostic(code="zebra"),
            _diagnostic(code="alpha"),
            _diagnostic(code="mid"),
        ]

        payload = _build_payload(self.contract, diagnostics=diagnostics)
        expected = self.contract.order_reference_traversal_diagnostics(diagnostics)

        self.assertEqual(
            [item["code"] for item in payload["diagnostics"]],
            [diagnostic.code for diagnostic in expected],
        )
        self.assertEqual(
            [item["sequence"] for item in payload["diagnostics"]],
            [0, 1, 2],
        )

    def test_contract_does_not_expose_runtime_wiring_functions(self) -> None:
        self.assertFalse(hasattr(self.contract, "write_reference_traversal_output"))
        self.assertFalse(hasattr(self.contract, "write_reference_traversal_file"))
        self.assertFalse(hasattr(self.contract, "run_reference_traversal_entrypoint"))


class ReferenceTraversalEmittedRawEvidenceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_emitted_path_fields_are_contract_field_paths(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS,
            (
                "sourceDocument",
                "nodes[].documentPath",
            ),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS, tuple
        )
        for field in self.contract.REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS:
            self.assertIsInstance(field, str)
            self.assertNotIn("/", field)
            self.assertNotIn("\\", field)

    def test_emitted_identifier_fields_are_raw_traversal_identifiers(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_IDENTIFIER_FIELDS,
            (
                "nodes[].id",
                "edges[].source",
                "edges[].target",
            ),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_IDENTIFIER_FIELDS, tuple
        )
        for field in self.contract.REFERENCE_TRAVERSAL_EMITTED_IDENTIFIER_FIELDS:
            self.assertNotIn("durable", field.lower())
            self.assertNotIn("pdm", field.lower())

    def test_emitted_object_name_fields(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_OBJECT_NAME_FIELDS,
            ("nodes[].objectName",),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_OBJECT_NAME_FIELDS, tuple
        )

    def test_emitted_label_fields(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_LABEL_FIELDS,
            ("nodes[].label",),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_LABEL_FIELDS, tuple
        )

    def test_emitted_inline_diagnostic_fields(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_INLINE_DIAGNOSTIC_FIELDS,
            (
                "nodes[].diagnostic",
                "edges[].diagnostic",
            ),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_INLINE_DIAGNOSTIC_FIELDS, tuple
        )

    def test_emitted_structured_diagnostic_fields(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_STRUCTURED_DIAGNOSTIC_FIELDS,
            (
                "diagnostics[].severity",
                "diagnostics[].code",
                "diagnostics[].message",
                "diagnostics[].stage",
            ),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_STRUCTURED_DIAGNOSTIC_FIELDS,
            tuple,
        )

    def test_aggregate_emitted_raw_evidence_fields_is_deterministic_tuple(self) -> None:
        aggregate = self.contract.REFERENCE_TRAVERSAL_EMITTED_RAW_EVIDENCE_FIELDS

        self.assertIsInstance(aggregate, tuple)
        self.assertEqual(
            aggregate,
            (
                "sourceDocument",
                "nodes[].documentPath",
                "nodes[].id",
                "edges[].source",
                "edges[].target",
                "nodes[].objectName",
                "nodes[].label",
                "nodes[].diagnostic",
                "edges[].diagnostic",
                "diagnostics[].severity",
                "diagnostics[].code",
                "diagnostics[].message",
                "diagnostics[].stage",
            ),
        )

    def test_aggregate_groups_categories_without_loss_or_reorder(self) -> None:
        aggregate = self.contract.REFERENCE_TRAVERSAL_EMITTED_RAW_EVIDENCE_FIELDS
        expected = (
            self.contract.REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS
            + self.contract.REFERENCE_TRAVERSAL_EMITTED_IDENTIFIER_FIELDS
            + self.contract.REFERENCE_TRAVERSAL_EMITTED_OBJECT_NAME_FIELDS
            + self.contract.REFERENCE_TRAVERSAL_EMITTED_LABEL_FIELDS
            + self.contract.REFERENCE_TRAVERSAL_EMITTED_INLINE_DIAGNOSTIC_FIELDS
            + self.contract.REFERENCE_TRAVERSAL_EMITTED_STRUCTURED_DIAGNOSTIC_FIELDS
        )

        self.assertEqual(aggregate, expected)
        self.assertEqual(len(aggregate), len(expected))

    def test_aggregate_emitted_raw_evidence_fields_is_immutable(self) -> None:
        aggregate = self.contract.REFERENCE_TRAVERSAL_EMITTED_RAW_EVIDENCE_FIELDS

        self.assertIsInstance(aggregate, tuple)
        self.assertNotIsInstance(aggregate, list)
        self.assertNotIsInstance(aggregate, dict)

    def test_helper_output_is_deterministic_and_independent(self) -> None:
        first = self.contract.build_reference_traversal_emitted_raw_evidence_contract()
        second = self.contract.build_reference_traversal_emitted_raw_evidence_contract()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_helper_output_contains_expected_categories_and_fields(self) -> None:
        payload = (
            self.contract.build_reference_traversal_emitted_raw_evidence_contract()
        )

        self.assertEqual(
            payload,
            {
                "pathFields": ["sourceDocument", "nodes[].documentPath"],
                "identifierFields": [
                    "nodes[].id",
                    "edges[].source",
                    "edges[].target",
                ],
                "objectNameFields": ["nodes[].objectName"],
                "labelFields": ["nodes[].label"],
                "inlineDiagnosticFields": [
                    "nodes[].diagnostic",
                    "edges[].diagnostic",
                ],
                "structuredDiagnosticFields": [
                    "diagnostics[].severity",
                    "diagnostics[].code",
                    "diagnostics[].message",
                    "diagnostics[].stage",
                ],
                "rawEvidenceFields": [
                    "sourceDocument",
                    "nodes[].documentPath",
                    "nodes[].id",
                    "edges[].source",
                    "edges[].target",
                    "nodes[].objectName",
                    "nodes[].label",
                    "nodes[].diagnostic",
                    "edges[].diagnostic",
                    "diagnostics[].severity",
                    "diagnostics[].code",
                    "diagnostics[].message",
                    "diagnostics[].stage",
                ],
            },
        )

    def test_helper_output_uses_json_friendly_lists(self) -> None:
        payload = (
            self.contract.build_reference_traversal_emitted_raw_evidence_contract()
        )

        self.assertIsInstance(payload, dict)
        for value in payload.values():
            self.assertIsInstance(value, list)
            for field in value:
                self.assertIsInstance(field, str)

    def test_helper_output_is_canonical_json_compatible(self) -> None:
        payload = (
            self.contract.build_reference_traversal_emitted_raw_evidence_contract()
        )

        serialized = dumps_canonical(payload)

        self.assertEqual(dumps_canonical(payload), serialized)
        self.assertIn('"pathFields":["sourceDocument","nodes[].documentPath"]', serialized)

    def test_helper_output_mutation_does_not_leak_to_future_calls(self) -> None:
        first = self.contract.build_reference_traversal_emitted_raw_evidence_contract()

        first["pathFields"].append("mutated")
        first["identifierFields"][0] = "mutated"
        first["injected"] = "mutated"

        third = self.contract.build_reference_traversal_emitted_raw_evidence_contract()

        self.assertEqual(
            third["pathFields"], ["sourceDocument", "nodes[].documentPath"]
        )
        self.assertEqual(
            third["identifierFields"],
            ["nodes[].id", "edges[].source", "edges[].target"],
        )
        self.assertNotIn("injected", third)

    def test_helper_output_mutation_does_not_leak_to_module_constants(self) -> None:
        payload = (
            self.contract.build_reference_traversal_emitted_raw_evidence_contract()
        )

        payload["rawEvidenceFields"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_RAW_EVIDENCE_FIELDS,
            (
                "sourceDocument",
                "nodes[].documentPath",
                "nodes[].id",
                "edges[].source",
                "edges[].target",
                "nodes[].objectName",
                "nodes[].label",
                "nodes[].diagnostic",
                "edges[].diagnostic",
                "diagnostics[].severity",
                "diagnostics[].code",
                "diagnostics[].message",
                "diagnostics[].stage",
            ),
        )

    def test_normal_traversal_payload_shape_excludes_emitted_evidence_metadata(
        self,
    ) -> None:
        payload = _build_payload(self.contract)

        self.assertEqual(
            set(payload),
            {
                "schemaVersion",
                "kind",
                "boundary",
                "operation",
                "status",
                "sourceDocument",
                "nodes",
                "edges",
                "diagnostics",
            },
        )
        self.assertEqual(
            set(payload["nodes"][0]),
            {
                "sequence",
                "id",
                "kind",
                "state",
                "documentPath",
                "objectName",
                "label",
                "diagnostic",
            },
        )
        self.assertEqual(
            set(payload["edges"][0]),
            {
                "sequence",
                "source",
                "target",
                "kind",
                "state",
                "diagnostic",
            },
        )
        self.assertEqual(
            set(payload["diagnostics"][0]),
            {
                "sequence",
                "severity",
                "code",
                "message",
                "stage",
            },
        )
        for key in (
            "pathFields",
            "identifierFields",
            "rawEvidenceFields",
            "emittedRawEvidence",
        ):
            self.assertNotIn(key, payload)

    def test_emitted_evidence_constants_do_not_alter_ordering_behavior(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(id="node-c"),
                _node(id="node-a"),
                _node(id="node-b"),
            ],
            edges=[
                _edge(source="node-c", target="node-a"),
                _edge(source="node-a", target="node-b"),
            ],
            diagnostics=[
                _diagnostic(code="third"),
                _diagnostic(code="first"),
                _diagnostic(code="second"),
            ],
        )

        self.assertEqual(
            [(item["sequence"], item["id"]) for item in payload["nodes"]],
            [(0, "node-a"), (1, "node-b"), (2, "node-c")],
        )
        self.assertEqual(
            [
                (item["sequence"], item["source"], item["target"])
                for item in payload["edges"]
            ],
            [(0, "node-a", "node-b"), (1, "node-c", "node-a")],
        )
        self.assertEqual(
            [(item["sequence"], item["code"]) for item in payload["diagnostics"]],
            [(0, "first"), (1, "second"), (2, "third")],
        )

    def test_module_imports_without_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()

        self.assertTrue(
            hasattr(module, "build_reference_traversal_emitted_raw_evidence_contract")
        )
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ReferenceTraversalReferenceDistinctionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_reference_scope_constant_values_are_stable(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL,
            "document_internal",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT,
            "external_document",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE,
            "external_file",
        )

    def test_defined_reference_scopes_are_deterministic_ordered(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES,
            (
                self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL,
                self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT,
                self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE,
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES,
            (
                "document_internal",
                "external_document",
                "external_file",
            ),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES, tuple
        )

    def test_edge_kind_constant_values_are_stable(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
            "document_internal_reference",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
            "external_document_reference",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
            "external_file_reference",
        )

    def test_node_kind_constant_values_are_stable(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT, "document"
        )
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT, "object")
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT,
            "external_document",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE,
            "external_file",
        )

    def test_internal_and_external_edge_kind_groupings_are_deterministic(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_INTERNAL_REFERENCE_EDGE_KINDS,
            (self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EXTERNAL_REFERENCE_EDGE_KINDS,
            (
                self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
                self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
            ),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_INTERNAL_REFERENCE_EDGE_KINDS, tuple
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EXTERNAL_REFERENCE_EDGE_KINDS, tuple
        )

    def test_internal_and_external_edge_kinds_are_disjoint(self) -> None:
        internal = set(
            self.contract.REFERENCE_TRAVERSAL_INTERNAL_REFERENCE_EDGE_KINDS
        )
        external = set(
            self.contract.REFERENCE_TRAVERSAL_EXTERNAL_REFERENCE_EDGE_KINDS
        )

        self.assertEqual(internal & external, set())

    def test_distinction_contract_helper_returns_plain_json_dict(self) -> None:
        payload = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )

        self.assertIsInstance(payload, dict)
        for key in payload:
            self.assertIsInstance(key, str)

    def test_distinction_contract_helper_is_deterministic_and_independent(self) -> None:
        first = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )
        second = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )

        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_distinction_contract_helper_is_canonical_json_compatible(self) -> None:
        payload = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )

        encoded = dumps_canonical(payload)

        self.assertEqual(dumps_canonical(payload), encoded)
        self.assertIn("document_internal", encoded)
        self.assertIn("external_document", encoded)
        self.assertIn("external_file", encoded)

    def test_distinction_contract_helper_includes_all_three_reference_scopes(
        self,
    ) -> None:
        payload = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )

        scopes = payload["referenceScopes"]

        self.assertIsInstance(scopes, dict)
        self.assertEqual(
            set(scopes),
            {
                self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL,
                self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT,
                self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE,
            },
        )
        self.assertEqual(
            payload["definedReferenceScopes"],
            list(self.contract.REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES),
        )

    def test_distinction_contract_helper_identifies_raw_evidence_fields(self) -> None:
        payload = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )

        distinction_fields = payload["distinctionFields"]

        for expected_field in (
            "nodes[].kind",
            "edges[].kind",
            "sourceDocument",
            "nodes[].documentPath",
            "edges[].source",
            "edges[].target",
        ):
            self.assertIn(expected_field, distinction_fields)

    def test_distinction_contract_helper_describes_scope_semantics(self) -> None:
        payload = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )
        scopes = payload["referenceScopes"]

        internal = scopes[
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL
        ]
        external_document = scopes[
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT
        ]
        external_file = scopes[
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE
        ]

        self.assertEqual(
            internal["edgeKind"],
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
        )
        self.assertEqual(
            external_document["edgeKind"],
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
        )
        self.assertEqual(
            external_file["edgeKind"],
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
        )

        internal_semantics = internal["semantics"].lower()
        self.assertIn("inside", internal_semantics)
        self.assertIn("document", internal_semantics)

        external_document_semantics = external_document["semantics"].lower()
        self.assertIn("external", external_document_semantics)
        self.assertIn("freecad", external_document_semantics)
        self.assertIn("document", external_document_semantics)

        external_file_semantics = external_file["semantics"].lower()
        self.assertIn("external", external_file_semantics)
        self.assertIn("non-freecad", external_file_semantics)
        self.assertIn("file", external_file_semantics)

    def test_distinction_contract_helper_exposes_edge_kind_groupings(self) -> None:
        payload = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )

        self.assertEqual(
            payload["internalReferenceEdgeKinds"],
            list(self.contract.REFERENCE_TRAVERSAL_INTERNAL_REFERENCE_EDGE_KINDS),
        )
        self.assertEqual(
            payload["externalReferenceEdgeKinds"],
            list(self.contract.REFERENCE_TRAVERSAL_EXTERNAL_REFERENCE_EDGE_KINDS),
        )
        self.assertEqual(
            payload["definedNodeKinds"],
            [
                self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
                self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT,
                self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE,
            ],
        )
        self.assertEqual(
            payload["definedEdgeKinds"],
            [
                self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
                self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
            ],
        )

    def test_distinction_contract_helper_avoids_normalized_or_decision_vocabulary(
        self,
    ) -> None:
        payload = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )

        encoded = dumps_canonical(payload).lower()

        for forbidden in (
            "pdm",
            "durable",
            "engine-normalized",
            "engine_normalized",
            "verification",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_distinction_contract_helper_mutation_does_not_leak(self) -> None:
        first = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )

        first["distinctionFields"].append("mutated")
        first["referenceScopes"][
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL
        ]["nodeKinds"].append("mutated")
        first["injected"] = "mutated"

        third = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )

        self.assertNotIn("mutated", third["distinctionFields"])
        self.assertNotIn(
            "mutated",
            third["referenceScopes"][
                self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL
            ]["nodeKinds"],
        )
        self.assertNotIn("injected", third)

    def test_distinction_contract_helper_mutation_does_not_leak_to_module_constants(
        self,
    ) -> None:
        payload = (
            self.contract.build_reference_traversal_reference_distinction_contract()
        )

        payload["internalReferenceEdgeKinds"].append("mutated")
        payload["definedReferenceScopes"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_INTERNAL_REFERENCE_EDGE_KINDS,
            ("document_internal_reference",),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES,
            ("document_internal", "external_document", "external_file"),
        )

    def test_payload_shape_unchanged_with_distinction_vocabulary(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(
                    id="assembly",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                ),
                _node(
                    id="body",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                ),
                _node(
                    id="external-doc",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT,
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                    document_path="other.FCStd",
                ),
                _node(
                    id="external-file",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE,
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                    document_path="drawing.dxf",
                ),
            ],
            edges=[
                _edge(
                    source="assembly",
                    target="body",
                    kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                ),
                _edge(
                    source="assembly",
                    target="external-doc",
                    kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                ),
                _edge(
                    source="body",
                    target="external-file",
                    kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                ),
            ],
        )

        self.assertEqual(
            set(payload),
            {
                "schemaVersion",
                "kind",
                "boundary",
                "operation",
                "status",
                "sourceDocument",
                "nodes",
                "edges",
                "diagnostics",
            },
        )
        for injected_field in (
            "referenceScope",
            "referenceScopes",
            "classification",
            "internalExternal",
        ):
            self.assertNotIn(injected_field, payload)

    def test_payload_passes_through_distinction_kind_values_unchanged(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(
                    id="external-doc",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT,
                    document_path="other.FCStd",
                ),
                _node(
                    id="external-file",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE,
                    document_path="drawing.dxf",
                ),
            ],
            edges=[
                _edge(
                    source="external-doc",
                    target="external-file",
                    kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
                ),
            ],
        )

        self.assertEqual(
            sorted(node["kind"] for node in payload["nodes"]),
            ["external_document", "external_file"],
        )
        self.assertEqual(
            [edge["kind"] for edge in payload["edges"]],
            ["external_document_reference"],
        )

    def test_payload_still_accepts_arbitrary_raw_kind_strings(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(id="node-a", kind="caller_provided_raw_kind")],
            edges=[
                _edge(
                    source="node-a",
                    target="node-b",
                    kind="caller_provided_edge_kind",
                ),
            ],
        )

        self.assertEqual(payload["nodes"][0]["kind"], "caller_provided_raw_kind")
        self.assertEqual(payload["edges"][0]["kind"], "caller_provided_edge_kind")

    def test_payload_preserves_deterministic_sequence_and_diagnostic_order(
        self,
    ) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(id="node-c", kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT),
                _node(id="node-a", kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT),
                _node(id="node-b", kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT),
            ],
            edges=[
                _edge(
                    source="node-c",
                    target="node-a",
                    kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                ),
                _edge(
                    source="node-a",
                    target="node-b",
                    kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                ),
            ],
            diagnostics=[
                _diagnostic(code="third"),
                _diagnostic(code="first"),
                _diagnostic(code="second"),
            ],
        )

        self.assertEqual(
            [(item["sequence"], item["id"]) for item in payload["nodes"]],
            [(0, "node-a"), (1, "node-b"), (2, "node-c")],
        )
        self.assertEqual(
            [
                (item["sequence"], item["source"], item["target"])
                for item in payload["edges"]
            ],
            [(0, "node-a", "node-b"), (1, "node-c", "node-a")],
        )
        self.assertEqual(
            [(item["sequence"], item["code"]) for item in payload["diagnostics"]],
            [(0, "first"), (1, "second"), (2, "third")],
        )

    def test_distinction_contract_module_imports_without_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()

        self.assertTrue(
            hasattr(
                module,
                "build_reference_traversal_reference_distinction_contract",
            )
        )
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ReferenceTraversalMalformedRequestContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def _build_failed_payload(self, **overrides):
        kwargs = {
            "boundary": self.contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
            "operation": self.contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
            "source_document": "assembly.FCStd",
            "diagnostic_message": "traversal request payload was malformed",
        }
        kwargs.update(overrides)
        return self.contract.build_malformed_reference_traversal_request_payload(
            **kwargs
        )

    def test_malformed_request_vocabulary_constants_are_stable(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR, "error"
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_MALFORMED_REQUEST,
            "malformed_traversal_request",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION,
            "request_validation",
        )

    def test_unsupported_value_shape_vocabulary_constants_are_stable(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_WARNING,
            "warning",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_UNSUPPORTED_REFERENCE_VALUE_SHAPE,
            "unsupported_reference_value_shape",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_STAGE_REFERENCE_DISCOVERY,
            "reference_discovery",
        )

    def test_failure_contract_helper_returns_plain_dict_with_contract_values(
        self,
    ) -> None:
        contract = (
            self.contract.build_reference_traversal_malformed_request_failure_contract()
        )

        self.assertIsInstance(contract, dict)
        self.assertEqual(
            contract["classification"], "malformed_traversal_request"
        )
        self.assertEqual(contract["status"], "failed")
        self.assertEqual(contract["failurePoint"], "request_validation")
        self.assertEqual(
            contract["diagnostic"],
            {
                "severity": "error",
                "code": "malformed_traversal_request",
                "stage": "request_validation",
            },
        )

    def test_failure_contract_helper_disclaims_out_of_scope_behavior(self) -> None:
        contract = (
            self.contract.build_reference_traversal_malformed_request_failure_contract()
        )

        self.assertFalse(contract["successfulTraversalPayloadEmitted"])
        self.assertFalse(contract["realFreecadTraversalAttempted"])
        self.assertFalse(contract["writerBehaviorDecided"])
        self.assertFalse(contract["outputContainmentDecided"])
        self.assertFalse(contract["engineNormalizationDecided"])
        self.assertFalse(contract["pdmBehaviorDecided"])
        self.assertEqual(
            contract["outOfScope"],
            [
                "real_freecad_traversal",
                "traversal_writer",
                "traversal_output_path_containment",
                "engine_normalization",
                "pdm_persistence_or_query_behavior",
            ],
        )

    def test_failure_contract_helper_is_deterministic_and_independent(self) -> None:
        first = (
            self.contract.build_reference_traversal_malformed_request_failure_contract()
        )
        second = (
            self.contract.build_reference_traversal_malformed_request_failure_contract()
        )

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["diagnostic"], second["diagnostic"])
        self.assertIsNot(first["outOfScope"], second["outOfScope"])

    def test_failure_contract_helper_is_canonical_json_compatible(self) -> None:
        contract = (
            self.contract.build_reference_traversal_malformed_request_failure_contract()
        )

        serialized = dumps_canonical(contract)

        self.assertEqual(dumps_canonical(contract), serialized)
        self.assertIn('"status":"failed"', serialized)
        self.assertIn('"code":"malformed_traversal_request"', serialized)
        self.assertIn('"stage":"request_validation"', serialized)

    def test_failure_contract_helper_mutation_does_not_leak(self) -> None:
        first = (
            self.contract.build_reference_traversal_malformed_request_failure_contract()
        )

        first["outOfScope"].append("mutated")
        first["diagnostic"]["code"] = "mutated"
        first["injected"] = "mutated"

        second = (
            self.contract.build_reference_traversal_malformed_request_failure_contract()
        )

        self.assertNotIn("mutated", second["outOfScope"])
        self.assertEqual(
            second["diagnostic"]["code"], "malformed_traversal_request"
        )
        self.assertNotIn("injected", second)

    def test_failed_payload_returns_exact_failure_shape(self) -> None:
        payload = self._build_failed_payload(
            diagnostic_message="request json missing required fields"
        )

        self.assertEqual(
            payload,
            {
                "schemaVersion": "1.0",
                "kind": "raw_reference_traversal",
                "boundary": "reference_traversal_entrypoint",
                "operation": "reference_traversal",
                "status": "failed",
                "sourceDocument": "assembly.FCStd",
                "nodes": [],
                "edges": [],
                "diagnostics": [
                    {
                        "sequence": 0,
                        "severity": "error",
                        "code": "malformed_traversal_request",
                        "message": "request json missing required fields",
                        "stage": "request_validation",
                    }
                ],
            },
        )

    def test_failed_payload_carries_caller_provided_values(self) -> None:
        payload = self._build_failed_payload(
            boundary=self.contract.REFERENCE_TRAVERSAL_BOUNDARY_ENGINE_INVOCATION,
            source_document="other.FCStd",
            diagnostic_message="caller message",
        )

        self.assertEqual(payload["boundary"], "engine_invocation")
        self.assertEqual(payload["sourceDocument"], "other.FCStd")
        self.assertEqual(payload["nodes"], [])
        self.assertEqual(payload["edges"], [])
        self.assertEqual(len(payload["diagnostics"]), 1)
        self.assertEqual(payload["diagnostics"][0]["message"], "caller message")

    def test_failed_payload_is_canonical_json_compatible(self) -> None:
        payload = self._build_failed_payload()

        serialized = dumps_canonical(payload)

        self.assertEqual(dumps_canonical(payload), serialized)
        self.assertIn('"status":"failed"', serialized)
        self.assertIn('"nodes":[]', serialized)
        self.assertIn('"edges":[]', serialized)
        self.assertIn('"code":"malformed_traversal_request"', serialized)

    def test_failed_payload_repeated_calls_are_stable_and_independent(self) -> None:
        first = self._build_failed_payload()
        second = self._build_failed_payload()

        self.assertEqual(first, second)
        self.assertEqual(dumps_canonical(first), dumps_canonical(second))
        self.assertIsNot(first, second)
        self.assertIsNot(first["diagnostics"], second["diagnostics"])

        first["diagnostics"][0]["message"] = "mutated"
        self.assertEqual(
            second["diagnostics"][0]["message"],
            "traversal request payload was malformed",
        )

    def test_failed_payload_rejects_invalid_source_document(self) -> None:
        for value in ("", 123):
            with self.subTest(value=value):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self._build_failed_payload(source_document=value)

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("sourceDocument", message)

    def test_failed_payload_rejects_invalid_diagnostic_message(self) -> None:
        for value in ("", 123):
            with self.subTest(value=value):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self._build_failed_payload(diagnostic_message=value)

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("diagnosticMessage", message)

    def test_malformed_request_module_imports_without_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()

        self.assertTrue(
            hasattr(
                module,
                "build_malformed_reference_traversal_request_payload",
            )
        )
        self.assertTrue(
            hasattr(
                module,
                "build_reference_traversal_malformed_request_failure_contract",
            )
        )
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ReferenceTraversalOutputContainmentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_containment_constants_have_stable_values(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_ROOT,
            "working_copy",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_POLICY,
            "working_copy_child",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_PATH_PARENT_POLICY,
            "existing_directory",
        )

    def test_containment_contract_helper_returns_plain_json_dict(self) -> None:
        payload = (
            self.contract.build_reference_traversal_output_containment_contract()
        )

        self.assertIsInstance(payload, dict)
        for key in payload:
            self.assertIsInstance(key, str)

    def test_containment_contract_helper_is_deterministic_and_independent(
        self,
    ) -> None:
        first = (
            self.contract.build_reference_traversal_output_containment_contract()
        )
        second = (
            self.contract.build_reference_traversal_output_containment_contract()
        )

        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_containment_contract_helper_is_canonical_json_compatible(self) -> None:
        payload = (
            self.contract.build_reference_traversal_output_containment_contract()
        )

        serialized = dumps_canonical(payload)

        self.assertEqual(dumps_canonical(payload), serialized)

    def test_containment_contract_helper_states_key_boundaries(self) -> None:
        payload = (
            self.contract.build_reference_traversal_output_containment_contract()
        )

        self.assertEqual(
            payload["containmentRoot"],
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_ROOT,
        )
        self.assertEqual(
            payload["containmentPolicy"],
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_POLICY,
        )
        self.assertEqual(
            payload["parentPolicy"],
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_PATH_PARENT_POLICY,
        )
        requirement = payload["workingCopyRequirement"]
        self.assertIn("existing directory", requirement)
        self.assertIn("authoritative", requirement)
        self.assertIn("basename", requirement)
        self.assertIn("not prescribed", requirement)
        self.assertNotIn(WORKING_COPY_DIR_NAME, requirement)
        self.assertEqual(
            payload["relativeOutputPathResolution"], "relative_to_working_copy"
        )
        self.assertEqual(
            payload["absoluteOutputPathPolicy"],
            "accepted_only_inside_working_copy",
        )
        self.assertEqual(
            payload["outputParentRequirement"],
            "parent_must_exist_and_be_directory",
        )
        self.assertEqual(
            payload["outputPathRequirement"],
            "output_path_must_not_be_directory",
        )

    def test_containment_contract_helper_lists_rejected_boundaries(self) -> None:
        payload = (
            self.contract.build_reference_traversal_output_containment_contract()
        )

        rejected = payload["rejectedPaths"]

        for expected in (
            "path_traversal_escape",
            "absolute_outside_working_copy",
            "symlink_escape_outside_working_copy",
            "missing_parent",
            "non_directory_parent",
            "existing_directory_output_path",
        ):
            self.assertIn(expected, rejected)

    def test_containment_contract_helper_lists_allowed_boundaries(self) -> None:
        payload = (
            self.contract.build_reference_traversal_output_containment_contract()
        )

        allowed = payload["allowedPaths"]

        for expected in (
            "relative_child_inside_working_copy",
            "absolute_child_inside_working_copy",
            "existing_non_directory_file_inside_working_copy",
        ):
            self.assertIn(expected, allowed)

    def test_containment_contract_helper_disclaims_out_of_scope_behavior(
        self,
    ) -> None:
        payload = (
            self.contract.build_reference_traversal_output_containment_contract()
        )

        helper_behavior = payload["helperBehavior"]

        self.assertEqual(helper_behavior["returns"], "absolute_resolved_path")
        self.assertFalse(helper_behavior["writesFiles"])
        self.assertFalse(helper_behavior["createsDirectories"])
        self.assertFalse(helper_behavior["performsRealFreecadTraversal"])
        self.assertFalse(helper_behavior["implementsTraversalWriter"])
        self.assertFalse(helper_behavior["implementsRuntimeEntrypointWiring"])

    def test_containment_contract_helper_keeps_raw_evidence_separate(self) -> None:
        payload = (
            self.contract.build_reference_traversal_output_containment_contract()
        )

        raw_evidence_policy = payload["rawEvidencePathPolicy"]

        self.assertEqual(
            raw_evidence_policy["fields"],
            list(self.contract.REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS),
        )
        self.assertFalse(raw_evidence_policy["normalizedByContainmentHelper"])
        self.assertFalse(raw_evidence_policy["usedForContainmentDecisions"])

    def test_containment_contract_helper_mutation_does_not_leak(self) -> None:
        first = (
            self.contract.build_reference_traversal_output_containment_contract()
        )

        first["rejectedPaths"].append("mutated")
        first["helperBehavior"]["writesFiles"] = True
        first["injected"] = "mutated"

        second = (
            self.contract.build_reference_traversal_output_containment_contract()
        )

        self.assertNotIn("mutated", second["rejectedPaths"])
        self.assertFalse(second["helperBehavior"]["writesFiles"])
        self.assertNotIn("injected", second)

    def test_containment_contract_module_imports_without_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()

        self.assertTrue(
            hasattr(module, "build_reference_traversal_output_containment_contract")
        )
        self.assertTrue(
            hasattr(module, "resolve_reference_traversal_output_path")
        )
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ResolveReferenceTraversalOutputPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.root = Path(self._tempdir.name).resolve()
        self.working_copy = self.root / WORKING_COPY_DIR_NAME
        self.working_copy.mkdir()
        self.outside = self.root / "outside"
        self.outside.mkdir()

    def _resolve(self, **overrides):
        kwargs = {"working_copy": self.working_copy, "output_path": "out.json"}
        kwargs.update(overrides)
        return self.contract.resolve_reference_traversal_output_path(**kwargs)

    def _snapshot(self, directory: Path) -> set:
        return {entry.name for entry in directory.iterdir()}

    def test_accepts_relative_output_path_inside_working_copy(self) -> None:
        before = self._snapshot(self.working_copy)

        result = self._resolve(output_path="out.json")

        self.assertEqual(result, self.working_copy / "out.json")
        self.assertTrue(result.is_absolute())
        self.assertEqual(self._snapshot(self.working_copy), before)

    def test_accepts_absolute_output_path_inside_working_copy(self) -> None:
        absolute_output = self.working_copy / "abs_out.json"

        result = self._resolve(output_path=str(absolute_output))

        self.assertEqual(result, absolute_output)
        self.assertFalse(absolute_output.exists())

    def test_accepts_nested_relative_output_path_with_existing_parent(self) -> None:
        (self.working_copy / "sub").mkdir()

        result = self._resolve(output_path="sub/nested.json")

        self.assertEqual(result, self.working_copy / "sub" / "nested.json")
        self.assertFalse(result.exists())

    def test_accepts_existing_non_directory_output_file(self) -> None:
        existing = self.working_copy / "existing.json"
        existing.write_text("raw", encoding="utf-8")

        result = self._resolve(output_path="existing.json")

        self.assertEqual(result, existing)
        self.assertEqual(existing.read_text(encoding="utf-8"), "raw")

    def test_accepts_str_and_path_inputs(self) -> None:
        from_str = self.contract.resolve_reference_traversal_output_path(
            working_copy=str(self.working_copy),
            output_path="out.json",
        )
        from_path = self.contract.resolve_reference_traversal_output_path(
            working_copy=self.working_copy,
            output_path=Path("out.json"),
        )

        self.assertEqual(from_str, from_path)

    def test_returns_absolute_resolved_path_object(self) -> None:
        result = self._resolve(output_path="out.json")

        self.assertIsInstance(result, Path)
        self.assertTrue(result.is_absolute())

    def test_does_not_create_missing_output_file(self) -> None:
        result = self._resolve(output_path="out.json")

        self.assertFalse(result.exists())
        self.assertEqual(self._snapshot(self.working_copy), set())

    def test_does_not_create_missing_parent_directories(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self._resolve(output_path="missing/out.json")

        self.assertFalse((self.working_copy / "missing").exists())

    def _assert_rejects(self, expected_side_effect_dir: Path, **overrides) -> None:
        before = self._snapshot(expected_side_effect_dir)

        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as ctx:
            self._resolve(**overrides)

        message = str(ctx.exception)
        self.assertNotIn("\n", message)
        self.assertNotEqual(message, "")
        self.assertEqual(self._snapshot(expected_side_effect_dir), before)

    def test_rejects_missing_working_copy(self) -> None:
        missing = self.root / "does-not-exist" / WORKING_COPY_DIR_NAME

        self._assert_rejects(self.root, working_copy=missing)

    def test_rejects_working_copy_that_is_not_a_directory(self) -> None:
        alt = self.root / "holder"
        alt.mkdir()
        file_path = alt / WORKING_COPY_DIR_NAME
        file_path.write_text("not a dir", encoding="utf-8")

        self._assert_rejects(alt, working_copy=file_path)

    def test_accepts_working_copy_with_arbitrary_safe_basename(self) -> None:
        arbitrary_root = self.root / "arbitrary-safe-root"
        arbitrary_root.mkdir()

        result = self.contract.resolve_reference_traversal_output_path(
            working_copy=arbitrary_root, output_path="references.json"
        )

        self.assertEqual(result, arbitrary_root / "references.json")
        self.assertFalse(result.exists())

    def test_accepts_child_output_path_beneath_existing_subdirectory_with_arbitrary_basename(
        self,
    ) -> None:
        arbitrary_root = self.root / "arbitrary-safe-root"
        arbitrary_root.mkdir()
        (arbitrary_root / "sub").mkdir()

        result = self.contract.resolve_reference_traversal_output_path(
            working_copy=arbitrary_root, output_path="sub/references.json"
        )

        self.assertEqual(result, arbitrary_root / "sub" / "references.json")
        self.assertFalse(result.exists())

    def test_accepts_directly_supplied_working_directory(self) -> None:
        self.assertEqual(self.working_copy.name, WORKING_COPY_DIR_NAME)

        result = self._resolve(output_path="out.json")

        self.assertEqual(result, self.working_copy / "out.json")
        self.assertFalse(result.exists())

    def test_accepts_nested_execution_root_relative_output_path(self) -> None:
        execution_root = self.working_copy / "execution-a"
        execution_root.mkdir()

        result = self.contract.resolve_reference_traversal_output_path(
            working_copy=execution_root, output_path="references.json"
        )

        self.assertEqual(result, execution_root / "references.json")
        self.assertTrue(result.is_absolute())
        self.assertEqual(result, result.resolve(strict=False))

    def test_accepts_nested_execution_root_absolute_output_path(self) -> None:
        execution_root = self.working_copy / "execution-a"
        execution_root.mkdir()
        absolute_output = execution_root / "references.json"

        result = self.contract.resolve_reference_traversal_output_path(
            working_copy=execution_root, output_path=str(absolute_output)
        )

        self.assertEqual(result, absolute_output)
        self.assertTrue(result.is_absolute())
        self.assertEqual(result, result.resolve(strict=False))

    def test_nested_execution_root_does_not_widen_containment_to_parent_or_sibling(
        self,
    ) -> None:
        execution_root = self.working_copy / "execution-a"
        execution_root.mkdir()
        (self.working_copy / "execution-b").mkdir()
        shared = self.root / "shared"
        shared.mkdir()

        rejected_absolute_paths = (
            self.working_copy / "references.json",
            self.working_copy / "execution-b" / "references.json",
            shared / "references.json",
        )

        for rejected_path in rejected_absolute_paths:
            with self.subTest(rejected_path=rejected_path.name):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.contract.resolve_reference_traversal_output_path(
                        working_copy=execution_root,
                        output_path=str(rejected_path),
                    )

                self.assertEqual(
                    str(ctx.exception),
                    "output_path must resolve inside working_copy",
                )

    def test_rejects_absolute_outside_path_with_prefix_confusion(self) -> None:
        run_a = self.root / "run-a"
        run_a.mkdir()
        run_a2 = self.root / "run-a2"
        run_a2.mkdir()

        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self.contract.resolve_reference_traversal_output_path(
                working_copy=run_a,
                output_path=str(run_a2 / "references.json"),
            )

    def test_root_symlink_resolves_to_canonical_real_directory(self) -> None:
        real_root = self.root / "real-root"
        real_root.mkdir()
        root_link = self.root / "root-link"
        try:
            os.symlink(real_root, root_link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not supported on this platform")

        result = self.contract.resolve_reference_traversal_output_path(
            working_copy=root_link, output_path="references.json"
        )

        self.assertEqual(result, real_root / "references.json")
        self.assertTrue(result.is_absolute())
        self.assertEqual(result, result.resolve(strict=False))

    def test_does_not_mutate_caller_provided_path_arguments(self) -> None:
        working_copy_path = Path(self.working_copy)
        output_path_arg = Path("out.json")

        self.contract.resolve_reference_traversal_output_path(
            working_copy=working_copy_path, output_path=output_path_arg
        )

        self.assertEqual(working_copy_path, self.working_copy)
        self.assertEqual(output_path_arg, Path("out.json"))

    def test_rejects_relative_traversal_escape(self) -> None:
        for escape_path in ("../escape.json", "outputs/../../escape.json"):
            with self.subTest(escape_path=escape_path):
                self._assert_rejects(self.root, output_path=escape_path)

    def test_rejects_absolute_output_path_outside_working_copy(self) -> None:
        self._assert_rejects(
            self.outside, output_path=str(self.outside / "escape.json")
        )

    def test_rejects_symlink_parent_escape(self) -> None:
        link = self.working_copy / "link"
        try:
            os.symlink(self.outside, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not supported on this platform")

        self._assert_rejects(self.outside, output_path="link/escape.json")

    def test_rejects_existing_symlink_output_that_resolves_outside(self) -> None:
        target = self.outside / "real.json"
        target.write_text("outside", encoding="utf-8")
        link = self.working_copy / "out.json"
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not supported on this platform")

        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self._resolve(output_path="out.json")

        self.assertEqual(target.read_text(encoding="utf-8"), "outside")
        self.assertTrue(link.is_symlink())

    def test_rejects_missing_output_parent(self) -> None:
        self._assert_rejects(self.working_copy, output_path="missing/out.json")

    def test_rejects_non_directory_output_parent(self) -> None:
        file_parent = self.working_copy / "afile"
        file_parent.write_text("raw", encoding="utf-8")

        self._assert_rejects(
            self.working_copy, output_path="afile/out.json"
        )

    def test_rejects_directory_output_target(self) -> None:
        (self.working_copy / "adir").mkdir()

        self._assert_rejects(self.working_copy, output_path="adir")

    def test_rejection_messages_are_single_line_and_deterministic(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as first:
            self._resolve(output_path="../escape.json")
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as second:
            self._resolve(output_path="../escape.json")

        self.assertEqual(str(first.exception), str(second.exception))
        self.assertNotIn("\n", str(first.exception))


class ReferenceTraversalRawEvidenceSeparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_raw_evidence_paths_are_preserved_and_not_containment_checked(
        self,
    ) -> None:
        payload = _build_payload(
            self.contract,
            source_document="../raw-evidence-only.FCStd",
            nodes=[
                _node(
                    id="external-doc",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT,
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                    document_path="../external/raw-evidence.FCStd",
                ),
            ],
            edges=[
                _edge(
                    source="external-doc",
                    target="external-file",
                    kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
                ),
            ],
        )

        self.assertEqual(payload["sourceDocument"], "../raw-evidence-only.FCStd")
        self.assertEqual(
            payload["nodes"][0]["documentPath"],
            "../external/raw-evidence.FCStd",
        )

    def test_raw_evidence_paths_are_rejected_as_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            working_copy = root / WORKING_COPY_DIR_NAME
            working_copy.mkdir()

            for raw_evidence in (
                "../raw-evidence-only.FCStd",
                "../external/raw-evidence.FCStd",
            ):
                with self.subTest(raw_evidence=raw_evidence):
                    with self.assertRaises(
                        self.contract.ReferenceTraversalOutputContractError
                    ):
                        self.contract.resolve_reference_traversal_output_path(
                            working_copy=working_copy,
                            output_path=raw_evidence,
                        )


class _StringLikeDocumentPath:
    """A non-string object whose __str__ must never be silently used."""

    def __str__(self) -> str:  # pragma: no cover - only invoked on defect
        return "coerced-via-str.FCStd"


def _assert_only_json_leaf_types(testcase: unittest.TestCase, value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            testcase.assertIsInstance(key, str)
            _assert_only_json_leaf_types(testcase, item)
        return
    if isinstance(value, list):
        for item in value:
            _assert_only_json_leaf_types(testcase, item)
        return
    testcase.assertIsInstance(value, (str, bool, int, float, type(None)))
    testcase.assertNotIsInstance(value, (tuple, set, frozenset, bytes))


class ReferenceTraversalSemanticNodeIdentityConstantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_identity_field_order_is_exact_and_deterministic(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS,
            ("kind", "documentPath", "objectName"),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS, tuple
        )
        self.assertNotIsInstance(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS,
            (list, set, dict),
        )

    def test_identity_field_order_cannot_be_mutated(self) -> None:
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS[0] = "x"

    def test_identity_fields_by_kind_definitions_are_exact(self) -> None:
        fields_by_kind = (
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND
        )

        self.assertEqual(dict(fields_by_kind), {
            "document": ("kind", "documentPath"),
            "object": ("kind", "documentPath", "objectName"),
            "external_document": ("kind", "documentPath"),
            "external_file": ("kind", "documentPath"),
        })
        self.assertEqual(list(fields_by_kind), [
            "document",
            "object",
            "external_document",
            "external_file",
        ])

    def test_identity_fields_by_kind_values_are_tuples(self) -> None:
        fields_by_kind = (
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND
        )

        for kind, fields in fields_by_kind.items():
            with self.subTest(kind=kind):
                self.assertIsInstance(fields, tuple)
                self.assertNotIsInstance(fields, list)

    def test_identity_fields_by_kind_mapping_cannot_be_mutated(self) -> None:
        fields_by_kind = (
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND
        )
        self.assertIsInstance(fields_by_kind, types.MappingProxyType)

        with self.assertRaises(TypeError):
            fields_by_kind["document"] = ("kind",)
        with self.assertRaises(TypeError):
            del fields_by_kind["object"]

    def test_identity_fields_by_kind_tuple_entries_cannot_be_mutated(self) -> None:
        fields_by_kind = (
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND
        )

        with self.assertRaises(TypeError):
            fields_by_kind["document"][0] = "mutated"

    def test_excluded_fields_are_exact(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS,
            ("id", "state", "label", "diagnostic", "sequence"),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS,
            tuple,
        )

    def test_excluded_fields_cannot_be_mutated(self) -> None:
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS[
                0
            ] = "mutated"

    def test_excluded_fields_match_raw_node_field_constants(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS,
            (
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_ID,
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_STATE,
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_LABEL,
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_DIAGNOSTIC,
                self.contract.REFERENCE_TRAVERSAL_NODE_FIELD_SEQUENCE,
            ),
        )

    def test_excluded_fields_are_disjoint_from_identity_fields(self) -> None:
        excluded = set(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS
        )
        identity = set(self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS)

        self.assertEqual(excluded & identity, set())

    def test_semantic_identity_names_are_not_part_of_key_builder_signature(self) -> None:
        # The excluded fields (id/state/label/diagnostic/sequence) are boundary
        # metadata, not accepted keyword arguments of the key builder.
        for excluded_field in (
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS
        ):
            with self.subTest(excluded_field=excluded_field):
                with self.assertRaises(TypeError):
                    self.contract.build_reference_traversal_semantic_node_identity_key(
                        kind="document",
                        document_path="assembly.FCStd",
                        **{excluded_field: "value"},
                    )


class ReferenceTraversalSemanticNodeIdentityKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_key = (
            self.contract.build_reference_traversal_semantic_node_identity_key
        )

    def test_document_key_shape(self) -> None:
        key = self.build_key(kind="document", document_path="assembly.FCStd")

        self.assertEqual(key, ("document", "assembly.FCStd"))
        self.assertIsInstance(key, tuple)

    def test_object_key_shape(self) -> None:
        key = self.build_key(
            kind="object", document_path="assembly.FCStd", object_name="Body"
        )

        self.assertEqual(key, ("object", "assembly.FCStd", "Body"))
        self.assertIsInstance(key, tuple)

    def test_external_document_key_shape(self) -> None:
        key = self.build_key(
            kind="external_document", document_path="parts/bolt.FCStd"
        )

        self.assertEqual(key, ("external_document", "parts/bolt.FCStd"))
        self.assertIsInstance(key, tuple)

    def test_external_file_key_shape(self) -> None:
        key = self.build_key(
            kind="external_file", document_path="resources/material.csv"
        )

        self.assertEqual(key, ("external_file", "resources/material.csv"))
        self.assertIsInstance(key, tuple)

    def test_keys_match_node_kind_constants(self) -> None:
        self.assertEqual(
            self.build_key(
                kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                document_path="assembly.FCStd",
            ),
            ("document", "assembly.FCStd"),
        )
        self.assertEqual(
            self.build_key(
                kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
                document_path="assembly.FCStd",
                object_name="Body",
            ),
            ("object", "assembly.FCStd", "Body"),
        )
        self.assertEqual(
            self.build_key(
                kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT,
                document_path="parts/bolt.FCStd",
            ),
            ("external_document", "parts/bolt.FCStd"),
        )
        self.assertEqual(
            self.build_key(
                kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE,
                document_path="resources/material.csv",
            ),
            ("external_file", "resources/material.csv"),
        )

    def test_repeated_equivalent_calls_produce_equal_tuples(self) -> None:
        first = self.build_key(
            kind="object", document_path="assembly.FCStd", object_name="Body"
        )
        second = self.build_key(
            kind="object", document_path="assembly.FCStd", object_name="Body"
        )

        self.assertEqual(first, second)

    def test_key_is_stable_across_unrelated_environment_state(self) -> None:
        first = self.build_key(kind="document", document_path="assembly.FCStd")

        os.environ["PARAMETRON_FREECAD_UNRELATED_TEST_VAR"] = "unrelated-value"
        try:
            second = self.build_key(kind="document", document_path="assembly.FCStd")
        finally:
            del os.environ["PARAMETRON_FREECAD_UNRELATED_TEST_VAR"]

        self.assertEqual(first, second)

    def test_key_does_not_depend_on_filesystem_existence(self) -> None:
        key = self.build_key(
            kind="document",
            document_path="does/not/exist/anywhere/on/disk.FCStd",
        )

        self.assertEqual(
            key, ("document", "does/not/exist/anywhere/on/disk.FCStd")
        )


class ReferenceTraversalSemanticNodeIdentityDistinctionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_key = (
            self.contract.build_reference_traversal_semantic_node_identity_key
        )

    def test_same_path_different_kinds_are_distinct(self) -> None:
        document_key = self.build_key(kind="document", document_path="a.FCStd")
        external_document_key = self.build_key(
            kind="external_document", document_path="a.FCStd"
        )
        external_file_key = self.build_key(
            kind="external_file", document_path="a.FCStd"
        )

        self.assertNotEqual(document_key, external_document_key)
        self.assertNotEqual(document_key, external_file_key)
        self.assertNotEqual(external_document_key, external_file_key)

    def test_external_document_and_external_file_are_distinct_for_same_path(
        self,
    ) -> None:
        external_document_key = self.build_key(
            kind="external_document", document_path="shared/path.ext"
        )
        external_file_key = self.build_key(
            kind="external_file", document_path="shared/path.ext"
        )

        self.assertNotEqual(external_document_key, external_file_key)

    def test_different_document_paths_are_distinct(self) -> None:
        first = self.build_key(kind="document", document_path="a.FCStd")
        second = self.build_key(kind="document", document_path="b.FCStd")

        self.assertNotEqual(first, second)

    def test_two_object_names_in_same_document_are_distinct(self) -> None:
        first = self.build_key(
            kind="object", document_path="assembly.FCStd", object_name="Body"
        )
        second = self.build_key(
            kind="object", document_path="assembly.FCStd", object_name="Bracket"
        )

        self.assertNotEqual(first, second)

    def test_same_object_name_in_different_documents_are_distinct(self) -> None:
        first = self.build_key(
            kind="object", document_path="a.FCStd", object_name="Body"
        )
        second = self.build_key(
            kind="object", document_path="b.FCStd", object_name="Body"
        )

        self.assertNotEqual(first, second)


class ReferenceTraversalSemanticNodeIdentityNoNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_key = (
            self.contract.build_reference_traversal_semantic_node_identity_key
        )

    def test_path_separators_are_not_converted(self) -> None:
        key = self.build_key(
            kind="document", document_path="sub\\dir\\assembly.FCStd"
        )

        self.assertEqual(key[1], "sub\\dir\\assembly.FCStd")

    def test_dotted_relative_paths_are_not_resolved(self) -> None:
        key = self.build_key(kind="document", document_path="./a.FCStd")

        self.assertEqual(key[1], "./a.FCStd")

    def test_parent_traversal_segments_are_not_resolved(self) -> None:
        key = self.build_key(kind="document", document_path="../a.FCStd")

        self.assertEqual(key[1], "../a.FCStd")

    def test_case_is_preserved_and_distinguishes_keys(self) -> None:
        lower = self.build_key(kind="document", document_path="assembly.fcstd")
        upper = self.build_key(kind="document", document_path="Assembly.FCStd")

        self.assertEqual(lower[1], "assembly.fcstd")
        self.assertEqual(upper[1], "Assembly.FCStd")
        self.assertNotEqual(lower, upper)

    def test_absolute_looking_paths_are_not_rewritten_to_relative(self) -> None:
        key = self.build_key(kind="document", document_path="/abs/assembly.FCStd")

        self.assertEqual(key[1], "/abs/assembly.FCStd")

    def test_surrounding_whitespace_is_not_trimmed(self) -> None:
        key = self.build_key(kind="document", document_path=" assembly.FCStd ")

        self.assertEqual(key[1], " assembly.FCStd ")

    def test_object_name_is_preserved_unchanged(self) -> None:
        key = self.build_key(
            kind="object",
            document_path="assembly.FCStd",
            object_name=" Body ",
        )

        self.assertEqual(key[2], " Body ")

    def test_path_objects_are_rejected_not_stringified(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self.build_key(kind="document", document_path=Path("assembly.FCStd"))

    def test_non_string_object_is_rejected_not_coerced_via_str(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self.build_key(
                kind="document", document_path=_StringLikeDocumentPath()
            )


class ReferenceTraversalSemanticNodeIdentityObjectNameValidationTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_key = (
            self.contract.build_reference_traversal_semantic_node_identity_key
        )

    def test_object_kind_requires_object_name(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as ctx:
            self.build_key(kind="object", document_path="assembly.FCStd")

        message = str(ctx.exception)
        self.assertIn("objectName", message)

    def test_object_kind_rejects_empty_object_name(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self.build_key(
                kind="object", document_path="assembly.FCStd", object_name=""
            )

    def test_object_kind_rejects_invalid_object_name_types(self) -> None:
        invalid_object_names = (123, 1.5, True, False, Path("Body"), [], {}, object())

        for object_name in invalid_object_names:
            with self.subTest(object_name=object_name):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ):
                    self.build_key(
                        kind="object",
                        document_path="assembly.FCStd",
                        object_name=object_name,
                    )

    def test_document_kind_rejects_supplied_object_name(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as ctx:
            self.build_key(
                kind="document", document_path="assembly.FCStd", object_name="Body"
            )

        self.assertIn("document", str(ctx.exception))

    def test_external_document_kind_rejects_supplied_object_name(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self.build_key(
                kind="external_document",
                document_path="parts/bolt.FCStd",
                object_name="Body",
            )

    def test_external_file_kind_rejects_supplied_object_name(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self.build_key(
                kind="external_file",
                document_path="resources/material.csv",
                object_name="Body",
            )

    def test_non_object_kinds_accept_omitted_object_name(self) -> None:
        for kind, document_path in (
            ("document", "assembly.FCStd"),
            ("external_document", "parts/bolt.FCStd"),
            ("external_file", "resources/material.csv"),
        ):
            with self.subTest(kind=kind):
                key = self.build_key(kind=kind, document_path=document_path)
                self.assertEqual(key, (kind, document_path))

    def test_non_object_kinds_accept_explicit_none_object_name(self) -> None:
        key = self.build_key(
            kind="document", document_path="assembly.FCStd", object_name=None
        )

        self.assertEqual(key, ("document", "assembly.FCStd"))


class ReferenceTraversalSemanticNodeIdentityKindValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_key = (
            self.contract.build_reference_traversal_semantic_node_identity_key
        )

    def test_all_four_supported_kinds_are_accepted(self) -> None:
        for kind in ("document", "object", "external_document", "external_file"):
            with self.subTest(kind=kind):
                kwargs = {"kind": kind, "document_path": "assembly.FCStd"}
                if kind == "object":
                    kwargs["object_name"] = "Body"
                key = self.build_key(**kwargs)
                self.assertEqual(key[0], kind)

    def test_unknown_kind_is_rejected(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as ctx:
            self.build_key(kind="component", document_path="assembly.FCStd")

        message = str(ctx.exception)
        self.assertIn("kind", message)
        for allowed in ("document", "object", "external_document", "external_file"):
            self.assertIn(allowed, message)

    def test_empty_kind_is_rejected(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self.build_key(kind="", document_path="assembly.FCStd")

    def test_invalid_kind_types_are_rejected(self) -> None:
        invalid_kinds = (123, 1.5, None, [], {}, object())

        for kind in invalid_kinds:
            with self.subTest(kind=kind):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ):
                    self.build_key(kind=kind, document_path="assembly.FCStd")

    def test_boolean_kind_values_are_rejected(self) -> None:
        for kind in (True, False):
            with self.subTest(kind=kind):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ):
                    self.build_key(kind=kind, document_path="assembly.FCStd")

    def test_numeric_kind_values_are_rejected(self) -> None:
        for kind in (0, 1, 3.14):
            with self.subTest(kind=kind):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ):
                    self.build_key(kind=kind, document_path="assembly.FCStd")

    def test_kind_errors_are_reference_traversal_output_contract_error(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as ctx:
            self.build_key(kind="unknown_kind", document_path="assembly.FCStd")

        self.assertIsInstance(ctx.exception, ValueError)


class ReferenceTraversalSemanticNodeIdentityPathValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_key = (
            self.contract.build_reference_traversal_semantic_node_identity_key
        )

    def test_missing_path_is_rejected_for_every_applicable_kind(self) -> None:
        for kind in ("document", "object", "external_document", "external_file"):
            with self.subTest(kind=kind):
                kwargs = {"kind": kind, "document_path": None}
                if kind == "object":
                    kwargs["object_name"] = "Body"
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.build_key(**kwargs)
                self.assertIn("documentPath", str(ctx.exception))

    def test_empty_path_is_rejected_for_every_applicable_kind(self) -> None:
        for kind in ("document", "object", "external_document", "external_file"):
            with self.subTest(kind=kind):
                kwargs = {"kind": kind, "document_path": ""}
                if kind == "object":
                    kwargs["object_name"] = "Body"
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ):
                    self.build_key(**kwargs)

    def test_invalid_non_string_path_types_are_rejected(self) -> None:
        invalid_paths = (123, 1.5, object(), b"assembly.FCStd", [], {})

        for kind in ("document", "object", "external_document", "external_file"):
            for document_path in invalid_paths:
                with self.subTest(kind=kind, document_path=document_path):
                    kwargs = {"kind": kind, "document_path": document_path}
                    if kind == "object":
                        kwargs["object_name"] = "Body"
                    with self.assertRaises(
                        self.contract.ReferenceTraversalOutputContractError
                    ):
                        self.build_key(**kwargs)

    def test_pathlib_path_is_rejected(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self.build_key(kind="document", document_path=Path("assembly.FCStd"))

    def test_boolean_path_is_rejected(self) -> None:
        for document_path in (True, False):
            with self.subTest(document_path=document_path):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ):
                    self.build_key(kind="document", document_path=document_path)

    def test_integer_path_is_rejected(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self.build_key(kind="document", document_path=7)

    def test_arbitrary_object_path_is_rejected(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self.build_key(kind="document", document_path=object())


class ReferenceTraversalSemanticNodeIdentityErrorDeterminismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_key = (
            self.contract.build_reference_traversal_semantic_node_identity_key
        )

    def test_error_type_is_reference_traversal_output_contract_error(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as ctx:
            self.build_key(kind="unknown", document_path="assembly.FCStd")

        self.assertIsInstance(
            ctx.exception, self.contract.ReferenceTraversalOutputContractError
        )

    def test_error_message_is_deterministic_across_repeated_calls(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as first:
            self.build_key(kind="unknown", document_path="assembly.FCStd")
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as second:
            self.build_key(kind="unknown", document_path="assembly.FCStd")

        self.assertEqual(str(first.exception), str(second.exception))

    def test_error_message_is_non_empty_and_single_line(self) -> None:
        cases = (
            {"kind": "unknown", "document_path": "assembly.FCStd"},
            {"kind": "document", "document_path": ""},
            {"kind": "object", "document_path": "assembly.FCStd"},
            {
                "kind": "document",
                "document_path": "assembly.FCStd",
                "object_name": "Body",
            },
        )

        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.build_key(**kwargs)

                message = str(ctx.exception)
                self.assertTrue(message)
                self.assertNotIn("\n", message)

    def test_error_message_contains_no_object_address_or_traceback(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as ctx:
            self.build_key(kind="unknown", document_path="assembly.FCStd")

        message = str(ctx.exception)
        self.assertNotIn("0x", message)
        self.assertNotIn("Traceback", message)
        self.assertNotIn("File \"", message)


class ReferenceTraversalSemanticNodeIdentityContractMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_semantic_node_identity_contract
        )

    def test_metadata_contains_documented_keys(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata),
            {
                "supportedNodeKinds",
                "identityFieldsByNodeKind",
                "identityFieldOrder",
                "excludedFields",
                "pathInputPolicy",
                "normalizationPerformed",
                "filesystemInspected",
                "generatedIdentifierFormula",
                "engineNormalizationPerformed",
                "pdmIdentityProduced",
            },
        )

    def test_metadata_required_false_values(self) -> None:
        metadata = self.build_contract()

        self.assertIs(metadata["normalizationPerformed"], False)
        self.assertIs(metadata["filesystemInspected"], False)
        self.assertIs(metadata["generatedIdentifierFormula"], False)
        self.assertIs(metadata["engineNormalizationPerformed"], False)
        self.assertIs(metadata["pdmIdentityProduced"], False)

    def test_metadata_supported_node_kinds_are_exact(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["supportedNodeKinds"],
            ["document", "object", "external_document", "external_file"],
        )
        self.assertIsInstance(metadata["supportedNodeKinds"], list)

    def test_metadata_identity_fields_by_node_kind_are_exact(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["identityFieldsByNodeKind"],
            {
                "document": ["kind", "documentPath"],
                "object": ["kind", "documentPath", "objectName"],
                "external_document": ["kind", "documentPath"],
                "external_file": ["kind", "documentPath"],
            },
        )

    def test_metadata_identity_field_order_is_exact(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["identityFieldOrder"], ["kind", "documentPath", "objectName"]
        )

    def test_metadata_excluded_fields_are_exact(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["excludedFields"],
            ["id", "state", "label", "diagnostic", "sequence"],
        )

    def test_metadata_path_input_policy_states_canonical_and_relative_expectations(
        self,
    ) -> None:
        metadata = self.build_contract()
        policy = metadata["pathInputPolicy"].lower()

        self.assertIn("canonical", policy)
        self.assertIn("contract-relative", policy)
        self.assertIn("does not", policy)

    def test_metadata_lists_and_dict_use_plain_json_friendly_containers(self) -> None:
        metadata = self.build_contract()

        self.assertIsInstance(metadata["supportedNodeKinds"], list)
        self.assertIsInstance(metadata["identityFieldsByNodeKind"], dict)
        self.assertIsInstance(metadata["identityFieldOrder"], list)
        self.assertIsInstance(metadata["excludedFields"], list)
        for fields in metadata["identityFieldsByNodeKind"].values():
            self.assertIsInstance(fields, list)


class ReferenceTraversalSemanticNodeIdentityMetadataFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_semantic_node_identity_contract
        )

    def test_repeated_calls_return_equal_independent_top_level_objects(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_repeated_calls_return_independent_nested_collections(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertIsNot(
            first["supportedNodeKinds"], second["supportedNodeKinds"]
        )
        self.assertIsNot(
            first["identityFieldsByNodeKind"], second["identityFieldsByNodeKind"]
        )
        self.assertIsNot(
            first["identityFieldsByNodeKind"]["object"],
            second["identityFieldsByNodeKind"]["object"],
        )
        self.assertIsNot(first["excludedFields"], second["excludedFields"])
        self.assertIsNot(first["identityFieldOrder"], second["identityFieldOrder"])

    def test_mutating_returned_metadata_does_not_leak_to_later_calls(self) -> None:
        first = self.build_contract()

        first["supportedNodeKinds"].append("mutated")
        first["identityFieldsByNodeKind"]["object"].append("mutated")
        first["identityFieldsByNodeKind"]["mutated_kind"] = ["mutated"]
        first["excludedFields"].append("mutated")
        first["identityFieldOrder"].append("mutated")
        first["injected"] = "mutated"

        second = self.build_contract()

        self.assertEqual(
            second["supportedNodeKinds"],
            ["document", "object", "external_document", "external_file"],
        )
        self.assertEqual(
            second["identityFieldsByNodeKind"]["object"],
            ["kind", "documentPath", "objectName"],
        )
        self.assertNotIn("mutated_kind", second["identityFieldsByNodeKind"])
        self.assertEqual(
            second["excludedFields"],
            ["id", "state", "label", "diagnostic", "sequence"],
        )
        self.assertEqual(
            second["identityFieldOrder"], ["kind", "documentPath", "objectName"]
        )
        self.assertNotIn("injected", second)

    def test_mutating_returned_metadata_does_not_alter_module_constants(self) -> None:
        metadata = self.build_contract()

        metadata["excludedFields"].append("mutated")
        metadata["identityFieldOrder"].append("mutated")
        metadata["supportedNodeKinds"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS,
            ("id", "state", "label", "diagnostic", "sequence"),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS,
            ("kind", "documentPath", "objectName"),
        )
        self.assertEqual(
            list(
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND
            ),
            ["document", "object", "external_document", "external_file"],
        )


class ReferenceTraversalSemanticNodeIdentityCanonicalJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_semantic_node_identity_contract
        )

    def test_metadata_contains_only_json_compatible_values(self) -> None:
        metadata = self.build_contract()

        _assert_only_json_leaf_types(self, metadata)

    def test_metadata_serializes_deterministically(self) -> None:
        metadata = self.build_contract()

        serialized_first = dumps_canonical(metadata)
        serialized_second = dumps_canonical(metadata)

        self.assertEqual(serialized_first, serialized_second)

    def test_repeated_calls_produce_equivalent_canonical_bytes(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(dumps_canonical(first), dumps_canonical(second))

    def test_metadata_serialization_contains_expected_fragments(self) -> None:
        metadata = self.build_contract()
        serialized = dumps_canonical(metadata)

        self.assertIn('"normalizationPerformed":false', serialized)
        self.assertIn('"filesystemInspected":false', serialized)
        self.assertIn('"generatedIdentifierFormula":false', serialized)
        self.assertIn('"engineNormalizationPerformed":false', serialized)
        self.assertIn('"pdmIdentityProduced":false', serialized)


class ReferenceTraversalSemanticNodeIdentityRawPayloadCompatibilityTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_raw_node_dataclass_fields_are_unchanged(self) -> None:
        expected_fields = {
            "id",
            "kind",
            "state",
            "document_path",
            "object_name",
            "label",
            "diagnostic",
        }
        actual_fields = {
            field.name
            for field in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }

        self.assertEqual(actual_fields, expected_fields)

    def test_raw_payload_builder_still_accepts_arbitrary_non_empty_raw_kind(
        self,
    ) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(id="node-a", kind="a_totally_unsemantic_raw_kind")],
        )

        self.assertEqual(payload["nodes"][0]["kind"], "a_totally_unsemantic_raw_kind")

    def test_semantic_kind_named_nodes_still_pass_through_raw_payload_unchanged(
        self,
    ) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(
                    id="assembly",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                    document_path="assembly.FCStd",
                    object_name=None,
                ),
                _node(
                    id="body",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
                    document_path="assembly.FCStd",
                    object_name="Body",
                ),
            ],
        )

        kinds = sorted(node["kind"] for node in payload["nodes"])
        self.assertEqual(kinds, ["document", "object"])

    def test_semantic_key_builder_is_not_invoked_by_payload_builder(self) -> None:
        # An invalid semantic identity combination (object kind without an
        # object name) must not surface as a failure from the raw payload
        # builder, proving the two validation paths are independent.
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(
                    id="loose-object",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
                    document_path=None,
                    object_name=None,
                )
            ],
        )

        self.assertEqual(payload["nodes"][0]["kind"], "object")
        self.assertIsNone(payload["nodes"][0]["documentPath"])
        self.assertIsNone(payload["nodes"][0]["objectName"])


class ReferenceTraversalSemanticNodeIdentityImportSafetyTests(unittest.TestCase):
    def test_module_imports_without_freecad_and_exposes_semantic_identity_api(
        self,
    ) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)

        def _cleanup() -> None:
            if previous is not None:
                sys.modules[MODULE_NAME] = previous
            else:
                sys.modules.pop(MODULE_NAME, None)

        self.addCleanup(_cleanup)

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()

        for name in (
            "REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS",
            "REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND",
            "REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS",
            "build_reference_traversal_semantic_node_identity_contract",
            "build_reference_traversal_semantic_node_identity_key",
            "REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS",
            "REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_EXCLUDED_FIELDS",
            "REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS",
            "build_reference_traversal_semantic_edge_identity_contract",
            "build_reference_traversal_semantic_edge_identity_key",
            "deduplicate_reference_traversal_semantic_edge_identity_keys",
        ):
            self.assertTrue(hasattr(module, name))

        key = module.build_reference_traversal_semantic_node_identity_key(
            kind="document", document_path="assembly.FCStd"
        )
        self.assertEqual(key, ("document", "assembly.FCStd"))

        source_key = module.build_reference_traversal_semantic_node_identity_key(
            kind="document", document_path="assembly.FCStd"
        )
        target_key = module.build_reference_traversal_semantic_node_identity_key(
            kind="external_document", document_path="parts/bolt.FCStd"
        )
        edge_key = module.build_reference_traversal_semantic_edge_identity_key(
            source_node_key=source_key,
            target_node_key=target_key,
            kind="external_document_reference",
        )
        self.assertEqual(
            edge_key,
            (
                ("document", "assembly.FCStd"),
                ("external_document", "parts/bolt.FCStd"),
                "external_document_reference",
            ),
        )
        self.assertEqual(
            module.deduplicate_reference_traversal_semantic_edge_identity_keys(
                [edge_key, edge_key]
            ),
            (edge_key,),
        )

        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ReferenceTraversalSemanticEdgeIdentityConstantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_identity_fields_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS,
            (
                "sourceSemanticNodeIdentityKey",
                "targetSemanticNodeIdentityKey",
                "kind",
            ),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS, tuple
        )

    def test_identity_fields_cannot_be_mutated(self) -> None:
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS[0] = "x"

    def test_excluded_fields_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_EXCLUDED_FIELDS,
            ("source", "target", "state", "diagnostic", "sequence"),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_EXCLUDED_FIELDS,
            tuple,
        )

    def test_excluded_fields_match_raw_edge_field_constants(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_EXCLUDED_FIELDS,
            (
                self.contract.REFERENCE_TRAVERSAL_EDGE_FIELD_SOURCE,
                self.contract.REFERENCE_TRAVERSAL_EDGE_FIELD_TARGET,
                self.contract.REFERENCE_TRAVERSAL_EDGE_FIELD_STATE,
                self.contract.REFERENCE_TRAVERSAL_EDGE_FIELD_DIAGNOSTIC,
                self.contract.REFERENCE_TRAVERSAL_EDGE_FIELD_SEQUENCE,
            ),
        )

    def test_excluded_fields_cannot_be_mutated(self) -> None:
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_EXCLUDED_FIELDS[
                0
            ] = "mutated"

    def test_excluded_fields_are_disjoint_from_identity_fields(self) -> None:
        excluded = set(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_EXCLUDED_FIELDS
        )
        identity = set(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS
        )

        self.assertEqual(excluded & identity, set())

    def test_supported_kinds_are_exact_and_ordered(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS,
            (
                "document_internal_reference",
                "external_document_reference",
                "external_file_reference",
            ),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS,
            tuple,
        )

    def test_supported_kinds_match_edge_kind_constants(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS,
            (
                self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
                self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
            ),
        )

    def test_supported_kinds_cannot_be_mutated(self) -> None:
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS[
                0
            ] = "mutated"

    def test_no_private_validation_helper_is_exported(self) -> None:
        self.assertNotIn(
            "_require_semantic_node_identity_key", self.contract.__all__
        )
        self.assertNotIn(
            "_require_semantic_edge_identity_key", self.contract.__all__
        )


class ReferenceTraversalSemanticEdgeIdentityKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_node_key = (
            self.contract.build_reference_traversal_semantic_node_identity_key
        )
        self.build_edge_key = (
            self.contract.build_reference_traversal_semantic_edge_identity_key
        )

    def test_object_to_object_document_internal_reference(self) -> None:
        source = self.build_node_key(
            kind="object", document_path="assembly.FCStd", object_name="SourceObject"
        )
        target = self.build_node_key(
            kind="object", document_path="assembly.FCStd", object_name="TargetObject"
        )

        key = self.build_edge_key(
            source_node_key=source,
            target_node_key=target,
            kind="document_internal_reference",
        )

        self.assertEqual(
            key,
            (
                ("object", "assembly.FCStd", "SourceObject"),
                ("object", "assembly.FCStd", "TargetObject"),
                "document_internal_reference",
            ),
        )
        self.assertIsInstance(key, tuple)
        self.assertIsInstance(key[0], tuple)
        self.assertIsInstance(key[1], tuple)

    def test_object_to_external_document_reference(self) -> None:
        source = self.build_node_key(
            kind="object", document_path="assembly.FCStd", object_name="SourceObject"
        )
        target = self.build_node_key(
            kind="external_document", document_path="parts/part.FCStd"
        )

        key = self.build_edge_key(
            source_node_key=source,
            target_node_key=target,
            kind="external_document_reference",
        )

        self.assertEqual(
            key,
            (
                ("object", "assembly.FCStd", "SourceObject"),
                ("external_document", "parts/part.FCStd"),
                "external_document_reference",
            ),
        )

    def test_object_to_external_file_reference(self) -> None:
        source = self.build_node_key(
            kind="object", document_path="assembly.FCStd", object_name="SourceObject"
        )
        target = self.build_node_key(
            kind="external_file", document_path="resources/material.csv"
        )

        key = self.build_edge_key(
            source_node_key=source,
            target_node_key=target,
            kind="external_file_reference",
        )

        self.assertEqual(
            key,
            (
                ("object", "assembly.FCStd", "SourceObject"),
                ("external_file", "resources/material.csv"),
                "external_file_reference",
            ),
        )

    def test_document_to_external_file_reference(self) -> None:
        source = self.build_node_key(kind="document", document_path="assembly.FCStd")
        target = self.build_node_key(
            kind="external_file", document_path="resources/material.csv"
        )

        key = self.build_edge_key(
            source_node_key=source,
            target_node_key=target,
            kind="external_file_reference",
        )

        self.assertEqual(
            key,
            (
                ("document", "assembly.FCStd"),
                ("external_file", "resources/material.csv"),
                "external_file_reference",
            ),
        )

    def test_document_to_document_is_accepted_by_generic_semantic_boundary(
        self,
    ) -> None:
        source = self.build_node_key(kind="document", document_path="a.FCStd")
        target = self.build_node_key(kind="document", document_path="b.FCStd")

        key = self.build_edge_key(
            source_node_key=source,
            target_node_key=target,
            kind="document_internal_reference",
        )

        self.assertEqual(
            key,
            (
                ("document", "a.FCStd"),
                ("document", "b.FCStd"),
                "document_internal_reference",
            ),
        )

    def test_self_edge_is_accepted(self) -> None:
        node = self.build_node_key(
            kind="object", document_path="assembly.FCStd", object_name="Body"
        )

        key = self.build_edge_key(
            source_node_key=node,
            target_node_key=node,
            kind="document_internal_reference",
        )

        self.assertEqual(
            key,
            (
                ("object", "assembly.FCStd", "Body"),
                ("object", "assembly.FCStd", "Body"),
                "document_internal_reference",
            ),
        )

    def test_components_are_not_flattened(self) -> None:
        source = self.build_node_key(kind="document", document_path="a.FCStd")
        target = self.build_node_key(
            kind="object", document_path="a.FCStd", object_name="Body"
        )

        key = self.build_edge_key(
            source_node_key=source,
            target_node_key=target,
            kind="document_internal_reference",
        )

        self.assertEqual(len(key), 3)
        self.assertEqual(len(key[0]), 2)
        self.assertEqual(len(key[1]), 3)

    def test_supplied_values_are_preserved_exactly(self) -> None:
        source = ("object", "Assembly Main.FCStd", "Source Object")
        target = ("external_document", "parts/Bölüm.FCStd")

        key = self.build_edge_key(
            source_node_key=source,
            target_node_key=target,
            kind="external_document_reference",
        )

        self.assertEqual(key, (source, target, "external_document_reference"))


class ReferenceTraversalSemanticEdgeIdentityDirectedSemanticsTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_edge_key = (
            self.contract.build_reference_traversal_semantic_edge_identity_key
        )

    def test_reversed_same_document_object_pair_is_distinct(self) -> None:
        a = ("object", "assembly.FCStd", "A")
        b = ("object", "assembly.FCStd", "B")

        forward = self.build_edge_key(
            source_node_key=a, target_node_key=b, kind="document_internal_reference"
        )
        backward = self.build_edge_key(
            source_node_key=b, target_node_key=a, kind="document_internal_reference"
        )

        self.assertNotEqual(forward, backward)

    def test_reversed_cross_document_external_pair_is_distinct(self) -> None:
        local = ("object", "assembly.FCStd", "Body")
        external = ("external_document", "parts/part.FCStd")

        forward = self.build_edge_key(
            source_node_key=local,
            target_node_key=external,
            kind="external_document_reference",
        )
        backward = self.build_edge_key(
            source_node_key=external,
            target_node_key=local,
            kind="external_document_reference",
        )

        self.assertNotEqual(forward, backward)
        self.assertEqual(forward[0], backward[1])
        self.assertEqual(forward[1], backward[0])


class ReferenceTraversalSemanticEdgeIdentityNodeKeyValidationTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_edge_key = (
            self.contract.build_reference_traversal_semantic_edge_identity_key
        )
        self.valid_target = ("document", "b.FCStd")
        self.valid_source = ("document", "a.FCStd")

    def _malformed_node_keys(self):
        return (
            ("plain string", "not-a-tuple"),
            ("bytes", b"not-a-tuple"),
            ("list instead of tuple", ["document", "a.FCStd"]),
            ("empty tuple", ()),
            ("unsupported node kind", ("component", "a.FCStd")),
            ("too few components (object)", ("object", "a.FCStd")),
            ("too many components (document)", ("document", "a.FCStd", "extra")),
            (
                "object key missing object name",
                ("object", "a.FCStd"),
            ),
            (
                "non-object key with extra object-name component",
                ("external_document", "a.FCStd", "extra"),
            ),
            ("non-string kind", (123, "a.FCStd")),
            ("non-string path component", ("document", 123)),
            ("non-string object name", ("object", "a.FCStd", 123)),
            ("empty required component", ("document", "")),
            (
                "nested malformed component",
                ("document", ("a.FCStd",)),
            ),
        )

    def test_rejects_malformed_source_node_keys(self) -> None:
        for label, malformed in self._malformed_node_keys():
            with self.subTest(case=label):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.build_edge_key(
                        source_node_key=malformed,
                        target_node_key=self.valid_target,
                        kind="document_internal_reference",
                    )

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("sourceNodeKey", message)

    def test_rejects_malformed_target_node_keys(self) -> None:
        for label, malformed in self._malformed_node_keys():
            with self.subTest(case=label):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.build_edge_key(
                        source_node_key=self.valid_source,
                        target_node_key=malformed,
                        kind="document_internal_reference",
                    )

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("targetNodeKey", message)

    def test_source_and_target_errors_are_independently_attributed(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as source_ctx:
            self.build_edge_key(
                source_node_key="bad-source",
                target_node_key=self.valid_target,
                kind="document_internal_reference",
            )
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as target_ctx:
            self.build_edge_key(
                source_node_key=self.valid_source,
                target_node_key="bad-target",
                kind="document_internal_reference",
            )

        self.assertIn("sourceNodeKey", str(source_ctx.exception))
        self.assertNotIn("targetNodeKey", str(source_ctx.exception))
        self.assertIn("targetNodeKey", str(target_ctx.exception))
        self.assertNotIn("sourceNodeKey", str(target_ctx.exception))

    def test_errors_are_reference_traversal_output_contract_error(self) -> None:
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ) as ctx:
            self.build_edge_key(
                source_node_key=(),
                target_node_key=self.valid_target,
                kind="document_internal_reference",
            )

        self.assertIsInstance(ctx.exception, ValueError)


class ReferenceTraversalSemanticEdgeIdentityKindValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_edge_key = (
            self.contract.build_reference_traversal_semantic_edge_identity_key
        )
        self.source = ("document", "a.FCStd")
        self.target = ("document", "b.FCStd")

    def test_all_three_supported_kinds_are_accepted(self) -> None:
        for kind in (
            "document_internal_reference",
            "external_document_reference",
            "external_file_reference",
        ):
            with self.subTest(kind=kind):
                key = self.build_edge_key(
                    source_node_key=self.source,
                    target_node_key=self.target,
                    kind=kind,
                )
                self.assertEqual(key[2], kind)

    def test_rejects_invalid_kinds(self) -> None:
        invalid_kinds = (
            "",
            "   ",
            123,
            "external_link",
            "future_reference_kind",
            "DOCUMENT_INTERNAL_REFERENCE",
            " document_internal_reference",
            "document_internal_reference ",
        )

        for kind in invalid_kinds:
            with self.subTest(kind=kind):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.build_edge_key(
                        source_node_key=self.source,
                        target_node_key=self.target,
                        kind=kind,
                    )

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("kind", message)

    def test_accepted_kind_strings_are_preserved_exactly(self) -> None:
        key = self.build_edge_key(
            source_node_key=self.source,
            target_node_key=self.target,
            kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
        )

        self.assertEqual(key[2], "external_file_reference")
        self.assertIs(type(key[2]), str)


class ReferenceTraversalSemanticEdgeIdentityNoNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_edge_key = (
            self.contract.build_reference_traversal_semantic_edge_identity_key
        )

    def test_case_differences_are_preserved_and_distinct(self) -> None:
        lower = ("document", "assembly.fcstd")
        upper = ("document", "Assembly.FCStd")

        lower_key = self.build_edge_key(
            source_node_key=lower,
            target_node_key=("document", "b.FCStd"),
            kind="document_internal_reference",
        )
        upper_key = self.build_edge_key(
            source_node_key=upper,
            target_node_key=("document", "b.FCStd"),
            kind="document_internal_reference",
        )

        self.assertEqual(lower_key[0], lower)
        self.assertEqual(upper_key[0], upper)
        self.assertNotEqual(lower_key, upper_key)

    def test_path_separator_differences_are_preserved(self) -> None:
        forward = ("document", "sub/dir/assembly.FCStd")
        backward = ("document", "sub\\dir\\assembly.FCStd")

        forward_key = self.build_edge_key(
            source_node_key=forward,
            target_node_key=("document", "b.FCStd"),
            kind="document_internal_reference",
        )
        backward_key = self.build_edge_key(
            source_node_key=backward,
            target_node_key=("document", "b.FCStd"),
            kind="document_internal_reference",
        )

        self.assertEqual(forward_key[0][1], "sub/dir/assembly.FCStd")
        self.assertEqual(backward_key[0][1], "sub\\dir\\assembly.FCStd")
        self.assertNotEqual(forward_key, backward_key)

    def test_unicode_values_are_preserved(self) -> None:
        source = ("object", "Bölüm.FCStd", "Gövde")
        target = ("document", "b.FCStd")

        key = self.build_edge_key(
            source_node_key=source,
            target_node_key=target,
            kind="document_internal_reference",
        )

        self.assertEqual(key[0], ("object", "Bölüm.FCStd", "Gövde"))

    def test_spaces_inside_names_are_preserved(self) -> None:
        source = ("object", "Main Assembly.FCStd", "Source Object")
        target = ("document", "b.FCStd")

        key = self.build_edge_key(
            source_node_key=source,
            target_node_key=target,
            kind="document_internal_reference",
        )

        self.assertEqual(key[0], source)

    def test_punctuation_is_preserved(self) -> None:
        source = ("external_document", "parts/part-v1.2(final).FCStd")

        key = self.build_edge_key(
            source_node_key=("document", "a.FCStd"),
            target_node_key=source,
            kind="external_document_reference",
        )

        self.assertEqual(key[1], source)

    def test_relative_path_spelling_differences_are_distinct(self) -> None:
        dotted = ("document", "./a.FCStd")
        plain = ("document", "a.FCStd")

        dotted_key = self.build_edge_key(
            source_node_key=dotted,
            target_node_key=("document", "b.FCStd"),
            kind="document_internal_reference",
        )
        plain_key = self.build_edge_key(
            source_node_key=plain,
            target_node_key=("document", "b.FCStd"),
            kind="document_internal_reference",
        )

        self.assertNotEqual(dotted_key, plain_key)
        self.assertEqual(dotted_key[0][1], "./a.FCStd")
        self.assertEqual(plain_key[0][1], "a.FCStd")

    def test_whitespace_only_path_component_is_accepted_and_not_normalized(
        self,
    ) -> None:
        # The helper's validation boundary only rejects falsy (empty) strings;
        # whitespace-only strings are non-empty and therefore accepted
        # unchanged, consistent with the existing semantic node identity
        # no-normalization behavior.
        key = self.build_edge_key(
            source_node_key=("document", "   "),
            target_node_key=("document", "b.FCStd"),
            kind="document_internal_reference",
        )

        self.assertEqual(key[0], ("document", "   "))

    def test_whitespace_only_object_name_is_accepted_and_not_normalized(self) -> None:
        key = self.build_edge_key(
            source_node_key=("object", "a.FCStd", "   "),
            target_node_key=("document", "b.FCStd"),
            kind="document_internal_reference",
        )

        self.assertEqual(key[0], ("object", "a.FCStd", "   "))

    def test_whitespace_only_kind_is_rejected_by_enum_check(self) -> None:
        # Whitespace-only kind values are rejected only because they do not
        # match the fixed supported-kind vocabulary, not because of any
        # whitespace-stripping or normalization step.
        with self.assertRaises(
            self.contract.ReferenceTraversalOutputContractError
        ):
            self.build_edge_key(
                source_node_key=("document", "a.FCStd"),
                target_node_key=("document", "b.FCStd"),
                kind="   ",
            )


class ReferenceTraversalSemanticEdgeIdentityContractMetadataTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_semantic_edge_identity_contract
        )

    def test_metadata_contains_documented_keys(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata),
            {
                "identityComponents",
                "supportedEdgeKinds",
                "excludedRawEdgeFields",
                "semanticNodeIdentityKeys",
                "directed",
                "reverseEdgeIsDistinct",
                "inputBehavior",
                "deduplication",
                "generatedSerializedEdgeIdentifier",
                "rawPayloadShapeChanged",
                "rawPayloadEdgesDeduplicated",
                "performsRealFreecadTraversal",
                "engineNormalizationPerformed",
                "pdmIdentityProduced",
                "propertyOrReferenceMechanismSensitiveIdentity",
            },
        )

    def test_metadata_identity_components_are_exact_and_ordered(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["identityComponents"],
            [
                "sourceSemanticNodeIdentityKey",
                "targetSemanticNodeIdentityKey",
                "kind",
            ],
        )
        self.assertIsInstance(metadata["identityComponents"], list)

    def test_metadata_supported_edge_kinds_are_exact_and_ordered(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["supportedEdgeKinds"],
            [
                "document_internal_reference",
                "external_document_reference",
                "external_file_reference",
            ],
        )

    def test_metadata_excluded_raw_edge_fields_are_exact(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["excludedRawEdgeFields"],
            ["source", "target", "state", "diagnostic", "sequence"],
        )

    def test_metadata_declares_directed_semantics(self) -> None:
        metadata = self.build_contract()

        self.assertIs(metadata["directed"], True)
        self.assertIs(metadata["reverseEdgeIsDistinct"], True)

    def test_metadata_declares_semantic_node_identity_dependency(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata["semanticNodeIdentityKeys"]), {"source", "target"}
        )
        for value in metadata["semanticNodeIdentityKeys"].values():
            self.assertIsInstance(value, str)
            self.assertTrue(value)

    def test_metadata_declares_no_normalization(self) -> None:
        metadata = self.build_contract()

        self.assertIs(
            metadata["inputBehavior"]["preservesAcceptedStringsExactly"], True
        )
        self.assertIs(metadata["inputBehavior"]["normalizationPerformed"], False)
        self.assertIs(metadata["inputBehavior"]["filesystemInspected"], False)

    def test_metadata_declares_deduplication_definition(self) -> None:
        metadata = self.build_contract()
        deduplication = metadata["deduplication"]

        self.assertEqual(
            deduplication["key"],
            [
                "sourceSemanticNodeIdentityKey",
                "targetSemanticNodeIdentityKey",
                "kind",
            ],
        )
        self.assertEqual(
            deduplication["duplicateCondition"], "all_identity_components_equal"
        )
        self.assertEqual(
            deduplication["outputOrder"],
            [
                "sourceSemanticNodeIdentityKey",
                "targetSemanticNodeIdentityKey",
                "kind",
            ],
        )
        self.assertIs(deduplication["rawStateOrDiagnosticMerged"], False)
        self.assertIs(deduplication["representativeRawEdgeSelected"], False)

    def test_metadata_declares_no_generated_edge_identifier_or_payload_changes(
        self,
    ) -> None:
        metadata = self.build_contract()

        self.assertIs(metadata["generatedSerializedEdgeIdentifier"], False)
        self.assertIs(metadata["rawPayloadShapeChanged"], False)
        self.assertIs(metadata["rawPayloadEdgesDeduplicated"], False)

    def test_metadata_declares_no_traversal_or_normalization_or_pdm_behavior(
        self,
    ) -> None:
        metadata = self.build_contract()

        self.assertIs(metadata["performsRealFreecadTraversal"], False)
        self.assertIs(metadata["engineNormalizationPerformed"], False)
        self.assertIs(metadata["pdmIdentityProduced"], False)

    def test_metadata_declares_property_and_mechanism_identity_deferred(
        self,
    ) -> None:
        metadata = self.build_contract()
        provenance = metadata["propertyOrReferenceMechanismSensitiveIdentity"]

        self.assertIs(provenance["supported"], False)
        self.assertIs(provenance["provenancePresentInRawEdgeContract"], False)
        self.assertIs(provenance["deferred"], True)
        self.assertIs(
            provenance["helperClaimsPropertySensitiveDeduplication"], False
        )
        self.assertIsInstance(provenance["futureRequirement"], str)
        self.assertTrue(provenance["futureRequirement"])

    def test_metadata_is_canonical_json_compatible(self) -> None:
        metadata = self.build_contract()

        serialized = dumps_canonical(metadata)

        self.assertEqual(dumps_canonical(metadata), serialized)
        _assert_only_json_leaf_types(self, metadata)

    def test_repeated_calls_return_equal_but_independent_objects(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["identityComponents"], second["identityComponents"])
        self.assertIsNot(first["deduplication"], second["deduplication"])
        self.assertIsNot(
            first["propertyOrReferenceMechanismSensitiveIdentity"],
            second["propertyOrReferenceMechanismSensitiveIdentity"],
        )

    def test_mutating_one_result_does_not_affect_a_later_call(self) -> None:
        first = self.build_contract()

        first["identityComponents"].append("mutated")
        first["supportedEdgeKinds"].append("mutated")
        first["excludedRawEdgeFields"].append("mutated")
        first["deduplication"]["key"].append("mutated")
        first["propertyOrReferenceMechanismSensitiveIdentity"]["supported"] = True
        first["injected"] = "mutated"

        second = self.build_contract()

        self.assertEqual(
            second["identityComponents"],
            [
                "sourceSemanticNodeIdentityKey",
                "targetSemanticNodeIdentityKey",
                "kind",
            ],
        )
        self.assertEqual(
            second["supportedEdgeKinds"],
            [
                "document_internal_reference",
                "external_document_reference",
                "external_file_reference",
            ],
        )
        self.assertEqual(
            second["excludedRawEdgeFields"],
            ["source", "target", "state", "diagnostic", "sequence"],
        )
        self.assertEqual(
            second["deduplication"]["key"],
            [
                "sourceSemanticNodeIdentityKey",
                "targetSemanticNodeIdentityKey",
                "kind",
            ],
        )
        self.assertIs(
            second["propertyOrReferenceMechanismSensitiveIdentity"]["supported"],
            False,
        )
        self.assertNotIn("injected", second)

    def test_mutation_does_not_affect_module_level_constants(self) -> None:
        metadata = self.build_contract()

        metadata["identityComponents"].append("mutated")
        metadata["supportedEdgeKinds"].append("mutated")
        metadata["excludedRawEdgeFields"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS,
            (
                "sourceSemanticNodeIdentityKey",
                "targetSemanticNodeIdentityKey",
                "kind",
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS,
            (
                "document_internal_reference",
                "external_document_reference",
                "external_file_reference",
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_EXCLUDED_FIELDS,
            ("source", "target", "state", "diagnostic", "sequence"),
        )


class ReferenceTraversalSemanticEdgeIdentityDeduplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_edge_key = (
            self.contract.build_reference_traversal_semantic_edge_identity_key
        )
        self.dedup = (
            self.contract.deduplicate_reference_traversal_semantic_edge_identity_keys
        )
        self.doc_a = ("document", "a.FCStd")
        self.doc_b = ("document", "b.FCStd")
        self.doc_c = ("document", "c.FCStd")
        self.obj_a_body = ("object", "a.FCStd", "Body")
        self.obj_a_bracket = ("object", "a.FCStd", "Bracket")
        self.obj_b_body = ("object", "b.FCStd", "Body")

    def _key(self, source, target, kind="document_internal_reference"):
        return self.build_edge_key(
            source_node_key=source, target_node_key=target, kind=kind
        )

    def test_empty_sequence_returns_empty_tuple(self) -> None:
        self.assertEqual(self.dedup([]), ())
        self.assertEqual(self.dedup(()), ())
        self.assertIsInstance(self.dedup([]), tuple)

    def test_two_duplicates_collapse_to_one(self) -> None:
        key = self._key(self.doc_a, self.doc_b)

        result = self.dedup([key, key])

        self.assertEqual(result, (key,))

    def test_many_duplicates_collapse_to_one(self) -> None:
        key = self._key(self.doc_a, self.doc_b)

        result = self.dedup([key] * 25)

        self.assertEqual(result, (key,))

    def test_non_contiguous_duplicates_collapse(self) -> None:
        key_a = self._key(self.doc_a, self.doc_b)
        key_b = self._key(self.doc_b, self.doc_c)

        result = self.dedup([key_a, key_b, key_a, key_b, key_a])

        self.assertEqual(result, tuple(sorted({key_a, key_b})))

    def test_duplicates_from_separate_builder_calls_collapse(self) -> None:
        first_call = self._key(self.doc_a, self.doc_b)
        second_call = self._key(self.doc_a, self.doc_b)

        self.assertEqual(first_call, second_call)
        self.assertEqual(self.dedup([first_call, second_call]), (first_call,))

    def test_equal_but_not_identical_nested_tuples_collapse(self) -> None:
        # tuple(list(...)) forces a fresh tuple object at runtime, avoiding
        # CPython's compile-time constant folding of identical tuple literals.
        def _build(*parts):
            return tuple(list(parts))

        key_one = (
            _build("document", "a.FCStd"),
            _build("document", "b.FCStd"),
            "document_internal_reference",
        )
        key_two = (
            _build("document", "a.FCStd"),
            _build("document", "b.FCStd"),
            "document_internal_reference",
        )

        self.assertIsNot(key_one[0], key_two[0])
        self.assertEqual(key_one[0], key_two[0])
        self.assertEqual(self.dedup([key_one, key_two]), (key_one,))

    def test_deterministic_lexicographic_ordering_with_explicit_expected_tuple(
        self,
    ) -> None:
        by_source_path = self._key(self.doc_b, self.doc_a)
        by_source_path_2 = self._key(self.doc_a, self.doc_a)
        by_object_name = self._key(self.obj_a_bracket, self.doc_a)
        by_object_name_2 = self._key(self.obj_a_body, self.doc_a)
        by_target_path = self._key(self.doc_a, self.doc_c)
        by_target_path_2 = self._key(self.doc_a, self.doc_b)
        by_target_object_name = self._key(self.doc_a, self.obj_a_bracket)
        by_target_object_name_2 = self._key(self.doc_a, self.obj_a_body)
        by_kind = self._key(
            self.doc_a, self.doc_b, kind="external_document_reference"
        )
        by_source_node_kind = self._key(self.obj_b_body, self.doc_a)

        unsorted_input = [
            by_source_path,
            by_kind,
            by_source_node_kind,
            by_object_name,
            by_target_path,
            by_target_object_name,
            by_source_path_2,
            by_object_name_2,
            by_target_path_2,
            by_target_object_name_2,
        ]

        expected = (
            by_source_path_2,  # ("document","a.FCStd") -> ("document","a.FCStd")
            by_target_path_2,  # ("document","a.FCStd") -> ("document","b.FCStd") internal
            by_kind,  # ("document","a.FCStd") -> ("document","b.FCStd") external_document
            by_target_path,  # ("document","a.FCStd") -> ("document","c.FCStd")
            by_target_object_name_2,  # ("document","a.FCStd") -> ("object","a.FCStd","Body")
            by_target_object_name,  # ("document","a.FCStd") -> ("object","a.FCStd","Bracket")
            by_source_path,  # ("document","b.FCStd") -> ("document","a.FCStd")
            by_object_name_2,  # ("object","a.FCStd","Body") -> ("document","a.FCStd")
            by_object_name,  # ("object","a.FCStd","Bracket") -> ("document","a.FCStd")
            by_source_node_kind,  # ("object","b.FCStd","Body") -> ("document","a.FCStd")
        )

        result = self.dedup(unsorted_input)

        self.assertEqual(result, expected)
        self.assertEqual(result, tuple(sorted(set(unsorted_input))))

    def test_permutation_and_duplicate_count_independence(self) -> None:
        import itertools

        keys = (
            self._key(self.doc_a, self.doc_b),
            self._key(self.doc_b, self.doc_a),
            self._key(self.obj_a_body, self.doc_a),
        )
        expected = tuple(sorted(set(keys)))

        for count, permutation in enumerate(itertools.permutations(keys)):
            with self.subTest(permutation=count):
                self.assertEqual(self.dedup(list(permutation)), expected)

        with_repeats = list(keys) + list(reversed(keys)) + [keys[0]] * 3
        self.assertEqual(self.dedup(with_repeats), expected)

    def test_preserves_reversed_edges(self) -> None:
        forward = self._key(self.doc_a, self.doc_b)
        backward = self._key(self.doc_b, self.doc_a)

        result = self.dedup([forward, backward])

        self.assertEqual(len(result), 2)
        self.assertIn(forward, result)
        self.assertIn(backward, result)

    def test_preserves_same_target_different_sources(self) -> None:
        from_a = self._key(self.doc_a, self.doc_c)
        from_b = self._key(self.doc_b, self.doc_c)

        result = self.dedup([from_a, from_b])

        self.assertEqual(len(result), 2)

    def test_preserves_same_source_different_targets(self) -> None:
        to_b = self._key(self.doc_a, self.doc_b)
        to_c = self._key(self.doc_a, self.doc_c)

        result = self.dedup([to_b, to_c])

        self.assertEqual(len(result), 2)

    def test_preserves_same_source_and_target_different_kinds(self) -> None:
        internal = self._key(self.doc_a, self.doc_b, kind="document_internal_reference")
        external = self._key(
            self.doc_a, self.doc_b, kind="external_document_reference"
        )

        result = self.dedup([internal, external])

        self.assertEqual(len(result), 2)

    def test_preserves_multiple_outgoing_edges_from_one_source(self) -> None:
        to_b = self._key(self.doc_a, self.doc_b)
        to_c = self._key(self.doc_a, self.doc_c)
        to_obj = self._key(self.doc_a, self.obj_a_body)

        result = self.dedup([to_b, to_c, to_obj])

        self.assertEqual(len(result), 3)

    def test_preserves_multiple_incoming_edges_to_shared_target(self) -> None:
        from_a = self._key(self.doc_a, self.doc_c)
        from_b = self._key(self.doc_b, self.doc_c)
        from_obj = self._key(self.obj_a_body, self.doc_c)

        result = self.dedup([from_a, from_b, from_obj])

        self.assertEqual(len(result), 3)

    def test_preserves_same_document_path_different_object_names(self) -> None:
        body = self._key(self.obj_a_body, self.doc_c)
        bracket = self._key(self.obj_a_bracket, self.doc_c)

        result = self.dedup([body, bracket])

        self.assertEqual(len(result), 2)

    def test_preserves_same_object_name_in_different_document_paths(self) -> None:
        in_a = self._key(self.obj_a_body, self.doc_c)
        in_b = self._key(self.obj_b_body, self.doc_c)

        result = self.dedup([in_a, in_b])

        self.assertEqual(len(result), 2)

    def test_rejects_invalid_outer_collections(self) -> None:
        key = self._key(self.doc_a, self.doc_b)
        invalid_outer = (
            "not-a-sequence",
            b"not-a-sequence",
            5,
            None,
            {"a": key},
            (entry for entry in [key]),
        )

        for value in invalid_outer:
            with self.subTest(value=value):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.dedup(value)

                message = str(ctx.exception)
                self.assertNotIn("\n", message)
                self.assertIn("identityKeys", message)

    def test_accepts_tuple_and_list_outer_collections(self) -> None:
        key = self._key(self.doc_a, self.doc_b)

        self.assertEqual(self.dedup([key, key]), (key,))
        self.assertEqual(self.dedup((key, key)), (key,))

    def test_rejects_malformed_entries(self) -> None:
        raw_edge = self.contract.RawReferenceTraversalEdge(
            source="a", target="b", kind="document_internal_reference", state="resolved"
        )
        malformed_entries = (
            "not-a-key",
            b"not-a-key",
            [self.doc_a, self.doc_b, "document_internal_reference"],
            (),
            (self.doc_a, self.doc_b),
            (self.doc_a, self.doc_b, "document_internal_reference", "extra"),
            ("bad-source", self.doc_b, "document_internal_reference"),
            (self.doc_a, "bad-target", "document_internal_reference"),
            (self.doc_a, self.doc_b, "external_link"),
            (self.doc_a, self.doc_b, 123),
            raw_edge,
            ("a", "b", "document_internal_reference", "resolved", None),
        )

        for entry in malformed_entries:
            with self.subTest(entry=entry):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.dedup([entry])

                message = str(ctx.exception)
                self.assertNotIn("\n", message)

    def test_self_edge_is_valid_at_dedup_boundary(self) -> None:
        node = self.obj_a_body
        self_edge = self._key(node, node)

        result = self.dedup([self_edge, self_edge])

        self.assertEqual(result, (self_edge,))

    def test_construction_does_not_mutate_supplied_node_key_tuples(self) -> None:
        source = ("document", "a.FCStd")
        target = ("document", "b.FCStd")
        source_snapshot = tuple(source)
        target_snapshot = tuple(target)

        self.build_edge_key(
            source_node_key=source,
            target_node_key=target,
            kind="document_internal_reference",
        )

        self.assertEqual(source, source_snapshot)
        self.assertEqual(target, target_snapshot)

    def test_dedup_does_not_mutate_outer_list_or_nested_tuples(self) -> None:
        key_a = self._key(self.doc_b, self.doc_a)
        key_b = self._key(self.doc_a, self.doc_b)
        keys = [key_a, key_b]
        snapshot = list(keys)

        self.dedup(keys)

        self.assertEqual(keys, snapshot)
        self.assertEqual(keys[0], key_a)
        self.assertEqual(keys[1], key_b)

    def test_returned_collection_and_entries_are_immutable_tuples(self) -> None:
        key = self._key(self.doc_a, self.doc_b)

        result = self.dedup([key])

        self.assertIsInstance(result, tuple)
        self.assertIsInstance(result[0], tuple)
        self.assertIsInstance(result[0][0], tuple)
        self.assertIsInstance(result[0][1], tuple)

        with self.assertRaises(TypeError):
            result[0] = "mutated"
        with self.assertRaises(TypeError):
            result[0][0][0] = "mutated"

    def test_repeated_calls_return_equal_values_without_shared_mutable_state(
        self,
    ) -> None:
        keys = [self._key(self.doc_b, self.doc_a), self._key(self.doc_a, self.doc_b)]

        first = self.dedup(keys)
        second = self.dedup(keys)

        self.assertEqual(first, second)
        self.assertEqual(first, tuple(sorted(set(keys))))


class ReferenceTraversalSemanticEdgeIdentityRawPayloadCompatibilityTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_duplicate_raw_edges_remain_separate_in_raw_payload(self) -> None:
        payload = _build_payload(
            self.contract,
            edges=[
                _edge(source="a", target="b", kind="link"),
                _edge(source="a", target="b", kind="link"),
            ],
        )

        self.assertEqual(len(payload["edges"]), 2)
        self.assertEqual(
            [edge["sequence"] for edge in payload["edges"]], [0, 1]
        )

    def test_raw_edge_ordering_is_unaffected_by_semantic_helper_existence(
        self,
    ) -> None:
        edges = [
            _edge(source="node-c", target="node-a"),
            _edge(source="node-a", target="node-b"),
        ]

        payload = _build_payload(self.contract, edges=edges)
        expected = self.contract.order_reference_traversal_edges(edges)

        self.assertEqual(
            [(edge["source"], edge["target"]) for edge in payload["edges"]],
            [(edge.source, edge.target) for edge in expected],
        )

    def test_raw_edge_sequence_assignment_remains_zero_based(self) -> None:
        payload = _build_payload(
            self.contract,
            edges=[
                _edge(source="node-c", target="node-a"),
                _edge(source="node-a", target="node-b"),
                _edge(source="node-a", target="node-b"),
            ],
        )

        self.assertEqual(
            [edge["sequence"] for edge in payload["edges"]], [0, 1, 2]
        )

    def test_arbitrary_non_semantic_raw_edge_kind_still_passes_through(self) -> None:
        payload = _build_payload(
            self.contract, edges=[_edge(source="a", target="b", kind="not_a_semantic_kind")]
        )

        self.assertEqual(payload["edges"][0]["kind"], "not_a_semantic_kind")

    def test_semantic_supported_kind_restriction_does_not_leak_into_raw_builder(
        self,
    ) -> None:
        # "external_link" is not one of the three semantic edge identity
        # supported kinds, yet the raw payload builder must still accept it
        # because raw payload validation and semantic edge identity
        # validation are independent boundaries.
        self.assertNotIn(
            "external_link",
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS,
        )
        payload = _build_payload(
            self.contract, edges=[_edge(source="a", target="b", kind="external_link")]
        )
        self.assertEqual(payload["edges"][0]["kind"], "external_link")

    def test_raw_state_and_diagnostic_fields_remain_emitted(self) -> None:
        payload = _build_payload(
            self.contract,
            edges=[
                _edge(
                    source="a",
                    target="b",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
                    diagnostic="edge diagnostic",
                )
            ],
        )

        self.assertEqual(payload["edges"][0]["state"], "missing")
        self.assertEqual(payload["edges"][0]["diagnostic"], "edge diagnostic")

    def test_raw_payload_edge_shape_has_no_provenance_or_semantic_id_fields(
        self,
    ) -> None:
        payload = _build_payload(self.contract, edges=[_edge(source="a", target="b")])

        self.assertEqual(
            set(payload["edges"][0]),
            {"sequence", "source", "target", "kind", "state", "diagnostic"},
        )

    def test_calling_dedup_helper_does_not_mutate_previously_built_raw_edges(
        self,
    ) -> None:
        edge = _edge(source="a", target="b")
        before = (edge.source, edge.target, edge.kind, edge.state, edge.diagnostic)

        key = self.contract.build_reference_traversal_semantic_edge_identity_key(
            source_node_key=("document", "a.FCStd"),
            target_node_key=("document", "b.FCStd"),
            kind="document_internal_reference",
        )
        self.contract.deduplicate_reference_traversal_semantic_edge_identity_keys(
            [key, key]
        )

        after = (edge.source, edge.target, edge.kind, edge.state, edge.diagnostic)
        self.assertEqual(before, after)

        payload = _build_payload(self.contract, edges=[edge])
        self.assertEqual(payload["edges"][0]["source"], "a")


class ReferenceTraversalSemanticEdgeIdentityCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_existing_semantic_node_identity_constants_are_unchanged(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS,
            ("kind", "documentPath", "objectName"),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_EXCLUDED_FIELDS,
            ("id", "state", "label", "diagnostic", "sequence"),
        )
        self.assertEqual(
            list(
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS_BY_KIND
            ),
            ["document", "object", "external_document", "external_file"],
        )

    def test_existing_node_key_builder_behavior_is_unchanged(self) -> None:
        key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind="object", document_path="assembly.FCStd", object_name="Body"
        )

        self.assertEqual(key, ("object", "assembly.FCStd", "Body"))

    def test_edge_key_validation_reuses_node_key_builder_output_directly(self) -> None:
        source = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind="document", document_path="assembly.FCStd"
        )
        target = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind="object", document_path="assembly.FCStd", object_name="Body"
        )

        edge_key = self.contract.build_reference_traversal_semantic_edge_identity_key(
            source_node_key=source,
            target_node_key=target,
            kind="document_internal_reference",
        )

        self.assertEqual(edge_key, (source, target, "document_internal_reference"))

    def test_edge_helper_additions_do_not_modify_node_identity_contract_metadata(
        self,
    ) -> None:
        node_metadata = (
            self.contract.build_reference_traversal_semantic_node_identity_contract()
        )

        self.assertEqual(
            set(node_metadata),
            {
                "supportedNodeKinds",
                "identityFieldsByNodeKind",
                "identityFieldOrder",
                "excludedFields",
                "pathInputPolicy",
                "normalizationPerformed",
                "filesystemInspected",
                "generatedIdentifierFormula",
                "engineNormalizationPerformed",
                "pdmIdentityProduced",
            },
        )


class ReferenceTraversalSemanticEdgeIdentityProvenanceLimitationTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_key_builder_signature_accepts_only_documented_parameters(self) -> None:
        import inspect

        signature = inspect.signature(
            self.contract.build_reference_traversal_semantic_edge_identity_key
        )

        self.assertEqual(
            set(signature.parameters),
            {"source_node_key", "target_node_key", "kind"},
        )

    def test_no_provenance_parameter_exists_on_key_builder(self) -> None:
        with self.assertRaises(TypeError):
            self.contract.build_reference_traversal_semantic_edge_identity_key(
                source_node_key=("document", "a.FCStd"),
                target_node_key=("document", "b.FCStd"),
                kind="document_internal_reference",
                source_property="Placement",
            )
        with self.assertRaises(TypeError):
            self.contract.build_reference_traversal_semantic_edge_identity_key(
                source_node_key=("document", "a.FCStd"),
                target_node_key=("document", "b.FCStd"),
                kind="document_internal_reference",
                reference_mechanism="expression",
            )
        with self.assertRaises(TypeError):
            self.contract.build_reference_traversal_semantic_edge_identity_key(
                source_node_key=("document", "a.FCStd"),
                target_node_key=("document", "b.FCStd"),
                kind="document_internal_reference",
                property="Placement",
            )

    def test_raw_edge_dataclass_fields_remain_unchanged(self) -> None:
        expected_fields = {"source", "target", "kind", "state", "diagnostic"}
        actual_fields = {
            field.name
            for field in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }

        self.assertEqual(actual_fields, expected_fields)

    def test_metadata_explicitly_marks_provenance_identity_as_deferred(self) -> None:
        metadata = (
            self.contract.build_reference_traversal_semantic_edge_identity_contract()
        )
        provenance = metadata["propertyOrReferenceMechanismSensitiveIdentity"]

        self.assertIs(provenance["deferred"], True)
        self.assertIs(provenance["supported"], False)
        self.assertIs(
            provenance["helperClaimsPropertySensitiveDeduplication"], False
        )


class ReferenceTraversalNodeOrderKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_key = self.contract.build_reference_traversal_node_order_key

    def test_document_path_none_sorts_before_provided_string(self) -> None:
        without_path = _node(document_path=None)
        with_path = _node(document_path="assembly.FCStd")

        self.assertLess(self.build_key(without_path), self.build_key(with_path))

    def test_object_name_none_sorts_before_provided_string(self) -> None:
        without_name = _node(object_name=None)
        with_name = _node(object_name="Body")

        self.assertLess(self.build_key(without_name), self.build_key(with_name))

    def test_label_none_sorts_before_provided_string(self) -> None:
        without_label = _node(label=None)
        with_label = _node(label="Main Body")

        self.assertLess(self.build_key(without_label), self.build_key(with_label))

    def test_diagnostic_none_sorts_before_provided_string(self) -> None:
        without_diagnostic = _node(diagnostic=None)
        with_diagnostic = _node(diagnostic="observed")

        self.assertLess(
            self.build_key(without_diagnostic), self.build_key(with_diagnostic)
        )

    def test_document_path_takes_priority_over_kind(self) -> None:
        earlier = _node(
            document_path=None,
            kind="zzz_kind",
            id="z",
            object_name=None,
            label=None,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            diagnostic=None,
        )
        later = _node(
            document_path="a.FCStd",
            kind="aaa_kind",
            id="a",
            object_name=None,
            label=None,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            diagnostic=None,
        )

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_kind_takes_priority_over_id(self) -> None:
        earlier = _node(
            document_path="a.FCStd",
            kind="aaa_kind",
            id="zzz",
            object_name=None,
            label=None,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            diagnostic=None,
        )
        later = _node(
            document_path="a.FCStd",
            kind="bbb_kind",
            id="aaa",
            object_name=None,
            label=None,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            diagnostic=None,
        )

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_id_takes_priority_over_object_name(self) -> None:
        earlier = _node(
            document_path="a.FCStd",
            kind="k",
            id="aaa",
            object_name="zzz",
            label=None,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            diagnostic=None,
        )
        later = _node(
            document_path="a.FCStd",
            kind="k",
            id="bbb",
            object_name="aaa",
            label=None,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            diagnostic=None,
        )

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_object_name_takes_priority_over_label(self) -> None:
        earlier = _node(
            document_path="a.FCStd",
            kind="k",
            id="a",
            object_name="aaa",
            label="zzz",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            diagnostic=None,
        )
        later = _node(
            document_path="a.FCStd",
            kind="k",
            id="a",
            object_name="bbb",
            label="aaa",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            diagnostic=None,
        )

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_label_takes_priority_over_state(self) -> None:
        earlier = _node(
            document_path="a.FCStd",
            kind="k",
            id="a",
            object_name="o",
            label="aaa",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
            diagnostic=None,
        )
        later = _node(
            document_path="a.FCStd",
            kind="k",
            id="a",
            object_name="o",
            label="bbb",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
            diagnostic=None,
        )

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_state_takes_priority_over_diagnostic(self) -> None:
        earlier = _node(
            document_path="a.FCStd",
            kind="k",
            id="a",
            object_name="o",
            label="l",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
            diagnostic="zzz",
        )
        later = _node(
            document_path="a.FCStd",
            kind="k",
            id="a",
            object_name="o",
            label="l",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
            diagnostic="aaa",
        )

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_state_uses_ordinary_lexicographic_order(self) -> None:
        nodes = [
            _node(
                document_path="a.FCStd",
                kind="k",
                id="a",
                object_name=None,
                label=None,
                state=state,
                diagnostic=None,
            )
            for state in self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES
        ]

        ordered = sorted(nodes, key=self.build_key)

        self.assertEqual(
            [node.state for node in ordered],
            ["failed", "missing", "resolved", "skipped", "unresolved"],
        )

    def test_case_is_preserved_in_comparison(self) -> None:
        upper = _node(document_path="Alpha.FCStd")
        lower = _node(document_path="alpha.FCStd")

        self.assertLess(self.build_key(upper), self.build_key(lower))

    def test_whitespace_is_preserved_in_comparison(self) -> None:
        padded = _node(document_path=" alpha.FCStd")
        unpadded = _node(document_path="alpha.FCStd")

        self.assertLess(self.build_key(padded), self.build_key(unpadded))

    def test_unicode_is_compared_lexicographically(self) -> None:
        plain = _node(document_path="cafe.FCStd")
        accented = _node(document_path="café.FCStd")

        self.assertLess(self.build_key(plain), self.build_key(accented))

    def test_path_separators_are_not_normalized(self) -> None:
        forward_slash = _node(document_path="dir/a.FCStd")
        backslash = _node(document_path="dir\\a.FCStd")

        self.assertLess(self.build_key(forward_slash), self.build_key(backslash))

    def test_key_is_safely_sortable(self) -> None:
        nodes = [_node(id="c"), _node(id="a"), _node(id="b")]

        ordered = sorted(nodes, key=self.build_key)

        self.assertEqual([node.id for node in ordered], ["a", "b", "c"])

    def test_order_helper_matches_key_builder_ordering(self) -> None:
        nodes = [_node(id="c"), _node(id="a"), _node(id="b")]

        ordered = self.contract.order_reference_traversal_nodes(nodes)
        expected = tuple(sorted(nodes, key=self.build_key))

        self.assertEqual(ordered, expected)

    def test_input_sequence_and_dataclass_instances_are_not_mutated(self) -> None:
        nodes = [_node(id="c"), _node(id="a"), _node(id="b")]
        snapshot = list(nodes)

        self.contract.order_reference_traversal_nodes(nodes)

        self.assertEqual(nodes, snapshot)

    def test_output_is_immutable_tuple(self) -> None:
        result = self.contract.order_reference_traversal_nodes([_node()])

        self.assertIsInstance(result, tuple)
        with self.assertRaises(TypeError):
            result[0] = _node()

    def test_duplicate_raw_nodes_remain_present(self) -> None:
        duplicate_a = _node(id="dup")
        duplicate_b = _node(id="dup")

        result = self.contract.order_reference_traversal_nodes(
            [duplicate_a, duplicate_b]
        )

        self.assertEqual(len(result), 2)

    def test_rejects_non_node_argument(self) -> None:
        with self.assertRaises(self.contract.ReferenceTraversalOutputContractError):
            self.build_key(object())


class ReferenceTraversalEdgeOrderKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_key = self.contract.build_reference_traversal_edge_order_key

    def test_diagnostic_none_sorts_before_provided_string(self) -> None:
        without_diagnostic = _edge(diagnostic=None)
        with_diagnostic = _edge(diagnostic="observed")

        self.assertLess(
            self.build_key(without_diagnostic), self.build_key(with_diagnostic)
        )

    def test_source_takes_priority_over_everything(self) -> None:
        earlier = _edge(
            source="a",
            target="z",
            kind="z",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
            diagnostic="z",
        )
        later = _edge(
            source="b",
            target="a",
            kind="a",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
            diagnostic="a",
        )

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_target_takes_priority_over_kind(self) -> None:
        earlier = _edge(
            source="x",
            target="a",
            kind="z",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
            diagnostic="z",
        )
        later = _edge(
            source="x",
            target="b",
            kind="a",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
            diagnostic="a",
        )

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_kind_takes_priority_over_state(self) -> None:
        earlier = _edge(
            source="x",
            target="y",
            kind="a",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
            diagnostic="z",
        )
        later = _edge(
            source="x",
            target="y",
            kind="b",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
            diagnostic="a",
        )

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_state_takes_priority_over_diagnostic(self) -> None:
        earlier = _edge(
            source="x",
            target="y",
            kind="k",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
            diagnostic="zzz",
        )
        later = _edge(
            source="x",
            target="y",
            kind="k",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
            diagnostic="aaa",
        )

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_case_is_preserved_in_comparison(self) -> None:
        upper = _edge(source="Alpha")
        lower = _edge(source="alpha")

        self.assertLess(self.build_key(upper), self.build_key(lower))

    def test_whitespace_is_preserved_in_comparison(self) -> None:
        padded = _edge(source=" alpha")
        unpadded = _edge(source="alpha")

        self.assertLess(self.build_key(padded), self.build_key(unpadded))

    def test_unicode_is_compared_lexicographically(self) -> None:
        plain = _edge(source="cafe")
        accented = _edge(source="café")

        self.assertLess(self.build_key(plain), self.build_key(accented))

    def test_endpoints_are_not_rewritten_or_normalized(self) -> None:
        forward_slash = _edge(source="dir/a", target="dir/b")
        backslash = _edge(source="dir\\a", target="dir\\b")

        self.assertLess(self.build_key(forward_slash), self.build_key(backslash))

    def test_order_helper_matches_key_builder_ordering(self) -> None:
        edges = [
            _edge(source="c", target="a"),
            _edge(source="a", target="b"),
        ]

        ordered = self.contract.order_reference_traversal_edges(edges)
        expected = tuple(sorted(edges, key=self.build_key))

        self.assertEqual(ordered, expected)

    def test_input_is_not_mutated(self) -> None:
        edges = [_edge(source="c", target="a"), _edge(source="a", target="b")]
        snapshot = list(edges)

        self.contract.order_reference_traversal_edges(edges)

        self.assertEqual(edges, snapshot)

    def test_output_is_immutable_tuple(self) -> None:
        result = self.contract.order_reference_traversal_edges([_edge()])

        self.assertIsInstance(result, tuple)
        with self.assertRaises(TypeError):
            result[0] = _edge()

    def test_duplicate_raw_edges_remain_present(self) -> None:
        duplicate_a = _edge(source="a", target="b")
        duplicate_b = _edge(source="a", target="b")

        result = self.contract.order_reference_traversal_edges(
            [duplicate_a, duplicate_b]
        )

        self.assertEqual(len(result), 2)

    def test_directed_edge_order_remains_significant(self) -> None:
        forward = _edge(source="a", target="b")
        backward = _edge(source="b", target="a")

        result = self.contract.order_reference_traversal_edges([backward, forward])

        self.assertEqual(
            [(edge.source, edge.target) for edge in result],
            [("a", "b"), ("b", "a")],
        )

    def test_rejects_non_edge_argument(self) -> None:
        with self.assertRaises(self.contract.ReferenceTraversalOutputContractError):
            self.build_key(object())


class ReferenceTraversalDiagnosticOrderKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_key = self.contract.build_reference_traversal_diagnostic_order_key
        self.order = self.contract.order_reference_traversal_diagnostics

    def test_order_fields_constant_is_exact_and_immutable(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_ORDER_FIELDS,
            ("stage", "severity", "code", "message"),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_ORDER_FIELDS, tuple
        )
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_ORDER_FIELDS[0] = "x"

    def test_stage_none_sorts_before_every_provided_stage(self) -> None:
        without_stage = _diagnostic(stage=None)
        with_stage = _diagnostic(stage="a")

        self.assertLess(self.build_key(without_stage), self.build_key(with_stage))

    def test_stage_takes_priority_over_severity_code_and_message(self) -> None:
        earlier = _diagnostic(stage="a", severity="z", code="z", message="z")
        later = _diagnostic(stage="b", severity="a", code="a", message="a")

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_severity_takes_priority_over_code_and_message(self) -> None:
        earlier = _diagnostic(stage="s", severity="a", code="z", message="z")
        later = _diagnostic(stage="s", severity="b", code="a", message="a")

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_code_takes_priority_over_message(self) -> None:
        earlier = _diagnostic(stage="s", severity="warn", code="a", message="z")
        later = _diagnostic(stage="s", severity="warn", code="b", message="a")

        self.assertLess(self.build_key(earlier), self.build_key(later))

    def test_case_whitespace_and_unicode_are_preserved(self) -> None:
        upper = _diagnostic(stage="s", severity="warn", code="Alpha", message="m")
        lower = _diagnostic(stage="s", severity="warn", code="alpha", message="m")
        padded = _diagnostic(stage="s", severity="warn", code=" alpha", message="m")
        plain = _diagnostic(stage="s", severity="warn", code="cafe", message="m")
        accented = _diagnostic(
            stage="s", severity="warn", code="café", message="m"
        )

        self.assertLess(self.build_key(upper), self.build_key(lower))
        self.assertLess(self.build_key(padded), self.build_key(lower))
        self.assertLess(self.build_key(plain), self.build_key(accented))

    def test_duplicate_diagnostics_remain_present(self) -> None:
        duplicate_a = _diagnostic(code="dup")
        duplicate_b = _diagnostic(code="dup")

        result = self.order([duplicate_a, duplicate_b])

        self.assertEqual(len(result), 2)

    def test_input_diagnostics_and_sequence_are_not_mutated(self) -> None:
        diagnostics = [_diagnostic(code="z"), _diagnostic(code="a")]
        snapshot = list(diagnostics)

        self.order(diagnostics)

        self.assertEqual(diagnostics, snapshot)

    def test_output_is_tuple(self) -> None:
        result = self.order([_diagnostic()])

        self.assertIsInstance(result, tuple)

    def test_list_and_tuple_inputs_are_accepted(self) -> None:
        diagnostics = [_diagnostic(code="z"), _diagnostic(code="a")]

        from_list = self.order(diagnostics)
        from_tuple = self.order(tuple(diagnostics))

        self.assertEqual(from_list, from_tuple)

    def test_strings_and_bytes_are_rejected_as_outer_containers(self) -> None:
        for value in ("not-diagnostics", b"not-diagnostics"):
            with self.subTest(value=value):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ):
                    self.order(value)

    def test_unsupported_item_types_are_rejected(self) -> None:
        with self.assertRaises(self.contract.ReferenceTraversalOutputContractError):
            self.order([object()])

    def test_invalid_participating_fields_are_rejected(self) -> None:
        diagnostic = _diagnostic()
        object.__setattr__(diagnostic, "severity", "")

        with self.assertRaises(self.contract.ReferenceTraversalOutputContractError):
            self.order([diagnostic])

    def test_rejects_non_diagnostic_argument(self) -> None:
        with self.assertRaises(self.contract.ReferenceTraversalOutputContractError):
            self.build_key(object())


class ReferenceTraversalDiagnosticSequencingAfterSortingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_sequence_numbers_correspond_to_sorted_positions(self) -> None:
        caller_diagnostics = [
            _diagnostic(stage="scan", severity="warning", code="third", message="m3"),
            _diagnostic(stage="scan", severity="warning", code="first", message="m1"),
            _diagnostic(stage="scan", severity="warning", code="second", message="m2"),
        ]
        snapshot = list(caller_diagnostics)

        payload = _build_payload(self.contract, diagnostics=caller_diagnostics)

        self.assertEqual(
            [(item["sequence"], item["code"]) for item in payload["diagnostics"]],
            [(0, "first"), (1, "second"), (2, "third")],
        )
        self.assertEqual(caller_diagnostics, snapshot)

    def test_node_and_edge_sequence_behavior_is_unchanged(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(id="node-c"), _node(id="node-a"), _node(id="node-b")],
            edges=[
                _edge(source="node-c", target="node-a"),
                _edge(source="node-a", target="node-b"),
            ],
        )

        self.assertEqual(
            [item["sequence"] for item in payload["nodes"]], [0, 1, 2]
        )
        self.assertEqual(
            [item["sequence"] for item in payload["edges"]], [0, 1]
        )

    def test_payload_shape_remains_unchanged(self) -> None:
        payload = _build_payload(
            self.contract,
            diagnostics=[_diagnostic(code="b"), _diagnostic(code="a")],
        )

        self.assertEqual(
            set(payload["diagnostics"][0]),
            {"sequence", "severity", "code", "message", "stage"},
        )


class ReferenceTraversalDiagnosticPermutationInvarianceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_payload_diagnostic_order_is_permutation_independent(self) -> None:
        import itertools

        diagnostics = (
            _diagnostic(stage=None, severity="error", code="a", message="m1"),
            _diagnostic(stage="scan", severity="error", code="a", message="m2"),
            _diagnostic(stage="scan", severity="warning", code="a", message="m3"),
            _diagnostic(stage="scan", severity="warning", code="b", message="m4"),
            _diagnostic(
                stage="scan", severity="warning", code="b", message="z-message"
            ),
        )

        baseline_payload = _build_payload(self.contract, diagnostics=list(diagnostics))
        expected_order = [
            (item["stage"], item["severity"], item["code"], item["message"])
            for item in baseline_payload["diagnostics"]
        ]
        expected_bytes = dumps_canonical(baseline_payload)

        for count, permutation in enumerate(itertools.permutations(diagnostics)):
            with self.subTest(permutation=count):
                payload = _build_payload(self.contract, diagnostics=list(permutation))

                actual_order = [
                    (item["stage"], item["severity"], item["code"], item["message"])
                    for item in payload["diagnostics"]
                ]
                self.assertEqual(actual_order, expected_order)
                self.assertEqual(
                    [item["sequence"] for item in payload["diagnostics"]],
                    [0, 1, 2, 3, 4],
                )
                self.assertEqual(dumps_canonical(payload), expected_bytes)


class ReferenceTraversalUnresolvedEntryConstantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_accepted_states_are_exactly_missing_and_unresolved(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES,
            (
                self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
                self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES,
            ("missing", "unresolved"),
        )

    def test_accepted_state_collection_is_immutable(self) -> None:
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES, tuple
        )
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES[0] = "x"

    def test_entry_types_are_exactly_node_and_edge(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_NODE, "node"
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_EDGE, "edge"
        )

    def test_type_order_is_node_before_edge(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_ORDER,
            (
                self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_NODE,
                self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_EDGE,
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_ORDER,
            ("node", "edge"),
        )

    def test_type_order_collection_is_immutable(self) -> None:
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_ORDER, tuple
        )
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_ORDER[0] = "x"


class ReferenceTraversalUnresolvedEntryOrderKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_key = (
            self.contract.build_reference_traversal_unresolved_entry_order_key
        )

    def test_missing_node_is_accepted(self) -> None:
        node = _node(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)

        self.assertEqual(self.build_key(node)[0], 0)

    def test_unresolved_node_is_accepted(self) -> None:
        node = _node(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED)

        self.assertEqual(self.build_key(node)[0], 0)

    def test_missing_edge_is_accepted(self) -> None:
        edge = _edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)

        self.assertEqual(self.build_key(edge)[0], 1)

    def test_unresolved_edge_is_accepted(self) -> None:
        edge = _edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED)

        self.assertEqual(self.build_key(edge)[0], 1)

    def test_every_accepted_node_key_sorts_before_every_accepted_edge_key(
        self,
    ) -> None:
        # Deliberately "larger" node evidence and "smaller" edge evidence to
        # prove the node/edge type discriminator dominates nested ordering.
        large_node = _node(
            id="zzzzz",
            document_path="zzzzz.FCStd",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
        )
        small_edge = _edge(
            source="aaaaa",
            target="aaaaa",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
        )

        self.assertLess(self.build_key(large_node), self.build_key(small_edge))

    def test_node_ordering_delegates_to_public_node_key(self) -> None:
        node = _node(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)

        self.assertEqual(
            self.build_key(node),
            (0, self.contract.build_reference_traversal_node_order_key(node)),
        )

    def test_edge_ordering_delegates_to_public_edge_key(self) -> None:
        edge = _edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)

        self.assertEqual(
            self.build_key(edge),
            (1, self.contract.build_reference_traversal_edge_order_key(edge)),
        )

    def test_differing_node_and_edge_key_shapes_do_not_cause_comparison_errors(
        self,
    ) -> None:
        entries = [
            _edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING),
            _node(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED),
            _edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED),
            _node(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING),
        ]

        ordered = sorted(entries, key=self.build_key)

        self.assertIsInstance(ordered[0], self.contract.RawReferenceTraversalNode)
        self.assertIsInstance(ordered[1], self.contract.RawReferenceTraversalNode)
        self.assertIsInstance(ordered[2], self.contract.RawReferenceTraversalEdge)
        self.assertIsInstance(ordered[3], self.contract.RawReferenceTraversalEdge)

    def test_no_path_identifier_label_or_diagnostic_normalization_occurs(
        self,
    ) -> None:
        node = _node(
            id="Node/A",
            document_path="Dir/Sub.FCStd",
            object_name="Body Name",
            label=" Label ",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
        )

        self.assertEqual(
            self.build_key(node),
            (0, self.contract.build_reference_traversal_node_order_key(node)),
        )

    def test_rejects_resolved_skipped_and_failed_node_states(self) -> None:
        for state in (
            self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED,
            self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
        ):
            with self.subTest(state=state):
                node = _node(state=state)
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.build_key(node)
                message = str(ctx.exception)
                self.assertIn("missing", message)
                self.assertIn("unresolved", message)

    def test_rejects_resolved_skipped_and_failed_edge_states(self) -> None:
        for state in (
            self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED,
            self.contract.REFERENCE_TRAVERSAL_STATE_FAILED,
        ):
            with self.subTest(state=state):
                edge = _edge(state=state)
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ) as ctx:
                    self.build_key(edge)
                message = str(ctx.exception)
                self.assertIn("missing", message)
                self.assertIn("unresolved", message)

    def test_rejects_unsupported_objects_mappings_strings_and_none(self) -> None:
        for value in (object(), {"state": "missing"}, "missing", None):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ):
                    self.build_key(value)


class ReferenceTraversalOrderUnresolvedEntriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.order = self.contract.order_reference_traversal_unresolved_entries

    def test_every_node_appears_before_every_edge(self) -> None:
        node_missing = _node(
            id="n1", state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING
        )
        node_unresolved = _node(
            id="n2", state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED
        )
        edge_missing = _edge(
            source="e1", target="e1b", state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING
        )
        edge_unresolved = _edge(
            source="e2",
            target="e2b",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
        )

        result = self.order(
            [edge_unresolved, node_unresolved, edge_missing, node_missing]
        )

        self.assertIsInstance(result[0], self.contract.RawReferenceTraversalNode)
        self.assertIsInstance(result[1], self.contract.RawReferenceTraversalNode)
        self.assertIsInstance(result[2], self.contract.RawReferenceTraversalEdge)
        self.assertIsInstance(result[3], self.contract.RawReferenceTraversalEdge)

    def test_nodes_use_node_total_ordering(self) -> None:
        node_b = _node(
            id="node-b", state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING
        )
        node_a = _node(
            id="node-a", state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING
        )

        result = self.order([node_b, node_a])

        self.assertEqual([node.id for node in result], ["node-a", "node-b"])

    def test_edges_use_edge_total_ordering(self) -> None:
        edge_b = _edge(
            source="b", target="x", state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING
        )
        edge_a = _edge(
            source="a", target="x", state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING
        )

        result = self.order([edge_b, edge_a])

        self.assertEqual([edge.source for edge in result], ["a", "b"])

    def test_duplicates_are_preserved_without_deduplication_or_filtering(
        self,
    ) -> None:
        duplicate_node_a = _node(
            id="dup", state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING
        )
        duplicate_node_b = _node(
            id="dup", state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING
        )
        duplicate_edge_a = _edge(
            source="dup",
            target="dup",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
        )
        duplicate_edge_b = _edge(
            source="dup",
            target="dup",
            state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
        )

        entries = [
            duplicate_node_a,
            duplicate_edge_a,
            duplicate_node_b,
            duplicate_edge_b,
        ]
        result = self.order(entries)

        self.assertEqual(len(result), len(entries))

    def test_input_is_not_mutated(self) -> None:
        entries = [
            _edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING),
            _node(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED),
        ]
        snapshot = list(entries)

        self.order(entries)

        self.assertEqual(entries, snapshot)

    def test_output_is_immutable_tuple(self) -> None:
        result = self.order(
            [_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)]
        )

        self.assertIsInstance(result, tuple)
        with self.assertRaises(TypeError):
            result[0] = _node(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)

    def test_list_and_tuple_input_are_accepted(self) -> None:
        entries = [
            _node(id="a", state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING),
            _edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED),
        ]

        from_list = self.order(entries)
        from_tuple = self.order(tuple(entries))

        self.assertEqual(from_list, from_tuple)

    def test_strings_and_bytes_are_rejected(self) -> None:
        for value in ("not-entries", b"not-entries"):
            with self.subTest(value=value):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ):
                    self.order(value)

    def test_unsupported_item_types_are_rejected(self) -> None:
        with self.assertRaises(self.contract.ReferenceTraversalOutputContractError):
            self.order([object()])

    def test_invalid_states_are_rejected(self) -> None:
        with self.assertRaises(self.contract.ReferenceTraversalOutputContractError):
            self.order(
                [_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED)]
            )

    def test_mixed_unresolved_evidence_order_is_permutation_independent(
        self,
    ) -> None:
        import itertools

        entries = (
            _node(id="node-a", state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING),
            _node(
                id="node-b", state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED
            ),
            _edge(
                source="a",
                target="b",
                state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
            ),
            _edge(
                source="b",
                target="c",
                state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
            ),
        )
        expected = self.order(list(entries))

        for count, permutation in enumerate(itertools.permutations(entries)):
            with self.subTest(permutation=count):
                self.assertEqual(self.order(list(permutation)), expected)


class ReferenceTraversalUnresolvedEntriesRemainHelperOnlyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_payload_builder_does_not_accept_unresolved_entries_argument(
        self,
    ) -> None:
        import inspect

        signature = inspect.signature(
            self.contract.build_reference_traversal_output_payload
        )

        self.assertNotIn("unresolved_entries", signature.parameters)
        self.assertNotIn("unresolvedEntries", signature.parameters)

        with self.assertRaises(TypeError):
            _build_payload(
                self.contract,
                unresolved_entries=[
                    _node(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)
                ],
            )

    def test_top_level_payload_fields_remain_exact(self) -> None:
        payload = _build_payload(self.contract)

        self.assertEqual(
            set(payload),
            {
                "schemaVersion",
                "kind",
                "boundary",
                "operation",
                "status",
                "sourceDocument",
                "nodes",
                "edges",
                "diagnostics",
            },
        )

    def test_no_new_top_level_unresolved_collection_exists(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING)],
            edges=[_edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED)],
        )

        for forbidden_key in ("unresolved", "unresolvedEntries", "unresolved_entries"):
            self.assertNotIn(forbidden_key, payload)

    def test_unresolved_and_missing_nodes_remain_serialized_in_nodes(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(
                    id="missing-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
                ),
                _node(
                    id="unresolved-node",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
                ),
            ],
            edges=[],
        )

        self.assertEqual(
            sorted(node["id"] for node in payload["nodes"]),
            ["missing-node", "unresolved-node"],
        )
        self.assertEqual(payload["edges"], [])

    def test_unresolved_and_missing_edges_remain_serialized_in_edges(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[],
            edges=[
                _edge(
                    source="a",
                    target="b",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
                ),
                _edge(
                    source="c",
                    target="d",
                    state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
                ),
            ],
        )

        self.assertEqual(len(payload["edges"]), 2)
        self.assertEqual(payload["nodes"], [])

    def test_unresolved_state_string_is_not_rejected_as_a_state_value(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED)],
        )

        self.assertEqual(payload["nodes"][0]["state"], "unresolved")

    def test_no_unresolved_entry_dataclass_exists(self) -> None:
        self.assertFalse(
            hasattr(self.contract, "RawReferenceTraversalUnresolvedEntry")
        )

    def test_node_edge_and_diagnostic_dataclass_fields_remain_unchanged(
        self,
    ) -> None:
        node_fields = {
            field.name
            for field in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }
        edge_fields = {
            field.name
            for field in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }
        diagnostic_fields = {
            field.name
            for field in dataclass_fields(
                self.contract.RawReferenceTraversalDiagnostic
            )
        }

        self.assertEqual(
            node_fields,
            {
                "id",
                "kind",
                "state",
                "document_path",
                "object_name",
                "label",
                "diagnostic",
            },
        )
        self.assertEqual(
            edge_fields, {"source", "target", "kind", "state", "diagnostic"}
        )
        self.assertEqual(
            diagnostic_fields, {"severity", "code", "message", "stage"}
        )

    def test_schema_version_remains_1_0(self) -> None:
        payload = _build_payload(self.contract)

        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION, "1.0"
        )


class ReferenceTraversalTotalOrderingContractMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_total_ordering_contract
        )

    def test_metadata_contains_documented_keys(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata),
            {
                "nodeOrderFields",
                "edgeOrderFields",
                "diagnosticOrderFields",
                "optionalStringOrder",
                "unresolvedEntries",
                "sorting",
                "payloadSchemaChanged",
                "performsRealFreecadTraversal",
                "implementsTraversalWriter",
                "implementsRuntimeWiring",
                "engineNormalizationPerformed",
                "pdmBehaviorProduced",
            },
        )

    def test_node_edge_and_diagnostic_order_fields_match_constants(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["nodeOrderFields"],
            list(self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS),
        )
        self.assertEqual(
            metadata["edgeOrderFields"],
            list(self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS),
        )
        self.assertEqual(
            metadata["diagnosticOrderFields"],
            list(self.contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_ORDER_FIELDS),
        )

    def test_optional_string_order_documents_none_first_behavior(self) -> None:
        metadata = self.build_contract()
        description = metadata["optionalStringOrder"].lower()

        self.assertIn("none", description)
        self.assertIn("before", description)

    def test_unresolved_entries_metadata_matches_constants(self) -> None:
        metadata = self.build_contract()
        unresolved = metadata["unresolvedEntries"]

        self.assertEqual(
            unresolved["acceptedStates"],
            list(self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES),
        )
        self.assertEqual(
            unresolved["typeOrder"],
            list(self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_ORDER),
        )
        self.assertEqual(
            unresolved["interpretation"],
            "existing node or edge evidence, not a payload collection",
        )

    def test_sorting_metadata_documents_no_normalization_or_deduplication(
        self,
    ) -> None:
        metadata = self.build_contract()
        sorting = metadata["sorting"]

        self.assertIs(sorting["preservesDuplicateRawEvidence"], True)
        self.assertIs(sorting["normalizationPerformed"], False)
        self.assertIs(sorting["deduplicationPerformed"], False)
        self.assertIs(sorting["filesystemInspected"], False)

    def test_scope_boundary_flags_are_all_false(self) -> None:
        metadata = self.build_contract()

        self.assertIs(metadata["payloadSchemaChanged"], False)
        self.assertIs(metadata["performsRealFreecadTraversal"], False)
        self.assertIs(metadata["implementsTraversalWriter"], False)
        self.assertIs(metadata["implementsRuntimeWiring"], False)
        self.assertIs(metadata["engineNormalizationPerformed"], False)

    def test_pdm_behavior_produced_flags_are_all_false(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["pdmBehaviorProduced"],
            {
                "identity": False,
                "persistence": False,
                "graph": False,
                "whereUsed": False,
            },
        )


class ReferenceTraversalTotalOrderingContractFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_total_ordering_contract
        )

    def test_repeated_calls_return_equal_independent_top_level_objects(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_repeated_calls_return_independent_nested_collections(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertIsNot(first["nodeOrderFields"], second["nodeOrderFields"])
        self.assertIsNot(first["unresolvedEntries"], second["unresolvedEntries"])
        self.assertIsNot(
            first["unresolvedEntries"]["acceptedStates"],
            second["unresolvedEntries"]["acceptedStates"],
        )
        self.assertIsNot(first["sorting"], second["sorting"])
        self.assertIsNot(
            first["pdmBehaviorProduced"], second["pdmBehaviorProduced"]
        )

    def test_mutating_returned_metadata_does_not_leak_to_later_calls(self) -> None:
        first = self.build_contract()

        first["nodeOrderFields"].append("mutated")
        first["unresolvedEntries"]["acceptedStates"].append("mutated")
        first["sorting"]["normalizationPerformed"] = True
        first["pdmBehaviorProduced"]["identity"] = True
        first["injected"] = "mutated"

        second = self.build_contract()

        self.assertEqual(
            second["nodeOrderFields"],
            list(self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS),
        )
        self.assertEqual(
            second["unresolvedEntries"]["acceptedStates"],
            list(self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES),
        )
        self.assertIs(second["sorting"]["normalizationPerformed"], False)
        self.assertIs(second["pdmBehaviorProduced"]["identity"], False)
        self.assertNotIn("injected", second)

    def test_mutating_returned_metadata_does_not_alter_module_constants(self) -> None:
        metadata = self.build_contract()

        metadata["nodeOrderFields"].append("mutated")
        metadata["edgeOrderFields"].append("mutated")
        metadata["diagnosticOrderFields"].append("mutated")
        metadata["unresolvedEntries"]["acceptedStates"].append("mutated")
        metadata["unresolvedEntries"]["typeOrder"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS,
            (
                "documentPath",
                "kind",
                "id",
                "objectName",
                "label",
                "state",
                "diagnostic",
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS,
            ("source", "target", "kind", "state", "diagnostic"),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_ORDER_FIELDS,
            ("stage", "severity", "code", "message"),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES,
            ("missing", "unresolved"),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_ORDER,
            ("node", "edge"),
        )


class ReferenceTraversalTotalOrderingContractCanonicalJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_total_ordering_contract
        )

    def test_metadata_contains_only_json_compatible_values(self) -> None:
        metadata = self.build_contract()

        _assert_only_json_leaf_types(self, metadata)

    def test_metadata_serializes_deterministically(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(dumps_canonical(metadata), dumps_canonical(metadata))

    def test_repeated_fresh_calls_serialize_identically(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(dumps_canonical(first), dumps_canonical(second))


class ReferenceTraversalOrderingExtensionFieldOrderTests(unittest.TestCase):
    """Exact ordering-extension field tuples and their deliberate placement."""

    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_extension_only_node_fields_are_exact(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS,
            ("objectType",),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS, tuple
        )

    def test_extension_only_edge_fields_are_exact(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS,
            ("sourceProperty", "referenceMechanism"),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS, tuple
        )

    def test_extension_fields_are_immutable_tuples(self) -> None:
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS[0] = "x"
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS[0] = "x"

    def test_extension_fields_reuse_existing_provenance_requirement_vocabulary(
        self,
    ) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS,
            (self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE,),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS,
            (
                self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY,
                self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM,
            ),
        )
        self.assertIn(
            self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE,
            self.contract.REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS,
        )
        self.assertIn(
            self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY,
            self.contract.REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS,
        )
        self.assertIn(
            self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM,
            self.contract.REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS,
        )

    def test_extended_node_order_matches_exact_future_order(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS,
            (
                "documentPath",
                "kind",
                "id",
                "objectName",
                "objectType",
                "label",
                "state",
                "diagnostic",
            ),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS, tuple
        )

    def test_extended_edge_order_matches_exact_future_order(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS,
            (
                "source",
                "target",
                "kind",
                "sourceProperty",
                "referenceMechanism",
                "state",
                "diagnostic",
            ),
        )
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS, tuple
        )

    def test_extended_orders_are_immutable_tuples(self) -> None:
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS[0] = "x"
        with self.assertRaises(TypeError):
            self.contract.REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS[0] = "x"

    def test_removing_extension_fields_from_extended_node_order_reproduces_phase1_order(
        self,
    ) -> None:
        extension_fields = set(
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS
        )
        reduced = tuple(
            field
            for field in self.contract.REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS
            if field not in extension_fields
        )

        self.assertEqual(
            reduced, self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS
        )

    def test_removing_extension_fields_from_extended_edge_order_reproduces_phase1_order(
        self,
    ) -> None:
        extension_fields = set(
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS
        )
        reduced = tuple(
            field
            for field in self.contract.REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS
            if field not in extension_fields
        )

        self.assertEqual(
            reduced, self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS
        )

    def test_object_type_insertion_position_is_after_object_name_before_label(
        self,
    ) -> None:
        order = self.contract.REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS
        object_name_index = order.index("objectName")
        object_type_index = order.index("objectType")
        label_index = order.index("label")

        self.assertEqual(object_type_index, object_name_index + 1)
        self.assertEqual(label_index, object_type_index + 1)

    def test_source_property_insertion_position_is_after_kind_before_reference_mechanism(
        self,
    ) -> None:
        order = self.contract.REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS
        kind_index = order.index("kind")
        source_property_index = order.index("sourceProperty")
        reference_mechanism_index = order.index("referenceMechanism")

        self.assertEqual(source_property_index, kind_index + 1)
        self.assertEqual(reference_mechanism_index, source_property_index + 1)

    def test_reference_mechanism_insertion_position_is_after_source_property_before_state(
        self,
    ) -> None:
        order = self.contract.REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS
        source_property_index = order.index("sourceProperty")
        reference_mechanism_index = order.index("referenceMechanism")
        state_index = order.index("state")

        self.assertEqual(reference_mechanism_index, source_property_index + 1)
        self.assertEqual(state_index, reference_mechanism_index + 1)

    def test_insertion_positions_are_not_a_trailing_append(self) -> None:
        node_order = self.contract.REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS
        edge_order = self.contract.REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS

        self.assertNotEqual(node_order[-1], "objectType")
        self.assertNotEqual(edge_order[-1], "sourceProperty")
        self.assertNotEqual(edge_order[-1], "referenceMechanism")
        self.assertNotEqual(
            node_order,
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS
            + self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS,
        )
        self.assertNotEqual(
            edge_order,
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS
            + self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS,
        )


class ReferenceTraversalOrderingExtensionContractMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_ordering_extension_contract
        )

    def test_helper_takes_no_required_arguments(self) -> None:
        import inspect

        signature = inspect.signature(self.build_contract)

        self.assertEqual(len(signature.parameters), 0)

    def test_helper_returns_a_plain_dict(self) -> None:
        metadata = self.build_contract()

        self.assertIsInstance(metadata, dict)

    def test_metadata_top_level_keys_are_exact(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata),
            {
                "phase1Order",
                "extensionOnlyFields",
                "deliberateFutureOrder",
                "activation",
                "compatibility",
                "performedBehavior",
            },
        )

    def test_phase1_order_section_matches_current_constants(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata["phase1Order"]), {"nodeFields", "edgeFields"}
        )
        self.assertEqual(
            metadata["phase1Order"]["nodeFields"],
            list(self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS),
        )
        self.assertEqual(
            metadata["phase1Order"]["edgeFields"],
            list(self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS),
        )

    def test_extension_only_fields_section_matches_constants(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata["extensionOnlyFields"]), {"nodeFields", "edgeFields"}
        )
        self.assertEqual(
            metadata["extensionOnlyFields"]["nodeFields"],
            list(self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS),
        )
        self.assertEqual(
            metadata["extensionOnlyFields"]["edgeFields"],
            list(self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS),
        )

    def test_deliberate_future_order_section_keys_and_field_orders(self) -> None:
        metadata = self.build_contract()
        section = metadata["deliberateFutureOrder"]

        self.assertEqual(
            set(section),
            {
                "nodeFields",
                "edgeFields",
                "preservesPhase1RelativeOrder",
                "insertionPositions",
                "futureOptionalStringOrder",
                "unknownFutureFieldPolicy",
                "incidentalOrderIsNotContractOrder",
            },
        )
        self.assertEqual(
            section["nodeFields"],
            list(self.contract.REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS),
        )
        self.assertEqual(
            section["edgeFields"],
            list(self.contract.REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS),
        )
        self.assertIs(section["preservesPhase1RelativeOrder"], True)

    def test_insertion_positions_section_describes_all_three_fields(self) -> None:
        metadata = self.build_contract()
        positions = metadata["deliberateFutureOrder"]["insertionPositions"]

        self.assertEqual(
            set(positions),
            {"objectType", "sourceProperty", "referenceMechanism"},
        )
        self.assertEqual(
            positions["objectType"], "after objectName and before label"
        )
        self.assertEqual(
            positions["sourceProperty"],
            "after kind and before referenceMechanism",
        )
        self.assertEqual(
            positions["referenceMechanism"],
            "after sourceProperty and before state",
        )

    def test_future_optional_string_order_documents_none_first_behavior(
        self,
    ) -> None:
        metadata = self.build_contract()
        description = metadata["deliberateFutureOrder"][
            "futureOptionalStringOrder"
        ].lower()

        self.assertIn("none", description)
        self.assertIn("before", description)

    def test_unknown_future_field_policy_requires_explicit_reviewed_placement(
        self,
    ) -> None:
        metadata = self.build_contract()
        policy = metadata["deliberateFutureOrder"]["unknownFutureFieldPolicy"]

        self.assertIn("explicit", policy.lower())
        self.assertIn("reviewed", policy.lower())

    def test_incidental_order_is_not_contract_order_lists_expected_categories(
        self,
    ) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["deliberateFutureOrder"]["incidentalOrderIsNotContractOrder"],
            [
                "dataclass declaration order",
                "mapping insertion order",
                "FreeCAD enumeration order",
                "runtime discovery order",
            ],
        )

    def test_activation_section_boundaries_are_all_inactive(self) -> None:
        metadata = self.build_contract()
        activation = metadata["activation"]

        self.assertEqual(
            set(activation),
            {
                "definedFutureOrderIsActive",
                "currentRawSchemaOrPayloadFieldsChanged",
                "provenanceFieldsActive",
                "provenanceFieldsSerialized",
                "currentNodeOrEdgeOrderKeyHelpersApplyExtendedOrder",
                "requiredApproval",
            },
        )
        self.assertIs(activation["definedFutureOrderIsActive"], False)
        self.assertIs(activation["currentRawSchemaOrPayloadFieldsChanged"], False)
        self.assertIs(activation["provenanceFieldsActive"], False)
        self.assertIs(activation["provenanceFieldsSerialized"], False)
        self.assertIs(
            activation["currentNodeOrEdgeOrderKeyHelpersApplyExtendedOrder"], False
        )
        self.assertIn("approval", activation["requiredApproval"].lower())

    def test_compatibility_section_matches_schema_and_semantic_edge_identity(
        self,
    ) -> None:
        metadata = self.build_contract()
        compatibility = metadata["compatibility"]

        self.assertEqual(
            set(compatibility),
            {
                "schemaVersion",
                "semanticEdgeIdentityComponents",
                "semanticEdgeIdentityRemainsThreeComponent",
                "semanticEdgeIdentityAndDeduplicationProvenanceInsensitive",
                "payloadBuilderBehaviorChanged",
                "serializationBehaviorChanged",
            },
        )
        self.assertEqual(compatibility["schemaVersion"], "1.0")
        self.assertEqual(
            compatibility["schemaVersion"],
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
        )
        self.assertEqual(
            compatibility["semanticEdgeIdentityComponents"],
            list(self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS),
        )
        self.assertEqual(len(compatibility["semanticEdgeIdentityComponents"]), 3)
        self.assertIs(
            compatibility["semanticEdgeIdentityRemainsThreeComponent"], True
        )
        self.assertIs(
            compatibility[
                "semanticEdgeIdentityAndDeduplicationProvenanceInsensitive"
            ],
            True,
        )
        self.assertIs(compatibility["payloadBuilderBehaviorChanged"], False)
        self.assertIs(compatibility["serializationBehaviorChanged"], False)

    def test_performed_behavior_section_all_flags_false(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["performedBehavior"],
            {
                "realFreecadTraversal": False,
                "normalization": False,
                "filesystemInspection": False,
                "traversalWriter": False,
                "runtimeWiring": False,
                "engineNormalization": False,
                "pdmBehavior": False,
            },
        )


class ReferenceTraversalOrderingExtensionFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_ordering_extension_contract
        )

    def test_repeated_calls_return_equal_independent_top_level_objects(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_repeated_calls_return_independent_nested_dicts_and_lists(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        for key in (
            "phase1Order",
            "extensionOnlyFields",
            "deliberateFutureOrder",
            "activation",
            "compatibility",
            "performedBehavior",
        ):
            self.assertIsNot(first[key], second[key])

        self.assertIsNot(
            first["phase1Order"]["nodeFields"], second["phase1Order"]["nodeFields"]
        )
        self.assertIsNot(
            first["phase1Order"]["edgeFields"], second["phase1Order"]["edgeFields"]
        )
        self.assertIsNot(
            first["extensionOnlyFields"]["nodeFields"],
            second["extensionOnlyFields"]["nodeFields"],
        )
        self.assertIsNot(
            first["deliberateFutureOrder"]["nodeFields"],
            second["deliberateFutureOrder"]["nodeFields"],
        )
        self.assertIsNot(
            first["deliberateFutureOrder"]["insertionPositions"],
            second["deliberateFutureOrder"]["insertionPositions"],
        )
        self.assertIsNot(
            first["deliberateFutureOrder"]["incidentalOrderIsNotContractOrder"],
            second["deliberateFutureOrder"]["incidentalOrderIsNotContractOrder"],
        )
        self.assertIsNot(
            first["compatibility"]["semanticEdgeIdentityComponents"],
            second["compatibility"]["semanticEdgeIdentityComponents"],
        )

    def test_mutating_returned_metadata_does_not_leak_to_later_calls(self) -> None:
        first = self.build_contract()

        first["phase1Order"]["nodeFields"].append("mutated")
        first["extensionOnlyFields"]["edgeFields"].append("mutated")
        first["deliberateFutureOrder"]["nodeFields"].append("mutated")
        first["deliberateFutureOrder"]["insertionPositions"]["objectType"] = "mutated"
        first["deliberateFutureOrder"][
            "incidentalOrderIsNotContractOrder"
        ].append("mutated")
        first["activation"]["definedFutureOrderIsActive"] = True
        first["compatibility"]["schemaVersion"] = "9.9"
        first["performedBehavior"]["realFreecadTraversal"] = True
        first["injected"] = "mutated"

        second = self.build_contract()

        self.assertEqual(
            second["phase1Order"]["nodeFields"],
            list(self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS),
        )
        self.assertEqual(
            second["extensionOnlyFields"]["edgeFields"],
            list(self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS),
        )
        self.assertEqual(
            second["deliberateFutureOrder"]["nodeFields"],
            list(self.contract.REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS),
        )
        self.assertEqual(
            second["deliberateFutureOrder"]["insertionPositions"]["objectType"],
            "after objectName and before label",
        )
        self.assertNotIn(
            "mutated",
            second["deliberateFutureOrder"]["incidentalOrderIsNotContractOrder"],
        )
        self.assertIs(second["activation"]["definedFutureOrderIsActive"], False)
        self.assertEqual(second["compatibility"]["schemaVersion"], "1.0")
        self.assertIs(second["performedBehavior"]["realFreecadTraversal"], False)
        self.assertNotIn("injected", second)

    def test_mutating_returned_metadata_does_not_alter_module_constants(self) -> None:
        metadata = self.build_contract()

        metadata["phase1Order"]["nodeFields"].append("mutated")
        metadata["phase1Order"]["edgeFields"].append("mutated")
        metadata["extensionOnlyFields"]["nodeFields"].append("mutated")
        metadata["extensionOnlyFields"]["edgeFields"].append("mutated")
        metadata["deliberateFutureOrder"]["nodeFields"].append("mutated")
        metadata["deliberateFutureOrder"]["edgeFields"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS,
            ("documentPath", "kind", "id", "objectName", "label", "state", "diagnostic"),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS,
            ("source", "target", "kind", "state", "diagnostic"),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_EXTENSION_FIELDS,
            ("objectType",),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_EXTENSION_FIELDS,
            ("sourceProperty", "referenceMechanism"),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS,
            (
                "documentPath",
                "kind",
                "id",
                "objectName",
                "objectType",
                "label",
                "state",
                "diagnostic",
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS,
            (
                "source",
                "target",
                "kind",
                "sourceProperty",
                "referenceMechanism",
                "state",
                "diagnostic",
            ),
        )


class ReferenceTraversalOrderingExtensionCanonicalJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_ordering_extension_contract
        )

    def test_metadata_contains_only_json_compatible_values(self) -> None:
        metadata = self.build_contract()

        _assert_only_json_leaf_types(self, metadata)

    def test_metadata_serializes_deterministically(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(dumps_canonical(metadata), dumps_canonical(metadata))

    def test_repeated_fresh_calls_serialize_identically(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(dumps_canonical(first), dumps_canonical(second))

    def test_equivalent_result_after_earlier_object_mutated_still_serializes_originally(
        self,
    ) -> None:
        first = self.build_contract()
        original_bytes = dumps_canonical(first)

        first["phase1Order"]["nodeFields"].append("mutated")
        first["deliberateFutureOrder"]["insertionPositions"]["objectType"] = "x"

        second = self.build_contract()

        self.assertEqual(dumps_canonical(second), original_bytes)

    def test_dumps_canonical_does_not_mutate_metadata(self) -> None:
        import copy

        metadata = self.build_contract()
        snapshot = copy.deepcopy(metadata)

        dumps_canonical(metadata)

        self.assertEqual(metadata, snapshot)


class ReferenceTraversalOrderingExtensionImportSafetyTests(unittest.TestCase):
    def test_import_and_call_ordering_extension_helper_does_not_require_freecad(
        self,
    ) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()
            metadata = module.build_reference_traversal_ordering_extension_contract()

        self.assertIsInstance(metadata, dict)
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ReferenceTraversalOrderingExtensionSideEffectSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_ordering_extension_contract
        )

    def test_metadata_does_not_touch_filesystem_or_open_files(self) -> None:
        with mock.patch(
            "builtins.open",
            side_effect=AssertionError("open must not be called"),
        ), mock.patch(
            "os.listdir", side_effect=AssertionError("listdir must not be called")
        ), mock.patch(
            "os.path.exists",
            side_effect=AssertionError("os.path.exists must not be called"),
        ):
            metadata = self.build_contract()

        self.assertIsInstance(metadata, dict)

    def test_metadata_unaffected_by_time_pid_cwd_env_or_random_identifiers(
        self,
    ) -> None:
        import uuid as uuid_module

        with mock.patch("time.time", return_value=999999999.0), mock.patch(
            "os.getpid", return_value=424242
        ), mock.patch("os.getcwd", return_value="/tmp/patched-cwd"), mock.patch.dict(
            os.environ, {"PARAMETRON_FREECAD_ORDERING_EXTENSION_TEST": "patched"}
        ), mock.patch.object(
            uuid_module, "uuid4", return_value=uuid_module.UUID(int=0)
        ):
            patched = self.build_contract()

        unpatched = self.build_contract()

        self.assertEqual(dumps_canonical(patched), dumps_canonical(unpatched))


class ReferenceTraversalOrderingExtensionCompatibilityTests(unittest.TestCase):
    """Prove the inactive future order does not alter current runtime behavior."""

    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_ordering_extension_contract
        )

    def test_schema_version_remains_1_0(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION, "1.0"
        )

    def test_raw_node_dataclass_fields_remain_unchanged(self) -> None:
        node_fields = {
            field.name
            for field in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }

        self.assertEqual(
            node_fields,
            {
                "id",
                "kind",
                "state",
                "document_path",
                "object_name",
                "label",
                "diagnostic",
            },
        )
        self.assertNotIn("objectType", node_fields)
        self.assertNotIn("object_type", node_fields)

    def test_raw_edge_dataclass_fields_remain_unchanged(self) -> None:
        edge_fields = {
            field.name
            for field in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }

        self.assertEqual(
            edge_fields, {"source", "target", "kind", "state", "diagnostic"}
        )
        self.assertNotIn("sourceProperty", edge_fields)
        self.assertNotIn("source_property", edge_fields)
        self.assertNotIn("referenceMechanism", edge_fields)
        self.assertNotIn("reference_mechanism", edge_fields)

    def test_representative_payload_shape_unchanged_and_omits_inactive_fields(
        self,
    ) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(
                    id="assembly",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                ),
                _node(
                    id="body",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
                    document_path="assembly.FCStd",
                    object_name="Body",
                ),
            ],
            edges=[
                _edge(
                    source="assembly",
                    target="body",
                    kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                ),
            ],
        )

        self.assertEqual(
            set(payload),
            {
                "schemaVersion",
                "kind",
                "boundary",
                "operation",
                "status",
                "sourceDocument",
                "nodes",
                "edges",
                "diagnostics",
            },
        )
        for node in payload["nodes"]:
            self.assertEqual(
                set(node),
                {
                    "sequence",
                    "id",
                    "kind",
                    "state",
                    "documentPath",
                    "objectName",
                    "label",
                    "diagnostic",
                },
            )
            self.assertNotIn("objectType", node)
        for edge in payload["edges"]:
            self.assertEqual(
                set(edge),
                {"sequence", "source", "target", "kind", "state", "diagnostic"},
            )
            self.assertNotIn("sourceProperty", edge)
            self.assertNotIn("referenceMechanism", edge)
        for diagnostic in payload["diagnostics"]:
            self.assertEqual(
                set(diagnostic),
                {"sequence", "severity", "code", "message", "stage"},
            )

    def test_current_node_order_key_ignores_extended_order_metadata(self) -> None:
        node = _node()
        key = self.contract.build_reference_traversal_node_order_key(node)

        self.assertEqual(
            len(key), len(self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS)
        )
        self.assertNotEqual(
            len(key),
            len(self.contract.REFERENCE_TRAVERSAL_EXTENDED_NODE_ORDER_FIELDS),
        )

    def test_current_edge_order_key_ignores_extended_order_metadata(self) -> None:
        edge = _edge()
        key = self.contract.build_reference_traversal_edge_order_key(edge)

        self.assertEqual(
            len(key), len(self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS)
        )
        self.assertNotEqual(
            len(key),
            len(self.contract.REFERENCE_TRAVERSAL_EXTENDED_EDGE_ORDER_FIELDS),
        )

    def test_node_ordering_still_follows_phase1_document_path_priority(self) -> None:
        nodes = [
            _node(id="node-b", document_path="b.FCStd"),
            _node(id="node-a", document_path="a.FCStd"),
        ]

        ordered = self.contract.order_reference_traversal_nodes(nodes)

        self.assertEqual([node.id for node in ordered], ["node-a", "node-b"])

    def test_edge_ordering_still_follows_phase1_source_then_target_priority(
        self,
    ) -> None:
        edges = [
            _edge(source="node-b", target="node-a"),
            _edge(source="node-a", target="node-b"),
        ]

        ordered = self.contract.order_reference_traversal_edges(edges)

        self.assertEqual(
            [(edge.source, edge.target) for edge in ordered],
            [("node-a", "node-b"), ("node-b", "node-a")],
        )

    def test_duplicate_raw_evidence_and_sequence_assignment_unaffected(self) -> None:
        duplicate_node = _node(id="dup", document_path="dup.FCStd")
        payload = _build_payload(
            self.contract,
            nodes=[duplicate_node, duplicate_node],
            edges=[_edge()],
        )

        self.assertEqual(len(payload["nodes"]), 2)
        self.assertEqual(
            [node["sequence"] for node in payload["nodes"]], [0, 1]
        )

    def test_diagnostic_and_unresolved_entry_ordering_unaffected(self) -> None:
        diagnostics = [
            _diagnostic(code="second", stage="b"),
            _diagnostic(code="first", stage="a"),
        ]
        ordered_diagnostics = self.contract.order_reference_traversal_diagnostics(
            diagnostics
        )
        self.assertEqual(
            [diagnostic.code for diagnostic in ordered_diagnostics],
            ["first", "second"],
        )

        unresolved_entries = [
            _edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING),
            _node(
                id="unresolved-node",
                state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
            ),
        ]
        ordered_unresolved = self.contract.order_reference_traversal_unresolved_entries(
            unresolved_entries
        )
        self.assertEqual(
            [
                self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_NODE
                if isinstance(entry, self.contract.RawReferenceTraversalNode)
                else self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_EDGE
                for entry in ordered_unresolved
            ],
            [
                self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_NODE,
                self.contract.REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_TYPE_EDGE,
            ],
        )

    def test_serializer_output_matches_payload_builder_and_omits_provenance_fields(
        self,
    ) -> None:
        kwargs = {
            "boundary": self.contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
            "operation": self.contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
            "status": self.contract.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
            "source_document": "assembly.FCStd",
            "nodes": [
                _node(id="assembly", kind="document"),
                _node(id="body", kind="object", document_path="assembly.FCStd", object_name="Body"),
            ],
            "edges": [_edge(source="assembly", target="body", kind="contains")],
            "diagnostics": [_diagnostic()],
        }
        expected = dumps_canonical(
            self.contract.build_reference_traversal_output_payload(**kwargs)
        ).encode("utf-8")

        actual = self.contract.serialize_reference_traversal_output(**kwargs)

        self.assertEqual(actual, expected)
        text = actual.decode("utf-8")
        self.assertNotIn("objectType", text)
        self.assertNotIn("sourceProperty", text)
        self.assertNotIn("referenceMechanism", text)
        self.assertFalse(actual.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r\n", actual)
        self.assertTrue(actual.endswith(b"\n"))
        self.assertFalse(actual.endswith(b"\n\n"))

    def test_equivalent_reordered_inputs_serialize_to_equal_bytes(self) -> None:
        nodes = [
            _node(id="assembly", kind="document"),
            _node(id="body", kind="object", document_path="assembly.FCStd", object_name="Body"),
        ]
        edges = [_edge(source="assembly", target="body", kind="contains")]
        kwargs = {
            "boundary": self.contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
            "operation": self.contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
            "status": self.contract.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
            "source_document": "assembly.FCStd",
            "diagnostics": [],
        }

        forward = self.contract.serialize_reference_traversal_output(
            nodes=nodes, edges=edges, **kwargs
        )
        reversed_result = self.contract.serialize_reference_traversal_output(
            nodes=list(reversed(nodes)), edges=list(edges), **kwargs
        )

        self.assertEqual(forward, reversed_result)

    def test_semantic_edge_identity_remains_three_component_and_provenance_insensitive(
        self,
    ) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["compatibility"]["semanticEdgeIdentityComponents"],
            list(self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS),
        )
        self.assertEqual(
            len(self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS), 3
        )

        source_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
            document_path="assembly.FCStd",
        )
        target_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            document_path="assembly.FCStd",
            object_name="Body",
        )
        identity_key = self.contract.build_reference_traversal_semantic_edge_identity_key(
            source_node_key=source_key,
            target_node_key=target_key,
            kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
        )

        deduplicated = self.contract.deduplicate_reference_traversal_semantic_edge_identity_keys(
            [identity_key, identity_key]
        )

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(len(identity_key), 3)

    def test_ordering_extension_metadata_activation_flags_confirm_inactivity(
        self,
    ) -> None:
        metadata = self.build_contract()

        self.assertIs(metadata["activation"]["definedFutureOrderIsActive"], False)
        self.assertIs(
            metadata["activation"][
                "currentNodeOrEdgeOrderKeyHelpersApplyExtendedOrder"
            ],
            False,
        )
        self.assertIs(metadata["activation"]["provenanceFieldsSerialized"], False)
        self.assertIs(metadata["compatibility"]["payloadBuilderBehaviorChanged"], False)
        self.assertIs(
            metadata["compatibility"]["serializationBehaviorChanged"], False
        )


class ReferenceTraversalProvenanceRequirementConstantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_provenance_requirement_constant_values_are_stable(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE,
            "objectType",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY,
            "sourceProperty",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM,
            "referenceMechanism",
        )

    def test_defined_provenance_requirements_are_deterministic_ordered_tuple(
        self,
    ) -> None:
        requirements = self.contract.REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS

        self.assertIsInstance(requirements, tuple)
        self.assertEqual(
            requirements,
            (
                self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE,
                self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_SOURCE_PROPERTY,
                self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_REFERENCE_MECHANISM,
            ),
        )
        self.assertEqual(
            requirements, ("objectType", "sourceProperty", "referenceMechanism")
        )

    def test_defined_provenance_requirements_contains_no_duplicates(self) -> None:
        requirements = self.contract.REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS

        self.assertEqual(len(requirements), len(set(requirements)))

    def test_defined_provenance_requirements_is_immutable_tuple(self) -> None:
        with self.assertRaises(AttributeError):
            self.contract.REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS.append(
                "mutated"
            )

    def test_repeated_access_does_not_expose_mutable_shared_list_state(self) -> None:
        first = list(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS
        )
        first.append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS,
            ("objectType", "sourceProperty", "referenceMechanism"),
        )

    def test_proposed_provenance_locations_is_a_mapping_proxy(self) -> None:
        self.assertIsInstance(
            self.contract.REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS,
            types.MappingProxyType,
        )

    def test_proposed_provenance_locations_values_are_exact(self) -> None:
        locations = self.contract.REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS

        self.assertEqual(
            dict(locations),
            {
                "objectType": "nodes[].objectType",
                "sourceProperty": "edges[].sourceProperty",
                "referenceMechanism": "edges[].referenceMechanism",
            },
        )

    def test_proposed_provenance_locations_cannot_be_mutated_by_callers(self) -> None:
        locations = self.contract.REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS

        with self.assertRaises(TypeError):
            locations["objectType"] = "mutated"
        with self.assertRaises(TypeError):
            locations["injected"] = "mutated"


class ReferenceTraversalDiscoverySemanticsContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_discovery_semantics_contract
        )

    def test_metadata_is_plain_json_compatible_dict(self) -> None:
        metadata = self.build_contract()

        self.assertIsInstance(metadata, dict)
        _assert_only_json_leaf_types(self, metadata)

    def test_metadata_contains_documented_top_level_keys(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata),
            {
                "buildsOn",
                "definedReferenceScopes",
                "discoverySemantics",
                "ambiguousOrUnsupportedMechanismPolicy",
                "runtimeStatePolicy",
                "diagnosticPolicy",
                "futureRuntimeMechanismPolicy",
                "performsRealFreecadDiscovery",
                "enumeratesSupportedRuntimeMechanisms",
                "classifiesRuntimeValues",
                "payloadSchemaChanged",
            },
        )

    def test_repeated_calls_are_value_equivalent_but_independent(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["discoverySemantics"], second["discoverySemantics"])

    def test_repeated_calls_serialize_to_identical_canonical_bytes(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(dumps_canonical(first), dumps_canonical(second))

    def test_mutating_one_result_does_not_leak_to_a_later_call(self) -> None:
        first = self.build_contract()

        first["definedReferenceScopes"].append("mutated")
        first["discoverySemantics"][
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL
        ]["requirements"].append("mutated")
        first["injected"] = "mutated"

        second = self.build_contract()

        self.assertNotIn("mutated", second["definedReferenceScopes"])
        self.assertNotIn(
            "mutated",
            second["discoverySemantics"][
                self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL
            ]["requirements"],
        )
        self.assertNotIn("injected", second)

    def test_mutation_does_not_leak_to_module_level_constants(self) -> None:
        metadata = self.build_contract()

        metadata["definedReferenceScopes"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES,
            ("document_internal", "external_document", "external_file"),
        )

    def test_metadata_reuses_existing_defined_reference_scopes(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["definedReferenceScopes"],
            list(self.contract.REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES),
        )
        self.assertEqual(
            set(metadata["discoverySemantics"]),
            {
                self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL,
                self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT,
                self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE,
            },
        )

    def test_metadata_reuses_existing_edge_and_node_kind_vocabulary(self) -> None:
        metadata = self.build_contract()
        semantics = metadata["discoverySemantics"]

        internal = semantics[
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL
        ]
        external_document = semantics[
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT
        ]
        external_file = semantics[
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE
        ]

        self.assertEqual(
            internal["edgeKind"],
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
        )
        self.assertEqual(
            set(internal["sourceNodeKinds"]),
            {
                self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            },
        )
        self.assertEqual(
            set(internal["targetNodeKinds"]),
            {
                self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            },
        )
        self.assertEqual(
            external_document["edgeKind"],
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
        )
        self.assertEqual(
            external_document["targetNodeKinds"],
            [self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT],
        )
        self.assertEqual(
            external_file["edgeKind"],
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
        )
        self.assertEqual(
            external_file["targetNodeKinds"],
            [self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE],
        )

    def test_no_competing_scope_or_edge_kind_vocabulary_is_introduced(self) -> None:
        metadata = self.build_contract()
        encoded = dumps_canonical(metadata)

        for expected_scope in self.contract.REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES:
            self.assertIn(expected_scope, encoded)
        for expected_edge_kind in (
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_DOCUMENT_REFERENCE,
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
        ):
            self.assertIn(expected_edge_kind, encoded)

        scope_values = set(self.contract.REFERENCE_TRAVERSAL_DEFINED_REFERENCE_SCOPES)
        for scope_key in metadata["discoverySemantics"]:
            self.assertIn(scope_key, scope_values)

    def test_document_internal_semantics_are_structurally_represented(self) -> None:
        internal = self.build_contract()["discoverySemantics"][
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_DOCUMENT_INTERNAL
        ]

        requirements = " ".join(internal["requirements"]).lower()
        self.assertIn("one freecad document", requirements)
        self.assertIn("document-local", requirements)

        does_not_imply = " ".join(internal["doesNotImply"]).lower()
        self.assertIn("another freecad document", does_not_imply)
        self.assertIn("external file", does_not_imply)

        not_inferred_from = " ".join(internal["notInferredFrom"]).lower()
        self.assertIn("equal raw node ids", not_inferred_from)
        self.assertIn("missing path evidence", not_inferred_from)

    def test_external_document_semantics_are_structurally_represented(self) -> None:
        external_document = self.build_contract()["discoverySemantics"][
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_DOCUMENT
        ]

        self.assertEqual(
            external_document["targetPathEvidenceField"], "nodes[].documentPath"
        )

        requirements = " ".join(external_document["requirements"]).lower()
        self.assertIn("distinct freecad document", requirements)
        self.assertIn("supported runtime relationship evidence", requirements)
        self.assertIn("documentpath", requirements)

        not_inferred_from = {
            item.lower() for item in external_document["notInferredFrom"]
        }
        self.assertEqual(
            not_inferred_from,
            {
                "filename extension",
                "path suffix",
                "filesystem existence",
                "string shape",
            },
        )

    def test_external_file_semantics_are_structurally_represented(self) -> None:
        external_file = self.build_contract()["discoverySemantics"][
            self.contract.REFERENCE_TRAVERSAL_REFERENCE_SCOPE_EXTERNAL_FILE
        ]

        self.assertEqual(
            external_file["targetPathEvidenceField"], "nodes[].documentPath"
        )

        requirements = " ".join(external_file["requirements"]).lower()
        self.assertIn("non-freecad file", requirements)
        self.assertIn("supported runtime relationship evidence", requirements)
        self.assertIn("documentpath", requirements)

        not_inferred_from = {
            item.lower() for item in external_file["notInferredFrom"]
        }
        self.assertEqual(
            not_inferred_from,
            {
                "filename extension",
                "path suffix",
                "filesystem existence",
                "string shape",
            },
        )

    def test_unsupported_and_ambiguous_mechanisms_must_not_be_guessed_into_a_scope(
        self,
    ) -> None:
        metadata = self.build_contract()
        policy = metadata["ambiguousOrUnsupportedMechanismPolicy"].lower()

        self.assertIn("unsupported", policy)
        self.assertIn("ambiguous", policy)
        self.assertIn("must not be guessed", policy)

    def test_helper_explicitly_disclaims_real_discovery_and_runtime_classification(
        self,
    ) -> None:
        metadata = self.build_contract()

        self.assertIs(metadata["performsRealFreecadDiscovery"], False)
        self.assertIs(metadata["enumeratesSupportedRuntimeMechanisms"], False)
        self.assertIs(metadata["classifiesRuntimeValues"], False)
        self.assertIs(metadata["payloadSchemaChanged"], False)

    def test_helper_explicitly_disclaims_runtime_state_and_diagnostic_creation(
        self,
    ) -> None:
        metadata = self.build_contract()

        runtime_state_policy = metadata["runtimeStatePolicy"].lower()
        diagnostic_policy = metadata["diagnosticPolicy"].lower()

        self.assertIn("not", runtime_state_policy)
        self.assertIn("state", runtime_state_policy)
        self.assertIn("not", diagnostic_policy)
        self.assertIn("diagnostic", diagnostic_policy)

    def test_future_runtime_mechanism_enumeration_is_deferred(self) -> None:
        metadata = self.build_contract()

        future_policy = metadata["futureRuntimeMechanismPolicy"].lower()
        self.assertIn("later", future_policy)
        self.assertIn("enumerat", future_policy)

    def test_discovery_contract_module_imports_without_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()
            module.build_reference_traversal_discovery_semantics_contract()

        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ReferenceTraversalObjectPropertyProvenanceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_object_property_provenance_contract
        )

    def test_metadata_is_plain_json_compatible_dict(self) -> None:
        metadata = self.build_contract()

        self.assertIsInstance(metadata, dict)
        _assert_only_json_leaf_types(self, metadata)

    def test_metadata_contains_documented_top_level_keys(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata),
            {
                "requirementNames",
                "requirements",
                "distinctEvidenceConcepts",
                "mustNotOverloadExistingFields",
                "ownership",
                "compatibility",
                "missingValueEncodingSelected",
                "normalizationPerformed",
                "proposedLocationsAreActiveSerializedFields",
            },
        )

    def test_repeated_calls_are_value_equivalent_but_independent(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["requirements"], second["requirements"])
        self.assertIsNot(first["ownership"], second["ownership"])

    def test_repeated_calls_serialize_to_identical_canonical_bytes(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(dumps_canonical(first), dumps_canonical(second))

    def test_mutating_one_result_does_not_leak_to_a_later_call(self) -> None:
        first = self.build_contract()

        first["requirementNames"].append("mutated")
        first["requirements"][
            self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE
        ]["semantics"] = "mutated"
        first["mustNotOverloadExistingFields"].append("mutated")
        first["injected"] = "mutated"

        second = self.build_contract()

        self.assertEqual(
            second["requirementNames"],
            list(self.contract.REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS),
        )
        self.assertNotEqual(
            second["requirements"][
                self.contract.REFERENCE_TRAVERSAL_PROVENANCE_REQUIREMENT_OBJECT_TYPE
            ]["semantics"],
            "mutated",
        )
        self.assertNotIn("mutated", second["mustNotOverloadExistingFields"])
        self.assertNotIn("injected", second)

    def test_mutation_does_not_leak_to_module_level_constants(self) -> None:
        metadata = self.build_contract()

        metadata["requirementNames"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS,
            ("objectType", "sourceProperty", "referenceMechanism"),
        )

    def test_requirement_names_match_defined_provenance_requirements(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["requirementNames"],
            list(self.contract.REFERENCE_TRAVERSAL_DEFINED_PROVENANCE_REQUIREMENTS),
        )
        self.assertEqual(
            metadata["requirementNames"],
            ["objectType", "sourceProperty", "referenceMechanism"],
        )

    def test_helper_independently_defines_all_three_requirement_concepts(
        self,
    ) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata["requirements"]),
            {"objectType", "sourceProperty", "referenceMechanism"},
        )

    def test_object_type_is_associated_with_object_node_raw_evidence(self) -> None:
        metadata = self.build_contract()
        object_type = metadata["requirements"]["objectType"]

        self.assertEqual(object_type["logicalAssociation"], "object node")
        self.assertEqual(
            object_type["proposedRawEvidenceLocation"], "nodes[].objectType"
        )
        self.assertIs(object_type["serializedInCurrentNodeDataclass"], False)

    def test_source_property_is_associated_with_an_observed_edge_relationship(
        self,
    ) -> None:
        metadata = self.build_contract()
        source_property = metadata["requirements"]["sourceProperty"]

        self.assertEqual(source_property["logicalAssociation"], "edge observation")
        self.assertEqual(
            source_property["proposedRawEvidenceLocation"],
            "edges[].sourceProperty",
        )
        self.assertIs(source_property["serializedInCurrentEdgeDataclass"], False)

    def test_reference_mechanism_is_associated_with_the_exposing_runtime_mechanism(
        self,
    ) -> None:
        metadata = self.build_contract()
        reference_mechanism = metadata["requirements"]["referenceMechanism"]

        self.assertEqual(
            reference_mechanism["logicalAssociation"], "edge observation"
        )
        self.assertEqual(
            reference_mechanism["proposedRawEvidenceLocation"],
            "edges[].referenceMechanism",
        )
        self.assertIs(
            reference_mechanism["serializedInCurrentEdgeDataclass"], False
        )
        mechanism_semantics = reference_mechanism["semantics"].lower()
        self.assertIn("mechanism", mechanism_semantics)
        self.assertIn("api", mechanism_semantics)

    def test_source_property_and_reference_mechanism_are_represented_as_distinct(
        self,
    ) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["requirements"]["sourceProperty"]["separateFrom"],
            ["source object identity", "edge kind"],
        )
        self.assertEqual(
            metadata["requirements"]["referenceMechanism"]["separateFrom"],
            ["sourceProperty"],
        )

    def test_none_of_the_requirements_is_treated_as_identity_kind_target_or_diagnostic(
        self,
    ) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata["distinctEvidenceConcepts"]),
            {
                "source object identity",
                "sourceProperty",
                "referenceMechanism",
                "edge kind",
                "target evidence",
                "resolution state",
                "diagnostic evidence",
            },
        )

    def test_proposed_future_locations_are_exact(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            {
                requirement: data["proposedRawEvidenceLocation"]
                for requirement, data in metadata["requirements"].items()
            },
            {
                "objectType": "nodes[].objectType",
                "sourceProperty": "edges[].sourceProperty",
                "referenceMechanism": "edges[].referenceMechanism",
            },
        )
        self.assertEqual(
            dict(self.contract.REFERENCE_TRAVERSAL_PROPOSED_PROVENANCE_LOCATIONS),
            {
                "objectType": "nodes[].objectType",
                "sourceProperty": "edges[].sourceProperty",
                "referenceMechanism": "edges[].referenceMechanism",
            },
        )

    def test_proposed_locations_are_marked_inactive_in_schema_1_0(self) -> None:
        metadata = self.build_contract()
        compatibility = metadata["compatibility"]

        self.assertEqual(compatibility["currentSchemaVersion"], "1.0")
        self.assertEqual(
            compatibility["currentSchemaVersion"],
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
        )
        self.assertIs(compatibility["presentInCurrentSchema"], False)
        self.assertIs(
            metadata["proposedLocationsAreActiveSerializedFields"], False
        )
        self.assertIs(
            metadata["requirements"]["objectType"][
                "serializedInCurrentNodeDataclass"
            ],
            False,
        )
        for requirement in ("sourceProperty", "referenceMechanism"):
            self.assertIs(
                metadata["requirements"][requirement][
                    "serializedInCurrentEdgeDataclass"
                ],
                False,
            )

    def test_ownership_identifies_raw_adapter_observed_evidence(self) -> None:
        metadata = self.build_contract()
        ownership = metadata["ownership"]

        self.assertIs(ownership["rawAdapterObservedProvenanceRequirements"], True)
        self.assertIs(ownership["engineNormalizedRecordFields"], False)
        self.assertIs(ownership["pdmIdentityOrStorageDefined"], False)

    def test_existing_fields_must_not_be_overloaded(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata["mustNotOverloadExistingFields"]),
            {
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
            },
        )

    def test_deferred_behavior_flags_are_all_false(self) -> None:
        metadata = self.build_contract()
        compatibility = metadata["compatibility"]

        self.assertIs(compatibility["presentInCurrentSchema"], False)
        self.assertIs(compatibility["serializedNodeOrEdgeIdsDefined"], False)
        self.assertIs(compatibility["participatesInSemanticIdentity"], False)
        self.assertIs(compatibility["participatesInDeduplication"], False)
        self.assertIs(compatibility["participatesInOrdering"], False)
        self.assertIs(compatibility["payloadSchemaChanged"], False)
        self.assertIs(metadata["missingValueEncodingSelected"], False)
        self.assertIs(metadata["normalizationPerformed"], False)

    def test_future_serialized_output_decision_is_required_and_described(
        self,
    ) -> None:
        metadata = self.build_contract()
        decision_text = metadata["compatibility"][
            "futureSerializedOutputDecisionRequired"
        ].lower()

        self.assertIn("explicit", decision_text)
        self.assertIn("compatible or versioned", decision_text)

    def test_provenance_contract_module_imports_without_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()
            module.build_reference_traversal_object_property_provenance_contract()

        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ReferenceTraversalProvenanceCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_schema_version_remains_1_0(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION, "1.0"
        )

    def test_object_type_is_not_an_active_node_dataclass_field(self) -> None:
        node_fields = {
            field.name
            for field in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }

        self.assertNotIn("objectType", node_fields)
        self.assertNotIn("object_type", node_fields)
        self.assertEqual(
            node_fields,
            {
                "id",
                "kind",
                "state",
                "document_path",
                "object_name",
                "label",
                "diagnostic",
            },
        )

    def test_source_property_and_reference_mechanism_are_not_active_edge_dataclass_fields(
        self,
    ) -> None:
        edge_fields = {
            field.name
            for field in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }

        self.assertNotIn("sourceProperty", edge_fields)
        self.assertNotIn("source_property", edge_fields)
        self.assertNotIn("referenceMechanism", edge_fields)
        self.assertNotIn("reference_mechanism", edge_fields)
        self.assertEqual(
            edge_fields, {"source", "target", "kind", "state", "diagnostic"}
        )

    def test_representative_payload_emits_no_provenance_fields(self) -> None:
        payload = _build_payload(
            self.contract,
            nodes=[
                _node(
                    id="assembly",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                ),
                _node(
                    id="body",
                    kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
                ),
            ],
            edges=[
                _edge(
                    source="assembly",
                    target="body",
                    kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                ),
            ],
        )

        for node in payload["nodes"]:
            self.assertNotIn("objectType", node)
        for edge in payload["edges"]:
            self.assertNotIn("sourceProperty", edge)
            self.assertNotIn("referenceMechanism", edge)

    def test_canonical_payload_bytes_remain_stable_for_a_representative_payload(
        self,
    ) -> None:
        first = _build_payload(self.contract)
        second = _build_payload(self.contract)

        self.assertEqual(dumps_canonical(first), dumps_canonical(second))
        self.assertEqual(
            set(first),
            {
                "schemaVersion",
                "kind",
                "boundary",
                "operation",
                "status",
                "sourceDocument",
                "nodes",
                "edges",
                "diagnostics",
            },
        )

    def test_semantic_edge_identity_key_builder_rejects_provenance_keyword_arguments(
        self,
    ) -> None:
        source_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
            document_path="assembly.FCStd",
        )
        target_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            document_path="assembly.FCStd",
            object_name="Body",
        )

        with self.assertRaises(TypeError):
            self.contract.build_reference_traversal_semantic_edge_identity_key(
                source_node_key=source_key,
                target_node_key=target_key,
                kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                sourceProperty="Placement",
            )
        with self.assertRaises(TypeError):
            self.contract.build_reference_traversal_semantic_edge_identity_key(
                source_node_key=source_key,
                target_node_key=target_key,
                kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                referenceMechanism="expression_engine",
            )
        with self.assertRaises(TypeError):
            self.contract.build_reference_traversal_semantic_edge_identity_key(
                source_node_key=source_key,
                target_node_key=target_key,
                kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
                objectType="PartDesign::Body",
            )

    def test_semantic_edge_identity_remains_three_component(self) -> None:
        source_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
            document_path="assembly.FCStd",
        )
        target_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            document_path="assembly.FCStd",
            object_name="Body",
        )

        identity_key = self.contract.build_reference_traversal_semantic_edge_identity_key(
            source_node_key=source_key,
            target_node_key=target_key,
            kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
        )

        self.assertEqual(len(identity_key), 3)
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_FIELDS,
            (
                "sourceSemanticNodeIdentityKey",
                "targetSemanticNodeIdentityKey",
                "kind",
            ),
        )

    def test_semantic_edge_identity_contract_still_marks_provenance_sensitive_identity_deferred(
        self,
    ) -> None:
        metadata = (
            self.contract.build_reference_traversal_semantic_edge_identity_contract()
        )
        provenance = metadata["propertyOrReferenceMechanismSensitiveIdentity"]

        self.assertIs(provenance["supported"], False)
        self.assertIs(provenance["deferred"], True)
        self.assertIs(
            provenance["helperClaimsPropertySensitiveDeduplication"], False
        )

    def test_deduplication_helper_does_not_accept_a_provenance_argument(self) -> None:
        import inspect

        signature = inspect.signature(
            self.contract.deduplicate_reference_traversal_semantic_edge_identity_keys
        )

        for forbidden_param in (
            "object_type",
            "objectType",
            "source_property",
            "sourceProperty",
            "reference_mechanism",
            "referenceMechanism",
        ):
            self.assertNotIn(forbidden_param, signature.parameters)

    def test_node_edge_and_diagnostic_ordering_helpers_remain_unaffected(self) -> None:
        import inspect

        for helper_name in (
            "build_reference_traversal_node_order_key",
            "build_reference_traversal_edge_order_key",
            "build_reference_traversal_diagnostic_order_key",
        ):
            signature = inspect.signature(getattr(self.contract, helper_name))
            for forbidden_param in (
                "object_type",
                "source_property",
                "reference_mechanism",
            ):
                self.assertNotIn(forbidden_param, signature.parameters)

    def test_import_and_call_new_metadata_helpers_do_not_require_freecad(
        self,
    ) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()
            module.build_reference_traversal_discovery_semantics_contract()
            module.build_reference_traversal_object_property_provenance_contract()

        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ReferenceTraversalRuntimeStateSemanticsContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_runtime_state_semantics_contract
        )

    # -- public API -----------------------------------------------------

    def test_helper_is_publicly_exported_and_callable(self) -> None:
        self.assertIn(
            "build_reference_traversal_runtime_state_semantics_contract",
            self.contract.__all__,
        )
        self.assertTrue(callable(self.build_contract))

    def test_export_does_not_leak_a_private_helper_name(self) -> None:
        self.assertFalse(
            hasattr(
                self.contract,
                "_build_reference_traversal_runtime_state_semantics_contract",
            )
        )
        for name in self.contract.__all__:
            self.assertFalse(name.startswith("_"), name)

    def test_task_introduces_no_new_public_state_constants(self) -> None:
        existing_state_constants = {
            "REFERENCE_TRAVERSAL_STATE_RESOLVED",
            "REFERENCE_TRAVERSAL_STATE_MISSING",
            "REFERENCE_TRAVERSAL_STATE_UNRESOLVED",
            "REFERENCE_TRAVERSAL_STATE_SKIPPED",
            "REFERENCE_TRAVERSAL_STATE_FAILED",
            "REFERENCE_TRAVERSAL_DEFINED_STATES",
            "REFERENCE_TRAVERSAL_NODE_FIELD_STATE",
            "REFERENCE_TRAVERSAL_EDGE_FIELD_STATE",
            "REFERENCE_TRAVERSAL_UNRESOLVED_ENTRY_STATE_VALUES",
            "build_reference_traversal_discovery_semantics_contract",
        }
        state_or_semantics_exports = {
            name
            for name in self.contract.__all__
            if "state" in name.lower() or "semantics" in name.lower()
        }
        self.assertEqual(
            state_or_semantics_exports,
            existing_state_constants
            | {
                "build_reference_traversal_runtime_state_semantics_contract",
                "build_reference_traversal_aggregate_status_semantics_contract",
            },
        )

    # -- helper signature / metadata-only boundary -----------------------

    def test_helper_signature_requires_no_arguments(self) -> None:
        import inspect

        signature = inspect.signature(self.build_contract)
        self.assertEqual(list(signature.parameters), [])

    def test_helper_returns_plain_dict_with_no_arguments(self) -> None:
        metadata = self.build_contract()

        self.assertIsInstance(metadata, dict)

    # -- state vocabulary and order --------------------------------------

    def test_state_order_matches_defined_states_exactly(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["stateOrder"],
            list(self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES),
        )
        self.assertEqual(
            metadata["stateOrder"],
            ["resolved", "missing", "unresolved", "skipped", "failed"],
        )

    def test_all_five_states_represented_exactly_once(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(len(metadata["stateOrder"]), 5)
        self.assertEqual(len(set(metadata["stateOrder"])), 5)
        self.assertEqual(
            set(metadata["stateSemantics"]),
            set(self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES),
        )
        self.assertEqual(len(metadata["stateSemantics"]), 5)

    def test_no_competing_state_vocabulary_is_introduced(self) -> None:
        metadata = self.build_contract()
        encoded = dumps_canonical(metadata)

        for state in self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES:
            self.assertIn(state, encoded)
        self.assertEqual(
            set(metadata["stateSemantics"]),
            set(self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES),
        )

    def test_metadata_contains_documented_top_level_keys(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata),
            {
                "stateOrder",
                "itemStateFields",
                "stateSemantics",
                "topLevelStatusBoundary",
                "helperBehavior",
            },
        )

    def test_item_state_fields_reference_node_and_edge_state_paths(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["itemStateFields"], ["nodes[].state", "edges[].state"]
        )

    def test_state_semantics_key_sets_are_exact_per_state(self) -> None:
        semantics = self.build_contract()["stateSemantics"]

        common_keys = {
            "meaning",
            "targetBindingSucceeded",
            "absenceEstablished",
            "operationAttempted",
            "ambiguousOrInsufficientEvidence",
            "deliberateNonAttempt",
            "runtimeDiagnosticEvidenceExpected",
        }

        self.assertEqual(set(semantics["resolved"]), common_keys | {"doesNotMean"})
        self.assertEqual(set(semantics["missing"]), common_keys | {"doesNotMean"})
        self.assertEqual(
            set(semantics["unresolved"]),
            common_keys | {"mustNotGuess", "doesNotMean"},
        )
        self.assertEqual(
            set(semantics["skipped"]),
            common_keys
            | {
                "evidenceRequirement",
                "mustNotHide",
                "genericFallbackAllowed",
                "futureCaseMappingsSelected",
            },
        )
        self.assertEqual(
            set(semantics["failed"]),
            common_keys | {"evidenceRequirement", "doesNotMean"},
        )

    # -- resolved semantics -----------------------------------------------

    def test_resolved_semantics_distinguish_target_binding_from_verification_and_storage(
        self,
    ) -> None:
        resolved = self.build_contract()["stateSemantics"][
            self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED
        ]

        self.assertIs(resolved["targetBindingSucceeded"], True)
        self.assertIs(resolved["absenceEstablished"], False)
        self.assertIs(resolved["operationAttempted"], True)
        self.assertIs(resolved["ambiguousOrInsufficientEvidence"], False)
        self.assertIs(resolved["deliberateNonAttempt"], False)

        does_not_mean = " ".join(resolved["doesNotMean"]).lower()
        self.assertIn("engine verification", does_not_mean)
        self.assertIn("pdm record", does_not_mean)
        self.assertIn("durable identity", does_not_mean)
        self.assertIn("filesystem-containment", does_not_mean)
        self.assertIn("recursively traversed", does_not_mean)

    # -- missing semantics --------------------------------------------------

    def test_missing_semantics_distinguish_established_absence_from_ambiguity(
        self,
    ) -> None:
        missing = self.build_contract()["stateSemantics"][
            self.contract.REFERENCE_TRAVERSAL_STATE_MISSING
        ]

        self.assertIs(missing["absenceEstablished"], True)
        self.assertIs(missing["targetBindingSucceeded"], False)
        self.assertIs(missing["ambiguousOrInsufficientEvidence"], False)
        self.assertIs(missing["deliberateNonAttempt"], False)

        does_not_mean = " ".join(missing["doesNotMean"]).lower()
        self.assertIn("incomplete", does_not_mean)
        self.assertIn("ambiguous", does_not_mean)
        self.assertIn("unsupported", does_not_mean)
        self.assertIn("exception", does_not_mean)
        self.assertIn("top-level traversal failure", does_not_mean)

    # -- unresolved semantics -----------------------------------------------

    def test_unresolved_semantics_require_ambiguous_or_insufficient_evidence(
        self,
    ) -> None:
        unresolved = self.build_contract()["stateSemantics"][
            self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED
        ]

        self.assertIs(unresolved["ambiguousOrInsufficientEvidence"], True)
        self.assertIs(unresolved["targetBindingSucceeded"], False)
        self.assertIs(unresolved["absenceEstablished"], False)
        self.assertIs(unresolved["deliberateNonAttempt"], False)

        must_not_guess = {item.lower() for item in unresolved["mustNotGuess"]}
        self.assertEqual(
            must_not_guess,
            {
                "target",
                "reference scope",
                "document kind",
                "file kind",
                "normalized identity",
            },
        )

        does_not_mean = " ".join(unresolved["doesNotMean"]).lower()
        self.assertIn("absent", does_not_mean)
        self.assertIn("exception", does_not_mean)
        self.assertIn("intentionally not attempted", does_not_mean)

    # -- skipped semantics --------------------------------------------------

    def test_skipped_semantics_require_deliberate_non_attempt(self) -> None:
        skipped = self.build_contract()["stateSemantics"][
            self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED
        ]

        self.assertIs(skipped["deliberateNonAttempt"], True)
        self.assertIs(skipped["operationAttempted"], False)
        self.assertIs(skipped["absenceEstablished"], False)
        self.assertIs(skipped["ambiguousOrInsufficientEvidence"], False)
        self.assertIs(skipped["runtimeDiagnosticEvidenceExpected"], True)
        self.assertIs(skipped["genericFallbackAllowed"], False)
        self.assertIs(skipped["futureCaseMappingsSelected"], False)

        evidence_requirement = skipped["evidenceRequirement"].lower()
        self.assertIn("explainable reason", evidence_requirement)

        must_not_hide = " ".join(skipped["mustNotHide"]).lower()
        self.assertIn("ambiguity", must_not_hide)
        self.assertIn("unresolved", must_not_hide)
        self.assertIn("absence", must_not_hide)
        self.assertIn("missing", must_not_hide)
        self.assertIn("attempted operation", must_not_hide)

    def test_skipped_does_not_map_to_specific_future_scenarios(self) -> None:
        skipped = self.build_contract()["stateSemantics"][
            self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED
        ]
        encoded = dumps_canonical(skipped).lower()

        for future_scenario in (
            "cycle",
            "visited",
            "unsupported_mechanism",
            "user scope",
        ):
            self.assertNotIn(future_scenario, encoded)

    # -- failed semantics -----------------------------------------------------

    def test_failed_semantics_require_attempted_operation_failure(self) -> None:
        failed = self.build_contract()["stateSemantics"][
            self.contract.REFERENCE_TRAVERSAL_STATE_FAILED
        ]

        self.assertIs(failed["operationAttempted"], True)
        self.assertIs(failed["targetBindingSucceeded"], False)
        self.assertIs(failed["absenceEstablished"], False)
        self.assertIs(failed["ambiguousOrInsufficientEvidence"], False)
        self.assertIs(failed["deliberateNonAttempt"], False)
        self.assertIs(failed["runtimeDiagnosticEvidenceExpected"], True)

        evidence_requirement = failed["evidenceRequirement"].lower()
        self.assertIn("explainable diagnostic evidence", evidence_requirement)

        does_not_mean = " ".join(failed["doesNotMean"]).lower()
        self.assertIn("established absent", does_not_mean)
        self.assertIn("insufficient or ambiguous", does_not_mean)
        self.assertIn("intentionally not attempted", does_not_mean)
        self.assertIn("top-level traversal failure", does_not_mean)

    def test_failed_helper_itself_creates_no_diagnostics(self) -> None:
        metadata = self.build_contract()

        self.assertIs(metadata["helperBehavior"]["createsDiagnostics"], False)

    # -- cross-state distinctions -------------------------------------------

    def test_cross_state_distinctions(self) -> None:
        metadata = self.build_contract()
        semantics = metadata["stateSemantics"]

        with self.subTest("missing_vs_unresolved"):
            self.assertNotEqual(
                (
                    semantics["missing"]["absenceEstablished"],
                    semantics["missing"]["ambiguousOrInsufficientEvidence"],
                ),
                (
                    semantics["unresolved"]["absenceEstablished"],
                    semantics["unresolved"]["ambiguousOrInsufficientEvidence"],
                ),
            )

        with self.subTest("skipped_vs_failed"):
            self.assertNotEqual(
                (
                    semantics["skipped"]["deliberateNonAttempt"],
                    semantics["skipped"]["operationAttempted"],
                ),
                (
                    semantics["failed"]["deliberateNonAttempt"],
                    semantics["failed"]["operationAttempted"],
                ),
            )

        with self.subTest("resolved_vs_verified"):
            self.assertIn(
                "engine verification",
                " ".join(semantics["resolved"]["doesNotMean"]).lower(),
            )

        with self.subTest("item_failed_vs_top_level_failed"):
            self.assertIs(
                metadata["topLevelStatusBoundary"][
                    "failedItemAutomaticallyMakesTraversalFailed"
                ],
                False,
            )
            self.assertIn(
                "top-level traversal failure",
                " ".join(semantics["failed"]["doesNotMean"]).lower(),
            )

    # -- item-state versus aggregate-status boundary -------------------------

    def test_top_level_status_boundary_now_defines_aggregation_semantics(self) -> None:
        boundary = self.build_contract()["topLevelStatusBoundary"]

        self.assertEqual(
            set(boundary),
            {
                "field",
                "itemStatesDeriveStatus",
                "partialVersusFailedAggregationDefined",
                "failedItemAutomaticallyMakesTraversalFailed",
                "requiredEvidenceCompletenessThresholdsDefined",
                "malformedRequestFailureBehaviorChanged",
            },
        )
        self.assertEqual(boundary["field"], self.contract.REFERENCE_TRAVERSAL_FIELD_STATUS)
        self.assertIs(boundary["itemStatesDeriveStatus"], False)
        self.assertIs(boundary["partialVersusFailedAggregationDefined"], True)
        self.assertIs(boundary["failedItemAutomaticallyMakesTraversalFailed"], False)
        self.assertIs(boundary["requiredEvidenceCompletenessThresholdsDefined"], True)
        self.assertIs(boundary["malformedRequestFailureBehaviorChanged"], False)

    def test_completeness_thresholds_are_semantic_not_numeric(self) -> None:
        boundary = self.build_contract()["topLevelStatusBoundary"]
        self.assertIs(boundary["requiredEvidenceCompletenessThresholdsDefined"], True)

        aggregate_contract = (
            self.contract.build_reference_traversal_aggregate_status_semantics_contract()
        )
        completeness = aggregate_contract["completenessCriteria"]

        self.assertIs(completeness["semantic"], True)
        self.assertIs(completeness["percentageOrNumericThresholdUsed"], False)
        self.assertNotIn("percentage", " ".join(completeness["basis"]).lower())
        self.assertNotIn("quota", " ".join(completeness["basis"]).lower())
        self.assertNotIn("count", " ".join(completeness["basis"]).lower())

    # -- metadata-only exclusions --------------------------------------------

    def test_helper_behavior_discloses_metadata_only_exclusions(self) -> None:
        behavior = self.build_contract()["helperBehavior"]

        self.assertEqual(
            set(behavior),
            {
                "performsRealFreecadDiscoveryOrClassification",
                "enumeratesSupportedFreecadMechanisms",
                "createsDiagnostics",
                "payloadSchemaChanged",
                "serializesOutput",
                "engineNormalizationPerformed",
                "pdmBehaviorPerformed",
            },
        )
        self.assertIs(behavior["performsRealFreecadDiscoveryOrClassification"], False)
        self.assertIs(behavior["enumeratesSupportedFreecadMechanisms"], False)
        self.assertIs(behavior["createsDiagnostics"], False)
        self.assertIs(behavior["payloadSchemaChanged"], False)
        self.assertIs(behavior["serializesOutput"], False)
        self.assertIs(behavior["engineNormalizationPerformed"], False)
        self.assertIs(behavior["pdmBehaviorPerformed"], False)

    # -- canonical JSON -------------------------------------------------------

    def test_metadata_is_plain_json_compatible_dict(self) -> None:
        metadata = self.build_contract()

        self.assertIsInstance(metadata, dict)
        _assert_only_json_leaf_types(self, metadata)

    def test_repeated_calls_serialize_to_identical_canonical_bytes(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(dumps_canonical(first), dumps_canonical(second))

    def test_dumps_canonical_does_not_mutate_metadata(self) -> None:
        import copy

        metadata = self.build_contract()
        snapshot = copy.deepcopy(metadata)

        dumps_canonical(metadata)

        self.assertEqual(metadata, snapshot)

    # -- fresh nested structures ----------------------------------------------

    def test_repeated_calls_are_value_equivalent_but_independent(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["stateOrder"], second["stateOrder"])
        self.assertIsNot(first["stateSemantics"], second["stateSemantics"])
        self.assertIsNot(
            first["stateSemantics"]["resolved"], second["stateSemantics"]["resolved"]
        )
        self.assertIsNot(
            first["stateSemantics"]["resolved"]["doesNotMean"],
            second["stateSemantics"]["resolved"]["doesNotMean"],
        )
        self.assertIsNot(
            first["topLevelStatusBoundary"], second["topLevelStatusBoundary"]
        )
        self.assertIsNot(first["helperBehavior"], second["helperBehavior"])

    # -- mutation isolation -----------------------------------------------------

    def test_deep_mutation_does_not_leak_to_a_later_call(self) -> None:
        first = self.build_contract()

        first["stateOrder"].append("mutated")
        first["stateSemantics"]["resolved"]["doesNotMean"].append("mutated")
        first["stateSemantics"]["skipped"]["mustNotHide"].append("mutated")
        first["topLevelStatusBoundary"]["itemStatesDeriveStatus"] = True
        first["helperBehavior"]["createsDiagnostics"] = True
        first["injected"] = "mutated"

        second = self.build_contract()

        self.assertNotIn("mutated", second["stateOrder"])
        self.assertNotIn(
            "mutated", second["stateSemantics"]["resolved"]["doesNotMean"]
        )
        self.assertNotIn(
            "mutated", second["stateSemantics"]["skipped"]["mustNotHide"]
        )
        self.assertIs(
            second["topLevelStatusBoundary"]["itemStatesDeriveStatus"], False
        )
        self.assertIs(second["helperBehavior"]["createsDiagnostics"], False)
        self.assertNotIn("injected", second)

    def test_mutation_does_not_leak_to_module_level_constants(self) -> None:
        metadata = self.build_contract()

        metadata["stateOrder"].append("mutated")
        metadata["stateSemantics"]["resolved"]["doesNotMean"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES,
            ("resolved", "missing", "unresolved", "skipped", "failed"),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED, "resolved"
        )
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATE_MISSING, "missing")
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED, "unresolved"
        )
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED, "skipped")
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATE_FAILED, "failed")

    # -- import safety ----------------------------------------------------------

    def test_import_and_call_do_not_require_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()
            module.build_reference_traversal_runtime_state_semantics_contract()

        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ReferenceTraversalAggregateStatusSemanticsContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_aggregate_status_semantics_contract
        )

    # -- public API -----------------------------------------------------

    def test_helper_is_publicly_exported_and_callable(self) -> None:
        self.assertIn(
            "build_reference_traversal_aggregate_status_semantics_contract",
            self.contract.__all__,
        )
        self.assertTrue(callable(self.build_contract))

    def test_export_does_not_leak_a_private_helper_name(self) -> None:
        self.assertFalse(
            hasattr(
                self.contract,
                "_build_reference_traversal_aggregate_status_semantics_contract",
            )
        )
        for name in self.contract.__all__:
            self.assertFalse(name.startswith("_"), name)

    def test_no_new_status_constants_or_values_introduced(self) -> None:
        status_exports = {
            name
            for name in self.contract.__all__
            if name.startswith("REFERENCE_TRAVERSAL_STATUS")
        }
        self.assertEqual(
            status_exports,
            {
                "REFERENCE_TRAVERSAL_STATUS_SUCCEEDED",
                "REFERENCE_TRAVERSAL_STATUS_PARTIAL",
                "REFERENCE_TRAVERSAL_STATUS_FAILED",
            },
        )

        metadata = self.build_contract()
        self.assertEqual(
            set(metadata["statusSemantics"]),
            {
                self.contract.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
                self.contract.REFERENCE_TRAVERSAL_STATUS_PARTIAL,
                self.contract.REFERENCE_TRAVERSAL_STATUS_FAILED,
            },
        )
        self.assertEqual(len(metadata["statusSemantics"]), 3)

    def test_status_order_matches_authoritative_order_exactly(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["statusOrder"],
            [
                self.contract.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
                self.contract.REFERENCE_TRAVERSAL_STATUS_PARTIAL,
                self.contract.REFERENCE_TRAVERSAL_STATUS_FAILED,
            ],
        )
        self.assertEqual(metadata["statusOrder"], ["succeeded", "partial", "failed"])

    # -- helper signature / metadata-only boundary -----------------------

    def test_helper_signature_requires_no_arguments(self) -> None:
        import inspect

        signature = inspect.signature(self.build_contract)
        self.assertEqual(list(signature.parameters), [])

    def test_helper_returns_plain_dict_with_no_arguments(self) -> None:
        metadata = self.build_contract()

        self.assertIsInstance(metadata, dict)

    def test_helper_behavior_discloses_metadata_only_exclusions(self) -> None:
        behavior = self.build_contract()["helperBehavior"]

        self.assertEqual(
            set(behavior),
            {
                "metadataOnly",
                "performsRealFreecadTraversal",
                "derivesStatusFromRuntimeValues",
                "loadsRequests",
                "createsDiagnostics",
                "writesFiles",
                "implementsRuntimeClassificationOrWiring",
                "payloadSchemaChanged",
                "payloadBuilderBehaviorChanged",
                "engineVerificationOrNormalizationPerformed",
                "pdmBehaviorPerformed",
            },
        )
        self.assertIs(behavior["metadataOnly"], True)
        self.assertIs(behavior["performsRealFreecadTraversal"], False)
        self.assertIs(behavior["derivesStatusFromRuntimeValues"], False)
        self.assertIs(behavior["loadsRequests"], False)
        self.assertIs(behavior["createsDiagnostics"], False)
        self.assertIs(behavior["writesFiles"], False)
        self.assertIs(behavior["implementsRuntimeClassificationOrWiring"], False)
        self.assertIs(behavior["payloadSchemaChanged"], False)
        self.assertIs(behavior["payloadBuilderBehaviorChanged"], False)
        self.assertIs(behavior["engineVerificationOrNormalizationPerformed"], False)
        self.assertIs(behavior["pdmBehaviorPerformed"], False)

    # -- exact metadata structure -----------------------------------------

    def test_metadata_contains_documented_top_level_keys(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata),
            {
                "statusOrder",
                "statusSemantics",
                "aggregateDecisionRules",
                "completenessCriteria",
                "usableRetainedEvidence",
                "dimensionSeparation",
                "helperBehavior",
            },
        )

    def test_status_semantics_key_sets_are_exact_per_status(self) -> None:
        semantics = self.build_contract()["statusSemantics"]

        self.assertEqual(
            set(semantics["succeeded"]),
            {
                "meaning",
                "requirements",
                "validItemOutcomesThatDoNotAutomaticallyReduceStatus",
                "skippedItemBoundary",
                "emptyGraphMaySucceed",
                "emptyGraphBoundary",
                "mustNotBeSelectedWhen",
                "doesNotImply",
            },
        )
        self.assertEqual(
            set(semantics["partial"]),
            {
                "meaning",
                "requirements",
                "failedItemBoundary",
                "notSelectedMerelyBecause",
                "excludedFailures",
                "diagnosticEvidenceAloneIsUsableGraphEvidence",
                "retainedEvidenceMayBeGuessedOrRewritten",
                "retainedEvidenceMayBeTreatedAsComplete",
            },
        )
        self.assertEqual(
            set(semantics["failed"]),
            {
                "meaning",
                "categories",
                "notSelectedMerelyBecause",
                "decisionBasis",
                "notWorstItemStateAggregation",
            },
        )

    def test_aggregate_decision_rules_key_set_is_exact(self) -> None:
        rules = self.build_contract()["aggregateDecisionRules"]

        self.assertEqual(
            set(rules),
            {
                "itemStatesDeriveStatus",
                "severityMaximumOverItemStates",
                "nonReducingItemStates",
                "nonReducingSkippedStateRequiresContractPermission",
                "failedItemWithOtherTrustworthyEvidenceMayBePartial",
                "noTrustworthyGraphEvidenceProducesFailed",
                "unusableResultProducesFailed",
                "preEvidenceBoundaryFailureProducesFailed",
                "completeRequiredScopeProcessingProducesSucceeded",
                "partialRequiresUsableRetainedGraphEvidence",
                "partialRequiresExplicitIncompleteness",
                "diagnosticPresenceOrCountDeterminesStatus",
                "nodeOrEdgeCountDeterminesStatus",
            },
        )

    def test_completeness_criteria_key_set_is_exact(self) -> None:
        completeness = self.build_contract()["completenessCriteria"]

        self.assertEqual(
            set(completeness), {"semantic", "percentageOrNumericThresholdUsed", "basis"}
        )

    def test_usable_retained_evidence_key_set_is_exact(self) -> None:
        usable_evidence = self.build_contract()["usableRetainedEvidence"]

        self.assertEqual(
            set(usable_evidence),
            {
                "requiresTrustworthyNonDiagnosticGraphEvidence",
                "examples",
                "diagnosticEvidenceAloneIsSufficient",
                "mustRemainIndependentlyReliable",
            },
        )

    def test_dimension_separation_key_set_is_exact(self) -> None:
        dimensions = self.build_contract()["dimensionSeparation"]

        self.assertEqual(
            set(dimensions),
            {
                "itemLevelStateSeparateFromTopLevelStatus",
                "failedItemAutomaticallyMakesTraversalFailed",
                "emptyGraphAutomaticallyMakesTraversalFailed",
            },
        )
        self.assertIs(dimensions["itemLevelStateSeparateFromTopLevelStatus"], True)
        self.assertIs(dimensions["failedItemAutomaticallyMakesTraversalFailed"], False)
        self.assertIs(dimensions["emptyGraphAutomaticallyMakesTraversalFailed"], False)

    # -- succeeded semantics ------------------------------------------------

    def test_succeeded_requires_core_conditions(self) -> None:
        succeeded = self.build_contract()["statusSemantics"]["succeeded"]
        requirements = " ".join(succeeded["requirements"]).lower()

        self.assertIn("request validation succeeded", requirements)
        self.assertIn("opened sufficiently", requirements)
        self.assertIn("required", requirements)
        self.assertIn("completed", requirements)
        self.assertIn("reliable", requirements)

    def test_succeeded_does_not_require_every_item_resolved(self) -> None:
        succeeded = self.build_contract()["statusSemantics"]["succeeded"]

        self.assertEqual(
            set(succeeded["validItemOutcomesThatDoNotAutomaticallyReduceStatus"]),
            {
                self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
                self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
                self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED,
            },
        )
        self.assertIn(
            "explicitly permitted",
            succeeded["skippedItemBoundary"].lower(),
        )

    def test_succeeded_empty_graph_may_succeed(self) -> None:
        succeeded = self.build_contract()["statusSemantics"]["succeeded"]

        self.assertIs(succeeded["emptyGraphMaySucceed"], True)
        empty_graph_boundary = succeeded["emptyGraphBoundary"].lower()
        self.assertIn("deterministically", empty_graph_boundary)
        self.assertIn("no references", empty_graph_boundary)

    def test_succeeded_must_not_be_selected_after_incomplete_required_work(
        self,
    ) -> None:
        succeeded = self.build_contract()["statusSemantics"]["succeeded"]
        must_not = " ".join(succeeded["mustNotBeSelectedWhen"]).lower()

        self.assertIn("required operation failed", must_not)
        self.assertIn("incomplete", must_not)

    def test_succeeded_does_not_imply_engine_pdm_identity_or_normalization(
        self,
    ) -> None:
        succeeded = self.build_contract()["statusSemantics"]["succeeded"]
        does_not_imply = " ".join(succeeded["doesNotImply"]).lower()

        self.assertIn("engine verification", does_not_imply)
        self.assertIn("pdm knowledge", does_not_imply)
        self.assertIn("durable identity", does_not_imply)
        self.assertIn("normalization", does_not_imply)
        self.assertIn("missing, unresolved, or contract-permitted skipped", does_not_imply)

    # -- partial semantics ----------------------------------------------------

    def test_partial_requires_core_conditions(self) -> None:
        partial = self.build_contract()["statusSemantics"]["partial"]
        requirements = " ".join(partial["requirements"]).lower()

        self.assertIn("request validation succeeded", requirements)
        self.assertIn("begin traversal", requirements)
        self.assertIn("non-diagnostic graph evidence was retained", requirements)
        self.assertIn("failed", requirements)
        self.assertIn("independently reliable", requirements)
        self.assertIn("incompleteness is explicit", requirements)
        self.assertIn("explainable diagnostic evidence", requirements)

    def test_partial_diagnostic_evidence_alone_is_insufficient(self) -> None:
        partial = self.build_contract()["statusSemantics"]["partial"]

        self.assertIs(partial["diagnosticEvidenceAloneIsUsableGraphEvidence"], False)
        not_selected = " ".join(partial["notSelectedMerelyBecause"]).lower()
        self.assertIn("warnings or diagnostics are present", not_selected)

    def test_partial_not_selected_merely_for_missing_unresolved_or_skipped(
        self,
    ) -> None:
        partial = self.build_contract()["statusSemantics"]["partial"]

        self.assertEqual(
            partial["notSelectedMerelyBecause"],
            [
                "an item is missing",
                "an item is unresolved",
                "an item is contract-permitted skipped",
                "warnings or diagnostics are present",
            ],
        )

    def test_partial_excludes_malformed_open_and_unsafe_emission_failures(
        self,
    ) -> None:
        partial = self.build_contract()["statusSemantics"]["partial"]
        excluded = partial["excludedFailures"]

        self.assertEqual(len(excluded), 4)
        excluded_text = " ".join(excluded).lower()
        self.assertIn("malformed or invalid traversal request", excluded_text)
        self.assertIn("source-document open failure", excluded_text)
        self.assertIn("output containment failure", excluded_text)
        self.assertIn("output-write failure", excluded_text)

    def test_partial_retained_evidence_must_not_be_guessed_or_treated_complete(
        self,
    ) -> None:
        partial = self.build_contract()["statusSemantics"]["partial"]

        self.assertIs(partial["retainedEvidenceMayBeGuessedOrRewritten"], False)
        self.assertIs(partial["retainedEvidenceMayBeTreatedAsComplete"], False)

    def test_partial_failed_item_boundary_permits_other_trustworthy_evidence(
        self,
    ) -> None:
        partial = self.build_contract()["statusSemantics"]["partial"]
        boundary = partial["failedItemBoundary"].lower()

        self.assertIn("other trustworthy graph evidence remains", boundary)
        self.assertIn("does not automatically force top-level failed", boundary)

    # -- failed semantics -------------------------------------------------------

    def test_failed_categories_cover_pre_evidence_and_unsafe_emission_failures(
        self,
    ) -> None:
        failed = self.build_contract()["statusSemantics"]["failed"]

        self.assertEqual(
            failed["categories"],
            [
                "malformed or invalid traversal request",
                "source-document open failure",
                "traversal failure before reliable graph evidence was established",
                "systemic or boundary failure that makes retained evidence unreliable",
                "failure where no trustworthy non-diagnostic graph evidence remains",
                "output containment failure that prevents safe traversal-result emission",
                "serialization failure that prevents safe traversal-result emission",
                "output-write failure that prevents safe traversal-result emission",
            ],
        )

    def test_failed_negative_distinctions(self) -> None:
        failed = self.build_contract()["statusSemantics"]["failed"]

        self.assertEqual(
            failed["notSelectedMerelyBecause"],
            [
                "a target is missing",
                "a relationship remains unresolved",
                "a permitted item was skipped",
                "a single item failed",
                "the graph is empty",
            ],
        )

    def test_failed_decision_basis_is_exact(self) -> None:
        failed = self.build_contract()["statusSemantics"]["failed"]

        self.assertEqual(
            failed["decisionBasis"],
            [
                "operation stage",
                "evidence trustworthiness",
                "required-scope completion",
                "safe result availability",
            ],
        )

    def test_failed_is_not_worst_item_state_aggregation(self) -> None:
        failed = self.build_contract()["statusSemantics"]["failed"]

        self.assertIs(failed["notWorstItemStateAggregation"], True)

    # -- aggregate decision rules -------------------------------------------

    def test_aggregate_status_not_severity_maximum_or_item_derived(self) -> None:
        rules = self.build_contract()["aggregateDecisionRules"]

        self.assertIs(rules["itemStatesDeriveStatus"], False)
        self.assertIs(rules["severityMaximumOverItemStates"], False)

    def test_non_reducing_item_states_match_known_permitted_states(self) -> None:
        rules = self.build_contract()["aggregateDecisionRules"]

        self.assertEqual(
            set(rules["nonReducingItemStates"]),
            {
                self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
                self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
                self.contract.REFERENCE_TRAVERSAL_STATE_SKIPPED,
            },
        )
        self.assertIs(rules["nonReducingSkippedStateRequiresContractPermission"], True)

    def test_failed_item_with_other_evidence_may_be_partial(self) -> None:
        rules = self.build_contract()["aggregateDecisionRules"]

        self.assertIs(rules["failedItemWithOtherTrustworthyEvidenceMayBePartial"], True)

    def test_no_trustworthy_evidence_or_unusable_result_produces_failed(self) -> None:
        rules = self.build_contract()["aggregateDecisionRules"]

        self.assertIs(rules["noTrustworthyGraphEvidenceProducesFailed"], True)
        self.assertIs(rules["unusableResultProducesFailed"], True)
        self.assertIs(rules["preEvidenceBoundaryFailureProducesFailed"], True)

    def test_complete_required_scope_processing_compatible_with_succeeded(
        self,
    ) -> None:
        rules = self.build_contract()["aggregateDecisionRules"]

        self.assertIs(rules["completeRequiredScopeProcessingProducesSucceeded"], True)

    def test_partial_requires_usable_evidence_and_explicit_incompleteness(
        self,
    ) -> None:
        rules = self.build_contract()["aggregateDecisionRules"]

        self.assertIs(rules["partialRequiresUsableRetainedGraphEvidence"], True)
        self.assertIs(rules["partialRequiresExplicitIncompleteness"], True)

    def test_diagnostic_and_count_signals_do_not_determine_status(self) -> None:
        rules = self.build_contract()["aggregateDecisionRules"]

        self.assertIs(rules["diagnosticPresenceOrCountDeterminesStatus"], False)
        self.assertIs(rules["nodeOrEdgeCountDeterminesStatus"], False)

    def test_no_numeric_or_percentage_completeness_rule(self) -> None:
        completeness = self.build_contract()["completenessCriteria"]

        self.assertEqual(
            completeness,
            {
                "semantic": True,
                "percentageOrNumericThresholdUsed": False,
                "basis": [
                    "whether required contract-approved traversal work completed",
                    "whether retained evidence is trustworthy",
                ],
            },
        )

    def test_no_numeric_leaf_values_anywhere_in_metadata(self) -> None:
        metadata = self.build_contract()

        def _assert_no_numeric_leaves(value: object) -> None:
            if isinstance(value, dict):
                for item in value.values():
                    _assert_no_numeric_leaves(item)
                return
            if isinstance(value, list):
                for item in value:
                    _assert_no_numeric_leaves(item)
                return
            if isinstance(value, bool):
                return
            self.assertNotIsInstance(value, (int, float))

        _assert_no_numeric_leaves(metadata)

    def test_usable_retained_evidence_requires_non_diagnostic_graph_evidence(
        self,
    ) -> None:
        usable_evidence = self.build_contract()["usableRetainedEvidence"]

        self.assertIs(usable_evidence["requiresTrustworthyNonDiagnosticGraphEvidence"], True)
        self.assertIs(usable_evidence["diagnosticEvidenceAloneIsSufficient"], False)
        self.assertIs(usable_evidence["mustRemainIndependentlyReliable"], True)
        self.assertEqual(
            usable_evidence["examples"],
            ["trustworthy node observation", "trustworthy edge observation"],
        )

    # -- item-state and aggregate-status alignment ---------------------------

    def test_both_helpers_refer_to_the_same_status_field_vocabulary(self) -> None:
        item_state_metadata = (
            self.contract.build_reference_traversal_runtime_state_semantics_contract()
        )
        aggregate_metadata = self.build_contract()

        self.assertEqual(
            item_state_metadata["topLevelStatusBoundary"]["field"],
            self.contract.REFERENCE_TRAVERSAL_FIELD_STATUS,
        )
        self.assertEqual(
            set(aggregate_metadata["statusOrder"]),
            {
                self.contract.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
                self.contract.REFERENCE_TRAVERSAL_STATUS_PARTIAL,
                self.contract.REFERENCE_TRAVERSAL_STATUS_FAILED,
            },
        )

    def test_both_helpers_agree_failed_item_does_not_force_aggregate_failed(
        self,
    ) -> None:
        item_state_metadata = (
            self.contract.build_reference_traversal_runtime_state_semantics_contract()
        )
        aggregate_metadata = self.build_contract()

        self.assertIs(
            item_state_metadata["topLevelStatusBoundary"][
                "failedItemAutomaticallyMakesTraversalFailed"
            ],
            False,
        )
        self.assertIs(
            aggregate_metadata["dimensionSeparation"][
                "failedItemAutomaticallyMakesTraversalFailed"
            ],
            False,
        )

    def test_both_helpers_agree_aggregation_semantics_are_now_defined(self) -> None:
        item_state_metadata = (
            self.contract.build_reference_traversal_runtime_state_semantics_contract()
        )
        aggregate_metadata = self.build_contract()

        self.assertIs(
            item_state_metadata["topLevelStatusBoundary"][
                "partialVersusFailedAggregationDefined"
            ],
            True,
        )
        self.assertGreater(len(aggregate_metadata["aggregateDecisionRules"]), 0)

    def test_neither_helper_introduces_a_new_item_state(self) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES,
            ("resolved", "missing", "unresolved", "skipped", "failed"),
        )

        aggregate_metadata = self.build_contract()
        referenced_states = set(
            aggregate_metadata["statusSemantics"]["succeeded"][
                "validItemOutcomesThatDoNotAutomaticallyReduceStatus"
            ]
        ) | set(aggregate_metadata["aggregateDecisionRules"]["nonReducingItemStates"])

        self.assertTrue(
            referenced_states.issubset(
                set(self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES)
            )
        )

    def test_aggregate_helper_does_not_duplicate_item_state_meanings(self) -> None:
        aggregate_metadata = self.build_contract()

        self.assertNotIn("stateSemantics", aggregate_metadata)
        self.assertNotIn("stateOrder", aggregate_metadata)

    def test_item_state_helper_does_not_perform_aggregate_derivation(self) -> None:
        item_state_metadata = (
            self.contract.build_reference_traversal_runtime_state_semantics_contract()
        )

        self.assertNotIn("aggregateDecisionRules", item_state_metadata)
        self.assertNotIn("completenessCriteria", item_state_metadata)

    # -- canonical JSON and determinism --------------------------------------

    def test_metadata_is_plain_json_compatible_dict(self) -> None:
        metadata = self.build_contract()

        self.assertIsInstance(metadata, dict)
        _assert_only_json_leaf_types(self, metadata)

    def test_repeated_calls_serialize_to_identical_canonical_bytes(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(dumps_canonical(first), dumps_canonical(second))

    def test_dumps_canonical_does_not_mutate_metadata(self) -> None:
        import copy

        metadata = self.build_contract()
        snapshot = copy.deepcopy(metadata)

        dumps_canonical(metadata)

        self.assertEqual(metadata, snapshot)

    def test_repeated_calls_are_value_equivalent_but_independent(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["statusOrder"], second["statusOrder"])
        self.assertIsNot(first["statusSemantics"], second["statusSemantics"])
        self.assertIsNot(
            first["statusSemantics"]["succeeded"],
            second["statusSemantics"]["succeeded"],
        )
        self.assertIsNot(
            first["statusSemantics"]["succeeded"]["requirements"],
            second["statusSemantics"]["succeeded"]["requirements"],
        )
        self.assertIsNot(
            first["statusSemantics"]["partial"]["excludedFailures"],
            second["statusSemantics"]["partial"]["excludedFailures"],
        )
        self.assertIsNot(
            first["statusSemantics"]["failed"]["categories"],
            second["statusSemantics"]["failed"]["categories"],
        )
        self.assertIsNot(
            first["aggregateDecisionRules"], second["aggregateDecisionRules"]
        )
        self.assertIsNot(first["completenessCriteria"], second["completenessCriteria"])
        self.assertIsNot(
            first["usableRetainedEvidence"], second["usableRetainedEvidence"]
        )
        self.assertIsNot(first["dimensionSeparation"], second["dimensionSeparation"])
        self.assertIsNot(first["helperBehavior"], second["helperBehavior"])

    # -- mutation isolation ---------------------------------------------------

    def test_deep_mutation_does_not_leak_to_a_later_call(self) -> None:
        first = self.build_contract()

        first["statusOrder"].append("mutated")
        first["statusSemantics"]["succeeded"]["requirements"].append("mutated")
        first["statusSemantics"]["partial"]["excludedFailures"].append("mutated")
        first["statusSemantics"]["failed"]["categories"].append("mutated")
        first["aggregateDecisionRules"]["itemStatesDeriveStatus"] = True
        first["helperBehavior"]["writesFiles"] = True
        first["injected"] = "mutated"

        second = self.build_contract()

        self.assertNotIn("mutated", second["statusOrder"])
        self.assertNotIn(
            "mutated", second["statusSemantics"]["succeeded"]["requirements"]
        )
        self.assertNotIn(
            "mutated", second["statusSemantics"]["partial"]["excludedFailures"]
        )
        self.assertNotIn(
            "mutated", second["statusSemantics"]["failed"]["categories"]
        )
        self.assertIs(
            second["aggregateDecisionRules"]["itemStatesDeriveStatus"], False
        )
        self.assertIs(second["helperBehavior"]["writesFiles"], False)
        self.assertNotIn("injected", second)

    def test_mutation_does_not_leak_to_module_level_constants(self) -> None:
        metadata = self.build_contract()

        metadata["statusOrder"].append("mutated")
        metadata["statusSemantics"]["succeeded"]["requirements"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED, "succeeded"
        )
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATUS_PARTIAL, "partial")
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_STATUS_FAILED, "failed")
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES,
            ("resolved", "missing", "unresolved", "skipped", "failed"),
        )

    # -- import safety ----------------------------------------------------------

    def test_import_and_call_do_not_require_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()
            module.build_reference_traversal_aggregate_status_semantics_contract()

        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class ReferenceTraversalAggregateStatusCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    # -- raw payload compatibility --------------------------------------------

    def test_payload_builder_still_requires_caller_supplied_status(self) -> None:
        with self.assertRaises(TypeError):
            self.contract.build_reference_traversal_output_payload(
                boundary=self.contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
                operation=self.contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
                source_document="assembly.FCStd",
                nodes=(),
                edges=(),
            )

    def test_payload_preserves_each_caller_supplied_status_unchanged(self) -> None:
        nodes = [_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED)]
        edges = [_edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED)]

        for status in (
            self.contract.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
            self.contract.REFERENCE_TRAVERSAL_STATUS_PARTIAL,
            self.contract.REFERENCE_TRAVERSAL_STATUS_FAILED,
        ):
            with self.subTest(status=status):
                payload = _build_payload(
                    self.contract, status=status, nodes=nodes, edges=edges
                )
                self.assertEqual(payload["status"], status)

    def test_item_level_failed_state_does_not_replace_caller_supplied_status(
        self,
    ) -> None:
        nodes = [_node(state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED)]
        edges = [_edge(state=self.contract.REFERENCE_TRAVERSAL_STATE_FAILED)]

        payload = _build_payload(
            self.contract,
            status=self.contract.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
            nodes=nodes,
            edges=edges,
        )

        self.assertEqual(payload["status"], "succeeded")

    def test_payload_builder_does_not_implicitly_call_aggregate_helper(self) -> None:
        with mock.patch.object(
            self.contract,
            "build_reference_traversal_aggregate_status_semantics_contract",
            wraps=self.contract.build_reference_traversal_aggregate_status_semantics_contract,
        ) as spy:
            _build_payload(self.contract)

        spy.assert_not_called()

    # -- malformed-request compatibility --------------------------------------

    def test_malformed_request_payload_unchanged_by_aggregate_helper_addition(
        self,
    ) -> None:
        payload = self.contract.build_malformed_reference_traversal_request_payload(
            boundary=self.contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
            operation=self.contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
            source_document="assembly.FCStd",
            diagnostic_message="traversal request payload was malformed",
        )

        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["nodes"], [])
        self.assertEqual(payload["edges"], [])
        self.assertEqual(len(payload["diagnostics"]), 1)
        self.assertEqual(
            payload["diagnostics"][0]["code"], "malformed_traversal_request"
        )
        self.assertEqual(payload["diagnostics"][0]["stage"], "request_validation")

    def test_malformed_request_payload_does_not_call_aggregate_helper(self) -> None:
        with mock.patch.object(
            self.contract,
            "build_reference_traversal_aggregate_status_semantics_contract",
            wraps=self.contract.build_reference_traversal_aggregate_status_semantics_contract,
        ) as spy:
            self.contract.build_malformed_reference_traversal_request_payload(
                boundary=self.contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
                operation=self.contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
                source_document="assembly.FCStd",
                diagnostic_message="traversal request payload was malformed",
            )

        spy.assert_not_called()

    # -- schema and dataclass shape regression --------------------------------

    def test_schema_version_and_output_kind_unchanged(self) -> None:
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION, "1.0")
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_KIND_RAW_REFERENCE_TRAVERSAL,
            "raw_reference_traversal",
        )

    def test_dataclass_field_sets_unchanged(self) -> None:
        node_fields = {f.name for f in dataclass_fields(self.contract.RawReferenceTraversalNode)}
        edge_fields = {f.name for f in dataclass_fields(self.contract.RawReferenceTraversalEdge)}
        diagnostic_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalDiagnostic)
        }

        self.assertEqual(
            node_fields,
            {"id", "kind", "state", "document_path", "object_name", "label", "diagnostic"},
        )
        self.assertEqual(
            edge_fields, {"source", "target", "kind", "state", "diagnostic"}
        )
        self.assertEqual(
            diagnostic_fields, {"severity", "code", "message", "stage"}
        )

    def test_payload_top_level_field_set_unchanged(self) -> None:
        payload = _build_payload(self.contract)

        self.assertEqual(
            set(payload),
            {
                "schemaVersion",
                "kind",
                "boundary",
                "operation",
                "status",
                "sourceDocument",
                "nodes",
                "edges",
                "diagnostics",
            },
        )


class ReferenceTraversalNormalizationContractPublicApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_normalization_contract
        )

    def test_helper_is_publicly_exported_and_callable(self) -> None:
        self.assertIn(
            "build_reference_traversal_normalization_contract",
            self.contract.__all__,
        )
        self.assertTrue(callable(self.build_contract))

    def test_export_does_not_leak_a_private_helper_name(self) -> None:
        self.assertFalse(
            hasattr(
                self.contract,
                "_build_reference_traversal_normalization_contract",
            )
        )
        for name in self.contract.__all__:
            self.assertFalse(name.startswith("_"), name)

    def test_helper_signature_requires_no_arguments(self) -> None:
        import inspect

        signature = inspect.signature(self.build_contract)
        self.assertEqual(list(signature.parameters), [])

    def test_helper_returns_plain_dict_with_no_arguments(self) -> None:
        metadata = self.build_contract()

        self.assertIsInstance(metadata, dict)

    def test_metadata_contains_documented_top_level_keys(self) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata),
            {
                "fieldCategories",
                "stringRules",
                "canonicalContractRelativePathRules",
                "destructiveCanonicalizationPreservation",
                "schemaCompatibilityBoundary",
                "capabilities",
            },
        )

    def test_no_new_schema_fields_or_dataclass_fields_are_introduced(self) -> None:
        node_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }
        edge_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }

        self.assertEqual(
            node_fields,
            {
                "id",
                "kind",
                "state",
                "document_path",
                "object_name",
                "label",
                "diagnostic",
            },
        )
        self.assertEqual(
            edge_fields, {"source", "target", "kind", "state", "diagnostic"}
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION, "1.0"
        )


class ReferenceTraversalNormalizationContractFieldCategoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.categories = (
            self.contract.build_reference_traversal_normalization_contract()[
                "fieldCategories"
            ]
        )

    def test_field_category_key_set_is_exact(self) -> None:
        self.assertEqual(
            set(self.categories),
            {
                "contractRelativePathEvidence",
                "stableSemanticOrControlledStrings",
                "exactRawDescriptiveOrDiagnosticEvidence",
                "inactiveFutureProvenanceStrings",
            },
        )

    # -- contract-relative path evidence -----------------------------------

    def test_contract_relative_path_evidence_fields_are_current_path_evidence(
        self,
    ) -> None:
        category = self.categories["contractRelativePathEvidence"]

        self.assertEqual(
            set(category),
            {
                "fields",
                "semanticNodeIdentityDocumentPathUsesSameContract",
                "notUsedAs",
            },
        )
        self.assertEqual(
            category["fields"],
            ["sourceDocument", "nodes[].documentPath"],
        )
        self.assertIs(
            category["semanticNodeIdentityDocumentPathUsesSameContract"], True
        )

    def test_contract_relative_path_evidence_is_not_described_as_containment_or_engine_identity(
        self,
    ) -> None:
        not_used_as = self.categories["contractRelativePathEvidence"]["notUsedAs"]
        joined = " ".join(not_used_as).lower()

        self.assertIn("traversal output-file containment", joined)
        self.assertIn("execution-root filesystem paths", joined)
        self.assertIn("temporary absolute working-copy paths", joined)
        self.assertIn("engine-normalized asset identity", joined)

    # -- stable semantic / controlled strings ------------------------------

    def test_stable_semantic_or_controlled_strings_covers_documented_fields(
        self,
    ) -> None:
        category = self.categories["stableSemanticOrControlledStrings"]

        self.assertEqual(set(category), {"currentSerializedFields", "semantics"})

        expected_fields = [
            self.contract.REFERENCE_TRAVERSAL_FIELD_SCHEMA_VERSION,
            self.contract.REFERENCE_TRAVERSAL_FIELD_KIND,
            self.contract.REFERENCE_TRAVERSAL_FIELD_BOUNDARY,
            self.contract.REFERENCE_TRAVERSAL_FIELD_OPERATION,
            self.contract.REFERENCE_TRAVERSAL_FIELD_STATUS,
            "nodes[].id",
            "edges[].source",
            "edges[].target",
            "nodes[].kind",
            "nodes[].state",
            "nodes[].objectName",
            "edges[].kind",
            "edges[].state",
            "diagnostics[].severity",
            "diagnostics[].code",
            "diagnostics[].stage",
        ]
        self.assertEqual(category["currentSerializedFields"], expected_fields)

        required_subset = {
            "schemaVersion",
            "boundary",
            "operation",
            "status",
            "nodes[].id",
            "nodes[].kind",
            "nodes[].state",
            "nodes[].objectName",
            "edges[].source",
            "edges[].target",
            "edges[].kind",
            "edges[].state",
            "diagnostics[].severity",
            "diagnostics[].code",
            "diagnostics[].stage",
        }
        self.assertTrue(
            required_subset.issubset(set(category["currentSerializedFields"]))
        )

    # -- exact raw descriptive/diagnostic evidence -------------------------

    def test_exact_raw_descriptive_or_diagnostic_evidence_covers_documented_fields(
        self,
    ) -> None:
        category = self.categories["exactRawDescriptiveOrDiagnosticEvidence"]

        self.assertEqual(
            set(category),
            {
                "currentSerializedFields",
                "preservedExactly",
                "semanticIdentityInputs",
                "canonicalPathInputs",
            },
        )
        self.assertEqual(
            category["currentSerializedFields"],
            [
                "nodes[].label",
                "nodes[].diagnostic",
                "edges[].diagnostic",
                "diagnostics[].message",
            ],
        )
        self.assertIs(category["preservedExactly"], True)
        self.assertIs(category["semanticIdentityInputs"], False)
        self.assertIs(category["canonicalPathInputs"], False)

    # -- inactive future provenance strings --------------------------------

    def test_inactive_future_provenance_strings_are_not_active_schema_fields(
        self,
    ) -> None:
        category = self.categories["inactiveFutureProvenanceStrings"]

        self.assertEqual(
            set(category),
            {
                "requirements",
                "proposedLocations",
                "active",
                "currentSerializedSchemaFields",
                "semantics",
            },
        )
        self.assertEqual(
            category["requirements"],
            ["objectType", "sourceProperty", "referenceMechanism"],
        )
        self.assertEqual(
            category["proposedLocations"],
            {
                "objectType": "nodes[].objectType",
                "sourceProperty": "edges[].sourceProperty",
                "referenceMechanism": "edges[].referenceMechanism",
            },
        )
        self.assertIs(category["active"], False)
        self.assertIs(category["currentSerializedSchemaFields"], False)

    def test_inactive_future_provenance_fields_are_not_tested_as_active_dataclass_fields(
        self,
    ) -> None:
        node_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }
        edge_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }

        self.assertNotIn("object_type", node_fields)
        self.assertNotIn("source_property", edge_fields)
        self.assertNotIn("reference_mechanism", edge_fields)


class ReferenceTraversalNormalizationContractStringRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.string_rules = (
            self.contract.build_reference_traversal_normalization_contract()[
                "stringRules"
            ]
        )

    def test_string_rule_key_set_is_exact(self) -> None:
        self.assertEqual(
            set(self.string_rules),
            {
                "requiredSemanticValuesAreStrings",
                "silentTypeCoercionAllowed",
                "requiredValuesMayBeEmpty",
                "controlledVocabularyExactAndCaseSensitive",
                "stableNamesIdentifiersPropertiesMechanismsCodesStagesPreserveCase",
                "caseFoldingPerformed",
                "localeSensitiveRewritingPerformed",
                "unicodeNormalizationPerformed",
                "transliterationPerformed",
                "semanticInferenceFromSpellingPerformed",
                "surroundingWhitespaceSilentlyRemoved",
                "futureInvalidSurroundingWhitespacePolicy",
                "rawLabelsAndDiagnosticTextPreservedExactly",
                "conceptOverloadingForbidden",
                "runtimeValidationChanged",
            },
        )

    def test_required_semantic_string_rules_reject_coercion_and_emptiness(
        self,
    ) -> None:
        rules = self.string_rules

        self.assertIs(rules["requiredSemanticValuesAreStrings"], True)
        self.assertIs(rules["silentTypeCoercionAllowed"], False)
        self.assertIs(rules["requiredValuesMayBeEmpty"], False)

    def test_controlled_vocabulary_is_exact_and_case_sensitive(self) -> None:
        rules = self.string_rules

        self.assertIs(rules["controlledVocabularyExactAndCaseSensitive"], True)
        self.assertIs(
            rules[
                "stableNamesIdentifiersPropertiesMechanismsCodesStagesPreserveCase"
            ],
            True,
        )

    def test_no_rewriting_transformations_are_performed(self) -> None:
        rules = self.string_rules

        self.assertIs(rules["caseFoldingPerformed"], False)
        self.assertIs(rules["localeSensitiveRewritingPerformed"], False)
        self.assertIs(rules["unicodeNormalizationPerformed"], False)
        self.assertIs(rules["transliterationPerformed"], False)
        self.assertIs(rules["semanticInferenceFromSpellingPerformed"], False)

    def test_whitespace_is_not_silently_trimmed_but_future_invalid_whitespace_is_rejected(
        self,
    ) -> None:
        rules = self.string_rules

        self.assertIs(rules["surroundingWhitespaceSilentlyRemoved"], False)
        self.assertEqual(
            rules["futureInvalidSurroundingWhitespacePolicy"], "reject_not_trim"
        )

    def test_raw_labels_and_diagnostics_preserved_exactly_without_concept_overload(
        self,
    ) -> None:
        rules = self.string_rules

        self.assertIs(rules["rawLabelsAndDiagnosticTextPreservedExactly"], True)
        self.assertEqual(
            rules["conceptOverloadingForbidden"],
            ["labels", "diagnostics", "identifiers", "kinds", "states", "provenance"],
        )

    def test_helper_does_not_claim_it_changed_runtime_validation(self) -> None:
        self.assertIs(self.string_rules["runtimeValidationChanged"], False)

    def test_helper_does_not_add_string_normalization_or_whitespace_rejection_helpers(
        self,
    ) -> None:
        self.assertFalse(hasattr(self.contract, "_require_stripped_string"))
        self.assertFalse(hasattr(self.contract, "normalize_reference_traversal_string"))


class ReferenceTraversalNormalizationContractPathRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.path_rules = (
            self.contract.build_reference_traversal_normalization_contract()[
                "canonicalContractRelativePathRules"
            ]
        )

    def test_path_rule_key_set_is_exact(self) -> None:
        self.assertEqual(
            set(self.path_rules),
            {
                "fields",
                "representation",
                "relativeTo",
                "absoluteFilesystemPathAllowed",
                "driveQualifiedAllowed",
                "uncOrNetworkRootAllowed",
                "leadingRootSeparatorAllowed",
                "canonicalSeparator",
                "dotSegmentsAllowed",
                "parentSegmentsAllowed",
                "emptySegmentsFromRepeatedSeparatorsAllowed",
                "lexicalParentEscapeAllowed",
                "casePreserved",
                "unicodeCodePointsPreservedAsSupplied",
                "tildeExpanded",
                "environmentVariablesExpanded",
                "resolvedAgainstHostCurrentWorkingDirectory",
                "resolvedThroughFilesystem",
                "symlinksFollowed",
                "referencedFileMustExist",
                "provesOutputContainment",
                "provesWorkingCopyContainment",
                "distinctions",
                "normalizerResolverOrValidatorImplemented",
            },
        )
        self.assertEqual(self.path_rules["fields"], ["sourceDocument", "nodes[].documentPath"])
        self.assertEqual(self.path_rules["canonicalSeparator"], "/")

    def test_canonical_path_is_non_empty_relative_and_not_filesystem_qualified(
        self,
    ) -> None:
        rules = self.path_rules

        self.assertIs(rules["absoluteFilesystemPathAllowed"], False)
        self.assertIs(rules["driveQualifiedAllowed"], False)
        self.assertIs(rules["uncOrNetworkRootAllowed"], False)
        self.assertIs(rules["leadingRootSeparatorAllowed"], False)
        self.assertEqual(
            rules["relativeTo"], "contract-defined traversal/document root"
        )

    def test_canonical_path_rejects_dot_and_parent_and_empty_segments(self) -> None:
        rules = self.path_rules

        self.assertIs(rules["dotSegmentsAllowed"], False)
        self.assertIs(rules["parentSegmentsAllowed"], False)
        self.assertIs(rules["emptySegmentsFromRepeatedSeparatorsAllowed"], False)
        self.assertIs(rules["lexicalParentEscapeAllowed"], False)

    def test_canonical_path_preserves_case_and_unicode_without_expansion(self) -> None:
        rules = self.path_rules

        self.assertIs(rules["casePreserved"], True)
        self.assertIs(rules["unicodeCodePointsPreservedAsSupplied"], True)
        self.assertIs(rules["tildeExpanded"], False)
        self.assertIs(rules["environmentVariablesExpanded"], False)

    def test_canonical_path_is_not_resolved_against_filesystem_or_cwd(self) -> None:
        rules = self.path_rules

        self.assertIs(rules["resolvedAgainstHostCurrentWorkingDirectory"], False)
        self.assertIs(rules["resolvedThroughFilesystem"], False)
        self.assertIs(rules["symlinksFollowed"], False)
        self.assertIs(rules["referencedFileMustExist"], False)

    def test_canonical_path_does_not_prove_containment(self) -> None:
        rules = self.path_rules

        self.assertIs(rules["provesOutputContainment"], False)
        self.assertIs(rules["provesWorkingCopyContainment"], False)

    def test_distinctions_separate_canonicalization_from_related_concepts(self) -> None:
        distinctions = " ".join(self.path_rules["distinctions"]).lower()

        self.assertIn("filesystem path resolution", distinctions)
        self.assertIn("traversal output containment", distinctions)
        self.assertIn("engine normalization", distinctions)

    def test_helper_does_not_implement_a_normalizer_resolver_or_validator(self) -> None:
        self.assertIs(
            self.path_rules["normalizerResolverOrValidatorImplemented"], False
        )
        self.assertFalse(
            hasattr(self.contract, "normalize_reference_traversal_document_path")
        )
        self.assertFalse(
            hasattr(self.contract, "validate_reference_traversal_document_path")
        )

    def test_helper_requires_no_filesystem_access(self) -> None:
        real_exists = Path.exists

        def _forbidden_exists(self_path: Path) -> bool:  # pragma: no cover - guard
            raise AssertionError(
                f"unexpected filesystem access during normalization-contract build: {self_path}"
            )

        with mock.patch.object(Path, "exists", _forbidden_exists):
            metadata = (
                self.contract.build_reference_traversal_normalization_contract()
            )

        self.assertIn("canonicalContractRelativePathRules", metadata)
        self.assertIs(Path.exists, real_exists)


class ReferenceTraversalNormalizationContractRawPreservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.preservation = (
            self.contract.build_reference_traversal_normalization_contract()[
                "destructiveCanonicalizationPreservation"
            ]
        )

    def test_raw_preservation_key_set_is_exact(self) -> None:
        self.assertEqual(
            set(self.preservation),
            {
                "trigger",
                "examples",
                "canonicalAndOriginalAreSeparateConcepts",
                "originalMayBeSilentlyOverwritten",
                "originalMayBeHiddenInUnrelatedExistingField",
                "originalRequiresSeparatelyApprovedRawEvidenceLocationOrSurface",
                "semanticIdentityUsesOnlyApprovedCanonicalValue",
                "labelsOrDiagnosticsUsedAsRawOriginalStorage",
            },
        )

    def test_destructive_transformation_examples_are_representative(self) -> None:
        examples = " ".join(self.preservation["examples"]).lower()

        self.assertIn("separator conversion", examples)
        self.assertIn("path-segment removal", examples)
        self.assertIn("whitespace removal", examples)
        self.assertIn("case rewriting", examples)
        self.assertIn("unicode rewriting", examples)

    def test_canonical_and_original_are_kept_separate_and_not_overwritten(self) -> None:
        preservation = self.preservation

        self.assertIs(preservation["canonicalAndOriginalAreSeparateConcepts"], True)
        self.assertIs(preservation["originalMayBeSilentlyOverwritten"], False)
        self.assertIs(preservation["originalMayBeHiddenInUnrelatedExistingField"], False)
        self.assertIs(
            preservation["originalRequiresSeparatelyApprovedRawEvidenceLocationOrSurface"],
            True,
        )

    def test_semantic_identity_uses_only_approved_canonical_value(self) -> None:
        self.assertIs(
            self.preservation["semanticIdentityUsesOnlyApprovedCanonicalValue"], True
        )

    def test_labels_and_diagnostics_are_not_repurposed_as_raw_original_storage(
        self,
    ) -> None:
        self.assertIs(
            self.preservation["labelsOrDiagnosticsUsedAsRawOriginalStorage"], False
        )

    def test_no_active_raw_original_field_is_introduced_or_tested_as_schema(
        self,
    ) -> None:
        node_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }
        edge_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }

        for forbidden in ("raw_document_path", "original_path", "raw_value"):
            self.assertNotIn(forbidden, node_fields)
            self.assertNotIn(forbidden, edge_fields)

        payload = _build_payload(self.contract)
        for forbidden in ("rawDocumentPath", "originalPath", "rawValue"):
            self.assertNotIn(forbidden, payload)
            self.assertNotIn(forbidden, payload["nodes"][0])
            self.assertNotIn(forbidden, payload["edges"][0])


class ReferenceTraversalNormalizationContractSchemaCompatibilityTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        metadata = self.contract.build_reference_traversal_normalization_contract()
        self.schema_boundary = metadata["schemaCompatibilityBoundary"]
        self.capabilities = metadata["capabilities"]

    def test_schema_compatibility_boundary_key_set_is_exact(self) -> None:
        self.assertEqual(
            set(self.schema_boundary),
            {
                "schemaVersion",
                "approvedGeneralPurposeSerializedRawOriginalFieldExists",
                "rawOriginalFieldActivatedByThisContract",
                "serializingBothFormsRequires",
                "helperSerializesPreservesOrTransformsRuntimeValues",
            },
        )

    def test_schema_version_remains_one_point_zero_and_matches_production_constant(
        self,
    ) -> None:
        self.assertEqual(self.schema_boundary["schemaVersion"], "1.0")
        self.assertEqual(
            self.schema_boundary["schemaVersion"],
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
        )

    def test_no_approved_raw_original_field_exists_or_was_activated(self) -> None:
        self.assertIs(
            self.schema_boundary["approvedGeneralPurposeSerializedRawOriginalFieldExists"],
            False,
        )
        self.assertIs(
            self.schema_boundary["rawOriginalFieldActivatedByThisContract"], False
        )

    def test_serializing_both_forms_requires_a_later_explicit_extension_decision(
        self,
    ) -> None:
        requirement = self.schema_boundary["serializingBothFormsRequires"].lower()

        self.assertIn("later", requirement)
        self.assertIn("explicit", requirement)
        self.assertTrue(
            "compatible" in requirement or "versioned" in requirement
        )
        self.assertIn("contract-extension decision", requirement)

    def test_helper_does_not_serialize_preserve_or_transform_runtime_values(
        self,
    ) -> None:
        self.assertIs(
            self.schema_boundary["helperSerializesPreservesOrTransformsRuntimeValues"],
            False,
        )

    def test_capability_key_set_is_exact(self) -> None:
        self.assertEqual(
            set(self.capabilities),
            {
                "definesNormalizationRules",
                "performsNormalization",
                "validatesRuntimeTraversalValues",
                "performsFilesystemInspection",
                "performsRealFreecadTraversal",
                "changesPayloadSchema",
                "addsSerializedField",
                "changesIdentityKey",
                "changesDeduplicationRule",
                "changesOrderingRule",
                "implementsWriter",
                "implementsRequestLoader",
                "implementsRuntimeWiring",
                "performsEngineNormalization",
                "producesPdmIdentityOrPersistenceBehavior",
            },
        )

    def test_capabilities_disclose_metadata_only_no_op_behavior(self) -> None:
        capabilities = self.capabilities

        self.assertIs(capabilities["definesNormalizationRules"], True)
        self.assertIs(capabilities["performsNormalization"], False)
        self.assertIs(capabilities["validatesRuntimeTraversalValues"], False)
        self.assertIs(capabilities["performsFilesystemInspection"], False)
        self.assertIs(capabilities["performsRealFreecadTraversal"], False)
        self.assertIs(capabilities["changesPayloadSchema"], False)
        self.assertIs(capabilities["addsSerializedField"], False)
        self.assertIs(capabilities["changesIdentityKey"], False)
        self.assertIs(capabilities["changesDeduplicationRule"], False)
        self.assertIs(capabilities["changesOrderingRule"], False)
        self.assertIs(capabilities["implementsWriter"], False)
        self.assertIs(capabilities["implementsRequestLoader"], False)
        self.assertIs(capabilities["implementsRuntimeWiring"], False)
        self.assertIs(capabilities["performsEngineNormalization"], False)
        self.assertIs(
            capabilities["producesPdmIdentityOrPersistenceBehavior"], False
        )

    def test_existing_dataclass_field_lists_remain_unchanged(self) -> None:
        node_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }
        edge_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }
        diagnostic_fields = {
            f.name
            for f in dataclass_fields(self.contract.RawReferenceTraversalDiagnostic)
        }

        self.assertEqual(
            node_fields,
            {
                "id",
                "kind",
                "state",
                "document_path",
                "object_name",
                "label",
                "diagnostic",
            },
        )
        self.assertEqual(
            edge_fields, {"source", "target", "kind", "state", "diagnostic"}
        )
        self.assertEqual(
            diagnostic_fields, {"severity", "code", "message", "stage"}
        )

    def test_representative_payload_still_has_only_established_fields(self) -> None:
        payload = _build_payload(self.contract)

        self.assertEqual(
            set(payload),
            {
                "schemaVersion",
                "kind",
                "boundary",
                "operation",
                "status",
                "sourceDocument",
                "nodes",
                "edges",
                "diagnostics",
            },
        )
        self.assertEqual(
            set(payload["nodes"][0]),
            {
                "sequence",
                "id",
                "kind",
                "state",
                "documentPath",
                "objectName",
                "label",
                "diagnostic",
            },
        )
        self.assertEqual(
            set(payload["edges"][0]),
            {"sequence", "source", "target", "kind", "state", "diagnostic"},
        )
        self.assertEqual(
            set(payload["diagnostics"][0]),
            {"sequence", "severity", "code", "message", "stage"},
        )


class ReferenceTraversalNormalizationContractDeterminismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_normalization_contract
        )

    # -- canonical JSON and determinism --------------------------------------

    def test_metadata_is_plain_json_compatible_dict(self) -> None:
        metadata = self.build_contract()

        self.assertIsInstance(metadata, dict)
        _assert_only_json_leaf_types(self, metadata)

    def test_repeated_calls_serialize_to_identical_canonical_bytes(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(dumps_canonical(first), dumps_canonical(second))
        self.assertEqual(
            dumps_canonical(first).encode("utf-8"),
            dumps_canonical(second).encode("utf-8"),
        )

    def test_dumps_canonical_does_not_mutate_metadata(self) -> None:
        import copy

        metadata = self.build_contract()
        snapshot = copy.deepcopy(metadata)

        dumps_canonical(metadata)

        self.assertEqual(metadata, snapshot)

    def test_repeated_calls_are_value_equivalent_but_independent(self) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["fieldCategories"], second["fieldCategories"])
        self.assertIsNot(first["stringRules"], second["stringRules"])
        self.assertIsNot(
            first["canonicalContractRelativePathRules"],
            second["canonicalContractRelativePathRules"],
        )
        self.assertIsNot(
            first["destructiveCanonicalizationPreservation"],
            second["destructiveCanonicalizationPreservation"],
        )
        self.assertIsNot(
            first["schemaCompatibilityBoundary"], second["schemaCompatibilityBoundary"]
        )
        self.assertIsNot(first["capabilities"], second["capabilities"])
        self.assertIsNot(
            first["fieldCategories"]["contractRelativePathEvidence"],
            second["fieldCategories"]["contractRelativePathEvidence"],
        )
        self.assertIsNot(
            first["fieldCategories"]["contractRelativePathEvidence"]["fields"],
            second["fieldCategories"]["contractRelativePathEvidence"]["fields"],
        )

    def test_invocation_order_or_prior_mutation_does_not_affect_later_calls(
        self,
    ) -> None:
        first = self.build_contract()
        first["stringRules"]["caseFoldingPerformed"] = True

        second = self.build_contract()

        self.assertIs(second["stringRules"]["caseFoldingPerformed"], False)

    # -- deep freshness and mutation isolation -------------------------------

    def test_deep_mutation_of_field_category_lists_does_not_leak(self) -> None:
        first = self.build_contract()

        first["fieldCategories"]["contractRelativePathEvidence"]["fields"].append(
            "mutated"
        )
        first["fieldCategories"]["contractRelativePathEvidence"]["notUsedAs"].append(
            "mutated"
        )
        first["fieldCategories"]["stableSemanticOrControlledStrings"][
            "currentSerializedFields"
        ].append("mutated")
        first["fieldCategories"]["exactRawDescriptiveOrDiagnosticEvidence"][
            "currentSerializedFields"
        ].append("mutated")
        first["fieldCategories"]["inactiveFutureProvenanceStrings"][
            "requirements"
        ].append("mutated")
        first["fieldCategories"]["inactiveFutureProvenanceStrings"][
            "proposedLocations"
        ]["mutated"] = "mutated"

        second = self.build_contract()

        self.assertNotIn(
            "mutated",
            second["fieldCategories"]["contractRelativePathEvidence"]["fields"],
        )
        self.assertNotIn(
            "mutated",
            second["fieldCategories"]["contractRelativePathEvidence"]["notUsedAs"],
        )
        self.assertNotIn(
            "mutated",
            second["fieldCategories"]["stableSemanticOrControlledStrings"][
                "currentSerializedFields"
            ],
        )
        self.assertNotIn(
            "mutated",
            second["fieldCategories"]["exactRawDescriptiveOrDiagnosticEvidence"][
                "currentSerializedFields"
            ],
        )
        self.assertNotIn(
            "mutated",
            second["fieldCategories"]["inactiveFutureProvenanceStrings"][
                "requirements"
            ],
        )
        self.assertNotIn(
            "mutated",
            second["fieldCategories"]["inactiveFutureProvenanceStrings"][
                "proposedLocations"
            ],
        )

    def test_deep_mutation_of_string_and_path_rule_lists_does_not_leak(self) -> None:
        first = self.build_contract()

        first["stringRules"]["conceptOverloadingForbidden"].append("mutated")
        first["stringRules"]["caseFoldingPerformed"] = True
        first["canonicalContractRelativePathRules"]["fields"].append("mutated")
        first["canonicalContractRelativePathRules"]["distinctions"].append("mutated")
        first["canonicalContractRelativePathRules"][
            "absoluteFilesystemPathAllowed"
        ] = True

        second = self.build_contract()

        self.assertNotIn(
            "mutated", second["stringRules"]["conceptOverloadingForbidden"]
        )
        self.assertIs(second["stringRules"]["caseFoldingPerformed"], False)
        self.assertNotIn(
            "mutated", second["canonicalContractRelativePathRules"]["fields"]
        )
        self.assertNotIn(
            "mutated", second["canonicalContractRelativePathRules"]["distinctions"]
        )
        self.assertIs(
            second["canonicalContractRelativePathRules"][
                "absoluteFilesystemPathAllowed"
            ],
            False,
        )

    def test_deep_mutation_of_preservation_and_schema_and_capability_sections_does_not_leak(
        self,
    ) -> None:
        first = self.build_contract()

        first["destructiveCanonicalizationPreservation"]["examples"].append("mutated")
        first["destructiveCanonicalizationPreservation"][
            "originalMayBeSilentlyOverwritten"
        ] = True
        first["schemaCompatibilityBoundary"]["schemaVersion"] = "2.0"
        first["capabilities"]["performsNormalization"] = True
        first["injected"] = "mutated"

        second = self.build_contract()

        self.assertNotIn(
            "mutated", second["destructiveCanonicalizationPreservation"]["examples"]
        )
        self.assertIs(
            second["destructiveCanonicalizationPreservation"][
                "originalMayBeSilentlyOverwritten"
            ],
            False,
        )
        self.assertEqual(second["schemaCompatibilityBoundary"]["schemaVersion"], "1.0")
        self.assertIs(second["capabilities"]["performsNormalization"], False)
        self.assertNotIn("injected", second)

    def test_mutation_does_not_leak_to_module_level_constants(self) -> None:
        metadata = self.build_contract()

        metadata["fieldCategories"]["contractRelativePathEvidence"]["fields"].append(
            "mutated"
        )
        metadata["stringRules"]["conceptOverloadingForbidden"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS,
            ("sourceDocument", "nodes[].documentPath"),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION, "1.0"
        )

    # -- import safety ----------------------------------------------------------

    def test_import_and_call_do_not_require_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()
            module.build_reference_traversal_normalization_contract()

        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)

    def test_import_safety_subprocess_does_not_trigger_blocked_imports(self) -> None:
        script = (
            "import sys\n"
            "sys.modules['FreeCAD'] = None\n"
            "sys.modules['FreeCADGui'] = None\n"
            "sys.modules['freecad'] = None\n"
            "sys.modules['Import'] = None\n"
            "sys.modules['TechDrawGui'] = None\n"
            "import builtins\n"
            "guarded = {'FreeCAD', 'FreeCADGui', 'freecad', 'Import', 'TechDrawGui'}\n"
            "original_import = builtins.__import__\n"
            "def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):\n"
            "    root = name.split('.', 1)[0]\n"
            "    if root in guarded:\n"
            "        raise AssertionError(root + ' must not be imported')\n"
            "    return original_import(name, globals, locals, fromlist, level)\n"
            "builtins.__import__ = guarded_import\n"
            "from parametron_freecad.runtime.reference_traversal_output_contract import ("
            "    build_reference_traversal_normalization_contract,"
            ")\n"
            "metadata = build_reference_traversal_normalization_contract()\n"
            "assert isinstance(metadata, dict)\n"
            "print('OK')\n"
        )

        result = __import__("subprocess").run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "OK")


class ReferenceTraversalNormalizationContractCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_helper_mutates_no_caller_provided_object(self) -> None:
        node = _node()
        edge = _edge()
        diagnostic = _diagnostic()

        self.contract.build_reference_traversal_normalization_contract()

        self.assertEqual(node, _node())
        self.assertEqual(edge, _edge())
        self.assertEqual(diagnostic, _diagnostic())

    def test_helper_writes_no_file_and_creates_no_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            before = set(os.listdir(tmp_dir))

            with mock.patch.object(os, "getcwd", return_value=tmp_dir):
                self.contract.build_reference_traversal_normalization_contract()

            after = set(os.listdir(tmp_dir))

        self.assertEqual(before, after)

    def test_raw_payload_construction_unaffected_by_calling_the_helper(self) -> None:
        before = _build_payload(self.contract)

        self.contract.build_reference_traversal_normalization_contract()

        after = _build_payload(self.contract)

        self.assertEqual(before, after)

    def test_semantic_node_identity_key_construction_unaffected(self) -> None:
        before = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            document_path="assembly.FCStd",
            object_name="Body",
        )

        self.contract.build_reference_traversal_normalization_contract()

        after = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            document_path="assembly.FCStd",
            object_name="Body",
        )

        self.assertEqual(before, after)

    def test_semantic_edge_identity_key_construction_and_deduplication_unaffected(
        self,
    ) -> None:
        source_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
            document_path="assembly.FCStd",
        )
        target_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            document_path="assembly.FCStd",
            object_name="Body",
        )
        edge_kind = (
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE
        )

        before_key = self.contract.build_reference_traversal_semantic_edge_identity_key(
            source_node_key=source_key, target_node_key=target_key, kind=edge_kind
        )
        before_dedup = (
            self.contract.deduplicate_reference_traversal_semantic_edge_identity_keys(
                [before_key, before_key]
            )
        )

        self.contract.build_reference_traversal_normalization_contract()

        after_key = self.contract.build_reference_traversal_semantic_edge_identity_key(
            source_node_key=source_key, target_node_key=target_key, kind=edge_kind
        )
        after_dedup = (
            self.contract.deduplicate_reference_traversal_semantic_edge_identity_keys(
                [after_key, after_key]
            )
        )

        self.assertEqual(before_key, after_key)
        self.assertEqual(before_dedup, after_dedup)
        self.assertEqual(len(after_dedup), 1)

    def test_node_and_edge_ordering_output_unaffected(self) -> None:
        nodes = [
            _node(id="node-b", document_path="b.FCStd"),
            _node(id="node-a", document_path="a.FCStd"),
        ]
        edges = [
            _edge(source="node-b", target="node-a"),
            _edge(source="node-a", target="node-b"),
        ]

        before_nodes = self.contract.order_reference_traversal_nodes(nodes)
        before_edges = self.contract.order_reference_traversal_edges(edges)

        self.contract.build_reference_traversal_normalization_contract()

        after_nodes = self.contract.order_reference_traversal_nodes(nodes)
        after_edges = self.contract.order_reference_traversal_edges(edges)

        self.assertEqual(before_nodes, after_nodes)
        self.assertEqual(before_edges, after_edges)

    def test_helper_changes_no_module_level_public_constant(self) -> None:
        before = {
            "schema_version": self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
            "defined_states": self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES,
            "node_order_fields": self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS,
            "edge_order_fields": self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS,
            "emitted_path_fields": self.contract.REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS,
        }

        self.contract.build_reference_traversal_normalization_contract()

        after = {
            "schema_version": self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
            "defined_states": self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES,
            "node_order_fields": self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS,
            "edge_order_fields": self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS,
            "emitted_path_fields": self.contract.REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS,
        }

        self.assertEqual(before, after)


class ReferenceTraversalSemanticOutputExclusionConstantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()

    def test_semantic_output_exclusion_category_constants_are_distinct_nonempty_strings(
        self,
    ) -> None:
        constants = [
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS,
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_REQUEST_IDS,
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_ACTORS,
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_PROCESS_RUNTIME_IDENTITIES,
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS,
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER,
        ]

        for value in constants:
            with self.subTest(value=value):
                self.assertIsInstance(value, str)
                self.assertTrue(value)
        self.assertEqual(len(constants), len(set(constants)))

    def test_semantic_output_exclusion_category_constants_use_documented_stable_values(
        self,
    ) -> None:
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS,
            "timestamps",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_REQUEST_IDS,
            "request_ids",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_ACTORS,
            "actors",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_PROCESS_RUNTIME_IDENTITIES,
            "process_runtime_identities",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS,
            "temporary_absolute_paths",
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER,
            "incidental_enumeration_order",
        )

    def test_semantic_output_exclusion_aggregate_vocabulary_is_an_immutable_tuple(
        self,
    ) -> None:
        aggregate = (
            self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS
        )

        self.assertIsInstance(aggregate, tuple)
        self.assertNotIsInstance(aggregate, list)
        with self.assertRaises(TypeError):
            aggregate[0] = "mutated"  # type: ignore[index]

    def test_semantic_output_exclusion_aggregate_vocabulary_has_exactly_six_entries(
        self,
    ) -> None:
        self.assertEqual(
            len(self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS),
            6,
        )

    def test_semantic_output_exclusion_aggregate_vocabulary_equals_the_six_category_constants(
        self,
    ) -> None:
        self.assertEqual(
            set(self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS),
            {
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS,
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_REQUEST_IDS,
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_ACTORS,
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_PROCESS_RUNTIME_IDENTITIES,
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS,
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER,
            },
        )

    def test_semantic_output_exclusion_aggregate_vocabulary_declared_order_is_not_sorted_in_this_test(
        self,
    ) -> None:
        # The declared order below is copied verbatim from the contract, not
        # produced by sorting, because declaration order is part of the
        # contract itself.
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS,
            (
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS,
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_REQUEST_IDS,
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_ACTORS,
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_PROCESS_RUNTIME_IDENTITIES,
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS,
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER,
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS,
            (
                "timestamps",
                "request_ids",
                "actors",
                "process_runtime_identities",
                "temporary_absolute_paths",
                "incidental_enumeration_order",
            ),
        )


class ReferenceTraversalSemanticOutputExclusionPublicApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_semantic_output_exclusion_contract
        )

    def test_semantic_output_exclusion_helper_is_publicly_exported_and_callable(
        self,
    ) -> None:
        self.assertIn(
            "build_reference_traversal_semantic_output_exclusion_contract",
            self.contract.__all__,
        )
        self.assertTrue(callable(self.build_contract))

    def test_semantic_output_exclusion_export_does_not_leak_a_private_helper_name(
        self,
    ) -> None:
        self.assertFalse(
            hasattr(
                self.contract,
                "_build_reference_traversal_semantic_output_exclusion_contract",
            )
        )
        for name in self.contract.__all__:
            self.assertFalse(name.startswith("_"), name)

    def test_semantic_output_exclusion_helper_signature_requires_no_arguments(
        self,
    ) -> None:
        import inspect

        signature = inspect.signature(self.build_contract)
        self.assertEqual(list(signature.parameters), [])

    def test_semantic_output_exclusion_helper_returns_plain_dict(self) -> None:
        metadata = self.build_contract()

        self.assertIsInstance(metadata, dict)

    def test_semantic_output_exclusion_metadata_contains_documented_top_level_keys(
        self,
    ) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            set(metadata),
            {
                "exclusionCategories",
                "appliesTo",
                "futureRuntimeAndSerializationRule",
                "exclusions",
                "operationalMetadataPlacement",
                "compatibility",
                "capabilities",
            },
        )

    def test_semantic_output_exclusion_metadata_contains_all_six_exclusions_in_order(
        self,
    ) -> None:
        metadata = self.build_contract()

        self.assertEqual(
            metadata["exclusionCategories"],
            list(self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS),
        )
        self.assertEqual(
            set(metadata["exclusions"]),
            set(self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS),
        )

    def test_semantic_output_exclusion_metadata_returns_only_json_leaf_types(
        self,
    ) -> None:
        metadata = self.build_contract()

        _assert_only_json_leaf_types(self, metadata)

    def test_semantic_output_exclusion_metadata_returns_no_runtime_objects(
        self,
    ) -> None:
        import enum
        from pathlib import Path as PathType
        from types import MappingProxyType

        def _walk(value: object) -> None:
            self.assertNotIsInstance(value, (tuple, set, frozenset, bytes))
            self.assertNotIsInstance(value, PathType)
            self.assertNotIsInstance(value, enum.Enum)
            self.assertNotIsInstance(value, MappingProxyType)
            self.assertFalse(is_dataclass(value) and not isinstance(value, type))
            if isinstance(value, dict):
                for item in value.values():
                    _walk(item)
            elif isinstance(value, list):
                for item in value:
                    _walk(item)

        _walk(self.build_contract())


class ReferenceTraversalSemanticOutputExclusionTimestampTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        metadata = self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        self.category = metadata["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS
        ]

    def test_semantic_output_exclusion_timestamp_examples_cover_operational_cases(
        self,
    ) -> None:
        joined = " ".join(self.category["examples"]).lower()

        self.assertIn("request time", joined)
        self.assertIn("start time", joined)
        self.assertIn("completion time", joined)
        self.assertIn("wall-clock time", joined)
        self.assertIn("generated-at", joined)
        self.assertIn("filesystem modification time", joined)

    def test_semantic_output_exclusion_timestamp_is_excluded_from_semantic_surfaces(
        self,
    ) -> None:
        joined = " ".join(self.category["excludedFrom"]).lower()

        self.assertIn("semantic node identity", joined)
        self.assertIn("semantic edge identity", joined)
        self.assertIn("hashes or fingerprints", joined)
        self.assertIn("deduplication", joined)
        self.assertIn("total ordering", joined)
        self.assertIn("sequence assignment", joined)

    def test_semantic_output_exclusion_timestamp_does_not_claim_a_field_hash_or_active_hashing(
        self,
    ) -> None:
        self.assertIs(self.category["timestampFieldAddedToSchema1.0"], False)

        node_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }
        edge_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }
        self.assertFalse(any("time" in f for f in node_fields))
        self.assertFalse(any("time" in f for f in edge_fields))
        self.assertFalse(hasattr(self.contract, "hash_reference_traversal_output"))
        self.assertFalse(
            hasattr(self.contract, "build_reference_traversal_semantic_hash")
        )


class ReferenceTraversalSemanticOutputExclusionRequestIdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        metadata = self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        self.category = metadata["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_REQUEST_IDS
        ]

    def test_semantic_output_exclusion_request_id_examples_cover_request_local_identifiers(
        self,
    ) -> None:
        joined = " ".join(self.category["examples"]).lower()

        self.assertIn("request identifiers", joined)
        self.assertIn("invocation identifiers", joined)
        self.assertIn("correlation identifiers", joined)
        self.assertIn("tracing identifiers", joined)
        self.assertIn("request-local execution-attempt identifiers", joined)

    def test_semantic_output_exclusion_request_id_is_excluded_from_semantic_surfaces(
        self,
    ) -> None:
        joined = " ".join(self.category["excludedFrom"]).lower()

        self.assertIn("semantic node identity", joined)
        self.assertIn("semantic edge identity", joined)
        self.assertIn("hashes or fingerprints", joined)
        self.assertIn("deduplication", joined)
        self.assertIn("total ordering", joined)
        self.assertIn("sequence assignment", joined)

    def test_semantic_output_exclusion_request_id_is_not_copied_into_schema_1_0(
        self,
    ) -> None:
        self.assertIs(self.category["copiedIntoSemanticGraphIdentifiers"], False)

        node_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }
        edge_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }
        for forbidden in ("request_id", "invocation_id", "correlation_id", "trace_id"):
            self.assertNotIn(forbidden, node_fields)
            self.assertNotIn(forbidden, edge_fields)
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION, "1.0"
        )


class ReferenceTraversalSemanticOutputExclusionActorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        metadata = self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        self.category = metadata["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_ACTORS
        ]

    def test_semantic_output_exclusion_actor_examples_cover_documented_actor_concepts(
        self,
    ) -> None:
        joined = " ".join(self.category["examples"]).lower()

        self.assertIn("user", joined)
        self.assertIn("service", joined)
        self.assertIn("caller", joined)
        self.assertIn("operator", joined)
        self.assertIn("audit actor", joined)

    def test_semantic_output_exclusion_actor_is_excluded_from_semantic_surfaces(
        self,
    ) -> None:
        joined = " ".join(self.category["excludedFrom"]).lower()

        self.assertIn("semantic node identity", joined)
        self.assertIn("semantic edge identity", joined)

    def test_semantic_output_exclusion_actor_identity_belongs_on_operational_surfaces(
        self,
    ) -> None:
        self.assertIs(self.category["belongsInOperationalSurfaces"], True)

    def test_semantic_output_exclusion_helper_implements_no_audit_trace_or_execution_writer(
        self,
    ) -> None:
        self.assertFalse(hasattr(self.contract, "write_reference_traversal_audit_log"))
        self.assertFalse(hasattr(self.contract, "build_reference_traversal_trace_event"))
        self.assertFalse(
            hasattr(self.contract, "record_reference_traversal_execution_metadata")
        )


class ReferenceTraversalSemanticOutputExclusionProcessRuntimeIdentityTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        metadata = self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        self.category = metadata["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_PROCESS_RUNTIME_IDENTITIES
        ]

    def test_semantic_output_exclusion_process_runtime_identity_examples_cover_unstable_identities(
        self,
    ) -> None:
        joined = " ".join(self.category["examples"]).lower()

        self.assertIn("process id", joined)
        self.assertIn("thread id", joined)
        self.assertIn("id(...)", joined)
        self.assertIn("object identity", joined)
        self.assertIn("memory address", joined)
        self.assertIn("random uuid", joined)
        self.assertIn("random identifier", joined)
        self.assertIn("database auto-increment identifier", joined)
        self.assertIn("database insertion identifier", joined)

    def test_semantic_output_exclusion_process_runtime_identity_is_excluded_from_semantic_surfaces(
        self,
    ) -> None:
        joined = " ".join(self.category["excludedFrom"]).lower()

        self.assertIn("semantic node identity", joined)
        self.assertIn("semantic edge identity", joined)
        self.assertIn("hashes or fingerprints", joined)
        self.assertIn("deduplication", joined)
        self.assertIn("total ordering", joined)
        self.assertIn("sequence assignment", joined)

    def test_semantic_output_exclusion_process_runtime_identity_preserves_raw_schema_fields(
        self,
    ) -> None:
        self.assertEqual(
            self.category["existingRawIdentifierFields"],
            ["nodes[].id", "edges[].source", "edges[].target"],
        )
        self.assertIs(
            self.category["existingRawIdentifierFieldsRemovedOrRenamed"], False
        )
        self.assertIs(
            self.category["existingRawIdentifierFieldsMayUseExcludedIdentity"], False
        )

        node_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }
        edge_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }
        self.assertIn("id", node_fields)
        self.assertIn("source", edge_fields)
        self.assertIn("target", edge_fields)

    def test_semantic_output_exclusion_process_runtime_identity_does_not_invent_a_serialized_id_formula(
        self,
    ) -> None:
        self.assertIs(self.category["serializedNodeIdFormulaDefined"], False)
        self.assertIs(
            self.category["semanticNodeAndEdgeIdentityHelpersChanged"], False
        )

        before_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            document_path="assembly.FCStd",
            object_name="Body",
        )
        self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        after_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            document_path="assembly.FCStd",
            object_name="Body",
        )
        self.assertEqual(before_key, after_key)


class ReferenceTraversalSemanticOutputExclusionTemporaryAbsolutePathTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        metadata = self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        self.category = metadata["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS
        ]

    def test_semantic_output_exclusion_temporary_absolute_path_examples_cover_documented_cases(
        self,
    ) -> None:
        joined = " ".join(self.category["examples"]).lower()

        self.assertIn("working-copy paths", joined)
        self.assertIn("execution-attempt root paths", joined)
        self.assertIn("host-specific temporary directories", joined)
        self.assertIn("temporary output paths", joined)
        self.assertIn("current-working-directory-dependent paths", joined)

    def test_semantic_output_exclusion_temporary_absolute_path_is_excluded_from_semantic_surfaces(
        self,
    ) -> None:
        joined = " ".join(self.category["excludedFrom"]).lower()

        self.assertIn("semantic node identity", joined)
        self.assertIn("semantic edge identity", joined)

    def test_semantic_output_exclusion_temporary_absolute_path_is_distinguished_from_contract_relative_evidence(
        self,
    ) -> None:
        self.assertEqual(
            self.category["validSemanticPathEvidence"],
            [
                "canonical contract-relative sourceDocument",
                "canonical contract-relative nodes[].documentPath",
            ],
        )
        self.assertIs(
            self.category["temporaryAbsoluteFilesystemLocationsAreSemanticIdentity"],
            False,
        )
        self.assertIs(self.category["traversalOutputContainmentIsSeparate"], True)

        joined_separation = " ".join(
            self.category["contractRelativeCanonicalizationIsSeparateFrom"]
        ).lower()
        self.assertIn("filesystem resolution", joined_separation)
        self.assertIn("engine normalization", joined_separation)

    def test_semantic_output_exclusion_temporary_absolute_path_performs_no_path_work(
        self,
    ) -> None:
        self.assertIs(self.category["pathNormalizationOrResolutionPerformed"], False)
        self.assertIs(self.category["containmentCheckPerformed"], False)
        self.assertIs(self.category["filesystemInspectionPerformed"], False)
        self.assertIs(self.category["schemaExtensionPerformed"], False)

    def test_semantic_output_exclusion_temporary_absolute_path_helper_performs_no_filesystem_access(
        self,
    ) -> None:
        real_exists = Path.exists

        def _forbidden_exists(self_path: Path) -> bool:  # pragma: no cover - guard
            raise AssertionError(
                f"unexpected filesystem access during exclusion-contract build: {self_path}"
            )

        with mock.patch.object(Path, "exists", _forbidden_exists):
            metadata = (
                self.contract.build_reference_traversal_semantic_output_exclusion_contract()
            )

        self.assertIn("exclusions", metadata)
        self.assertIs(Path.exists, real_exists)


class ReferenceTraversalSemanticOutputExclusionEnumerationOrderTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        metadata = self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        self.category = metadata["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER
        ]

    def test_semantic_output_exclusion_enumeration_order_examples_cover_documented_sources(
        self,
    ) -> None:
        joined = " ".join(self.category["examples"]).lower()

        self.assertIn("freecad api return order", joined)
        self.assertIn("document.objects", joined)
        self.assertIn("filesystem directory order", joined)
        self.assertIn("dictionary or map iteration order", joined)
        self.assertIn("database insertion order", joined)
        self.assertIn("set iteration order", joined)
        self.assertIn("arbitrary discovery order", joined)
        self.assertIn("caller insertion order not explicitly approved", joined)

    def test_semantic_output_exclusion_enumeration_order_is_excluded_from_semantic_surfaces(
        self,
    ) -> None:
        joined = " ".join(self.category["excludedFrom"]).lower()

        self.assertIn("semantic node identity", joined)
        self.assertIn("semantic edge identity", joined)
        self.assertIn("hashes or fingerprints", joined)
        self.assertIn("deduplication", joined)
        self.assertIn("total ordering", joined)
        self.assertIn("sequence assignment", joined)

    def test_semantic_output_exclusion_enumeration_order_defers_to_authoritative_ordering_helpers(
        self,
    ) -> None:
        joined = " ".join(self.category["authoritativeOrderingHelpers"]).lower()

        self.assertIn("node total-order helper", joined)
        self.assertIn("edge total-order helper", joined)
        self.assertIn("diagnostic total-order helper", joined)
        self.assertIn("unresolved-entry total-order helper", joined)

        self.assertIs(
            self.category["orderingAppliedBeforeZeroBasedSequenceAssignment"], True
        )
        self.assertIs(
            self.category["contractDefinedSequenceIsPermittedSerializationEvidence"],
            True,
        )

    def test_semantic_output_exclusion_enumeration_order_does_not_determine_final_order_or_sequence(
        self,
    ) -> None:
        self.assertIs(
            self.category["incidentalInputOrderDeterminesFinalOrderOrSequence"], False
        )

    def test_semantic_output_exclusion_enumeration_order_helper_performs_no_sorting_itself(
        self,
    ) -> None:
        self.assertIs(self.category["sortingExecutedByThisHelper"], False)
        self.assertIs(self.category["existingOrderingKeysChanged"], False)

    def test_semantic_output_exclusion_enumeration_order_does_not_claim_real_traversal_already_applies_it(
        self,
    ) -> None:
        rule = self.category["futureTraversalRule"].lower()

        self.assertIn("collect evidence independently", rule)
        self.assertNotIn("already applies", rule)
        self.assertNotIn("real freecad traversal", rule)

    def test_semantic_output_exclusion_enumeration_order_existing_ordering_helpers_remain_authoritative(
        self,
    ) -> None:
        nodes = [
            _node(id="node-b", document_path="b.FCStd"),
            _node(id="node-a", document_path="a.FCStd"),
        ]
        before = self.contract.order_reference_traversal_nodes(nodes)

        self.contract.build_reference_traversal_semantic_output_exclusion_contract()

        after = self.contract.order_reference_traversal_nodes(nodes)
        self.assertEqual(before, after)


class ReferenceTraversalSemanticOutputExclusionApplicabilitySurfaceTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.metadata = (
            self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        )

    def test_semantic_output_exclusion_applies_to_lists_the_documented_semantic_surfaces(
        self,
    ) -> None:
        self.assertEqual(
            self.metadata["appliesTo"],
            [
                "semantic traversal output",
                "semantic node identity",
                "semantic edge identity",
                "semantic hashes or fingerprints",
                "semantic deduplication keys",
                "semantic total ordering",
                "deterministic sequence assignment",
            ],
        )

    def test_semantic_output_exclusion_hash_or_fingerprint_rule_is_future_facing_not_implemented(
        self,
    ) -> None:
        rule = self.metadata["futureRuntimeAndSerializationRule"].lower()

        self.assertIn("future", rule)
        self.assertIn("no semantic hash or fingerprint is", rule)
        self.assertIn("claimed to exist", rule)
        self.assertIs(self.metadata["capabilities"]["performsHashing"], False)


class ReferenceTraversalSemanticOutputExclusionOperationalPlacementTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        metadata = (
            self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        )
        self.placement = metadata["operationalMetadataPlacement"]

    def test_semantic_output_exclusion_operational_placement_key_set_is_exact(
        self,
    ) -> None:
        self.assertEqual(
            set(self.placement),
            {
                "permittedConceptualSurfaces",
                "surfacesOrFieldsAdded",
                "runtimeTraceContractChanged",
                "mustNotUseAsHiddenStorage",
                "deterministicTraversalOutcomeDiagnosticsRemainPermitted",
                "stackTracePolicyDefined",
                "runtimeDiagnosticCollectionImplemented",
            },
        )

    def test_semantic_output_exclusion_operational_metadata_belongs_on_documented_conceptual_surfaces(
        self,
    ) -> None:
        self.assertEqual(
            self.placement["permittedConceptualSurfaces"],
            [
                "execution surfaces",
                "runtime trace surfaces",
                "audit surfaces",
                "request/invocation envelopes",
            ],
        )
        self.assertIs(self.placement["surfacesOrFieldsAdded"], False)
        self.assertIs(self.placement["runtimeTraceContractChanged"], False)

    def test_semantic_output_exclusion_forbids_hiding_operational_values_in_unrelated_semantic_fields(
        self,
    ) -> None:
        hidden_storage = self.placement["mustNotUseAsHiddenStorage"]

        for expected in (
            "labels",
            "diagnostics",
            "documentPath",
            "identifiers",
            "kinds",
            "states",
            "source fields",
            "target fields",
            "provenance fields",
        ):
            self.assertIn(expected, hidden_storage)

    def test_semantic_output_exclusion_does_not_ban_deterministic_traversal_diagnostics(
        self,
    ) -> None:
        self.assertIs(
            self.placement["deterministicTraversalOutcomeDiagnosticsRemainPermitted"],
            True,
        )

    def test_semantic_output_exclusion_defines_no_stack_trace_or_diagnostic_collection_policy(
        self,
    ) -> None:
        self.assertIs(self.placement["stackTracePolicyDefined"], False)
        self.assertIs(self.placement["runtimeDiagnosticCollectionImplemented"], False)


class ReferenceTraversalSemanticOutputExclusionCapabilityAndCompatibilityTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        metadata = (
            self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        )
        self.compatibility = metadata["compatibility"]
        self.capabilities = metadata["capabilities"]

    def test_semantic_output_exclusion_compatibility_key_set_is_exact(self) -> None:
        self.assertEqual(
            set(self.compatibility),
            {
                "schemaVersion",
                "payloadSchemaChanged",
                "serializedFieldAdded",
                "dataclassChanged",
                "semanticNodeIdentityKeyChanged",
                "semanticEdgeIdentityKeyChanged",
                "deduplicationRuleChanged",
                "totalOrderKeyChanged",
                "payloadBuilderBehaviorChanged",
            },
        )

    def test_semantic_output_exclusion_compatibility_schema_version_matches_production_constant(
        self,
    ) -> None:
        self.assertEqual(self.compatibility["schemaVersion"], "1.0")
        self.assertEqual(
            self.compatibility["schemaVersion"],
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
        )

    def test_semantic_output_exclusion_compatibility_booleans_disclose_no_behavior_change(
        self,
    ) -> None:
        compatibility = self.compatibility

        self.assertIs(compatibility["payloadSchemaChanged"], False)
        self.assertIs(compatibility["serializedFieldAdded"], False)
        self.assertIs(compatibility["dataclassChanged"], False)
        self.assertIs(compatibility["semanticNodeIdentityKeyChanged"], False)
        self.assertIs(compatibility["semanticEdgeIdentityKeyChanged"], False)
        self.assertIs(compatibility["deduplicationRuleChanged"], False)
        self.assertIs(compatibility["totalOrderKeyChanged"], False)
        self.assertIs(compatibility["payloadBuilderBehaviorChanged"], False)

    def test_semantic_output_exclusion_capability_key_set_is_exact(self) -> None:
        self.assertEqual(
            set(self.capabilities),
            {
                "definesSemanticOutputExclusionRules",
                "performsRealFreecadTraversal",
                "performsRuntimeClassification",
                "performsNormalization",
                "performsFilesystemInspection",
                "performsHashing",
                "performsDeduplication",
                "performsOrdering",
                "performsSerialization",
                "performsWriting",
                "performsRequestLoading",
                "performsRuntimeWiring",
                "performsEngineNormalizationOrVerification",
                "performsPdmPersistenceOrGraphBehavior",
            },
        )

    def test_semantic_output_exclusion_capabilities_disclose_metadata_only_boundary(
        self,
    ) -> None:
        capabilities = self.capabilities

        self.assertIs(capabilities["definesSemanticOutputExclusionRules"], True)
        self.assertIs(capabilities["performsRealFreecadTraversal"], False)
        self.assertIs(capabilities["performsRuntimeClassification"], False)
        self.assertIs(capabilities["performsNormalization"], False)
        self.assertIs(capabilities["performsFilesystemInspection"], False)
        self.assertIs(capabilities["performsHashing"], False)
        self.assertIs(capabilities["performsDeduplication"], False)
        self.assertIs(capabilities["performsOrdering"], False)
        self.assertIs(capabilities["performsSerialization"], False)
        self.assertIs(capabilities["performsWriting"], False)
        self.assertIs(capabilities["performsRequestLoading"], False)
        self.assertIs(capabilities["performsRuntimeWiring"], False)
        self.assertIs(
            capabilities["performsEngineNormalizationOrVerification"], False
        )
        self.assertIs(
            capabilities["performsPdmPersistenceOrGraphBehavior"], False
        )

    def test_semantic_output_exclusion_no_serialized_field_dataclass_or_identity_key_actually_changed(
        self,
    ) -> None:
        node_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }
        edge_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }
        diagnostic_fields = {
            f.name
            for f in dataclass_fields(self.contract.RawReferenceTraversalDiagnostic)
        }

        self.assertEqual(
            node_fields,
            {
                "id",
                "kind",
                "state",
                "document_path",
                "object_name",
                "label",
                "diagnostic",
            },
        )
        self.assertEqual(
            edge_fields, {"source", "target", "kind", "state", "diagnostic"}
        )
        self.assertEqual(
            diagnostic_fields, {"severity", "code", "message", "stage"}
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION, "1.0"
        )


class ReferenceTraversalSemanticOutputExclusionDeterminismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_semantic_output_exclusion_contract
        )

    # -- canonical JSON and repeated-call determinism ------------------------

    def test_semantic_output_exclusion_metadata_serializes_with_dumps_canonical(
        self,
    ) -> None:
        metadata = self.build_contract()

        serialized = dumps_canonical(metadata)
        self.assertIsInstance(serialized, str)

    def test_semantic_output_exclusion_repeated_calls_serialize_to_identical_canonical_bytes(
        self,
    ) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(dumps_canonical(first), dumps_canonical(second))
        self.assertEqual(
            dumps_canonical(first).encode("utf-8"),
            dumps_canonical(second).encode("utf-8"),
        )

    def test_semantic_output_exclusion_dumps_canonical_does_not_mutate_metadata(
        self,
    ) -> None:
        import copy

        metadata = self.build_contract()
        snapshot = copy.deepcopy(metadata)

        dumps_canonical(metadata)

        self.assertEqual(metadata, snapshot)

    def test_semantic_output_exclusion_invocation_order_or_prior_mutation_does_not_affect_later_calls(
        self,
    ) -> None:
        first = self.build_contract()
        first["compatibility"]["payloadSchemaChanged"] = True

        second = self.build_contract()

        self.assertIs(second["compatibility"]["payloadSchemaChanged"], False)

    def test_semantic_output_exclusion_metadata_unaffected_by_operational_state(
        self,
    ) -> None:
        import uuid as uuid_module

        with mock.patch("time.time", return_value=999999999.0), mock.patch(
            "os.getpid", return_value=424242
        ), mock.patch("os.getcwd", return_value="/tmp/patched-cwd"), mock.patch.dict(
            os.environ, {"PARAMETRON_FREECAD_SEMANTIC_EXCLUSION_TEST": "patched"}
        ), mock.patch.object(
            uuid_module, "uuid4", return_value=uuid_module.UUID(int=0)
        ):
            patched = self.build_contract()

        unpatched = self.build_contract()

        self.assertEqual(dumps_canonical(patched), dumps_canonical(unpatched))

    # -- deep freshness and mutation isolation -------------------------------

    def test_semantic_output_exclusion_top_level_and_nested_sections_are_fresh_objects(
        self,
    ) -> None:
        first = self.build_contract()
        second = self.build_contract()

        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["exclusions"], second["exclusions"])
        self.assertIsNot(first["appliesTo"], second["appliesTo"])
        self.assertIsNot(
            first["operationalMetadataPlacement"],
            second["operationalMetadataPlacement"],
        )
        self.assertIsNot(first["compatibility"], second["compatibility"])
        self.assertIsNot(first["capabilities"], second["capabilities"])
        for category_name in self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS:
            self.assertIsNot(
                first["exclusions"][category_name],
                second["exclusions"][category_name],
            )
            self.assertIsNot(
                first["exclusions"][category_name]["examples"],
                second["exclusions"][category_name]["examples"],
            )
            self.assertIsNot(
                first["exclusions"][category_name]["excludedFrom"],
                second["exclusions"][category_name]["excludedFrom"],
            )

    def test_semantic_output_exclusion_mutating_exclusion_example_lists_does_not_leak(
        self,
    ) -> None:
        first = self.build_contract()

        for category_name in self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS:
            first["exclusions"][category_name]["examples"].append("mutated")
            first["exclusions"][category_name]["excludedFrom"].append("mutated")

        second = self.build_contract()

        for category_name in self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS:
            self.assertNotIn(
                "mutated", second["exclusions"][category_name]["examples"]
            )
            self.assertNotIn(
                "mutated", second["exclusions"][category_name]["excludedFrom"]
            )

    def test_semantic_output_exclusion_mutating_applicability_and_placement_lists_does_not_leak(
        self,
    ) -> None:
        first = self.build_contract()

        first["appliesTo"].append("mutated")
        first["operationalMetadataPlacement"]["permittedConceptualSurfaces"].append(
            "mutated"
        )
        first["operationalMetadataPlacement"]["mustNotUseAsHiddenStorage"].append(
            "mutated"
        )

        second = self.build_contract()

        self.assertNotIn("mutated", second["appliesTo"])
        self.assertNotIn(
            "mutated",
            second["operationalMetadataPlacement"]["permittedConceptualSurfaces"],
        )
        self.assertNotIn(
            "mutated",
            second["operationalMetadataPlacement"]["mustNotUseAsHiddenStorage"],
        )

    def test_semantic_output_exclusion_mutating_path_boundary_and_enumeration_order_lists_does_not_leak(
        self,
    ) -> None:
        first = self.build_contract()

        temporary_path_category = first["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS
        ]
        temporary_path_category["validSemanticPathEvidence"].append("mutated")
        temporary_path_category["contractRelativeCanonicalizationIsSeparateFrom"].append(
            "mutated"
        )

        enumeration_order_category = first["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER
        ]
        enumeration_order_category["authoritativeOrderingHelpers"].append("mutated")

        second = self.build_contract()

        second_temporary_path_category = second["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TEMPORARY_ABSOLUTE_PATHS
        ]
        self.assertNotIn(
            "mutated", second_temporary_path_category["validSemanticPathEvidence"]
        )
        self.assertNotIn(
            "mutated",
            second_temporary_path_category[
                "contractRelativeCanonicalizationIsSeparateFrom"
            ],
        )

        second_enumeration_order_category = second["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_INCIDENTAL_ENUMERATION_ORDER
        ]
        self.assertNotIn(
            "mutated",
            second_enumeration_order_category["authoritativeOrderingHelpers"],
        )

    def test_semantic_output_exclusion_mutating_capability_booleans_and_injected_keys_does_not_leak(
        self,
    ) -> None:
        first = self.build_contract()

        first["capabilities"]["performsHashing"] = True
        first["compatibility"]["payloadSchemaChanged"] = True
        first["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS
        ]["timestampFieldAddedToSchema1.0"] = True
        first["injected"] = "mutated"
        first["exclusions"]["injected"] = "mutated"

        second = self.build_contract()

        self.assertIs(second["capabilities"]["performsHashing"], False)
        self.assertIs(second["compatibility"]["payloadSchemaChanged"], False)
        self.assertIs(
            second["exclusions"][
                self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS
            ]["timestampFieldAddedToSchema1.0"],
            False,
        )
        self.assertNotIn("injected", second)
        self.assertNotIn("injected", second["exclusions"])

    def test_semantic_output_exclusion_mutation_does_not_leak_to_module_level_constants(
        self,
    ) -> None:
        metadata = self.build_contract()

        metadata["appliesTo"].append("mutated")
        metadata["exclusions"][
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS
        ]["examples"].append("mutated")

        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS,
            (
                "timestamps",
                "request_ids",
                "actors",
                "process_runtime_identities",
                "temporary_absolute_paths",
                "incidental_enumeration_order",
            ),
        )
        self.assertEqual(
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_OUTPUT_EXCLUSION_TIMESTAMPS,
            "timestamps",
        )

    # -- import safety --------------------------------------------------------

    def test_semantic_output_exclusion_import_and_call_do_not_require_freecad(
        self,
    ) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        for guarded_name in guarded_names:
            sys.modules.pop(guarded_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_reference_traversal_output_contract_module()
            result = module.build_reference_traversal_semantic_output_exclusion_contract()

        self.assertIsInstance(result, dict)
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)

    def test_semantic_output_exclusion_import_safety_subprocess_does_not_trigger_blocked_imports(
        self,
    ) -> None:
        script = (
            "import sys\n"
            "sys.modules['FreeCAD'] = None\n"
            "sys.modules['FreeCADGui'] = None\n"
            "sys.modules['freecad'] = None\n"
            "sys.modules['Import'] = None\n"
            "sys.modules['TechDrawGui'] = None\n"
            "import builtins\n"
            "guarded = {'FreeCAD', 'FreeCADGui', 'freecad', 'Import', 'TechDrawGui'}\n"
            "original_import = builtins.__import__\n"
            "def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):\n"
            "    root = name.split('.', 1)[0]\n"
            "    if root in guarded:\n"
            "        raise AssertionError(root + ' must not be imported')\n"
            "    return original_import(name, globals, locals, fromlist, level)\n"
            "builtins.__import__ = guarded_import\n"
            "from parametron_freecad.runtime.reference_traversal_output_contract import ("
            "    build_reference_traversal_semantic_output_exclusion_contract,"
            ")\n"
            "metadata = build_reference_traversal_semantic_output_exclusion_contract()\n"
            "assert isinstance(metadata, dict)\n"
            "print('OK')\n"
        )

        result = __import__("subprocess").run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "OK")

    # -- no filesystem or runtime side effects -------------------------------

    def test_semantic_output_exclusion_helper_writes_no_file_and_creates_no_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            before = set(os.listdir(tmp_dir))

            with mock.patch.object(os, "getcwd", return_value=tmp_dir):
                self.build_contract()

            after = set(os.listdir(tmp_dir))

        self.assertEqual(before, after)

    def test_semantic_output_exclusion_helper_changes_no_current_working_directory(
        self,
    ) -> None:
        before_cwd = os.getcwd()

        self.build_contract()

        self.assertEqual(os.getcwd(), before_cwd)

    def test_semantic_output_exclusion_helper_mutates_no_caller_provided_object(
        self,
    ) -> None:
        node = _node()
        edge = _edge()
        diagnostic = _diagnostic()

        self.build_contract()

        self.assertEqual(node, _node())
        self.assertEqual(edge, _edge())
        self.assertEqual(diagnostic, _diagnostic())

    def test_semantic_output_exclusion_helper_produces_no_stdout_or_stderr(
        self,
    ) -> None:
        import contextlib
        import io

        out = io.StringIO()
        err = io.StringIO()

        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.build_contract()

        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "")


class ReferenceTraversalSemanticOutputExclusionCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.build_contract = (
            self.contract.build_reference_traversal_semantic_output_exclusion_contract
        )

    # -- payload compatibility -------------------------------------------------

    def test_semantic_output_exclusion_representative_payload_is_unchanged_before_and_after(
        self,
    ) -> None:
        before = _build_payload(self.contract)

        self.build_contract()

        after = _build_payload(self.contract)

        self.assertEqual(before, after)
        self.assertEqual(self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION, "1.0")
        self.assertEqual(
            set(before),
            {
                "schemaVersion",
                "kind",
                "boundary",
                "operation",
                "status",
                "sourceDocument",
                "nodes",
                "edges",
                "diagnostics",
            },
        )
        for forbidden in (
            "timestamp",
            "requestId",
            "actor",
            "pid",
            "uuid",
            "temporaryRoot",
            "exclusions",
        ):
            self.assertNotIn(forbidden, before)

    def test_semantic_output_exclusion_dataclass_field_sets_are_unchanged(
        self,
    ) -> None:
        node_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalNode)
        }
        edge_fields = {
            f.name for f in dataclass_fields(self.contract.RawReferenceTraversalEdge)
        }
        diagnostic_fields = {
            f.name
            for f in dataclass_fields(self.contract.RawReferenceTraversalDiagnostic)
        }

        self.build_contract()

        self.assertEqual(
            node_fields,
            {
                "id",
                "kind",
                "state",
                "document_path",
                "object_name",
                "label",
                "diagnostic",
            },
        )
        self.assertEqual(
            edge_fields, {"source", "target", "kind", "state", "diagnostic"}
        )
        self.assertEqual(diagnostic_fields, {"severity", "code", "message", "stage"})

    def test_semantic_output_exclusion_canonical_payload_bytes_are_unchanged(
        self,
    ) -> None:
        before = dumps_canonical(_build_payload(self.contract))

        self.build_contract()

        after = dumps_canonical(_build_payload(self.contract))

        self.assertEqual(before, after)

    # -- semantic identity and deduplication compatibility ---------------------

    def test_semantic_output_exclusion_semantic_node_identity_keys_are_unaffected(
        self,
    ) -> None:
        cases = [
            {
                "kind": self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
                "document_path": "assembly.FCStd",
            },
            {
                "kind": self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
                "document_path": "assembly.FCStd",
                "object_name": "Body",
            },
            {
                "kind": self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_DOCUMENT,
                "document_path": "linked.FCStd",
            },
            {
                "kind": self.contract.REFERENCE_TRAVERSAL_NODE_KIND_EXTERNAL_FILE,
                "document_path": "linked.step",
            },
        ]
        before_keys = [
            self.contract.build_reference_traversal_semantic_node_identity_key(**case)
            for case in cases
        ]

        self.build_contract()

        after_keys = [
            self.contract.build_reference_traversal_semantic_node_identity_key(**case)
            for case in cases
        ]

        self.assertEqual(before_keys, after_keys)

    def test_semantic_output_exclusion_semantic_edge_identity_and_deduplication_are_unaffected(
        self,
    ) -> None:
        source_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
            document_path="assembly.FCStd",
        )
        target_key = self.contract.build_reference_traversal_semantic_node_identity_key(
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            document_path="assembly.FCStd",
            object_name="Body",
        )
        edge_kind = (
            self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE
        )

        before_forward = (
            self.contract.build_reference_traversal_semantic_edge_identity_key(
                source_node_key=source_key, target_node_key=target_key, kind=edge_kind
            )
        )
        before_reverse = (
            self.contract.build_reference_traversal_semantic_edge_identity_key(
                source_node_key=target_key, target_node_key=source_key, kind=edge_kind
            )
        )
        before_dedup = (
            self.contract.deduplicate_reference_traversal_semantic_edge_identity_keys(
                [before_forward, before_forward, before_reverse]
            )
        )

        self.build_contract()

        after_forward = (
            self.contract.build_reference_traversal_semantic_edge_identity_key(
                source_node_key=source_key, target_node_key=target_key, kind=edge_kind
            )
        )
        after_reverse = (
            self.contract.build_reference_traversal_semantic_edge_identity_key(
                source_node_key=target_key, target_node_key=source_key, kind=edge_kind
            )
        )
        after_dedup = (
            self.contract.deduplicate_reference_traversal_semantic_edge_identity_keys(
                [after_forward, after_forward, after_reverse]
            )
        )

        self.assertEqual(before_forward, after_forward)
        self.assertEqual(before_reverse, after_reverse)
        self.assertNotEqual(before_forward, before_reverse)
        self.assertEqual(before_dedup, after_dedup)
        self.assertEqual(len(after_dedup), 2)

    def test_semantic_output_exclusion_does_not_mutate_identity_constants_or_supported_kinds(
        self,
    ) -> None:
        before_node_fields = (
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS
        )
        before_edge_kinds = (
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS
        )

        self.build_contract()

        self.assertEqual(
            before_node_fields,
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_NODE_IDENTITY_FIELDS,
        )
        self.assertEqual(
            before_edge_kinds,
            self.contract.REFERENCE_TRAVERSAL_SEMANTIC_EDGE_IDENTITY_SUPPORTED_KINDS,
        )

    # -- ordering and sequence compatibility ------------------------------------

    def test_semantic_output_exclusion_node_edge_diagnostic_and_unresolved_ordering_are_unaffected(
        self,
    ) -> None:
        nodes = [
            _node(id="node-b", document_path="b.FCStd", state="missing"),
            _node(id="node-a", document_path="a.FCStd", state="resolved"),
        ]
        edges = [
            _edge(source="node-b", target="node-a", state="unresolved"),
            _edge(source="node-a", target="node-b", state="resolved"),
        ]
        diagnostics = [_diagnostic(stage="reference_scan"), _diagnostic(stage=None)]
        unresolved_entries = [
            _node(id="node-c", document_path="c.FCStd", state="missing"),
            _edge(source="node-d", target="node-e", state="unresolved"),
        ]

        before_nodes = self.contract.order_reference_traversal_nodes(nodes)
        before_edges = self.contract.order_reference_traversal_edges(edges)
        before_diagnostics = self.contract.order_reference_traversal_diagnostics(
            diagnostics
        )
        before_unresolved = self.contract.order_reference_traversal_unresolved_entries(
            unresolved_entries
        )
        before_payload = _build_payload(
            self.contract, nodes=nodes, edges=edges, diagnostics=diagnostics
        )

        self.build_contract()

        after_nodes = self.contract.order_reference_traversal_nodes(nodes)
        after_edges = self.contract.order_reference_traversal_edges(edges)
        after_diagnostics = self.contract.order_reference_traversal_diagnostics(
            diagnostics
        )
        after_unresolved = self.contract.order_reference_traversal_unresolved_entries(
            unresolved_entries
        )
        after_payload = _build_payload(
            self.contract, nodes=nodes, edges=edges, diagnostics=diagnostics
        )

        self.assertEqual(before_nodes, after_nodes)
        self.assertEqual(before_edges, after_edges)
        self.assertEqual(before_diagnostics, after_diagnostics)
        self.assertEqual(before_unresolved, after_unresolved)
        self.assertEqual(before_payload, after_payload)

    # -- normalization and containment compatibility -----------------------------

    def test_semantic_output_exclusion_normalization_contract_output_is_unaffected(
        self,
    ) -> None:
        before = self.contract.build_reference_traversal_normalization_contract()

        self.build_contract()

        after = self.contract.build_reference_traversal_normalization_contract()

        self.assertEqual(before, after)

    def test_semantic_output_exclusion_output_containment_resolution_is_unaffected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            before = self.contract.resolve_reference_traversal_output_path(
                working_copy=root, output_path="result.json"
            )

            self.build_contract()

            after = self.contract.resolve_reference_traversal_output_path(
                working_copy=root, output_path="result.json"
            )

        self.assertEqual(before, after)

    def test_semantic_output_exclusion_containment_contract_metadata_is_unaffected(
        self,
    ) -> None:
        before = self.contract.build_reference_traversal_output_containment_contract()

        self.build_contract()

        after = self.contract.build_reference_traversal_output_containment_contract()

        self.assertEqual(before, after)

    def test_semantic_output_exclusion_helper_changes_no_module_level_public_constant(
        self,
    ) -> None:
        before = {
            "schema_version": self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
            "defined_states": self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES,
            "node_order_fields": self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS,
            "edge_order_fields": self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS,
            "emitted_path_fields": self.contract.REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS,
            "defined_exclusions": (
                self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS
            ),
        }

        self.build_contract()

        after = {
            "schema_version": self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
            "defined_states": self.contract.REFERENCE_TRAVERSAL_DEFINED_STATES,
            "node_order_fields": self.contract.REFERENCE_TRAVERSAL_NODE_ORDER_FIELDS,
            "edge_order_fields": self.contract.REFERENCE_TRAVERSAL_EDGE_ORDER_FIELDS,
            "emitted_path_fields": self.contract.REFERENCE_TRAVERSAL_EMITTED_PATH_FIELDS,
            "defined_exclusions": (
                self.contract.REFERENCE_TRAVERSAL_DEFINED_SEMANTIC_OUTPUT_EXCLUSIONS
            ),
        }

        self.assertEqual(before, after)


class ReferenceTraversalOutputSerializationTests(unittest.TestCase):
    """Focused byte-level contract tests for serialize_reference_traversal_output.

    These tests prove deterministic in-memory serialized traversal bytes only;
    they do not exercise a traversal output writer, filesystem persistence, or
    real FreeCAD traversal.
    """

    def setUp(self) -> None:
        self.contract = _import_reference_traversal_output_contract_module()
        self.serialize = self.contract.serialize_reference_traversal_output

    def _node_alpha(self):
        return _node(
            id="node-alpha",
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_DOCUMENT,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            document_path="Sub Dir/assembly çağrı.FCStd",
            object_name=None,
            label=None,
            diagnostic=None,
        )

    def _node_beta(self):
        return _node(
            id="node-beta",
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_MISSING,
            document_path="assembly çağrı.FCStd",
            object_name="  Body 東京  ",
            label="Label With Spaces",
            diagnostic="Inline Diagnostic çağrı",
        )

    def _edge_alpha(self):
        return _edge(
            source="node-alpha",
            target="node-beta",
            kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            diagnostic=None,
        )

    def _edge_beta(self):
        return _edge(
            source="node-beta",
            target="node-alpha",
            kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_EXTERNAL_FILE_REFERENCE,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_UNRESOLVED,
            diagnostic="Edge Diagnostic 東京",
        )

    def _diagnostic_alpha(self):
        return _diagnostic(
            severity=self.contract.REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR,
            code="alpha_code",
            message="Alpha message çağrı",
            stage=None,
        )

    def _diagnostic_beta(self):
        return _diagnostic(
            severity="warning",
            code="beta_code",
            message="Beta message 東京",
            stage="reference_scan",
        )

    def _kwargs(self, **overrides):
        kwargs = {
            "boundary": self.contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
            "operation": self.contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
            "status": self.contract.REFERENCE_TRAVERSAL_STATUS_PARTIAL,
            "source_document": "root çağrı.FCStd",
            "nodes": [self._node_alpha(), self._node_beta()],
            "edges": [self._edge_alpha(), self._edge_beta()],
            "diagnostics": [self._diagnostic_alpha(), self._diagnostic_beta()],
        }
        kwargs.update(overrides)
        return kwargs

    # -- exact public signature ------------------------------------------

    def test_signature_matches_documented_keyword_only_contract(self) -> None:
        import inspect

        signature = inspect.signature(self.serialize)

        self.assertEqual(
            set(signature.parameters),
            {
                "boundary",
                "operation",
                "status",
                "source_document",
                "nodes",
                "edges",
                "diagnostics",
            },
        )
        for name, parameter in signature.parameters.items():
            self.assertEqual(parameter.kind, inspect.Parameter.KEYWORD_ONLY, name)
        for name in (
            "boundary",
            "operation",
            "status",
            "source_document",
            "nodes",
            "edges",
        ):
            self.assertIs(
                signature.parameters[name].default, inspect.Parameter.empty
            )
        self.assertEqual(signature.parameters["diagnostics"].default, ())

    def test_positional_arguments_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            self.serialize(
                self.contract.REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
                self.contract.REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
                self.contract.REFERENCE_TRAVERSAL_STATUS_SUCCEEDED,
                "assembly.FCStd",
                [],
                [],
            )

    # -- canonical payload equivalence -------------------------------------

    def test_serialized_bytes_exactly_match_canonical_payload_builder_output(
        self,
    ) -> None:
        kwargs = self._kwargs()
        expected = dumps_canonical(
            self.contract.build_reference_traversal_output_payload(**kwargs)
        ).encode("utf-8")

        actual = self.serialize(**kwargs)

        self.assertEqual(actual, expected)

    def test_diagnostics_default_matches_payload_builder_default(self) -> None:
        kwargs = self._kwargs()
        del kwargs["diagnostics"]

        expected = dumps_canonical(
            self.contract.build_reference_traversal_output_payload(**kwargs)
        ).encode("utf-8")

        actual = self.serialize(**kwargs)

        self.assertEqual(actual, expected)

    # -- return and encoding behavior --------------------------------------

    def test_output_is_utf8_bytes_without_bom_or_crlf_with_single_trailing_lf(
        self,
    ) -> None:
        result = self.serialize(**self._kwargs())

        self.assertIsInstance(result, bytes)
        result.decode("utf-8")
        self.assertFalse(result.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r\n", result)
        self.assertTrue(result.endswith(b"\n"))
        self.assertFalse(result.endswith(b"\n\n"))

    def test_output_uses_compact_canonical_json_formatting(self) -> None:
        result = self.serialize(**self._kwargs())
        text = result.decode("utf-8")

        self.assertNotIn(": ", text)
        self.assertNotIn(", ", text)

    def test_non_ascii_values_remain_direct_utf8_without_escape_sequences(
        self,
    ) -> None:
        result = self.serialize(**self._kwargs())
        text = result.decode("utf-8")

        self.assertIn("çağrı", text)
        self.assertIn("東京", text)
        self.assertNotIn("\\u", text)

    # -- repeated-call byte equality ----------------------------------------

    def test_repeated_calls_with_same_input_objects_produce_equal_bytes(
        self,
    ) -> None:
        kwargs = self._kwargs()

        first = self.serialize(**kwargs)
        second = self.serialize(**kwargs)

        self.assertEqual(first, second)

    def test_repeated_calls_with_freshly_built_equivalent_inputs_produce_equal_bytes(
        self,
    ) -> None:
        first = self.serialize(**self._kwargs())
        second = self.serialize(**self._kwargs())

        self.assertEqual(first, second)

    # -- incidental enumeration-order independence ---------------------------

    def test_reordered_equivalent_nodes_edges_and_diagnostics_serialize_identically(
        self,
    ) -> None:
        forward = self.serialize(**self._kwargs())
        reordered = self.serialize(
            **self._kwargs(
                nodes=[self._node_beta(), self._node_alpha()],
                edges=[self._edge_beta(), self._edge_alpha()],
                diagnostics=[self._diagnostic_beta(), self._diagnostic_alpha()],
            )
        )

        self.assertEqual(forward, reordered)

    # -- existing ordering and sequence assignment ---------------------------

    def test_decoded_output_preserves_ordering_and_independent_zero_based_sequences(
        self,
    ) -> None:
        import json

        kwargs = self._kwargs()
        expected_payload = self.contract.build_reference_traversal_output_payload(
            **kwargs
        )

        decoded = json.loads(self.serialize(**kwargs))

        self.assertEqual(decoded["nodes"], expected_payload["nodes"])
        self.assertEqual(decoded["edges"], expected_payload["edges"])
        self.assertEqual(decoded["diagnostics"], expected_payload["diagnostics"])
        self.assertEqual(
            [node["sequence"] for node in decoded["nodes"]],
            list(range(len(decoded["nodes"]))),
        )
        self.assertEqual(
            [edge["sequence"] for edge in decoded["edges"]],
            list(range(len(decoded["edges"]))),
        )
        self.assertEqual(
            [diagnostic["sequence"] for diagnostic in decoded["diagnostics"]],
            list(range(len(decoded["diagnostics"]))),
        )

    # -- duplicate preservation ----------------------------------------------

    def test_duplicate_raw_evidence_is_preserved_not_deduplicated(self) -> None:
        import json

        duplicate_node = self._node_alpha()
        duplicate_edge = self._edge_alpha()
        duplicate_diagnostic = self._diagnostic_alpha()

        result = self.serialize(
            **self._kwargs(
                nodes=[duplicate_node, duplicate_node],
                edges=[duplicate_edge, duplicate_edge],
                diagnostics=[duplicate_diagnostic, duplicate_diagnostic],
            )
        )
        decoded = json.loads(result)

        self.assertEqual(len(decoded["nodes"]), 2)
        self.assertEqual(len(decoded["edges"]), 2)
        self.assertEqual(len(decoded["diagnostics"]), 2)

    # -- exact string preservation --------------------------------------

    def test_exact_string_values_are_preserved_verbatim(self) -> None:
        import json

        node = _node(
            id="Node-ID-MixedCase",
            kind=self.contract.REFERENCE_TRAVERSAL_NODE_KIND_OBJECT,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            document_path="Sub Dir/Assembly çağrı.FCStd",
            object_name="  Body 東京  ",
            label="Label With Spaces",
            diagnostic="Inline Diagnostic çağrı",
        )
        edge = _edge(
            source="Node-ID-MixedCase",
            target="Node-ID-MixedCase",
            kind=self.contract.REFERENCE_TRAVERSAL_EDGE_KIND_DOCUMENT_INTERNAL_REFERENCE,
            state=self.contract.REFERENCE_TRAVERSAL_STATE_RESOLVED,
            diagnostic="Edge Diagnostic  With  Spaces",
        )
        diagnostic = _diagnostic(
            severity="Warning",
            code="Structured_Code",
            message="Structured message with çağrı and 東京",
            stage="Request_Validation",
        )

        result = self.serialize(
            **self._kwargs(nodes=[node], edges=[edge], diagnostics=[diagnostic])
        )
        decoded = json.loads(result)

        self.assertEqual(decoded["nodes"][0]["id"], "Node-ID-MixedCase")
        self.assertEqual(
            decoded["nodes"][0]["documentPath"], "Sub Dir/Assembly çağrı.FCStd"
        )
        self.assertEqual(decoded["nodes"][0]["objectName"], "  Body 東京  ")
        self.assertEqual(decoded["nodes"][0]["label"], "Label With Spaces")
        self.assertEqual(decoded["nodes"][0]["diagnostic"], "Inline Diagnostic çağrı")
        self.assertEqual(
            decoded["edges"][0]["diagnostic"], "Edge Diagnostic  With  Spaces"
        )
        self.assertEqual(decoded["diagnostics"][0]["severity"], "Warning")
        self.assertEqual(decoded["diagnostics"][0]["code"], "Structured_Code")
        self.assertEqual(
            decoded["diagnostics"][0]["message"],
            "Structured message with çağrı and 東京",
        )
        self.assertEqual(decoded["diagnostics"][0]["stage"], "Request_Validation")

    # -- input mutation isolation --------------------------------------------

    def test_serialization_does_not_mutate_input_list_or_contents(self) -> None:
        nodes = [self._node_alpha(), self._node_beta()]
        edges = [self._edge_alpha(), self._edge_beta()]
        diagnostics = [self._diagnostic_alpha(), self._diagnostic_beta()]
        nodes_snapshot = list(nodes)
        edges_snapshot = list(edges)
        diagnostics_snapshot = list(diagnostics)

        self.serialize(**self._kwargs(nodes=nodes, edges=edges, diagnostics=diagnostics))

        self.assertEqual(nodes, nodes_snapshot)
        self.assertEqual(edges, edges_snapshot)
        self.assertEqual(diagnostics, diagnostics_snapshot)

    def test_serialization_accepts_tuple_inputs_without_mutation(self) -> None:
        nodes = (self._node_alpha(), self._node_beta())
        edges = (self._edge_alpha(), self._edge_beta())
        diagnostics = (self._diagnostic_alpha(), self._diagnostic_beta())

        self.serialize(**self._kwargs(nodes=nodes, edges=edges, diagnostics=diagnostics))

        self.assertEqual(nodes, (self._node_alpha(), self._node_beta()))
        self.assertEqual(edges, (self._edge_alpha(), self._edge_beta()))
        self.assertEqual(
            diagnostics, (self._diagnostic_alpha(), self._diagnostic_beta())
        )

    def test_frozen_dataclass_field_values_remain_unmutated_after_serialization(
        self,
    ) -> None:
        node = self._node_alpha()
        edge = self._edge_alpha()
        diagnostic = self._diagnostic_alpha()
        node_before = (
            node.id,
            node.kind,
            node.state,
            node.document_path,
            node.object_name,
            node.label,
            node.diagnostic,
        )
        edge_before = (edge.source, edge.target, edge.kind, edge.state, edge.diagnostic)
        diagnostic_before = (
            diagnostic.severity,
            diagnostic.code,
            diagnostic.message,
            diagnostic.stage,
        )

        self.serialize(**self._kwargs(nodes=[node], edges=[edge], diagnostics=[diagnostic]))

        self.assertEqual(
            (
                node.id,
                node.kind,
                node.state,
                node.document_path,
                node.object_name,
                node.label,
                node.diagnostic,
            ),
            node_before,
        )
        self.assertEqual(
            (edge.source, edge.target, edge.kind, edge.state, edge.diagnostic),
            edge_before,
        )
        self.assertEqual(
            (
                diagnostic.severity,
                diagnostic.code,
                diagnostic.message,
                diagnostic.stage,
            ),
            diagnostic_before,
        )

    # -- validation/error preservation ---------------------------------------

    def test_invalid_top_level_and_sequence_inputs_raise_output_contract_error(
        self,
    ) -> None:
        invalid_overrides = (
            {"boundary": ""},
            {"operation": 123},
            {"status": ""},
            {"source_document": ""},
            {"nodes": "not-a-sequence"},
            {"edges": [object()]},
            {"diagnostics": [object()]},
        )

        for overrides in invalid_overrides:
            with self.subTest(overrides=overrides):
                with self.assertRaises(
                    self.contract.ReferenceTraversalOutputContractError
                ):
                    self.serialize(**self._kwargs(**overrides))

    def test_invalid_node_state_raises_output_contract_error(self) -> None:
        node = self._node_alpha()
        object.__setattr__(node, "state", "not-a-real-state")

        with self.assertRaises(self.contract.ReferenceTraversalOutputContractError):
            self.serialize(**self._kwargs(nodes=[node]))

    def test_invalid_edge_state_raises_output_contract_error(self) -> None:
        edge = self._edge_alpha()
        object.__setattr__(edge, "state", "not-a-real-state")

        with self.assertRaises(self.contract.ReferenceTraversalOutputContractError):
            self.serialize(**self._kwargs(edges=[edge]))

    def test_invalid_diagnostic_field_raises_output_contract_error(self) -> None:
        diagnostic = self._diagnostic_alpha()
        object.__setattr__(diagnostic, "message", "")

        with self.assertRaises(self.contract.ReferenceTraversalOutputContractError):
            self.serialize(**self._kwargs(diagnostics=[diagnostic]))

    # -- no filesystem side effects ------------------------------------------

    def test_serialization_performs_no_filesystem_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            before = set(os.listdir(tmp_dir))
            cwd = os.getcwd()
            try:
                os.chdir(tmp_dir)
                self.serialize(**self._kwargs())
            finally:
                os.chdir(cwd)

            self.assertEqual(set(os.listdir(tmp_dir)), before)

    # -- compatibility coverage ----------------------------------------------

    def test_serialized_payload_uses_existing_schema_version_and_field_names(
        self,
    ) -> None:
        import json

        decoded = json.loads(self.serialize(**self._kwargs()))

        self.assertEqual(
            decoded[self.contract.REFERENCE_TRAVERSAL_FIELD_SCHEMA_VERSION],
            self.contract.REFERENCE_TRAVERSAL_OUTPUT_SCHEMA_VERSION,
        )
        self.assertEqual(
            set(decoded),
            {
                self.contract.REFERENCE_TRAVERSAL_FIELD_SCHEMA_VERSION,
                self.contract.REFERENCE_TRAVERSAL_FIELD_KIND,
                self.contract.REFERENCE_TRAVERSAL_FIELD_BOUNDARY,
                self.contract.REFERENCE_TRAVERSAL_FIELD_OPERATION,
                self.contract.REFERENCE_TRAVERSAL_FIELD_STATUS,
                self.contract.REFERENCE_TRAVERSAL_FIELD_SOURCE_DOCUMENT,
                self.contract.REFERENCE_TRAVERSAL_FIELD_NODES,
                self.contract.REFERENCE_TRAVERSAL_FIELD_EDGES,
                self.contract.REFERENCE_TRAVERSAL_FIELD_DIAGNOSTICS,
            },
        )

    def test_serialization_does_not_alter_semantic_output_exclusion_contract_metadata(
        self,
    ) -> None:
        before = (
            self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        )

        self.serialize(**self._kwargs())

        after = (
            self.contract.build_reference_traversal_semantic_output_exclusion_contract()
        )

        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
