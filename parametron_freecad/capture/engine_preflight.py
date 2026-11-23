"""Optional Engine CLI validation preflight.

The Engine remains the final semantic/schema authority. FreeCAD validates
capture invariants and can ask the Engine CLI to validate the whole project
(DSL + project mapping + ``prm.cad.json``) after a write. This module invokes
the Engine CLI when it is available and never duplicates Engine planning,
semantic resolution, or verification decisions.

The preflight is optional. An unavailable Engine is reported, not treated as a
failure, unless the caller explicitly requires it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parametron_freecad.capture.orchestration_errors import CapturePreflightError

ENGINE_BIN_ENVIRONMENT = "PARAMETRON_ENGINE_BIN"
_ENGINE_CANDIDATES = ("parametron", "parametron-engine")
_STATUS_UNAVAILABLE = "unavailable"
_STATUS_OK = "ok"
_STATUS_FAILED = "failed"


class EnginePreflightResult:
    """Deterministic result of one optional Engine CLI validation."""

    __slots__ = (
        "available",
        "ran",
        "status",
        "executable",
        "returncode",
        "stdout",
        "stderr",
    )

    def __init__(
        self,
        *,
        available: bool,
        ran: bool,
        status: str,
        executable: str | None,
        returncode: int | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.available = available
        self.ran = ran
        self.status = status
        self.executable = executable
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def to_mapping(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "ran": self.ran,
            "status": self.status,
            "executable": self.executable,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EnginePreflightResult):
            return NotImplemented
        return self.to_mapping() == other.to_mapping()


@dataclass(frozen=True, slots=True)
class EnginePreflightRunner:
    """Resolve and run the optional Engine CLI validation.

    ``executable`` overrides environment/path discovery. ``runner`` overrides
    ``subprocess.run`` for tests and returns an object with ``returncode``,
    ``stdout``, and ``stderr`` attributes.
    """

    executable: str | None = None
    timeout_seconds: float = 60.0
    runner: Callable[..., Any] | None = None

    def resolve_executable(self) -> str | None:
        if self.executable is not None:
            return self.executable
        configured = os.environ.get(ENGINE_BIN_ENVIRONMENT)
        if configured:
            return configured
        for name in _ENGINE_CANDIDATES:
            found = shutil.which(name)
            if found is not None:
                return found
        return None

    def run(self, project_root: str | Path) -> EnginePreflightResult:
        executable = self.resolve_executable()
        if executable is None:
            return EnginePreflightResult(
                available=False,
                ran=False,
                status=_STATUS_UNAVAILABLE,
                executable=None,
            )

        command = [executable, "validate", "--project", str(project_root)]
        execute = self.runner or subprocess.run
        try:
            completed = execute(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except OSError as exc:
            return EnginePreflightResult(
                available=True,
                ran=False,
                status=_STATUS_FAILED,
                executable=executable,
                returncode=None,
                stdout="",
                stderr=str(exc),
            )
        except subprocess.TimeoutExpired as exc:
            return EnginePreflightResult(
                available=True,
                ran=True,
                status=_STATUS_FAILED,
                executable=executable,
                returncode=None,
                stdout=_text(exc.stdout),
                stderr=_text(exc.stderr) or "engine preflight timed out",
            )

        returncode = getattr(completed, "returncode", None)
        status = _STATUS_OK if returncode == 0 else _STATUS_FAILED
        return EnginePreflightResult(
            available=True,
            ran=True,
            status=status,
            executable=executable,
            returncode=returncode if isinstance(returncode, int) else None,
            stdout=_text(getattr(completed, "stdout", "")),
            stderr=_text(getattr(completed, "stderr", "")),
        )

    def require(self, project_root: str | Path) -> EnginePreflightResult:
        """Run the preflight and raise only when an available Engine fails."""

        result = self.run(project_root)
        if result.status == _STATUS_FAILED:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise CapturePreflightError("engine preflight failed: " + detail)
        return result


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return str(value)


__all__ = [
    "ENGINE_BIN_ENVIRONMENT",
    "EnginePreflightResult",
    "EnginePreflightRunner",
]
