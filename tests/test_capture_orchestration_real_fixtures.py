"""Permanent real-FreeCAD capture orchestration fixture tests.

These tests copy committed project fixtures to throwaway directories, run
``freecadcmd`` against the copied saved source, and prove end-to-end capture:
project context resolution, active-source verification, native discovery,
explicit decisions, both project-root outputs, atomic writes, determinism, and
unchanged source/project mapping.

Committed fixtures are never opened directly and never modified.
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
RUNNER = Path(__file__).parent / "freecad_capture_orchestration_fixture_runner.py"

CANONICAL_PROJECT = FIXTURE_ROOT / "canonical_lifecycle"
CANONICAL_MODEL = "cube_canonical_lifecycle_model"
METADATA_PROJECT = FIXTURE_ROOT / "metadata_mutation"
METADATA_MODEL = "metadata_coexistence_model"

LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freecad_host() -> str:
    configured = os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd")
    host = shutil.which(configured)
    if host is not None:
        return host
    message = f"FreeCAD host {configured!r} unavailable outside the Nix shell"
    if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
        pytest.fail(message)
    pytest.skip(message)


def _copy_project(fixture: Path, destination: Path) -> Path:
    shutil.copytree(fixture, destination)
    # Discard committed outputs so the run proves the create path.
    (destination / "prm.cad.json").unlink()
    (destination / "prm.semantic-map.json").unlink()
    return destination


def _run_orchestration(project: Path, logical_id: str, output_directory: Path) -> dict:
    script = next(path for path in project.rglob("*.FCStd") if path.is_file())
    assert not script.read_bytes().startswith(LFS_POINTER_PREFIX), (
        f"fixture must be fetched from Git LFS: {script}"
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    evidence_path = output_directory / "orchestration.json"
    completed = subprocess.run(
        [
            _freecad_host(),
            "-P",
            str(REPOSITORY_ROOT),
            str(RUNNER),
            f"--pass={project}",
            f"--pass={logical_id}",
            f"--pass={evidence_path}",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "Exception while processing file" not in completed.stderr, completed.stderr
    assert evidence_path.is_file(), completed.stderr + completed.stdout
    return json.loads(evidence_path.read_text(encoding="utf-8"))


def _load_outputs(project: Path) -> tuple[dict, dict, bytes, bytes]:
    capture_bytes = (project / "prm.cad.json").read_bytes()
    semantic_bytes = (project / "prm.semantic-map.json").read_bytes()
    capture = json.loads(capture_bytes)
    semantic = json.loads(semantic_bytes)
    return capture, semantic, capture_bytes, semantic_bytes


def test_cube_project_captures_end_to_end(tmp_path: Path) -> None:
    project = _copy_project(CANONICAL_PROJECT, tmp_path / "project")
    context = load_project_context(project)
    source = context.source_path(context.model(CANONICAL_MODEL))
    source_before = _sha256(source)
    mapping_before = _sha256(project / "prm.project.json")

    payload = _run_orchestration(project, CANONICAL_MODEL, tmp_path / "evidence")

    assert payload["source"]["unchanged"] is True
    assert payload["source"]["sha256"] == source_before
    assert payload["projectMapping"]["unchanged"] is True
    assert payload["plan"]["status"] == "create"
    assert payload["plan"]["requiresConfirmation"] is False
    assert payload["write"]["wroteCapture"] is True
    assert payload["write"]["wroteSemantic"] is True
    assert payload["repeatStatus"] == "unchanged"
    assert _sha256(source) == source_before
    assert _sha256(project / "prm.project.json") == mapping_before

    capture, semantic, _, _ = _load_outputs(project)
    CaptureDocument.from_mapping(capture)
    validate_capture_document(capture)
    validate_semantic_map(semantic)

    assert capture["sourceDocument"]["logicalId"] == CANONICAL_MODEL
    assert capture["sourceDocument"]["path"] == "input/cube.FCStd"
    assert capture["sourceDocument"]["fingerprint"].startswith("sha256:")
    assert capture["rootProduct"]["id"] == "cmp.cube"
    assert "/home/" not in json.dumps(capture, sort_keys=True)

    counts = payload["counts"]
    assert counts["components"] == 5
    assert counts["features"] == 16
    assert counts["parameterGroups"] == 1
    assert counts["parameters"] == 5


def test_metadata_project_selects_only_supported_metadata(tmp_path: Path) -> None:
    project = _copy_project(METADATA_PROJECT, tmp_path / "project")
    context = load_project_context(project)
    source = context.source_path(context.model(METADATA_MODEL))
    source_before = _sha256(source)

    payload = _run_orchestration(project, METADATA_MODEL, tmp_path / "evidence")

    assert payload["source"]["unchanged"] is True
    assert _sha256(source) == source_before
    assert payload["plan"]["status"] == "create"
    assert payload["repeatStatus"] == "unchanged"

    capture, semantic, _, _ = _load_outputs(project)
    validate_capture_document(capture)
    validate_semantic_map(semantic)

    metadata_keys = {item["key"] for item in capture["entities"]["metadata"]}
    assert metadata_keys == {
        "mass",
        "material",
        "revision",
        "sequence",
        "tagged",
        "tolerance",
    }
    assert "measured_length" not in metadata_keys
    assert payload["counts"]["selectedMetadata"] == 6


def test_repeated_capture_is_byte_identical(tmp_path: Path) -> None:
    first_project = _copy_project(CANONICAL_PROJECT, tmp_path / "first")
    second_project = _copy_project(CANONICAL_PROJECT, tmp_path / "second")

    _run_orchestration(first_project, CANONICAL_MODEL, tmp_path / "first-evidence")
    _run_orchestration(second_project, CANONICAL_MODEL, tmp_path / "second-evidence")

    _, _, first_capture, first_semantic = _load_outputs(first_project)
    _, _, second_capture, second_semantic = _load_outputs(second_project)

    assert first_capture == second_capture
    assert first_semantic == second_semantic
