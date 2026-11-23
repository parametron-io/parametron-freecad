"""Schema 1.0 capture contract validation tests for the GUI-free core."""

from __future__ import annotations

import copy
import math
import unittest
from typing import Any

from capture_support import empty_annotations, targetability, valid_mapping

from parametron_freecad.capture import (
    CaptureContractError,
    CaptureDocument,
    validate_capture_document,
)


def _component(
    component_id: str,
    name: str,
    *,
    path: str,
    kind: str = "part",
) -> dict[str, Any]:
    return {
        "id": component_id,
        "kind": kind,
        "name": name,
        "displayName": name,
        "cadType": "Part::Box",
        "quantity": 1,
        "material": "",
        "identitySource": {
            "kind": "parent_scoped_path",
            "path": path,
            "nativeRef": name,
        },
        "stabilityClass": "stable",
        "targetability": targetability(),
        "annotations": empty_annotations(),
    }


def _add_third_component(
    payload: dict[str, Any],
    *,
    component_id: str = "cmp.extra",
    name: str = "Extra",
    parent_id: str = "cmp.part",
) -> None:
    payload["entities"]["components"].append(
        _component(component_id, name, path=f"cmp.root/{name}")
    )
    payload["structure"]["nodes"].append(
        {
            "componentId": component_id,
            "parentComponentId": parent_id,
            "children": [],
        }
    )
    for node in payload["structure"]["nodes"]:
        if node["componentId"] == parent_id:
            node["children"].append(component_id)
            node["children"].sort()
            break


def _add_feature(
    payload: dict[str, Any],
    *,
    feature_id: str = "fea.enclosure.pad2",
    name: str = "Pad2",
    component_id: str = "cmp.part",
    owner_scoped_key: str = "Pad2",
) -> None:
    payload["entities"]["features"].append(
        {
            "id": feature_id,
            "componentId": component_id,
            "name": name,
            "displayName": name,
            "cadType": "PartDesign::Pad",
            "identitySource": {
                "kind": "owner_scoped_key",
                "ownerScopedKey": owner_scoped_key,
                "nativeRef": name,
            },
            "stabilityClass": "conditionally_stable",
            "targetability": targetability(),
            "annotations": empty_annotations(),
        }
    )


class CaptureValidationBase(unittest.TestCase):
    def payload(self) -> dict[str, Any]:
        return valid_mapping()

    def assert_contract_problem(
        self,
        payload: dict[str, Any],
        *expected: str,
    ) -> CaptureContractError:
        with self.assertRaises(CaptureContractError) as raised:
            validate_capture_document(payload)
        message = str(raised.exception)
        for fragment in expected:
            self.assertIn(fragment, message)
        return raised.exception


class ValidDocumentTests(CaptureValidationBase):
    def test_valid_document_round_trips_without_mutation(self) -> None:
        payload = self.payload()
        original = copy.deepcopy(payload)

        document = CaptureDocument.from_mapping(payload)

        self.assertEqual(payload, original)
        self.assertEqual(document.to_mapping(), payload)

    def test_explicit_false_values_are_preserved(self) -> None:
        payload = self.payload()
        payload["entities"]["metadata"][0]["valueType"] = "boolean"
        payload["entities"]["metadata"][0]["currentValue"] = False

        document = CaptureDocument.from_mapping(payload)
        result = document.to_mapping()

        self.assertIs(result["entities"]["metadata"][0]["currentValue"], False)
        self.assertIs(
            result["entities"]["components"][0]["targetability"]["delete"],
            False,
        )

    def test_empty_relationships_are_supported(self) -> None:
        payload = self.payload()
        payload["entities"]["relationships"] = []

        validate_capture_document(payload)

    def test_current_value_may_be_absent(self) -> None:
        payload = self.payload()
        del payload["entities"]["parameters"][0]["currentValue"]

        document = CaptureDocument.from_mapping(payload)

        self.assertNotIn(
            "currentValue",
            document.to_mapping()["entities"]["parameters"][0],
        )


