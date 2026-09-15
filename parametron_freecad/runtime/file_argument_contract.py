"""Engine-to-FreeCAD required file-argument contract metadata."""

from __future__ import annotations

from dataclasses import dataclass

from parametron_freecad.execution.manifest_contract import EXPORT_MANIFEST_V1_FILENAME
from parametron_freecad.observation.observed_contract import PARAMETRON_OBSERVED_FILENAME
from parametron_freecad.observation.verification_contract import (
    PARAMETRON_VERIFICATION_FILENAME,
)
from parametron_freecad.runtime.reference_traversal_request import (
    REFERENCE_TRAVERSAL_OUTPUT_FILENAME,
    REFERENCE_TRAVERSAL_REQUEST_CLI_FLAG,
    REFERENCE_TRAVERSAL_REQUEST_FILENAME,
)

FILE_ARGUMENT_CONTRACT_VERSION = "1.0"

# Semantic role constants — use these exact strings to avoid drift
FILE_ARGUMENT_ROLE_CONTEXT_PATH = "context_path"
FILE_ARGUMENT_ROLE_INPUT_FILE = "input_file"
FILE_ARGUMENT_ROLE_OUTPUT_PATH = "output_path"
FILE_ARGUMENT_ROLE_OUTPUT_DIRECTORY = "output_directory"

# Boundary constants — use these exact strings to avoid drift
FILE_ARGUMENT_BOUNDARY_EXECUTE_CLI = "execute_cli"
FILE_ARGUMENT_BOUNDARY_ENGINE_EXECUTE = "engine_execute"
FILE_ARGUMENT_BOUNDARY_ENGINE_OBSERVE = "engine_observe"

# Status constants — use these exact strings to avoid drift
FILE_ARGUMENT_STATUS_IMPLEMENTED = "implemented"
FILE_ARGUMENT_STATUS_PLANNED = "planned"

# result.json has no central filename constant elsewhere; define it here
RESULT_JSON_FILENAME = "prm.result.json"


@dataclass(frozen=True, slots=True)
class FileArgumentSpec:
    """Immutable metadata for one required file/path argument at a runtime boundary."""

    name: str
    boundary: str
    required: bool
    status: str
    role: str
    cli_flag: str | None
    invocation_field: str | None
    canonical_filename: str | None
    path_contract: str


@dataclass(frozen=True, slots=True)
class EngineFileArgumentContract:
    """Engine-to-FreeCAD required file-argument contract metadata."""

    version: str
    file_arguments: tuple[FileArgumentSpec, ...]
    required_file_arguments: tuple[FileArgumentSpec, ...]
    implemented_required_file_arguments: tuple[FileArgumentSpec, ...]
    planned_required_file_arguments: tuple[FileArgumentSpec, ...]
    execute_cli_required_file_arguments: tuple[FileArgumentSpec, ...]
    engine_execute_required_file_arguments: tuple[FileArgumentSpec, ...]
    engine_observe_required_file_arguments: tuple[FileArgumentSpec, ...]
    canonical_file_contract_names: tuple[str, ...]


# ---------------------------------------------------------------------------
# Execute CLI file argument specs
# ---------------------------------------------------------------------------

EXECUTE_CLI_WORKING_COPY_SPEC = FileArgumentSpec(
    name="working_copy",
    boundary=FILE_ARGUMENT_BOUNDARY_EXECUTE_CLI,
    required=True,
    status=FILE_ARGUMENT_STATUS_IMPLEMENTED,
    role=FILE_ARGUMENT_ROLE_CONTEXT_PATH,
    cli_flag="--working-copy",
    invocation_field=None,
    canonical_filename=None,
    path_contract=(
        "The supplied existing directory is the authoritative "
        "execution-instance root. All runtime file arguments and "
        "manifest-resolved paths must remain contained beneath it. "
        "The root name is not prescribed."
    ),
)

EXECUTE_CLI_MANIFEST_SPEC = FileArgumentSpec(
    name="manifest",
    boundary=FILE_ARGUMENT_BOUNDARY_EXECUTE_CLI,
    required=True,
    status=FILE_ARGUMENT_STATUS_IMPLEMENTED,
    role=FILE_ARGUMENT_ROLE_INPUT_FILE,
    cli_flag="--manifest",
    invocation_field=None,
    canonical_filename=EXPORT_MANIFEST_V1_FILENAME,
    path_contract="must be an existing file inside the working copy",
)

