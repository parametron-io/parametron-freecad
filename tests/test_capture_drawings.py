"""Focused schema 1.0 technical drawing capture contract tests."""

from __future__ import annotations

import copy
import json
import unittest

from capture_support import valid_mapping

from parametron_freecad.capture import (
    CaptureContractError,
    CaptureDocument,
    CaptureIdPolicyError,
    CaptureNamePolicyError,
    canonical_capture_bytes,
    generate_drawing_id,
    generate_drawing_sheet_id,
    validate_capture_document,
)


def _drawing(
    *,
    identifier: str = "drw.manufacturing",
    name: str = "manufacturing",
    display_name: str = "Manufacturing",
    component_ids: list[str] | None = None,
    topology: str = "embedded",
    path: str | None = None,
    sheets: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    resource: dict[str, object] = {"topology": topology}
    if path is not None:
        resource["path"] = path
    if sheets is None:
        sheets = [_sheet()]
    return {
        "id": identifier,
        "name": name,
        "displayName": display_name,
        "componentIds": list(component_ids or ["cmp.part"]),
        "resource": resource,
        "sheets": sheets,
    }


def _sheet(
    *,
    identifier: str = "sht.manufacturing.assembly",
    name: str = "assembly",
    display_name: str = "Assembly",
    order: int = 1,
    cad_type: str = "TechDraw::DrawPage",
    native_ref: str = "Page",
) -> dict[str, object]:
    return {
        "id": identifier,
        "name": name,
        "displayName": display_name,
        "order": order,
        "cadType": cad_type,
        "identitySource": {"kind": "native_ref", "nativeRef": native_ref},
    }


def _mapping() -> dict[str, object]:
    mapping = copy.deepcopy(valid_mapping())
    mapping["entities"]["drawings"] = [_drawing()]
    return mapping


class DrawingContractModelTests(unittest.TestCase):
    def test_drawing_mapping_round_trips_through_the_record_model(self) -> None:
        mapping = _mapping()
        validate_capture_document(mapping)

        document = CaptureDocument.from_mapping(mapping)
        round_trip = document.to_mapping()

        self.assertEqual(
            round_trip["entities"]["drawings"], mapping["entities"]["drawings"]
        )
        self.assertEqual(
            round_trip["entities"]["drawings"][0]["resource"],
            {"topology": "embedded"},
        )

    def test_zero_drawings_remain_an_empty_array(self) -> None:
        mapping = valid_mapping()
        validate_capture_document(mapping)
        self.assertEqual(mapping["entities"]["drawings"], [])
        self.assertIn(
            '"drawings":[]',
            canonical_capture_bytes(mapping).decode("utf-8"),
        )

    def test_canonicalization_sorts_drawings_components_and_sheets(self) -> None:
        mapping = _mapping()
        mapping["entities"]["drawings"] = [
            _drawing(
                identifier="drw.second",
                name="second",
                component_ids=["cmp.part"],
                sheets=[
                    _sheet(
                        identifier="sht.second.two",
                        name="two",
                        order=2,
                        native_ref="Page002",
                    ),
                    _sheet(
                        identifier="sht.second.one",
                        name="one",
                        order=1,
                        native_ref="Page001",
                    ),
                ],
            ),
            _drawing(
                identifier="drw.first",
                name="first",
                component_ids=["cmp.part", "cmp.root"],
                sheets=[
                    _sheet(
                        identifier="sht.first.one",
                        name="one",
                        order=1,
                        native_ref="Page",
                    )
                ],
            ),
        ]

        payload = json.loads(canonical_capture_bytes(mapping))
        drawings = payload["entities"]["drawings"]
        self.assertEqual(
            [item["id"] for item in drawings],
            ["drw.first", "drw.second"],
        )
        self.assertEqual(drawings[0]["componentIds"], ["cmp.part", "cmp.root"])
        self.assertEqual(
            [item["id"] for item in drawings[1]["sheets"]],
            ["sht.second.one", "sht.second.two"],
        )


class DrawingContractValidationTests(unittest.TestCase):
    def _assert_contract_error(self, mutate) -> None:
        mapping = _mapping()
        mutate(mapping)
        with self.assertRaises(CaptureContractError):
            validate_capture_document(mapping)

    def test_drawings_registry_is_required(self) -> None:
        mapping = _mapping()
        del mapping["entities"]["drawings"]
        with self.assertRaises(CaptureContractError):
            validate_capture_document(mapping)

    def test_null_drawings_registry_is_rejected(self) -> None:
        self._assert_contract_error(
            lambda value: value["entities"].__setitem__("drawings", None)
        )

    def test_unknown_drawing_fields_are_rejected(self) -> None:
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0].__setitem__("extra", True)
        )

    def test_unknown_resource_and_sheet_fields_are_rejected(self) -> None:
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0]["resource"].__setitem__(
                "extra", True
            )
        )
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0]["sheets"][0].__setitem__(
                "extra", True
            )
        )

    def test_component_ids_must_be_nonempty_unique_and_resolve(self) -> None:
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0].__setitem__(
                "componentIds", []
            )
        )
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0].__setitem__(
                "componentIds", ["cmp.part", "cmp.part"]
            )
        )
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0].__setitem__(
                "componentIds", ["cmp.missing"]
            )
        )

    def test_sheets_must_be_nonempty_with_positive_unique_orders(self) -> None:
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0].__setitem__("sheets", [])
        )
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0]["sheets"][0].__setitem__(
                "order", 0
            )
        )
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0].__setitem__(
                "sheets",
                [
                    _sheet(native_ref="Page"),
                    _sheet(
                        identifier="sht.manufacturing.second",
                        name="second",
                        order=1,
                        native_ref="Page001",
                    ),
                ],
            )
        )

    def test_sheet_identity_source_is_required_and_native_ref_bound(self) -> None:
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0]["sheets"][0].pop(
                "identitySource"
            )
        )
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0]["sheets"][0][
                "identitySource"
            ].__setitem__("kind", "owner_scoped_key")
        )
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0]["sheets"][0][
                "identitySource"
            ].__setitem__("nativeRef", "")
        )

    def test_resource_topology_rules(self) -> None:
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0].__setitem__(
                "resource", {"topology": "embedded", "path": "drawings/a.FCStd"}
            )
        )
        self._assert_contract_error(
            lambda value: value["entities"]["drawings"][0].__setitem__(
                "resource", {"topology": "separate"}
            )
        )
        for path in (
            "/absolute.FCStd",
            "../escape.FCStd",
            "drawings/../escape.FCStd",
            "drawings\\escape.FCStd",
            "C:/escape.FCStd",
            "./drawings.FCStd",
        ):
            self._assert_contract_error(
                lambda value, path=path: value["entities"]["drawings"][0].__setitem__(
                    "resource", {"topology": "separate", "path": path}
                )
            )

    def test_separate_resource_path_is_accepted(self) -> None:
        mapping = _mapping()
        mapping["entities"]["drawings"][0]["resource"] = {
            "topology": "separate",
            "path": "drawings/inspection.FCStd",
        }
        validate_capture_document(mapping)

    def test_drawing_and_sheet_names_are_policy_checked(self) -> None:
        mapping = _mapping()
        mapping["entities"]["drawings"][0]["name"] = "1 invalid"
        with self.assertRaises(CaptureNamePolicyError):
            validate_capture_document(mapping)

        mapping = _mapping()
        mapping["entities"]["drawings"][0]["name"] = "drawing"
        mapping["entities"]["drawings"].append(
            _drawing(
                identifier="drw.other",
                name="drawing",
                component_ids=["cmp.part"],
                sheets=[
                    _sheet(
                        identifier="sht.other.one",
                        name="one",
                        native_ref="Page001",
                    )
                ],
            )
        )
        with self.assertRaises(CaptureNamePolicyError):
            validate_capture_document(mapping)

        mapping = _mapping()
        mapping["entities"]["drawings"][0]["sheets"].append(
            _sheet(
                identifier="sht.manufacturing.other",
                name="assembly",
                order=2,
                native_ref="Page001",
            )
        )
        with self.assertRaises(CaptureNamePolicyError):
            validate_capture_document(mapping)

    def test_drawing_and_sheet_ids_are_globally_unique(self) -> None:
        mapping = _mapping()
        mapping["entities"]["drawings"][0]["id"] = "cmp.part"
        with self.assertRaises(CaptureIdPolicyError):
            validate_capture_document(mapping)

        mapping = _mapping()
        mapping["entities"]["drawings"][0]["sheets"][0]["id"] = "cmp.part"
        with self.assertRaises(CaptureIdPolicyError):
            validate_capture_document(mapping)

        mapping = _mapping()
        mapping["entities"]["drawings"][0]["sheets"][0]["id"] = "drw.manufacturing"
        with self.assertRaises(CaptureIdPolicyError):
            validate_capture_document(mapping)


class DrawingNamingTests(unittest.TestCase):
    def test_generated_drawing_and_sheet_ids_are_deterministic(self) -> None:
        self.assertEqual(generate_drawing_id("Manufacturing"), "drw.manufacturing")
        self.assertEqual(
            generate_drawing_sheet_id("drw.manufacturing", "Assembly"),
            "sht.manufacturing.assembly",
        )


if __name__ == "__main__":
    unittest.main()
