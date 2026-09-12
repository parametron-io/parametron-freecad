"""Structured failure result writer for Phase 1 headless execute mode."""

from __future__ import annotations

from pathlib import Path

from parametron_freecad.common.canonical_json import write_canonical_json
from parametron_freecad.runtime.failure_output_contract import (
    FailureOutputContractError,
    StructuredFailure,
    build_failure_output_payload,
)


class FailureResultWriteError(OSError):
    """Raised when a structured failure result cannot be written."""


def write_failure_result(path: str | Path, failure: StructuredFailure) -> None:
    """Write a canonical failed result payload at path.

    Does not mutate the input failure object.
    Raises FailureResultWriteError on payload or file write failure.
    """
    try:
        payload = build_failure_output_payload(failure)
        write_canonical_json(path, payload)
    except (FailureOutputContractError, OSError, ValueError) as exc:
        raise FailureResultWriteError(
            f"failed to write failure result file {Path(path)}: {exc}"
        ) from exc


__all__ = ["FailureResultWriteError", "write_failure_result"]
