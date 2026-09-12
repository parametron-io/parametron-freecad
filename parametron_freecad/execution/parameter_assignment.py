"""Deterministic Phase 1 parameter assignment execution helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from parametron_freecad.execution.parameter_target_resolver import (
    ParameterTargetDocumentError,
    ParameterTargetObjectNotFoundError,
    ParameterTargetResolutionError,
    ParameterTargetSyntaxError,
    UnsupportedParameterTargetError,
    resolve_parameter_target,
    validate_parameter_target_document,
)
from parametron_freecad.runtime.parameter_access import (
    ParameterAccessPropertyWriteError,
    write_parameter_property,
)


class ParameterAssignmentError(ValueError):
    """Base class for deterministic parameter assignment failures."""


class ParameterTargetError(ParameterAssignmentError):
    """Raised when a parameter target does not match the supported syntax."""


class ParameterObjectNotFoundError(ParameterAssignmentError):
    """Raised when a target object cannot be resolved from the document."""


class ParameterPropertyAssignmentError(ParameterAssignmentError):
    """Raised when a property assignment cannot be completed deterministically."""


def apply_parameter_assignments(
    document: Any,
    assignments: Sequence[Mapping[str, Any]],
) -> None:
    """Apply manifest parameter assignments to an opened FreeCAD document."""

    try:
        validate_parameter_target_document(document)
    except ParameterTargetDocumentError as exc:
        raise ParameterAssignmentError(
            "document does not provide getObject for parameter assignment"
        ) from exc

    for index, assignment in enumerate(assignments):
        target = assignment["target"]
        value = assignment["value"]
        value_kind = assignment["valueKind"]
        del value_kind

        try:
            resolved_target = resolve_parameter_target(document, target)
        except (ParameterTargetSyntaxError, UnsupportedParameterTargetError) as exc:
            raise ParameterTargetError(
                _format_assignment_message(
                    index=index,
                    target=target,
                    detail=(
                        "target must use the exact format "
                        "<ObjectName>.<PropertyName>"
                    ),
                )
            ) from exc
        except ParameterTargetObjectNotFoundError as exc:
            raise ParameterObjectNotFoundError(
                _format_assignment_message(
                    index=index,
                    target=target,
                    detail=str(exc),
                )
            ) from exc
        except ParameterTargetDocumentError as exc:
            cause = exc.__cause__ if exc.__cause__ is not None else exc
            raise ParameterObjectNotFoundError(
                _format_assignment_message(
                    index=index,
                    target=target,
                    detail=str(exc),
                )
            ) from cause
        except ParameterTargetResolutionError as exc:
            raise ParameterAssignmentError(
                _format_assignment_message(
                    index=index,
                    target=target,
                    detail=str(exc),
                )
            ) from exc

        try:
            write_parameter_property(
                resolved_target.object,
                resolved_target.property_name,
                value,
                object_name=resolved_target.object_name,
            )
        except ParameterAccessPropertyWriteError as exc:
            cause = exc.__cause__ if exc.__cause__ is not None else exc
            raise ParameterPropertyAssignmentError(
                _format_assignment_message(
                    index=index,
                    target=target,
                    detail=(
                        "failed to assign property "
                        f"'{resolved_target.property_name}'"
                    ),
                )
            ) from cause


def _format_assignment_message(*, index: int, target: str, detail: str) -> str:
    return f"assignment[{index}] target '{target}': {detail}"


__all__ = [
    "ParameterAssignmentError",
    "ParameterObjectNotFoundError",
    "ParameterPropertyAssignmentError",
    "ParameterTargetError",
    "apply_parameter_assignments",
]
