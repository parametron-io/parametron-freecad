#!/usr/bin/env python3
"""Run the opt-in Engine acceptance proof for FreeCAD metadata evidence.

Engine owns request composition, expected-versus-observed verification, and
normalized records. FreeCAD owns the native metadata mutation and raw
observation. This harness runs the normal Engine CLI against the committed
metadata fixture with the production ``parametron-freecad`` launcher and
verifies Engine's recorded acceptance result.

    nix develop --command python \
      scripts/run_metadata_engine_acceptance_proof.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENGINE_REPO = REPOSITORY_ROOT.parent / "parametron-engine"
REQUIRED_PROJECT_FILES = (
    "prm.project.json",
    "prm.cad.json",
    "prm.semantic-map.json",
    "metadata.project.dsl",
    "prm.export-manifest.json",
    "prm.verification.json",
    "input/metadata-coexistence.FCStd",
)

FIXTURE_SHA256 = "b6a09b7f7092db0efb594026e8e6dc3eb5fff49fa78582851e2961e0e15910c0"

EXPECTED_AUTHORED_METADATA = {
    "meta.enclosure.mass": {
        "ownerId": "MetadataBody",
        "key": "mass",
        "value": 12.5,
        "valueKind": "number",
    },
    "meta.enclosure.material": {
        "ownerId": "MetadataBody",
        "key": "material",
        "value": "S235JR",
        "valueKind": "string",
    },
    "meta.enclosure.revision": {
        "ownerId": "MetadataBody",
        "key": "revision",
        "value": 7,
        "valueKind": "integer",
    },
    "meta.enclosure.sequence": {
        "ownerId": "MetadataBody",
        "key": "sequence",
        "value": 20,
        "valueKind": "integer",
    },
    "meta.enclosure.tagged": {
        "ownerId": "MetadataBody",
        "key": "tagged",
        "value": True,
        "valueKind": "boolean",
    },
    "meta.enclosure.tolerance": {
        "ownerId": "MetadataBody",
        "key": "tolerance",
        "value": 0.75,
        "valueKind": "number",
    },
}

EXPECTED_OBSERVED_METADATA = [
    {
        "id": "working_copy_sha256",
        "key": "working_copy_sha256",
        "ownerId": "workingCopy",
        "value": FIXTURE_SHA256,
        "valueKind": "string",
    },
    *[
        {
            "id": metadata_id,
            "key": expected["key"],
            "ownerId": expected["ownerId"],
            "value": expected["value"],
            "valueKind": expected["valueKind"],
        }
        for metadata_id, expected in EXPECTED_AUTHORED_METADATA.items()
    ],
]

EXPECTED_OBSERVED_PARAMETERS = [
    {
        "groupId": "Parameters",
        "id": "par.root.varset.pilotValue",
        "name": "pilotValue",
        "value": 12.5,
        "valueKind": "number",
    }
]

EXPECTED_TARGET_STATE = {
    "existence": [
        {
            "destination": "part",
            "object": "DeletionMarker",
            "status": "absent",
        }
    ],
    "suppression": [
        {
            "destination": "part",
            "object": "Pad",
            "status": "observed",
            "value": True,
        }
    ],
    "visibility": [
        {
            "destination": "part",
            "object": "MetadataBody",
            "status": "observed",
            "value": False,
        }
    ],
}


class ProofError(RuntimeError):
    """Raised when the metadata Engine acceptance proof cannot complete."""


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Engine acceptance proof for real FreeCAD metadata "
            "mutation and observation evidence."
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


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_inputs(*, engine_repo: Path, freecad_repo: Path) -> Path:
    if not (engine_repo / "go.mod").is_file():
        raise ProofError(f"Engine checkout is unavailable: {engine_repo}")
    if not (engine_repo / "cmd" / "parametron").is_dir():
        raise ProofError(f"Engine CLI source is unavailable: {engine_repo}")
    if shutil.which("nix") is None:
        raise ProofError("nix is required to build and run the Engine proof")
    launcher = os.environ.get("PARAMETRON_FREECAD_RUNTIME") or shutil.which(
        "parametron-freecad"
    )
    if not launcher:
        raise ProofError(
            "parametron-freecad launcher is unavailable; run inside the "
            "repository Nix shell or set PARAMETRON_FREECAD_RUNTIME"
        )
    launcher_path = Path(launcher).expanduser().resolve(strict=False)
    if not launcher_path.is_file() or not os.access(launcher_path, os.X_OK):
        raise ProofError(f"launcher is not executable: {launcher_path}")
    project_dir = freecad_repo / "tests" / "fixtures" / "metadata_mutation"
    missing = [
        relative
        for relative in REQUIRED_PROJECT_FILES
        if not (project_dir / relative).is_file()
    ]
    if missing:
        raise ProofError("metadata fixture bundle is incomplete: " + ", ".join(missing))
    fixture_path = project_dir / "input" / "metadata-coexistence.FCStd"
    if _sha256(fixture_path) != FIXTURE_SHA256:
        raise ProofError("committed metadata coexistence fixture digest drifted")
    if fixture_path.read_bytes().startswith(
        b"version https://git-lfs.github.com/spec/v1"
    ):
        raise ProofError("metadata fixture is not fetched from Git LFS")
    return launcher_path


def _engine_revision(engine_repo: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(engine_repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _build_engine(engine_repo: Path, workspace: Path, timeout: int) -> Path:
    binary = workspace / "parametron"
    command = [
        "nix",
        "develop",
        str(engine_repo),
        "--command",
        "go",
        "build",
        "-C",
        str(engine_repo),
        "-o",
        str(binary),
        "./cmd/parametron",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProofError(f"Engine build timed out after {timeout}s") from exc
    if completed.returncode != 0 or not binary.is_file():
        raise ProofError(
            "Engine build failed\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return binary


def _freecad_version(launcher: Path) -> str:
    completed = subprocess.run(
        [str(launcher), "smoke"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise ProofError(
            "FreeCAD smoke probe failed\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    for line in reversed(completed.stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        version = payload.get("freecadVersion")
        if isinstance(version, list) and len(version) >= 3:
            return ".".join(str(part) for part in version[:3])
    raise ProofError("FreeCAD smoke probe returned no version payload")


def _run_engine(
    *,
    binary: Path,
    engine_repo: Path,
    freecad_repo: Path,
    launcher: Path,
    workspace: Path,
    timeout: int,
) -> None:
    environment = os.environ.copy()
    environment["PARAMETRON_FREECAD_RUNTIME"] = str(launcher)
    freecad_host = shutil.which("freecadcmd")
    if freecad_host is not None:
        environment["PARAMETRON_FREECAD_BIN"] = freecad_host
    command = [
        str(binary),
        "--project",
        str(freecad_repo / "tests" / "fixtures" / "metadata_mutation"),
        "--out",
        str(workspace / "output"),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProofError(f"Engine acceptance run timed out after {timeout}s") from exc
    if completed.returncode != 0:
        raise ProofError(
            "Engine acceptance run failed\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def _single(paths: list[Path], description: str) -> Path:
    if len(paths) != 1:
        raise ProofError(
            f"expected exactly one {description}, found {len(paths)}: {paths}"
        )
    return paths[0]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProofError(f"cannot decode Engine evidence {path}: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ProofError(f"Engine evidence root is not an object: {path}")
    return decoded


def _verification_record(workspace: Path) -> tuple[Path, dict[str, Any]]:
    path = _single(
        sorted(workspace.rglob("prm.verification-record.json")),
        "verification record",
    )
    return path, _load_json(path)


def _observed_evidence(workspace: Path) -> dict[str, Any]:
    candidates = sorted(workspace.rglob("prm.observed.json"))
    if not candidates:
        raise ProofError("Engine run produced no observed evidence")
    raw = [path for path in candidates if path.parent.name == "observed"]
    chosen = raw[0] if raw else candidates[0]
    return _load_json(chosen)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProofError(message)


def _validate_verification(record: dict[str, Any]) -> dict[str, Any]:
    verification = record.get("verification")
    _require(isinstance(verification, dict), "verification record is malformed")
    _require(
        verification.get("outcome") == "pass",
        f"Engine verification did not pass: {verification.get('outcome')!r}",
    )
    categories = {
        category.get("category"): category
        for category in verification.get("categories", [])
        if isinstance(category, dict)
    }
    for name, expected_message in (
        ("metadata", "verified 7 metadata entries"),
        ("parameters", "verified 1 parameters"),
        ("references", "verified 1 reference entries"),
        ("target_state", "verified 3 target-state entries"),
    ):
        category = categories.get(name)
        _require(isinstance(category, dict), f"verification category {name} is missing")
        _require(
            category.get("enabled") is True
            and category.get("outcome") == "pass"
            and category.get("message") == expected_message,
            f"verification category {name} did not pass: {category}",
        )
    components = categories.get("components")
    _require(
        isinstance(components, dict)
        and components.get("enabled") is False
        and components.get("outcome") == "skipped",
        f"component verification did not stay disabled: {components}",
    )

    provenance = record.get("provenance")
    _require(isinstance(provenance, dict), "verification provenance is missing")
    resources = provenance.get("Integrity", {}).get("Resources")
    _require(
        isinstance(resources, list) and len(resources) == 1,
        "verification integrity resource is missing",
    )
    resource = resources[0]
    _require(
        resource.get("SourceDigestSHA256") == FIXTURE_SHA256,
        f"Engine accepted a different source digest: {resource.get('SourceDigestSHA256')!r}",
    )
    for field in ("MaterializationStatus", "RuntimeBaselineStatus", "ResultStatus"):
        _require(
            resource.get(field) == "verified",
            f"integrity field {field} is not verified: {resource.get(field)!r}",
        )
    persisted = resource.get("PersistedResultDigestSHA256")
    _require(
        isinstance(persisted, str) and bool(persisted),
        "persisted result digest is missing",
    )

    return {
        "metadataVerified": 7,
        "persistedResultDigest": persisted,
        "categories": {
            name: categories[name]["outcome"]
            for name in (
                "components",
                "metadata",
                "parameters",
                "references",
                "target_state",
            )
        },
    }


def _validate_observed(observed: dict[str, Any]) -> None:
    observation = observed.get("observation")
    _require(isinstance(observation, dict), "observed evidence is malformed")
    _require(
        observation.get("metadata") == EXPECTED_OBSERVED_METADATA,
        f"observed metadata drifted: {observation.get('metadata')}",
    )
    _require(
        observation.get("parameters") == EXPECTED_OBSERVED_PARAMETERS,
        f"observed parameter drifted: {observation.get('parameters')}",
    )
    _require(
        observation.get("targetState") == EXPECTED_TARGET_STATE,
        f"observed target state drifted: {observation.get('targetState')}",
    )
    working_copy = observed.get("workingCopy")
    _require(
        isinstance(working_copy, dict) and working_copy.get("sha256") == FIXTURE_SHA256,
        f"observed working copy digest drifted: {working_copy}",
    )


def _validate_report(
    *,
    record_path: Path,
    record: dict[str, Any],
    observed: dict[str, Any],
    engine_revision: str,
    freecad_version: str,
    source_digest_before: str,
    source_digest_after: str,
) -> dict[str, Any]:
    _require(
        source_digest_before == source_digest_after == FIXTURE_SHA256,
        "the committed source fixture changed during the Engine proof",
    )
    verification = _validate_verification(record)
    _validate_observed(observed)
    run_root = record_path.parents[2]
    return {
        "status": "passed",
        "engineRevision": engine_revision,
        "freecadVersion": freecad_version,
        "metadataVerified": verification["metadataVerified"],
        "authoredMetadataIds": sorted(EXPECTED_AUTHORED_METADATA),
        "parameterValue": EXPECTED_OBSERVED_PARAMETERS[0]["value"],
        "targetState": EXPECTED_TARGET_STATE,
        "sourceDigest": FIXTURE_SHA256,
        "persistedResultDigest": verification["persistedResultDigest"],
        "categories": verification["categories"],
        "runRoot": str(run_root),
    }


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    engine_repo = args.engine_repo.expanduser().resolve(strict=False)
    freecad_repo = args.freecad_repo.expanduser().resolve(strict=False)
    owned_workspace = args.workspace is None
    workspace = (
        Path(tempfile.mkdtemp(prefix="parametron-metadata-proof-"))
        if owned_workspace
        else args.workspace.expanduser().resolve(strict=False)
    )
    report = (
        args.report.expanduser().resolve(strict=False)
        if args.report is not None
        else workspace / "metadata-proof-report.json"
    )
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        launcher = _require_inputs(
            engine_repo=engine_repo,
            freecad_repo=freecad_repo,
        )
        fixture_path = (
            freecad_repo
            / "tests"
            / "fixtures"
            / "metadata_mutation"
            / "input"
            / "metadata-coexistence.FCStd"
        )
        source_before = _sha256(fixture_path)
        engine_revision = _engine_revision(engine_repo)
        freecad_version = _freecad_version(launcher)
        binary = _build_engine(engine_repo, workspace, args.timeout)
        _run_engine(
            binary=binary,
            engine_repo=engine_repo,
            freecad_repo=freecad_repo,
            launcher=launcher,
            workspace=workspace,
            timeout=args.timeout,
        )
        record_path, record = _verification_record(workspace)
        observed = _observed_evidence(workspace)
        summary = _validate_report(
            record_path=record_path,
            record=record,
            observed=observed,
            engine_revision=engine_revision,
            freecad_version=freecad_version,
            source_digest_before=source_before,
            source_digest_after=_sha256(fixture_path),
        )
        summary["reportPath"] = str(report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        sys.stdout.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return 0
    except ProofError as exc:
        sys.stderr.write(f"metadata Engine acceptance proof failed: {exc}\n")
        return 1
    finally:
        if owned_workspace and not args.keep_workspace:
            shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
