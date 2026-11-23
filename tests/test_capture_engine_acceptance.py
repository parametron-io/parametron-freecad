"""Opt-in proof that production capture is consumed by the Engine CLI.

The proof is disabled by default because it depends on an external Engine
checkout and a Go toolchain. Enable it with:

    PARAMETRON_ENGINE_ACCEPTANCE=1 python -m pytest -q \
        tests/test_capture_engine_acceptance.py

The Engine repository is discovered from ``PARAMETRON_ENGINE_REPO`` or the
sibling ``parametron-engine`` checkout. A prebuilt CLI can be supplied with
``PARAMETRON_ENGINE_BIN``; otherwise the CLI is built once into a temporary
directory with ``go build ./cmd/parametron``.

Committed fixtures are copied to throwaway directories and never modified.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from parametron_freecad.capture import (
    CaptureDocument,
    load_project_context,
    validate_capture_document,
    validate_semantic_map,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).parent / "fixtures"
RUNNER = Path(__file__).parent / "freecad_capture_engine_acceptance_runner.py"

CANONICAL_PROJECT = FIXTURE_ROOT / "canonical_lifecycle"
CANONICAL_MODEL = "cube_canonical_lifecycle_model"
METADATA_PROJECT = FIXTURE_ROOT / "metadata_mutation"
METADATA_MODEL = "metadata_coexistence_model"

LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"

pytestmark = pytest.mark.skipif(
    os.environ.get("PARAMETRON_ENGINE_ACCEPTANCE") != "1",
    reason="set PARAMETRON_ENGINE_ACCEPTANCE=1 to run the Engine acceptance proof",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freecad_host() -> str:
    configured = os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd")
    host = shutil.which(configured)
    if host is None:
        pytest.skip(f"FreeCAD host {configured!r} unavailable outside the Nix shell")
    return host


def _engine_repo() -> Path | None:
    configured = os.environ.get("PARAMETRON_ENGINE_REPO")
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(REPOSITORY_ROOT.parent / "parametron-engine")
    for candidate in candidates:
        if (candidate / "go.mod").is_file() and (
            candidate / "cmd" / "parametron"
        ).is_dir():
            return candidate
    return None


@pytest.fixture(scope="session")
def engine_binary(tmp_path_factory: pytest.TempPathFactory) -> Path:
    configured = os.environ.get("PARAMETRON_ENGINE_BIN")
    if configured:
        binary = Path(configured)
        if not binary.is_file():
            pytest.fail(f"PARAMETRON_ENGINE_BIN does not exist: {binary}")
        return binary

    repository = _engine_repo()
    if repository is None:
        pytest.skip(
            "Engine checkout not found; set PARAMETRON_ENGINE_REPO or "
            "PARAMETRON_ENGINE_BIN"
        )
    go = shutil.which("go")
    if go is None:
        pytest.skip("Go toolchain unavailable to build the Engine CLI")

    output_directory = tmp_path_factory.mktemp("engine")
    binary = output_directory / "parametron"
    completed = subprocess.run(
        [go, "build", "-o", str(binary), "./cmd/parametron"],
        cwd=str(repository),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if completed.returncode != 0:
        pytest.fail("Engine CLI build failed:\n" + completed.stderr + completed.stdout)
    return binary


def _copy_project(fixture: Path, destination: Path) -> Path:
    shutil.copytree(fixture, destination)
    (destination / "prm.cad.json").unlink()
    (destination / "prm.semantic-map.json").unlink()
    return destination


def _run_capture(
    project: Path,
    logical_id: str,
    committed_cad: Path,
    committed_map: Path,
    evidence_directory: Path,
) -> dict:
    source = next(path for path in project.rglob("*.FCStd") if path.is_file())
    assert not source.read_bytes().startswith(LFS_POINTER_PREFIX), (
        f"fixture must be fetched from Git LFS: {source}"
    )
    evidence_directory.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_directory / "acceptance.json"
    completed = subprocess.run(
        [
            _freecad_host(),
            "-P",
            str(REPOSITORY_ROOT),
            str(RUNNER),
            f"--pass={project}",
            f"--pass={logical_id}",
            f"--pass={committed_cad}",
            f"--pass={committed_map}",
            f"--pass={evidence_path}",
        ],
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "Exception while processing file" not in completed.stderr, completed.stderr
    assert evidence_path.is_file(), completed.stderr + completed.stdout
    return json.loads(evidence_path.read_text(encoding="utf-8"))


def _engine_validate(binary: Path, project: Path) -> None:
    completed = subprocess.run(
        [str(binary), "validate", "--project", str(project)],
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "Validation succeeded" in completed.stdout, (
        completed.stderr + completed.stdout
    )


def _assert_positive_evidence(payload: dict) -> None:
    assert payload["source"]["unchanged"] is True
    assert payload["projectMapping"]["unchanged"] is True
    assert payload["plan"]["status"] == "create"
    assert payload["plan"]["requiresConfirmation"] is False
    assert payload["write"]["wroteCapture"] is True
    assert payload["write"]["wroteSemantic"] is True
    assert payload["repeatStatus"] == "unchanged"


def _assert_negative_evidence(payload: dict, *, unsupported_metadata: bool) -> None:
    negatives = payload["negativeCases"]
    assert negatives["name_collision"] == "CaptureNamePolicyError"
    assert negatives["missing_parent_capture"] == "CaptureDecisionError"
    assert negatives["stale_native_selector"] == "CaptureDriftError"
    if unsupported_metadata:
        assert negatives["unsupported_metadata_type"] == "CaptureDecisionError"
    else:
        assert negatives["unsupported_metadata_type"] == "not_applicable"


def _load_outputs(project: Path) -> tuple[dict, dict, bytes, bytes]:
    capture_bytes = (project / "prm.cad.json").read_bytes()
    semantic_bytes = (project / "prm.semantic-map.json").read_bytes()
    return (
        json.loads(capture_bytes),
        json.loads(semantic_bytes),
        capture_bytes,
        semantic_bytes,
    )


def _committed_ids(capture: dict) -> dict[str, set[str]]:
    entities = capture["entities"]
    return {
        "components": {item["id"] for item in entities["components"]},
        "features": {item["id"] for item in entities["features"]},
        "parameterGroups": {item["id"] for item in entities["parameterGroups"]},
        "parameters": {item["id"] for item in entities["parameters"]},
        "metadata": {item["id"] for item in entities["metadata"]},
    }


def test_canonical_capture_is_accepted_by_engine(
    engine_binary: Path, tmp_path: Path
) -> None:
    project = _copy_project(CANONICAL_PROJECT, tmp_path / "project")
    context = load_project_context(project)
    source = context.source_path(context.model(CANONICAL_MODEL))
    source_before = _sha256(source)
    mapping_before = _sha256(project / "prm.project.json")

    payload = _run_capture(
        project,
        CANONICAL_MODEL,
        CANONICAL_PROJECT / "prm.cad.json",
        CANONICAL_PROJECT / "prm.semantic-map.json",
        tmp_path / "evidence",
    )
    _assert_positive_evidence(payload)
    _assert_negative_evidence(payload, unsupported_metadata=False)
    assert _sha256(source) == source_before
    assert _sha256(project / "prm.project.json") == mapping_before

    capture, semantic, _, _ = _load_outputs(project)
    CaptureDocument.from_mapping(capture)
    validate_capture_document(capture)
    validate_semantic_map(semantic)
    assert "/home/" not in json.dumps(capture, sort_keys=True)

    committed = json.loads((CANONICAL_PROJECT / "prm.cad.json").read_text())
    assert capture["captureId"] == committed["captureId"]
    assert _committed_ids(capture) == _committed_ids(committed)

    _engine_validate(engine_binary, project)


def test_metadata_capture_is_accepted_by_engine(
    engine_binary: Path, tmp_path: Path
) -> None:
    project = _copy_project(METADATA_PROJECT, tmp_path / "project")
    context = load_project_context(project)
    source = context.source_path(context.model(METADATA_MODEL))
    source_before = _sha256(source)
    mapping_before = _sha256(project / "prm.project.json")

    payload = _run_capture(
        project,
        METADATA_MODEL,
        METADATA_PROJECT / "prm.cad.json",
        METADATA_PROJECT / "prm.semantic-map.json",
        tmp_path / "evidence",
    )
    _assert_positive_evidence(payload)
    _assert_negative_evidence(payload, unsupported_metadata=True)
    assert _sha256(source) == source_before
    assert _sha256(project / "prm.project.json") == mapping_before

    capture, semantic, _, _ = _load_outputs(project)
    validate_capture_document(capture)
    validate_semantic_map(semantic)
    assert "measured_length" not in {
        item["key"] for item in capture["entities"]["metadata"]
    }

    committed = json.loads((METADATA_PROJECT / "prm.cad.json").read_text())
    assert capture["captureId"] == committed["captureId"]
    assert _committed_ids(capture) == _committed_ids(committed)

    _engine_validate(engine_binary, project)


def test_repeated_capture_is_semantically_deterministic(tmp_path: Path) -> None:
    first_project = _copy_project(CANONICAL_PROJECT, tmp_path / "first")
    second_project = _copy_project(CANONICAL_PROJECT, tmp_path / "second")

    first = _run_capture(
        first_project,
        CANONICAL_MODEL,
        CANONICAL_PROJECT / "prm.cad.json",
        CANONICAL_PROJECT / "prm.semantic-map.json",
        tmp_path / "first-evidence",
    )
    second = _run_capture(
        second_project,
        CANONICAL_MODEL,
        CANONICAL_PROJECT / "prm.cad.json",
        CANONICAL_PROJECT / "prm.semantic-map.json",
        tmp_path / "second-evidence",
    )

    _, _, first_capture_bytes, first_semantic_bytes = _load_outputs(first_project)
    _, _, second_capture_bytes, second_semantic_bytes = _load_outputs(second_project)

    assert first_capture_bytes == second_capture_bytes
    assert first_semantic_bytes == second_semantic_bytes
    assert first["outputs"]["captureSha256"] == second["outputs"]["captureSha256"]
    assert first["outputs"]["semanticSha256"] == second["outputs"]["semanticSha256"]

    first_identity = json.loads(first_capture_bytes)["captureId"]
    second_identity = json.loads(second_capture_bytes)["captureId"]
    assert first_identity == second_identity
