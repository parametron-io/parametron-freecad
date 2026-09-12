"""Launch the Parametron FreeCAD headless runtime under a FreeCAD host.

This module is a transport/bootstrap boundary only. Protocol parsing and CAD
behavior remain owned by ``parametron_freecad.runtime.headless.main``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from parametron_freecad.runtime.environment_contract import (
    PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE,
)

DEFAULT_FREECAD_HOST_NAME = "freecadcmd"
PASS_ARGUMENT_PREFIX = "--pass="
WRAPPER_EXECUTABLE_NAME = "parametron-freecad"
HOST_START_FAILURE_EXIT_CODE = 127

# Fixed bootstrap executed inside FreeCAD. Protocol values are never embedded.
FREECAD_BOOTSTRAP_EXPRESSION = (
    "from parametron_freecad.runtime.launcher import run_under_freecad_host; "
    "raise SystemExit(run_under_freecad_host())"
)


class FreeCADHostResolutionError(RuntimeError):
    """Raised when the underlying FreeCAD host cannot be resolved."""


def package_root() -> Path:
    """Return the repository/package root that contains ``parametron_freecad``."""

    return Path(__file__).resolve().parents[2]


def recover_protocol_argv(argv: list[str] | None = None) -> list[str]:
    """Recover protocol arguments forwarded through ``--pass=<value>`` entries."""

    resolved_argv = sys.argv if argv is None else argv
    prefix_length = len(PASS_ARGUMENT_PREFIX)
    return [
        argument[prefix_length:]
        for argument in resolved_argv
        if argument.startswith(PASS_ARGUMENT_PREFIX)
    ]


def run_under_freecad_host() -> int:
    """Import and execute the authoritative headless entrypoint under FreeCAD."""

    from parametron_freecad.runtime.headless import main

    try:
        return main(recover_protocol_argv())
    finally:
        sys.stdout.flush()
        sys.stderr.flush()


def _is_path_like(value: str) -> bool:
    return os.path.sep in value or (os.path.altsep is not None and os.path.altsep in value)


def _reject_recursive_wrapper(host_path: str) -> None:
    if Path(host_path).name == WRAPPER_EXECUTABLE_NAME:
        raise FreeCADHostResolutionError(
            f"refusing to launch wrapper recursively: {host_path}"
        )


def resolve_freecad_host() -> str:
    """Resolve the underlying FreeCAD command-line host executable."""

    configured = os.environ.get(PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE)
    if configured is not None:
        host = configured.strip()
        if not host:
            raise FreeCADHostResolutionError(
                f"{PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE} is empty or whitespace-only"
            )
    else:
        host = DEFAULT_FREECAD_HOST_NAME

    if _is_path_like(host):
        resolved = str(Path(host).expanduser())
        if not os.path.isfile(resolved):
            raise FreeCADHostResolutionError(
                f"FreeCAD host executable not found: {resolved}"
            )
        if not os.access(resolved, os.X_OK):
            raise FreeCADHostResolutionError(
                f"FreeCAD host path is not executable: {resolved}"
            )
        _reject_recursive_wrapper(resolved)
        return resolved

    resolved_from_path = shutil.which(host)
    if resolved_from_path is None:
        raise FreeCADHostResolutionError(
            f"FreeCAD host not found on PATH: {host}"
        )
    _reject_recursive_wrapper(resolved_from_path)
    return resolved_from_path


def build_host_argv(host: str, protocol_argv: list[str]) -> list[str]:
    """Construct the FreeCAD host argv with structured protocol forwarding."""

    host_argv = [
        host,
        "-P",
        str(package_root()),
        "-c",
        FREECAD_BOOTSTRAP_EXPRESSION,
    ]
    for argument in protocol_argv:
        host_argv.append(f"{PASS_ARGUMENT_PREFIX}{argument}")
    return host_argv


def _propagate_returncode(returncode: int) -> int:
    if returncode < 0:
        return 128 + (-returncode)
    return returncode


def launch(protocol_argv: list[str] | None = None) -> int:
    """Resolve the FreeCAD host, launch it, and propagate its exit status."""

    resolved_protocol_argv = sys.argv[1:] if protocol_argv is None else protocol_argv

    try:
        host = resolve_freecad_host()
    except FreeCADHostResolutionError as exc:
        sys.stderr.write(
            f"parametron-freecad: FreeCAD host could not be started: {exc}\n"
        )
        return HOST_START_FAILURE_EXIT_CODE

    host_argv = build_host_argv(host, resolved_protocol_argv)
    try:
        completed = subprocess.run(host_argv, check=False)
    except OSError as exc:
        sys.stderr.write(
            f"parametron-freecad: FreeCAD host could not be started: {exc}\n"
        )
        return HOST_START_FAILURE_EXIT_CODE

    return _propagate_returncode(completed.returncode)


def main(argv: list[str] | None = None) -> int:
    """CLI entry for the ``parametron-freecad`` wrapper."""

    if argv is None:
        return launch()
    return launch(argv)


if __name__ == "__main__":
    raise SystemExit(main())
