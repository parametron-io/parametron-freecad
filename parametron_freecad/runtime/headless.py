"""Headless FreeCAD runtime entrypoints and argument handling."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Literal, TextIO

from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.common.paths import (
    require_child_path,
    require_existing_directory,
    require_existing_file,
)
from parametron_freecad.execution.document_recompute import (
    DocumentRecomputeError,
    recompute_document,
)
from parametron_freecad.execution.document_save import (
    DocumentSaveError,
    save_document,
)
from parametron_freecad.execution.parameter_assignment import (
    ParameterAssignmentError,
    apply_parameter_assignments,
)
from parametron_freecad.execution.csv_export import (
    CsvArtifactExportError,
    export_csv_artifacts,
)
from parametron_freecad.execution.pdf_export import (
    PdfArtifactExportError,
    export_pdf_artifacts,
)
from parametron_freecad.execution.step_export import (
    StepArtifactExportError,
    export_step_artifacts,
)
from parametron_freecad.execution.result_writer import (
    ResultWriteError,
    write_success_result,
)
from parametron_freecad.runtime.document_lifecycle import (
    DocumentLifecycleError,
    opened_freecad_document,
)
from parametron_freecad.runtime.entrypoints import (
    ExecutionEntrypointError,
    FreeCADUnavailableEntrypointError,
    ValidatedExecutionManifest,
    _ExecutionEntrypointDependencies,
    _format_manifest_validation_error,
    _validate_execution_manifest,
    run_execution_entrypoint,
)
from parametron_freecad.runtime.exit_codes import (
    ARGUMENT_ERROR_EXIT_CODE,
    EXECUTION_FAILURE_EXIT_CODE,
    FREECAD_UNAVAILABLE_EXIT_CODE,
    SUCCESS_EXIT_CODE,
)
from parametron_freecad.runtime.reference_traversal_request import (
    REFERENCE_TRAVERSAL_REQUEST_CLI_FLAG,
)

# Deprecated compatibility surface for callers that imported the old boundary.
EXECUTION_NOT_IMPLEMENTED_EXIT_CODE = 3

FREECAD_UNAVAILABLE_MESSAGE = (
    "parametron-freecad: FreeCAD module is not available"
)
INVALID_ARGUMENTS_MESSAGE_PREFIX = "parametron-freecad: invalid arguments: "
EXECUTION_FAILURE_MESSAGE_PREFIX = "parametron-freecad: execute failed: "
EXECUTION_NOT_IMPLEMENTED_MESSAGE = (
    "parametron-freecad: execute mode is not implemented yet"
)


@dataclass(frozen=True, slots=True)
class HeadlessInvocation:
    command: Literal["smoke", "execute"]
    working_copy: Path | None = None
    manifest: Path | None = None
    result: Path | None = None
    output_dir: Path | None = None
    observation_request: Path | None = None
    reference_traversal_request: Path | None = None


class HeadlessArgumentError(ValueError):
    """Raised when headless CLI arguments are invalid."""


ExecuteRuntimeError = ExecutionEntrypointError
ValidatedExecuteManifest = ValidatedExecutionManifest


class _HeadlessArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise HeadlessArgumentError(message)


def _build_execute_argument_parser() -> argparse.ArgumentParser:
    parser = _HeadlessArgumentParser(
        prog="parametron-freecad execute",
        add_help=False,
        allow_abbrev=False,
    )
    parser.add_argument("--working-copy", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--observation-request")
    parser.add_argument(REFERENCE_TRAVERSAL_REQUEST_CLI_FLAG)
    return parser


def _normalize_working_copy(path: str) -> Path:
    try:
        return require_existing_directory(path)
    except ValueError as exc:
        raise HeadlessArgumentError(f"--working-copy {exc}") from exc


def _normalize_manifest(path: str, *, working_copy: Path) -> Path:
    try:
        manifest = require_existing_file(path)
    except ValueError as exc:
        raise HeadlessArgumentError(f"--manifest {exc}") from exc

    try:
        return require_child_path(working_copy, manifest)
    except ValueError as exc:
        raise HeadlessArgumentError(f"--manifest {exc}") from exc


def _normalize_result(path: str, *, working_copy: Path) -> Path:
    result = Path(path).expanduser().resolve(strict=False)

    try:
        return require_child_path(working_copy, result)
    except ValueError as exc:
        raise HeadlessArgumentError(f"--result {exc}") from exc


def _normalize_optional_path(
    path: str | None,
    *,
    option: str,
    working_copy: Path,
) -> Path | None:
    if path is None:
        return None
    if not path.strip():
        raise HeadlessArgumentError(f"{option} must not be empty")

    resolved = Path(path).expanduser().resolve(strict=False)
    try:
        return require_child_path(working_copy, resolved)
    except ValueError as exc:
        raise HeadlessArgumentError(f"{option} {exc}") from exc


def _normalize_output_dir(path: str | None, *, working_copy: Path) -> Path | None:
    output_dir = _normalize_optional_path(
        path,
        option="--output-dir",
        working_copy=working_copy,
    )
    if output_dir is not None and output_dir.exists() and not output_dir.is_dir():
        raise HeadlessArgumentError(
            f"--output-dir path is not a directory: {output_dir}"
        )
    return output_dir


def _normalize_observation_request(
    path: str | None,
    *,
    working_copy: Path,
) -> Path | None:
    request = _normalize_optional_path(
        path,
        option="--observation-request",
        working_copy=working_copy,
    )
    if request is None:
        return None
    try:
        return require_existing_file(request)
    except ValueError as exc:
        raise HeadlessArgumentError(f"--observation-request {exc}") from exc


def _normalize_reference_traversal_request(
    path: str | None,
    *,
    working_copy: Path,
) -> Path | None:
    request = _normalize_optional_path(
        path,
        option=REFERENCE_TRAVERSAL_REQUEST_CLI_FLAG,
        working_copy=working_copy,
    )
    if request is None:
        return None
    try:
        return require_existing_file(request)
    except ValueError as exc:
        raise HeadlessArgumentError(
            f"{REFERENCE_TRAVERSAL_REQUEST_CLI_FLAG} {exc}"
        ) from exc


def parse_headless_arguments(argv: list[str] | None) -> HeadlessInvocation:
    if argv is None:
        return HeadlessInvocation(command="smoke")

    if not argv:
        return HeadlessInvocation(command="smoke")

    command = argv[0]

    if command == "smoke":
        if len(argv) != 1:
            raise HeadlessArgumentError(
                f"smoke does not accept additional arguments: {' '.join(argv[1:])}"
            )
        return HeadlessInvocation(command="smoke")

    if command != "execute":
        raise HeadlessArgumentError(f"unknown command: {command}")

    namespace = _build_execute_argument_parser().parse_args(argv[1:])
    working_copy = _normalize_working_copy(namespace.working_copy)
    manifest = _normalize_manifest(namespace.manifest, working_copy=working_copy)
    result = _normalize_result(namespace.result, working_copy=working_copy)
    output_dir = _normalize_output_dir(namespace.output_dir, working_copy=working_copy)
    observation_request = _normalize_observation_request(
        namespace.observation_request,
        working_copy=working_copy,
    )
    if observation_request is not None and output_dir is None:
        raise HeadlessArgumentError(
            "--observation-request requires --output-dir"
        )
    reference_traversal_request = _normalize_reference_traversal_request(
        namespace.reference_traversal_request,
        working_copy=working_copy,
    )
    if reference_traversal_request is not None and output_dir is None:
        raise HeadlessArgumentError(
            f"{REFERENCE_TRAVERSAL_REQUEST_CLI_FLAG} requires --output-dir"
        )
    if reference_traversal_request is not None and not output_dir.is_dir():
        raise HeadlessArgumentError(
            "--output-dir must be an existing directory when reference "
            "traversal output emission is requested"
        )

    return HeadlessInvocation(
        command="execute",
        working_copy=working_copy,
        manifest=manifest,
        result=result,
        output_dir=output_dir,
        observation_request=observation_request,
        reference_traversal_request=reference_traversal_request,
    )


def _resolve_freecad_module(freecad_module: Any | None) -> Any | None:
    if freecad_module is not None:
        return freecad_module

    try:
        return import_module("FreeCAD")
    except ImportError:
        return None


def run_headless_smoke(
    freecad_module: Any,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    del stderr

    payload = {
        "freecadVersion": freecad_module.Version(),
        "host": "freecadcmd",
        "status": "ok",
    }
    stdout.write(dumps_canonical(payload))
    return SUCCESS_EXIT_CODE


def run_execute_not_implemented(
    invocation: HeadlessInvocation,
    stderr: TextIO,
) -> int:
    del invocation
    stderr.write(f"{EXECUTION_NOT_IMPLEMENTED_MESSAGE}\n")
    return EXECUTION_NOT_IMPLEMENTED_EXIT_CODE


def _validate_execute_manifest(
    *,
    working_copy: Path,
    manifest_path: Path,
) -> ValidatedExecuteManifest:
    return _validate_execution_manifest(
        working_copy=working_copy,
        manifest_path=manifest_path,
    )


def _run_execute(
    invocation: HeadlessInvocation,
    stderr: TextIO,
    freecad_module: Any | None,
) -> int:
    if invocation.working_copy is None or invocation.manifest is None:
        raise ExecuteRuntimeError("execute invocation is missing validated paths")

    try:
        run_execution_entrypoint(
            working_copy=invocation.working_copy,
            manifest_path=invocation.manifest,
            result_path=invocation.result,
            output_directory=invocation.output_dir,
            observation_request_path=invocation.observation_request,
            reference_traversal_request_path=invocation.reference_traversal_request,
            freecad_module=freecad_module,
            resolve_freecad_module=lambda: _resolve_freecad_module(None),
            _dependencies=_ExecutionEntrypointDependencies(
                apply_parameter_assignments=apply_parameter_assignments,
                recompute_document=recompute_document,
                save_document=save_document,
                export_step_artifacts=export_step_artifacts,
                export_csv_artifacts=export_csv_artifacts,
                export_pdf_artifacts=export_pdf_artifacts,
                opened_freecad_document=opened_freecad_document,
                write_success_result=write_success_result,
            ),
        )
    except FreeCADUnavailableEntrypointError:
        stderr.write(f"{FREECAD_UNAVAILABLE_MESSAGE}\n")
        return FREECAD_UNAVAILABLE_EXIT_CODE
    except ExecuteRuntimeError as exc:
        stderr.write(f"{EXECUTION_FAILURE_MESSAGE_PREFIX}{exc}\n")
        return EXECUTION_FAILURE_EXIT_CODE

    return SUCCESS_EXIT_CODE


def _run_smoke(
    *,
    stdout: TextIO,
    stderr: TextIO,
    freecad_module: Any | None,
) -> int:
    resolved_freecad_module = _resolve_freecad_module(freecad_module)
    if resolved_freecad_module is None:
        stderr.write(f"{FREECAD_UNAVAILABLE_MESSAGE}\n")
        return FREECAD_UNAVAILABLE_EXIT_CODE

    return run_headless_smoke(
        freecad_module=resolved_freecad_module,
        stdout=stdout,
        stderr=stderr,
    )


def main(
    argv: list[str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    freecad_module: Any | None = None,
) -> int:
    import sys

    resolved_argv = argv
    resolved_stdout = sys.stdout if stdout is None else stdout
    resolved_stderr = sys.stderr if stderr is None else stderr

    try:
        invocation = parse_headless_arguments(resolved_argv)
    except HeadlessArgumentError as exc:
        resolved_stderr.write(f"{INVALID_ARGUMENTS_MESSAGE_PREFIX}{exc}\n")
        return ARGUMENT_ERROR_EXIT_CODE

    if invocation.command == "execute":
        return _run_execute(invocation, resolved_stderr, freecad_module)

    return _run_smoke(
        stdout=resolved_stdout,
        stderr=resolved_stderr,
        freecad_module=freecad_module,
    )
