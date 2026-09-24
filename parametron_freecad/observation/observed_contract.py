"""Phase 2 observed output contract metadata for prm.observed.json."""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Filename and schema version
# ---------------------------------------------------------------------------

PARAMETRON_OBSERVED_FILENAME = "prm.observed.json"
PARAMETRON_OBSERVED_SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Top-level field names
# ---------------------------------------------------------------------------

FIELD_SCHEMA_VERSION = "schemaVersion"
FIELD_WORKING_COPY = "workingCopy"
FIELD_OBSERVATION = "observation"

TOP_LEVEL_FIELDS = (
    FIELD_SCHEMA_VERSION,
    FIELD_WORKING_COPY,
    FIELD_OBSERVATION,
)

REQUIRED_TOP_LEVEL_FIELDS = (
    FIELD_SCHEMA_VERSION,
    FIELD_WORKING_COPY,
    FIELD_OBSERVATION,
)

# ---------------------------------------------------------------------------
# workingCopy fields
# ---------------------------------------------------------------------------

WORKING_COPY_FIELD_PATH = "path"
WORKING_COPY_FIELD_SHA256 = "sha256"

WORKING_COPY_FIELDS = (
    WORKING_COPY_FIELD_PATH,
    WORKING_COPY_FIELD_SHA256,
)

# ---------------------------------------------------------------------------
# observation category fields
# ---------------------------------------------------------------------------

OBSERVATION_FIELD_PARAMETERS = "parameters"
OBSERVATION_FIELD_METADATA = "metadata"
OBSERVATION_FIELD_REFERENCES = "references"
OBSERVATION_FIELD_COMPONENTS = "components"
OBSERVATION_FIELD_TARGET_STATE = "targetState"
TARGET_STATE_FAMILIES = ("suppression", "visibility", "existence")
TARGET_STATE_BOOLEAN_FIELDS = ("destination", "object", "status", "value")
TARGET_STATE_EXISTENCE_FIELDS = ("destination", "object", "status")

OBSERVATION_FIELDS = (
    OBSERVATION_FIELD_PARAMETERS,
    OBSERVATION_FIELD_METADATA,
    OBSERVATION_FIELD_REFERENCES,
    OBSERVATION_FIELD_COMPONENTS,
    OBSERVATION_FIELD_TARGET_STATE,
)

# ---------------------------------------------------------------------------
# observation.parameters[] fields
# ---------------------------------------------------------------------------

OBSERVED_PARAMETER_FIELD_ID = "id"
OBSERVED_PARAMETER_FIELD_NAME = "name"
OBSERVED_PARAMETER_FIELD_GROUP_ID = "groupId"
OBSERVED_PARAMETER_FIELD_VALUE = "value"
OBSERVED_PARAMETER_FIELD_VALUE_KIND = "valueKind"

OBSERVED_PARAMETER_FIELDS = (
    OBSERVED_PARAMETER_FIELD_ID,
    OBSERVED_PARAMETER_FIELD_NAME,
    OBSERVED_PARAMETER_FIELD_GROUP_ID,
    OBSERVED_PARAMETER_FIELD_VALUE,
    OBSERVED_PARAMETER_FIELD_VALUE_KIND,
)

OBSERVED_PARAMETER_VALUE_KIND_NUMBER = "number"
OBSERVED_PARAMETER_VALUE_KIND_INTEGER = "integer"
OBSERVED_PARAMETER_VALUE_KIND_STRING = "string"
OBSERVED_PARAMETER_VALUE_KIND_BOOLEAN = "boolean"

SUPPORTED_OBSERVED_PARAMETER_VALUE_KINDS = (
    OBSERVED_PARAMETER_VALUE_KIND_NUMBER,
    OBSERVED_PARAMETER_VALUE_KIND_INTEGER,
    OBSERVED_PARAMETER_VALUE_KIND_STRING,
    OBSERVED_PARAMETER_VALUE_KIND_BOOLEAN,
)

# ---------------------------------------------------------------------------
# observation.metadata[] fields
# ---------------------------------------------------------------------------

OBSERVED_METADATA_FIELD_ID = "id"
OBSERVED_METADATA_FIELD_KEY = "key"
OBSERVED_METADATA_FIELD_OWNER_ID = "ownerId"
OBSERVED_METADATA_FIELD_VALUE = "value"
OBSERVED_METADATA_FIELD_VALUE_KIND = "valueKind"

