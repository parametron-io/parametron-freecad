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
from parametron_freecad.execution.post_mutation_validity import (
    PostMutationValidityError,
    inspect_document_post_mutation_validity,
)
from parametron_freecad.execution.result_writer import (
    ResultWriteError,
    write_success_result,
)
from parametron_freecad.execution.step_export import (
    StepArtifactExportError,
    export_step_artifacts,
)
from parametron_freecad.execution.suppression import (
    SuppressionMutationError,
    apply_suppression_mutations,
)
from parametron_freecad.execution.visibility import (
    VisibilityMutationError,
    apply_visibility_mutations,
)
from parametron_freecad.observation.observed_contract import (
    PARAMETRON_OBSERVED_CONTRACT,
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
from parametron_freecad.runtime.evidence_sidecar import (
    EvidenceSidecarContainmentError,
    EvidenceSidecarError,
    EvidenceSidecarWriteError,
    remove_evidence_sidecar,
    require_evidence_output_directory,
)
from parametron_freecad.runtime.fact_evidence import (
    FACT_EVIDENCE_FILENAME,
    FactObservationError,
    inspect_fact_evidence,
    prepare_fact_evidence,
    write_fact_evidence,
)
from parametron_freecad.runtime.fact_request import (
    FACT_REQUEST_FILENAME,
    FactRequestError,
    discover_fact_request,
    load_fact_request,
)
from parametron_freecad.runtime.failure_output_contract import (
    FAILURE_BOUNDARY_EXECUTION_ENTRYPOINT,
    FAILURE_CATEGORY_EXECUTION,
    FAILURE_CATEGORY_FREECAD_UNAVAILABLE,
    FAILURE_CODE_FREECAD_UNAVAILABLE,
    FAILURE_CODE_RUNTIME_FAILURE,
    FAILURE_STAGE_ARTIFACT_EXPORT,
    FAILURE_STAGE_DELETION,
    FAILURE_STAGE_DOCUMENT_CLOSE,
    FAILURE_STAGE_DOCUMENT_OPEN,
    FAILURE_STAGE_DOCUMENT_SAVE,
    FAILURE_STAGE_FACT_EVIDENCE,
    FAILURE_STAGE_FACT_REQUEST,
    FAILURE_STAGE_FREECAD_RESOLUTION,
    FAILURE_STAGE_INTEGRITY_BASELINE,
    FAILURE_STAGE_INTEGRITY_EVIDENCE,
    FAILURE_STAGE_INTEGRITY_RESULT,
    FAILURE_STAGE_MANIFEST_LOADING,
    FAILURE_STAGE_MANIFEST_VALIDATION,
    FAILURE_STAGE_OBSERVATION,
    FAILURE_STAGE_OBSERVATION_OUTPUT,
    FAILURE_STAGE_OCCURRENCE_EVIDENCE,
    FAILURE_STAGE_OCCURRENCE_REQUEST,
    FAILURE_STAGE_PARAMETER_ASSIGNMENT,
    FAILURE_STAGE_POST_MUTATION_VALIDITY,
    FAILURE_STAGE_RECOMPUTE,
    FAILURE_STAGE_REFERENCE_TRAVERSAL,
    FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_CONTAINMENT,
    FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_WRITE,
    FAILURE_STAGE_RESOURCE_INVENTORY,
    FAILURE_STAGE_RESULT_WRITE,
    FAILURE_STAGE_SOURCE_DOCUMENT_RESOLUTION,
    FAILURE_STAGE_SUPPRESSION,
    FAILURE_STAGE_UNKNOWN,
    FAILURE_STAGE_VISIBILITY,
    StructuredFailure,
)
from parametron_freecad.runtime.failure_result_writer import write_failure_result
from parametron_freecad.runtime.integrity_observation import (
    INTEGRITY_EVIDENCE_FILENAME,
    IntegrityBaselineError,
    IntegrityEvidenceError,
    IntegrityObservationError,
    IntegrityResultError,
    observe_persisted_result,
    prepare_integrity_observation,
    write_integrity_evidence,
)
from parametron_freecad.runtime.observation_request import (
    ObservationRequestError,
    load_observation_request,
)
from parametron_freecad.runtime.occurrence_access import (
    OccurrenceNativeAccessError,
)
from parametron_freecad.runtime.occurrence_evidence import (
    OCCURRENCE_EVIDENCE_FILENAME,
    OccurrenceObservationError,
    inspect_occurrence_evidence,
    prepare_occurrence_evidence,
    require_occurrence_parent_source,
    resolve_freecad_version,
    resolver_from_inventory,
    resolver_from_selected_source,
    write_occurrence_evidence,
)
from parametron_freecad.runtime.occurrence_request import (
    OCCURRENCE_REQUEST_FILENAME,
    OccurrenceRequestError,
    discover_occurrence_request,
    load_occurrence_request,
)
from parametron_freecad.runtime.reference_traversal import (
    ReferenceTraversalExecutionError,
    ReferenceTraversalExecutionResult,
    run_reference_traversal,
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
from parametron_freecad.runtime.reference_traversal_request import (
    REFERENCE_TRAVERSAL_OUTPUT_FILENAME,
    ReferenceTraversalRequest,
    ReferenceTraversalRequestError,
    load_reference_traversal_request,
)
from parametron_freecad.runtime.resource_inventory import (
    ResourceInventoryError,
    load_resource_inventory,
)


class ExecutionEntrypointError(ValueError):
    """Raised when runtime execution fails after path validation."""


class FreeCADUnavailableEntrypointError(ExecutionEntrypointError):
    """Raised when execution needs FreeCAD but the caller boundary cannot supply it."""


class ObservationEntrypointError(ValueError):
    """Raised when runtime observation output generation fails."""


class _ReferenceTraversalFailedResultError(ExecutionEntrypointError):
    """Internal marker for a typed failed traversal result."""


class EvidenceOutputDirectoryError(ExecutionEntrypointError):
    """Raised when an enabled evidence surface has no usable output directory."""

    def __init__(self, message: str, *, stage: str) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True, slots=True)
class _EvidenceSurface:
    label: str
    filename: str
    stage: str


@dataclass(frozen=True, slots=True)
class ValidatedExecutionManifest:
    loaded_manifest: LoadedManifest
    source_document_path: Path


@dataclass(frozen=True, slots=True)
class _ExecutionEntrypointDependencies:
    apply_parameter_assignments: Callable[[Any, Any], None] = (
        apply_parameter_assignments
    )
    apply_suppression_mutations: Callable[[Any, Any], None] = (
        apply_suppression_mutations
    )
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


def _request_sidecar_present(working_copy: Path, filename: str) -> bool:
    return os.path.lexists(working_copy / filename)


def _enabled_evidence_surfaces(
    *,
    traversal_enabled: bool,
    observation_enabled: bool,
    integrity_enabled: bool,
    occurrence_enabled: bool,
    fact_enabled: bool,
) -> tuple[_EvidenceSurface, ...]:
    surfaces: list[_EvidenceSurface] = []
    if traversal_enabled:
        surfaces.append(
            _EvidenceSurface(
                label="reference traversal request",
                filename=REFERENCE_TRAVERSAL_OUTPUT_FILENAME,
                stage=FAILURE_STAGE_REFERENCE_TRAVERSAL_OUTPUT_CONTAINMENT,
            )
        )
    if observation_enabled:
        surfaces.append(
            _EvidenceSurface(
                label="observation request",
                filename=PARAMETRON_OBSERVED_CONTRACT.filename,
                stage=FAILURE_STAGE_OBSERVATION_OUTPUT,
            )
        )
    if integrity_enabled:
        surfaces.append(
            _EvidenceSurface(
                label="integrity evidence",
                filename=INTEGRITY_EVIDENCE_FILENAME,
                stage=FAILURE_STAGE_INTEGRITY_EVIDENCE,
            )
        )
    if occurrence_enabled:
        surfaces.append(
            _EvidenceSurface(
                label="occurrence evidence",
                filename=OCCURRENCE_EVIDENCE_FILENAME,
                stage=FAILURE_STAGE_OCCURRENCE_EVIDENCE,
            )
        )
    if fact_enabled:
        surfaces.append(
            _EvidenceSurface(
                label="fact evidence",
                filename=FACT_EVIDENCE_FILENAME,
                stage=FAILURE_STAGE_FACT_EVIDENCE,
            )
        )
    return tuple(surfaces)


def _require_enabled_evidence_output_directory(
    *,
    working_copy: Path,
    output_directory: Path | None,
    surfaces: tuple[_EvidenceSurface, ...],
) -> None:
    if not surfaces:
        return
    primary = surfaces[0]
    if output_directory is None:
        raise EvidenceOutputDirectoryError(
            f"{primary.label} requires an output directory",
            stage=primary.stage,
        )
    try:
        require_evidence_output_directory(
            working_copy=working_copy,
            output_directory=output_directory,
        )
    except (EvidenceSidecarContainmentError, EvidenceSidecarError) as exc:
        raise EvidenceOutputDirectoryError(
            f"{primary.label} requires an existing output directory",
            stage=primary.stage,
        ) from exc


def _remove_stale_evidence(
    *,
    working_copy: Path,
    output_directory: Path | None,
    surfaces: tuple[_EvidenceSurface, ...],
) -> None:
    if output_directory is None:
        return
    for surface in surfaces:
        try:
            remove_evidence_sidecar(
                working_copy=working_copy,
                output_directory=output_directory,
                filename=surface.filename,
            )
        except (EvidenceSidecarError, EvidenceSidecarWriteError) as exc:
            raise EvidenceOutputDirectoryError(
                f"{surface.label} destination is not usable",
                stage=surface.stage,
            ) from exc


def _selected_source_sha256(
    *,
    observation_enabled: bool,
    integrity_observation: Any | None,
    source_document_path: Path,
) -> str | None:
    if not observation_enabled:
        return None
    if integrity_observation is not None:
        digest = integrity_observation.primary.baseline_sha256
        if isinstance(digest, str) and digest:
            return digest
    try:
        return hashlib.sha256(source_document_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ObservationRequestError(
            "unable to hash source document for observation"
        ) from exc


def _failure_stage_for_exception(exc: BaseException) -> str:
    if isinstance(exc, EvidenceOutputDirectoryError):
        return exc.stage
    if isinstance(exc, ExecutionEntrypointError) and isinstance(
        exc.__cause__, EvidenceOutputDirectoryError
    ):
        return exc.__cause__.stage
    if isinstance(exc, FreeCADUnavailableEntrypointError):
        return FAILURE_STAGE_FREECAD_RESOLUTION

    source = exc
    if isinstance(exc, ExecutionEntrypointError) and exc.__cause__ is not None:
        source = exc.__cause__

    if isinstance(source, ManifestLoadError):
        return FAILURE_STAGE_MANIFEST_LOADING
    if isinstance(source, SourceDocumentPathError):
        return FAILURE_STAGE_SOURCE_DOCUMENT_RESOLUTION
    if isinstance(source, ResourceInventoryError):
        return FAILURE_STAGE_RESOURCE_INVENTORY
    if isinstance(source, IntegrityBaselineError):
        return FAILURE_STAGE_INTEGRITY_BASELINE
    if isinstance(source, IntegrityResultError):
        return FAILURE_STAGE_INTEGRITY_RESULT
    if isinstance(source, IntegrityEvidenceError):
        return FAILURE_STAGE_INTEGRITY_EVIDENCE
    if isinstance(source, IntegrityObservationError):
        return FAILURE_STAGE_INTEGRITY_EVIDENCE
    if isinstance(source, OccurrenceRequestError):
        return FAILURE_STAGE_OCCURRENCE_REQUEST
    if isinstance(source, (OccurrenceObservationError, OccurrenceNativeAccessError)):
        return FAILURE_STAGE_OCCURRENCE_EVIDENCE
    if isinstance(source, FactRequestError):
        return FAILURE_STAGE_FACT_REQUEST
    if isinstance(source, FactObservationError):
        return FAILURE_STAGE_FACT_EVIDENCE
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
    integrity_request_path: str | Path | None = None,
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
        source_document = validated_manifest.loaded_manifest.data[
            EXPORT_MANIFEST_V1_CONTRACT.source_document_field
        ]
        evidence_surfaces = _enabled_evidence_surfaces(
            traversal_enabled=reference_traversal_request_path is not None,
            observation_enabled=observation_request_path is not None,
            integrity_enabled=integrity_request_path is not None,
            occurrence_enabled=_request_sidecar_present(
                working_copy, OCCURRENCE_REQUEST_FILENAME
            ),
            fact_enabled=_request_sidecar_present(working_copy, FACT_REQUEST_FILENAME),
        )
        _require_enabled_evidence_output_directory(
            working_copy=working_copy,
            output_directory=output_directory,
            surfaces=evidence_surfaces,
        )
        _remove_stale_evidence(
            working_copy=working_copy,
            output_directory=output_directory,
            surfaces=evidence_surfaces,
        )
        reference_traversal_request: ReferenceTraversalRequest | None = None
        if reference_traversal_request_path is not None:
            try:
                reference_traversal_request = load_reference_traversal_request(
                    reference_traversal_request_path
                )
            except ReferenceTraversalRequestError as exc:
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
                            severity=(REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR),
                            code=REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_MALFORMED_REQUEST,
                            message=_normalize_failure_message(str(diagnostic_source)),
                            stage=REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION,
                        ),
                    ),
                )
                raise

        observation_request = None
        if observation_request_path is not None:
            observation_request = load_observation_request(observation_request_path)

        integrity_observation = None
        inventory = None
        if integrity_request_path is not None:
            inventory = load_resource_inventory(
                integrity_request_path,
                working_copy=working_copy,
                expected_source_path=validated_manifest.source_document_path,
            )
            integrity_observation = prepare_integrity_observation(
                inventory,
                working_copy=working_copy,
                output_directory=output_directory,
            )

        occurrence_request = None
        occurrence_resolver = None
        occurrence_request_path = discover_occurrence_request(working_copy)
        if occurrence_request_path is not None:
            prepare_occurrence_evidence(
                working_copy=working_copy,
                output_directory=output_directory,
            )
            occurrence_request = load_occurrence_request(occurrence_request_path)
            if inventory is not None:
                require_occurrence_parent_source(
                    occurrence_request,
                    inventory,
                    source_document=source_document,
                )
                occurrence_resolver = resolver_from_inventory(
                    inventory,
                    project_id=(occurrence_request.scope.parent.resource.project_id),
                )
            else:
                occurrence_resolver = resolver_from_selected_source(
                    parent_resource=occurrence_request.scope.parent.resource,
                    source_document=source_document,
                    source_path=validated_manifest.source_document_path,
                )

        fact_request = None
        fact_request_path = discover_fact_request(working_copy)
        if fact_request_path is not None:
            prepare_fact_evidence(
                working_copy=working_copy,
                output_directory=output_directory,
            )
            fact_request = load_fact_request(fact_request_path)

        source_document_sha256 = _selected_source_sha256(
            observation_enabled=observation_request is not None,
            integrity_observation=integrity_observation,
            source_document_path=validated_manifest.source_document_path,
        )

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
        occurrence_observation = None
        fact_observation = None
        with _dependencies.opened_freecad_document(
            resolved_freecad_module,
            validated_manifest.source_document_path,
        ) as opened:
            _dependencies.apply_parameter_assignments(opened.document, assignments)
            _apply_target_mutations_and_recompute(
                opened.document, validated_manifest.loaded_manifest.data, _dependencies
            )
            _dependencies.save_document(opened.document)
            if integrity_observation is not None:
                integrity_observation = observe_persisted_result(
                    integrity_observation,
                    document=opened.document,
                    opened_path=opened.path,
                )
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
            if occurrence_request is not None:
                if occurrence_resolver is None:
                    raise OccurrenceObservationError(
                        "occurrence resource resolver is unavailable"
                    )
                occurrence_observation = inspect_occurrence_evidence(
                    opened.document,
                    occurrence_request,
                    source_document=source_document,
                    resolver=occurrence_resolver,
                    freecad_version=resolve_freecad_version(resolved_freecad_module),
                )
            if fact_request is not None:
                fact_observation = inspect_fact_evidence(
                    opened.document,
                    fact_request,
                    source_path=opened.path,
                    inventory=inventory,
                    freecad_module=resolved_freecad_module,
                    freecad_version=resolve_freecad_version(resolved_freecad_module),
                )
            if occurrence_observation is not None:
                write_occurrence_evidence(
                    occurrence_observation,
                    working_copy=working_copy,
                    output_directory=output_directory,
                )
            if fact_observation is not None:
                write_fact_evidence(
                    fact_observation,
                    working_copy=working_copy,
                    output_directory=output_directory,
                )
        if integrity_observation is not None:
            write_integrity_evidence(
                integrity_observation,
                working_copy=working_copy,
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
        ResourceInventoryError,
        IntegrityObservationError,
        OccurrenceRequestError,
        OccurrenceObservationError,
        OccurrenceNativeAccessError,
        FactRequestError,
        FactObservationError,
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
    "EvidenceOutputDirectoryError",
    "ExecutionEntrypointError",
    "FreeCADUnavailableEntrypointError",
    "ObservationEntrypointError",
    "ValidatedExecutionManifest",
    "run_document_observation_entrypoint",
    "run_execution_entrypoint",
    "run_observation_entrypoint",
]
