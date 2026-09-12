"""Engine-to-FreeCAD required output-file contract metadata."""

from __future__ import annotations

from dataclasses import dataclass

from parametron_freecad.execution.manifest_contract import SUPPORTED_OUTPUT_FORMATS
from parametron_freecad.observation.observed_contract import (
    PARAMETRON_OBSERVED_FILENAME,
)
from parametron_freecad.runtime.file_argument_contract import RESULT_JSON_FILENAME

OUTPUT_FILE_CONTRACT_VERSION = "1.0"

# Semantic role constants - use these exact strings to avoid drift
OUTPUT_FILE_ROLE_RUNNER_RESULT = "runner_result"
OUTPUT_FILE_ROLE_DECLARED_ARTIFACT = "declared_artifact"
OUTPUT_FILE_ROLE_OBSERVED_OUTPUT = "observed_output"

# Boundary constants - use these exact strings to avoid drift
OUTPUT_FILE_BOUNDARY_EXECUTE = "execute"
OUTPUT_FILE_BOUNDARY_OBSERVE = "observe"

# Status constants - use these exact strings to avoid drift
OUTPUT_FILE_STATUS_IMPLEMENTED = "implemented"
OUTPUT_FILE_STATUS_PLANNED = "planned"

# Cardinality constants - use these exact strings to avoid drift
OUTPUT_FILE_CARDINALITY_ONE = "one"
OUTPUT_FILE_CARDINALITY_PER_MANIFEST_OUTPUT = "per_manifest_output"


@dataclass(frozen=True, slots=True)
class OutputFileSpec:
    """Immutable metadata for one required output file at a runtime boundary."""

    name: str
    boundary: str
    required: bool
    status: str
    role: str
    canonical_filename: str | None
    path_source: str
    cardinality: str
    payload_contract: str
    write_contract: str


@dataclass(frozen=True, slots=True)
class EngineOutputFileContract:
    """Engine-to-FreeCAD required output-file contract metadata."""

    version: str
    output_files: tuple[OutputFileSpec, ...]
    required_output_files: tuple[OutputFileSpec, ...]
    implemented_required_output_files: tuple[OutputFileSpec, ...]
    planned_required_output_files: tuple[OutputFileSpec, ...]
    execute_required_output_files: tuple[OutputFileSpec, ...]
    observe_required_output_files: tuple[OutputFileSpec, ...]
    canonical_output_filenames: tuple[str, ...]
    declared_artifact_formats: tuple[str, ...]


# ---------------------------------------------------------------------------
# Execute output specs
# ---------------------------------------------------------------------------

EXECUTE_RESULT_JSON_OUTPUT_SPEC = OutputFileSpec(
    name="result_json",
    boundary=OUTPUT_FILE_BOUNDARY_EXECUTE,
    required=True,
    status=OUTPUT_FILE_STATUS_IMPLEMENTED,
    role=OUTPUT_FILE_ROLE_RUNNER_RESULT,
    canonical_filename=RESULT_JSON_FILENAME,
    path_source=(
        "execute CLI --result path and Engine ExecutionInvocation.result_path"
    ),
    cardinality=OUTPUT_FILE_CARDINALITY_ONE,
    payload_contract=(
        'canonical JSON with schemaVersion "1.0", status "succeeded", and '
        "an artifacts array preserving manifest output declaration order"
    ),
    write_contract=(
        "written after successful execute completion only; not written during "
        "argument validation; not written on execute failure"
    ),
)

EXECUTE_DECLARED_ARTIFACTS_OUTPUT_SPEC = OutputFileSpec(
    name="declared_artifacts",
    boundary=OUTPUT_FILE_BOUNDARY_EXECUTE,
    required=True,
    status=OUTPUT_FILE_STATUS_IMPLEMENTED,
    role=OUTPUT_FILE_ROLE_DECLARED_ARTIFACT,
    canonical_filename=None,
    path_source="manifest outputs[].path resolved inside the working copy",
    cardinality=OUTPUT_FILE_CARDINALITY_PER_MANIFEST_OUTPUT,
    payload_contract=(
        "manifest-declared artifacts for supported output formats "
        + ", ".join(SUPPORTED_OUTPUT_FORMATS)
    ),
    write_contract=(
        "artifacts are produced for declared manifest outputs through existing "
        "exporter paths; output order follows manifest declaration order; export "
        "failure remains execute failure and prevents success result writing"
    ),
)

# ---------------------------------------------------------------------------
# Observe output specs
# ---------------------------------------------------------------------------