OBSERVED_METADATA_FIELDS = (
    OBSERVED_METADATA_FIELD_ID,
    OBSERVED_METADATA_FIELD_KEY,
    OBSERVED_METADATA_FIELD_OWNER_ID,
    OBSERVED_METADATA_FIELD_VALUE,
    OBSERVED_METADATA_FIELD_VALUE_KIND,
)

OBSERVED_METADATA_VALUE_KIND_NUMBER = "number"
OBSERVED_METADATA_VALUE_KIND_INTEGER = "integer"
OBSERVED_METADATA_VALUE_KIND_STRING = "string"
OBSERVED_METADATA_VALUE_KIND_BOOLEAN = "boolean"

SUPPORTED_OBSERVED_METADATA_VALUE_KINDS = (
    OBSERVED_METADATA_VALUE_KIND_NUMBER,
    OBSERVED_METADATA_VALUE_KIND_INTEGER,
    OBSERVED_METADATA_VALUE_KIND_STRING,
    OBSERVED_METADATA_VALUE_KIND_BOOLEAN,
)

# ---------------------------------------------------------------------------
# observation.references[] fields
# ---------------------------------------------------------------------------

OBSERVED_REFERENCE_FIELD_KIND = "kind"
OBSERVED_REFERENCE_FIELD_NAME = "name"

OBSERVED_REFERENCE_FIELDS = (
    OBSERVED_REFERENCE_FIELD_KIND,
    OBSERVED_REFERENCE_FIELD_NAME,
)

# ---------------------------------------------------------------------------
# observation.components[] fields
# ---------------------------------------------------------------------------

OBSERVED_COMPONENT_FIELD_ID = "id"
OBSERVED_COMPONENT_FIELD_KIND = "kind"
OBSERVED_COMPONENT_FIELD_NAME = "name"
OBSERVED_COMPONENT_FIELD_PARENT_ID = "parentId"

OBSERVED_COMPONENT_FIELDS = (
    OBSERVED_COMPONENT_FIELD_ID,
    OBSERVED_COMPONENT_FIELD_KIND,
    OBSERVED_COMPONENT_FIELD_NAME,
    OBSERVED_COMPONENT_FIELD_PARENT_ID,
)

OBSERVED_COMPONENT_KIND_ASSEMBLY = "assembly"
OBSERVED_COMPONENT_KIND_PART = "part"

