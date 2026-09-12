"""Versioned manifest contract metadata for headless export execution."""

from __future__ import annotations

from dataclasses import dataclass

EXPORT_MANIFEST_V1_FILENAME = "export_manifest_v1.json"
EXPORT_MANIFEST_SCHEMA_VERSION = "1.0"
EXPORT_MANIFEST_SCHEMA_VERSION_V1 = EXPORT_MANIFEST_SCHEMA_VERSION
EXPORT_MANIFEST_SCHEMA_VERSION_V2 = "2.0"

FIELD_ASSEMBLY_MUTATIONS = "assemblyMutations"
FIELD_OUTPUTS = "outputs"
FIELD_PARAMETER_ASSIGNMENTS = "parameterAssignments"
FIELD_PART_MUTATIONS = "partMutations"
FIELD_SCHEMA_VERSION = "schemaVersion"
FIELD_SOURCE_DOCUMENT = "sourceDocument"

TOP_LEVEL_FIELDS = (
    FIELD_SCHEMA_VERSION,
    FIELD_SOURCE_DOCUMENT,
    FIELD_PARAMETER_ASSIGNMENTS,
    FIELD_OUTPUTS,
)

V2_REQUIRED_TOP_LEVEL_FIELDS = TOP_LEVEL_FIELDS
V2_OPTIONAL_TOP_LEVEL_FIELDS = (
    FIELD_ASSEMBLY_MUTATIONS,
    FIELD_PART_MUTATIONS,
)
V2_TOP_LEVEL_FIELDS = V2_REQUIRED_TOP_LEVEL_FIELDS + V2_OPTIONAL_TOP_LEVEL_FIELDS

MUTATION_COLLECTION_SUPPRESSION = "suppression"
MUTATION_COLLECTION_VISIBILITY = "visibility"
MUTATION_COLLECTION_DELETION = "deletion"

TARGET_MUTATION_SECTION_FIELDS = (
    MUTATION_COLLECTION_SUPPRESSION,
    MUTATION_COLLECTION_VISIBILITY,
    MUTATION_COLLECTION_DELETION,
)

MUTATION_ENTRY_FIELD_OBJECT = "object"
SUPPRESSION_ENTRY_FIELD_SUPPRESSED = "suppressed"
VISIBILITY_ENTRY_FIELD_VISIBLE = "visible"

SUPPRESSION_ENTRY_FIELDS = (
    MUTATION_ENTRY_FIELD_OBJECT,
    SUPPRESSION_ENTRY_FIELD_SUPPRESSED,
)
VISIBILITY_ENTRY_FIELDS = (
    MUTATION_ENTRY_FIELD_OBJECT,
    VISIBILITY_ENTRY_FIELD_VISIBLE,
)
DELETION_ENTRY_FIELDS = (MUTATION_ENTRY_FIELD_OBJECT,)

PARAMETER_ASSIGNMENT_FIELD_TARGET = "target"
PARAMETER_ASSIGNMENT_FIELD_VALUE = "value"
PARAMETER_ASSIGNMENT_FIELD_VALUE_KIND = "valueKind"

PARAMETER_ASSIGNMENT_FIELDS = (
    PARAMETER_ASSIGNMENT_FIELD_TARGET,
    PARAMETER_ASSIGNMENT_FIELD_VALUE,
    PARAMETER_ASSIGNMENT_FIELD_VALUE_KIND,
)

OUTPUT_FIELD_FORMAT = "format"
OUTPUT_FIELD_ID = "id"
OUTPUT_FIELD_PATH = "path"

OUTPUT_FIELDS = (
    OUTPUT_FIELD_ID,
    OUTPUT_FIELD_FORMAT,
    OUTPUT_FIELD_PATH,
)

OUTPUT_FORMAT_CSV = "csv"
OUTPUT_FORMAT_PDF = "pdf"
OUTPUT_FORMAT_STEP = "step"

SUPPORTED_OUTPUT_FORMATS = (
    OUTPUT_FORMAT_CSV,
    OUTPUT_FORMAT_PDF,
    OUTPUT_FORMAT_STEP,
)


@dataclass(frozen=True, slots=True)
class ParameterAssignmentContract:
    """Supported Phase 1 parameter-assignment field names."""

    fields: tuple[str, ...]
    target_field: str
    value_field: str
    value_kind_field: str


@dataclass(frozen=True, slots=True)
class OutputContract:
    """Supported Phase 1 output declaration field names and formats."""

    fields: tuple[str, ...]
    id_field: str
    format_field: str
    path_field: str
    supported_formats: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ManifestContract:
    """Supported Phase 1 export manifest field names."""

    filename: str
    schema_version: str
    top_level_fields: tuple[str, ...]
    schema_version_field: str
    source_document_field: str
    parameter_assignments_field: str
    outputs_field: str
    parameter_assignment: ParameterAssignmentContract
    output: OutputContract


