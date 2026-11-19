"""Strict occurrence request contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from parametron_freecad.runtime.occurrence_request import (
    OCCURRENCE_MECHANISM_DIRECT_MEMBER,
    OCCURRENCE_REQUEST_FILENAME,
    OccurrenceRequestError,
    discover_occurrence_request,
    load_occurrence_request,
)

_PARENT = {
    "resource": {
        "projectId": "project",
        "kind": "model",
        "logicalId": "assembly",
    },
    "nativeKind": "object",
    "name": "Assembly",
}


def _request_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schemaVersion": "1.0",
        "requirement": "optional",
        "scope": {
            "parent": json.loads(json.dumps(_PARENT)),
            "context": [],
            "mechanism": OCCURRENCE_MECHANISM_DIRECT_MEMBER,
        },
    }
    payload.update(overrides)
    return payload


class OccurrenceRequestTests(unittest.TestCase):
    def _load(self, payload: object) -> object:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / OCCURRENCE_REQUEST_FILENAME
            if isinstance(payload, str):
                path.write_text(payload, encoding="utf-8")
            else:
                path.write_text(json.dumps(payload), encoding="utf-8")
            return load_occurrence_request(path)

    def test_loads_supported_request_and_echoes_scope(self) -> None:
        request = self._load(_request_payload())

        self.assertEqual(request.schema_version, "1.0")
        self.assertEqual(request.requirement, "optional")
        self.assertEqual(request.scope.parent.name, "Assembly")
        self.assertEqual(request.scope.parent.resource.logical_id, "assembly")
        self.assertEqual(request.scope.context, ())
        self.assertEqual(request.scope.mechanism, OCCURRENCE_MECHANISM_DIRECT_MEMBER)
        self.assertEqual(
            request.scope.to_payload(),
            _request_payload()["scope"],
        )

    def test_optional_semantic_id_is_preserved(self) -> None:
        parent = json.loads(json.dumps(_PARENT))
        parent["semanticId"] = "component-body"
        request = self._load(
            _request_payload(
                scope={
                    "parent": parent,
                    "context": [],
                    "mechanism": OCCURRENCE_MECHANISM_DIRECT_MEMBER,
                }
            )
        )

        self.assertEqual(request.scope.parent.semantic_id, "component-body")
        self.assertEqual(
            request.scope.to_payload()["parent"]["semanticId"],
            "component-body",
        )

    def test_non_empty_context_is_accepted_as_unsupported_intent(self) -> None:
        frame = {
            "parent": {
                "resource": {
                    "projectId": "project",
                    "kind": "model",
                    "logicalId": "nested",
                },
                "nativeKind": "object",
                "name": "Nested",
            },
            "member": "NestedLink",
        }
        request = self._load(
            _request_payload(
                scope={
                    "parent": json.loads(json.dumps(_PARENT)),
                    "context": [frame],
                    "mechanism": OCCURRENCE_MECHANISM_DIRECT_MEMBER,
                }
            )
        )

        self.assertEqual(len(request.scope.context), 1)
        self.assertEqual(request.scope.context[0].member, "NestedLink")

    def test_rejects_unknown_fields(self) -> None:
        payload = _request_payload()
        payload["extra"] = True
        with self.assertRaisesRegex(OccurrenceRequestError, "unknown field"):
            self._load(payload)

    def test_rejects_unsupported_schema_and_requirement(self) -> None:
        for field, value in (
            ("schemaVersion", "2.0"),
            ("requirement", "required"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(OccurrenceRequestError):
                    self._load(_request_payload(**{field: value}))

    def test_rejects_malformed_scope_shapes(self) -> None:
        for scope in (
            [],
            {"parent": _PARENT, "context": [], "mechanism": ""},
            {
                "parent": _PARENT,
                "context": {},
                "mechanism": OCCURRENCE_MECHANISM_DIRECT_MEMBER,
            },
            {
                "parent": {**_PARENT, "nativeKind": "document"},
                "context": [],
                "mechanism": OCCURRENCE_MECHANISM_DIRECT_MEMBER,
            },
            {
                "parent": {
                    **_PARENT,
                    "resource": {
                        "projectId": "p",
                        "kind": "assembly",
                        "logicalId": "a",
                    },
                },
                "context": [],
                "mechanism": OCCURRENCE_MECHANISM_DIRECT_MEMBER,
            },
            {
                "parent": {**_PARENT, "name": "Nested/Name"},
                "context": [],
                "mechanism": OCCURRENCE_MECHANISM_DIRECT_MEMBER,
            },
        ):
            with self.subTest(scope=scope):
                with self.assertRaises(OccurrenceRequestError):
                    self._load(_request_payload(scope=scope))

    def test_rejects_context_over_sixteen_frames(self) -> None:
        frame = {"parent": json.loads(json.dumps(_PARENT)), "member": "Link"}
        with self.assertRaisesRegex(OccurrenceRequestError, "at most 16"):
            self._load(
                _request_payload(
                    scope={
                        "parent": json.loads(json.dumps(_PARENT)),
                        "context": [
                            {
                                **frame,
                                "parent": {
                                    **json.loads(json.dumps(_PARENT)),
                                    "name": f"Assembly{index}",
                                },
                            }
                            for index in range(17)
                        ],
                        "mechanism": OCCURRENCE_MECHANISM_DIRECT_MEMBER,
                    }
                )
            )

    def test_rejects_duplicate_or_cyclic_context(self) -> None:
        with self.assertRaisesRegex(OccurrenceRequestError, "repeats or cycles"):
            self._load(
                _request_payload(
                    scope={
                        "parent": json.loads(json.dumps(_PARENT)),
                        "context": [
                            {
                                "parent": json.loads(json.dumps(_PARENT)),
                                "member": "Link",
                            }
                        ],
                        "mechanism": OCCURRENCE_MECHANISM_DIRECT_MEMBER,
                    }
                )
            )

    def test_rejects_malformed_json_and_duplicate_keys(self) -> None:
        with self.assertRaises(OccurrenceRequestError):
            self._load("{")
        duplicate = (
            '{"schemaVersion":"1.0","requirement":"optional",'
            '"requirement":"optional","scope":{}}'
        )
        with self.assertRaises(OccurrenceRequestError):
            self._load(duplicate)

    def test_discovers_confined_request_only_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = Path(tmp_dir) / "attempt"
            working.mkdir()
            self.assertIsNone(discover_occurrence_request(working))

            request = working / OCCURRENCE_REQUEST_FILENAME
            request.write_text(json.dumps(_request_payload()), encoding="utf-8")
            self.assertEqual(discover_occurrence_request(working), request)

    def test_discovery_rejects_symlink_and_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = Path(tmp_dir)
            real = working / "real.json"
            real.write_text("{}", encoding="utf-8")
            request = working / OCCURRENCE_REQUEST_FILENAME
            request.symlink_to(real)
            with self.assertRaisesRegex(OccurrenceRequestError, "symbolic link"):
                discover_occurrence_request(working)

            request.unlink()
            request.mkdir()
            with self.assertRaisesRegex(OccurrenceRequestError, "regular file"):
                discover_occurrence_request(working)


if __name__ == "__main__":
    unittest.main()
