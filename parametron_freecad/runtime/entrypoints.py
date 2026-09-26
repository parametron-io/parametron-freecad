"""Consolidated runtime entrypoints for execution and observation."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ContextManager, Mapping

from parametron_freecad.execution.csv_export import (
    CsvArtifactExportError,
    export_csv_artifacts,
)
from parametron_freecad.execution.deletion import (
    DeletionMutationError,
    DeletionValidityError,
    apply_deletion_mutations,
)
from parametron_freecad.execution.suppression import (
    SuppressionMutationError,
    apply_suppression_mutations,
)
from parametron_freecad.execution.visibility import (
    VisibilityMutationError,
    apply_visibility_mutations,
)
from parametron_freecad.execution.post_mutation_validity import (
    PostMutationValidityError,
    inspect_document_post_mutation_validity,
)
from parametron_freecad.execution.document_recompute import (
    DocumentRecomputeError,
    recompute_document,
)
from parametron_freecad.execution.document_save import (
    DocumentSaveError,
    save_document,
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
from parametron_freecad.execution.parameter_assignment import (
    ParameterAssignmentError,
    apply_parameter_assignments,
)
from parametron_freecad.execution.pdf_export import (
    PdfArtifactExportError,
    export_pdf_artifacts,
)
from parametron_freecad.execution.result_writer import (
    ResultWriteError,
    write_success_result,
)
from parametron_freecad.execution.step_export import (
    StepArtifactExportError,
    export_step_artifacts,
)
from parametron_freecad.observation.observed_output import (
    ObservedOutputError,
    generate_observed_output,
)
from parametron_freecad.runtime.document_lifecycle import (
    DocumentCloseError,
    DocumentLifecycleError,
    OpenedDocument,
    SourceDocumentPathError,
    opened_freecad_document,
    resolve_source_document_path,
)
from parametron_freecad.runtime.failure_output_contract import (
    FAILURE_BOUNDARY_EXECUTION_ENTRYPOINT,
    FAILURE_CATEGORY_EXECUTION,
    FAILURE_CATEGORY_FREECAD_UNAVAILABLE,
    FAILURE_CODE_FREECAD_UNAVAILABLE,
    FAILURE_CODE_RUNTIME_FAILURE,
    FAILURE_STAGE_ARTIFACT_EXPORT,
    FAILURE_STAGE_DOCUMENT_OPEN,
    FAILURE_STAGE_DOCUMENT_SAVE,
    FAILURE_STAGE_FREECAD_RESOLUTION,
    FAILURE_STAGE_DOCUMENT_CLOSE,
    FAILURE_STAGE_SUPPRESSION,
    FAILURE_STAGE_VISIBILITY,
    FAILURE_STAGE_DELETION,
    FAILURE_STAGE_POST_MUTATION_VALIDITY,
    FAILURE_STAGE_MANIFEST_LOADING,
    FAILURE_STAGE_MANIFEST_VALIDATION,
    FAILURE_STAGE_OBSERVATION,
    FAILURE_STAGE_PARAMETER_ASSIGNMENT,
    FAILURE_STAGE_RECOMPUTE,
    FAILURE_STAGE_REFERENCE_TRAVERSAL,
    FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_CONTAINMENT,
    FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_WRITE,
    FAILURE_STAGE_RESULT_WRITE,
    FAILURE_STAGE_SOURCE_DOCUMENT_RESOLUTION,
    FAILURE_STAGE_UNKNOWN,
    StructuredFailure,
)
from parametron_freecad.runtime.failure_result_writer import write_failure_result
from parametron_freecad.runtime.observation_request import (
    ObservationRequestError,
    load_observation_request,
)
from parametron_freecad.runtime.reference_traversal_output_contract import (
    REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
    REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_MALFORMED_REQUEST,
    REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR,
    REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
    REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION,
    REFERENCE_TRAVERSAL_STATUS_FAILED,
    RawReferenceTraversalDiagnostic,
)
from parametron_freecad.runtime.reference_traversal_output_writer import (
    ReferenceTraversalOutputWriteError,
    write_reference_traversal_output_atomically,
)
from parametron_freecad.runtime.reference_traversal import (
    ReferenceTraversalExecutionError,
    ReferenceTraversalExecutionResult,
    run_reference_traversal,
)
from parametron_freecad.runtime.reference_traversal_request import (
    REFERENCE_TRAVERSAL_OUTPUT_FILENAME,
    ReferenceTraversalRequest,
    ReferenceTraversalRequestError,
    load_reference_traversal_request,
)


class ExecutionEntrypointError(ValueError):
    """Raised when runtime execution fails after path validation."""


class FreeCADUnavailableEntrypointError(ExecutionEntrypointError):
    """Raised when execution needs FreeCAD but the caller boundary cannot supply it."""


class ObservationEntrypointError(ValueError):
    """Raised when runtime observation output generation fails."""


class _ReferenceTraversalFailedResultError(ExecutionEntrypointError):
    """Internal marker for a typed failed traversal result."""


@dataclass(frozen=True, slots=True)
class ValidatedExecutionManifest:
    loaded_manifest: LoadedManifest
    source_document_path: Path


@dataclass(frozen=True, slots=True)
class _ExecutionEntrypointDependencies:
    apply_parameter_assignments: Callable[[Any, Any], None] = apply_parameter_assignments
    apply_suppression_mutations: Callable[[Any, Any], None] = apply_suppression_mutations
    apply_visibility_mutations: Callable[[Any, Any], None] = apply_visibility_mutations
    apply_deletion_mutations: Callable[[Any, Any], None] = apply_deletion_mutations
    inspect_document_post_mutation_validity: Callable[[Any], Any] = (
        inspect_document_post_mutation_validity
    )
    recompute_document: Callable[[Any], None] = recompute_document
    save_document: Callable[[Any], None] = save_document
    export_step_artifacts: Callable[..., None] = export_step_artifacts
    export_csv_artifacts: Callable[..., None] = export_csv_artifacts
    export_pdf_artifacts: Callable[..., None] = export_pdf_artifacts
    opened_freecad_document: Callable[
        [Any, Path],
        ContextManager[OpenedDocument],
    ] = opened_freecad_document
    write_success_result: Callable[[Path | None, Any], None] = write_success_result
    run_observation_entrypoint: Callable[..., None] | None = None
    run_reference_traversal: Callable[..., ReferenceTraversalExecutionResult] = (
        run_reference_traversal
    )
    write_reference_traversal_output_atomically: Callable[..., None] = (
        write_reference_traversal_output_atomically
    )


_MANIFEST_VALIDATION_FAILURE_PREFIX = "manifest validation failed with "


def _normalize_failure_message(message: str) -> str:
    normalized = " ".join(message.replace("\r", "\n").split())
    return normalized or "runtime failure"


def _failure_stage_for_exception(exc: BaseException) -> str:
    if isinstance(exc, FreeCADUnavailableEntrypointError):
        return FAILURE_STAGE_FREECAD_RESOLUTION

    source = exc
    if isinstance(exc, ExecutionEntrypointError) and exc.__cause__ is not None:
        source = exc.__cause__

    if isinstance(source, ManifestLoadError):
        return FAILURE_STAGE_MANIFEST_LOADING
    if isinstance(source, SourceDocumentPathError):
        return FAILURE_STAGE_SOURCE_DOCUMENT_RESOLUTION
    if isinstance(source, DocumentCloseError):
        return FAILURE_STAGE_DOCUMENT_CLOSE
    if isinstance(source, DocumentLifecycleError):
        return FAILURE_STAGE_DOCUMENT_OPEN
    if isinstance(source, ParameterAssignmentError):
        return FAILURE_STAGE_PARAMETER_ASSIGNMENT
    if isinstance(source, SuppressionMutationError):
        return FAILURE_STAGE_SUPPRESSION
    if isinstance(source, VisibilityMutationError):
        return FAILURE_STAGE_VISIBILITY
    if isinstance(source, DeletionValidityError):
        if isinstance(source.__cause__, DocumentRecomputeError):
            return FAILURE_STAGE_RECOMPUTE
        return FAILURE_STAGE_POST_MUTATION_VALIDITY
    if isinstance(source, DeletionMutationError):
        return FAILURE_STAGE_DELETION
    if isinstance(source, PostMutationValidityError):
        return FAILURE_STAGE_POST_MUTATION_VALIDITY
    if isinstance(source, DocumentRecomputeError):
        return FAILURE_STAGE_RECOMPUTE
    if isinstance(source, DocumentSaveError):
        return FAILURE_STAGE_DOCUMENT_SAVE
    if isinstance(
        source,
        (StepArtifactExportError, CsvArtifactExportError, PdfArtifactExportError),
    ):
        return FAILURE_STAGE_ARTIFACT_EXPORT
    if isinstance(source, ResultWriteError):
        return FAILURE_STAGE_RESULT_WRITE
    if isinstance(source, (ObservationEntrypointError, ObservationRequestError)):
        return FAILURE_STAGE_OBSERVATION
    if isinstance(source, ReferenceTraversalRequestError):
        return REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION
    if isinstance(source, ReferenceTraversalExecutionError) or isinstance(
        exc, _ReferenceTraversalFailedResultError
    ):
        return FAILURE_STAGE_REFERENCE_TRAVERSAL
    if isinstance(source, ReferenceTraversalOutputWriteError):
        if getattr(source, "_is_containment_failure", False):
            return FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_CONTAINMENT
        return FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_WRITE

    if isinstance(exc, ExecutionEntrypointError):
        if str(exc).startswith(_MANIFEST_VALIDATION_FAILURE_PREFIX):
            return FAILURE_STAGE_MANIFEST_VALIDATION

    return FAILURE_STAGE_UNKNOWN


def _structured_failure_from_execution_exception(
    exc: BaseException,
) -> StructuredFailure:
    if isinstance(exc, FreeCADUnavailableEntrypointError):
        return StructuredFailure(
            boundary=FAILURE_BOUNDARY_EXECUTION_ENTRYPOINT,
            category=FAILURE_CATEGORY_FREECAD_UNAVAILABLE,
            code=FAILURE_CODE_FREECAD_UNAVAILABLE,
            message=_normalize_failure_message(str(exc)),
            stage=FAILURE_STAGE_FREECAD_RESOLUTION,
        )

    return StructuredFailure(
        boundary=FAILURE_BOUNDARY_EXECUTION_ENTRYPOINT,
        category=FAILURE_CATEGORY_EXECUTION,
        code=FAILURE_CODE_RUNTIME_FAILURE,
        message=_normalize_failure_message(str(exc)),
        stage=_failure_stage_for_exception(exc),
    )


def _should_skip_failure_result_emission(exc: BaseException) -> bool:
    if isinstance(exc, ResultWriteError):
        return True
    return isinstance(exc, ExecutionEntrypointError) and isinstance(
        exc.__cause__,
        ResultWriteError,
    )


def _try_emit_failure_result(
    result_path: Path | None,
    exc: BaseException,
) -> None:
    if result_path is None or _should_skip_failure_result_emission(exc):
        return

    try:
        write_failure_result(
            result_path,
            _structured_failure_from_execution_exception(exc),
        )
    except Exception:
        return


def _format_manifest_validation_error(
    validation_result: ManifestValidationResult,
) -> str:
    diagnostics = validation_result.diagnostics
    count = len(diagnostics)
    first = diagnostics[0]
    return (
        "manifest validation failed with "
        f"{count} diagnostic(s); first diagnostic: "
        f"{first.path}: {first.message}"
    )


def _validate_execution_manifest(
    *,
    working_copy: Path,
    manifest_path: Path,
) -> ValidatedExecutionManifest:
    try:
        loaded_manifest = load_export_manifest_v1(manifest_path)
    except ManifestLoadError as exc:
        raise ExecutionEntrypointError(str(exc)) from exc

    validation_result = validate_export_manifest_v1(loaded_manifest.data)
    if not validation_result.is_valid:
        raise ExecutionEntrypointError(
            _format_manifest_validation_error(validation_result)
        )

    source_document = loaded_manifest.data[
        EXPORT_MANIFEST_V1_CONTRACT.source_document_field
    ]
    try:
        source_document_path = resolve_source_document_path(
            working_copy,
            source_document,
        )
    except SourceDocumentPathError as exc:
        raise ExecutionEntrypointError(str(exc)) from exc

    return ValidatedExecutionManifest(
        loaded_manifest=loaded_manifest,
        source_document_path=source_document_path,
    )


def _apply_target_mutations_and_recompute(
    document: Any,
    manifest: Mapping[str, Any],
    dependencies: _ExecutionEntrypointDependencies,
) -> None:
    """Compose native consumers in contract order, reusing deletion's checks."""

    contract = EXPORT_MANIFEST_V1_CONTRACT
    consumers = {
        contract.assembly_mutations.suppression_field: dependencies.apply_suppression_mutations,
        contract.assembly_mutations.visibility_field: dependencies.apply_visibility_mutations,
        contract.assembly_mutations.deletion_field: dependencies.apply_deletion_mutations,
    }
    # Preserve ordinary execution's recompute even with no assignments/mutations.
    needs_recompute = True
    has_target_mutations = False
    for section_field in contract.optional_top_level_fields:
        section = manifest.get(section_field, {})
        for family in contract.assembly_mutations.fields:
            mutations = section.get(family, ())
            if not mutations:
                continue
            consumers[family](document, mutations)
            has_target_mutations = True
            # Each successful deletion already recomputes and checks all Bodies.
            # Later suppression/visibility writes require a new final check.
            needs_recompute = family != contract.assembly_mutations.deletion_field

    if needs_recompute:
        dependencies.recompute_document(document)
        if has_target_mutations:
            dependencies.inspect_document_post_mutation_validity(document)