@dataclass(frozen=True, slots=True)
class SuppressionEntryContract:
    """Field names for one schema 2.0 suppression mutation entry."""

    fields: tuple[str, ...]
    object_field: str
    suppressed_field: str


@dataclass(frozen=True, slots=True)
class VisibilityEntryContract:
    """Field names for one schema 2.0 visibility mutation entry."""

    fields: tuple[str, ...]
    object_field: str
    visible_field: str


@dataclass(frozen=True, slots=True)
class DeletionEntryContract:
    """Field names for one schema 2.0 deletion mutation entry."""

    fields: tuple[str, ...]
    object_field: str


@dataclass(frozen=True, slots=True)
class TargetMutationSectionContract:
    """Shared field and entry contracts for schema 2.0 target mutations."""

    fields: tuple[str, ...]
    suppression_field: str
    visibility_field: str
    deletion_field: str
    suppression_entry: SuppressionEntryContract
    visibility_entry: VisibilityEntryContract
    deletion_entry: DeletionEntryContract


@dataclass(frozen=True, slots=True)
class ManifestV2Contract:
    """Schema 2.0 manifest fields layered on the existing transport contract."""

    filename: str
    schema_version: str
    required_top_level_fields: tuple[str, ...]
    optional_top_level_fields: tuple[str, ...]
    top_level_fields: tuple[str, ...]
    schema_version_field: str
    source_document_field: str
    parameter_assignments_field: str
    outputs_field: str
    assembly_mutations_field: str
    part_mutations_field: str
    parameter_assignment: ParameterAssignmentContract
    output: OutputContract
    assembly_mutations: TargetMutationSectionContract
    part_mutations: TargetMutationSectionContract


PARAMETER_ASSIGNMENT_CONTRACT = ParameterAssignmentContract(
    fields=PARAMETER_ASSIGNMENT_FIELDS,
    target_field=PARAMETER_ASSIGNMENT_FIELD_TARGET,
    value_field=PARAMETER_ASSIGNMENT_FIELD_VALUE,
    value_kind_field=PARAMETER_ASSIGNMENT_FIELD_VALUE_KIND,
)

OUTPUT_CONTRACT = OutputContract(
    fields=OUTPUT_FIELDS,
    id_field=OUTPUT_FIELD_ID,
    format_field=OUTPUT_FIELD_FORMAT,
    path_field=OUTPUT_FIELD_PATH,
    supported_formats=SUPPORTED_OUTPUT_FORMATS,
)

SUPPRESSION_ENTRY_CONTRACT = SuppressionEntryContract(
    fields=SUPPRESSION_ENTRY_FIELDS,
    object_field=MUTATION_ENTRY_FIELD_OBJECT,
    suppressed_field=SUPPRESSION_ENTRY_FIELD_SUPPRESSED,
)

VISIBILITY_ENTRY_CONTRACT = VisibilityEntryContract(
    fields=VISIBILITY_ENTRY_FIELDS,
    object_field=MUTATION_ENTRY_FIELD_OBJECT,
    visible_field=VISIBILITY_ENTRY_FIELD_VISIBLE,
)

DELETION_ENTRY_CONTRACT = DeletionEntryContract(
    fields=DELETION_ENTRY_FIELDS,
    object_field=MUTATION_ENTRY_FIELD_OBJECT,
)

TARGET_MUTATION_SECTION_CONTRACT = TargetMutationSectionContract(
    fields=TARGET_MUTATION_SECTION_FIELDS,
    suppression_field=MUTATION_COLLECTION_SUPPRESSION,
    visibility_field=MUTATION_COLLECTION_VISIBILITY,
    deletion_field=MUTATION_COLLECTION_DELETION,
    suppression_entry=SUPPRESSION_ENTRY_CONTRACT,
    visibility_entry=VISIBILITY_ENTRY_CONTRACT,
    deletion_entry=DELETION_ENTRY_CONTRACT,
)

EXPORT_MANIFEST_V1_CONTRACT = ManifestContract(
    filename=EXPORT_MANIFEST_V1_FILENAME,
    schema_version=EXPORT_MANIFEST_SCHEMA_VERSION,
    top_level_fields=TOP_LEVEL_FIELDS,
    schema_version_field=FIELD_SCHEMA_VERSION,
    source_document_field=FIELD_SOURCE_DOCUMENT,
    parameter_assignments_field=FIELD_PARAMETER_ASSIGNMENTS,
    outputs_field=FIELD_OUTPUTS,
    parameter_assignment=PARAMETER_ASSIGNMENT_CONTRACT,
    output=OUTPUT_CONTRACT,
)

