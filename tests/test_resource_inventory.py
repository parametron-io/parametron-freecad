"""Declared resource inventory tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from parametron_freecad.runtime.resource_inventory import (
    NATIVE_RESOURCE_STATUS_AMBIGUOUS,
    NATIVE_RESOURCE_STATUS_MISSING,
    NATIVE_RESOURCE_STATUS_RESOLVED,
    NATIVE_RESOURCE_STATUS_UNAVAILABLE,
    NATIVE_RESOURCE_STATUS_UNDECLARED,
    ResourceBinding,
    ResourceInventory,
    ResourceInventoryError,
    load_resource_inventory,
)

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64

_SELECTED_COORDINATE = "source/Assembly.FCStd"
_COMPONENT_A_COORDINATE = "resources/component-a/Body.FCStd"
_COMPONENT_B_COORDINATE = "resources/component-b/Body.FCStd"


class _FakeNativeDocument:
    def __init__(self, file_name: str | Path | None) -> None:
        self.FileName = file_name


class ResourceInventoryTests(unittest.TestCase):
    def _working_copy(self, tmp_dir: str) -> Path:
        working = Path(tmp_dir) / "run" / "_working" / "attempt"
        working.mkdir(parents=True)
        return working

    def _resources(self) -> list[dict[str, Any]]:
        return [
            {
                "logicalId": "assembly",
                "kind": "model",
                "materializedCoordinate": _SELECTED_COORDINATE,
                "baselineSha256": _DIGEST_A,
                "expectsPersistedResult": True,
            },
            {
                "logicalId": "component_a",
                "kind": "model",
                "materializedCoordinate": _COMPONENT_A_COORDINATE,
                "baselineSha256": _DIGEST_B,
                "expectsPersistedResult": False,
            },
            {
                "logicalId": "component_b",
                "kind": "model",
                "materializedCoordinate": _COMPONENT_B_COORDINATE,
                "baselineSha256": _DIGEST_C,
                "expectsPersistedResult": False,
            },
        ]

    def _write_request(
        self,
        path: Path,
        resources: list[dict[str, Any]] | None = None,
        **overrides: Any,
    ) -> Path:
        payload: dict[str, Any] = {
            "schemaVersion": "1.0",
            "resources": self._resources() if resources is None else resources,
        }
        payload.update(overrides)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _materialize(self, working: Path) -> None:
        for coordinate in (
            _SELECTED_COORDINATE,
            _COMPONENT_A_COORDINATE,
            _COMPONENT_B_COORDINATE,
        ):
            path = working / coordinate
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture")

    def test_loads_declared_inventory_and_joins_selected_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            self._materialize(working)
            request = self._write_request(working / "request.json")

            inventory = load_resource_inventory(
                request,
                working_copy=working,
                expected_source_path=working / _SELECTED_COORDINATE,
            )

        self.assertEqual(
            tuple(binding.logical_id for binding in inventory.bindings),
            ("assembly", "component_a", "component_b"),
        )
        self.assertEqual(
            tuple(binding.materialized_coordinate for binding in inventory.bindings),
            (
                _SELECTED_COORDINATE,
                _COMPONENT_A_COORDINATE,
                _COMPONENT_B_COORDINATE,
            ),
        )
        self.assertEqual(inventory.selected_source_binding.logical_id, "assembly")
        self.assertEqual(inventory.persisted_result_binding.logical_id, "assembly")
        self.assertEqual(
            inventory.binding_for_logical_id("component_a").materialized_coordinate,
            _COMPONENT_A_COORDINATE,
        )
        self.assertEqual(
            inventory.binding_for_coordinate(_COMPONENT_B_COORDINATE).logical_id,
            "component_b",
        )
        self.assertIsNone(inventory.binding_for_logical_id("missing"))
        self.assertIsNone(inventory.binding_for_coordinate("missing"))

    def test_missing_materialized_files_still_produce_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            request = self._write_request(working / "request.json")

            inventory = load_resource_inventory(
                request,
                working_copy=working,
                expected_source_path=working / _SELECTED_COORDINATE,
            )

        self.assertEqual(len(inventory.bindings), 3)
        self.assertFalse((working / _SELECTED_COORDINATE).exists())

    def test_relative_expected_source_is_resolved_inside_working_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            self._materialize(working)
            request = self._write_request(working / "request.json")

            inventory = load_resource_inventory(
                request,
                working_copy=working,
                expected_source_path="./source/Assembly.FCStd",
            )

        self.assertEqual(inventory.selected_source_binding.logical_id, "assembly")

    def test_selected_source_must_be_persisted_result_resource(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            self._materialize(working)
            request = self._write_request(working / "request.json")

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "not the integrity request persisted-result resource",
            ):
                load_resource_inventory(
                    request,
                    working_copy=working,
                    expected_source_path=working / _COMPONENT_A_COORDINATE,
                )

    def test_expected_source_must_resolve_inside_working_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            request = self._write_request(working / "request.json")
            outside = Path(tmp_dir) / "outside.FCStd"
            outside.write_bytes(b"outside")

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "selected source document must resolve inside the working copy",
            ):
                load_resource_inventory(
                    request,
                    working_copy=working,
                    expected_source_path=outside,
                )

    def test_request_path_must_be_absolute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            request = self._write_request(working / "request.json")

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "integrity request path must be absolute",
            ):
                load_resource_inventory(
                    "request.json",
                    working_copy=working,
                )

    def test_request_path_must_exist_and_be_regular(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "existing regular file",
            ):
                load_resource_inventory(
                    Path(tmp_dir) / "missing.json",
                    working_copy=working,
                )

    def test_request_path_must_not_be_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            request = self._write_request(working / "request.json")
            link = Path(tmp_dir) / "request-link.json"
            link.symlink_to(request)

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "must not be a symbolic link",
            ):
                load_resource_inventory(link, working_copy=working)

    def test_empty_request_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            for value in ("", "   "):
                with self.subTest(value=value):
                    with self.assertRaisesRegex(
                        ResourceInventoryError,
                        "must not be empty",
                    ):
                        load_resource_inventory(value, working_copy=working)

    def test_working_copy_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            request = self._write_request(working / "request.json")

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "working copy must be an existing directory",
            ):
                load_resource_inventory(
                    request,
                    working_copy=Path(tmp_dir) / "missing",
                )

    def test_schema_version_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            request = self._write_request(
                working / "request.json",
                schemaVersion="2.0",
            )

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "schemaVersion must equal",
            ):
                load_resource_inventory(request, working_copy=working)

    def test_root_and_resource_fields_are_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            root_request = self._write_request(
                working / "root.json",
                extra="value",
            )
            resources = self._resources()
            resources[0]["extra"] = "value"
            resource_request = self._write_request(
                working / "resource.json",
                resources,
            )

            with self.assertRaisesRegex(ResourceInventoryError, "unknown field"):
                load_resource_inventory(root_request, working_copy=working)
            with self.assertRaisesRegex(ResourceInventoryError, "unknown field"):
                load_resource_inventory(resource_request, working_copy=working)

    def test_missing_required_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            resources = self._resources()
            del resources[0]["baselineSha256"]
            request = self._write_request(working / "request.json", resources)

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "requires field 'baselineSha256'",
            ):
                load_resource_inventory(request, working_copy=working)

    def test_resources_must_be_ordered_by_logical_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            resources = self._resources()
            resources = [resources[1], resources[0], resources[2]]
            request = self._write_request(working / "request.json", resources)

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "unique and ordered by logical ID",
            ):
                load_resource_inventory(request, working_copy=working)

    def test_exactly_one_persisted_result_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            resources = self._resources()
            resources[0]["expectsPersistedResult"] = False
            request = self._write_request(working / "request.json", resources)

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "exactly one persisted result",
            ):
                load_resource_inventory(request, working_copy=working)

            resources = self._resources()
            resources[1]["expectsPersistedResult"] = True
            request = self._write_request(working / "request.json", resources)
            with self.assertRaisesRegex(
                ResourceInventoryError,
                "exactly one persisted result",
            ):
                load_resource_inventory(request, working_copy=working)

    def test_coordinate_must_be_canonical(self) -> None:
        invalid_coordinates = (
            "",
            " /source/Assembly.FCStd",
            "/source/Assembly.FCStd",
            "../Assembly.FCStd",
            "source/../Assembly.FCStd",
            "source//Assembly.FCStd",
            "source/Assembly.FCStd/",
            "source\\Assembly.FCStd",
            "C:/Assembly.FCStd",
            ".",
            "..",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            for coordinate in invalid_coordinates:
                with self.subTest(coordinate=coordinate):
                    resources = self._resources()
                    resources[0]["materializedCoordinate"] = coordinate
                    request = self._write_request(working / "request.json", resources)
                    with self.assertRaisesRegex(
                        ResourceInventoryError,
                        "canonical relative coordinate",
                    ):
                        load_resource_inventory(request, working_copy=working)

    def test_digest_must_be_canonical(self) -> None:
        invalid_digests = ("A" * 64, "a" * 63, "g" * 64, "")
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            for digest in invalid_digests:
                with self.subTest(digest=digest):
                    resources = self._resources()
                    resources[0]["baselineSha256"] = digest
                    request = self._write_request(working / "request.json", resources)
                    with self.assertRaisesRegex(
                        ResourceInventoryError,
                        "canonical lowercase SHA-256 digest",
                    ):
                        load_resource_inventory(request, working_copy=working)

    def test_kind_and_expects_persisted_result_are_typed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            resources = self._resources()
            resources[0]["kind"] = "table"
            request = self._write_request(working / "request.json", resources)
            with self.assertRaisesRegex(ResourceInventoryError, "kind must equal"):
                load_resource_inventory(request, working_copy=working)

            resources = self._resources()
            resources[0]["expectsPersistedResult"] = 1
            request = self._write_request(working / "request.json", resources)
            with self.assertRaisesRegex(
                ResourceInventoryError,
                "must be a boolean",
            ):
                load_resource_inventory(request, working_copy=working)

    def test_duplicate_coordinate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            resources = self._resources()
            resources[1]["materializedCoordinate"] = _SELECTED_COORDINATE
            request = self._write_request(working / "request.json", resources)

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "already bound",
            ):
                load_resource_inventory(request, working_copy=working)

    def test_ancestor_coordinate_conflict_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            resources = self._resources()
            resources[1]["materializedCoordinate"] = "source"
            request = self._write_request(working / "request.json", resources)

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "conflicts with another declared resource coordinate",
            ):
                load_resource_inventory(request, working_copy=working)

    def test_coordinate_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            outside = Path(tmp_dir) / "outside.FCStd"
            outside.write_bytes(b"outside")
            (working / "source").mkdir()
            (working / "source" / "Assembly.FCStd").symlink_to(outside)
            request = self._write_request(working / "request.json")

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "escapes the working copy",
            ):
                load_resource_inventory(request, working_copy=working)

    def test_coordinate_alias_resolution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            self._materialize(working)
            (working / _COMPONENT_B_COORDINATE).unlink()
            (working / _COMPONENT_B_COORDINATE).symlink_to(
                working / _COMPONENT_A_COORDINATE
            )
            request = self._write_request(working / "request.json")

            with self.assertRaisesRegex(
                ResourceInventoryError,
                "resolves to the same working-copy path",
            ):
                load_resource_inventory(request, working_copy=working)

    def test_native_document_resolution_uses_declared_coordinate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            self._materialize(working)
            request = self._write_request(working / "request.json")
            inventory = load_resource_inventory(
                request,
                working_copy=working,
                expected_source_path=working / _SELECTED_COORDINATE,
            )

            resolution = inventory.resolve_native_document(
                _FakeNativeDocument(working / _COMPONENT_A_COORDINATE)
            )

        self.assertEqual(resolution.status, NATIVE_RESOURCE_STATUS_RESOLVED)
        self.assertEqual(resolution.binding.logical_id, "component_a")
        self.assertEqual(
            resolution.binding.materialized_coordinate,
            _COMPONENT_A_COORDINATE,
        )

    def test_duplicate_native_names_in_separate_resources_are_distinguishable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            self._materialize(working)
            request = self._write_request(working / "request.json")
            inventory = load_resource_inventory(
                request,
                working_copy=working,
                expected_source_path=working / _SELECTED_COORDINATE,
            )

            first = inventory.resolve_native_document(
                _FakeNativeDocument(working / _COMPONENT_A_COORDINATE)
            )
            second = inventory.resolve_native_document(
                _FakeNativeDocument(working / _COMPONENT_B_COORDINATE)
            )

        self.assertEqual(first.binding.logical_id, "component_a")
        self.assertEqual(second.binding.logical_id, "component_b")
        self.assertNotEqual(first.binding.logical_id, second.binding.logical_id)
        self.assertNotEqual(
            first.binding.materialized_coordinate,
            second.binding.materialized_coordinate,
        )

    def test_missing_declared_native_document_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            (working / _SELECTED_COORDINATE).parent.mkdir(parents=True)
            (working / _SELECTED_COORDINATE).write_bytes(b"selected")
            request = self._write_request(working / "request.json")
            inventory = load_resource_inventory(
                request,
                working_copy=working,
                expected_source_path=working / _SELECTED_COORDINATE,
            )

            resolution = inventory.resolve_native_document(
                _FakeNativeDocument(working / _COMPONENT_A_COORDINATE)
            )

        self.assertEqual(resolution.status, NATIVE_RESOURCE_STATUS_MISSING)
        self.assertEqual(resolution.binding.logical_id, "component_a")
        self.assertEqual(
            resolution.binding.materialized_coordinate,
            _COMPONENT_A_COORDINATE,
        )
        self.assertIsNotNone(resolution.diagnostic)

    def test_undeclared_native_document_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            self._materialize(working)
            request = self._write_request(working / "request.json")
            inventory = load_resource_inventory(
                request,
                working_copy=working,
                expected_source_path=working / _SELECTED_COORDINATE,
            )
            outside = Path(tmp_dir) / "outside.FCStd"
            outside.write_bytes(b"outside")

            resolution = inventory.resolve_native_document(_FakeNativeDocument(outside))

        self.assertEqual(resolution.status, NATIVE_RESOURCE_STATUS_UNDECLARED)
        self.assertIsNone(resolution.binding)
        self.assertNotIn(tmp_dir, repr(resolution))

    def test_unavailable_native_document_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            request = self._write_request(working / "request.json")
            inventory = load_resource_inventory(
                request,
                working_copy=working,
                expected_source_path=working / _SELECTED_COORDINATE,
            )

            for document in (
                _FakeNativeDocument(None),
                object(),
                _FakeNativeDocument("relative.FCStd"),
            ):
                with self.subTest(document=document):
                    resolution = inventory.resolve_native_document(document)
                    self.assertEqual(
                        resolution.status,
                        NATIVE_RESOURCE_STATUS_UNAVAILABLE,
                    )
                    self.assertIsNone(resolution.binding)

    def test_ambiguous_native_document_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            shared_path = working / "source" / "Assembly.FCStd"
            shared_path.parent.mkdir(parents=True)
            shared_path.write_bytes(b"fixture")
            binding = ResourceBinding(
                logical_id="assembly",
                kind="model",
                materialized_coordinate=_SELECTED_COORDINATE,
                baseline_sha256=_DIGEST_A,
                expects_persisted_result=True,
                resolved_path=shared_path,
            )
            inventory = ResourceInventory(
                working_copy=working,
                bindings=(binding, binding),
            )

            resolution = inventory.resolve_native_document(
                _FakeNativeDocument(shared_path)
            )

        self.assertEqual(resolution.status, NATIVE_RESOURCE_STATUS_AMBIGUOUS)
        self.assertIsNone(resolution.binding)

    def test_relocation_preserves_coordinates_and_joins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            original = self._working_copy(tmp_dir)
            self._materialize(original)
            self._write_request(original / "request.json")

            relocated = Path(tmp_dir) / "relocated" / "nested" / "attempt"
            relocated.parent.mkdir(parents=True)
            original.rename(relocated)
            request = relocated / "request.json"

            inventory = load_resource_inventory(
                request,
                working_copy=relocated,
                expected_source_path=relocated / _SELECTED_COORDINATE,
            )
            resolution = inventory.resolve_native_document(
                _FakeNativeDocument(relocated / _COMPONENT_A_COORDINATE)
            )

        self.assertEqual(
            tuple(binding.materialized_coordinate for binding in inventory.bindings),
            (
                _SELECTED_COORDINATE,
                _COMPONENT_A_COORDINATE,
                _COMPONENT_B_COORDINATE,
            ),
        )
        self.assertEqual(resolution.binding.logical_id, "component_a")


if __name__ == "__main__":
    unittest.main()
