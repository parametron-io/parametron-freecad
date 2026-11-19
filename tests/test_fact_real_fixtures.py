"""Real FreeCAD acceptance tests for bounded fact evidence."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "fact_evidence"
GENERATOR = REPOSITORY_ROOT / "scripts" / "generate_fact_evidence_fixtures.py"

SOURCE_DOCUMENT = "fact-source.FCStd"
SECONDARY_DOCUMENT = "resources/secondary.FCStd"

SOURCE_RESOURCE = "fact_source"
SECONDARY_RESOURCE = "secondary"


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
        pytest.skip("fact fixture bundle is not available")
    if source.read_bytes().startswith(b"version https://git-lfs.github.com/spec/v1"):
        message = "fact fixture bundle is not fetched from Git LFS"
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


def _subject(logical_id: str, name: str) -> dict[str, object]:
    return {
        "resource": {
            "projectId": "project",
            "kind": "model",
            "logicalId": logical_id,
        },
        "nativeKind": "object",
        "name": name,
    }


def _binding(
    logical_id: str,
    name: str,
    property_name: str,
    value_kind: str,
    *,
    unit: str | None = None,
    requirement: str = "optional",
) -> dict[str, object]:
    binding: dict[str, object] = {
        "kind": "bound_property",
        "subject": _subject(logical_id, name),
        "context": [],
        "property": property_name,
        "valueKind": value_kind,
        "requirement": requirement,
    }
    if unit is not None:
        binding["unit"] = unit
    return binding


_ALL_BINDINGS = [
    _binding(SOURCE_RESOURCE, "Box", "Length", "number", unit="kg"),
    _binding(SOURCE_RESOURCE, "Props", "MeasuredLength", "number", unit="mm"),
    _binding(SOURCE_RESOURCE, "Props", "Ratio", "number"),
    _binding(SOURCE_RESOURCE, "Props", "Count", "integer"),
    _binding(SOURCE_RESOURCE, "Props", "Enabled", "boolean"),
    _binding(SOURCE_RESOURCE, "Props", "PlainText", "string"),
    _binding(SOURCE_RESOURCE, "Props", "SpecialText", "string"),
    _binding(SOURCE_RESOURCE, "Props", "NonFinite", "number"),
    _binding(SOURCE_RESOURCE, "Props", "MissingProperty", "number"),
    _binding(SOURCE_RESOURCE, "Ghost", "Length", "number"),
    _binding(
        SECONDARY_RESOURCE,
        "SecondaryProps",
        "SecondaryLength",
        "number",
        unit="mm",
    ),
]


def _attempt(tmp_path: Path, name: str, bindings: list[dict]) -> Path:
    root = tmp_path / name / "arbitrary" / "nested" / "attempt"
    root.parent.mkdir(parents=True)
    shutil.copytree(FIXTURE_ROOT, root)
    (root / "outputs").mkdir()
    (root / "prm.fact-request.json").write_text(
        json.dumps({"schemaVersion": "1.0", "bindings": bindings}),
        encoding="utf-8",
    )
    return root


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
    request = root.parent / "prm.integrity-request.json"
    request.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "resources": [
                    {
                        "logicalId": SOURCE_RESOURCE,
                        "kind": "model",
                        "materializedCoordinate": SOURCE_DOCUMENT,
                        "baselineSha256": _digest(
                            (root / SOURCE_DOCUMENT).read_bytes()
                        ),
                        "expectsPersistedResult": True,
                    },
                    {
                        "logicalId": SECONDARY_RESOURCE,
                        "kind": "model",
                        "materializedCoordinate": SECONDARY_DOCUMENT,
                        "baselineSha256": _digest(
                            (root / SECONDARY_DOCUMENT).read_bytes()
                        ),
                        "expectsPersistedResult": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return request


def _run(root: Path, *, integrity_request: Path) -> subprocess.CompletedProcess:
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


def _evidence(root: Path) -> dict:
    return json.loads(
        (root / "outputs" / "prm.fact-evidence.json").read_text(encoding="utf-8")
    )


def _facts(evidence: dict) -> dict[tuple[str, str], dict]:
    return {
        (fact["subject"]["entity"]["name"], fact["property"]): fact
        for fact in evidence["facts"]
    }


def test_real_bound_properties_emit_typed_fact_evidence(tmp_path):
    root = _attempt(tmp_path, "facts", _ALL_BINDINGS)
    integrity_request = _write_integrity_request(root)
    secondary_before = _digest((root / SECONDARY_DOCUMENT).read_bytes())

    process = _run(root, integrity_request=integrity_request)

    assert process.returncode == 0, process.stdout + process.stderr
    result = json.loads((root / "prm.result.json").read_text(encoding="utf-8"))
    assert result["status"] == "succeeded"
    evidence = _evidence(root)
    facts = _facts(evidence)

    assert evidence["schemaVersion"] == "1.0"
    assert evidence["kind"] == "native_fact_evidence"
    assert evidence["freecadVersion"] == "1.1.4"

    measured = facts[("Props", "MeasuredLength")]
    assert measured["availability"] == "observed"
    assert measured["valueKind"] == "number"
    assert measured["value"] == 12.5
    assert measured["unit"] == "mm"
    assert measured["subject"]["document"] == SOURCE_DOCUMENT
    assert measured["subject"]["nativeType"] == "App::FeaturePython"

    assert facts[("Props", "Ratio")]["value"] == 3.25
    assert "unit" not in facts[("Props", "Ratio")]
    assert facts[("Props", "Count")]["valueKind"] == "integer"
    assert facts[("Props", "Count")]["value"] == 42
    assert facts[("Props", "Enabled")]["valueKind"] == "boolean"
    assert facts[("Props", "Enabled")]["value"] is True
    assert facts[("Props", "PlainText")]["valueKind"] == "string"
    assert facts[("Props", "PlainText")]["value"] == "bounded fact string"

    secondary = facts[("SecondaryProps", "SecondaryLength")]
    assert secondary["availability"] == "observed"
    assert secondary["value"] == 20.0
    assert secondary["unit"] == "mm"
    assert secondary["subject"]["document"] == SECONDARY_DOCUMENT
    assert _digest((root / SECONDARY_DOCUMENT).read_bytes()) == secondary_before

    special = facts[("Props", "SpecialText")]
    assert special["availability"] == "unsupported"
    assert "canonical" in special["diagnostic"]
    assert "value" not in special
    assert "valueKind" not in special

    non_finite = facts[("Props", "NonFinite")]
    assert non_finite["availability"] == "unsupported"
    assert "non-finite" in non_finite["diagnostic"]
    assert "value" not in non_finite
    assert "valueKind" not in non_finite

    missing = facts[("Props", "MissingProperty")]
    assert missing["availability"] == "unavailable"
    assert missing["subject"]["nativeType"] == "App::FeaturePython"
    assert "value" not in missing
    assert "valueKind" not in missing

    ghost = facts[("Ghost", "Length")]
    assert ghost["availability"] == "unavailable"
    assert ghost["subject"]["nativeType"] == ""

    mass = facts[("Box", "Length")]
    assert mass["availability"] == "unsupported"
    assert "disagrees" in mass["diagnostic"]
    assert "value" not in mass

    rendered = json.dumps(evidence)
    assert "quantity" not in rendered.lower()
    assert "components" not in evidence
    assert str(root) not in rendered
    assert str(tmp_path) not in rendered
    assert not (root / "outputs" / "prm.observed.json").exists()


def test_real_required_unavailable_fact_fails_deterministically(tmp_path):
    root = _attempt(
        tmp_path,
        "required",
        [
            _binding(
                SOURCE_RESOURCE,
                "Props",
                "MissingProperty",
                "number",
                requirement="required",
            )
        ],
    )
    integrity_request = _write_integrity_request(root)
    stale = root / "outputs" / "prm.fact-evidence.json"
    stale.write_bytes(b"stale")

    process = _run(root, integrity_request=integrity_request)

    assert process.returncode == 70, process.stdout + process.stderr
    result = json.loads((root / "prm.result.json").read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert result["failure"]["stage"] == "fact_evidence"
    assert not stale.exists()


def test_real_fact_evidence_is_relocation_and_repeated_run_stable(tmp_path):
    bindings = [
        _binding(SOURCE_RESOURCE, "Props", "MeasuredLength", "number", unit="mm"),
        _binding(SOURCE_RESOURCE, "Props", "Ratio", "number"),
        _binding(SOURCE_RESOURCE, "Props", "Count", "integer"),
        _binding(SOURCE_RESOURCE, "Props", "Enabled", "boolean"),
        _binding(SOURCE_RESOURCE, "Props", "PlainText", "string"),
        _binding(SOURCE_RESOURCE, "Props", "NonFinite", "number"),
        _binding(
            SECONDARY_RESOURCE,
            "SecondaryProps",
            "SecondaryLength",
            "number",
            unit="mm",
        ),
    ]
    first_root = _attempt(tmp_path, "first", bindings)
    repeated_root = _attempt(tmp_path, "repeated", bindings)
    second_root = _attempt(tmp_path, "second", list(reversed(bindings)))

    first_process = _run(
        first_root, integrity_request=_write_integrity_request(first_root)
    )
    repeated_process = _run(
        repeated_root, integrity_request=_write_integrity_request(repeated_root)
    )
    second_process = _run(
        second_root, integrity_request=_write_integrity_request(second_root)
    )

    for process in (first_process, repeated_process, second_process):
        assert process.returncode == 0, process.stdout + process.stderr

    first = (first_root / "outputs" / "prm.fact-evidence.json").read_bytes()
    repeated = (repeated_root / "outputs" / "prm.fact-evidence.json").read_bytes()
    second = (second_root / "outputs" / "prm.fact-evidence.json").read_bytes()

    assert first == repeated == second
    rendered = first.decode("utf-8")
    assert str(tmp_path) not in rendered
    assert "arbitrary" not in rendered


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
    ) == [SOURCE_DOCUMENT, SECONDARY_DOCUMENT]

    bindings = [
        _binding(SOURCE_RESOURCE, "Props", "MeasuredLength", "number", unit="mm"),
        _binding(SOURCE_RESOURCE, "Props", "Ratio", "number"),
        _binding(SOURCE_RESOURCE, "Props", "Count", "integer"),
        _binding(SOURCE_RESOURCE, "Props", "Enabled", "boolean"),
        _binding(SOURCE_RESOURCE, "Props", "PlainText", "string"),
    ]
    regenerated_root = tmp_path / "regenerated-attempt"
    shutil.copytree(regenerated, regenerated_root)
    (regenerated_root / "outputs").mkdir()
    (regenerated_root / "prm.fact-request.json").write_text(
        json.dumps({"schemaVersion": "1.0", "bindings": bindings}),
        encoding="utf-8",
    )
    regenerated_process = _run(
        regenerated_root,
        integrity_request=_write_integrity_request(regenerated_root),
    )
    assert regenerated_process.returncode == 0, (
        regenerated_process.stdout + regenerated_process.stderr
    )

    committed_root = _attempt(tmp_path, "committed", bindings)
    committed_process = _run(
        committed_root, integrity_request=_write_integrity_request(committed_root)
    )
    assert committed_process.returncode == 0, (
        committed_process.stdout + committed_process.stderr
    )

    assert (regenerated_root / "outputs" / "prm.fact-evidence.json").read_bytes() == (
        committed_root / "outputs" / "prm.fact-evidence.json"
    ).read_bytes()
