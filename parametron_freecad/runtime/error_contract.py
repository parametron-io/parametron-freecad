"""Stable Engine-facing runtime invocation error contract."""

from __future__ import annotations

from dataclasses import dataclass

ENGINE_ERROR_CONTRACT_VERSION = "1.0"

# Category constants - use these exact strings to avoid drift
ENGINE_ERROR_CATEGORY_BASE = "base"
ENGINE_ERROR_CATEGORY_REQUEST = "request"
ENGINE_ERROR_CATEGORY_EXECUTION = "execution"
ENGINE_ERROR_CATEGORY_OBSERVATION = "observation"

# Boundary constants - use these exact strings to avoid drift
ENGINE_ERROR_BOUNDARY_ENGINE_INVOCATION = "engine_invocation"
ENGINE_ERROR_BOUNDARY_EXECUTION_ENTRYPOINT = "execution_entrypoint"
ENGINE_ERROR_BOUNDARY_OBSERVATION_ENTRYPOINT = "observation_entrypoint"

ENGINE_INVOCATION_ERROR_PUBLIC_IMPORT_PATH = (
    "parametron_freecad.runtime.error_contract.EngineInvocationError"
)
ENGINE_INVOCATION_REQUEST_ERROR_PUBLIC_IMPORT_PATH = (
    "parametron_freecad.runtime.error_contract.EngineInvocationRequestError"
)
ENGINE_INVOCATION_EXECUTION_ERROR_PUBLIC_IMPORT_PATH = (
    "parametron_freecad.runtime.error_contract.EngineInvocationExecutionError"
)
ENGINE_INVOCATION_OBSERVATION_ERROR_PUBLIC_IMPORT_PATH = (
    "parametron_freecad.runtime.error_contract.EngineInvocationObservationError"
)


class EngineInvocationError(ValueError):
    """Raised when Engine runtime invocation fails."""


class EngineInvocationRequestError(EngineInvocationError):
    """Raised when an Engine runtime invocation request is invalid."""


class EngineInvocationExecutionError(EngineInvocationError):
    """Raised when Engine runtime invocation execution fails."""


class EngineInvocationObservationError(EngineInvocationError):
    """Raised when Engine runtime invocation observation fails."""


@dataclass(frozen=True, slots=True)
class EngineErrorClassSpec:
    """Immutable metadata for one stable Engine-facing error class."""

    class_name: str
    category: str
    public_import_path: str
    base_class_name: str
    directly_raised_by_request_validation: bool
    wraps_delegated_runtime_failure: bool
    delegated_source_boundary: str | None
    preserves_cause: bool


@dataclass(frozen=True, slots=True)
class EngineErrorContract:
    """Stable Engine-facing error class contract metadata."""

    version: str
    error_classes: tuple[EngineErrorClassSpec, ...]
    error_class_names: tuple[str, ...]
    categories: tuple[str, ...]
    wrapping_boundaries: tuple[str, ...]
    request_validation_error_class_name: str
    execution_wrapping_error_class_name: str
    observation_wrapping_error_class_name: str


ENGINE_INVOCATION_ERROR_SPEC = EngineErrorClassSpec(
    class_name="EngineInvocationError",
    category=ENGINE_ERROR_CATEGORY_BASE,
    public_import_path=ENGINE_INVOCATION_ERROR_PUBLIC_IMPORT_PATH,
    base_class_name="ValueError",
    directly_raised_by_request_validation=False,
    wraps_delegated_runtime_failure=False,
    delegated_source_boundary=None,
    preserves_cause=False,
)

ENGINE_INVOCATION_REQUEST_ERROR_SPEC = EngineErrorClassSpec(
    class_name="EngineInvocationRequestError",
    category=ENGINE_ERROR_CATEGORY_REQUEST,
    public_import_path=ENGINE_INVOCATION_REQUEST_ERROR_PUBLIC_IMPORT_PATH,
    base_class_name="EngineInvocationError",
    directly_raised_by_request_validation=True,
    wraps_delegated_runtime_failure=False,
    delegated_source_boundary=ENGINE_ERROR_BOUNDARY_ENGINE_INVOCATION,
    preserves_cause=False,
)

ENGINE_INVOCATION_EXECUTION_ERROR_SPEC = EngineErrorClassSpec(
    class_name="EngineInvocationExecutionError",
    category=ENGINE_ERROR_CATEGORY_EXECUTION,
    public_import_path=ENGINE_INVOCATION_EXECUTION_ERROR_PUBLIC_IMPORT_PATH,
    base_class_name="EngineInvocationError",
    directly_raised_by_request_validation=False,
    wraps_delegated_runtime_failure=True,
    delegated_source_boundary=ENGINE_ERROR_BOUNDARY_EXECUTION_ENTRYPOINT,
    preserves_cause=True,
)

