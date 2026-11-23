"""Round-trip tests against the committed schema 1.0 capture fixtures."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from parametron_freecad.capture import (
    CaptureDocument,
    canonical_capture_bytes,
    validate_capture_document,
)

FIXTURES = (
    Path(__file__).parent / "fixtures" / "canonical_lifecycle" / "prm.cad.json",
    Path(__file__).parent / "fixtures" / "metadata_mutation" / "prm.cad.json",
)

_REGISTRIES = (
    "components",
    "features",
    "relationships",
    "parameterGroups",
    "parameters",
    "metadata",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class CommittedCaptureFixtureTests(unittest.TestCase):
    def test_fixtures_parse_to_models_and_round_trip(self) -> None:
        for path in FIXTURES:
            with self.subTest(fixture=path.name, directory=path.parent.name):
                mapping = _load(path)
                original = copy.deepcopy(mapping)

                document = CaptureDocument.from_mapping(mapping)

                self.assertEqual(mapping, original)
                self.assertEqual(document.to_mapping(), mapping)
                validate_capture_document(document.to_mapping())

    def test_fixtures_produce_deterministic_canonical_bytes(self) -> None:
        for path in FIXTURES:
            with self.subTest(fixture=path.name, directory=path.parent.name):
                document = CaptureDocument.from_mapping(_load(path))

                first = canonical_capture_bytes(document)
                second = canonical_capture_bytes(document)
                third = canonical_capture_bytes(json.loads(first.decode("utf-8")))

                self.assertEqual(first, second)
                self.assertEqual(first, third)
                self.assertTrue(first.endswith(b"\n"))
                self.assertFalse(first.endswith(b"\n\n"))

    def test_fixtures_preserve_ids_names_and_structure(self) -> None:
        for path in FIXTURES:
            with self.subTest(fixture=path.name, directory=path.parent.name):
                mapping = _load(path)
                document = CaptureDocument.from_mapping(mapping)
                result = document.to_mapping()

                for registry in _REGISTRIES:
                    source_ids = [item["id"] for item in mapping["entities"][registry]]
                    result_ids = [item["id"] for item in result["entities"][registry]]
                    self.assertEqual(result_ids, source_ids)

                for registry in (
                    "components",
                    "features",
                    "relationships",
                    "parameterGroups",
                    "parameters",
                ):
                    source_names = [
                        item["name"] for item in mapping["entities"][registry]
                    ]
                    result_names = [
                        item["name"] for item in result["entities"][registry]
                    ]
                    self.assertEqual(result_names, source_names)

                self.assertEqual(result["rootProduct"], mapping["rootProduct"])
                self.assertEqual(
                    result["structure"]["rootComponentId"],
                    mapping["structure"]["rootComponentId"],
                )

    def test_fixtures_canonicalize_registries_by_id(self) -> None:
        for path in FIXTURES:
            with self.subTest(fixture=path.name, directory=path.parent.name):
                document = CaptureDocument.from_mapping(_load(path))
                result = json.loads(canonical_capture_bytes(document))

                for registry in _REGISTRIES:
                    identifiers = [item["id"] for item in result["entities"][registry]]
                    self.assertEqual(identifiers, sorted(identifiers))

                node_ids = [
                    node["componentId"] for node in result["structure"]["nodes"]
                ]
                self.assertEqual(node_ids, sorted(node_ids))

    def test_metadata_fixture_preserves_native_keys_and_semantic_names(
        self,
    ) -> None:
        path = FIXTURES[1]
        result = CaptureDocument.from_mapping(_load(path)).to_mapping()

        names = {
            component["id"]: component["name"]
            for component in result["entities"]["components"]
        }
        self.assertEqual(names["cmp.enclosure"], "Enclosure")
        self.assertEqual(names["cmp.sacrificialMarker"], "SacrificialMarker")

        metadata_keys = [entry["key"] for entry in result["entities"]["metadata"]]
        self.assertTrue(
            all("name" not in entry for entry in result["entities"]["metadata"])
        )
        self.assertEqual(
            metadata_keys,
            [
                "material",
                "tagged",
                "mass",
                "revision",
                "tolerance",
                "sequence",
            ],
        )

    def test_fixture_files_are_not_modified(self) -> None:
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest() for path in FIXTURES
        }

        for path in FIXTURES:
            document = CaptureDocument.from_mapping(_load(path))
            canonical_capture_bytes(document)

        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest() for path in FIXTURES
        }
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
