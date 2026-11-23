"""Canonical serialization tests for the GUI-free capture core."""

from __future__ import annotations

import copy
import json
import unittest
from typing import Any

from capture_support import empty_annotations, targetability, valid_mapping

from parametron_freecad.capture import (
    CaptureContractError,
    CaptureDocument,
    canonical_capture_bytes,
    canonical_capture_text,
)

_REGISTRIES = (
    "components",
    "features",
    "relationships",
    "parameterGroups",
    "parameters",
    "metadata",
)


def _scrambled_mapping() -> dict[str, Any]:
    payload = valid_mapping()

    payload["entities"]["components"].append(
        {
            "id": "cmp.extra",
            "kind": "part",
            "name": "Extra",
            "displayName": "Extra",
            "cadType": "Part::Box",
            "quantity": 1,
            "material": "",
            "identitySource": {
                "kind": "parent_scoped_path",
                "path": "cmp.root/Extra",
                "nativeRef": "Extra",
            },
            "stabilityClass": "stable",
            "targetability": targetability(),
            "annotations": empty_annotations(),
        }
    )

    payload["entities"]["features"].append(
        {
            "id": "fea.aaa.alpha",
            "componentId": "cmp.part",
            "name": "Alpha",
            "displayName": "Alpha",
            "cadType": "PartDesign::Pad",
            "identitySource": {
                "kind": "owner_scoped_key",
                "ownerScopedKey": "Alpha",
                "nativeRef": "Alpha",
            },
            "stabilityClass": "conditionally_stable",
            "targetability": targetability(),
            "annotations": empty_annotations(),
        }
    )

    payload["entities"]["relationships"] = [
        {
            "id": "rel.root.mount",
            "kind": "relationship",
            "componentId": "cmp.root",
            "name": "mount",
            "cadType": "App::FeaturePython",
            "endpoints": ["fea.enclosure.pad", "cmp.part"],
            "stabilityClass": "stable",
            "targetability": targetability(),
            "annotations": empty_annotations(),
        },
        {
            "id": "rel.aaa.first",
            "kind": "relationship",
            "componentId": "cmp.root",
            "name": "firstRel",
            "cadType": "App::FeaturePython",
            "endpoints": ["cmp.extra"],
            "stabilityClass": "stable",
            "targetability": targetability(),
            "annotations": empty_annotations(),
        },
    ]

    payload["entities"]["parameterGroups"].append(
        {
            "id": "grp.aaa.first",
            "ownerComponentId": "cmp.root",
            "name": "FirstGroup",
            "displayName": "First Group",
            "groupKind": "varset",
            "cadType": "App::VarSet",
            "observable": True,
            "writable": True,
            "identitySource": {
                "kind": "owner_scoped_key",
                "ownerScopedKey": "FirstGroup",
                "nativeRef": "FirstGroup",
            },
            "stabilityClass": "stable",
            "annotations": empty_annotations(),
        }
    )

    payload["entities"]["parameters"].append(
        {
            "id": "par.aaa.first",
            "ownerKind": "component",
            "ownerId": "cmp.root",
            "componentId": "cmp.root",
            "name": "firstParam",
            "displayName": "First Param",
            "cadType": "App::PropertyFloat",
            "valueType": "number",
            "observable": True,
            "writable": True,
            "currentValue": 1,
            "identitySource": {
                "kind": "owner_scoped_key",
                "ownerScopedKey": "firstParam",
                "nativeRef": "CaptureCore.firstParam",
            },
            "stabilityClass": "stable",
            "annotations": empty_annotations(),
        }
    )

    payload["entities"]["metadata"].append(
        {
            "id": "meta.aaa.first",
            "ownerKind": "component",
            "ownerId": "cmp.part",
            "componentId": "cmp.part",
            "key": "firstKey",
            "displayName": "First Key",
            "cadType": "App::PropertyString",
            "valueType": "string",
            "observable": True,
            "writable": True,
            "currentValue": "first",
            "identitySource": {
                "kind": "owner_scoped_key",
                "ownerScopedKey": "firstKey",
                "nativeRef": "Body.firstKey",
            },
            "stabilityClass": "stable",
            "annotations": empty_annotations(),
        }
    )

    payload["structure"]["nodes"] = [
        {
            "componentId": "cmp.part",
            "parentComponentId": "cmp.root",
            "children": [],
        },
        {
            "componentId": "cmp.root",
            "parentComponentId": "",
            "children": ["cmp.part", "cmp.extra"],
        },
        {
            "componentId": "cmp.extra",
            "parentComponentId": "cmp.root",
            "children": [],
        },
    ]

    return payload