class RequiredFieldTests(CaptureValidationBase):
    def test_required_top_level_fields(self) -> None:
        cases = (
            ("schemaVersion", "schemaVersion is required"),
            ("captureId", "captureId is required"),
            ("adapter", "adapter is required"),
            ("cadSystem", "cadSystem is required"),
            ("sourceDocument", "sourceDocument is required"),
            ("rootProduct", "rootProduct is required"),
            ("annotations", "annotations is required"),
            ("entities", "entities is required"),
            ("structure", "structure is required"),
        )
        for field, fragment in cases:
            with self.subTest(field=field):
                payload = self.payload()
                del payload[field]
                self.assert_contract_problem(payload, fragment)

    def test_required_nested_fields(self) -> None:
        cases = (
            (
                lambda p: p["adapter"].pop("name"),
                "adapter.name is required",
            ),
            (
                lambda p: p["sourceDocument"].pop("fingerprint"),
                "sourceDocument.fingerprint is required",
            ),
            (
                lambda p: p["rootProduct"].pop("id"),
                "rootProduct.id is required",
            ),
            (
                lambda p: p["annotations"].pop("purpose"),
                "annotations.purpose is required",
            ),
            (
                lambda p: p["entities"].pop("components"),
                "entities.components is required",
            ),
            (
                lambda p: p["structure"].pop("rootComponentId"),
                "structure.rootComponentId is required",
            ),
            (
                lambda p: p["structure"].pop("nodes"),
                "structure.nodes is required",
            ),
            (
                lambda p: p["structure"]["nodes"][0].pop("children"),
                "structure.nodes[0].children is required",
            ),
        )
        for mutate, fragment in cases:
            with self.subTest(fragment=fragment):
                payload = self.payload()
                mutate(payload)
                self.assert_contract_problem(payload, fragment)

    def test_required_component_fields(self) -> None:
        for field in (
            "id",
            "kind",
            "name",
            "displayName",
            "cadType",
            "quantity",
            "material",
            "targetability",
            "annotations",
        ):
            with self.subTest(field=field):
                payload = self.payload()
                del payload["entities"]["components"][0][field]
                self.assert_contract_problem(
                    payload,
                    f"entities.components[0].{field} is required",
                )

    def test_required_metadata_key_and_no_semantic_name(self) -> None:
        payload = self.payload()
        del payload["entities"]["metadata"][0]["key"]
        self.assert_contract_problem(
            payload,
            "entities.metadata[0].key is required",
        )

        payload = self.payload()
        payload["entities"]["metadata"][0]["name"] = "Material"
        self.assert_contract_problem(
            payload,
            'entities.metadata[0] has unknown field "name"',
        )

        payload = self.payload()
        payload["entities"]["metadata"][0]["unit"] = "mm"
        self.assert_contract_problem(
            payload,
            'entities.metadata[0] has unknown field "unit"',
        )

    def test_required_annotations_fields(self) -> None:
        payload = self.payload()
        del payload["entities"]["components"][0]["annotations"]["comment"]
        self.assert_contract_problem(
            payload,
            "entities.components[0].annotations.comment is required",
        )

    def test_required_fields_for_each_entity_registry(self) -> None:
        required = {
            "features": (
                "id",
                "componentId",
                "name",
                "displayName",
                "cadType",
                "targetability",
                "annotations",
            ),
            "relationships": (
                "id",
                "kind",
                "componentId",
                "name",
                "cadType",
                "endpoints",
                "targetability",
                "annotations",
            ),
            "parameterGroups": (
                "id",
                "ownerComponentId",
                "name",
                "displayName",
                "groupKind",
                "cadType",
                "observable",
                "writable",
                "annotations",
            ),
            "parameters": (
                "id",
                "ownerKind",
                "ownerId",
                "componentId",
                "name",
                "displayName",
                "cadType",
                "valueType",
                "observable",
                "writable",
                "annotations",
            ),
            "metadata": (
                "id",
                "ownerKind",
                "ownerId",
                "componentId",
                "key",
                "displayName",
                "cadType",
                "valueType",
                "observable",
                "writable",
                "annotations",
            ),
        }
        for registry, fields in required.items():
            for field in fields:
                with self.subTest(registry=registry, field=field):
                    payload = self.payload()
                    del payload["entities"][registry][0][field]
                    self.assert_contract_problem(
                        payload,
                        f"entities.{registry}[0].{field} is required",
                    )