def run_execution_entrypoint(
    *,
    working_copy: Path,
    manifest_path: Path,
    result_path: Path | None,
    output_directory: Path | None = None,
    observation_request_path: Path | None = None,
    reference_traversal_request_path: Path | None = None,
    freecad_module: Any | None = None,
    resolve_freecad_module: Callable[[], Any | None] | None = None,
    _dependencies: _ExecutionEntrypointDependencies = _ExecutionEntrypointDependencies(),
) -> None:
    """Run manifest-driven FreeCAD execution from validated runtime paths."""

    try:
        validated_manifest = _validate_execution_manifest(
            working_copy=working_copy,
            manifest_path=manifest_path,
        )
        reference_traversal_request: ReferenceTraversalRequest | None = None
        if reference_traversal_request_path is not None:
            if output_directory is None:
                raise ExecutionEntrypointError(
                    "reference traversal request requires an output directory"
                )
            try:
                reference_traversal_request = load_reference_traversal_request(
                    reference_traversal_request_path
                )
            except ReferenceTraversalRequestError as exc:
                source_document = validated_manifest.loaded_manifest.data[
                    EXPORT_MANIFEST_V1_CONTRACT.source_document_field
                ]
                diagnostic_source = exc.__cause__ if exc.__cause__ is not None else exc
                _dependencies.write_reference_traversal_output_atomically(
                    working_copy,
                    output_directory / REFERENCE_TRAVERSAL_OUTPUT_FILENAME,
                    boundary=(
                        REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT
                    ),
                    operation=REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
                    status=REFERENCE_TRAVERSAL_STATUS_FAILED,
                    source_document=source_document,
                    nodes=(),
                    edges=(),
                    diagnostics=(
                        RawReferenceTraversalDiagnostic(
                            severity=(
                                REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR
                            ),
                            code=REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_MALFORMED_REQUEST,
                            message=_normalize_failure_message(str(diagnostic_source)),
                            stage=REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION,
                        ),
                    ),
                )
                raise

        observation_request = None
        source_document_sha256 = None
        if observation_request_path is not None:
            if output_directory is None:
                raise ExecutionEntrypointError(
                    "observation request requires an output directory"
                )
            observation_request = load_observation_request(observation_request_path)
            try:
                source_document_sha256 = hashlib.sha256(
                    validated_manifest.source_document_path.read_bytes()
                ).hexdigest()
            except OSError as exc:
                raise ObservationRequestError(
                    "unable to hash source document for observation"
                ) from exc

        resolved_freecad_module = freecad_module
        if resolved_freecad_module is None and resolve_freecad_module is not None:
            resolved_freecad_module = resolve_freecad_module()
        if resolved_freecad_module is None:
            raise FreeCADUnavailableEntrypointError("FreeCAD module is not available")

        assignments = validated_manifest.loaded_manifest.data[
            EXPORT_MANIFEST_V1_CONTRACT.parameter_assignments_field
        ]
        outputs = validated_manifest.loaded_manifest.data[
            EXPORT_MANIFEST_V1_CONTRACT.outputs_field
        ]
        with _dependencies.opened_freecad_document(
            resolved_freecad_module,
            validated_manifest.source_document_path,
        ) as opened:
            _dependencies.apply_parameter_assignments(opened.document, assignments)
            _apply_target_mutations_and_recompute(
                opened.document, validated_manifest.loaded_manifest.data, _dependencies
            )
            _dependencies.save_document(opened.document)
            _dependencies.export_step_artifacts(
                opened.document,
                outputs,
                working_copy=working_copy,
            )
            _dependencies.export_csv_artifacts(
                opened.document,
                outputs,
                working_copy=working_copy,
            )
            _dependencies.export_pdf_artifacts(
                opened.document,
                outputs,
                working_copy=working_copy,
            )
            if reference_traversal_request is not None:
                source_document = validated_manifest.loaded_manifest.data[
                    EXPORT_MANIFEST_V1_CONTRACT.source_document_field
                ]
                traversal_result = _dependencies.run_reference_traversal(
                    opened.document,
                    reference_traversal_request,
                    working_copy=working_copy,
                    source_document=source_document,
                    source_document_path=validated_manifest.source_document_path,
                )
                if traversal_result.status == REFERENCE_TRAVERSAL_STATUS_FAILED:
                    raise _ReferenceTraversalFailedResultError(
                        "reference traversal returned failed status"
                    )
                traversal_output_path = (
                    output_directory / REFERENCE_TRAVERSAL_OUTPUT_FILENAME
                )
                _dependencies.write_reference_traversal_output_atomically(
                    working_copy,
                    traversal_output_path,
                    boundary=(
                        REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT
                    ),
                    operation=REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
                    status=traversal_result.status,
                    source_document=source_document,
                    nodes=traversal_result.nodes,
                    edges=traversal_result.edges,
                    diagnostics=traversal_result.diagnostics,
                )
            if observation_request is not None:
                observation_runner = _dependencies.run_observation_entrypoint
                if observation_runner is None:
                    observation_runner = run_observation_entrypoint
                observation_runner(
                    opened.document,
                    observation_request,
                    working_copy_path=working_copy,
                    working_copy_sha256=source_document_sha256,
                    output_directory=output_directory,
                )
        _dependencies.write_success_result(result_path, outputs)
    except (
        SuppressionMutationError,
        VisibilityMutationError,
        DeletionMutationError,
        PostMutationValidityError,
        CsvArtifactExportError,
        DocumentLifecycleError,
        DocumentRecomputeError,
        DocumentSaveError,
        ExecutionEntrypointError,
        ParameterAssignmentError,
        PdfArtifactExportError,
        ResultWriteError,
        StepArtifactExportError,
        ObservationEntrypointError,
        ObservationRequestError,
        ReferenceTraversalRequestError,
        ReferenceTraversalExecutionError,
        ReferenceTraversalOutputWriteError,
    ) as exc:
        _try_emit_failure_result(result_path, exc)
        if isinstance(exc, ExecutionEntrypointError):
            raise
        raise ExecutionEntrypointError(str(exc)) from exc


