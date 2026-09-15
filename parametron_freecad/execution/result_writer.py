"""Runner-owned result JSON writer for headless execute mode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from parametron_freecad.common.canonical_json import write_canonical_json
from parametron_freecad.execution.manifest_contract import (
    OUTPUT_FIELD_FORMAT,
    OUTPUT_FIELD_ID,
    OUTPUT_FIELD_PATH,
)

RESULT_SCHEMA_VERSION = "1.0"
RESULT_STATUS_SUCCEEDED = "succeeded"


class ResultWriteError(OSError):
    """Raised when result JSON cannot be written to the supplied destination."""


def write_success_result(path: str | Path, outputs: list[dict[str, Any]]) -> None:
    """Write deterministic success result JSON to the supplied path.

    outputs is the validated manifest outputs list; declaration order is preserved.
    Raises ResultWriteError on any file or serialization failure.
    """
    artifacts = [
        {
            OUTPUT_FIELD_FORMAT: output[OUTPUT_FIELD_FORMAT],
            OUTPUT_FIELD_ID: output[OUTPUT_FIELD_ID],
            OUTPUT_FIELD_PATH: output[OUTPUT_FIELD_PATH],
        }
        for output in outputs
    ]

    payload = {
        "artifacts": artifacts,
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": RESULT_STATUS_SUCCEEDED,
    }

    try:
        write_canonical_json(path, payload)
    except (OSError, ValueError) as exc:
        raise ResultWriteError(
            f"failed to write result file {Path(path)}: {exc}"
        ) from exc