EXECUTE_CLI_RESULT_SPEC = FileArgumentSpec(
    name="result",
    boundary=FILE_ARGUMENT_BOUNDARY_EXECUTE_CLI,
    required=True,
    status=FILE_ARGUMENT_STATUS_IMPLEMENTED,
    role=FILE_ARGUMENT_ROLE_OUTPUT_PATH,
    cli_flag="--result",
    invocation_field=None,
    canonical_filename=RESULT_JSON_FILENAME,
    path_contract=(
        "must resolve inside the working copy; "
        "not created during argument validation"
    ),
)

EXECUTE_CLI_REFERENCE_TRAVERSAL_REQUEST_SPEC = FileArgumentSpec(
    name="reference_traversal_request",
    boundary=FILE_ARGUMENT_BOUNDARY_EXECUTE_CLI,
    required=False,
    status=FILE_ARGUMENT_STATUS_IMPLEMENTED,
    role=FILE_ARGUMENT_ROLE_INPUT_FILE,
    cli_flag=REFERENCE_TRAVERSAL_REQUEST_CLI_FLAG,
    invocation_field="reference_traversal_request",
    canonical_filename=REFERENCE_TRAVERSAL_REQUEST_FILENAME,
    path_contract=(
        "implemented optional existing request file contained by the "
        "authoritative working copy; requires --output-dir when supplied; JSON "
        "content is not loaded during CLI argument validation"
    ),
)

EXECUTE_CLI_REFERENCE_TRAVERSAL_OUTPUT_SPEC = FileArgumentSpec(
    name="reference_traversal_output",
    boundary=FILE_ARGUMENT_BOUNDARY_EXECUTE_CLI,
    required=False,
    status=FILE_ARGUMENT_STATUS_IMPLEMENTED,
    role=FILE_ARGUMENT_ROLE_OUTPUT_PATH,
    cli_flag=None,
    invocation_field=None,
    canonical_filename=REFERENCE_TRAVERSAL_OUTPUT_FILENAME,
    path_contract=(
        "derived as the canonical filename beneath the existing --output-dir; "
        "the exact supplied working copy remains the authoritative containment "
        "root; not request-controlled; directories are caller-created"
    ),
)

# ---------------------------------------------------------------------------
# Engine execute invocation file argument specs
# ---------------------------------------------------------------------------

ENGINE_EXECUTE_WORKING_COPY_SPEC = FileArgumentSpec(
    name="working_copy",
    boundary=FILE_ARGUMENT_BOUNDARY_ENGINE_EXECUTE,
    required=True,
    status=FILE_ARGUMENT_STATUS_IMPLEMENTED,
    role=FILE_ARGUMENT_ROLE_CONTEXT_PATH,
    cli_flag=None,
    invocation_field="working_copy",
    canonical_filename=None,
    path_contract="context directory path for execute invocation",
)

ENGINE_EXECUTE_MANIFEST_PATH_SPEC = FileArgumentSpec(
    name="manifest_path",
    boundary=FILE_ARGUMENT_BOUNDARY_ENGINE_EXECUTE,
    required=True,
    status=FILE_ARGUMENT_STATUS_IMPLEMENTED,
    role=FILE_ARGUMENT_ROLE_INPUT_FILE,
    cli_flag=None,
    invocation_field="manifest_path",
    canonical_filename=EXPORT_MANIFEST_V1_FILENAME,
    path_contract="input manifest file path for execute invocation",
)

ENGINE_EXECUTE_RESULT_PATH_SPEC = FileArgumentSpec(
    name="result_path",
    boundary=FILE_ARGUMENT_BOUNDARY_ENGINE_EXECUTE,
    required=True,
    status=FILE_ARGUMENT_STATUS_IMPLEMENTED,
    role=FILE_ARGUMENT_ROLE_OUTPUT_PATH,
    cli_flag=None,
    invocation_field="result_path",
    canonical_filename=RESULT_JSON_FILENAME,
    path_contract="output result file path for execute invocation",
)

# ---------------------------------------------------------------------------
# Engine observe invocation file argument specs (implemented)
# ---------------------------------------------------------------------------

ENGINE_OBSERVE_WORKING_COPY_PATH_SPEC = FileArgumentSpec(
    name="working_copy_path",
    boundary=FILE_ARGUMENT_BOUNDARY_ENGINE_OBSERVE,
    required=True,
    status=FILE_ARGUMENT_STATUS_IMPLEMENTED,
    role=FILE_ARGUMENT_ROLE_CONTEXT_PATH,
    cli_flag=None,
    invocation_field="working_copy_path",
    canonical_filename=None,
    path_contract=(
        "caller-supplied context path metadata for observed payload generation; "
        "not validated or computed"
    ),
)