class ClosedFieldTests(CaptureValidationBase):
    def test_unknown_top_level_field(self) -> None:
        payload = self.payload()
        payload["extra"] = True
        self.assert_contract_problem(payload, 'root has unknown field "extra"')

    def test_unknown_entity_field(self) -> None:
        payload = self.payload()
        payload["entities"]["components"][0]["extra"] = True
        self.assert_contract_problem(
            payload,
            'entities.components[0] has unknown field "extra"',
        )

    def test_unknown_nested_object_fields(self) -> None:
        cases = (
            (
                lambda p: p["adapter"].__setitem__("extra", True),
                'adapter has unknown field "extra"',
            ),
            (
                lambda p: p["sourceDocument"].__setitem__("extra", True),
                'sourceDocument has unknown field "extra"',
            ),
            (
                lambda p: p["entities"]["components"][0]["annotations"].__setitem__(
                    "extra", True
                ),
                'entities.components[0].annotations has unknown field "extra"',
            ),
            (
                lambda p: p["entities"]["components"][0]["targetability"].__setitem__(
                    "extra", True
                ),
                'entities.components[0].targetability has unknown field "extra"',
            ),
            (
                lambda p: p["entities"]["components"][0]["identitySource"].__setitem__(
                    "extra", True
                ),
                'entities.components[0].identitySource has unknown field "extra"',
            ),
            (
                lambda p: p["structure"]["nodes"][0].__setitem__("extra", True),
                'structure.nodes[0] has unknown field "extra"',
            ),
        )
        for mutate, fragment in cases:
            with self.subTest(fragment=fragment):
                payload = self.payload()
                mutate(payload)
                self.assert_contract_problem(payload, fragment)


class NestedShapeTests(CaptureValidationBase):
    def test_entity_registry_must_be_an_array(self) -> None:
        payload = self.payload()
        payload["entities"]["components"] = {}
        self.assert_contract_problem(
            payload,
            "entities.components must be an array",
        )

    def test_entity_item_must_be_an_object(self) -> None:
        payload = self.payload()
        payload["entities"]["components"].append("not an object")
        self.assert_contract_problem(
            payload,
            "entities.components[2] must be an object",
        )

    def test_structure_shape_variants(self) -> None:
        payload = self.payload()
        payload["structure"]["nodes"] = {}
        self.assert_contract_problem(
            payload,
            "structure.nodes must be an array",
        )

        payload = self.payload()
        payload["structure"]["nodes"].append("not an object")
        self.assert_contract_problem(
            payload,
            "structure.nodes[2] must be an object",
        )

        payload = self.payload()
        del payload["structure"]["nodes"][0]["componentId"]
        self.assert_contract_problem(
            payload,
            "structure.nodes[0].componentId is required",
        )

        payload = self.payload()
        del payload["structure"]["nodes"][0]["parentComponentId"]
        self.assert_contract_problem(
            payload,
            "structure.nodes[0].parentComponentId is required",
        )

        payload = self.payload()
        payload["structure"]["nodes"][0]["children"] = "cmp.part"
        self.assert_contract_problem(
            payload,
            "structure.nodes[0].children must be an array",
        )

        payload = self.payload()
        payload["structure"]["nodes"][0]["children"] = [1]
        self.assert_contract_problem(
            payload,
            "structure.nodes[0].children[0] must be a string",
        )

        payload = self.payload()
        payload["structure"]["nodes"][0]["children"] = ["  "]
        self.assert_contract_problem(
            payload,
            "structure.nodes[0].children[0] is required",
        )

    def test_targetability_and_annotations_must_be_objects(self) -> None:
        payload = self.payload()
        payload["entities"]["components"][0]["targetability"] = True
        self.assert_contract_problem(
            payload,
            "entities.components[0].targetability must be an object",
        )

        payload = self.payload()
        payload["entities"]["components"][0]["annotations"] = []
        self.assert_contract_problem(
            payload,
            "entities.components[0].annotations must be an object",
        )

    def test_identity_source_must_be_an_object(self) -> None:
        payload = self.payload()
        payload["entities"]["components"][0]["identitySource"] = "cmp.root"
        self.assert_contract_problem(
            payload,
            "entities.components[0].identitySource must be an object",
        )

    def test_relationship_endpoints_shape(self) -> None:
        payload = self.payload()
        payload["entities"]["relationships"][0]["endpoints"] = "cmp.part"
        self.assert_contract_problem(
            payload,
            "entities.relationships[0].endpoints must be an array",
        )

        payload = self.payload()
        payload["entities"]["relationships"][0]["endpoints"] = [1]
        self.assert_contract_problem(
            payload,
            "entities.relationships[0].endpoints[0] must be a string",
        )

        payload = self.payload()
        payload["entities"]["relationships"][0]["endpoints"] = ["  "]
        self.assert_contract_problem(
            payload,
            "entities.relationships[0].endpoints[0] is required",
        )


