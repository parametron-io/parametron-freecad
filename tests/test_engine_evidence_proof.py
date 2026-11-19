"""Opt-in cross-repository Engine evidence acceptance proof rehearsal."""

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
PROOF_SCRIPT = REPOSITORY_ROOT / "scripts" / "run_engine_evidence_proof.py"
ENGINE_REPO = Path(
    os.environ.get(
        "PARAMETRON_ENGINE_REPO", REPOSITORY_ROOT.parent / "parametron-engine"
    )
)

FIXTURE_ROOTS = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "assembly_occurrence",
    REPOSITORY_ROOT / "tests" / "fixtures" / "fact_evidence",
)


def _fixture_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(REPOSITORY_ROOT)): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for root in FIXTURE_ROOTS
        for path in sorted(root.rglob("*.FCStd"))
    }


def _require_enabled() -> None:
    if os.environ.get("PARAMETRON_RUN_ENGINE_EVIDENCE_PROOF") != "1":
        pytest.skip(
            "set PARAMETRON_RUN_ENGINE_EVIDENCE_PROOF=1 to run the Engine "
            "evidence acceptance proof"
        )
    if not (ENGINE_REPO / "scripts" / "cad_runtime_integration_proof.py").is_file():
        pytest.fail(f"parametron-engine checkout is unavailable: {ENGINE_REPO}")
    if shutil.which("nix") is None:
        pytest.fail("nix is required to run the Engine evidence acceptance proof")
    missing = [
        str(path.relative_to(REPOSITORY_ROOT))
        for root in FIXTURE_ROOTS
        for path in sorted(root.rglob("*.FCStd"))
        if not path.is_file()
    ]
    if missing:
        pytest.fail("FreeCAD fixture bundle is incomplete: " + ", ".join(missing))
    for root in FIXTURE_ROOTS:
        for path in sorted(root.rglob("*.FCStd")):
            if path.read_bytes().startswith(
                b"version https://git-lfs.github.com/spec/v1"
            ):
                pytest.fail("FreeCAD fixture bundle is not fetched from Git LFS")


def test_engine_accepts_real_freecad_evidence(tmp_path):
    _require_enabled()
    before = _fixture_hashes()
    workspace = tmp_path / "evidence-workspace"
    report = workspace / "proof-report.json"

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
        timeout=1200,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["status"] == "passed"
    assert summary["freecadVersion"] == "1.1.4"
    assert summary["host"] == "freecadcmd"
    assert summary["completeOccurrences"] == 10
    assert summary["quantity"] == 10
    assert summary["quantityTarget"] == "component_a/Body"
    assert summary["mixedCompleteness"] == "incomplete"
    assert summary["requiredFactStage"] == "fact_evidence"
    assert summary["baselineStage"] == "integrity_baseline"
    assert summary["multiOutcomeEvidenceFiles"] == 2
    assert summary["crossRepositoryBlocker"]["boundary"] == "freecad"
    assert summary["facts"] == {
        "observed": 7,
        "unavailable": 1,
        "unsupported": 2,
    }

    evidence_report = json.loads(report.read_text(encoding="utf-8"))
    assert evidence_report["status"] == "passed"
    real_evidence = evidence_report["realEvidence"]
    assert real_evidence["freecadVersion"][:3] == ["1", "1", "4"]
    assert real_evidence["crossRepositoryBlocker"]["boundary"] == "freecad"
    assert _fixture_hashes() == before