ENGINE_OBSERVE_OUTPUT_DIRECTORY_SPEC = FileArgumentSpec(
    name="output_directory",
    boundary=FILE_ARGUMENT_BOUNDARY_ENGINE_OBSERVE,
    required=True,
    status=FILE_ARGUMENT_STATUS_IMPLEMENTED,
    role=FILE_ARGUMENT_ROLE_OUTPUT_DIRECTORY,
    cli_flag=None,
    invocation_field="output_directory",
    canonical_filename=PARAMETRON_OBSERVED_FILENAME,
    path_contract=(
        "output directory for observed JSON writer; "
        "observed file written as "
        + PARAMETRON_OBSERVED_FILENAME
        + " within this directory"
    ),
)

# ---------------------------------------------------------------------------
# Engine observe invocation file argument specs (planned)
# ---------------------------------------------------------------------------

# Safe planned metadata: expresses the canonical verification input file contract
# without inventing an unsupported CLI surface — no cli_flag or invocation_field yet
ENGINE_OBSERVE_VERIFICATION_INPUT_SPEC = FileArgumentSpec(
    name="verification_input",
    boundary=FILE_ARGUMENT_BOUNDARY_ENGINE_OBSERVE,
    required=True,
    status=FILE_ARGUMENT_STATUS_PLANNED,
    role=FILE_ARGUMENT_ROLE_INPUT_FILE,
    cli_flag=None,
    invocation_field=None,
    canonical_filename=PARAMETRON_VERIFICATION_FILENAME,
    path_contract=(
        "planned input verification file for observe invocation; "
        "not yet supported at any boundary"
    ),
)

# ---------------------------------------------------------------------------
# Tuple groupings (exact immutable tuples)
# ---------------------------------------------------------------------------

EXECUTE_CLI_REQUIRED_FILE_ARGUMENT_SPECS: tuple[FileArgumentSpec, ...] = (
    EXECUTE_CLI_WORKING_COPY_SPEC,
    EXECUTE_CLI_MANIFEST_SPEC,
    EXECUTE_CLI_RESULT_SPEC,
)

ENGINE_EXECUTE_REQUIRED_FILE_ARGUMENT_SPECS: tuple[FileArgumentSpec, ...] = (
    ENGINE_EXECUTE_WORKING_COPY_SPEC,
    ENGINE_EXECUTE_MANIFEST_PATH_SPEC,
    ENGINE_EXECUTE_RESULT_PATH_SPEC,
)

ENGINE_OBSERVE_REQUIRED_FILE_ARGUMENT_SPECS: tuple[FileArgumentSpec, ...] = (
    ENGINE_OBSERVE_WORKING_COPY_PATH_SPEC,
    ENGINE_OBSERVE_OUTPUT_DIRECTORY_SPEC,
)

ALL_FILE_ARGUMENT_SPECS: tuple[FileArgumentSpec, ...] = (
    *EXECUTE_CLI_REQUIRED_FILE_ARGUMENT_SPECS,
    *ENGINE_EXECUTE_REQUIRED_FILE_ARGUMENT_SPECS,
    *ENGINE_OBSERVE_REQUIRED_FILE_ARGUMENT_SPECS,
    ENGINE_OBSERVE_VERIFICATION_INPUT_SPEC,
)

REQUIRED_FILE_ARGUMENT_SPECS: tuple[FileArgumentSpec, ...] = ALL_FILE_ARGUMENT_SPECS

IMPLEMENTED_REQUIRED_FILE_ARGUMENT_SPECS: tuple[FileArgumentSpec, ...] = (
    EXECUTE_CLI_WORKING_COPY_SPEC,
    EXECUTE_CLI_MANIFEST_SPEC,
    EXECUTE_CLI_RESULT_SPEC,
    ENGINE_EXECUTE_WORKING_COPY_SPEC,
    ENGINE_EXECUTE_MANIFEST_PATH_SPEC,
    ENGINE_EXECUTE_RESULT_PATH_SPEC,
    ENGINE_OBSERVE_WORKING_COPY_PATH_SPEC,
    ENGINE_OBSERVE_OUTPUT_DIRECTORY_SPEC,
)

PLANNED_REQUIRED_FILE_ARGUMENT_SPECS: tuple[FileArgumentSpec, ...] = (
    ENGINE_OBSERVE_VERIFICATION_INPUT_SPEC,
)

