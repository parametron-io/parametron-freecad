"""Strict fact request contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from parametron_freecad.runtime.fact_request import (
    FACT_REQUEST_FILENAME,
    FactRequestError,
    discover_fact_request,
    load_fact_request,
)

_SUBJECT = {
    "resource": {
        "projectId": "project",
        "kind": "model",
        "logicalId": "source",
    },
    "nativeKind": "object",
    "name": "Props",
}


def _binding(**overrides: object) -> dict[str, object]:
    binding: dict[str, object] = {
        "kind": "bound_property",
        "subject": json.loads(json.dumps(_SUBJECT)),
        "context": [],
        "property": "Length",
        "valueKind": "number",
        "unit": "mm",
        "requirement": "optional",
    }
    binding.update(overrides)
    return binding


def _request_payload(*bindings: dict[str, object]) -> dict[str, object]:
    return {
        "schemaVersion": "1.0",
        "bindings": list(bindings) if bindings else [_binding()],
    }


class FactRequestTests(unittest.TestCase):
    def _load(self, payload: object) -> object:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / FACT_REQUEST_FILENAME
            if isinstance(payload, str):
                path.write_text(payload, encoding="utf-8")
            else:
                path.write_text(json.dumps(payload), encoding="utf-8")
            return load_fact_request(path)

    def test_loads_bounded_binding(self) -> None:
        request = self._load(_request_payload())

        self.assertEqual(request.schema_version, "1.0")
        self.assertEqual(len(request.bindings), 1)
        binding = request.bindings[0]
        self.assertEqual(binding.kind, "bound_property")
        self.assertEqual(binding.subject.name, "Props")
        self.assertEqual(binding.context, ())
        self.assertEqual(binding.property, "Length")
        self.assertEqual(binding.value_kind, "number")
        self.assertEqual(binding.unit, "mm")
        self.assertEqual(binding.requirement, "optional")

    def test_unit_is_optional_and_omitted_unit_loads_empty(self) -> None:
        payload = _binding(valueKind="boolean")
        payload.pop("unit")
        request = self._load(_request_payload(payload))
        self.assertEqual(request.bindings[0].unit, "")

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
        request = self._load(_request_payload(_binding(context=[frame])))
        self.assertEqual(len(request.bindings[0].context), 1)

    def test_rejects_malformed_requests(self) -> None:
        cases = [
            [],
            {"schemaVersion": "2.0", "bindings": [_binding()]},
            {"schemaVersion": "1.0", "bindings": []},
            {"schemaVersion": "1.0", "bindings": [_binding(), _binding()]},
            _request_payload(_binding(extra=True)),
            _request_payload(_binding(kind="mass")),
            _request_payload(_binding(valueKind="float")),
            _request_payload(_binding(requirement="mandatory")),
            _request_payload(_binding(property="")),
            _request_payload(_binding(property="P" * 129)),
            _request_payload(_binding(subject={**_SUBJECT, "nativeKind": "document"})),
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(FactRequestError):
                    self._load(payload)

    def test_rejects_unit_incompatible_with_non_numeric_values(self) -> None:
        for value_kind in ("string", "boolean"):
            with self.subTest(value_kind=value_kind):
                with self.assertRaises(FactRequestError):
                    self._load(
                        _request_payload(_binding(valueKind=value_kind, unit="mm"))
                    )

    def test_rejects_malformed_unit_tokens(self) -> None:
        for unit in ("mm\n", " mm", "\tmm", "m" * 33, "mm\x00"):
            with self.subTest(unit=unit):
                with self.assertRaises(FactRequestError):
                    self._load(_request_payload(_binding(unit=unit)))

    def test_rejects_duplicate_and_conflicting_bindings(self) -> None:
        first = _binding()
        duplicate = _binding()
        conflicting = _binding(valueKind="integer")
        for bindings in ((first, duplicate), (first, conflicting)):
            with self.subTest(bindings=bindings):
                with self.assertRaisesRegex(
                    FactRequestError, "duplicate or conflicting"
                ):
                    self._load(_request_payload(*bindings))

    def test_allows_same_property_on_distinct_subjects(self) -> None:
        other = json.loads(json.dumps(_SUBJECT))
        other["name"] = "OtherProps"
        request = self._load(_request_payload(_binding(), _binding(subject=other)))
        self.assertEqual(len(request.bindings), 2)

    def test_rejects_cyclic_context(self) -> None:
        frame = {
            "parent": json.loads(json.dumps(_SUBJECT)),
            "member": "Link",
        }
        with self.assertRaises(FactRequestError):
            self._load(_request_payload(_binding(context=[frame])))

    def test_rejects_duplicate_json_keys(self) -> None:
        duplicate = '{"schemaVersion":"1.0","schemaVersion":"1.0","bindings":[]}'
        with self.assertRaises(FactRequestError):
            self._load(duplicate)

    def test_discovers_confined_request_only_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = Path(tmp_dir) / "attempt"
            working.mkdir()
            self.assertIsNone(discover_fact_request(working))

            request = working / FACT_REQUEST_FILENAME
            request.write_text(json.dumps(_request_payload()), encoding="utf-8")
            self.assertEqual(discover_fact_request(working), request)

    def test_discovery_rejects_symlink_and_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = Path(tmp_dir)
            real = working / "real.json"
            real.write_text("{}", encoding="utf-8")
            request = working / FACT_REQUEST_FILENAME
            request.symlink_to(real)
            with self.assertRaisesRegex(FactRequestError, "symbolic link"):
                discover_fact_request(working)

            request.unlink()
            request.mkdir()
            with self.assertRaisesRegex(FactRequestError, "regular file"):
                discover_fact_request(working)


if __name__ == "__main__":
    unittest.main()
