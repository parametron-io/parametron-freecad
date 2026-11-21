"""Opt-in cross-repository Engine acceptance proof for metadata evidence."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROOF_SCRIPT = REPOSITORY_ROOT / "scripts" / "run_metadata_engine_acceptance_proof.py"
ENGINE_REPO = Path(
    os.environ.get(
        "PARAMETRON_ENGINE_REPO",
        REPOSITORY_ROOT.parent / "parametron-engine",
    )
)
PROOF_GATE_ENV = "PARAMETRON_RUN_METADATA_ENGINE_ACCEPTANCE_PROOF"

FIXTURE_SHA256 = "b6a09b7f7092db0efb594026e8e6dc3eb5fff49fa78582851e2961e0e15910c0"
MANIFEST_SHA256 = "4f588142c08397990349089dca6b9a27ca5ff1956c4b916473840a0de88c2fdd"
VERIFICATION_SHA256 = "a36e5c6b6cb35ff8a8e18a0ce1a4f58f379a2db2df7bd8a34e2e8df63fef351e"

FIXTURE_DIR = REPOSITORY_ROOT / "tests" / "fixtures" / "metadata_mutation"
REQUIRED_FILES = (
    FIXTURE_DIR / "prm.project.json",
    FIXTURE_DIR / "prm.cad.json",
    FIXTURE_DIR / "prm.semantic-map.json",
    FIXTURE_DIR / "metadata.project.dsl",
    FIXTURE_DIR / "prm.export-manifest.json",
    FIXTURE_DIR / "prm.verification.json",
    FIXTURE_DIR / "input" / "metadata-coexistence.FCStd",
)

EXPECTED_CATEGORIES = {
    "components": "skipped",
    "metadata": "pass",
    "parameters": "pass",
    "references": "pass",
    "target_state": "pass",
}

EXPECTED_METADATA_IDS = [
    "meta.enclosure.mass",
    "meta.enclosure.material",
    "meta.enclosure.revision",
    "meta.enclosure.sequence",
    "meta.enclosure.tagged",
    "meta.enclosure.tolerance",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(REPOSITORY_ROOT)): _sha256(path) for path in REQUIRED_FILES
    }


def _require_enabled() -> None:
    if os.environ.get(PROOF_GATE_ENV) != "1":
        pytest.skip(
            f"set {PROOF_GATE_ENV}=1 to run the metadata Engine acceptance proof"
        )
    if not (ENGINE_REPO / "cmd" / "parametron").is_dir():
        pytest.fail(f"parametron-engine checkout is unavailable: {ENGINE_REPO}")
    if shutil.which("nix") is None:
        pytest.fail("nix is required to run the metadata Engine acceptance proof")
    if shutil.which("parametron-freecad") is None:
        pytest.fail("the parametron-freecad launcher is unavailable")
    missing = [str(path) for path in REQUIRED_FILES if not path.is_file()]
    if missing:
        pytest.fail("metadata fixture bundle is incomplete: " + ", ".join(missing))
    for path in REQUIRED_FILES:
        if path.read_bytes().startswith(b"version https://git-lfs.github.com/spec/v1"):
            pytest.fail(f"fixture is not fetched from Git LFS: {path}")
    fixture = FIXTURE_DIR / "input" / "metadata-coexistence.FCStd"
    assert _sha256(fixture) == FIXTURE_SHA256
    assert _sha256(FIXTURE_DIR / "prm.export-manifest.json") == MANIFEST_SHA256
    assert _sha256(FIXTURE_DIR / "prm.verification.json") == VERIFICATION_SHA256


def test_engine_accepts_real_freecad_metadata_evidence(tmp_path):
    _require_enabled()
    before = _fixture_hashes()
    workspace = tmp_path / "metadata-workspace"
    report = workspace / "metadata-proof-report.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(PROOF_SCRIPT),
            "--engine-repo",
            str(ENGINE_REPO),
            "--workspace",
            str(workspace),
            "--report",
            str(report),
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["status"] == "passed"
    assert summary["freecadVersion"] == "1.1.4"
    assert summary["metadataVerified"] == 7
    assert summary["authoredMetadataIds"] == EXPECTED_METADATA_IDS
    assert summary["parameterValue"] == 12.5
    assert summary["categories"] == EXPECTED_CATEGORIES
    assert summary["sourceDigest"] == FIXTURE_SHA256
    assert len(summary["engineRevision"]) == 40
    assert Path(summary["runRoot"]).is_dir()
    assert summary["persistedResultDigest"]

    report_data = json.loads(report.read_text(encoding="utf-8"))
    assert report_data == summary
    assert _fixture_hashes() == before
