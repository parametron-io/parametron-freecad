#!/usr/bin/env python3
"""Run the Engine-owned real-FreeCAD evidence acceptance proof.

This repository owns the FreeCAD fixtures and the production launcher. Engine
owns request composition, strict evidence intake, normalization, quantity
rollup, integrity provenance, and record-package emission. This harness only
delegates to the Engine proof and verifies its recorded acceptance result.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENGINE_REPO = REPOSITORY_ROOT.parent / "parametron-engine"
ENGINE_PROOF_SCRIPT = Path("scripts") / "cad_runtime_integration_proof.py"

REQUIRED_SCENARIOS = (
    "executor_facts_and_integrity",
    "executor_required_unavailable_fact",
    "executor_multi_outcome",
    "executor_occurrence_materialization_blocker",
    "fixture_complete_scope",
    "fixture_mixed_scope",
    "fixture_baseline_mismatch",
)

FIXTURE_REQUIRED_FILES = (
    "tests/fixtures/assembly_occurrence/assembly-root.FCStd",
    "tests/fixtures/assembly_occurrence/resources/component-a.FCStd",
    "tests/fixtures/assembly_occurrence/resources/component-b.FCStd",
    "tests/fixtures/assembly_occurrence/resources/nested-assembly.FCStd",
    "tests/fixtures/fact_evidence/fact-source.FCStd",
    "tests/fixtures/fact_evidence/resources/secondary.FCStd",
)


class ProofError(RuntimeError):
    """Raised when the delegated Engine proof cannot establish acceptance."""


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Engine-owned real-FreeCAD occurrence, fact, and integrity "
            "acceptance proof against this FreeCAD checkout."
        )
    )
    parser.add_argument(
        "--engine-repo",
        type=Path,
        default=DEFAULT_ENGINE_REPO,
        help="Sibling parametron-engine checkout (default: ../parametron-engine)",
    )
    parser.add_argument(
        "--freecad-repo",
        type=Path,
        default=REPOSITORY_ROOT,
        help="FreeCAD adapter checkout (default: this repository)",
    )
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--keep-workspace", action="store_true")
    return parser.parse_args(argv)


def _require_inputs(
    *,
    engine_repo: Path,
    freecad_repo: Path,
) -> Path:
    proof_script = engine_repo / ENGINE_PROOF_SCRIPT
    if not proof_script.is_file():
        raise ProofError(f"Engine proof script is unavailable: {proof_script}")
    if shutil.which("nix") is None:
        raise ProofError("nix is required to run the Engine evidence proof")
    missing = [
        relative
        for relative in FIXTURE_REQUIRED_FILES
        if not (freecad_repo / relative).is_file()
    ]
    if missing:
        raise ProofError("FreeCAD fixture bundle is incomplete: " + ", ".join(missing))
    return proof_script


def _run_engine_proof(
    *,
    proof_script: Path,
    engine_repo: Path,
    freecad_repo: Path,
    workspace: Path,
    report: Path,
    timeout: int,
    keep_workspace: bool,
) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(proof_script),
        "--mode",
        "evidence-real",
        "--freecad-repo",
        str(freecad_repo),
        "--workspace",
        str(workspace),
        "--report",
        str(report),
        "--timeout",
        str(timeout),
    ]
    if keep_workspace:
        command.append("--keep-workspace")
    try:
        completed = subprocess.run(
            command,
            cwd=engine_repo,
            capture_output=True,
            text=True,
            timeout=timeout + 180,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProofError(
            f"Engine evidence proof timed out after {timeout + 180}s"
        ) from exc
    if completed.returncode != 0:
        raise ProofError(
            "Engine evidence proof failed\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def _load_report(report: Path) -> dict[str, Any]:
    try:
        decoded = json.loads(report.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProofError(
            f"Engine evidence proof report is unavailable: {report}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ProofError(
            f"Engine evidence proof report is not valid JSON: {report}"
        ) from exc
    if not isinstance(decoded, dict):
        raise ProofError("Engine evidence proof report root must be an object")
    return decoded


def _scenario_facts(
    real_evidence: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    scenarios = real_evidence.get("scenarios")
    if not isinstance(scenarios, list):
        raise ProofError("Engine evidence proof report has no scenario list")
    scenarios_by_name: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise ProofError("Engine evidence proof scenario is not an object")
        name = scenario.get("name")
        facts = scenario.get("facts")
        if not isinstance(name, str) or not isinstance(facts, dict):
            raise ProofError("Engine evidence proof scenario is malformed")
        if name in scenarios_by_name:
            raise ProofError(f"Engine evidence proof repeats scenario {name!r}")
        scenarios_by_name[name] = scenario
    missing = [name for name in REQUIRED_SCENARIOS if name not in scenarios_by_name]
    if missing:
        raise ProofError(
            "Engine evidence proof is missing scenarios: " + ", ".join(missing)
        )
    return scenarios_by_name


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProofError(message)


def _validate_report(report: dict[str, Any]) -> dict[str, Any]:
    _require(report.get("status") == "passed", "Engine evidence proof did not pass")
    real_evidence = report.get("realEvidence")
    _require(
        isinstance(real_evidence, dict), "Engine evidence proof has no realEvidence"
    )
    version = real_evidence.get("freecadVersion")
    _require(
        isinstance(version, list) and version[:3] == ["1", "1", "4"],
        f"Engine evidence proof did not run on FreeCAD 1.1.4: {version!r}",
    )
    _require(
        real_evidence.get("host") == "freecadcmd",
        "Engine evidence proof did not use the freecadcmd host",
    )
    scenarios = _scenario_facts(real_evidence)
    for name in REQUIRED_SCENARIOS:
        scenario = scenarios[name]
        _require(
            scenario.get("status") == "passed",
            f"scenario {name!r} did not pass",
        )
        _require(
            isinstance(scenario.get("enginePath"), str)
            and bool(scenario.get("enginePath")),
            f"scenario {name!r} has no Engine path",
        )
    facts = {name: scenarios[name]["facts"] for name in REQUIRED_SCENARIOS}

    complete = facts["fixture_complete_scope"]
    _require(
        complete.get("occurrences") == 10,
        "complete scope did not accept ten occurrences",
    )
    _require(
        complete.get("quantity") == 10, "complete scope did not roll up quantity ten"
    )
    _require(
        complete.get("quantityTarget") == "component_a/Body",
        "complete scope quantity target drifted",
    )

    mixed = facts["fixture_mixed_scope"]
    _require(
        mixed.get("completeness") == "incomplete",
        "mixed scope was not explicitly incomplete",
    )
    _require(
        mixed.get("quantities") is None, "mixed scope unexpectedly produced quantity"
    )
    _require(
        mixed.get("duplicateNativeName") == "Body",
        "mixed scope lost duplicate native-name separation",
    )
    _require(
        mixed.get("sharedTarget") == "component_a/Body",
        "mixed scope lost the shared target",
    )

    facts_evidence = facts["executor_facts_and_integrity"]
    _require(
        facts_evidence.get("observedCount") == 7,
        "fact proof did not observe the expected bound facts",
    )
    _require(
        facts_evidence.get("unavailableCount") == 1,
        "fact proof did not preserve one unavailable fact",
    )
    _require(
        facts_evidence.get("unsupportedCount") == 2,
        "fact proof did not preserve two unsupported facts",
    )
    _require(
        facts_evidence.get("integrityResources") == 2,
        "fact proof did not evaluate both declared resources",
    )

    required = facts["executor_required_unavailable_fact"]
    _require(
        required.get("stage") == "fact_evidence",
        "required unavailable fact did not fail at fact_evidence",
    )

    baseline = facts["fixture_baseline_mismatch"]
    _require(
        baseline.get("stage") == "integrity_baseline",
        "baseline mismatch did not fail at integrity_baseline",
    )
    _require(
        baseline.get("sourceUnchanged") is True,
        "baseline mismatch mutated the source fixture",
    )

    blocker_scope = facts["executor_occurrence_materialization_blocker"]
    _require(
        blocker_scope.get("completeness") == "incomplete",
        "executor-layout blocker was not explicit",
    )
    _require(
        blocker_scope.get("acceptedOccurrences") == 0,
        "executor-layout blocker unexpectedly accepted occurrences",
    )

    multi = facts["executor_multi_outcome"]
    _require(
        multi.get("outcomeScopedRaw") == 2,
        "multi-outcome proof did not retain two evidence files",
    )
    _require(
        multi.get("distinctRawEvidence") is True,
        "multi-outcome proof aggregated distinct evidence",
    )

    blocker = real_evidence.get("crossRepositoryBlocker")
    _require(
        isinstance(blocker, dict) and blocker.get("boundary") == "freecad",
        "Engine evidence proof lost the documented FreeCAD blocker",
    )

    return {
        "status": "passed",
        "freecadVersion": ".".join(version[:3]),
        "host": real_evidence.get("host"),
        "reportPath": None,
        "scenarios": list(REQUIRED_SCENARIOS),
        "completeOccurrences": complete.get("occurrences"),
        "quantity": complete.get("quantity"),
        "quantityTarget": complete.get("quantityTarget"),
        "mixedCompleteness": mixed.get("completeness"),
        "facts": {
            "observed": facts_evidence.get("observedCount"),
            "unavailable": facts_evidence.get("unavailableCount"),
            "unsupported": facts_evidence.get("unsupportedCount"),
        },
        "requiredFactStage": required.get("stage"),
        "baselineStage": baseline.get("stage"),
        "multiOutcomeEvidenceFiles": multi.get("outcomeScopedRaw"),
        "crossRepositoryBlocker": {
            "boundary": blocker.get("boundary"),
            "summary": blocker.get("summary"),
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    engine_repo = args.engine_repo.expanduser().resolve(strict=False)
    freecad_repo = args.freecad_repo.expanduser().resolve(strict=False)
    owned_workspace = args.workspace is None
    workspace = (
        Path(tempfile.mkdtemp(prefix="parametron-evidence-proof-"))
        if owned_workspace
        else args.workspace.expanduser().resolve(strict=False)
    )
    report = (
        args.report.expanduser().resolve(strict=False)
        if args.report is not None
        else workspace / "proof-report.json"
    )
    try:
        proof_script = _require_inputs(
            engine_repo=engine_repo,
            freecad_repo=freecad_repo,
        )
        _run_engine_proof(
            proof_script=proof_script,
            engine_repo=engine_repo,
            freecad_repo=freecad_repo,
            workspace=workspace,
            report=report,
            timeout=args.timeout,
            keep_workspace=args.keep_workspace,
        )
        summary = _validate_report(_load_report(report))
        summary["reportPath"] = str(report)
        sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return 0
    except ProofError as exc:
        sys.stderr.write(f"engine evidence proof failed: {exc}\n")
        return 1
    finally:
        if owned_workspace and not args.keep_workspace:
            shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
