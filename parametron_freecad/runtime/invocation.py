"""Engine-callable runtime invocation dispatch."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

from parametron_freecad.runtime.entrypoints import (
    ExecutionEntrypointError,
    ObservationEntrypointError,
    run_execution_entrypoint,
    run_observation_entrypoint,
)
from parametron_freecad.runtime.error_contract import (
    EngineInvocationError,
    EngineInvocationExecutionError,
    EngineInvocationObservationError,
    EngineInvocationRequestError,
)
from parametron_freecad.runtime.invocation_contract import (
    COMBINED_INVOCATION_UNSUPPORTED_MESSAGE,
    PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES,
    SUPPORTED_ENGINE_INVOCATION_MODES,
)

RuntimeInvocationMode = Literal["execute", "observe"]

_SUPPORTED_MODES: frozenset[str] = frozenset(SUPPORTED_ENGINE_INVOCATION_MODES)
_PLANNED_UNSUPPORTED_MODES: frozenset[str] = frozenset(
    PLANNED_UNSUPPORTED_ENGINE_INVOCATION_MODES
)
_ENTRYPOINTS_MODULE = "parametron_freecad.runtime.entrypoints"
_ORIGINAL_RUN_EXECUTION_ENTRYPOINT = run_execution_entrypoint
_ORIGINAL_RUN_OBSERVATION_ENTRYPOINT = run_observation_entrypoint


@dataclass(frozen=True, slots=True)
class ExecutionInvocation:
    working_copy: Path
    manifest_path: Path
    result_path: Path | None
    freecad_module: Any | None = None
    resolve_freecad_module: Callable[[], Any | None] | None = None


@dataclass(frozen=True, slots=True)
class ObservationInvocation:
    document: Any
    verification_data: Mapping[str, Any]
    working_copy_path: str | os.PathLike[str]
    working_copy_sha256: str
    output_directory: str | os.PathLike[str]


@dataclass(frozen=True, slots=True)
class EngineRuntimeInvocation:
    mode: RuntimeInvocationMode
    execution: ExecutionInvocation | None = None
    observation: ObservationInvocation | None = None


def _validate_invocation_request(invocation: EngineRuntimeInvocation) -> None:
    mode = invocation.mode

    if mode in _PLANNED_UNSUPPORTED_MODES:
        raise EngineInvocationRequestError(
            COMBINED_INVOCATION_UNSUPPORTED_MESSAGE
        )

    if mode not in _SUPPORTED_MODES:
        raise EngineInvocationRequestError(
            f"unsupported runtime invocation mode: {mode}"
        )

    has_execution = invocation.execution is not None
    has_observation = invocation.observation is not None

    if mode == "execute":
        if not has_execution:
            raise EngineInvocationRequestError(
                "execute mode requires an execution request"
            )
        if has_observation:
            raise EngineInvocationRequestError(
                "execute mode must not include an observation request"
            )
        return

    if not has_observation:
        raise EngineInvocationRequestError(
            "observe mode requires an observation request"
        )
    if has_execution:
        raise EngineInvocationRequestError(
            "observe mode must not include an execution request"
        )


def _entrypoint_callable(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
    configured = globals()[name]
    if configured is not original:
        return configured

    current_module = sys.modules.get(_ENTRYPOINTS_MODULE)
    current = getattr(current_module, name, None)
    if callable(current):
        return current
    return configured


def _is_entrypoint_error(
    exc: Exception,
    *,
    name: str,
    original: type[Exception],
) -> bool:
    current_module = sys.modules.get(_ENTRYPOINTS_MODULE)
    current = getattr(current_module, name, original)
    return isinstance(exc, (original, current))


def run_engine_invocation(invocation: EngineRuntimeInvocation) -> None:
    """Dispatch a validated Engine runtime invocation to runtime entrypoints."""

    _validate_invocation_request(invocation)

    if invocation.mode == "execute":
        assert invocation.execution is not None
        execution = invocation.execution
        try:
            _entrypoint_callable(
                "run_execution_entrypoint",
                _ORIGINAL_RUN_EXECUTION_ENTRYPOINT,
            )(
                working_copy=execution.working_copy,
                manifest_path=execution.manifest_path,
                result_path=execution.result_path,
                freecad_module=execution.freecad_module,
                resolve_freecad_module=execution.resolve_freecad_module,
            )
        except Exception as exc:
            if not _is_entrypoint_error(
                exc,
                name="ExecutionEntrypointError",
                original=ExecutionEntrypointError,
            ):
                raise
            raise EngineInvocationExecutionError(str(exc)) from exc
        return

    assert invocation.observation is not None
    observation = invocation.observation
    try:
        _entrypoint_callable(
            "run_observation_entrypoint",
            _ORIGINAL_RUN_OBSERVATION_ENTRYPOINT,
        )(
            observation.document,
            observation.verification_data,
            working_copy_path=observation.working_copy_path,
            working_copy_sha256=observation.working_copy_sha256,
            output_directory=observation.output_directory,
        )
    except Exception as exc:
        if not _is_entrypoint_error(
            exc,
            name="ObservationEntrypointError",
            original=ObservationEntrypointError,
        ):
            raise
        raise EngineInvocationObservationError(str(exc)) from exc


__all__ = [
    "EngineInvocationError",
    "EngineInvocationExecutionError",
    "EngineInvocationObservationError",
    "EngineInvocationRequestError",
    "EngineRuntimeInvocation",
    "ExecutionInvocation",
    "ObservationInvocation",
    "RuntimeInvocationMode",
    "run_engine_invocation",
]
