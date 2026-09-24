"""Phase 2 verification contract metadata for prm.verification.json."""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Filename and schema version
# ---------------------------------------------------------------------------

PARAMETRON_VERIFICATION_FILENAME = "prm.verification.json"
PARAMETRON_VERIFICATION_SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Top-level field names
# ---------------------------------------------------------------------------

FIELD_SCHEMA_VERSION = "schemaVersion"
FIELD_OBSERVE = "observe"
FIELD_OBSERVATION_CONTEXT = "observationContext"
FIELD_EXPECTED = "expected"
FIELD_CHECKS = "checks"

TOP_LEVEL_FIELDS = (
    FIELD_SCHEMA_VERSION,
    FIELD_OBSERVE,
    FIELD_OBSERVATION_CONTEXT,
    FIELD_EXPECTED,
    FIELD_CHECKS,
)

REQUIRED_TOP_LEVEL_FIELDS = (
    FIELD_SCHEMA_VERSION,
    FIELD_OBSERVE,
    FIELD_EXPECTED,
    FIELD_CHECKS,
)

# observationContext is recognized but optional; Engine defaults its parameter
# bindings to an empty list when the field is absent.
OPTIONAL_TOP_LEVEL_FIELDS = (
    FIELD_OBSERVATION_CONTEXT,
)

# ---------------------------------------------------------------------------
# observe fields
# ---------------------------------------------------------------------------

OBSERVE_FIELD_COMPONENTS = "components"
OBSERVE_FIELD_PARAMETERS = "parameters"
OBSERVE_FIELD_METADATA = "metadata"
OBSERVE_FIELD_REFERENCES = "references"
OBSERVE_FIELD_TARGET_STATE = "targetState"

OBSERVE_FIELDS = (
    OBSERVE_FIELD_COMPONENTS,
    OBSERVE_FIELD_PARAMETERS,
    OBSERVE_FIELD_METADATA,
    OBSERVE_FIELD_REFERENCES,
    OBSERVE_FIELD_TARGET_STATE,
)

# ---------------------------------------------------------------------------
# observationContext fields
# ---------------------------------------------------------------------------

OBSERVATION_CONTEXT_FIELD_PARAMETERS = "parameters"
OBSERVATION_CONTEXT_FIELD_TARGET_STATE = "targetState"
TARGET_STATE_FAMILIES = ("suppression", "visibility", "existence")
TARGET_IDENTITY_FIELDS = ("destination", "object")

OBSERVATION_CONTEXT_FIELDS = (
    OBSERVATION_CONTEXT_FIELD_PARAMETERS,
    OBSERVATION_CONTEXT_FIELD_TARGET_STATE,
)

# ---------------------------------------------------------------------------
# observationContext.parameters[] (parameter binding) fields
# ---------------------------------------------------------------------------

OBSERVATION_PARAMETER_FIELD_ID = "id"
OBSERVATION_PARAMETER_FIELD_NAME = "name"
OBSERVATION_PARAMETER_FIELD_GROUP_NAME = "groupName"

OBSERVATION_PARAMETER_FIELDS = (
    OBSERVATION_PARAMETER_FIELD_ID,
    OBSERVATION_PARAMETER_FIELD_NAME,
    OBSERVATION_PARAMETER_FIELD_GROUP_NAME,
)

# ---------------------------------------------------------------------------
# expected fields
# ---------------------------------------------------------------------------

EXPECTED_FIELD_COMPONENTS = "components"
EXPECTED_FIELD_PARAMETERS = "parameters"
EXPECTED_FIELD_METADATA = "metadata"
EXPECTED_FIELD_REFERENCES = "references"

EXPECTED_FIELDS = (
    EXPECTED_FIELD_COMPONENTS,
    EXPECTED_FIELD_PARAMETERS,
    EXPECTED_FIELD_METADATA,
    EXPECTED_FIELD_REFERENCES,
)

# ---------------------------------------------------------------------------
# expected.components[] fields
# ---------------------------------------------------------------------------

