"""Structured runtime failure output contract for Phase 1 headless execute mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FAILURE_OUTPUT_SCHEMA_VERSION = "1.0"
FAILURE_OUTPUT_STATUS_FAILED = "failed"

FAILURE_FIELD_SCHEMA_VERSION = "schemaVersion"
FAILURE_FIELD_STATUS = "status"
FAILURE_FIELD_FAILURE = "failure"

FAILURE_DETAIL_FIELD_BOUNDARY = "boundary"
FAILURE_DETAIL_FIELD_CATEGORY = "category"
FAILURE_DETAIL_FIELD_CODE = "code"
FAILURE_DETAIL_FIELD_MESSAGE = "message"
FAILURE_DETAIL_FIELD_STAGE = "stage"

FAILURE_CATEGORY_ARGUMENTS = "arguments"
FAILURE_CATEGORY_FREECAD_UNAVAILABLE = "freecad_unavailable"
FAILURE_CATEGORY_EXECUTION = "execution"
FAILURE_CATEGORY_OBSERVATION = "observation"

FAILURE_BOUNDARY_HEADLESS_CLI = "headless_cli"
FAILURE_BOUNDARY_EXECUTION_ENTRYPOINT = "execution_entrypoint"
FAILURE_BOUNDARY_OBSERVATION_ENTRYPOINT = "observation_entrypoint"
FAILURE_BOUNDARY_ENGINE_INVOCATION = "engine_invocation"

FAILURE_STAGE_ARGUMENT_VALIDATION = "argument_validation"
FAILURE_STAGE_FREECAD_RESOLUTION = "freecad_resolution"
FAILURE_STAGE_MANIFEST_LOADING = "manifest_loading"
FAILURE_STAGE_MANIFEST_COMPATIBILITY = "manifest_compatibility"
FAILURE_STAGE_MANIFEST_VALIDATION = "manifest_validation"
FAILURE_STAGE_SOURCE_DOCUMENT_RESOLUTION = "source_document_resolution"
FAILURE_STAGE_DOCUMENT_OPEN = "document_open"
FAILURE_STAGE_PARAMETER_ASSIGNMENT = "parameter_assignment"
FAILURE_STAGE_RECOMPUTE = "recompute"
FAILURE_STAGE_DOCUMENT_SAVE = "document_save"
FAILURE_STAGE_ARTIFACT_EXPORT = "artifact_export"
FAILURE_STAGE_OBSERVATION = "observation"
FAILURE_STAGE_REFERENCE_TRAVERSAL = "reference_traversal"
FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_CONTAINMENT = (
    "reference_traversal_output_containment"
)
FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_WRITE = "reference_traversal_output_write"
FAILURE_STAGE_RESULT_WRITE = "result_write"
FAILURE_STAGE_OBSERVATION_OUTPUT = "observation_output"
FAILURE_STAGE_UNKNOWN = "unknown"

FAILURE_CODE_INVALID_ARGUMENTS = "invalid_arguments"
FAILURE_CODE_FREECAD_UNAVAILABLE = "freecad_unavailable"
FAILURE_CODE_RUNTIME_FAILURE = "runtime_failure"
FAILURE_CODE_OBSERVATION_FAILURE = "observation_failure"


class FailureOutputContractError(ValueError):
    """Raised when structured failure output cannot be built."""


@dataclass(frozen=True, slots=True)
class StructuredFailure:
    boundary: str
    category: str
    code: str
    message: str
    stage: str | None = None


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise FailureOutputContractError(f"{field_name} must be a non-empty string")
    return value


def _require_optional_stage(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise FailureOutputContractError("stage must be a non-empty string when provided")
    return value


def build_failure_output_payload(failure: StructuredFailure) -> dict[str, Any]:
    """Return the canonical structured failure output payload shape.

    Does not write files or mutate the input failure object.
    """
    boundary = _require_non_empty_string(failure.boundary, "boundary")
    category = _require_non_empty_string(failure.category, "category")
    code = _require_non_empty_string(failure.code, "code")
    message = _require_non_empty_string(failure.message, "message")
    stage = _require_optional_stage(failure.stage)

    return {
        FAILURE_FIELD_FAILURE: {
            FAILURE_DETAIL_FIELD_BOUNDARY: boundary,
            FAILURE_DETAIL_FIELD_CATEGORY: category,
            FAILURE_DETAIL_FIELD_CODE: code,
            FAILURE_DETAIL_FIELD_MESSAGE: message,
            FAILURE_DETAIL_FIELD_STAGE: stage,
        },
        FAILURE_FIELD_SCHEMA_VERSION: FAILURE_OUTPUT_SCHEMA_VERSION,
        FAILURE_FIELD_STATUS: FAILURE_OUTPUT_STATUS_FAILED,
    }


__all__ = [
    "FAILURE_BOUNDARY_ENGINE_INVOCATION",
    "FAILURE_BOUNDARY_EXECUTION_ENTRYPOINT",
    "FAILURE_BOUNDARY_HEADLESS_CLI",
    "FAILURE_BOUNDARY_OBSERVATION_ENTRYPOINT",
    "FAILURE_CATEGORY_ARGUMENTS",
    "FAILURE_CATEGORY_EXECUTION",
    "FAILURE_CATEGORY_FREECAD_UNAVAILABLE",
    "FAILURE_CATEGORY_OBSERVATION",
    "FAILURE_CODE_FREECAD_UNAVAILABLE",
    "FAILURE_CODE_INVALID_ARGUMENTS",
    "FAILURE_CODE_OBSERVATION_FAILURE",
    "FAILURE_CODE_RUNTIME_FAILURE",
    "FAILURE_DETAIL_FIELD_BOUNDARY",
    "FAILURE_DETAIL_FIELD_CATEGORY",
    "FAILURE_DETAIL_FIELD_CODE",
    "FAILURE_DETAIL_FIELD_MESSAGE",
    "FAILURE_DETAIL_FIELD_STAGE",
    "FAILURE_FIELD_FAILURE",
    "FAILURE_FIELD_SCHEMA_VERSION",
    "FAILURE_FIELD_STATUS",
    "FAILURE_OUTPUT_SCHEMA_VERSION",
    "FAILURE_OUTPUT_STATUS_FAILED",
    "FAILURE_STAGE_ARGUMENT_VALIDATION",
    "FAILURE_STAGE_ARTIFACT_EXPORT",
    "FAILURE_STAGE_DOCUMENT_OPEN",
    "FAILURE_STAGE_DOCUMENT_SAVE",
    "FAILURE_STAGE_FREECAD_RESOLUTION",
    "FAILURE_STAGE_MANIFEST_COMPATIBILITY",
    "FAILURE_STAGE_MANIFEST_LOADING",
    "FAILURE_STAGE_MANIFEST_VALIDATION",
    "FAILURE_STAGE_OBSERVATION_OUTPUT",
    "FAILURE_STAGE_PARAMETER_ASSIGNMENT",
    "FAILURE_STAGE_RECOMPUTE",
    "FAILURE_STAGE_REFERENCE_TRAVERSAL",
    "FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_CONTAINMENT",
    "FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_WRITE",
    "FAILURE_STAGE_RESULT_WRITE",
    "FAILURE_STAGE_SOURCE_DOCUMENT_RESOLUTION",
    "FAILURE_STAGE_UNKNOWN",
    "FailureOutputContractError",
    "StructuredFailure",
    "build_failure_output_payload",
]