SUPPORTED_OBSERVED_COMPONENT_KINDS = (
    OBSERVED_COMPONENT_KIND_ASSEMBLY,
    OBSERVED_COMPONENT_KIND_PART,
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkingCopyContract:
    """Supported v1 workingCopy field names."""

    fields: tuple[str, ...]
    path_field: str
    sha256_field: str


@dataclass(frozen=True, slots=True)
class ObservedParameterContract:
    """Supported v1 observed parameter field names and value kinds."""

    fields: tuple[str, ...]
    id_field: str
    name_field: str
    group_id_field: str
    value_field: str
    value_kind_field: str
    supported_value_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObservedMetadataContract:
    """Supported v1 observed metadata field names and value kinds."""

    fields: tuple[str, ...]
    id_field: str
    key_field: str
    owner_id_field: str
    value_field: str
    value_kind_field: str
    supported_value_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObservedReferenceContract:
    """Supported v1 observed reference field names."""

    fields: tuple[str, ...]
    kind_field: str
    name_field: str


@dataclass(frozen=True, slots=True)
class ObservedComponentContract:
    """Supported v1 observed component field names and kinds."""

    fields: tuple[str, ...]
    id_field: str
    kind_field: str
    name_field: str
    parent_id_field: str
    supported_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ObservationContract:
    """Supported v1 observation category field names and nested contracts."""

    fields: tuple[str, ...]
    parameters_field: str
    metadata_field: str
    references_field: str
    components_field: str
    target_state_field: str
    parameter: ObservedParameterContract
    metadata: ObservedMetadataContract
    reference: ObservedReferenceContract
    component: ObservedComponentContract


@dataclass(frozen=True, slots=True)
class ObservedContract:
    """Supported v1 prm.observed.json contract surfaces."""

    filename: str
    schema_version: str
    schema_version_field: str
    top_level_fields: tuple[str, ...]
    required_top_level_fields: tuple[str, ...]
    working_copy_field: str
    observation_field: str
    working_copy: WorkingCopyContract
    observation: ObservationContract


# ---------------------------------------------------------------------------
# Canonical sub-contract instances
# ---------------------------------------------------------------------------

WORKING_COPY_CONTRACT = WorkingCopyContract(
    fields=WORKING_COPY_FIELDS,
    path_field=WORKING_COPY_FIELD_PATH,
    sha256_field=WORKING_COPY_FIELD_SHA256,
)

OBSERVED_PARAMETER_CONTRACT = ObservedParameterContract(
    fields=OBSERVED_PARAMETER_FIELDS,
    id_field=OBSERVED_PARAMETER_FIELD_ID,
    name_field=OBSERVED_PARAMETER_FIELD_NAME,
    group_id_field=OBSERVED_PARAMETER_FIELD_GROUP_ID,
    value_field=OBSERVED_PARAMETER_FIELD_VALUE,
    value_kind_field=OBSERVED_PARAMETER_FIELD_VALUE_KIND,
    supported_value_kinds=SUPPORTED_OBSERVED_PARAMETER_VALUE_KINDS,
)

OBSERVED_METADATA_CONTRACT = ObservedMetadataContract(
    fields=OBSERVED_METADATA_FIELDS,
    id_field=OBSERVED_METADATA_FIELD_ID,
    key_field=OBSERVED_METADATA_FIELD_KEY,
    owner_id_field=OBSERVED_METADATA_FIELD_OWNER_ID,
    value_field=OBSERVED_METADATA_FIELD_VALUE,
    value_kind_field=OBSERVED_METADATA_FIELD_VALUE_KIND,
    supported_value_kinds=SUPPORTED_OBSERVED_METADATA_VALUE_KINDS,
)

OBSERVED_REFERENCE_CONTRACT = ObservedReferenceContract(
    fields=OBSERVED_REFERENCE_FIELDS,
    kind_field=OBSERVED_REFERENCE_FIELD_KIND,
    name_field=OBSERVED_REFERENCE_FIELD_NAME,
)

OBSERVED_COMPONENT_CONTRACT = ObservedComponentContract(
    fields=OBSERVED_COMPONENT_FIELDS,
    id_field=OBSERVED_COMPONENT_FIELD_ID,
    kind_field=OBSERVED_COMPONENT_FIELD_KIND,
    name_field=OBSERVED_COMPONENT_FIELD_NAME,
    parent_id_field=OBSERVED_COMPONENT_FIELD_PARENT_ID,
    supported_kinds=SUPPORTED_OBSERVED_COMPONENT_KINDS,
)

OBSERVATION_CONTRACT = ObservationContract(
    fields=OBSERVATION_FIELDS,
    parameters_field=OBSERVATION_FIELD_PARAMETERS,
    metadata_field=OBSERVATION_FIELD_METADATA,
    references_field=OBSERVATION_FIELD_REFERENCES,
    components_field=OBSERVATION_FIELD_COMPONENTS,
    target_state_field=OBSERVATION_FIELD_TARGET_STATE,
    parameter=OBSERVED_PARAMETER_CONTRACT,
    metadata=OBSERVED_METADATA_CONTRACT,
    reference=OBSERVED_REFERENCE_CONTRACT,
    component=OBSERVED_COMPONENT_CONTRACT,
)

# ---------------------------------------------------------------------------
# Canonical top-level contract instance
# ---------------------------------------------------------------------------

PARAMETRON_OBSERVED_CONTRACT = ObservedContract(
    filename=PARAMETRON_OBSERVED_FILENAME,
    schema_version=PARAMETRON_OBSERVED_SCHEMA_VERSION,
    schema_version_field=FIELD_SCHEMA_VERSION,
    top_level_fields=TOP_LEVEL_FIELDS,
    required_top_level_fields=REQUIRED_TOP_LEVEL_FIELDS,
    working_copy_field=FIELD_WORKING_COPY,
    observation_field=FIELD_OBSERVATION,
    working_copy=WORKING_COPY_CONTRACT,
    observation=OBSERVATION_CONTRACT,
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def supported_observation_categories() -> tuple[str, ...]:
    """Return the supported v1 observation category names in deterministic order."""
    return OBSERVATION_FIELDS


def supported_observed_component_kinds() -> tuple[str, ...]:
    """Return the supported v1 observed component kinds in deterministic order."""
    return SUPPORTED_OBSERVED_COMPONENT_KINDS


def supported_observed_parameter_value_kinds() -> tuple[str, ...]:
    """Return the supported v1 observed parameter value kinds in deterministic order."""
    return SUPPORTED_OBSERVED_PARAMETER_VALUE_KINDS


def supported_observed_metadata_value_kinds() -> tuple[str, ...]:
    """Return the supported v1 observed metadata value kinds in deterministic order."""
    return SUPPORTED_OBSERVED_METADATA_VALUE_KINDS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "FIELD_OBSERVATION",
    "FIELD_SCHEMA_VERSION",
    "FIELD_WORKING_COPY",
    "OBSERVATION_CONTRACT",
    "OBSERVATION_FIELD_COMPONENTS",
    "OBSERVATION_FIELD_METADATA",
    "OBSERVATION_FIELD_PARAMETERS",
    "OBSERVATION_FIELD_REFERENCES",
    "OBSERVATION_FIELD_TARGET_STATE",
    "TARGET_STATE_FAMILIES",
    "TARGET_STATE_BOOLEAN_FIELDS",
    "TARGET_STATE_EXISTENCE_FIELDS",
    "OBSERVATION_FIELDS",
    "OBSERVED_COMPONENT_CONTRACT",
    "OBSERVED_COMPONENT_FIELD_ID",
    "OBSERVED_COMPONENT_FIELD_KIND",
    "OBSERVED_COMPONENT_FIELD_NAME",
    "OBSERVED_COMPONENT_FIELD_PARENT_ID",
    "OBSERVED_COMPONENT_FIELDS",
    "OBSERVED_COMPONENT_KIND_ASSEMBLY",
    "OBSERVED_COMPONENT_KIND_PART",
    "OBSERVED_METADATA_CONTRACT",
    "OBSERVED_METADATA_FIELD_ID",
    "OBSERVED_METADATA_FIELD_KEY",
    "OBSERVED_METADATA_FIELD_OWNER_ID",
    "OBSERVED_METADATA_FIELD_VALUE",
    "OBSERVED_METADATA_FIELD_VALUE_KIND",
    "OBSERVED_METADATA_FIELDS",
    "OBSERVED_METADATA_VALUE_KIND_BOOLEAN",
    "OBSERVED_METADATA_VALUE_KIND_INTEGER",
    "OBSERVED_METADATA_VALUE_KIND_NUMBER",
    "OBSERVED_METADATA_VALUE_KIND_STRING",
    "OBSERVED_PARAMETER_CONTRACT",
    "OBSERVED_PARAMETER_FIELD_GROUP_ID",
    "OBSERVED_PARAMETER_FIELD_ID",
    "OBSERVED_PARAMETER_FIELD_NAME",
    "OBSERVED_PARAMETER_FIELD_VALUE",
    "OBSERVED_PARAMETER_FIELD_VALUE_KIND",
    "OBSERVED_PARAMETER_FIELDS",
    "OBSERVED_PARAMETER_VALUE_KIND_BOOLEAN",
    "OBSERVED_PARAMETER_VALUE_KIND_INTEGER",
    "OBSERVED_PARAMETER_VALUE_KIND_NUMBER",
    "OBSERVED_PARAMETER_VALUE_KIND_STRING",
    "OBSERVED_REFERENCE_CONTRACT",
    "OBSERVED_REFERENCE_FIELD_KIND",
    "OBSERVED_REFERENCE_FIELD_NAME",
    "OBSERVED_REFERENCE_FIELDS",
    "ObservedComponentContract",
    "ObservedContract",
    "ObservedMetadataContract",
    "ObservedParameterContract",
    "ObservedReferenceContract",
    "ObservationContract",
    "PARAMETRON_OBSERVED_CONTRACT",
    "PARAMETRON_OBSERVED_FILENAME",
    "PARAMETRON_OBSERVED_SCHEMA_VERSION",
    "REQUIRED_TOP_LEVEL_FIELDS",
    "SUPPORTED_OBSERVED_COMPONENT_KINDS",
    "SUPPORTED_OBSERVED_METADATA_VALUE_KINDS",
    "SUPPORTED_OBSERVED_PARAMETER_VALUE_KINDS",
    "TOP_LEVEL_FIELDS",
    "WORKING_COPY_CONTRACT",
    "WORKING_COPY_FIELD_PATH",
    "WORKING_COPY_FIELD_SHA256",
    "WORKING_COPY_FIELDS",
    "WorkingCopyContract",
    "supported_observation_categories",
    "supported_observed_component_kinds",
    "supported_observed_metadata_value_kinds",
    "supported_observed_parameter_value_kinds",
]