EXPORT_MANIFEST_V2_CONTRACT = ManifestV2Contract(
    filename=EXPORT_MANIFEST_V1_FILENAME,
    schema_version=EXPORT_MANIFEST_SCHEMA_VERSION_V2,
    required_top_level_fields=V2_REQUIRED_TOP_LEVEL_FIELDS,
    optional_top_level_fields=V2_OPTIONAL_TOP_LEVEL_FIELDS,
    top_level_fields=V2_TOP_LEVEL_FIELDS,
    schema_version_field=FIELD_SCHEMA_VERSION,
    source_document_field=FIELD_SOURCE_DOCUMENT,
    parameter_assignments_field=FIELD_PARAMETER_ASSIGNMENTS,
    outputs_field=FIELD_OUTPUTS,
    assembly_mutations_field=FIELD_ASSEMBLY_MUTATIONS,
    part_mutations_field=FIELD_PART_MUTATIONS,
    parameter_assignment=PARAMETER_ASSIGNMENT_CONTRACT,
    output=OUTPUT_CONTRACT,
    assembly_mutations=TARGET_MUTATION_SECTION_CONTRACT,
    part_mutations=TARGET_MUTATION_SECTION_CONTRACT,
)


def supported_output_formats() -> tuple[str, ...]:
    """Return the supported Phase 1 output formats in deterministic order."""

    return SUPPORTED_OUTPUT_FORMATS


__all__ = [
    "DELETION_ENTRY_CONTRACT",
    "DELETION_ENTRY_FIELDS",
    "DeletionEntryContract",
    "EXPORT_MANIFEST_SCHEMA_VERSION",
    "EXPORT_MANIFEST_SCHEMA_VERSION_V1",
    "EXPORT_MANIFEST_SCHEMA_VERSION_V2",
    "EXPORT_MANIFEST_V1_CONTRACT",
    "EXPORT_MANIFEST_V1_FILENAME",
    "EXPORT_MANIFEST_V2_CONTRACT",
    "FIELD_ASSEMBLY_MUTATIONS",
    "FIELD_OUTPUTS",
    "FIELD_PARAMETER_ASSIGNMENTS",
    "FIELD_PART_MUTATIONS",
    "FIELD_SCHEMA_VERSION",
    "FIELD_SOURCE_DOCUMENT",
    "ManifestContract",
    "ManifestV2Contract",
    "MUTATION_COLLECTION_DELETION",
    "MUTATION_COLLECTION_SUPPRESSION",
    "MUTATION_COLLECTION_VISIBILITY",
    "MUTATION_ENTRY_FIELD_OBJECT",
    "OUTPUT_CONTRACT",
    "OUTPUT_FIELDS",
    "OUTPUT_FIELD_FORMAT",
    "OUTPUT_FIELD_ID",
    "OUTPUT_FIELD_PATH",
    "OUTPUT_FORMAT_CSV",
    "OUTPUT_FORMAT_PDF",
    "OUTPUT_FORMAT_STEP",
    "OutputContract",
    "PARAMETER_ASSIGNMENT_CONTRACT",
    "PARAMETER_ASSIGNMENT_FIELDS",
    "PARAMETER_ASSIGNMENT_FIELD_TARGET",
    "PARAMETER_ASSIGNMENT_FIELD_VALUE",
    "PARAMETER_ASSIGNMENT_FIELD_VALUE_KIND",
    "ParameterAssignmentContract",
    "SUPPORTED_OUTPUT_FORMATS",
    "SUPPRESSION_ENTRY_CONTRACT",
    "SUPPRESSION_ENTRY_FIELDS",
    "SUPPRESSION_ENTRY_FIELD_SUPPRESSED",
    "SuppressionEntryContract",
    "TARGET_MUTATION_SECTION_CONTRACT",
    "TARGET_MUTATION_SECTION_FIELDS",
    "TOP_LEVEL_FIELDS",
    "TargetMutationSectionContract",
    "V2_OPTIONAL_TOP_LEVEL_FIELDS",
    "V2_REQUIRED_TOP_LEVEL_FIELDS",
    "V2_TOP_LEVEL_FIELDS",
    "VISIBILITY_ENTRY_CONTRACT",
    "VISIBILITY_ENTRY_FIELDS",
    "VISIBILITY_ENTRY_FIELD_VISIBLE",
    "VisibilityEntryContract",
    "supported_output_formats",
]
