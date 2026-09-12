"""Strict loading boundary for external runtime observation requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from parametron_freecad.observation.engine_verification_expectations import (
    EngineVerificationExpectationCompatibilityError,
    require_engine_verification_expectations_compatible,
)
from parametron_freecad.observation.verification_loader import (
    VerificationLoadError,
    load_parametron_verification_v1,
)


class ObservationRequestError(ValueError):
    """Raised when an external observation request cannot be normalized."""


def load_observation_request(path: Path) -> Mapping[str, Any]:
    """Load and validate requested CAD observation scope without evaluating it."""

    try:
        loaded = load_parametron_verification_v1(path)
        require_engine_verification_expectations_compatible(loaded.data)
    except (
        EngineVerificationExpectationCompatibilityError,
        VerificationLoadError,
    ) as exc:
        raise ObservationRequestError(str(exc)) from exc

    return loaded.data


__all__ = ["ObservationRequestError", "load_observation_request"]