EXPECTED_COMPONENT_FIELD_ID = "id"
EXPECTED_COMPONENT_FIELD_KIND = "kind"
EXPECTED_COMPONENT_FIELD_NAME = "name"
EXPECTED_COMPONENT_FIELD_PARENT_ID = "parentId"

EXPECTED_COMPONENT_FIELDS = (
    EXPECTED_COMPONENT_FIELD_ID,
    EXPECTED_COMPONENT_FIELD_KIND,
    EXPECTED_COMPONENT_FIELD_NAME,
    EXPECTED_COMPONENT_FIELD_PARENT_ID,
)

EXPECTED_COMPONENT_KIND_ASSEMBLY = "assembly"
EXPECTED_COMPONENT_KIND_PART = "part"

SUPPORTED_EXPECTED_COMPONENT_KINDS = (
    EXPECTED_COMPONENT_KIND_ASSEMBLY,
    EXPECTED_COMPONENT_KIND_PART,
)

# ---------------------------------------------------------------------------
# expected.parameters[] fields
# ---------------------------------------------------------------------------

EXPECTED_PARAMETER_FIELD_ID = "id"
EXPECTED_PARAMETER_FIELD_NAME = "name"
EXPECTED_PARAMETER_FIELD_TYPE = "type"
EXPECTED_PARAMETER_FIELD_UNIT = "unit"
EXPECTED_PARAMETER_FIELD_VALUE = "value"

EXPECTED_PARAMETER_FIELDS = (
    EXPECTED_PARAMETER_FIELD_ID,
    EXPECTED_PARAMETER_FIELD_NAME,
    EXPECTED_PARAMETER_FIELD_TYPE,
    EXPECTED_PARAMETER_FIELD_UNIT,
    EXPECTED_PARAMETER_FIELD_VALUE,
)

EXPECTED_PARAMETER_TYPE_NUMBER = "number"

SUPPORTED_EXPECTED_PARAMETER_TYPES = (
    EXPECTED_PARAMETER_TYPE_NUMBER,
)

EXPECTED_PARAMETER_UNIT_MM = "mm"

SUPPORTED_EXPECTED_PARAMETER_UNITS = (
    EXPECTED_PARAMETER_UNIT_MM,
)

# ---------------------------------------------------------------------------
# expected.metadata[] fields
# ---------------------------------------------------------------------------

EXPECTED_METADATA_FIELD_ID = "id"
EXPECTED_METADATA_FIELD_KEY = "key"
EXPECTED_METADATA_FIELD_OWNER_ID = "ownerId"
EXPECTED_METADATA_FIELD_VALUE = "value"
EXPECTED_METADATA_FIELD_VALUE_KIND = "valueKind"

EXPECTED_METADATA_FIELDS = (
    EXPECTED_METADATA_FIELD_ID,
    EXPECTED_METADATA_FIELD_KEY,
    EXPECTED_METADATA_FIELD_OWNER_ID,
    EXPECTED_METADATA_FIELD_VALUE,
    EXPECTED_METADATA_FIELD_VALUE_KIND,
)

EXPECTED_METADATA_VALUE_KIND_NUMBER = "number"
EXPECTED_METADATA_VALUE_KIND_INTEGER = "integer"
EXPECTED_METADATA_VALUE_KIND_STRING = "string"
EXPECTED_METADATA_VALUE_KIND_BOOLEAN = "boolean"

SUPPORTED_EXPECTED_METADATA_VALUE_KINDS = (
    EXPECTED_METADATA_VALUE_KIND_NUMBER,
    EXPECTED_METADATA_VALUE_KIND_INTEGER,
    EXPECTED_METADATA_VALUE_KIND_STRING,
    EXPECTED_METADATA_VALUE_KIND_BOOLEAN,
)

# ---------------------------------------------------------------------------
# expected.references[] fields
# ---------------------------------------------------------------------------

EXPECTED_REFERENCE_FIELD_KIND = "kind"
EXPECTED_REFERENCE_FIELD_NAME = "name"

