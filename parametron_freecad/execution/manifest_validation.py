"""Deterministic structural validation for Phase 1 export manifests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from parametron_freecad.execution.manifest_contract import (
    EXPORT_MANIFEST_V1_CONTRACT,
    EXPORT_MANIFEST_V2_CONTRACT,
)

ROOT_PATH = "$"

DIAGNOSTIC_MISSING_REQUIRED_FIELD = "missing_required_field"
DIAGNOSTIC_UNKNOWN_FIELD = "unknown_field"
DIAGNOSTIC_INVALID_SCHEMA_VERSION = "invalid_schema_version"
DIAGNOSTIC_INVALID_FIELD_TYPE = "invalid_field_type"

DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENTS_TYPE = "invalid_parameter_assignments_type"
DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_TYPE = "invalid_parameter_assignment_type"
DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD = "missing_parameter_assignment_field"
DIAGNOSTIC_UNKNOWN_PARAMETER_ASSIGNMENT_FIELD = "unknown_parameter_assignment_field"
DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE = (
    "invalid_parameter_assignment_field_type"
)

DIAGNOSTIC_INVALID_OUTPUTS_TYPE = "invalid_outputs_type"
DIAGNOSTIC_INVALID_OUTPUT_TYPE = "invalid_output_type"
DIAGNOSTIC_MISSING_OUTPUT_FIELD = "missing_output_field"
DIAGNOSTIC_UNKNOWN_OUTPUT_FIELD = "unknown_output_field"
DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE = "invalid_output_field_type"
DIAGNOSTIC_UNSUPPORTED_OUTPUT_FORMAT = "unsupported_output_format"

DIAGNOSTIC_INVALID_MUTATION_SECTION_TYPE = "invalid_mutation_section_type"
DIAGNOSTIC_UNKNOWN_MUTATION_COLLECTION = "unknown_mutation_collection"
DIAGNOSTIC_INVALID_MUTATION_COLLECTION_TYPE = "invalid_mutation_collection_type"
DIAGNOSTIC_INVALID_MUTATION_ENTRY_TYPE = "invalid_mutation_entry_type"
DIAGNOSTIC_MISSING_MUTATION_ENTRY_FIELD = "missing_mutation_entry_field"
DIAGNOSTIC_UNKNOWN_MUTATION_ENTRY_FIELD = "unknown_mutation_entry_field"
DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE = (
    "invalid_mutation_entry_field_type"
)
DIAGNOSTIC_DUPLICATE_MUTATION_OBJECT = "duplicate_mutation_object"
DIAGNOSTIC_MUTATION_FAMILY_CONFLICT = "mutation_family_conflict"
DIAGNOSTIC_CROSS_SCOPE_MUTATION_OBJECT_CONFLICT = (
    "cross_scope_mutation_object_conflict"
)


@dataclass(frozen=True, slots=True)
class ManifestDiagnostic:
    """A stable validation diagnostic for manifest contract violations."""

    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ManifestValidationResult:
    """Validation result for a decoded export manifest."""

    diagnostics: tuple[ManifestDiagnostic, ...]

    @property
    def is_valid(self) -> bool:
        """Return True when the manifest contains no validation diagnostics."""

        return not self.diagnostics


def validate_export_manifest(data: Mapping[str, Any]) -> ManifestValidationResult:
    """Validate a decoded export manifest using its exact schema version."""

    if not isinstance(data, Mapping):
        return validate_export_manifest_v1(data)

    field_name = EXPORT_MANIFEST_V1_CONTRACT.schema_version_field
    if field_name not in data:
        return ManifestValidationResult(
            diagnostics=(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_MISSING_REQUIRED_FIELD,
                    path=field_name,
                    message=f"missing required field '{field_name}'",
                ),
            )
        )

    value = data[field_name]
    if not isinstance(value, str):
        return ManifestValidationResult(
            diagnostics=(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_INVALID_FIELD_TYPE,
                    path=field_name,
                    message=f"field '{field_name}' must be a string",
                ),
            )
        )

    if value == EXPORT_MANIFEST_V1_CONTRACT.schema_version:
        return validate_export_manifest_v1(data)
    if value == EXPORT_MANIFEST_V2_CONTRACT.schema_version:
        return validate_export_manifest_v2(data)

    return ManifestValidationResult(
        diagnostics=(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_SCHEMA_VERSION,
                path=field_name,
                message=f"unsupported schemaVersion '{value}'",
            ),
        )
    )


def validate_export_manifest_v1(data: Mapping[str, Any]) -> ManifestValidationResult:
    """Validate a decoded Phase 1 export manifest without executing anything."""

    diagnostics: list[ManifestDiagnostic] = []
    contract = EXPORT_MANIFEST_V1_CONTRACT

    if not isinstance(data, Mapping):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_FIELD_TYPE,
                path=ROOT_PATH,
                message="manifest root must be an object",
            )
        )
        return ManifestValidationResult(diagnostics=tuple(diagnostics))

    for field_name in contract.required_top_level_fields:
        if field_name not in data:
            diagnostics.append(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_MISSING_REQUIRED_FIELD,
                    path=field_name,
                    message=f"missing required field '{field_name}'",
                )
            )

    for field_name in sorted(
        key for key in data if key not in contract.top_level_fields
    ):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_UNKNOWN_FIELD,
                path=field_name,
                message=f"unknown field '{field_name}'",
            )
        )

    _validate_schema_version(data, diagnostics)
    _validate_source_document(data, diagnostics)
    _validate_parameter_assignments(data, diagnostics)
    _validate_outputs(data, diagnostics)
    _validate_target_mutations(data, diagnostics)

    return ManifestValidationResult(diagnostics=tuple(diagnostics))


def validate_export_manifest_v2(data: Mapping[str, Any]) -> ManifestValidationResult:
    """Validate a decoded schema 2.0 manifest without executing mutations."""

    diagnostics: list[ManifestDiagnostic] = []
    contract = EXPORT_MANIFEST_V2_CONTRACT

    if not isinstance(data, Mapping):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_FIELD_TYPE,
                path=ROOT_PATH,
                message="manifest root must be an object",
            )
        )
        return ManifestValidationResult(diagnostics=tuple(diagnostics))

    for field_name in contract.required_top_level_fields:
        if field_name not in data:
            diagnostics.append(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_MISSING_REQUIRED_FIELD,
                    path=field_name,
                    message=f"missing required field '{field_name}'",
                )
            )

    for field_name in sorted(key for key in data if key not in contract.top_level_fields):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_UNKNOWN_FIELD,
                path=field_name,
                message=f"unknown field '{field_name}'",
            )
        )

    _validate_schema_version_v2(data, diagnostics)
    _validate_source_document(data, diagnostics)
    _validate_parameter_assignments(data, diagnostics)
    _validate_outputs(data, diagnostics)
    _validate_target_mutations(data, diagnostics)

    return ManifestValidationResult(diagnostics=tuple(diagnostics))


def _validate_target_mutations(
    data: Mapping[str, Any], diagnostics: list[ManifestDiagnostic]
) -> None:
    contract = EXPORT_MANIFEST_V1_CONTRACT

    assembly_occurrences = _validate_mutation_section(
        data,
        contract.assembly_mutations_field,
        contract.assembly_mutations,
        diagnostics,
    )
    part_occurrences = _validate_mutation_section(
        data,
        contract.part_mutations_field,
        contract.part_mutations,
        diagnostics,
    )
    _validate_within_scope_mutation_conflicts(assembly_occurrences, diagnostics)
    _validate_within_scope_mutation_conflicts(part_occurrences, diagnostics)
    _validate_cross_scope_mutation_conflicts(
        assembly_occurrences, part_occurrences, diagnostics
    )


def _validate_schema_version_v2(
    data: Mapping[str, Any], diagnostics: list[ManifestDiagnostic]
) -> None:
    field_name = EXPORT_MANIFEST_V2_CONTRACT.schema_version_field
    if field_name not in data:
        return
    value = data[field_name]
    if not isinstance(value, str):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_FIELD_TYPE,
                path=field_name,
                message=f"field '{field_name}' must be a string",
            )
        )
        return
    if value != EXPORT_MANIFEST_V2_CONTRACT.schema_version:
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_SCHEMA_VERSION,
                path=field_name,
                message=(
                    "schemaVersion must be "
                    f"'{EXPORT_MANIFEST_V2_CONTRACT.schema_version}'"
                ),
            )
        )


def _validate_mutation_section(
    data: Mapping[str, Any],
    section_field: str,
    contract: Any,
    diagnostics: list[ManifestDiagnostic],
) -> dict[str, list[tuple[str, str]]]:
    occurrences = {field_name: [] for field_name in contract.fields}
    if section_field not in data:
        return occurrences

    section = data[section_field]
    if not isinstance(section, Mapping):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_MUTATION_SECTION_TYPE,
                path=section_field,
                message=f"field '{section_field}' must be an object",
            )
        )
        return occurrences

    for field_name in sorted(key for key in section if key not in contract.fields):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_UNKNOWN_MUTATION_COLLECTION,
                path=f"{section_field}.{field_name}",
                message=f"unknown mutation collection '{field_name}'",
            )
        )

    entry_contracts = {
        contract.suppression_field: contract.suppression_entry,
        contract.visibility_field: contract.visibility_entry,
        contract.deletion_field: contract.deletion_entry,
    }
    for collection_field in contract.fields:
        if collection_field not in section:
            continue
        collection_path = f"{section_field}.{collection_field}"
        collection = section[collection_field]
        if not isinstance(collection, list):
            diagnostics.append(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_INVALID_MUTATION_COLLECTION_TYPE,
                    path=collection_path,
                    message=f"field '{collection_field}' must be a list",
                )
            )
            continue
        _validate_mutation_collection(
            collection,
            collection_path,
            entry_contracts[collection_field],
            occurrences[collection_field],
            diagnostics,
        )
    return occurrences


def _validate_mutation_collection(
    collection: list[Any],
    collection_path: str,
    contract: Any,
    occurrences: list[tuple[str, str]],
    diagnostics: list[ManifestDiagnostic],
) -> None:
    first_paths: dict[str, str] = {}
    for index, item in enumerate(collection):
        item_path = f"{collection_path}[{index}]"
        if not isinstance(item, Mapping):
            diagnostics.append(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_INVALID_MUTATION_ENTRY_TYPE,
                    path=item_path,
                    message="mutation entry must be an object",
                )
            )
            continue

        for field_name in contract.fields:
            if field_name not in item:
                diagnostics.append(
                    ManifestDiagnostic(
                        code=DIAGNOSTIC_MISSING_MUTATION_ENTRY_FIELD,
                        path=item_path,
                        message=f"missing required field '{field_name}'",
                    )
                )
        for field_name in sorted(key for key in item if key not in contract.fields):
            diagnostics.append(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_UNKNOWN_MUTATION_ENTRY_FIELD,
                    path=f"{item_path}.{field_name}",
                    message=f"unknown field '{field_name}'",
                )
            )

        object_field = contract.object_field
        object_value = item.get(object_field)
        object_path = f"{item_path}.{object_field}"
        if object_field in item and (
            not isinstance(object_value, str) or object_value == ""
        ):
            diagnostics.append(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE,
                    path=object_path,
                    message=f"field '{object_field}' must be a non-empty string",
                )
            )
        _validate_mutation_boolean_field(item, item_path, contract, diagnostics)

        if not isinstance(object_value, str) or object_value == "":
            continue
        first_path = first_paths.get(object_value)
        if first_path is not None:
            diagnostics.append(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_DUPLICATE_MUTATION_OBJECT,
                    path=object_path,
                    message=(
                        f"duplicate mutation object '{object_value}'; "
                        f"first occurrence at {first_path}"
                    ),
                )
            )
            continue
        first_paths[object_value] = object_path
        occurrences.append((object_value, object_path))


def _validate_mutation_boolean_field(
    item: Mapping[str, Any],
    item_path: str,
    contract: Any,
    diagnostics: list[ManifestDiagnostic],
) -> None:
    boolean_field = getattr(contract, "suppressed_field", None)
    if boolean_field is None:
        boolean_field = getattr(contract, "visible_field", None)
    if boolean_field is None or boolean_field not in item:
        return
    if type(item[boolean_field]) is bool:
        return
    diagnostics.append(
        ManifestDiagnostic(
            code=DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE,
            path=f"{item_path}.{boolean_field}",
            message=f"field '{boolean_field}' must be a boolean",
        )
    )


def _validate_within_scope_mutation_conflicts(
    occurrences: dict[str, list[tuple[str, str]]],
    diagnostics: list[ManifestDiagnostic],
) -> None:
    contract = EXPORT_MANIFEST_V1_CONTRACT.assembly_mutations
    suppression = {name for name, _ in occurrences[contract.suppression_field]}
    visibility = {name for name, _ in occurrences[contract.visibility_field]}
    for object_name, object_path in occurrences[contract.deletion_field]:
        conflicting_family = None
        if object_name in suppression:
            conflicting_family = contract.suppression_field
        elif object_name in visibility:
            conflicting_family = contract.visibility_field
        if conflicting_family is not None:
            diagnostics.append(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_MUTATION_FAMILY_CONFLICT,
                    path=object_path,
                    message=(
                        f"mutation object '{object_name}' conflicts between "
                        f"'{conflicting_family}' and '{contract.deletion_field}'"
                    ),
                )
            )


def _validate_cross_scope_mutation_conflicts(
    assembly_occurrences: dict[str, list[tuple[str, str]]],
    part_occurrences: dict[str, list[tuple[str, str]]],
    diagnostics: list[ManifestDiagnostic],
) -> None:
    contract = EXPORT_MANIFEST_V1_CONTRACT.assembly_mutations
    assembly_names = {
        name
        for family in contract.fields
        for name, _ in assembly_occurrences[family]
    }
    reported: set[str] = set()
    for family in contract.fields:
        for object_name, object_path in part_occurrences[family]:
            if object_name not in assembly_names or object_name in reported:
                continue
            reported.add(object_name)
            diagnostics.append(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_CROSS_SCOPE_MUTATION_OBJECT_CONFLICT,
                    path=object_path,
                    message=(
                        f"mutation object '{object_name}' occurs in both "
                        f"'{EXPORT_MANIFEST_V1_CONTRACT.assembly_mutations_field}' "
                        f"and '{EXPORT_MANIFEST_V1_CONTRACT.part_mutations_field}'"
                    ),
                )
            )


def _validate_schema_version(
    data: Mapping[str, Any], diagnostics: list[ManifestDiagnostic]
) -> None:
    field_name = EXPORT_MANIFEST_V1_CONTRACT.schema_version_field
    if field_name not in data:
        return

    value = data[field_name]
    if not isinstance(value, str):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_FIELD_TYPE,
                path=field_name,
                message=f"field '{field_name}' must be a string",
            )
        )
        return

    if value != EXPORT_MANIFEST_V1_CONTRACT.schema_version:
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_SCHEMA_VERSION,
                path=field_name,
                message=(
                    "schemaVersion must be "
                    f"'{EXPORT_MANIFEST_V1_CONTRACT.schema_version}'"
                ),
            )
        )


def _validate_source_document(
    data: Mapping[str, Any], diagnostics: list[ManifestDiagnostic]
) -> None:
    field_name = EXPORT_MANIFEST_V1_CONTRACT.source_document_field
    if field_name not in data:
        return

    value = data[field_name]
    if not isinstance(value, str) or value == "":
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_FIELD_TYPE,
                path=field_name,
                message=f"field '{field_name}' must be a non-empty string",
            )
        )


def _validate_parameter_assignments(
    data: Mapping[str, Any], diagnostics: list[ManifestDiagnostic]
) -> None:
    field_name = EXPORT_MANIFEST_V1_CONTRACT.parameter_assignments_field
    if field_name not in data:
        return

    value = data[field_name]
    if not isinstance(value, list):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENTS_TYPE,
                path=field_name,
                message=f"field '{field_name}' must be a list",
            )
        )
        return

    for index, item in enumerate(value):
        item_path = f"{field_name}[{index}]"
        _validate_parameter_assignment_item(item, item_path, diagnostics)


def _validate_parameter_assignment_item(
    item: Any, item_path: str, diagnostics: list[ManifestDiagnostic]
) -> None:
    contract = EXPORT_MANIFEST_V1_CONTRACT.parameter_assignment
    if not isinstance(item, Mapping):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_TYPE,
                path=item_path,
                message="parameter assignment must be an object",
            )
        )
        return

    for field_name in contract.fields:
        if field_name not in item:
            diagnostics.append(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD,
                    path=item_path,
                    message=f"missing required field '{field_name}'",
                )
            )

    for field_name in sorted(key for key in item if key not in contract.fields):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_UNKNOWN_PARAMETER_ASSIGNMENT_FIELD,
                path=f"{item_path}.{field_name}",
                message=f"unknown field '{field_name}'",
            )
        )

    _validate_required_non_empty_string_field(
        item=item,
        item_path=item_path,
        field_name=contract.target_field,
        diagnostics=diagnostics,
        code=DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE,
    )
    _validate_parameter_assignment_value_field(
        item=item,
        item_path=item_path,
        field_name=contract.value_field,
        diagnostics=diagnostics,
    )
    _validate_required_non_empty_string_field(
        item=item,
        item_path=item_path,
        field_name=contract.value_kind_field,
        diagnostics=diagnostics,
        code=DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE,
    )


def _validate_outputs(
    data: Mapping[str, Any], diagnostics: list[ManifestDiagnostic]
) -> None:
    field_name = EXPORT_MANIFEST_V1_CONTRACT.outputs_field
    if field_name not in data:
        return

    value = data[field_name]
    if not isinstance(value, list):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_OUTPUTS_TYPE,
                path=field_name,
                message=f"field '{field_name}' must be a list",
            )
        )
        return

    for index, item in enumerate(value):
        item_path = f"{field_name}[{index}]"
        _validate_output_item(item, item_path, diagnostics)


def _validate_output_item(
    item: Any, item_path: str, diagnostics: list[ManifestDiagnostic]
) -> None:
    contract = EXPORT_MANIFEST_V1_CONTRACT.output
    if not isinstance(item, Mapping):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_OUTPUT_TYPE,
                path=item_path,
                message="output must be an object",
            )
        )
        return

    for field_name in contract.fields:
        if field_name not in item:
            diagnostics.append(
                ManifestDiagnostic(
                    code=DIAGNOSTIC_MISSING_OUTPUT_FIELD,
                    path=item_path,
                    message=f"missing required field '{field_name}'",
                )
            )

    for field_name in sorted(key for key in item if key not in contract.fields):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_UNKNOWN_OUTPUT_FIELD,
                path=f"{item_path}.{field_name}",
                message=f"unknown field '{field_name}'",
            )
        )

    _validate_required_non_empty_string_field(
        item=item,
        item_path=item_path,
        field_name=contract.id_field,
        diagnostics=diagnostics,
        code=DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE,
    )
    _validate_output_format_field(item, item_path, diagnostics)
    _validate_required_non_empty_string_field(
        item=item,
        item_path=item_path,
        field_name=contract.path_field,
        diagnostics=diagnostics,
        code=DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE,
    )


def _validate_parameter_assignment_value_field(
    item: Mapping[str, Any],
    item_path: str,
    field_name: str,
    diagnostics: list[ManifestDiagnostic],
) -> None:
    if field_name not in item:
        return

    value = item[field_name]
    if _is_supported_json_scalar(value):
        return

    diagnostics.append(
        ManifestDiagnostic(
            code=DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE,
            path=f"{item_path}.{field_name}",
            message=f"field '{field_name}' must be a JSON scalar",
        )
    )


def _validate_output_format_field(
    item: Mapping[str, Any], item_path: str, diagnostics: list[ManifestDiagnostic]
) -> None:
    contract = EXPORT_MANIFEST_V1_CONTRACT.output
    field_name = contract.format_field
    if field_name not in item:
        return

    value = item[field_name]
    field_path = f"{item_path}.{field_name}"

    if not isinstance(value, str):
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE,
                path=field_path,
                message=f"field '{field_name}' must be a string",
            )
        )
        return

    if value not in contract.supported_formats:
        supported_formats = ", ".join(contract.supported_formats)
        diagnostics.append(
            ManifestDiagnostic(
                code=DIAGNOSTIC_UNSUPPORTED_OUTPUT_FORMAT,
                path=field_path,
                message=f"unsupported output format '{value}'; supported: {supported_formats}",
            )
        )


def _validate_required_non_empty_string_field(
    item: Mapping[str, Any],
    item_path: str,
    field_name: str,
    diagnostics: list[ManifestDiagnostic],
    code: str,
) -> None:
    if field_name not in item:
        return

    value = item[field_name]
    if isinstance(value, str) and value != "":
        return

    diagnostics.append(
        ManifestDiagnostic(
            code=code,
            path=f"{item_path}.{field_name}",
            message=f"field '{field_name}' must be a non-empty string",
        )
    )


def _is_supported_json_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


__all__ = [
    "DIAGNOSTIC_CROSS_SCOPE_MUTATION_OBJECT_CONFLICT",
    "DIAGNOSTIC_DUPLICATE_MUTATION_OBJECT",
    "DIAGNOSTIC_INVALID_FIELD_TYPE",
    "DIAGNOSTIC_INVALID_MUTATION_COLLECTION_TYPE",
    "DIAGNOSTIC_INVALID_MUTATION_ENTRY_FIELD_TYPE",
    "DIAGNOSTIC_INVALID_MUTATION_ENTRY_TYPE",
    "DIAGNOSTIC_INVALID_MUTATION_SECTION_TYPE",
    "DIAGNOSTIC_INVALID_OUTPUTS_TYPE",
    "DIAGNOSTIC_INVALID_OUTPUT_FIELD_TYPE",
    "DIAGNOSTIC_INVALID_OUTPUT_TYPE",
    "DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENTS_TYPE",
    "DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_FIELD_TYPE",
    "DIAGNOSTIC_INVALID_PARAMETER_ASSIGNMENT_TYPE",
    "DIAGNOSTIC_INVALID_SCHEMA_VERSION",
    "DIAGNOSTIC_MISSING_OUTPUT_FIELD",
    "DIAGNOSTIC_MISSING_MUTATION_ENTRY_FIELD",
    "DIAGNOSTIC_MISSING_PARAMETER_ASSIGNMENT_FIELD",
    "DIAGNOSTIC_MISSING_REQUIRED_FIELD",
    "DIAGNOSTIC_MUTATION_FAMILY_CONFLICT",
    "DIAGNOSTIC_UNKNOWN_FIELD",
    "DIAGNOSTIC_UNKNOWN_MUTATION_COLLECTION",
    "DIAGNOSTIC_UNKNOWN_MUTATION_ENTRY_FIELD",
    "DIAGNOSTIC_UNKNOWN_OUTPUT_FIELD",
    "DIAGNOSTIC_UNKNOWN_PARAMETER_ASSIGNMENT_FIELD",
    "DIAGNOSTIC_UNSUPPORTED_OUTPUT_FORMAT",
    "ManifestDiagnostic",
    "ManifestValidationResult",
    "ROOT_PATH",
    "validate_export_manifest",
    "validate_export_manifest_v1",
    "validate_export_manifest_v2",
]