class ScalarAndBooleanTests(CaptureValidationBase):
    def test_schema_version_must_be_exact(self) -> None:
        for value in ("2.0", "1", 1.0, None):
            with self.subTest(value=value):
                payload = self.payload()
                payload["schemaVersion"] = value
                self.assert_contract_problem(payload, "schemaVersion")

    def test_capture_id_must_be_nonblank_and_exact(self) -> None:
        payload = self.payload()
        payload["captureId"] = ""
        self.assert_contract_problem(payload, "captureId is required")

        payload = self.payload()
        payload["captureId"] = " cap "
        self.assert_contract_problem(
            payload,
            "captureId must not have leading or trailing whitespace",
        )

    def test_adapter_and_cad_system_names_and_versions(self) -> None:
        payload = self.payload()
        payload["adapter"]["name"] = ""
        self.assert_contract_problem(payload, "adapter.name is required")

        payload = self.payload()
        payload["cadSystem"]["version"] = "   "
        self.assert_contract_problem(
            payload,
            "cadSystem.version must not be blank",
        )

    def test_quantity_must_be_a_positive_integer(self) -> None:
        for value in (0, -1, True, 1.0, "1"):
            with self.subTest(value=value):
                payload = self.payload()
                payload["entities"]["components"][0]["quantity"] = value
                self.assert_contract_problem(
                    payload,
                    "entities.components[0].quantity",
                )

    def test_booleans_must_be_explicit_boolean_values(self) -> None:
        payload = self.payload()
        payload["entities"]["parameterGroups"][0]["observable"] = 1
        self.assert_contract_problem(
            payload,
            "entities.parameterGroups[0].observable must be a boolean",
        )

        payload = self.payload()
        payload["entities"]["parameterGroups"][0]["writable"] = "true"
        self.assert_contract_problem(
            payload,
            "entities.parameterGroups[0].writable must be a boolean",
        )

    def test_targetability_requires_all_five_booleans(self) -> None:
        payload = self.payload()
        del payload["entities"]["components"][0]["targetability"]["delete"]
        self.assert_contract_problem(
            payload,
            "entities.components[0].targetability.delete is required",
        )

        payload = self.payload()
        payload["entities"]["components"][0]["targetability"]["delete"] = "false"
        self.assert_contract_problem(
            payload,
            "entities.components[0].targetability.delete must be a boolean",
        )

    def test_current_value_null_array_and_object_are_rejected(self) -> None:
        for value in (None, [1], {"a": 1}):
            with self.subTest(value=value):
                payload = self.payload()
                payload["entities"]["metadata"][0]["currentValue"] = value
                self.assert_contract_problem(
                    payload,
                    "entities.metadata[0].currentValue must be a JSON scalar",
                )

    def test_current_value_must_match_declared_type(self) -> None:
        cases = (
            ("number", True, 'must match valueType "number"'),
            ("number", "10", 'must match valueType "number"'),
            ("string", 10, 'must match valueType "string"'),
            ("boolean", 0, 'must match valueType "boolean"'),
        )
        for value_type, value, fragment in cases:
            with self.subTest(value_type=value_type, value=value):
                payload = self.payload()
                payload["entities"]["metadata"][0]["valueType"] = value_type
                payload["entities"]["metadata"][0]["currentValue"] = value
                self.assert_contract_problem(
                    payload,
                    f"entities.metadata[0].currentValue {fragment}",
                )

    def test_non_finite_number_is_not_a_json_scalar(self) -> None:
        payload = self.payload()
        payload["entities"]["parameters"][0]["currentValue"] = math.nan
        self.assert_contract_problem(
            payload,
            "entities.parameters[0].currentValue must be a JSON scalar",
        )

    def test_empty_optional_strings_present_are_rejected(self) -> None:
        # Engine's parser rejects a present empty optional string even though
        # the public prose describes it as allowed. Capture follows the parser
        # so every emitted contract is accepted by Engine.
        payload = self.payload()
        payload["entities"]["parameters"][0]["unit"] = ""
        self.assert_contract_problem(
            payload,
            "entities.parameters[0].unit is required",
        )

        payload = self.payload()
        payload["entities"]["components"][0]["stabilityClass"] = ""
        self.assert_contract_problem(
            payload,
            "entities.components[0].stabilityClass is required",
        )

    def test_invalid_stability_class_is_rejected(self) -> None:
        payload = self.payload()
        payload["entities"]["components"][0]["stabilityClass"] = "maybe"
        self.assert_contract_problem(
            payload,
            "entities.components[0].stabilityClass must be one of",
        )

    def test_nonblank_annotations_may_be_empty_strings(self) -> None:
        payload = self.payload()
        payload["annotations"] = {"description": "", "comment": "", "purpose": ""}
        validate_capture_document(payload)

    def test_metadata_key_must_be_exact(self) -> None:
        for key in (" material", "material ", "mat\x00erial"):
            with self.subTest(key=repr(key)):
                payload = self.payload()
                payload["entities"]["metadata"][0]["key"] = key
                self.assert_contract_problem(
                    payload,
                    "entities.metadata[0].key must be an exact native property key",
                )

    def test_metadata_key_must_be_a_string(self) -> None:
        payload = self.payload()
        payload["entities"]["metadata"][0]["key"] = 1
        self.assert_contract_problem(
            payload,
            "entities.metadata[0].key must be a string",
        )

    def test_optional_source_file_shape(self) -> None:
        payload = self.payload()
        payload["entities"]["components"][0]["sourceFile"] = {
            "path": "input/part.FCStd"
        }
        document = CaptureDocument.from_mapping(payload)
        self.assertEqual(
            document.to_mapping()["entities"]["components"][0]["sourceFile"],
            {"path": "input/part.FCStd"},
        )

        payload = self.payload()
        payload["entities"]["components"][0]["sourceFile"] = {"path": ""}
        self.assert_contract_problem(
            payload,
            "entities.components[0].sourceFile.path is required",
        )

        payload = self.payload()
        payload["entities"]["components"][0]["sourceFile"] = "input/part.FCStd"
        self.assert_contract_problem(
            payload,
            "entities.components[0].sourceFile must be an object",
        )

        payload = self.payload()
        payload["entities"]["components"][0]["sourceFile"] = {
            "path": "input/part.FCStd",
            "extra": True,
        }
        self.assert_contract_problem(
            payload,
            'entities.components[0].sourceFile has unknown field "extra"',
        )