class CanonicalOrderingTests(unittest.TestCase):
    def test_sorts_every_entity_registry_by_id(self) -> None:
        payload = _scrambled_mapping()

        result = json.loads(canonical_capture_bytes(payload))

        for registry in _REGISTRIES:
            with self.subTest(registry=registry):
                identifiers = [item["id"] for item in result["entities"][registry]]
                self.assertEqual(identifiers, sorted(identifiers))

    def test_sorts_structure_nodes_by_component_id(self) -> None:
        payload = _scrambled_mapping()

        result = json.loads(canonical_capture_bytes(payload))

        identifiers = [node["componentId"] for node in result["structure"]["nodes"]]
        self.assertEqual(identifiers, sorted(identifiers))
        self.assertEqual(identifiers, ["cmp.extra", "cmp.part", "cmp.root"])

    def test_sorts_child_lists_lexicographically(self) -> None:
        payload = _scrambled_mapping()

        result = json.loads(canonical_capture_bytes(payload))

        root = next(
            node
            for node in result["structure"]["nodes"]
            if node["componentId"] == "cmp.root"
        )
        self.assertEqual(root["children"], ["cmp.extra", "cmp.part"])

    def test_preserves_relationship_endpoint_order(self) -> None:
        payload = _scrambled_mapping()

        result = json.loads(canonical_capture_bytes(payload))

        relationship = next(
            item
            for item in result["entities"]["relationships"]
            if item["id"] == "rel.root.mount"
        )
        self.assertEqual(
            relationship["endpoints"],
            ["fea.enclosure.pad", "cmp.part"],
        )

    def test_canonical_output_has_sorted_keys_compact_separators_and_one_newline(
        self,
    ) -> None:
        text = canonical_capture_text(valid_mapping())

        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))
        self.assertNotIn(": ", text)
        self.assertNotIn(", ", text)
        decoded = json.loads(text)
        self.assertEqual(list(decoded), sorted(decoded))

    def test_non_ascii_text_is_utf8_unescaped(self) -> None:
        payload = valid_mapping()
        payload["entities"]["components"][0]["displayName"] = "Çağrı 東京"

        data = canonical_capture_bytes(payload)

        self.assertIn("Çağrı 東京".encode("utf-8"), data)
        self.assertNotIn(b"\\u", data)


class CanonicalDeterminismTests(unittest.TestCase):
    def test_repeated_serialization_is_byte_identical(self) -> None:
        payload = _scrambled_mapping()

        first = canonical_capture_bytes(payload)
        second = canonical_capture_bytes(payload)

        self.assertEqual(first, second)

    def test_canonical_output_revalidates_and_round_trips_to_same_bytes(
        self,
    ) -> None:
        first = canonical_capture_bytes(_scrambled_mapping())
        second = canonical_capture_bytes(json.loads(first.decode("utf-8")))

        self.assertEqual(first, second)

    def test_mapping_and_document_produce_identical_bytes(self) -> None:
        payload = _scrambled_mapping()
        document = CaptureDocument.from_mapping(payload)

        self.assertEqual(
            canonical_capture_bytes(payload),
            canonical_capture_bytes(document),
        )

    def test_serialization_does_not_mutate_input_mapping(self) -> None:
        payload = _scrambled_mapping()
        original = copy.deepcopy(payload)

        canonical_capture_bytes(payload)

        self.assertEqual(payload, original)

    def test_serialization_does_not_mutate_document(self) -> None:
        document = CaptureDocument.from_mapping(_scrambled_mapping())
        before = document.to_mapping()

        canonical_capture_bytes(document)

        self.assertEqual(document.to_mapping(), before)

    def test_invalid_document_is_rejected_before_serialization(self) -> None:
        payload = valid_mapping()
        payload["entities"]["features"][0]["componentId"] = "cmp.missing"

        with self.assertRaises(CaptureContractError):
            canonical_capture_bytes(payload)

    def test_unsupported_value_type_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            canonical_capture_bytes(object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
