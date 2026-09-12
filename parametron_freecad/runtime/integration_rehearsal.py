"""Fixture-based rehearsal helper for Engine integration boundaries."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from parametron_freecad.common.paths import require_child_path, resolve_path
from parametron_freecad.execution.engine_manifest_compat import (
    EngineManifestCompatibilityError,
    normalize_loaded_export_manifest_v1,
)
from parametron_freecad.execution.manifest_contract import (
    EXPORT_MANIFEST_V1_CONTRACT,
)
from parametron_freecad.execution.manifest_loader import (
    LoadedManifest,
    ManifestLoadError,
    load_export_manifest_v1,
)
from parametron_freecad.execution.manifest_validation import (
    ManifestValidationResult,
    validate_export_manifest_v1,
)
from parametron_freecad.observation.engine_verification_expectations import (
    EngineVerificationExpectationCompatibilityError,
    require_engine_verification_expectations_compatible,
)
from parametron_freecad.observation.observed_writer import observed_json_path
from parametron_freecad.observation.verification_loader import (
    VerificationLoadError,
    load_parametron_verification_v1,
)
from parametron_freecad.runtime.document_lifecycle import (
    SourceDocumentPathError,
    resolve_source_document_path,
)
from parametron_freecad.runtime.entrypoints import (
    ObservationEntrypointError,
    run_document_observation_entrypoint,
)
from parametron_freecad.runtime.error_contract import EngineInvocationError
from parametron_freecad.runtime.invocation import (
    EngineRuntimeInvocation,
    ExecutionInvocation,
    run_engine_invocation,
)


class FixtureIntegrationRehearsalError(ValueError):
    """Raised when fixture-based Engine integration rehearsal fails."""


@dataclass(frozen=True, slots=True)
class FixtureIntegrationRehearsalRequest:
    working_copy: Path
    manifest_path: Path
    result_path: Path | None
    verification_path: Path | None = None
    observed_output_directory: Path | None = None
    working_copy_path: str | os.PathLike[str] | None = None
    working_copy_sha256: str | None = None
    freecad_module: Any | None = None
    resolve_freecad_module: Callable[[], Any | None] | None = None


@dataclass(frozen=True, slots=True)
class FixtureIntegrationRehearsalOutput:
    name: str
    path: Path
    role: str


@dataclass(frozen=True, slots=True)
class FixtureIntegrationRehearsalReport:
    working_copy: Path
    manifest_path: Path
    verification_path: Path | None
    source_document_path: Path
    result_path: Path | None
    observed_output_path: Path | None
    declared_artifact_paths: tuple[Path, ...]
    outputs: tuple[FixtureIntegrationRehearsalOutput, ...]


@dataclass(frozen=True, slots=True)
class _ValidatedRehearsalManifest:
    loaded_manifest: LoadedManifest
    source_document_path: Path
    declared_artifact_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class _ValidatedRehearsalVerification:
    path: Path
    data: Mapping[str, Any]
    observed_output_directory: Path
    working_copy_path: str | os.PathLike[str]
    working_copy_sha256: str
    observed_output_path: Path


def run_fixture_integration_rehearsal(
    request: FixtureIntegrationRehearsalRequest,
) -> FixtureIntegrationRehearsalReport:
    """Rehearse Engine fixture execution and optional observation integration."""

    working_copy = resolve_path(request.working_copy)
    manifest_path = resolve_path(request.manifest_path)
    result_path = (
        None if request.result_path is None else resolve_path(request.result_path)
    )
    verification_path = (
        None
        if request.verification_path is None
        else resolve_path(request.verification_path)
    )

    manifest = _load_and_validate_rehearsal_manifest(
        working_copy=working_copy,
        manifest_path=manifest_path,
    )
    verification = _load_and_validate_rehearsal_verification(
        verification_path=verification_path,
        observed_output_directory=request.observed_output_directory,
        working_copy_path=request.working_copy_path,
        working_copy_sha256=request.working_copy_sha256,
    )

    try:
        run_engine_invocation(
            EngineRuntimeInvocation(
                mode="execute",
                execution=ExecutionInvocation(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    freecad_module=request.freecad_module,
                    resolve_freecad_module=request.resolve_freecad_module,
                ),
            )
        )
    except EngineInvocationError as exc:
        raise FixtureIntegrationRehearsalError(
            "fixture integration rehearsal execution failed"
        ) from exc

    if verification is not None:
        try:
            run_document_observation_entrypoint(
                working_copy=working_copy,
                source_document=manifest.source_document_path,
                verification_data=verification.data,
                working_copy_path=verification.working_copy_path,
                working_copy_sha256=verification.working_copy_sha256,
                output_directory=verification.observed_output_directory,
                freecad_module=request.freecad_module,
                resolve_freecad_module=request.resolve_freecad_module,
            )
        except ObservationEntrypointError as exc:
            raise FixtureIntegrationRehearsalError(
                "fixture integration rehearsal observation failed"
            ) from exc

    observed_output_path = (
        None if verification is None else verification.observed_output_path
    )
    return FixtureIntegrationRehearsalReport(
        working_copy=working_copy,
        manifest_path=manifest_path,
        verification_path=None if verification is None else verification.path,
        source_document_path=manifest.source_document_path,
        result_path=result_path,
        observed_output_path=observed_output_path,
        declared_artifact_paths=manifest.declared_artifact_paths,
        outputs=_rehearsal_outputs(
            result_path=result_path,
            declared_artifact_paths=manifest.declared_artifact_paths,
            observed_output_path=observed_output_path,
        ),
    )


def _load_and_validate_rehearsal_manifest(
    *,
    working_copy: Path,
    manifest_path: Path,
) -> _ValidatedRehearsalManifest:
    try:
        loaded_manifest = load_export_manifest_v1(manifest_path)
        loaded_manifest = normalize_loaded_export_manifest_v1(loaded_manifest)
        validation_result = validate_export_manifest_v1(loaded_manifest.data)
        if not validation_result.is_valid:
            raise FixtureIntegrationRehearsalError(
                _format_manifest_validation_error(validation_result)
            )
        source_document = loaded_manifest.data[
            EXPORT_MANIFEST_V1_CONTRACT.source_document_field
        ]
        source_document_path = resolve_source_document_path(
            working_copy,
            source_document,
        )
        declared_artifact_paths = _declared_artifact_paths(
            loaded_manifest.data[EXPORT_MANIFEST_V1_CONTRACT.outputs_field],
            working_copy=working_copy,
        )
    except FixtureIntegrationRehearsalError:
        raise
    except (
        EngineManifestCompatibilityError,
        ManifestLoadError,
        SourceDocumentPathError,
        ValueError,
    ) as exc:
        raise FixtureIntegrationRehearsalError(
            "fixture integration rehearsal manifest preflight failed"
        ) from exc

    return _ValidatedRehearsalManifest(
        loaded_manifest=loaded_manifest,
        source_document_path=source_document_path,
        declared_artifact_paths=declared_artifact_paths,
    )


def _load_and_validate_rehearsal_verification(
    *,
    verification_path: Path | None,
    observed_output_directory: Path | None,
    working_copy_path: str | os.PathLike[str] | None,
    working_copy_sha256: str | None,
) -> _ValidatedRehearsalVerification | None:
    if verification_path is None:
        return None

    if observed_output_directory is None:
        raise FixtureIntegrationRehearsalError(
            "verification rehearsal requires observed_output_directory"
        )
    if working_copy_path is None:
        raise FixtureIntegrationRehearsalError(
            "verification rehearsal requires working_copy_path"
        )
    if working_copy_sha256 is None:
        raise FixtureIntegrationRehearsalError(
            "verification rehearsal requires working_copy_sha256"
        )

    try:
        loaded_verification = load_parametron_verification_v1(verification_path)
        require_engine_verification_expectations_compatible(
            loaded_verification.data
        )
    except (
        EngineVerificationExpectationCompatibilityError,
        VerificationLoadError,
    ) as exc:
        raise FixtureIntegrationRehearsalError(
            "fixture integration rehearsal verification preflight failed"
        ) from exc

    output_directory = resolve_path(observed_output_directory)
    observed_output = resolve_path(observed_json_path(output_directory))
    return _ValidatedRehearsalVerification(
        path=loaded_verification.path,
        data=loaded_verification.data,
        observed_output_directory=output_directory,
        working_copy_path=working_copy_path,
        working_copy_sha256=working_copy_sha256,
        observed_output_path=observed_output,
    )


def _declared_artifact_paths(
    outputs: object,
    *,
    working_copy: Path,
) -> tuple[Path, ...]:
    contract = EXPORT_MANIFEST_V1_CONTRACT.output
    artifact_paths: list[Path] = []
    for output in outputs:
        raw_path = output[contract.path_field]
        resolved_path = resolve_path(raw_path, base=working_copy)
        artifact_paths.append(require_child_path(working_copy, resolved_path))
    return tuple(artifact_paths)


def _rehearsal_outputs(
    *,
    result_path: Path | None,
    declared_artifact_paths: tuple[Path, ...],
    observed_output_path: Path | None,
) -> tuple[FixtureIntegrationRehearsalOutput, ...]:
    outputs: list[FixtureIntegrationRehearsalOutput] = []
    if result_path is not None:
        outputs.append(
            FixtureIntegrationRehearsalOutput(
                name=result_path.name,
                path=result_path,
                role="result",
            )
        )
    outputs.extend(
        FixtureIntegrationRehearsalOutput(
            name=artifact_path.name,
            path=artifact_path,
            role="artifact",
        )
        for artifact_path in declared_artifact_paths
    )
    if observed_output_path is not None:
        outputs.append(
            FixtureIntegrationRehearsalOutput(
                name=observed_output_path.name,
                path=observed_output_path,
                role="observed",
            )
        )
    return tuple(outputs)


def _format_manifest_validation_error(
    validation_result: ManifestValidationResult,
) -> str:
    diagnostics = validation_result.diagnostics
    first = diagnostics[0]
    return (
        "fixture integration rehearsal manifest validation failed with "
        f"{len(diagnostics)} diagnostic(s); first diagnostic: "
        f"{first.path}: {first.message}"
    )


__all__ = [
    "FixtureIntegrationRehearsalError",
    "FixtureIntegrationRehearsalOutput",
    "FixtureIntegrationRehearsalReport",
    "FixtureIntegrationRehearsalRequest",
    "run_fixture_integration_rehearsal",
]
