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


def test_public_execute_persists_ordinary_parameters(tmp_path: Path) -> None:
    wrapper = _required_executable("parametron-freecad", "production wrapper")
    host = _required_executable(
        os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd"), "real FreeCAD host"
    )
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    try:
        source_dir = tmp_path / "source"
        source_dir.mkdir()
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
        (tmp_path / "prm.export-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        _run_production_execute(wrapper, tmp_path)
        result = json.loads((tmp_path / "prm.result.json").read_text(encoding="utf-8"))
        assert result == {"schemaVersion": "1.0", "status": "succeeded", "artifacts": []}

        facts = _inspect_persisted_document(
            host, working_document, tmp_path / "native-parameter-facts.json"
        )
        assert facts == VALUES
    finally:
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
