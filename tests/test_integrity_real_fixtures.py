"""Real FreeCAD integrity evidence acceptance tests."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    Path(__file__).parent / "fixtures" / "canonical_lifecycle" / "input" / "cube.FCStd"
)

_PRIMARY_COORDINATE = "source/cube.FCStd"
_SECONDARY_COORDINATE = "resources/component/Copy.FCStd"
_RESULT_FILENAME = "prm.result.json"
_INTEGRITY_EVIDENCE_FILENAME = "prm.integrity-evidence.json"


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _require_runtime() -> str:
    wrapper = shutil.which("parametron-freecad")
    host_name = os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd")
    host = shutil.which(host_name)
    if wrapper is None or host is None:
        message = "parametron-freecad and a FreeCAD host are required"
        if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
            pytest.fail(message)
        pytest.skip(message)
    return wrapper


def _manifest() -> dict:
    return {
        "schemaVersion": "1.0",
        "sourceDocument": _PRIMARY_COORDINATE,
        "parameterAssignments": [
            {
                "target": "VarSet.boxLength",
                "value": 80,
                "valueKind": "float",
            }
        ],
        "outputs": [],
    }


def _make_attempt(root: Path, *, include_secondary: bool = True) -> dict:
    (root / "source").mkdir(parents=True)
    (root / "outputs").mkdir()
    shutil.copyfile(SOURCE, root / _PRIMARY_COORDINATE)
    if include_secondary:
        (root / "resources" / "component").mkdir(parents=True)
        shutil.copyfile(SOURCE, root / _SECONDARY_COORDINATE)
    (root / "prm.export-manifest.json").write_text(
        json.dumps(_manifest()),
        encoding="utf-8",
    )

    primary_digest = _digest((root / _PRIMARY_COORDINATE).read_bytes())
    resources = []
    if include_secondary:
        resources.append(
            {
                "logicalId": "component_copy",
                "kind": "model",
                "materializedCoordinate": _SECONDARY_COORDINATE,
                "baselineSha256": _digest((root / _SECONDARY_COORDINATE).read_bytes()),
                "expectsPersistedResult": False,
            }
        )
    resources.append(
        {
            "logicalId": "cube_model",
            "kind": "model",
            "materializedCoordinate": _PRIMARY_COORDINATE,
            "baselineSha256": primary_digest,
            "expectsPersistedResult": True,
        }
    )

    request_path = root.parent / "prm.integrity-request.json"
    request_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "resources": resources,
            }
        ),
        encoding="utf-8",
    )
    return {
        "request": request_path,
        "baseline": primary_digest,
    }


def _run(root: Path, request_path: Path) -> subprocess.CompletedProcess:
    wrapper = _require_runtime()
    environment = os.environ.copy()
    environment["PARAMETRON_RUNTIME_INTEGRITY_REQUEST"] = str(request_path)
    return subprocess.run(
        [
            wrapper,
            "execute",
            "--working-copy",
            str(root),
            "--manifest",
            str(root / "prm.export-manifest.json"),
            "--result",
            str(root / _RESULT_FILENAME),
            "--output-dir",
            str(root / "outputs"),
        ],
        cwd=root.parent,
        capture_output=True,
        text=True,
        timeout=120,
        env=environment,
        check=False,
    )


def test_real_integrity_evidence_matches_independent_hashes(tmp_path):
    source_before = SOURCE.read_bytes()
    root = tmp_path / "relocated" / "deep" / "attempt"
    setup = _make_attempt(root)

    process = _run(root, setup["request"])

    assert process.returncode == 0, process.stdout + process.stderr
    assert "Traceback" not in process.stderr
    result = json.loads((root / _RESULT_FILENAME).read_text(encoding="utf-8"))
    assert result == {
        "artifacts": [],
        "schemaVersion": "1.0",
        "status": "succeeded",
    }

    evidence = json.loads(
        (root / "outputs" / _INTEGRITY_EVIDENCE_FILENAME).read_text(encoding="utf-8")
    )
    assert evidence["schemaVersion"] == "1.0"
    assert [resource["logicalId"] for resource in evidence["resources"]] == [
        "component_copy",
        "cube_model",
    ]

    secondary, primary = evidence["resources"]
    assert secondary["materializedCoordinate"] == _SECONDARY_COORDINATE
    assert secondary["status"] == "observed"
    assert secondary["baselineSha256"] == _digest(
        (root / _SECONDARY_COORDINATE).read_bytes()
    )
    assert secondary["persistedResult"] is None

    persisted_bytes = (root / _PRIMARY_COORDINATE).read_bytes()
    persisted_digest = _digest(persisted_bytes)
    assert primary["materializedCoordinate"] == _PRIMARY_COORDINATE
    assert primary["status"] == "observed"
    assert primary["baselineSha256"] == setup["baseline"]
    assert primary["baselineSha256"] != persisted_digest
    assert primary["persistedResult"] == {
        "coordinate": _PRIMARY_COORDINATE,
        "sha256": persisted_digest,
    }
    assert SOURCE.read_bytes() == source_before


def test_real_baseline_mismatch_fails_before_mutation(tmp_path):
    source_before = SOURCE.read_bytes()
    root = tmp_path / "mismatch" / "attempt"
    setup = _make_attempt(root)
    request = json.loads(setup["request"].read_text(encoding="utf-8"))
    request["resources"][-1]["baselineSha256"] = "0" * 64
    setup["request"].write_text(json.dumps(request), encoding="utf-8")
    stale = root / "outputs" / _INTEGRITY_EVIDENCE_FILENAME
    stale.write_bytes(b"stale")

    process = _run(root, setup["request"])

    assert process.returncode == 70, process.stdout + process.stderr
    result = json.loads((root / _RESULT_FILENAME).read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert result["failure"]["stage"] == "integrity_baseline"
    assert not stale.exists()
    assert _digest((root / _PRIMARY_COORDINATE).read_bytes()) == setup["baseline"]
    assert SOURCE.read_bytes() == source_before


def test_real_missing_secondary_is_explicit(tmp_path):
    root = tmp_path / "missing-secondary" / "attempt"
    setup = _make_attempt(root)
    (root / _SECONDARY_COORDINATE).unlink()

    process = _run(root, setup["request"])

    assert process.returncode == 0, process.stdout + process.stderr
    evidence = json.loads(
        (root / "outputs" / _INTEGRITY_EVIDENCE_FILENAME).read_text(encoding="utf-8")
    )
    secondary, primary = evidence["resources"]
    assert secondary["status"] == "missing"
    assert secondary["baselineSha256"] == ""
    assert secondary["persistedResult"] is None
    assert primary["status"] == "observed"
    assert primary["persistedResult"]["sha256"] == _digest(
        (root / _PRIMARY_COORDINATE).read_bytes()
    )
