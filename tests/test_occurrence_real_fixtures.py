"""Real FreeCAD acceptance tests for native occurrence evidence."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "assembly_occurrence"
GENERATOR = REPOSITORY_ROOT / "scripts" / "generate_assembly_occurrence_fixtures.py"

SOURCE_DOCUMENT = "assembly-root.FCStd"
COMPONENT_A = "resources/component-a.FCStd"
COMPONENT_B = "resources/component-b.FCStd"
NESTED_ASSEMBLY = "resources/nested-assembly.FCStd"
MISSING_COMPONENT = "resources/missing-component.FCStd"

MECHANISM = "freecad-1.1.4-assembly-group-individual-link"
SUPPORTED_LINK_NAMES = [f"Link{index:02d}" for index in range(1, 11)]

RESOURCES = (
    ("assembly_root", SOURCE_DOCUMENT, True),
    ("component_a", COMPONENT_A, False),
    ("component_b", COMPONENT_B, False),
    ("missing_component", MISSING_COMPONENT, False),
    ("nested_assembly", NESTED_ASSEMBLY, False),
)


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
    if not (FIXTURE_ROOT / SOURCE_DOCUMENT).is_file():
        pytest.skip("occurrence fixture bundle is not available")
    content = (FIXTURE_ROOT / SOURCE_DOCUMENT).read_bytes()
    if content.startswith(b"version https://git-lfs.github.com/spec/v1"):
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


def _copy_bundle(destination: Path) -> None:
    shutil.copytree(FIXTURE_ROOT, destination)


def _write_manifest(root: Path) -> Path:
    manifest = root / "prm.export-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "sourceDocument": SOURCE_DOCUMENT,
                "parameterAssignments": [],
                "outputs": [],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _write_integrity_request(root: Path) -> Path:
    resources = []
    for logical_id, coordinate, expects_result in RESOURCES:
        path = root / coordinate
        digest = _digest(path.read_bytes()) if path.is_file() else "0" * 64
        resources.append(
            {
                "logicalId": logical_id,
                "kind": "model",
                "materializedCoordinate": coordinate,
                "baselineSha256": digest,
                "expectsPersistedResult": expects_result,
            }
        )
    request = root.parent / "prm.integrity-request.json"
    request.write_text(
        json.dumps({"schemaVersion": "1.0", "resources": resources}),
        encoding="utf-8",
    )
    return request


def _write_occurrence_request(
    root: Path,
    *,
    parent_name: str,
    context: list[dict] | None = None,
) -> Path:
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
                        "name": parent_name,
                    },
                    "context": context or [],
                    "mechanism": MECHANISM,
                },
            }
        ),
        encoding="utf-8",
    )
    return request


def _run(
    root: Path,
    *,
    integrity_request: Path,
) -> subprocess.CompletedProcess:
    wrapper = _require_runtime()
    manifest = _write_manifest(root)
    environment = os.environ.copy()
    environment["PARAMETRON_RUNTIME_INTEGRITY_REQUEST"] = str(integrity_request)
    return subprocess.run(
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
            str(root / "outputs"),
        ],
        cwd=root.parent,
        capture_output=True,
        text=True,
        timeout=120,
        env=environment,
        check=False,
    )


def _attempt(tmp_path: Path, name: str, *, parent_name: str, context=None) -> Path:
    root = tmp_path / name / "arbitrary" / "nested" / "attempt"
    root.parent.mkdir(parents=True)
    _copy_bundle(root)
    (root / "outputs").mkdir()
    _write_occurrence_request(root, parent_name=parent_name, context=context)
    return root


def _evidence(root: Path) -> dict:
    return json.loads(
        (root / "outputs" / "prm.occurrence-evidence.json").read_text(encoding="utf-8")
    )


def _members(evidence: dict) -> dict[str, dict]:
    return {member["name"]: member for member in evidence["members"]}


def test_real_supported_assembly_emits_complete_occurrences(tmp_path):
    root = _attempt(tmp_path, "supported", parent_name="SupportedAssembly")
    integrity_request = _write_integrity_request(root)

    process = _run(root, integrity_request=integrity_request)

    assert process.returncode == 0, process.stdout + process.stderr
    result = json.loads((root / "prm.result.json").read_text(encoding="utf-8"))
    assert result["status"] == "succeeded"
    evidence = _evidence(root)

    assert evidence["schemaVersion"] == "1.1"
    assert evidence["kind"] == "native_occurrence_evidence"
    assert evidence["freecadVersion"] == "1.1.4"
    assert evidence["completeness"] == "complete"
    assert evidence["inspectionCompleted"] is True
    assert evidence["diagnostics"] == []
    assert evidence["scope"]["parent"]["name"] == "SupportedAssembly"
    assert evidence["scope"]["mechanism"] == MECHANISM
    assert evidence["scope"]["context"] == []
    assert evidence["parent"] == {
        "entity": evidence["scope"]["parent"],
        "document": SOURCE_DOCUMENT,
        "nativeType": "Assembly::AssemblyObject",
    }
    assert evidence["group"] == sorted(SUPPORTED_LINK_NAMES)
    assert [member["name"] for member in evidence["members"]] == sorted(
        SUPPORTED_LINK_NAMES
    )

    for member in evidence["members"]:
        assert member["nativeType"] == "App::Link"
        assert member["elementCount"] == 0
        assert member["membershipCorroborated"] is True
        assert member["classification"] == "occurrence"
        assert member["resolution"] == "resolved"
        assert member["nativeStateValid"] is True
        assert member["target"] == {
            "entity": {
                "resource": {
                    "projectId": "project",
                    "kind": "model",
                    "logicalId": "component_a",
                },
                "nativeKind": "object",
                "name": "Body",
            },
            "document": COMPONENT_A,
            "nativeType": "PartDesign::Body",
        }

    rendered = json.dumps(evidence)
    assert "quantity" not in rendered
    assert "components" not in evidence
    assert str(root) not in rendered
    assert str(tmp_path) not in rendered
    assert not (root / "outputs" / "prm.observed.json").exists()


def test_real_mixed_assembly_reports_explicit_incomplete_states(tmp_path):
    root = _attempt(tmp_path, "mixed", parent_name="Assembly")
    integrity_request = _write_integrity_request(root)

    process = _run(root, integrity_request=integrity_request)

    assert process.returncode == 0, process.stdout + process.stderr
    evidence = _evidence(root)
    members = _members(evidence)

    assert evidence["completeness"] == "incomplete"
    assert evidence["inspectionCompleted"] is True
    assert evidence["diagnostics"]
    assert evidence["group"] == sorted(members)

    assert members["SharedSourceA"]["classification"] == "occurrence"
    assert (
        members["SharedSourceA"]["target"]["entity"]["resource"]["logicalId"]
        == "component_a"
    )
    assert members["SharedSourceB"]["classification"] == "occurrence"
    assert (
        members["SharedSourceB"]["target"]["entity"]["resource"]["logicalId"]
        == "component_a"
    )
    assert members["CrossResourceBody"]["classification"] == "occurrence"
    assert (
        members["CrossResourceBody"]["target"]["entity"]["resource"]["logicalId"]
        == "component_b"
    )
    assert (
        members["CrossResourceBody"]["target"]["entity"]["name"]
        == members["SharedSourceA"]["target"]["entity"]["name"]
        == "Body"
    )
    assert members["PartLink"]["classification"] == "occurrence"
    assert members["PartLink"]["target"]["nativeType"] == "App::Part"
    assert members["MarkerLink"]["classification"] == "unsupported"
    assert members["NestedLink"]["classification"] == "unsupported"
    assert "AssemblyLink" in members["NestedLink"]["diagnostic"]
    assert members["ArrayLink"]["classification"] == "unsupported"
    assert members["ArrayLink"]["elementCount"] == 1
    assert members["MissingTarget"]["classification"] == "unresolved"
    assert members["MissingTarget"]["nativeStateValid"] is False
    assert members["Joints"]["classification"] == "auxiliary"
    assert members["Joints"]["resolution"] == "resolved"
    assert members["Joints"]["contents"] == {
        "inspectionCompleted": True,
        "group": [],
    }
    assert not (root / MISSING_COMPONENT).exists()


def test_real_evidence_is_relocation_and_repeated_run_stable(tmp_path):
    first_root = _attempt(tmp_path, "first", parent_name="SupportedAssembly")
    repeated_root = _attempt(tmp_path, "repeated", parent_name="SupportedAssembly")
    second_root = _attempt(tmp_path, "second", parent_name="SupportedAssembly")

    first_process = _run(
        first_root,
        integrity_request=_write_integrity_request(first_root),
    )
    repeated_process = _run(
        repeated_root,
        integrity_request=_write_integrity_request(repeated_root),
    )
    second_process = _run(
        second_root,
        integrity_request=_write_integrity_request(second_root),
    )

    for process in (first_process, repeated_process, second_process):
        assert process.returncode == 0, process.stdout + process.stderr

    first = (first_root / "outputs" / "prm.occurrence-evidence.json").read_bytes()
    repeated = (repeated_root / "outputs" / "prm.occurrence-evidence.json").read_bytes()
    second = (second_root / "outputs" / "prm.occurrence-evidence.json").read_bytes()

    assert first == repeated == second
    rendered = first.decode("utf-8")
    for prohibited in (
        str(tmp_path),
        "first",
        "repeated",
        "second",
        "arbitrary",
        "nested",
    ):
        assert prohibited not in rendered


def test_real_non_empty_context_is_explicitly_unsupported(tmp_path):
    root = _attempt(tmp_path, "context", parent_name="SupportedAssembly")
    _write_occurrence_request(
        root,
        parent_name="SupportedAssembly",
        context=[
            {
                "parent": {
                    "resource": {
                        "projectId": "project",
                        "kind": "model",
                        "logicalId": "component_a",
                    },
                    "nativeKind": "object",
                    "name": "Body",
                },
                "member": "Link01",
            }
        ],
    )
    integrity_request = _write_integrity_request(root)

    process = _run(root, integrity_request=integrity_request)

    assert process.returncode == 0, process.stdout + process.stderr
    evidence = _evidence(root)
    assert evidence["completeness"] == "unsupported"
    assert evidence["inspectionCompleted"] is False
    assert evidence["group"] == []
    assert evidence["members"] == []
    assert evidence["diagnostics"]
    assert evidence["parent"]["nativeType"] == "Assembly::AssemblyObject"


def test_maintenance_generator_is_semantically_reproducible(tmp_path):
    host_name = os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd")
    host = shutil.which(host_name)
    if host is None:
        message = "a FreeCAD host is required"
        if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
            pytest.fail(message)
        pytest.skip(message)

    regenerated = tmp_path / "regenerated"
    completed = subprocess.run(
        [host, str(GENERATOR), f"--pass={regenerated}"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert sorted(
        str(path.relative_to(regenerated)) for path in regenerated.rglob("*.FCStd")
    ) == [
        SOURCE_DOCUMENT,
        COMPONENT_A,
        COMPONENT_B,
        NESTED_ASSEMBLY,
    ]

    regenerated_root = tmp_path / "regenerated-attempt"
    shutil.copytree(regenerated, regenerated_root)
    (regenerated_root / "outputs").mkdir()
    _write_occurrence_request(
        regenerated_root,
        parent_name="SupportedAssembly",
    )
    regenerated_process = _run(
        regenerated_root,
        integrity_request=_write_integrity_request(regenerated_root),
    )
    assert regenerated_process.returncode == 0, (
        regenerated_process.stdout + regenerated_process.stderr
    )

    committed_root = _attempt(tmp_path, "committed", parent_name="SupportedAssembly")
    committed_process = _run(
        committed_root,
        integrity_request=_write_integrity_request(committed_root),
    )
    assert committed_process.returncode == 0, (
        committed_process.stdout + committed_process.stderr
    )

    assert (
        regenerated_root / "outputs" / "prm.occurrence-evidence.json"
    ).read_bytes() == (
        committed_root / "outputs" / "prm.occurrence-evidence.json"
    ).read_bytes()
