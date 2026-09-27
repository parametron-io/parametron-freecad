"""Prerequisite failures must remain visible in permanent native rehearsals."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


NATIVE_CASES = (
    "tests/test_execute_real_rehearsal.py::test_public_execute_persists_ordinary_parameters",
    "tests/test_reference_traversal_real_fixtures.py::RealReferenceTraversalFixtureTests::test_runtime_emission_is_relocation_and_repeated_run_byte_stable",
)


@pytest.mark.parametrize("missing", ("host", "wrapper"))
@pytest.mark.parametrize("strict", (False, True))
def test_unusable_native_prerequisite_is_skip_or_failure(
    tmp_path: Path, missing: str, strict: bool
) -> None:
    if os.name != "posix":
        pytest.skip("executable fault injection requires POSIX")
    if missing == "host" and shutil.which("parametron-freecad") is None:
        pytest.skip("public wrapper is unavailable for host fault injection")
    broken = tmp_path / ("broken-freecadcmd" if missing == "host" else "parametron-freecad")
    broken.write_text("#!/bin/sh\nexit 127\n", encoding="utf-8")
    broken.chmod(0o755)
    environment = os.environ.copy()
    if missing == "host":
        environment["PARAMETRON_FREECAD_BIN"] = str(broken)
    else:
        environment["PARAMETRON_FREECAD_BIN"] = shutil.which("true") or "/bin/true"
        environment["PATH"] = str(tmp_path) + os.pathsep + environment.get("PATH", "")
    if strict:
        environment["PARAMETRON_FREECAD_STRICT_SMOKE"] = "1"
    else:
        environment.pop("PARAMETRON_FREECAD_STRICT_SMOKE", None)

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rs", *NATIVE_CASES],
        env=environment, capture_output=True, text=True, timeout=30,
    )
    if strict:
        assert completed.returncode != 0
        assert "skipped" not in completed.stdout
    else:
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "2 skipped" in completed.stdout
    assert "unusable" in completed.stdout
