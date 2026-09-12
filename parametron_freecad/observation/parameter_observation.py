"""Phase 2 runtime helper for observing requested parameters from an opened FreeCAD document."""

from __future__ import annotations

import math
from typing import Any, Mapping

from parametron_freecad.observation.verification_contract import (
    FIELD_OBSERVATION_CONTEXT,
    FIELD_OBSERVE,
    OBSERVATION_CONTEXT_FIELD_PARAMETERS,
    OBSERVATION_PARAMETER_FIELD_GROUP_NAME,
    OBSERVATION_PARAMETER_FIELD_ID,
    OBSERVATION_PARAMETER_FIELD_NAME,
    OBSERVE_FIELD_PARAMETERS,
)
from parametron_freecad.observation.observed_contract import (
    OBSERVED_PARAMETER_FIELD_GROUP_ID,
    OBSERVED_PARAMETER_FIELD_ID,
    OBSERVED_PARAMETER_FIELD_NAME,
    OBSERVED_PARAMETER_FIELD_VALUE,
    OBSERVED_PARAMETER_FIELD_VALUE_KIND,
    OBSERVED_PARAMETER_VALUE_KIND_BOOLEAN,
    OBSERVED_PARAMETER_VALUE_KIND_INTEGER,
    OBSERVED_PARAMETER_VALUE_KIND_NUMBER,
    OBSERVED_PARAMETER_VALUE_KIND_STRING,
)
from parametron_freecad.runtime.parameter_access import (
    ParameterAccessDocumentError,
    ParameterAccessObjectNotFoundError,
    ParameterAccessPropertyReadError,
    read_parameter_property,
    resolve_parameter_object,
)

# ---------------------------------------------------------------------------
# Typed deterministic errors
# ---------------------------------------------------------------------------


class ParameterObservationError(ValueError):
    """Base class for all parameter observation errors."""


class ParameterObservationRequestError(ParameterObservationError):
    """Raised when the parameter observation request data is malformed."""


class ParameterObservationDocumentError(ParameterObservationError):
    """Raised when the document object is invalid or getObject raises unexpectedly."""


class ParameterObservationObjectNotFoundError(ParameterObservationError):
    """Raised when getObject returns None for a requested group name."""


class ParameterObservationPropertyError(ParameterObservationError):
    """Raised when a requested property cannot be read from the resolved object."""


