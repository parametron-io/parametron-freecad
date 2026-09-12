"""Stable process exit code taxonomy for the headless runtime."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExitCode:
    """Public description of a stable headless process outcome."""

    name: str
    code: int
    description: str


SUCCESS_EXIT_CODE = 0
FREECAD_UNAVAILABLE_EXIT_CODE = 2
EXECUTION_FAILURE_EXIT_CODE = 70
ARGUMENT_ERROR_EXIT_CODE = 64

EXIT_CODE_TAXONOMY = (
    ExitCode(
        name="success",
        code=SUCCESS_EXIT_CODE,
        description="Command completed successfully.",
    ),
    ExitCode(
        name="freecad_unavailable",
        code=FREECAD_UNAVAILABLE_EXIT_CODE,
        description="FreeCAD was required but could not be imported or resolved.",
    ),
    ExitCode(
        name="invalid_arguments",
        code=ARGUMENT_ERROR_EXIT_CODE,
        description="Command-line usage or argument validation failed before execution.",
    ),
    ExitCode(
        name="execute_failure",
        code=EXECUTION_FAILURE_EXIT_CODE,
        description=(
            "Execute mode reached deterministic runtime execution and failed."
        ),
    ),
)


def code_name(code: int) -> str | None:
    """Return the public taxonomy name for an exit code, if known."""

    for exit_code in EXIT_CODE_TAXONOMY:
        if exit_code.code == code:
            return exit_code.name
    return None