FILE_ARGUMENT_CANONICAL_NAMES: tuple[str, ...] = (
    EXPORT_MANIFEST_V1_FILENAME,
    RESULT_JSON_FILENAME,
    PARAMETRON_VERIFICATION_FILENAME,
    PARAMETRON_OBSERVED_FILENAME,
    REFERENCE_TRAVERSAL_REQUEST_FILENAME,
    REFERENCE_TRAVERSAL_OUTPUT_FILENAME,
)

# ---------------------------------------------------------------------------
# Canonical singleton
# ---------------------------------------------------------------------------

ENGINE_FILE_ARGUMENT_CONTRACT = EngineFileArgumentContract(
    version=FILE_ARGUMENT_CONTRACT_VERSION,
    file_arguments=ALL_FILE_ARGUMENT_SPECS,
    required_file_arguments=REQUIRED_FILE_ARGUMENT_SPECS,
    implemented_required_file_arguments=IMPLEMENTED_REQUIRED_FILE_ARGUMENT_SPECS,
    planned_required_file_arguments=PLANNED_REQUIRED_FILE_ARGUMENT_SPECS,
    execute_cli_required_file_arguments=EXECUTE_CLI_REQUIRED_FILE_ARGUMENT_SPECS,
    engine_execute_required_file_arguments=ENGINE_EXECUTE_REQUIRED_FILE_ARGUMENT_SPECS,
    engine_observe_required_file_arguments=ENGINE_OBSERVE_REQUIRED_FILE_ARGUMENT_SPECS,
    canonical_file_contract_names=FILE_ARGUMENT_CANONICAL_NAMES,
)


__all__ = [
    "ALL_FILE_ARGUMENT_SPECS",
    "ENGINE_EXECUTE_MANIFEST_PATH_SPEC",
    "ENGINE_EXECUTE_REQUIRED_FILE_ARGUMENT_SPECS",
    "ENGINE_EXECUTE_RESULT_PATH_SPEC",
    "ENGINE_EXECUTE_WORKING_COPY_SPEC",
    "ENGINE_FILE_ARGUMENT_CONTRACT",
    "ENGINE_OBSERVE_OUTPUT_DIRECTORY_SPEC",
    "ENGINE_OBSERVE_REQUIRED_FILE_ARGUMENT_SPECS",
    "ENGINE_OBSERVE_VERIFICATION_INPUT_SPEC",
    "ENGINE_OBSERVE_WORKING_COPY_PATH_SPEC",
    "EngineFileArgumentContract",
    "EXECUTE_CLI_MANIFEST_SPEC",
    "EXECUTE_CLI_REFERENCE_TRAVERSAL_OUTPUT_SPEC",
    "EXECUTE_CLI_REFERENCE_TRAVERSAL_REQUEST_SPEC",
    "EXECUTE_CLI_REQUIRED_FILE_ARGUMENT_SPECS",
    "EXECUTE_CLI_RESULT_SPEC",
    "EXECUTE_CLI_WORKING_COPY_SPEC",
    "FILE_ARGUMENT_BOUNDARY_ENGINE_EXECUTE",
    "FILE_ARGUMENT_BOUNDARY_ENGINE_OBSERVE",
    "FILE_ARGUMENT_BOUNDARY_EXECUTE_CLI",
    "FILE_ARGUMENT_CANONICAL_NAMES",
    "FILE_ARGUMENT_CONTRACT_VERSION",
    "FILE_ARGUMENT_ROLE_CONTEXT_PATH",
    "FILE_ARGUMENT_ROLE_INPUT_FILE",
    "FILE_ARGUMENT_ROLE_OUTPUT_DIRECTORY",
    "FILE_ARGUMENT_ROLE_OUTPUT_PATH",
    "FILE_ARGUMENT_STATUS_IMPLEMENTED",
    "FILE_ARGUMENT_STATUS_PLANNED",
    "FileArgumentSpec",
    "IMPLEMENTED_REQUIRED_FILE_ARGUMENT_SPECS",
    "PLANNED_REQUIRED_FILE_ARGUMENT_SPECS",
    "REQUIRED_FILE_ARGUMENT_SPECS",
    "RESULT_JSON_FILENAME",
    "REFERENCE_TRAVERSAL_OUTPUT_FILENAME",
    "REFERENCE_TRAVERSAL_REQUEST_CLI_FLAG",
    "REFERENCE_TRAVERSAL_REQUEST_FILENAME",
]