class ReferenceResolutionTests(CaptureValidationBase):
    def test_dangling_feature_component(self) -> None:
        payload = self.payload()
        payload["entities"]["features"][0]["componentId"] = "cmp.missing"
        self.assert_contract_problem(
            payload,
            'entities.features[0].componentId "cmp.missing" must resolve',
        )

    def test_dangling_relationship_component_and_endpoint(self) -> None:
        payload = self.payload()
        payload["entities"]["relationships"][0]["componentId"] = "cmp.missing"
        self.assert_contract_problem(
            payload,
            'entities.relationships[0].componentId "cmp.missing" must resolve',
        )

        payload = self.payload()
        payload["entities"]["relationships"][0]["endpoints"] = ["cmp.missing"]
        self.assert_contract_problem(
            payload,
            'entities.relationships[0].endpoints[0] "cmp.missing" must resolve',
        )

    def test_duplicate_relationship_endpoint(self) -> None:
        payload = self.payload()
        payload["entities"]["relationships"][0]["endpoints"] = [
            "cmp.part",
            "cmp.part",
        ]
        self.assert_contract_problem(
            payload,
            'entities.relationships[0].endpoints[1] duplicates endpoint "cmp.part"',
        )

    def test_dangling_parameter_group_owner(self) -> None:
        payload = self.payload()
        payload["entities"]["parameterGroups"][0]["ownerComponentId"] = "cmp.missing"
        self.assert_contract_problem(
            payload,
            'entities.parameterGroups[0].ownerComponentId "cmp.missing"',
        )

    def test_dangling_parameter_owner(self) -> None:
        payload = self.payload()
        payload["entities"]["parameters"][0]["ownerId"] = "grp.missing"
        self.assert_contract_problem(
            payload,
            'entities.parameters[0].ownerId "grp.missing" must resolve to an '
            "existing parameter group",
        )

    def test_parameter_group_owner_component_mismatch(self) -> None:
        payload = self.payload()
        payload["entities"]["parameters"][0]["componentId"] = "cmp.part"
        self.assert_contract_problem(
            payload,
            'entities.parameters[0].componentId "cmp.part" must match owner '
            "parameter group component",
        )

    def test_component_owned_parameter_component_must_equal_owner(self) -> None:
        payload = self.payload()
        parameter = payload["entities"]["parameters"][0]
        parameter["ownerKind"] = "component"
        parameter["ownerId"] = "cmp.root"
        parameter["componentId"] = "cmp.part"
        parameter["identitySource"] = {
            "kind": "owner_scoped_key",
            "ownerScopedKey": "length",
            "nativeRef": "Body.length",
        }
        self.assert_contract_problem(
            payload,
            "must equal ownerId for component-owned parameters",
        )

    def test_feature_owned_parameter_component_must_match_feature(self) -> None:
        payload = self.payload()
        parameter = payload["entities"]["parameters"][0]
        parameter["ownerKind"] = "feature"
        parameter["ownerId"] = "fea.enclosure.pad"
        parameter["componentId"] = "cmp.root"
        parameter["identitySource"] = {
            "kind": "owner_scoped_key",
            "ownerScopedKey": "length",
            "nativeRef": "Pad.length",
        }
        self.assert_contract_problem(
            payload,
            "must match owner feature component",
        )

    def test_dangling_metadata_owners(self) -> None:
        cases = (
            ("component", "cmp.missing", "component"),
            ("feature", "fea.missing", "feature"),
            ("relationship", "rel.missing", "relationship"),
        )
        for owner_kind, owner_id, noun in cases:
            with self.subTest(owner_kind=owner_kind):
                payload = self.payload()
                metadata = payload["entities"]["metadata"][0]
                metadata["ownerKind"] = owner_kind
                metadata["ownerId"] = owner_id
                metadata["componentId"] = "cmp.part"
                self.assert_contract_problem(
                    payload,
                    f'ownerId "{owner_id}" must resolve to an existing {noun}',
                )

    def test_metadata_component_must_agree_with_owner(self) -> None:
        payload = self.payload()
        payload["entities"]["metadata"][0]["componentId"] = "cmp.root"
        self.assert_contract_problem(
            payload,
            "must equal ownerId for component-owned metadata",
        )


