"""Compose requested Phase 2 observation categories from an injected document."""

from __future__ import annotations

from typing import Any, Mapping

from parametron_freecad.observation.metadata_observation import (
    observe_requested_metadata,
)
from parametron_freecad.observation.observed_contract import (
    OBSERVATION_FIELD_METADATA,
    OBSERVATION_FIELD_PARAMETERS,
    OBSERVATION_FIELD_REFERENCES,
    OBSERVATION_FIELD_TARGET_STATE,
)
from parametron_freecad.observation.observation_ordering import (
    order_observation_payload,
)
from parametron_freecad.observation.parameter_observation import (
    observe_requested_parameters,
)
from parametron_freecad.observation.reference_observation import (
    observe_requested_references,
)
from parametron_freecad.observation.target_state_observation import (
    observe_target_state,
    requested_target_state,
)
from parametron_freecad.observation.verification_contract import (
    FIELD_OBSERVE,
    OBSERVE_FIELD_METADATA,
    OBSERVE_FIELD_PARAMETERS,
    OBSERVE_FIELD_REFERENCES,
)


class RequestedScopeObservationError(ValueError):
    """Base class for requested-scope observation composition errors."""


class RequestedScopeObservationRequestError(RequestedScopeObservationError):
    """Raised when request data needed for composition is malformed."""


def _read_observe(verification_data: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if FIELD_OBSERVE not in verification_data:
        return None

    observe = verification_data[FIELD_OBSERVE]
    if not isinstance(observe, Mapping):
        raise RequestedScopeObservationRequestError(
            f"{FIELD_OBSERVE!r} must be a mapping when present, "
            f"got {type(observe).__name__!r}"
        )
    return observe


def observe_requested_contract_scope(
    document: Any,
    verification_data: Mapping[str, Any],
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Build the observed ``observation`` payload for explicitly requested categories.

    Only supported, enabled categories are emitted. Unsupported categories such as
    components are intentionally ignored until their observation helper exists.
    """
    if not isinstance(verification_data, Mapping):
        raise RequestedScopeObservationRequestError(
            f"verification_data must be a mapping, "
            f"got {type(verification_data).__name__!r}"
        )

    observe = _read_observe(verification_data)
    if observe is None:
        return {}

    target_state_request = requested_target_state(verification_data)
    observation: dict[str, Any] = {}

    if observe.get(OBSERVE_FIELD_PARAMETERS):
        observation[OBSERVATION_FIELD_PARAMETERS] = observe_requested_parameters(
            document,
            verification_data,
        )
    if observe.get(OBSERVE_FIELD_METADATA):
        observation[OBSERVATION_FIELD_METADATA] = observe_requested_metadata(
            document,
            verification_data,
        )
    if observe.get(OBSERVE_FIELD_REFERENCES):
        observation[OBSERVATION_FIELD_REFERENCES] = observe_requested_references(
            document,
            verification_data,
        )

    if target_state_request is not None:
        observation[OBSERVATION_FIELD_TARGET_STATE] = observe_target_state(
            document, target_state_request
        )

    return order_observation_payload(observation)


__all__ = [
    "RequestedScopeObservationError",
    "RequestedScopeObservationRequestError",
    "observe_requested_contract_scope",
]
