"""Structured runtime trace output contract for Phase 1 headless runtime."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

TRACE_OUTPUT_SCHEMA_VERSION = "1.0"
TRACE_OUTPUT_KIND_RUNTIME_TRACE = "runtime_trace"

TRACE_FIELD_SCHEMA_VERSION = "schemaVersion"
TRACE_FIELD_KIND = "kind"
TRACE_FIELD_BOUNDARY = "boundary"
TRACE_FIELD_OPERATION = "operation"
TRACE_FIELD_STATUS = "status"
TRACE_FIELD_EVENTS = "events"

TRACE_EVENT_FIELD_SEQUENCE = "sequence"
TRACE_EVENT_FIELD_STAGE = "stage"
TRACE_EVENT_FIELD_STATE = "state"
TRACE_EVENT_FIELD_MESSAGE = "message"

TRACE_BOUNDARY_HEADLESS_CLI = "headless_cli"
TRACE_BOUNDARY_EXECUTION_ENTRYPOINT = "execution_entrypoint"
TRACE_BOUNDARY_OBSERVATION_ENTRYPOINT = "observation_entrypoint"
TRACE_BOUNDARY_ENGINE_INVOCATION = "engine_invocation"
TRACE_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT = "reference_traversal_entrypoint"

TRACE_OPERATION_EXECUTE = "execute"
TRACE_OPERATION_OBSERVE = "observe"
TRACE_OPERATION_REFERENCE_TRAVERSAL = "reference_traversal"

TRACE_STATUS_STARTED = "started"
TRACE_STATUS_SUCCEEDED = "succeeded"
TRACE_STATUS_FAILED = "failed"

TRACE_EVENT_STATE_STARTED = "started"
TRACE_EVENT_STATE_SUCCEEDED = "succeeded"
TRACE_EVENT_STATE_FAILED = "failed"
TRACE_EVENT_STATE_SKIPPED = "skipped"

TRACE_STAGE_ARGUMENT_VALIDATION = "argument_validation"
TRACE_STAGE_FREECAD_RESOLUTION = "freecad_resolution"
TRACE_STAGE_MANIFEST_LOADING = "manifest_loading"
TRACE_STAGE_MANIFEST_COMPATIBILITY = "manifest_compatibility"
TRACE_STAGE_MANIFEST_VALIDATION = "manifest_validation"
TRACE_STAGE_SOURCE_DOCUMENT_RESOLUTION = "source_document_resolution"
TRACE_STAGE_DOCUMENT_OPEN = "document_open"
TRACE_STAGE_PARAMETER_ASSIGNMENT = "parameter_assignment"
TRACE_STAGE_RECOMPUTE = "recompute"
TRACE_STAGE_ARTIFACT_EXPORT = "artifact_export"
TRACE_STAGE_RESULT_WRITE = "result_write"
TRACE_STAGE_OBSERVATION_OUTPUT = "observation_output"
TRACE_STAGE_REFERENCE_TRAVERSAL = "reference_traversal"
TRACE_STAGE_UNKNOWN = "unknown"


class TraceOutputContractError(ValueError):
    """Raised when runtime trace output cannot be built."""


@dataclass(frozen=True, slots=True)
class RuntimeTraceEvent:
    stage: str
    state: str
    message: str | None = None


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TraceOutputContractError(f"{field_name} must be a non-empty string")
    return value


def _require_optional_message(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TraceOutputContractError("message must be a non-empty string when provided")
    return value


def _require_events_sequence(value: object) -> Sequence[RuntimeTraceEvent]:
    if isinstance(value, (str, bytes)):
        raise TraceOutputContractError(
            "events must be a non-empty sequence of RuntimeTraceEvent"
        )
    if not isinstance(value, Sequence):
        raise TraceOutputContractError(
            "events must be a non-empty sequence of RuntimeTraceEvent"
        )
    if not value:
        raise TraceOutputContractError(
            "events must be a non-empty sequence of RuntimeTraceEvent"
        )
    for event in value:
        if not isinstance(event, RuntimeTraceEvent):
            raise TraceOutputContractError(
                "events must be a non-empty sequence of RuntimeTraceEvent"
            )
    return value


def build_trace_output_payload(
    *,
    boundary: str,
    operation: str,
    status: str,
    events: Sequence[RuntimeTraceEvent],
) -> dict[str, Any]:
    """Return the canonical runtime trace output payload shape.

    Does not write files or mutate the input event sequence or event objects.
    """
    boundary_value = _require_non_empty_string(boundary, "boundary")
    operation_value = _require_non_empty_string(operation, "operation")
    status_value = _require_non_empty_string(status, "status")
    event_sequence = _require_events_sequence(events)

    event_payloads: list[dict[str, Any]] = []
    for sequence, event in enumerate(event_sequence):
        stage = _require_non_empty_string(event.stage, "stage")
        state = _require_non_empty_string(event.state, "state")
        message = _require_optional_message(event.message)
        event_payloads.append(
            {
                TRACE_EVENT_FIELD_SEQUENCE: sequence,
                TRACE_EVENT_FIELD_STAGE: stage,
                TRACE_EVENT_FIELD_STATE: state,
                TRACE_EVENT_FIELD_MESSAGE: message,
            }
        )

    return {
        TRACE_FIELD_SCHEMA_VERSION: TRACE_OUTPUT_SCHEMA_VERSION,
        TRACE_FIELD_KIND: TRACE_OUTPUT_KIND_RUNTIME_TRACE,
        TRACE_FIELD_BOUNDARY: boundary_value,
        TRACE_FIELD_OPERATION: operation_value,
        TRACE_FIELD_STATUS: status_value,
        TRACE_FIELD_EVENTS: event_payloads,
    }


__all__ = [
    "TRACE_BOUNDARY_ENGINE_INVOCATION",
    "TRACE_BOUNDARY_EXECUTION_ENTRYPOINT",
    "TRACE_BOUNDARY_HEADLESS_CLI",
    "TRACE_BOUNDARY_OBSERVATION_ENTRYPOINT",
    "TRACE_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT",
    "TRACE_EVENT_FIELD_MESSAGE",
    "TRACE_EVENT_FIELD_SEQUENCE",
    "TRACE_EVENT_FIELD_STAGE",
    "TRACE_EVENT_FIELD_STATE",
    "TRACE_EVENT_STATE_FAILED",
    "TRACE_EVENT_STATE_SKIPPED",
    "TRACE_EVENT_STATE_STARTED",
    "TRACE_EVENT_STATE_SUCCEEDED",
    "TRACE_FIELD_BOUNDARY",
    "TRACE_FIELD_EVENTS",
    "TRACE_FIELD_KIND",
    "TRACE_FIELD_OPERATION",
    "TRACE_FIELD_SCHEMA_VERSION",
    "TRACE_FIELD_STATUS",
    "TRACE_OPERATION_EXECUTE",
    "TRACE_OPERATION_OBSERVE",
    "TRACE_OPERATION_REFERENCE_TRAVERSAL",
    "TRACE_OUTPUT_KIND_RUNTIME_TRACE",
    "TRACE_OUTPUT_SCHEMA_VERSION",
    "TRACE_STAGE_ARGUMENT_VALIDATION",
    "TRACE_STAGE_ARTIFACT_EXPORT",
    "TRACE_STAGE_DOCUMENT_OPEN",
    "TRACE_STAGE_FREECAD_RESOLUTION",
    "TRACE_STAGE_MANIFEST_COMPATIBILITY",
    "TRACE_STAGE_MANIFEST_LOADING",
    "TRACE_STAGE_MANIFEST_VALIDATION",
    "TRACE_STAGE_OBSERVATION_OUTPUT",
    "TRACE_STAGE_PARAMETER_ASSIGNMENT",
    "TRACE_STAGE_RECOMPUTE",
    "TRACE_STAGE_REFERENCE_TRAVERSAL",
    "TRACE_STAGE_RESULT_WRITE",
    "TRACE_STAGE_SOURCE_DOCUMENT_RESOLUTION",
    "TRACE_STAGE_UNKNOWN",
    "TRACE_STATUS_FAILED",
    "TRACE_STATUS_STARTED",
    "TRACE_STATUS_SUCCEEDED",
    "RuntimeTraceEvent",
    "TraceOutputContractError",
    "build_trace_output_payload",
]
