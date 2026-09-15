"""Canonical writer for already-built Phase 2 observed payloads."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from parametron_freecad.common.canonical_json import write_canonical_json
from parametron_freecad.observation.observation_ordering import (
    ObservationOrderingError,
    order_observation_payload,
)
from parametron_freecad.observation.observed_contract import (
    PARAMETRON_OBSERVED_CONTRACT,
)


class ObservedPayloadError(ValueError):
    """Raised when data for prm.observed.json is malformed."""


class ObservedWriteError(OSError):
    """Raised when prm.observed.json cannot be written."""


def observed_json_path(output_directory: str | os.PathLike[str]) -> Path:
    """Return the standard observed JSON path inside output_directory."""
    return Path(output_directory) / PARAMETRON_OBSERVED_CONTRACT.filename


def _coerce_working_copy_path(path: str | os.PathLike[str]) -> str:
    try:
        text_path = os.fspath(path)
    except TypeError as exc:
        raise ObservedPayloadError(
            "working copy path must be a string or path-like value"
        ) from exc

    if not isinstance(text_path, str) or not text_path:
        raise ObservedPayloadError("working copy path must be a non-empty string")
    return text_path


def _coerce_working_copy_sha256(sha256: str) -> str:
    if not isinstance(sha256, str) or not sha256:
        raise ObservedPayloadError("working copy sha256 must be a non-empty string")
    return sha256


def build_observed_payload(
    *,
    working_copy_path: str | os.PathLike[str],
    working_copy_sha256: str,
    observation_data: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the canonical top-level prm.observed.json payload.

    observation_data must already contain observed values. This helper only
    applies the observed output contract shape and deterministic ordering.
    """
    contract = PARAMETRON_OBSERVED_CONTRACT

    try:
        observation = order_observation_payload(observation_data)
    except ObservationOrderingError as exc:
        raise ObservedPayloadError(f"invalid observation payload: {exc}") from exc

    return {
        contract.schema_version_field: contract.schema_version,
        contract.working_copy_field: {
            contract.working_copy.path_field: _coerce_working_copy_path(
                working_copy_path
            ),
            contract.working_copy.sha256_field: _coerce_working_copy_sha256(
                working_copy_sha256
            ),
        },
        contract.observation_field: observation,
    }


def write_observed_json(
    output_path: str | os.PathLike[str],
    *,
    working_copy_path: str | os.PathLike[str],
    working_copy_sha256: str,
    observation_data: Mapping[str, Any],
) -> None:
    """Write canonical UTF-8 prm.observed.json from observed data."""
    payload = build_observed_payload(
        working_copy_path=working_copy_path,
        working_copy_sha256=working_copy_sha256,
        observation_data=observation_data,
    )

    try:
        target = Path(output_path)
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
            )
            os.close(descriptor)
            temporary_path = Path(temporary_name)
            write_canonical_json(temporary_path, payload)
            temporary_path.replace(target)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    except (OSError, TypeError, ValueError) as exc:
        raise ObservedWriteError(
            f"failed to write observed file {output_path!r}: {exc}"
        ) from exc


__all__ = [
    "ObservedPayloadError",
    "ObservedWriteError",
    "build_observed_payload",
    "observed_json_path",
    "write_observed_json",
]