class RootAndStructureTests(CaptureValidationBase):
    def test_root_product_must_resolve(self) -> None:
        payload = self.payload()
        payload["rootProduct"]["id"] = "cmp.missing"
        self.assert_contract_problem(
            payload,
            'rootProduct.id "cmp.missing" must resolve',
        )

    def test_structure_root_must_resolve(self) -> None:
        payload = self.payload()
        payload["structure"]["rootComponentId"] = "cmp.missing"
        self.assert_contract_problem(
            payload,
            'structure.rootComponentId "cmp.missing" must resolve',
        )

    def test_root_must_be_assembly(self) -> None:
        payload = self.payload()
        payload["entities"]["components"][0]["kind"] = "part"
        self.assert_contract_problem(
            payload,
            "must resolve to an assembly component",
        )

    def test_root_product_and_structure_root_must_match(self) -> None:
        payload = self.payload()
        payload["rootProduct"]["id"] = "cmp.part"
        self.assert_contract_problem(
            payload,
            "structure.rootComponentId must equal rootProduct.id",
        )

    def test_structure_nodes_must_not_be_empty(self) -> None:
        payload = self.payload()
        payload["structure"]["nodes"] = []
        self.assert_contract_problem(
            payload,
            "structure.nodes must not be empty",
        )

    def test_exactly_one_root_node(self) -> None:
        payload = self.payload()
        payload["structure"]["nodes"][1]["parentComponentId"] = ""
        self.assert_contract_problem(
            payload,
            "must contain exactly one root node",
        )

        payload = self.payload()
        payload["structure"]["nodes"][0]["parentComponentId"] = "cmp.part"
        self.assert_contract_problem(
            payload,
            "must contain exactly one root node",
        )

    def test_every_component_needs_a_node(self) -> None:
        payload = self.payload()
        payload["structure"]["nodes"] = [payload["structure"]["nodes"][0]]
        self.assert_contract_problem(
            payload,
            'structure.nodes must include component "cmp.part"',
        )

    def test_duplicate_node_is_rejected(self) -> None:
        payload = self.payload()
        payload["structure"]["nodes"].append(
            {
                "componentId": "cmp.part",
                "parentComponentId": "cmp.root",
                "children": [],
            }
        )
        self.assert_contract_problem(
            payload,
            'structure.nodes[2].componentId "cmp.part" duplicates node',
        )

    def test_self_parent_and_self_child_are_rejected(self) -> None:
        payload = self.payload()
        payload["structure"]["nodes"][1]["parentComponentId"] = "cmp.part"
        self.assert_contract_problem(
            payload,
            "must not reference the same component",
        )

        payload = self.payload()
        payload["structure"]["nodes"][1]["children"] = ["cmp.part"]
        self.assert_contract_problem(
            payload,
            "must not reference the same component",
        )

    def test_child_parent_consistency(self) -> None:
        payload = self.payload()
        _add_third_component(payload, parent_id="cmp.part")
        # Declare the extra component's parent as root while part lists it.
        for node in payload["structure"]["nodes"]:
            if node["componentId"] == "cmp.extra":
                node["parentComponentId"] = "cmp.root"
        self.assert_contract_problem(
            payload,
            'references child "cmp.extra" whose declared parent is "cmp.root"',
        )

    def test_cycle_is_rejected(self) -> None:
        payload = self.payload()
        payload["structure"]["nodes"][1]["children"] = ["cmp.root"]
        self.assert_contract_problem(
            payload,
            "structure.nodes must not contain cycles",
        )

    def test_disconnected_component_is_rejected(self) -> None:
        payload = self.payload()
        _add_third_component(payload, parent_id="cmp.part")
        # Detach the extra component from part's child list.
        for node in payload["structure"]["nodes"]:
            if node["componentId"] == "cmp.part":
                node["children"] = []
        self.assert_contract_problem(
            payload,
            'structure component "cmp.extra" is not reachable',
        )