class ParameterObservationValueError(ParameterObservationError):
    """Raised when an observed property value is not a supported scalar kind."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_parameters_enabled(verification_data: Mapping[str, Any]) -> bool:
    observe = verification_data.get(FIELD_OBSERVE)
    if not isinstance(observe, Mapping):
        return False
    return bool(observe.get(OBSERVE_FIELD_PARAMETERS))


def _read_parameter_bindings(verification_data: Mapping[str, Any]) -> list[Any]:
    observation_context = verification_data.get(FIELD_OBSERVATION_CONTEXT)
    if not isinstance(observation_context, Mapping):
        raise ParameterObservationRequestError(
            f"verification data missing or invalid {FIELD_OBSERVATION_CONTEXT!r}: "
            f"expected a mapping, got {type(observation_context).__name__!r}"
        )
    bindings = observation_context.get(OBSERVATION_CONTEXT_FIELD_PARAMETERS)
    if bindings is None:
        raise ParameterObservationRequestError(
            f"{FIELD_OBSERVATION_CONTEXT!r}.{OBSERVATION_CONTEXT_FIELD_PARAMETERS!r} "
            f"is absent; parameter observation is enabled but no bindings are provided"
        )
    if isinstance(bindings, (str, bytes)):
        raise ParameterObservationRequestError(
            f"{FIELD_OBSERVATION_CONTEXT!r}.{OBSERVATION_CONTEXT_FIELD_PARAMETERS!r} "
            f"must be a list of mappings, got {type(bindings).__name__!r}"
        )
    try:
        bindings_list = list(bindings)
    except TypeError:
        raise ParameterObservationRequestError(
            f"{FIELD_OBSERVATION_CONTEXT!r}.{OBSERVATION_CONTEXT_FIELD_PARAMETERS!r} "
            f"is not iterable: got {type(bindings).__name__!r}"
        ) from None
    return bindings_list


def _validate_binding(index: int, binding: Any) -> tuple[str, str, str]:
    if not isinstance(binding, Mapping):
        raise ParameterObservationRequestError(
            f"parameter binding at index {index} must be a mapping, "
            f"got {type(binding).__name__!r}"
        )
    param_id = binding.get(OBSERVATION_PARAMETER_FIELD_ID)
    name = binding.get(OBSERVATION_PARAMETER_FIELD_NAME)
    group_name = binding.get(OBSERVATION_PARAMETER_FIELD_GROUP_NAME)
    if not isinstance(param_id, str):
        raise ParameterObservationRequestError(
            f"parameter binding at index {index}: "
            f"{OBSERVATION_PARAMETER_FIELD_ID!r} must be a string, "
            f"got {type(param_id).__name__!r}"
        )
    if not isinstance(name, str):
        raise ParameterObservationRequestError(
            f"parameter binding at index {index}: "
            f"{OBSERVATION_PARAMETER_FIELD_NAME!r} must be a string, "
            f"got {type(name).__name__!r}"
        )
    if not isinstance(group_name, str):
        raise ParameterObservationRequestError(
            f"parameter binding at index {index}: "
            f"{OBSERVATION_PARAMETER_FIELD_GROUP_NAME!r} must be a string, "
            f"got {type(group_name).__name__!r}"
        )
    return param_id, name, group_name


def _resolve_object(document: Any, group_name: str) -> Any:
    try:
        return resolve_parameter_object(document, group_name).object
    except ParameterAccessDocumentError as exc:
        if exc.__cause__ is not None:
            raise ParameterObservationDocumentError(
                f"document.getObject({group_name!r}) raised an error: {exc.__cause__}"
            ) from exc.__cause__
        raise ParameterObservationDocumentError(
            "document does not have a callable 'getObject' method"
        ) from exc
    except ParameterAccessObjectNotFoundError as exc:
        raise ParameterObservationObjectNotFoundError(
            f"document.getObject({group_name!r}) returned None; "
            f"no object with that name exists in the document"
        ) from exc


def _read_property(obj: Any, name: str, group_name: str) -> Any:
    try:
        return read_parameter_property(obj, name, object_name=group_name)
    except ParameterAccessPropertyReadError as exc:
        cause = exc.__cause__ if exc.__cause__ is not None else exc
        raise ParameterObservationPropertyError(
            f"object {group_name!r} property {name!r} could not be read: {cause}"
        ) from cause


def _derive_value_kind(value: Any, group_name: str, name: str) -> str:
    if isinstance(value, bool):
        return OBSERVED_PARAMETER_VALUE_KIND_BOOLEAN
    if isinstance(value, int):
        return OBSERVED_PARAMETER_VALUE_KIND_INTEGER
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ParameterObservationValueError(
                f"property {name!r} on object {group_name!r} has a non-finite float "
                f"value {value!r}; only finite floats are supported"
            )
        return OBSERVED_PARAMETER_VALUE_KIND_NUMBER
    if isinstance(value, str):
        return OBSERVED_PARAMETER_VALUE_KIND_STRING
    raise ParameterObservationValueError(
        f"property {name!r} on object {group_name!r} has an unsupported value type "
        f"{type(value).__name__!r}; supported types are bool, int, finite float, str"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def observe_requested_parameters(
    document: Any,
    verification_data: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Observe only the parameters requested in verification_data from document.

    Returns an empty tuple when observe.parameters is not enabled.
    Returns one observed parameter dict per binding, in request order.
    Raises a ParameterObservationError subclass for all failure modes.
    """
    if not _is_parameters_enabled(verification_data):
        return ()

    bindings_list = _read_parameter_bindings(verification_data)

    results: list[dict[str, Any]] = []
    for index, binding in enumerate(bindings_list):
        param_id, name, group_name = _validate_binding(index, binding)
        obj = _resolve_object(document, group_name)
        raw_value = _read_property(obj, name, group_name)
        value_kind = _derive_value_kind(raw_value, group_name, name)
        results.append(
            {
                OBSERVED_PARAMETER_FIELD_ID: param_id,
                OBSERVED_PARAMETER_FIELD_NAME: name,
                OBSERVED_PARAMETER_FIELD_GROUP_ID: group_name,
                OBSERVED_PARAMETER_FIELD_VALUE: raw_value,
                OBSERVED_PARAMETER_FIELD_VALUE_KIND: value_kind,
            }
        )

    return tuple(results)


__all__ = [
    "ParameterObservationDocumentError",
    "ParameterObservationError",
    "ParameterObservationObjectNotFoundError",
    "ParameterObservationPropertyError",
    "ParameterObservationRequestError",
    "ParameterObservationValueError",
    "observe_requested_parameters",
]