ENGINE_INVOCATION_OBSERVATION_ERROR_SPEC = EngineErrorClassSpec(
    class_name="EngineInvocationObservationError",
    category=ENGINE_ERROR_CATEGORY_OBSERVATION,
    public_import_path=ENGINE_INVOCATION_OBSERVATION_ERROR_PUBLIC_IMPORT_PATH,
    base_class_name="EngineInvocationError",
    directly_raised_by_request_validation=False,
    wraps_delegated_runtime_failure=True,
    delegated_source_boundary=ENGINE_ERROR_BOUNDARY_OBSERVATION_ENTRYPOINT,
    preserves_cause=True,
)

ENGINE_ERROR_CLASS_SPECS: tuple[EngineErrorClassSpec, ...] = (
    ENGINE_INVOCATION_ERROR_SPEC,
    ENGINE_INVOCATION_REQUEST_ERROR_SPEC,
    ENGINE_INVOCATION_EXECUTION_ERROR_SPEC,
    ENGINE_INVOCATION_OBSERVATION_ERROR_SPEC,
)

ENGINE_ERROR_CLASS_NAMES: tuple[str, ...] = tuple(
    spec.class_name for spec in ENGINE_ERROR_CLASS_SPECS
)

ENGINE_ERROR_CATEGORIES: tuple[str, ...] = (
    ENGINE_ERROR_CATEGORY_BASE,
    ENGINE_ERROR_CATEGORY_REQUEST,
    ENGINE_ERROR_CATEGORY_EXECUTION,
    ENGINE_ERROR_CATEGORY_OBSERVATION,
)

ENGINE_ERROR_WRAPPING_BOUNDARIES: tuple[str, ...] = (
    ENGINE_ERROR_BOUNDARY_ENGINE_INVOCATION,
    ENGINE_ERROR_BOUNDARY_EXECUTION_ENTRYPOINT,
    ENGINE_ERROR_BOUNDARY_OBSERVATION_ENTRYPOINT,
)

ENGINE_ERROR_CONTRACT = EngineErrorContract(
    version=ENGINE_ERROR_CONTRACT_VERSION,
    error_classes=ENGINE_ERROR_CLASS_SPECS,
    error_class_names=ENGINE_ERROR_CLASS_NAMES,
    categories=ENGINE_ERROR_CATEGORIES,
    wrapping_boundaries=ENGINE_ERROR_WRAPPING_BOUNDARIES,
    request_validation_error_class_name="EngineInvocationRequestError",
    execution_wrapping_error_class_name="EngineInvocationExecutionError",
    observation_wrapping_error_class_name="EngineInvocationObservationError",
)


__all__ = [
    "ENGINE_ERROR_BOUNDARY_ENGINE_INVOCATION",
    "ENGINE_ERROR_BOUNDARY_EXECUTION_ENTRYPOINT",
    "ENGINE_ERROR_BOUNDARY_OBSERVATION_ENTRYPOINT",
    "ENGINE_ERROR_CATEGORIES",
    "ENGINE_ERROR_CATEGORY_BASE",
    "ENGINE_ERROR_CATEGORY_EXECUTION",
    "ENGINE_ERROR_CATEGORY_OBSERVATION",
    "ENGINE_ERROR_CATEGORY_REQUEST",
    "ENGINE_ERROR_CLASS_NAMES",
    "ENGINE_ERROR_CLASS_SPECS",
    "ENGINE_ERROR_CONTRACT",
    "ENGINE_ERROR_CONTRACT_VERSION",
    "ENGINE_ERROR_WRAPPING_BOUNDARIES",
    "ENGINE_INVOCATION_ERROR_PUBLIC_IMPORT_PATH",
    "ENGINE_INVOCATION_ERROR_SPEC",
    "ENGINE_INVOCATION_EXECUTION_ERROR_PUBLIC_IMPORT_PATH",
    "ENGINE_INVOCATION_EXECUTION_ERROR_SPEC",
    "ENGINE_INVOCATION_OBSERVATION_ERROR_PUBLIC_IMPORT_PATH",
    "ENGINE_INVOCATION_OBSERVATION_ERROR_SPEC",
    "ENGINE_INVOCATION_REQUEST_ERROR_PUBLIC_IMPORT_PATH",
    "ENGINE_INVOCATION_REQUEST_ERROR_SPEC",
    "EngineErrorClassSpec",
    "EngineErrorContract",
    "EngineInvocationError",
    "EngineInvocationExecutionError",
    "EngineInvocationObservationError",
    "EngineInvocationRequestError",
]
