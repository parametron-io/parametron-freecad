"""Real FreeCAD rehearsal of ordinary native-only production execution."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/canonical_lifecycle/input/cube.FCStd"
INSPECTOR = ROOT / "tests/freecad_canonical_parameter_inspection_runner.py"
VALUES = {
    "boxChamfer": 5,
    "boxHeight": 60,
    "boxLength": 80,
    "boxWidth": 50,
    "holeDia": 18,
}


def _required_executable(name: str, description: str) -> str:
    executable = shutil.which(name)
    if executable is not None:
        return executable
    message = f"{description} is unavailable: {name}"
    if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
        pytest.fail(message)
    pytest.skip(message)


def _run_production_execute(wrapper: str, root: Path) -> subprocess.CompletedProcess[str]:
    command = [
        wrapper, "execute", "--working-copy", str(root),
        "--manifest", str(root / "prm.export-manifest.json"),
        "--result", str(root / "prm.result.json"),
    ]
    return subprocess.run(command, capture_output=True, text=True, timeout=90)


def _inspect_persisted_document(host: str, document: Path, facts: Path) -> dict:
    command = [
        host, "-P", str(ROOT), str(INSPECTOR),
        f"--pass={document}", f"--pass={facts}",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Exception while processing file" not in completed.stderr
    assert facts.is_file(), completed.stdout + completed.stderr
    return json.loads(facts.read_text(encoding="utf-8"))


def _run_ordinary_native_rehearsal(wrapper: str, host: str, root: Path) -> tuple[bytes, dict]:
    source_dir = root / "source"
    source_dir.mkdir(parents=True)
    working_document = source_dir / "cube.FCStd"
    shutil.copyfile(SOURCE, working_document)
    manifest = {
        "schemaVersion": "1.0",
        "sourceDocument": "source/cube.FCStd",
        "parameterAssignments": [
            {"target": f"VarSet.{name}", "value": value, "valueKind": "float"}
            for name, value in VALUES.items()
        ],
        "outputs": [],
    }
    (root / "prm.export-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    completed = _run_production_execute(wrapper, root)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result_bytes = (root / "prm.result.json").read_bytes()
    result = json.loads(result_bytes)
    assert result == {"schemaVersion": "1.0", "status": "succeeded", "artifacts": []}
    facts = _inspect_persisted_document(
        host, working_document, root / "native-parameter-facts.json"
    )
    assert facts == VALUES
    return result_bytes, facts


def test_public_execute_persists_ordinary_parameters(tmp_path: Path) -> None:
    wrapper = _required_executable("parametron-freecad", "production wrapper")
    host = _required_executable(
        os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd"), "real FreeCAD host"
    )
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    roots = (tmp_path / "alpha", tmp_path / "nested" / "beta")
    try:
        outcomes = [
            _run_ordinary_native_rehearsal(wrapper, host, root) for root in roots
        ]
        assert outcomes[0] == outcomes[1]
        for result_bytes, _ in outcomes:
            for path in (SOURCE, ROOT, tmp_path, *roots):
                assert str(path).encode("utf-8") not in result_bytes
    finally:
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash


def _run_invalid_native_document_rehearsal(wrapper: str, root: Path) -> tuple[str, ...]:
    source_dir = root / "source"
    source_dir.mkdir(parents=True)
    invalid_document = source_dir / "invalid.FCStd"
    invalid_document.write_bytes(b"not a FreeCAD document\n")
    assert invalid_document.is_file() and invalid_document.parent == root / "source"

    manifest = {
        "schemaVersion": "1.0",
        "sourceDocument": "source/invalid.FCStd",
        "parameterAssignments": [],
        "outputs": [],
    }
    (root / "prm.export-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    completed = _run_production_execute(wrapper, root)
    assert completed.returncode == 70, completed.stdout + completed.stderr
    result_path = root / "prm.result.json"
    assert result_path.is_file(), completed.stdout + completed.stderr
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert set(result) == {"schemaVersion", "status", "failure"}
    assert result["schemaVersion"] == "1.0"
    assert result["status"] == "failed"
    failure = result["failure"]
    assert set(failure) == {"boundary", "category", "code", "message", "stage"}
    identity = (
        failure["boundary"], failure["category"], failure["code"], failure["stage"]
    )
    assert identity == (
        "execution_entrypoint", "execution", "runtime_failure", "document_open"
    )
    message = failure["message"]
    assert message.startswith(f"FreeCAD failed to open document: {invalid_document}: ")
    assert "Invalid project file" in message
    assert "Traceback" not in message
    assert message == " ".join(message.split())
    assert "artifacts" not in result
    return (result["status"], *identity)


def test_public_execute_reports_native_document_open_failure(tmp_path: Path) -> None:
    wrapper = _required_executable("parametron-freecad", "production wrapper")
    _required_executable(
        os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd"), "real FreeCAD host"
    )
    roots = (tmp_path / "invalid-first", tmp_path / "nested" / "invalid-second")
    outcomes = [_run_invalid_native_document_rehearsal(wrapper, root) for root in roots]
    assert outcomes[0] == outcomes[1]
