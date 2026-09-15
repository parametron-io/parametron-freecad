from __future__ import annotations

import builtins
import json
import re
import tempfile
import unittest
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from unittest import mock

from parametron_freecad.runtime import reference_traversal_request as contract


class ReferenceTraversalRequestContractTests(unittest.TestCase):
    def _write_bytes(self, directory: str, content: bytes) -> Path:
        path = Path(directory) / contract.REFERENCE_TRAVERSAL_REQUEST_FILENAME
        path.write_bytes(content)
        return path

    def test_public_contract_values_are_exact(self) -> None:
        self.assertEqual(contract.REFERENCE_TRAVERSAL_REQUEST_SCHEMA_VERSION, "1.0")
        self.assertEqual(
            contract.REFERENCE_TRAVERSAL_REQUEST_FILENAME,
            "prm.reference-traversal-request.json",
        )
        self.assertEqual(
            contract.REFERENCE_TRAVERSAL_OUTPUT_FILENAME,
            "prm.reference-traversal.json",
        )
        self.assertEqual(
            contract.REFERENCE_TRAVERSAL_REQUEST_CLI_FLAG,
            "--reference-traversal-request",
        )

    def test_loads_exact_closed_schema_into_immutable_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_bytes(tmp, b'{"schemaVersion":"1.0"}')
            loaded = contract.load_reference_traversal_request(path)

        self.assertEqual(
            loaded,
            contract.ReferenceTraversalRequest(schema_version="1.0"),
        )
        self.assertEqual(
            tuple(field.name for field in fields(contract.ReferenceTraversalRequest)),
            ("schema_version",),
        )
        with self.assertRaises(FrozenInstanceError):
            loaded.schema_version = "2.0"  # type: ignore[misc]

    def test_loads_exact_schema_2_empty_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_bytes(
                tmp, b'{"schemaVersion":"2.0","externalTargets":[]}'
            )
            loaded = contract.load_reference_traversal_request(path)
        self.assertEqual(
            loaded,
            contract.ReferenceTraversalRequestV2(
                schema_version="2.0", external_targets=()
            ),
        )

    def test_schema_1_remains_closed_against_external_targets(self) -> None:
        self._assert_invalid(
            b'{"schemaVersion":"1.0","externalTargets":[]}',
            "unknown field(s): 'externalTargets'",
        )

    def test_schema_2_parses_exact_entry_and_canonicalizes_order(self) -> None:
        values = [
            {
                "sourceObjectName": "B",
                "sourceProperty": "Parts",
                "referenceMechanism": "App::PropertyXLinkList",
                "targetObjectName": "Wheel",
                "targetDocumentPath": "references/wheel.FCStd",
            },
            {
                "sourceObjectName": "A",
                "sourceProperty": "Part",
                "referenceMechanism": "App::PropertyXLink",
                "targetObjectName": "Body",
                "targetDocumentPath": "references/part.FCStd",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_bytes(
                tmp,
                json.dumps(
                    {"schemaVersion": "2.0", "externalTargets": values}
                ).encode(),
            )
            loaded = contract.load_reference_traversal_request(path)
        self.assertEqual(
            [value.source_object_name for value in loaded.external_targets],
            ["A", "B"],
        )

    def test_schema_2_entry_is_closed_and_complete(self) -> None:
        base = {
            "sourceObjectName": "AssemblyLink",
            "sourceProperty": "LinkedParts",
            "referenceMechanism": "App::PropertyXLinkList",
            "targetObjectName": "Body",
            "targetDocumentPath": "references/part.FCStd",
        }
        for mutation, message in (
            ({**base, "extra": True}, "unknown field(s): 'extra'"),
            ({key: value for key, value in base.items() if key != "sourceProperty"}, "requires field 'sourceProperty'"),
            ({**base, "targetObjectName": ""}, "must be an exact non-empty string"),
            ({**base, "targetDocumentPath": "../part.FCStd"}, "canonical contract-relative"),
            ({**base, "targetDocumentPath": "/runtime/part.FCStd"}, "canonical contract-relative"),
            ({**base, "referenceMechanism": "App::PropertyString"}, "unsupported reference mechanism"),
        ):
            with self.subTest(mutation=mutation):
                self._assert_invalid(
                    json.dumps({"schemaVersion": "2.0", "externalTargets": [mutation]}).encode(),
                    message,
                )

    def test_schema_2_rejects_duplicates_conflicts_and_cardinality(self) -> None:
        base = {
            "sourceObjectName": "Source", "sourceProperty": "Link",
            "referenceMechanism": "App::PropertyXLink",
            "targetObjectName": "Body", "targetDocumentPath": "refs/a.FCStd",
        }
        cases = (
            ([base, base], "exact duplicate"),
            ([base, {**base, "targetDocumentPath": "refs/b.FCStd"}], "conflicting target identities"),
            ([base, {**base, "targetObjectName": "Wheel", "targetDocumentPath": "refs/b.FCStd"}], "multiple mapped targets"),
        )
        for entries, message in cases:
            with self.subTest(message=message):
                self._assert_invalid(
                    json.dumps({"schemaVersion": "2.0", "externalTargets": entries}).encode(),
                    message,
                )

    def test_equivalent_json_formatting_produces_equal_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = self._write_bytes(tmp, b'{"schemaVersion":"1.0"}')
            loaded_first = contract.load_reference_traversal_request(first)
            second = Path(tmp) / "second.json"
            second.write_text(
                json.dumps({"schemaVersion": "1.0"}, indent=2), encoding="utf-8"
            )
            loaded_second = contract.load_reference_traversal_request(second)
        self.assertEqual(loaded_first, loaded_second)

    def test_non_object_root_is_rejected_with_cause(self) -> None:
        self._assert_invalid(b"[]", "root must be a JSON object")

    def test_missing_schema_version_is_rejected_with_cause(self) -> None:
        self._assert_invalid(b"{}", "requires field 'schemaVersion'")

    def test_unknown_fields_are_rejected_with_cause(self) -> None:
        self._assert_invalid(
            b'{"schemaVersion":"1.0","sourceDocument":"part.FCStd"}',
            "unknown field(s): 'sourceDocument'",
        )

    def test_schema_2_requires_external_targets_with_cause(self) -> None:
        self._assert_invalid(
            b'{"schemaVersion":"2.0"}', "requires field 'externalTargets'"
        )

    def test_non_string_schema_version_is_rejected_with_cause(self) -> None:
        self._assert_invalid(
            b'{"schemaVersion":1.0}', "'schemaVersion' must equal '1.0'"
        )

    def test_duplicate_keys_are_rejected_with_cause(self) -> None:
        self._assert_invalid(
            b'{"schemaVersion":"1.0","schemaVersion":"1.0"}',
            "duplicate object key",
        )

    def test_non_standard_json_constants_are_rejected_with_cause(self) -> None:
        self._assert_invalid(
            b'{"schemaVersion":NaN}', "non-standard JSON constant"
        )

    def test_malformed_json_is_rejected_with_cause(self) -> None:
        self._assert_invalid(b'{"schemaVersion":', "Expecting value")

    def test_invalid_utf8_is_rejected_with_cause(self) -> None:
        self._assert_invalid(b"\xff", "utf-8")

    def test_file_read_failure_is_rejected_with_cause(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.json"
            with self.assertRaises(contract.ReferenceTraversalRequestError) as caught:
                contract.load_reference_traversal_request(missing)
        self.assertIsInstance(caught.exception.__cause__, OSError)

    def test_loader_has_no_freecad_import_or_write_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_bytes(tmp, b'{"schemaVersion":"1.0"}')
            original_import = builtins.__import__

            def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name.split(".", maxsplit=1)[0] in {"FreeCAD", "FreeCADGui"}:
                    raise AssertionError("request loader must not import FreeCAD")
                return original_import(name, globals, locals, fromlist, level)

            with mock.patch("builtins.__import__", side_effect=guarded_import):
                loaded = contract.load_reference_traversal_request(path)
        self.assertEqual(loaded.schema_version, "1.0")

    def _assert_invalid(self, content: bytes, message: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_bytes(tmp, content)
            with self.assertRaisesRegex(
                contract.ReferenceTraversalRequestError, re.escape(message)
            ) as caught:
                contract.load_reference_traversal_request(path)
        self.assertIsNotNone(caught.exception.__cause__)


if __name__ == "__main__":
    unittest.main()
