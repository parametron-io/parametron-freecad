"""Runtime helper for generating canonical Phase 2 observed output."""

from __future__ import annotations

import os
from typing import Any, Mapping

from parametron_freecad.observation.engine_verification_compat import (
    EngineVerificationCompatibilityError,
    observe_engine_compatible_requested_scope,
)
from parametron_freecad.observation.metadata_observation import (
    MetadataObservationError,
)
from parametron_freecad.observation.observed_writer import (
    ObservedPayloadError,
    ObservedWriteError,
    observed_json_path,
    write_observed_json,
)
from parametron_freecad.observation.parameter_observation import (
    ParameterObservationError,
)
from parametron_freecad.observation.reference_observation import (
    ReferenceObservationError,
)
from parametron_freecad.observation.requested_scope_observation import (
    RequestedScopeObservationError,
)


class ObservedOutputError(ValueError):
    """Raised when observed output generation fails at the runtime boundary."""


def generate_observed_output(
    document: Any,
    verification_data: Mapping[str, Any],
    *,
    working_copy_path: str | os.PathLike[str],
    working_copy_sha256: str,
    output_directory: str | os.PathLike[str],
) -> None:
    """Generate canonical prm.observed.json from injected runtime state."""

    try:
        observation_data = observe_engine_compatible_requested_scope(
            document,
            verification_data,
            working_copy_path=working_copy_path,
            working_copy_sha256=working_copy_sha256,
        )
        write_observed_json(
            observed_json_path(output_directory),
            working_copy_path=working_copy_path,
            working_copy_sha256=working_copy_sha256,
            observation_data=observation_data,
        )
    except (
        EngineVerificationCompatibilityError,
        MetadataObservationError,
        ObservedPayloadError,
        ObservedWriteError,
        ParameterObservationError,
        ReferenceObservationError,
        RequestedScopeObservationError,
    ) as exc:
        raise ObservedOutputError(str(exc)) from exc


__all__ = [
    "ObservedOutputError",
    "generate_observed_output",
]