class IdentitySourceTests(CaptureValidationBase):
    def test_component_identity_requires_parent_scoped_path(self) -> None:
        payload = self.payload()
        payload["entities"]["components"][0]["identitySource"]["kind"] = (
            "owner_scoped_key"
        )
        self.assert_contract_problem(
            payload,
            'identitySource.kind must be "parent_scoped_path"',
        )

        payload = self.payload()
        del payload["entities"]["components"][0]["identitySource"]["path"]
        self.assert_contract_problem(
            payload,
            "entities.components[0].identitySource.path is required",
        )

    def test_feature_identity_requires_owner_scoped_key(self) -> None:
        payload = self.payload()
        payload["entities"]["features"][0]["identitySource"]["kind"] = (
            "parent_scoped_path"
        )
        self.assert_contract_problem(
            payload,
            'identitySource.kind must be "owner_scoped_key"',
        )

        payload = self.payload()
        del payload["entities"]["features"][0]["identitySource"]["ownerScopedKey"]
        self.assert_contract_problem(
            payload,
            "entities.features[0].identitySource.ownerScopedKey is required",
        )

    def test_group_identity_requires_owner_scoped_key(self) -> None:
        payload = self.payload()
        del payload["entities"]["parameterGroups"][0]["identitySource"][
            "ownerScopedKey"
        ]
        self.assert_contract_problem(
            payload,
            "entities.parameterGroups[0].identitySource.ownerScopedKey is required",
        )

    def test_group_owned_parameter_requires_group_scoped_key(self) -> None:
        payload = self.payload()
        del payload["entities"]["parameters"][0]["identitySource"]["groupScopedKey"]
        self.assert_contract_problem(
            payload,
            "entities.parameters[0].identitySource.groupScopedKey is required",
        )

    def test_metadata_identity_requires_owner_scoped_key(self) -> None:
        payload = self.payload()
        payload["entities"]["metadata"][0]["identitySource"] = {
            "kind": "owner_scoped_key",
        }
        self.assert_contract_problem(
            payload,
            "entities.metadata[0].identitySource.ownerScopedKey is required",
        )

    def test_relationship_identity_kind_is_not_further_constrained(self) -> None:
        payload = self.payload()
        payload["entities"]["relationships"][0]["identitySource"] = {
            "kind": "custom_relationship_identity",
        }
        validate_capture_document(payload)

    def test_duplicate_component_identity_path_is_rejected(self) -> None:
        payload = self.payload()
        payload["entities"]["components"][1]["identitySource"]["path"] = "cmp.root"
        self.assert_contract_problem(
            payload,
            "duplicates parent-scoped identity source already declared at",
        )

    def test_duplicate_feature_identity_key_in_component_scope(self) -> None:
        payload = self.payload()
        _add_feature(payload, owner_scoped_key="Pad")
        self.assert_contract_problem(
            payload,
            'ownerScopedKey "Pad" duplicates owner-scoped identity source',
        )

    def test_duplicate_group_identity_key_in_owner_component_scope(self) -> None:
        payload = self.payload()
        payload["entities"]["parameterGroups"].append(
            {
                "id": "grp.root.parameters2",
                "ownerComponentId": "cmp.root",
                "name": "Parameters2",
                "displayName": "Parameters 2",
                "groupKind": "varset",
                "cadType": "App::VarSet",
                "observable": True,
                "writable": True,
                "identitySource": {
                    "kind": "owner_scoped_key",
                    "ownerScopedKey": "Parameters",
                    "nativeRef": "Parameters2",
                },
                "stabilityClass": "stable",
                "annotations": empty_annotations(),
            }
        )
        self.assert_contract_problem(
            payload,
            'ownerScopedKey "Parameters" duplicates owner-scoped identity source',
        )

    def test_parameter_and_metadata_share_owner_key_scope(self) -> None:
        payload = self.payload()
        payload["entities"]["metadata"][0]["identitySource"] = {
            "kind": "owner_scoped_key",
            "ownerScopedKey": "material",
            "nativeRef": "Body.material",
        }
        payload["entities"]["parameters"].append(
            {
                "id": "par.part.material",
                "ownerKind": "component",
                "ownerId": "cmp.part",
                "componentId": "cmp.part",
                "name": "materialParam",
                "displayName": "Material Param",
                "cadType": "App::PropertyString",
                "valueType": "string",
                "observable": True,
                "writable": True,
                "currentValue": "PLA",
                "identitySource": {
                    "kind": "owner_scoped_key",
                    "ownerScopedKey": "material",
                    "nativeRef": "Body.material",
                },
                "stabilityClass": "stable",
                "annotations": empty_annotations(),
            }
        )
        self.assert_contract_problem(
            payload,
            'ownerScopedKey "material" duplicates owner-scoped identity source',
        )

    def test_same_owner_key_in_different_scopes_is_allowed(self) -> None:
        payload = self.payload()
        payload["entities"]["metadata"][0]["identitySource"] = {
            "kind": "owner_scoped_key",
            "ownerScopedKey": "material",
            "nativeRef": "Body.material",
        }
        payload["entities"]["parameters"].append(
            {
                "id": "par.root.material",
                "ownerKind": "component",
                "ownerId": "cmp.root",
                "componentId": "cmp.root",
                "name": "materialParam",
                "displayName": "Material Param",
                "cadType": "App::PropertyString",
                "valueType": "string",
                "observable": True,
                "writable": True,
                "currentValue": "PLA",
                "identitySource": {
                    "kind": "owner_scoped_key",
                    "ownerScopedKey": "material",
                    "nativeRef": "CaptureCore.material",
                },
                "stabilityClass": "stable",
                "annotations": empty_annotations(),
            }
        )
        validate_capture_document(payload)


class DeterminismAndImmutabilityTests(CaptureValidationBase):
    def test_contract_failure_is_deterministic(self) -> None:
        payload = self.payload()
        payload["entities"]["features"][0]["componentId"] = "cmp.missing"

        messages = []
        for _ in range(2):
            with self.assertRaises(CaptureContractError) as raised:
                validate_capture_document(copy.deepcopy(payload))
            messages.append(str(raised.exception))
        self.assertEqual(messages[0], messages[1])

    def test_validation_does_not_mutate_input(self) -> None:
        payload = self.payload()
        original = copy.deepcopy(payload)

        validate_capture_document(payload)

        self.assertEqual(payload, original)

    def test_problems_are_ordered_and_classified(self) -> None:
        payload = self.payload()
        del payload["entities"]["components"][0]["quantity"]
        payload["entities"]["components"][0]["extra"] = True

        with self.assertRaises(CaptureContractError) as raised:
            validate_capture_document(payload)

        problems = raised.exception.problems
        self.assertEqual(
            problems,
            (
                'entities.components[0] has unknown field "extra"',
                "entities.components[0].quantity is required",
            ),
        )


if __name__ == "__main__":
    unittest.main()