def run_observation_entrypoint(
    document: Any,
    verification_data: Mapping[str, Any],
    *,
    working_copy_path: str | os.PathLike[str],
    working_copy_sha256: str,
    output_directory: str | os.PathLike[str],
) -> None:
    """Generate observed output from already-injected Phase 2 runtime state."""

    try:
        generate_observed_output(
            document,
            verification_data,
            working_copy_path=working_copy_path,
            working_copy_sha256=working_copy_sha256,
            output_directory=output_directory,
        )
    except ObservedOutputError as exc:
        raise ObservationEntrypointError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class _DocumentObservationEntrypointDependencies:
    opened_freecad_document: Callable[
        [Any, Path],
        ContextManager[OpenedDocument],
    ] = opened_freecad_document
    run_observation_entrypoint: Callable[..., None] = run_observation_entrypoint


def run_document_observation_entrypoint(
    *,
    working_copy: Path,
    source_document: str | os.PathLike[str],
    verification_data: Mapping[str, Any],
    working_copy_path: str | os.PathLike[str],
    working_copy_sha256: str,
    output_directory: str | os.PathLike[str],
    freecad_module: Any | None = None,
    resolve_freecad_module: Callable[[], Any | None] | None = None,
    _dependencies: _DocumentObservationEntrypointDependencies = (
        _DocumentObservationEntrypointDependencies()
    ),
) -> None:
    """Generate observed output by opening a source document through lifecycle helpers."""

    try:
        source_document_path = resolve_source_document_path(
            working_copy,
            os.fspath(source_document),
        )
        resolved_freecad_module = freecad_module
        if resolved_freecad_module is None and resolve_freecad_module is not None:
            resolved_freecad_module = resolve_freecad_module()
        if resolved_freecad_module is None:
            raise ObservationEntrypointError("FreeCAD module is not available")

        with _dependencies.opened_freecad_document(
            resolved_freecad_module,
            source_document_path,
        ) as opened:
            _dependencies.run_observation_entrypoint(
                opened.document,
                verification_data,
                working_copy_path=working_copy_path,
                working_copy_sha256=working_copy_sha256,
                output_directory=output_directory,
            )
    except DocumentLifecycleError as exc:
        raise ObservationEntrypointError(str(exc)) from exc


__all__ = [
    "ExecutionEntrypointError",
    "FreeCADUnavailableEntrypointError",
    "ObservationEntrypointError",
    "ValidatedExecutionManifest",
    "run_document_observation_entrypoint",
    "run_execution_entrypoint",
    "run_observation_entrypoint",
]
