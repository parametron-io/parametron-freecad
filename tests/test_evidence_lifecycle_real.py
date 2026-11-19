"""One real FreeCAD end-to-end run emitting every engineering sidecar."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "assembly_occurrence"

SOURCE_DOCUMENT = "assembly-root.FCStd"
COMPONENT_A = "resources/component-a.FCStd"
COMPONENT_B = "resources/component-b.FCStd"
NESTED_ASSEMBLY = "resources/nested-assembly.FCStd"
MISSING_COMPONENT = "resources/missing-component.FCStd"

MECHANISM = "freecad-1.1.4-assembly-group-individual-link"


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
    source = FIXTURE_ROOT / SOURCE_DOCUMENT
    if not source.is_file():
        pytest.skip("occurrence fixture bundle is not available")
    if source.read_bytes().startswith(b"version https://git-lfs.github.com/spec/v1"):
        message = "occurrence fixture bundle is not fetched from Git LFS"
        if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
            pytest.fail(message)
        pytest.skip(message)
    smoke = subprocess.run(
        [wrapper, "smoke"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if smoke.returncode != 0:
        message = (
            "parametron-freecad wrapper or FreeCAD host is unusable: "
            f"{smoke.stderr.strip() or smoke.stdout.strip() or smoke.returncode}"
        )
        if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
            pytest.fail(message)
        pytest.skip(message)
    return wrapper


def _write_manifest(root: Path) -> Path:
    manifest = root / "prm.export-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "sourceDocument": SOURCE_DOCUMENT,
                "parameterAssignments": [
                    {
                        "target": "Link01.Label",
                        "value": "MutatedLink",
                        "valueKind": "string",
                    }
                ],
                "outputs": [],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _write_integrity_request(root: Path) -> Path:
    resources = []
    for logical_id, coordinate, expects_result in (
        ("assembly_root", SOURCE_DOCUMENT, True),
        ("component_a", COMPONENT_A, False),
        ("component_b", COMPONENT_B, False),
        ("missing_component", MISSING_COMPONENT, False),
        ("nested_assembly", NESTED_ASSEMBLY, False),
    ):
        path = root / coordinate
        resources.append(
            {
                "logicalId": logical_id,
                "kind": "model",
                "materializedCoordinate": coordinate,
                "baselineSha256": (
                    _digest(path.read_bytes()) if path.is_file() else "0" * 64
                ),
                "expectsPersistedResult": expects_result,
            }
        )
    request = root.parent / "prm.integrity-request.json"
    request.write_text(
        json.dumps({"schemaVersion": "1.0", "resources": resources}),
        encoding="utf-8",
    )
    return request


def _write_occurrence_request(root: Path) -> Path:
    request = root / "prm.occurrence-request.json"
    request.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "requirement": "optional",
                "scope": {
                    "parent": {
                        "resource": {
                            "projectId": "project",
                            "kind": "model",
                            "logicalId": "assembly_root",
                        },
                        "nativeKind": "object",
                        "name": "SupportedAssembly",
                    },
                    "context": [],
                    "mechanism": MECHANISM,
                },
            }
        ),
        encoding="utf-8",
    )
    return request


def _write_fact_request(root: Path) -> Path:
    request = root / "prm.fact-request.json"
    request.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "bindings": [
                    {
                        "kind": "bound_property",
                        "subject": {
                            "resource": {
                                "projectId": "project",
                                "kind": "model",
                                "logicalId": "assembly_root",
                            },
                            "nativeKind": "object",
                            "name": "Link01",
                        },
                        "context": [],
                        "property": "Label",
                        "valueKind": "string",
                        "requirement": "optional",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return request


def _write_observation_request(root: Path) -> Path:
    request = root / "prm.observation-request.json"
    request.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "observe": {
                    "components": False,
                    "parameters": False,
                    "metadata": True,
                    "references": True,
                    "targetState": False,
                },
                "observationContext": {"parameters": []},
                "expected": {
                    "components": [],
                    "parameters": [],
                    "metadata": [{"key": "working_copy_sha256", "value": "runtime"}],
                    "references": [{"kind": "working_copy_path", "name": "runtime"}],
                },
                "checks": {
                    "components": {"enabled": False},
                    "parameters": {"enabled": False},
                    "metadata": {"enabled": True},
                    "references": {"enabled": True},
                },
            }
        ),
        encoding="utf-8",
    )
    return request


def _write_traversal_request(root: Path) -> Path:
    request = root / "prm.reference-traversal-request.json"
    request.write_text(
        json.dumps({"schemaVersion": "1.0", "externalTargets": []}),
        encoding="utf-8",
    )
    return request


def test_real_execute_emits_all_engineering_sidecars(tmp_path):
    wrapper = _require_runtime()
    root = tmp_path / "arbitrary" / "nested" / "attempt"
    root.parent.mkdir(parents=True)
    shutil.copytree(FIXTURE_ROOT, root)
    output = root / "outputs"
    output.mkdir()

    baseline = _digest((root / SOURCE_DOCUMENT).read_bytes())
    manifest = _write_manifest(root)
    integrity_request = _write_integrity_request(root)
    occurrence_request = _write_occurrence_request(root)
    fact_request = _write_fact_request(root)
    observation_request = _write_observation_request(root)
    traversal_request = _write_traversal_request(root)

    environment = os.environ.copy()
    environment["PARAMETRON_RUNTIME_INTEGRITY_REQUEST"] = str(integrity_request)
    process = subprocess.run(
        [
            wrapper,
            "execute",
            "--working-copy",
            str(root),
            "--manifest",
            str(manifest),
            "--result",
            str(root / "prm.result.json"),
            "--output-dir",
            str(output),
            "--observation-request",
            str(observation_request),
            "--reference-traversal-request",
            str(traversal_request),
        ],
        cwd=root.parent,
        capture_output=True,
        text=True,
        timeout=120,
        env=environment,
        check=False,
    )

    assert process.returncode == 0, process.stdout + process.stderr
    result = json.loads((root / "prm.result.json").read_text(encoding="utf-8"))
    assert result == {
        "artifacts": [],
        "schemaVersion": "1.0",
        "status": "succeeded",
    }

    expected_sidecars = {
        "prm.reference-traversal.json",
        "prm.observed.json",
        "prm.occurrence-evidence.json",
        "prm.fact-evidence.json",
        "prm.integrity-evidence.json",
    }
    assert {path.name for path in output.iterdir()} == expected_sidecars

    traversal = json.loads(
        (output / "prm.reference-traversal.json").read_text(encoding="utf-8")
    )
    assert traversal["schemaVersion"] == "1.0"
    assert traversal["sourceDocument"] == SOURCE_DOCUMENT
    assert traversal["status"] == "succeeded"

    observed = json.loads((output / "prm.observed.json").read_text(encoding="utf-8"))
    assert observed["schemaVersion"] == "1.0"
    assert observed["workingCopy"]["sha256"] == baseline
    assert "components" not in observed["observation"]

    occurrence = json.loads(
        (output / "prm.occurrence-evidence.json").read_text(encoding="utf-8")
    )
    assert occurrence["schemaVersion"] == "1.1"
    assert occurrence["completeness"] == "complete"
    assert occurrence["parent"]["entity"]["name"] == "SupportedAssembly"
    assert occurrence["parent"]["document"] == SOURCE_DOCUMENT
    assert len(occurrence["members"]) == 10
    assert all(
        member["classification"] == "occurrence" for member in occurrence["members"]
    )

    fact = json.loads((output / "prm.fact-evidence.json").read_text(encoding="utf-8"))
    assert fact["schemaVersion"] == "1.0"
    assert len(fact["facts"]) == 1
    observed_fact = fact["facts"][0]
    assert observed_fact["availability"] == "observed"
    assert observed_fact["valueKind"] == "string"
    assert observed_fact["value"] == "MutatedLink"
    assert observed_fact["subject"]["document"] == SOURCE_DOCUMENT

    integrity = json.loads(
        (output / "prm.integrity-evidence.json").read_text(encoding="utf-8")
    )
    source_integrity = next(
        resource
        for resource in integrity["resources"]
        if resource["logicalId"] == "assembly_root"
    )
    persisted_digest = _digest((root / SOURCE_DOCUMENT).read_bytes())
    assert source_integrity["baselineSha256"] == baseline
    assert source_integrity["persistedResult"] == {
        "coordinate": SOURCE_DOCUMENT,
        "sha256": persisted_digest,
    }
    assert persisted_digest != baseline

    for name in (
        "prm.occurrence-evidence.json",
        "prm.fact-evidence.json",
        "prm.integrity-evidence.json",
    ):
        rendered = (output / name).read_text(encoding="utf-8")
        assert str(root) not in rendered
        assert str(tmp_path) not in rendered
