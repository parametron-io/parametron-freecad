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


def _run_production_execute(wrapper: str, root: Path) -> None:
    command = [
        wrapper, "execute", "--working-copy", str(root),
        "--manifest", str(root / "prm.export-manifest.json"),
        "--result", str(root / "prm.result.json"),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stdout + completed.stderr


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

    _run_production_execute(wrapper, root)
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