EXPECTED_REFERENCE_FIELDS = (
    EXPECTED_REFERENCE_FIELD_KIND,
    EXPECTED_REFERENCE_FIELD_NAME,
)

# ---------------------------------------------------------------------------
# checks fields
# ---------------------------------------------------------------------------

CHECKS_FIELD_COMPONENTS = "components"
CHECKS_FIELD_PARAMETERS = "parameters"
CHECKS_FIELD_METADATA = "metadata"
CHECKS_FIELD_REFERENCES = "references"

CHECKS_FIELDS = (
    CHECKS_FIELD_COMPONENTS,
    CHECKS_FIELD_PARAMETERS,
    CHECKS_FIELD_METADATA,
    CHECKS_FIELD_REFERENCES,
)

# Each checks.<category> object fields
CHECK_FIELD_ENABLED = "enabled"

CHECK_FIELDS = (
    CHECK_FIELD_ENABLED,
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ObservationParameterBindingContract:
    """Supported v1 observationContext parameter binding field names."""

    fields: tuple[str, ...]
    id_field: str
    name_field: str
    group_name_field: str


@dataclass(frozen=True, slots=True)
class ObservationContextContract:
    """Supported v1 observationContext field names."""

    fields: tuple[str, ...]
    parameters_field: str
    target_state_field: str
    parameter_binding: ObservationParameterBindingContract


@dataclass(frozen=True, slots=True)
class ObserveContract:
    """Supported v1 observe field names."""

    fields: tuple[str, ...]
    components_field: str
    parameters_field: str
    metadata_field: str
    references_field: str
    target_state_field: str


@dataclass(frozen=True, slots=True)
class ExpectedComponentContract:
    """Supported v1 expected component field names and kinds."""

    fields: tuple[str, ...]
    id_field: str
    kind_field: str
    name_field: str
    parent_id_field: str
    supported_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExpectedParameterContract:
    """Supported v1 expected parameter field names, types, and units."""

    fields: tuple[str, ...]
    id_field: str
    name_field: str
    type_field: str
    unit_field: str
    value_field: str
    supported_types: tuple[str, ...]
    supported_units: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExpectedMetadataContract:
    """Supported v1 expected metadata field names and value kinds."""

    fields: tuple[str, ...]
    id_field: str
    key_field: str
    owner_id_field: str
    value_field: str
    value_kind_field: str
    supported_value_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExpectedReferenceContract:
    """Supported v1 expected reference field names."""

    fields: tuple[str, ...]
    kind_field: str
    name_field: str


@dataclass(frozen=True, slots=True)
class ExpectedContract:
    """Supported v1 expected category field names and nested contracts."""

    fields: tuple[str, ...]
    components_field: str
    parameters_field: str
    metadata_field: str
    references_field: str
    component: ExpectedComponentContract
    parameter: ExpectedParameterContract
    metadata: ExpectedMetadataContract
    reference: ExpectedReferenceContract


@dataclass(frozen=True, slots=True)
class CheckContract:
    """Supported v1 per-category check field names."""

    fields: tuple[str, ...]
    enabled_field: str


@dataclass(frozen=True, slots=True)
class ChecksContract:
    """Supported v1 checks category field names."""

    fields: tuple[str, ...]
    components_field: str
    parameters_field: str
    metadata_field: str
    references_field: str
    check: CheckContract


@dataclass(frozen=True, slots=True)
class VerificationContract:
    """Supported v1 prm.verification.json contract surfaces."""

    filename: str
    schema_version: str
    schema_version_field: str
    top_level_fields: tuple[str, ...]
    required_top_level_fields: tuple[str, ...]
    optional_top_level_fields: tuple[str, ...]
    observe_field: str
    observation_context_field: str
    expected_field: str
    checks_field: str
    observe: ObserveContract
    observation_context: ObservationContextContract
    expected: ExpectedContract
    checks: ChecksContract


# ---------------------------------------------------------------------------
# Canonical sub-contract instances
# ---------------------------------------------------------------------------

OBSERVATION_PARAMETER_BINDING_CONTRACT = ObservationParameterBindingContract(
    fields=OBSERVATION_PARAMETER_FIELDS,
    id_field=OBSERVATION_PARAMETER_FIELD_ID,
    name_field=OBSERVATION_PARAMETER_FIELD_NAME,
    group_name_field=OBSERVATION_PARAMETER_FIELD_GROUP_NAME,
)

OBSERVATION_CONTEXT_CONTRACT = ObservationContextContract(
    fields=OBSERVATION_CONTEXT_FIELDS,
    parameters_field=OBSERVATION_CONTEXT_FIELD_PARAMETERS,
    target_state_field=OBSERVATION_CONTEXT_FIELD_TARGET_STATE,
    parameter_binding=OBSERVATION_PARAMETER_BINDING_CONTRACT,
)

OBSERVE_CONTRACT = ObserveContract(
    fields=OBSERVE_FIELDS,
    components_field=OBSERVE_FIELD_COMPONENTS,
    parameters_field=OBSERVE_FIELD_PARAMETERS,
    metadata_field=OBSERVE_FIELD_METADATA,
    references_field=OBSERVE_FIELD_REFERENCES,
    target_state_field=OBSERVE_FIELD_TARGET_STATE,
)

EXPECTED_COMPONENT_CONTRACT = ExpectedComponentContract(
    fields=EXPECTED_COMPONENT_FIELDS,
    id_field=EXPECTED_COMPONENT_FIELD_ID,
    kind_field=EXPECTED_COMPONENT_FIELD_KIND,
    name_field=EXPECTED_COMPONENT_FIELD_NAME,
    parent_id_field=EXPECTED_COMPONENT_FIELD_PARENT_ID,
    supported_kinds=SUPPORTED_EXPECTED_COMPONENT_KINDS,
)

EXPECTED_PARAMETER_CONTRACT = ExpectedParameterContract(
    fields=EXPECTED_PARAMETER_FIELDS,
    id_field=EXPECTED_PARAMETER_FIELD_ID,
    name_field=EXPECTED_PARAMETER_FIELD_NAME,
    type_field=EXPECTED_PARAMETER_FIELD_TYPE,
    unit_field=EXPECTED_PARAMETER_FIELD_UNIT,
    value_field=EXPECTED_PARAMETER_FIELD_VALUE,
    supported_types=SUPPORTED_EXPECTED_PARAMETER_TYPES,
    supported_units=SUPPORTED_EXPECTED_PARAMETER_UNITS,
)

EXPECTED_METADATA_CONTRACT = ExpectedMetadataContract(
    fields=EXPECTED_METADATA_FIELDS,
    id_field=EXPECTED_METADATA_FIELD_ID,
    key_field=EXPECTED_METADATA_FIELD_KEY,
    owner_id_field=EXPECTED_METADATA_FIELD_OWNER_ID,
    value_field=EXPECTED_METADATA_FIELD_VALUE,
    value_kind_field=EXPECTED_METADATA_FIELD_VALUE_KIND,
    supported_value_kinds=SUPPORTED_EXPECTED_METADATA_VALUE_KINDS,
)

EXPECTED_REFERENCE_CONTRACT = ExpectedReferenceContract(
    fields=EXPECTED_REFERENCE_FIELDS,
    kind_field=EXPECTED_REFERENCE_FIELD_KIND,
    name_field=EXPECTED_REFERENCE_FIELD_NAME,
)

EXPECTED_CONTRACT = ExpectedContract(
    fields=EXPECTED_FIELDS,
    components_field=EXPECTED_FIELD_COMPONENTS,
    parameters_field=EXPECTED_FIELD_PARAMETERS,
    metadata_field=EXPECTED_FIELD_METADATA,
    references_field=EXPECTED_FIELD_REFERENCES,
    component=EXPECTED_COMPONENT_CONTRACT,
    parameter=EXPECTED_PARAMETER_CONTRACT,
    metadata=EXPECTED_METADATA_CONTRACT,
    reference=EXPECTED_REFERENCE_CONTRACT,
)

CHECK_CONTRACT = CheckContract(
    fields=CHECK_FIELDS,
    enabled_field=CHECK_FIELD_ENABLED,
)

CHECKS_CONTRACT = ChecksContract(
    fields=CHECKS_FIELDS,
    components_field=CHECKS_FIELD_COMPONENTS,
    parameters_field=CHECKS_FIELD_PARAMETERS,
    metadata_field=CHECKS_FIELD_METADATA,
    references_field=CHECKS_FIELD_REFERENCES,
    check=CHECK_CONTRACT,
)

# ---------------------------------------------------------------------------
# Canonical top-level contract instance
# ---------------------------------------------------------------------------

PARAMETRON_VERIFICATION_CONTRACT = VerificationContract(
    filename=PARAMETRON_VERIFICATION_FILENAME,
    schema_version=PARAMETRON_VERIFICATION_SCHEMA_VERSION,
    schema_version_field=FIELD_SCHEMA_VERSION,
    top_level_fields=TOP_LEVEL_FIELDS,
    required_top_level_fields=REQUIRED_TOP_LEVEL_FIELDS,
    optional_top_level_fields=OPTIONAL_TOP_LEVEL_FIELDS,
    observe_field=FIELD_OBSERVE,
    observation_context_field=FIELD_OBSERVATION_CONTEXT,
    expected_field=FIELD_EXPECTED,
    checks_field=FIELD_CHECKS,
    observe=OBSERVE_CONTRACT,
    observation_context=OBSERVATION_CONTEXT_CONTRACT,
    expected=EXPECTED_CONTRACT,
    checks=CHECKS_CONTRACT,
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def supported_observation_categories() -> tuple[str, ...]:
    """Return the supported v1 observation category names in deterministic order."""
    return OBSERVE_FIELDS


def supported_expected_component_kinds() -> tuple[str, ...]:
    """Return the supported v1 expected component kinds in deterministic order."""
    return SUPPORTED_EXPECTED_COMPONENT_KINDS


def supported_expected_parameter_types() -> tuple[str, ...]:
    """Return the supported v1 expected parameter types in deterministic order."""
    return SUPPORTED_EXPECTED_PARAMETER_TYPES


def supported_expected_parameter_units() -> tuple[str, ...]:
    """Return the supported v1 expected parameter units in deterministic order."""
    return SUPPORTED_EXPECTED_PARAMETER_UNITS


def supported_expected_metadata_value_kinds() -> tuple[str, ...]:
    """Return the supported v1 expected metadata value kinds in deterministic order."""
    return SUPPORTED_EXPECTED_METADATA_VALUE_KINDS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "CHECK_CONTRACT",
    "CHECK_FIELD_ENABLED",
    "CHECK_FIELDS",
    "CHECKS_CONTRACT",
    "CHECKS_FIELD_COMPONENTS",
    "CHECKS_FIELD_METADATA",
    "CHECKS_FIELD_PARAMETERS",
    "CHECKS_FIELD_REFERENCES",
    "CHECKS_FIELDS",
    "CheckContract",
    "ChecksContract",
    "EXPECTED_COMPONENT_CONTRACT",
    "EXPECTED_COMPONENT_FIELD_ID",
    "EXPECTED_COMPONENT_FIELD_KIND",
    "EXPECTED_COMPONENT_FIELD_NAME",
    "EXPECTED_COMPONENT_FIELD_PARENT_ID",
    "EXPECTED_COMPONENT_FIELDS",
    "EXPECTED_COMPONENT_KIND_ASSEMBLY",
    "EXPECTED_COMPONENT_KIND_PART",
    "EXPECTED_CONTRACT",
    "EXPECTED_FIELD_COMPONENTS",
    "EXPECTED_FIELD_METADATA",
    "EXPECTED_FIELD_PARAMETERS",
    "EXPECTED_FIELD_REFERENCES",
    "EXPECTED_FIELDS",
    "EXPECTED_METADATA_CONTRACT",
    "EXPECTED_METADATA_FIELD_ID",
    "EXPECTED_METADATA_FIELD_KEY",
    "EXPECTED_METADATA_FIELD_OWNER_ID",
    "EXPECTED_METADATA_FIELD_VALUE",
    "EXPECTED_METADATA_FIELD_VALUE_KIND",
    "EXPECTED_METADATA_FIELDS",
    "EXPECTED_METADATA_VALUE_KIND_BOOLEAN",
    "EXPECTED_METADATA_VALUE_KIND_INTEGER",
    "EXPECTED_METADATA_VALUE_KIND_NUMBER",
    "EXPECTED_METADATA_VALUE_KIND_STRING",
    "EXPECTED_PARAMETER_CONTRACT",
    "EXPECTED_PARAMETER_FIELD_ID",
    "EXPECTED_PARAMETER_FIELD_NAME",
    "EXPECTED_PARAMETER_FIELD_TYPE",
    "EXPECTED_PARAMETER_FIELD_UNIT",
    "EXPECTED_PARAMETER_FIELD_VALUE",
    "EXPECTED_PARAMETER_FIELDS",
    "EXPECTED_PARAMETER_TYPE_NUMBER",
    "EXPECTED_PARAMETER_UNIT_MM",
    "EXPECTED_REFERENCE_CONTRACT",
    "EXPECTED_REFERENCE_FIELD_KIND",
    "EXPECTED_REFERENCE_FIELD_NAME",
    "EXPECTED_REFERENCE_FIELDS",
    "ExpectedComponentContract",
    "ExpectedContract",
    "ExpectedMetadataContract",
    "ExpectedParameterContract",
    "ExpectedReferenceContract",
    "FIELD_CHECKS",
    "FIELD_EXPECTED",
    "FIELD_OBSERVATION_CONTEXT",
    "FIELD_OBSERVE",
    "FIELD_SCHEMA_VERSION",
    "OBSERVE_CONTRACT",
    "OBSERVE_FIELD_COMPONENTS",
    "OBSERVE_FIELD_METADATA",
    "OBSERVE_FIELD_PARAMETERS",
    "OBSERVE_FIELD_REFERENCES",
    "OBSERVE_FIELD_TARGET_STATE",
    "OBSERVE_FIELDS",
    "OBSERVATION_CONTEXT_CONTRACT",
    "OBSERVATION_CONTEXT_FIELD_PARAMETERS",
    "OBSERVATION_CONTEXT_FIELD_TARGET_STATE",
    "TARGET_STATE_FAMILIES",
    "TARGET_IDENTITY_FIELDS",
    "OBSERVATION_CONTEXT_FIELDS",
    "OBSERVATION_PARAMETER_BINDING_CONTRACT",
    "OBSERVATION_PARAMETER_FIELD_GROUP_NAME",
    "OBSERVATION_PARAMETER_FIELD_ID",
    "OBSERVATION_PARAMETER_FIELD_NAME",
    "OBSERVATION_PARAMETER_FIELDS",
    "OPTIONAL_TOP_LEVEL_FIELDS",
    "ObservationContextContract",
    "ObservationParameterBindingContract",
    "ObserveContract",
    "PARAMETRON_VERIFICATION_CONTRACT",
    "PARAMETRON_VERIFICATION_FILENAME",
    "PARAMETRON_VERIFICATION_SCHEMA_VERSION",
    "REQUIRED_TOP_LEVEL_FIELDS",
    "SUPPORTED_EXPECTED_COMPONENT_KINDS",
    "SUPPORTED_EXPECTED_METADATA_VALUE_KINDS",
    "SUPPORTED_EXPECTED_PARAMETER_TYPES",
    "SUPPORTED_EXPECTED_PARAMETER_UNITS",
    "TOP_LEVEL_FIELDS",
    "VerificationContract",
    "supported_expected_component_kinds",
    "supported_expected_metadata_value_kinds",
    "supported_expected_parameter_types",
    "supported_expected_parameter_units",
    "supported_observation_categories",
]
