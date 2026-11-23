"""GUI-free tests for FreeCAD semantic-map generation, merge, and writing."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from parametron_freecad.capture import (
    FREECAD_CAD_SYSTEM_MIN_VERSION,
    FREECAD_SEMANTIC_MAP_TEMPLATE_VERSION,
    SEMANTIC_MAP_SCHEMA_VERSION,
    FreeCADSemanticMapSelection,
    SemanticMapConfirmationRequiredError,
    SemanticMapContractError,
    SemanticMapDecodeError,
    SemanticMapDiffEntry,
    SemanticMapIdentityError,
    SemanticMapSelectionError,
    SemanticMapWriteError,
    SemanticParameterTypeSelection,
    build_semantic_map,
    canonical_semantic_map_bytes,
    canonical_semantic_map_text,
    freecad_semantic_map_template,
    plan_semantic_map_update,
    update_semantic_map,
    validate_semantic_map,
    write_semantic_map,
)
from parametron_freecad.capture.native_types import (
    METADATA_NATIVE_TYPES,
    METADATA_RESOLVED_VALUE_KINDS,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
METADATA_FIXTURE = FIXTURE_ROOT / "metadata_mutation" / "prm.semantic-map.json"
CANONICAL_FIXTURE = FIXTURE_ROOT / "canonical_lifecycle" / "prm.semantic-map.json"


def _load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_selection(
    *,
    mapping_id: str = "freecad-example-v1",
    parameter_types: tuple[SemanticParameterTypeSelection, ...] | None = None,
    native_map: dict[str, str] | None = None,
    cad_system_min_version: str = FREECAD_CAD_SYSTEM_MIN_VERSION,
) -> FreeCADSemanticMapSelection:
    return FreeCADSemanticMapSelection(
        mapping_id=mapping_id,
        parameter_types=parameter_types
        if parameter_types is not None
        else (
            SemanticParameterTypeSelection(
                "length",
                "number",
                "mm",
                "number_to_length",
            ),
            SemanticParameterTypeSelection(
                "count",
                "integer",
                "count",
                "number_to_integer_exact",
            ),
        ),
        native_type_to_semantic_type=native_map
        if native_map is not None
        else {
            "App::PropertyLength": "length",
            "App::PropertyFloat": "length",
            "App::PropertyInteger": "count",
        },
        cad_system_min_version=cad_system_min_version,
    )


def _selection_from_fixture(fixture: dict) -> FreeCADSemanticMapSelection:
    parameter_types = tuple(
        SemanticParameterTypeSelection(
            name=name,
            value_kind=entry["valueKind"],
            default_unit=entry["defaultUnit"],
            coercion=entry["coercion"],
        )
        for name, entry in sorted(fixture["semanticTypes"]["parameterTypes"].items())
    )
    return FreeCADSemanticMapSelection(
        mapping_id=fixture["mappingId"],
        parameter_types=parameter_types,
        native_type_to_semantic_type=fixture["captureToSemantic"]["parameters"][0][
            "semanticType"
        ]["map"],
        cad_system_min_version=fixture["cadSystem"]["minVersion"],
    )


class SemanticMapTemplateTests(unittest.TestCase):
    def test_template_version_is_one(self) -> None:
        self.assertEqual(FREECAD_SEMANTIC_MAP_TEMPLATE_VERSION, "1")

    def test_template_contains_fixed_freecad_contract_sections(self) -> None:
        template = freecad_semantic_map_template()

        self.assertEqual(template["schemaVersion"], SEMANTIC_MAP_SCHEMA_VERSION)
        self.assertEqual(template["adapter"], "freecad")
        self.assertEqual(template["cadSystem"]["name"], "FreeCAD")
        self.assertEqual(
            template["cadSystem"]["minVersion"],
            FREECAD_CAD_SYSTEM_MIN_VERSION,
        )
        self.assertEqual(template["mappingId"], "")
        self.assertEqual(template["semanticTypes"]["parameterTypes"], {})
        self.assertEqual(
            template["captureToSemantic"]["parameters"][0]["semanticType"]["map"],
            {},
        )
        self.assertEqual(
            set(template["operationCapabilities"]),
            {
                "suppress",
                "hide",
                "delete",
                "write_parameter",
                "write_metadata",
            },
        )
        for value in template["overridePolicy"].values():
            self.assertIs(value, False)
        for value in template["determinism"].values():
            self.assertIs(value, False)

    def test_template_metadata_value_kinds_match_shared_contract(self) -> None:
        template = freecad_semantic_map_template()
        metadata = template["captureToSemantic"]["metadata"][0]

        self.assertEqual(
            metadata["nativeValueKinds"],
            dict(METADATA_RESOLVED_VALUE_KINDS),
        )
        self.assertEqual(set(metadata["nativeValueKinds"]), set(METADATA_NATIVE_TYPES))
        self.assertEqual(len(metadata["nativeValueKinds"]), 6)
        self.assertEqual(
            metadata["nativeValueKinds"]["App::PropertyFloat"],
            "number",
        )
        self.assertEqual(
            metadata["nativeValueKinds"]["App::PropertyInteger"],
            "integer",
        )

    def test_template_is_fresh_on_each_call(self) -> None:
        first = freecad_semantic_map_template()
        second = freecad_semantic_map_template()

        first["captureToSemantic"]["parameterGroups"].append(
            {"captureKind": "x", "cadContainerType": "y", "semanticKind": "z"}
        )
        first["captureToSemantic"]["metadata"][0]["nativeValueKinds"].clear()

        self.assertEqual(len(second["captureToSemantic"]["parameterGroups"]), 1)
        self.assertEqual(
            second["captureToSemantic"]["metadata"][0]["nativeValueKinds"],
            dict(METADATA_RESOLVED_VALUE_KINDS),
        )

    def test_incomplete_template_is_not_a_valid_generated_map(self) -> None:
        with self.assertRaises(SemanticMapContractError) as raised:
            validate_semantic_map(freecad_semantic_map_template())

        message = str(raised.exception)
        self.assertIn("mappingId is required", message)
        self.assertIn("semanticTypes.parameterTypes must not be empty", message)
        self.assertIn(
            "captureToSemantic.parameters[0].semanticType.map must not be empty",
            message,
        )


class SemanticMapGenerationTests(unittest.TestCase):
    def test_build_applies_explicit_parameter_types_and_units(self) -> None:
        selection = _valid_selection()
        generated = build_semantic_map(selection)

        self.assertEqual(generated["mappingId"], "freecad-example-v1")
        self.assertEqual(
            generated["cadSystem"]["minVersion"],
            FREECAD_CAD_SYSTEM_MIN_VERSION,
        )
        self.assertEqual(
            generated["semanticTypes"]["parameterTypes"],
            {
                "length": {
                    "valueKind": "number",
                    "defaultUnit": "mm",
                    "coercion": "number_to_length",
                },
                "count": {
                    "valueKind": "integer",
                    "defaultUnit": "count",
                    "coercion": "number_to_integer_exact",
                },
            },
        )
        self.assertEqual(
            generated["captureToSemantic"]["parameters"][0]["semanticType"]["map"],
            {
                "App::PropertyLength": "length",
                "App::PropertyFloat": "length",
                "App::PropertyInteger": "count",
            },
        )
        validate_semantic_map(generated)

    def test_generated_map_reproduces_committed_metadata_fixture(self) -> None:
        fixture = _load_fixture(METADATA_FIXTURE)
        generated = build_semantic_map(_selection_from_fixture(fixture))

        self.assertEqual(generated, fixture)
        self.assertEqual(
            canonical_semantic_map_bytes(generated),
            canonical_semantic_map_bytes(fixture),
        )

    def test_canonical_output_is_stable_and_compact(self) -> None:
        generated = build_semantic_map(_valid_selection())

        first = canonical_semantic_map_bytes(generated)
        second = canonical_semantic_map_bytes(generated)
        text = canonical_semantic_map_text(generated)

        self.assertEqual(first, second)
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))
        self.assertEqual(
            text,
            json.dumps(
                json.loads(text),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
        )

    def test_canonicalization_sorts_mapping_arrays_and_targets(self) -> None:
        generated = build_semantic_map(_valid_selection())
        generated["captureToSemantic"]["parameterGroups"].append(
            {
                "captureKind": "parameter_group",
                "cadContainerType": "VarSet",
                "semanticKind": "parameter_group",
            }
        )
        generated["operationCapabilities"]["delete"]["allowedSemanticTargets"] = [
            "part",
            "feature",
        ]

        decoded = json.loads(canonical_semantic_map_bytes(generated))

        groups = decoded["captureToSemantic"]["parameterGroups"]
        self.assertEqual(
            [item["cadContainerType"] for item in groups],
            ["App::VarSet", "VarSet"],
        )
        self.assertEqual(
            decoded["operationCapabilities"]["delete"]["allowedSemanticTargets"],
            ["feature", "part"],
        )

    def test_build_does_not_mutate_selection_or_template(self) -> None:
        selection = _valid_selection()
        native_map_before = copy.deepcopy(selection.native_type_to_semantic_type)
        template_before = freecad_semantic_map_template()

        build_semantic_map(selection)

        self.assertEqual(selection.native_type_to_semantic_type, native_map_before)
        self.assertEqual(freecad_semantic_map_template(), template_before)

    def test_build_rejects_unsupported_selections(self) -> None:
        cases = (
            (
                _valid_selection(mapping_id=""),
                "mappingId is required",
            ),
            (
                _valid_selection(mapping_id=" map "),
                "mappingId must not have leading or trailing whitespace",
            ),
            (
                _valid_selection(parameter_types=()),
                "semanticTypes.parameterTypes must not be empty",
            ),
            (
                _valid_selection(cad_system_min_version=" "),
                "cadSystem.minVersion is required",
            ),
            (
                _valid_selection(native_map={}),
                "semanticType.map must not be empty",
            ),
            (
                _valid_selection(native_map={"App::PropertyVector": "length"}),
                "is not a supported FreeCAD parameter native type",
            ),
            (
                _valid_selection(native_map={"App::PropertyLength": "unknown"}),
                "references unknown semantic type",
            ),
            (
                _valid_selection(
                    parameter_types=(
                        SemanticParameterTypeSelection(
                            "length",
                            "boolean",
                            "none",
                            "number_to_length",
                        ),
                    ),
                    native_map={"App::PropertyLength": "length"},
                ),
                'coercion "number_to_length" requires valueKind "number"',
            ),
            (
                _valid_selection(
                    parameter_types=(
                        SemanticParameterTypeSelection(
                            "length",
                            "number",
                            "mm",
                            "number_to_magic",
                        ),
                    ),
                    native_map={"App::PropertyLength": "length"},
                ),
                'coercion "number_to_magic" is not supported',
            ),
            (
                _valid_selection(
                    parameter_types=(
                        SemanticParameterTypeSelection(
                            "length", "number", "", "number_to_length"
                        ),
                    ),
                    native_map={"App::PropertyLength": "length"},
                ),
                "defaultUnit is required",
            ),
            (
                _valid_selection(
                    parameter_types=(
                        SemanticParameterTypeSelection(
                            "length",
                            "number",
                            "mm",
                            "number_to_length",
                        ),
                        SemanticParameterTypeSelection(
                            "length",
                            "number",
                            "mm",
                            "number_to_length",
                        ),
                    ),
                    native_map={"App::PropertyLength": "length"},
                ),
                "duplicates semantic type",
            ),
        )
        for selection, fragment in cases:
            with self.subTest(fragment=fragment):
                with self.assertRaises(SemanticMapSelectionError) as raised:
                    build_semantic_map(selection)
                self.assertIn(fragment, str(raised.exception))

    def test_selection_must_have_an_object_for_native_map(self) -> None:
        selection = FreeCADSemanticMapSelection(
            mapping_id="example",
            parameter_types=(
                SemanticParameterTypeSelection(
                    "length",
                    "number",
                    "mm",
                    "number_to_length",
                ),
            ),
            native_type_to_semantic_type=["not-a-map"],  # type: ignore[arg-type]
        )

        with self.assertRaises(SemanticMapSelectionError) as raised:
            build_semantic_map(selection)

        self.assertIn("semanticType.map must be an object", str(raised.exception))

    def test_build_requires_selection_record(self) -> None:
        with self.assertRaises(TypeError):
            build_semantic_map(object())  # type: ignore[arg-type]


class SemanticMapValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid = build_semantic_map(_valid_selection())

    def _assert_problem(self, mapping: dict, *fragments: str) -> None:
        with self.assertRaises(SemanticMapContractError) as raised:
            validate_semantic_map(mapping)
        message = str(raised.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)

    def test_committed_metadata_fixture_is_valid(self) -> None:
        validate_semantic_map(_load_fixture(METADATA_FIXTURE))

    def test_unknown_fields_are_rejected(self) -> None:
        cases = (
            (("extra",), 'root has unknown field "extra"'),
            (
                ("cadSystem", "extra"),
                'cadSystem has unknown field "extra"',
            ),
            (
                ("semanticTypes", "extra"),
                'semanticTypes has unknown field "extra"',
            ),
            (
                ("captureToSemantic", "extra"),
                'captureToSemantic has unknown field "extra"',
            ),
            (
                ("semanticToManifest", "extra"),
                'semanticToManifest has unknown field "extra"',
            ),
            (
                ("determinism", "extra"),
                'determinism has unknown field "extra"',
            ),
        )
        for path, fragment in cases:
            with self.subTest(path=path):
                mapping = copy.deepcopy(self.valid)
                current = mapping
                for key in path[:-1]:
                    current = current[key]
                current[path[-1]] = True
                self._assert_problem(mapping, fragment)

    def test_missing_required_sections_are_rejected(self) -> None:
        for field in (
            "schemaVersion",
            "mappingId",
            "adapter",
            "cadSystem",
            "semanticTypes",
            "captureToSemantic",
            "semanticToManifest",
            "overridePolicy",
            "operationCapabilities",
            "determinism",
        ):
            with self.subTest(field=field):
                mapping = copy.deepcopy(self.valid)
                del mapping[field]
                self._assert_problem(mapping, f"{field} is required")

    def test_invalid_parameter_semantic_references_are_rejected(self) -> None:
        mapping = copy.deepcopy(self.valid)
        mapping["captureToSemantic"]["parameters"][0]["semanticType"]["map"][
            "App::PropertyBool"
        ] = "missing"
        self._assert_problem(
            mapping, "references unknown semanticTypes.parameterTypes key"
        )

    def test_duplicate_natural_keys_are_rejected(self) -> None:
        mapping = copy.deepcopy(self.valid)
        mapping["captureToSemantic"]["parameterGroups"].append(
            copy.deepcopy(mapping["captureToSemantic"]["parameterGroups"][0])
        )
        self._assert_problem(
            mapping,
            "duplicates the natural key of an earlier parameter group mapping",
        )

        mapping = copy.deepcopy(self.valid)
        mapping["captureToSemantic"]["components"].append(
            copy.deepcopy(mapping["captureToSemantic"]["components"][0])
        )
        self._assert_problem(
            mapping,
            "duplicates the natural key of an earlier component mapping",
        )

    def test_invalid_outputs_and_mutations_are_rejected(self) -> None:
        mapping = copy.deepcopy(self.valid)
        mapping["semanticToManifest"]["outputs"]["dxf"] = {"manifestType": "dxf"}
        self._assert_problem(mapping, 'manifestType "dxf" is not supported')

        mapping = copy.deepcopy(self.valid)
        del mapping["semanticToManifest"]["outputs"]["csv"]["scopeMap"]
        self._assert_problem(mapping, "scopeMap is required")

        mapping = copy.deepcopy(self.valid)
        mapping["semanticToManifest"]["outputs"]["pdf"]["targetField"] = "object"
        self._assert_problem(mapping, "targetField must not be set")

        mapping = copy.deepcopy(self.valid)
        mapping["semanticToManifest"]["mutations"]["set_property"] = {
            "manifestCollection": "partMutations.properties",
            "targetField": "object",
            "propertyField": "property",
            "valueField": "value",
        }
        self._assert_problem(
            mapping,
            'manifestCollection "partMutations.properties" is not supported',
        )

    def test_invalid_operation_capabilities_are_rejected(self) -> None:
        mapping = copy.deepcopy(self.valid)
        mapping["operationCapabilities"]["explode"] = {
            "allowedSemanticTargets": ["part"]
        }
        self._assert_problem(
            mapping, "operationCapabilities['explode'] is not supported"
        )

        mapping = copy.deepcopy(self.valid)
        mapping["operationCapabilities"]["suppress"]["allowedSemanticTargets"] = []
        self._assert_problem(mapping, "allowedSemanticTargets must not be empty")

        mapping = copy.deepcopy(self.valid)
        mapping["operationCapabilities"]["suppress"]["allowedSemanticTargets"] = [
            "part",
            "part",
        ]
        self._assert_problem(mapping, "duplicates an earlier semantic target")

        mapping = copy.deepcopy(self.valid)
        mapping["operationCapabilities"]["suppress"]["allowedSemanticTargets"] = [
            "unknown"
        ]
        self._assert_problem(mapping, '"unknown" is not supported')

    def test_true_policy_flags_are_rejected(self) -> None:
        mapping = copy.deepcopy(self.valid)
        mapping["overridePolicy"]["allowUserOverrides"] = True
        self._assert_problem(mapping, "overridePolicy.allowUserOverrides must be false")

        mapping = copy.deepcopy(self.valid)
        mapping["determinism"]["allowCaseInsensitiveMatch"] = True
        self._assert_problem(
            mapping,
            "determinism.allowCaseInsensitiveMatch must be false",
        )

        mapping = copy.deepcopy(self.valid)
        mapping["semanticTypes"]["resolutionPolicy"]["allowEngineDefault"] = True
        self._assert_problem(
            mapping,
            "semanticTypes.resolutionPolicy.allowEngineDefault must be false",
        )

    def test_invalid_metadata_native_value_kinds_are_rejected(self) -> None:
        mapping = copy.deepcopy(self.valid)
        mapping["captureToSemantic"]["metadata"][0]["nativeValueKinds"][
            "App::PropertyFloat"
        ] = "float"
        self._assert_problem(mapping, '"float" is not supported')

        mapping = copy.deepcopy(self.valid)
        mapping["captureToSemantic"]["metadata"][0]["nativeValueKinds"] = {}
        self._assert_problem(mapping, "nativeValueKinds must not be empty")

    def test_retired_properties_mutation_family_is_rejected(self) -> None:
        canonical_fixture = _load_fixture(CANONICAL_FIXTURE)

        with self.assertRaises(SemanticMapContractError) as raised:
            validate_semantic_map(canonical_fixture)

        self.assertIn("partMutations.properties", str(raised.exception))

    def test_validation_is_deterministic(self) -> None:
        mapping = copy.deepcopy(self.valid)
        mapping["operationCapabilities"]["explode"] = {
            "allowedSemanticTargets": ["unknown"]
        }

        messages = []
        for _ in range(2):
            with self.assertRaises(SemanticMapContractError) as raised:
                validate_semantic_map(copy.deepcopy(mapping))
            messages.append(str(raised.exception))
        self.assertEqual(messages[0], messages[1])

    def test_non_mapping_root_is_rejected(self) -> None:
        with self.assertRaises(SemanticMapContractError) as raised:
            validate_semantic_map([])  # type: ignore[arg-type]
        self.assertIn("root must be an object", str(raised.exception))


class SemanticMapMergeAndWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)
        self.path = self.directory / "prm.semantic-map.json"

    def _write_map(self, mapping: dict) -> None:
        self.path.write_bytes(canonical_semantic_map_bytes(mapping))

    def _temporary_files(self) -> list[Path]:
        return sorted(self.directory.glob(".*.tmp"))

    def test_create_plan_and_write(self) -> None:
        generated = build_semantic_map(_valid_selection())

        plan = plan_semantic_map_update(self.path, generated)
        self.assertEqual(plan.status, "create")
        self.assertIsNone(plan.existing)
        self.assertFalse(plan.requires_confirmation)
        self.assertEqual(plan.diff, ())

        result = write_semantic_map(
            self.path,
            generated,
            confirm_replace=False,
        )
        self.assertEqual(result.status, "create")
        self.assertTrue(result.wrote)
        self.assertEqual(
            self.path.read_bytes(), canonical_semantic_map_bytes(generated)
        )
        self.assertEqual(self._temporary_files(), [])

    def test_identical_existing_map_is_unchanged(self) -> None:
        generated = build_semantic_map(_valid_selection())
        self._write_map(generated)
        before = self.path.read_bytes()

        plan = plan_semantic_map_update(self.path, generated)
        result = write_semantic_map(self.path, generated, confirm_replace=True)

        self.assertEqual(plan.status, "unchanged")
        self.assertFalse(plan.requires_confirmation)
        self.assertEqual(result.status, "unchanged")
        self.assertFalse(result.wrote)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self._temporary_files(), [])

    def test_merge_preserves_user_edits_and_applies_selection(self) -> None:
        existing = build_semantic_map(_valid_selection(mapping_id="old-v1"))
        existing["captureToSemantic"]["parameterGroups"] = [
            {
                "captureKind": "parameter_group",
                "cadContainerType": "VarSet",
                "semanticKind": "parameter_group",
            }
        ]
        existing["operationCapabilities"]["delete"]["allowedSemanticTargets"] = [
            "part",
            "feature",
        ]
        del existing["semanticToManifest"]["mutations"]["unsuppress"]
        self._write_map(existing)
        existing_before = self.path.read_bytes()

        generated = build_semantic_map(
            _valid_selection(
                mapping_id="new-v1",
                parameter_types=(
                    SemanticParameterTypeSelection(
                        "length",
                        "number",
                        "mm",
                        "number_to_length",
                    ),
                ),
                native_map={"App::PropertyLength": "length"},
            )
        )
        plan = plan_semantic_map_update(self.path, generated)

        self.assertEqual(plan.status, "merge")
        self.assertTrue(plan.requires_confirmation)
        self.assertEqual(self.path.read_bytes(), existing_before)
        self.assertEqual(plan.merged["mappingId"], "new-v1")
        self.assertEqual(
            set(plan.merged["semanticTypes"]["parameterTypes"]),
            {"length"},
        )
        self.assertEqual(
            plan.merged["captureToSemantic"]["parameterGroups"],
            [
                {
                    "captureKind": "parameter_group",
                    "cadContainerType": "VarSet",
                    "semanticKind": "parameter_group",
                }
            ],
        )
        self.assertNotIn(
            "unsuppress",
            plan.merged["semanticToManifest"]["mutations"],
        )
        self.assertEqual(
            sorted(
                plan.merged["operationCapabilities"]["delete"]["allowedSemanticTargets"]
            ),
            ["feature", "part"],
        )
        diff_paths = {entry.path for entry in plan.diff}
        self.assertIn("/mappingId", diff_paths)
        self.assertTrue(
            any(path.startswith("/semanticTypes/parameterTypes") for path in diff_paths)
        )
        self.assertTrue(
            any(path.startswith("/captureToSemantic/parameters") for path in diff_paths)
        )
        self.assertFalse(
            any(
                path.startswith("/captureToSemantic/parameterGroups")
                for path in diff_paths
            )
        )
        self.assertFalse(
            any(path.startswith("/semanticToManifest") for path in diff_paths)
        )
        self.assertFalse(
            any(path.startswith("/operationCapabilities") for path in diff_paths)
        )

        with self.assertRaises(SemanticMapConfirmationRequiredError) as raised:
            write_semantic_map(self.path, generated, confirm_replace=False)
        self.assertEqual(raised.exception.diff, plan.diff)
        self.assertEqual(self.path.read_bytes(), existing_before)

        result = write_semantic_map(self.path, generated, confirm_replace=True)
        self.assertEqual(result.status, "merge")
        self.assertTrue(result.wrote)
        self.assertEqual(
            self.path.read_bytes(), canonical_semantic_map_bytes(plan.merged)
        )
        self.assertEqual(self._temporary_files(), [])

        persisted = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(
            persisted["captureToSemantic"]["parameterGroups"][0]["cadContainerType"],
            "VarSet",
        )
        self.assertNotIn("unsuppress", persisted["semanticToManifest"]["mutations"])

    def test_update_semantic_map_convenience_and_repeatability(self) -> None:
        selection = _valid_selection()
        first = update_semantic_map(
            self.path,
            selection,
            confirm_replace=False,
        )
        first_bytes = self.path.read_bytes()
        second = update_semantic_map(
            self.path,
            selection,
            confirm_replace=True,
        )

        self.assertEqual(first.status, "create")
        self.assertTrue(first.wrote)
        self.assertEqual(second.status, "unchanged")
        self.assertFalse(second.wrote)
        self.assertEqual(self.path.read_bytes(), first_bytes)

    def test_existing_invalid_json_is_not_overwritten(self) -> None:
        self.path.write_text("{", encoding="utf-8")
        before = self.path.read_bytes()
        generated = build_semantic_map(_valid_selection())

        with self.assertRaises(SemanticMapDecodeError):
            plan_semantic_map_update(self.path, generated)
        with self.assertRaises(SemanticMapDecodeError):
            write_semantic_map(self.path, generated, confirm_replace=True)

        self.assertEqual(self.path.read_bytes(), before)

    def test_existing_duplicate_json_keys_are_rejected(self) -> None:
        self.path.write_text(
            '{"schemaVersion":"1.0","schemaVersion":"1.0"}',
            encoding="utf-8",
        )
        generated = build_semantic_map(_valid_selection())

        with self.assertRaises(SemanticMapDecodeError):
            plan_semantic_map_update(self.path, generated)

    def test_existing_invalid_map_is_not_overwritten(self) -> None:
        invalid = build_semantic_map(_valid_selection())
        del invalid["determinism"]
        self.path.write_text(json.dumps(invalid), encoding="utf-8")
        before = self.path.read_bytes()
        generated = build_semantic_map(_valid_selection())

        with self.assertRaises(SemanticMapContractError):
            plan_semantic_map_update(self.path, generated)

        self.assertEqual(self.path.read_bytes(), before)

    def test_existing_wrong_identity_is_not_merged(self) -> None:
        existing = build_semantic_map(_valid_selection())
        existing["adapter"] = "othercad"
        self._write_map(existing)
        before = self.path.read_bytes()
        generated = build_semantic_map(_valid_selection())

        with self.assertRaises(SemanticMapIdentityError):
            plan_semantic_map_update(self.path, generated)
        self.assertEqual(self.path.read_bytes(), before)

        existing = build_semantic_map(_valid_selection())
        existing["cadSystem"]["name"] = "OtherCAD"
        self._write_map(existing)
        before = self.path.read_bytes()
        with self.assertRaises(SemanticMapIdentityError):
            plan_semantic_map_update(self.path, generated)
        self.assertEqual(self.path.read_bytes(), before)

    def test_write_errors_for_missing_parent_and_directory_target(self) -> None:
        generated = build_semantic_map(_valid_selection())
        missing_parent = self.directory / "missing" / "prm.semantic-map.json"

        with self.assertRaises(SemanticMapWriteError):
            write_semantic_map(missing_parent, generated, confirm_replace=False)

        self.path.mkdir()
        with self.assertRaises(SemanticMapWriteError):
            plan_semantic_map_update(self.path, generated)

    def test_confirmation_decision_is_required_and_boolean(self) -> None:
        generated = build_semantic_map(_valid_selection())

        with self.assertRaises(TypeError):
            write_semantic_map(self.path, generated)  # type: ignore[call-arg]

        with self.assertRaises(TypeError):
            write_semantic_map(
                self.path,
                generated,
                confirm_replace=1,  # type: ignore[arg-type]
            )

    def test_plan_and_result_mappings_are_json_safe(self) -> None:
        generated = build_semantic_map(_valid_selection())
        plan = plan_semantic_map_update(self.path, generated)
        result = write_semantic_map(self.path, generated, confirm_replace=False)

        json.dumps(plan.to_mapping(), sort_keys=True)
        json.dumps(result.to_mapping(), sort_keys=True)

    def test_plan_does_not_mutate_inputs(self) -> None:
        generated = build_semantic_map(_valid_selection())
        self._write_map(generated)
        existing_before = self.path.read_bytes()
        generated_before = copy.deepcopy(generated)

        plan = plan_semantic_map_update(self.path, generated)

        self.assertEqual(generated, generated_before)
        self.assertEqual(self.path.read_bytes(), existing_before)
        self.assertIsInstance(plan.diff, tuple)
        for entry in plan.diff:
            self.assertIsInstance(entry, SemanticMapDiffEntry)


if __name__ == "__main__":
    unittest.main()