OBSERVE_PARAMETRON_OBSERVED_JSON_OUTPUT_SPEC = OutputFileSpec(
    name="parametron_observed_json",
    boundary=OUTPUT_FILE_BOUNDARY_OBSERVE,
    required=True,
    status=OUTPUT_FILE_STATUS_IMPLEMENTED,
    role=OUTPUT_FILE_ROLE_OBSERVED_OUTPUT,
    canonical_filename=PARAMETRON_OBSERVED_FILENAME,
    path_source="output_directory / " + PARAMETRON_OBSERVED_FILENAME,
    cardinality=OUTPUT_FILE_CARDINALITY_ONE,
    payload_contract=(
        'canonical JSON with schemaVersion "1.0" and top-level workingCopy '
        "and observation payload"
    ),
    write_contract=(
        "written by the existing observation helper/writer path for injected "
        "document state and already-decoded verification data; no CLI observation "
        "mode is implied; no verification decisions are written"
    ),
)

# ---------------------------------------------------------------------------
# Tuple groupings (exact immutable tuples)
# ---------------------------------------------------------------------------

EXECUTE_REQUIRED_OUTPUT_FILE_SPECS: tuple[OutputFileSpec, ...] = (
    EXECUTE_RESULT_JSON_OUTPUT_SPEC,
    EXECUTE_DECLARED_ARTIFACTS_OUTPUT_SPEC,
)

OBSERVE_REQUIRED_OUTPUT_FILE_SPECS: tuple[OutputFileSpec, ...] = (
    OBSERVE_PARAMETRON_OBSERVED_JSON_OUTPUT_SPEC,
)

ALL_OUTPUT_FILE_SPECS: tuple[OutputFileSpec, ...] = (
    *EXECUTE_REQUIRED_OUTPUT_FILE_SPECS,
    *OBSERVE_REQUIRED_OUTPUT_FILE_SPECS,
)

REQUIRED_OUTPUT_FILE_SPECS: tuple[OutputFileSpec, ...] = ALL_OUTPUT_FILE_SPECS
IMPLEMENTED_REQUIRED_OUTPUT_FILE_SPECS = ALL_OUTPUT_FILE_SPECS
PLANNED_REQUIRED_OUTPUT_FILE_SPECS: tuple[OutputFileSpec, ...] = ()

OUTPUT_FILE_CANONICAL_NAMES: tuple[str, ...] = (
    RESULT_JSON_FILENAME,
    PARAMETRON_OBSERVED_FILENAME,
)

DECLARED_ARTIFACT_OUTPUT_FORMATS: tuple[str, ...] = SUPPORTED_OUTPUT_FORMATS

# ---------------------------------------------------------------------------
# Canonical singleton
# ---------------------------------------------------------------------------

ENGINE_OUTPUT_FILE_CONTRACT = EngineOutputFileContract(
    version=OUTPUT_FILE_CONTRACT_VERSION,
    output_files=ALL_OUTPUT_FILE_SPECS,
    required_output_files=REQUIRED_OUTPUT_FILE_SPECS,
    implemented_required_output_files=IMPLEMENTED_REQUIRED_OUTPUT_FILE_SPECS,
    planned_required_output_files=PLANNED_REQUIRED_OUTPUT_FILE_SPECS,
    execute_required_output_files=EXECUTE_REQUIRED_OUTPUT_FILE_SPECS,
    observe_required_output_files=OBSERVE_REQUIRED_OUTPUT_FILE_SPECS,
    canonical_output_filenames=OUTPUT_FILE_CANONICAL_NAMES,
    declared_artifact_formats=DECLARED_ARTIFACT_OUTPUT_FORMATS,
)


__all__ = [
    "ALL_OUTPUT_FILE_SPECS",
    "DECLARED_ARTIFACT_OUTPUT_FORMATS",
    "ENGINE_OUTPUT_FILE_CONTRACT",
    "EXECUTE_DECLARED_ARTIFACTS_OUTPUT_SPEC",
    "EXECUTE_REQUIRED_OUTPUT_FILE_SPECS",
    "EXECUTE_RESULT_JSON_OUTPUT_SPEC",
    "EngineOutputFileContract",
    "IMPLEMENTED_REQUIRED_OUTPUT_FILE_SPECS",
    "OBSERVE_PARAMETRON_OBSERVED_JSON_OUTPUT_SPEC",
    "OBSERVE_REQUIRED_OUTPUT_FILE_SPECS",
    "OUTPUT_FILE_BOUNDARY_EXECUTE",
    "OUTPUT_FILE_BOUNDARY_OBSERVE",
    "OUTPUT_FILE_CANONICAL_NAMES",
    "OUTPUT_FILE_CARDINALITY_ONE",
    "OUTPUT_FILE_CARDINALITY_PER_MANIFEST_OUTPUT",
    "OUTPUT_FILE_CONTRACT_VERSION",
    "OUTPUT_FILE_ROLE_DECLARED_ARTIFACT",
    "OUTPUT_FILE_ROLE_OBSERVED_OUTPUT",
    "OUTPUT_FILE_ROLE_RUNNER_RESULT",
    "OUTPUT_FILE_STATUS_IMPLEMENTED",
    "OUTPUT_FILE_STATUS_PLANNED",
    "OutputFileSpec",
    "PLANNED_REQUIRED_OUTPUT_FILE_SPECS",
    "REQUIRED_OUTPUT_FILE_SPECS",
]
