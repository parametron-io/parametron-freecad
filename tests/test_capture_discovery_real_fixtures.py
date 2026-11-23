"""Permanent real-FreeCAD capture discovery fixture tests.

These tests run ``freecadcmd`` against committed fixtures, invoke the
GUI-free discovery core on the live active document, and assert deterministic
native evidence. The committed fixtures must remain byte-for-byte unchanged and
discovery must not mark the open document as touched.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).parent / "fixtures"
RUNNER = Path(__file__).parent / "freecad_capture_discovery_fixture_runner.py"

METADATA_SOURCE = FIXTURE_ROOT / "metadata_mutation" / "input" / "metadata-source.FCStd"
METADATA_COEXISTENCE = (
    FIXTURE_ROOT / "metadata_mutation" / "input" / "metadata-coexistence.FCStd"
)
CANONICAL_CUBE = FIXTURE_ROOT / "canonical_lifecycle" / "input" / "cube.FCStd"
ASSEMBLY_ROOT = FIXTURE_ROOT / "assembly_occurrence" / "assembly-root.FCStd"

LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freecad_host() -> str:
    configured = os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd")
    host = shutil.which(configured)
    if host is not None:
        return host
    message = f"FreeCAD host {configured!r} unavailable outside the Nix shell"
    if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
        pytest.fail(message)
    pytest.skip(message)


def _run_discovery(fixture: Path, output_directory: Path) -> dict:
    assert fixture.is_file(), f"missing capture discovery fixture: {fixture}"
    assert not fixture.read_bytes().startswith(LFS_POINTER_PREFIX), (
        f"fixture must be fetched from Git LFS: {fixture}"
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    before_hash = _sha256(fixture)
    output_path = output_directory / "discovery.json"
    completed = subprocess.run(
        [
            _freecad_host(),
            "-P",
            str(REPOSITORY_ROOT),
            str(RUNNER),
            f"--pass={fixture}",
            f"--pass={output_path}",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "Exception while processing file" not in completed.stderr, completed.stderr
    assert _sha256(fixture) == before_hash, "committed fixture bytes changed"
    assert output_path.is_file(), completed.stderr + completed.stdout

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["source"]["unchanged"] is True
    assert payload["source"]["sha256BeforeOpen"] == before_hash
    assert payload["source"]["sha256AfterClose"] == before_hash
    # Discovery itself must not change the native touched state. Some fixture
    # documents are already touched by FreeCAD while restoring unresolved
    # external links, so only stability across discovery is asserted here.
    assert payload["document"]["touchedAfter"] == payload["document"]["touchedBefore"]
    assert "/home/" not in json.dumps(payload["discovery"], sort_keys=True)
    return payload


def _components(payload: dict) -> dict[str, dict]:
    return {item["nativeRef"]: item for item in payload["discovery"]["components"]}


def _features(payload: dict) -> dict[str, dict]:
    return {item["nativeRef"]: item for item in payload["discovery"]["features"]}


def _parameters(payload: dict) -> dict[str, dict]:
    return {item["nativeKey"]: item for item in payload["discovery"]["parameters"]}


def _metadata(payload: dict) -> dict[str, dict]:
    return {item["nativeKey"]: item for item in payload["discovery"]["metadata"]}


def test_single_part_fixture_synthesizes_document_root(tmp_path: Path) -> None:
    payload = _run_discovery(METADATA_SOURCE, tmp_path)
    discovery = payload["discovery"]

    assert payload["document"]["name"] == "metadata_source"
    assert payload["document"]["label"] == "metadata-source"
    assert payload["document"]["touchedBefore"] is False
    assert discovery["document"]["name"] == "metadata_source"
    assert discovery["document"]["label"] == "metadata-source"
    assert discovery["rootComponentNativeRef"] == "metadata_source"

    components = _components(payload)
    assert set(components) == {"metadata_source", "MetadataBody"}
    root = components["metadata_source"]
    assert root["synthetic"] is True
    assert root["kind"] == "assembly"
    assert root["cadType"] == "App::Document"
    assert root["parentNativeRef"] is None
    assert root["quantity"] == 1
    assert root["material"] == ""
    assert root["targetability"]["delete"] is False

    body_component = components["MetadataBody"]
    assert body_component["synthetic"] is False
    assert body_component["kind"] == "part"
    assert body_component["cadType"] == "PartDesign::Body"
    assert body_component["parentNativeRef"] == "metadata_source"
    assert body_component["targetability"]["hide"] is True
    assert body_component["targetability"]["delete"] is True

    features = _features(payload)
    assert set(features) == {"Pad", "ProfileSketch"}
    assert features["Pad"]["componentNativeRef"] == "MetadataBody"
    assert features["Pad"]["targetability"]["suppress"] is True
    assert features["Pad"]["targetability"]["delete"] is False
    assert features["Pad"]["targetability"]["deleteDependents"] == ["MetadataBody"]

    assert discovery["parameterGroups"] == []
    assert discovery["parameters"] == []

    metadata = _metadata(payload)
    assert set(metadata) == {
        "mass",
        "material",
        "measured_length",
        "revision",
        "sequence",
        "tagged",
        "tolerance",
    }
    assert metadata["material"]["currentValue"] == "PLA"
    assert metadata["tagged"]["currentValue"] is False
    assert metadata["mass"]["currentValue"] == 1.5
    assert metadata["revision"]["currentValue"] == 1
    assert metadata["tolerance"]["currentValue"] == 0.5
    assert metadata["sequence"]["currentValue"] == 10
    assert metadata["measured_length"]["supported"] is False
    assert (
        metadata["measured_length"]["unsupportedReason"]
        == "unsupported_native_metadata_type"
    )


def test_coexistence_fixture_discovers_parameters_and_delete_evidence(
    tmp_path: Path,
) -> None:
    payload = _run_discovery(METADATA_COEXISTENCE, tmp_path)
    discovery = payload["discovery"]

    assert payload["document"]["name"] == "metadata_coexistence"
    assert payload["document"]["touchedBefore"] is False
    assert discovery["rootComponentNativeRef"] == "metadata_coexistence"

    components = _components(payload)
    assert set(components) == {
        "metadata_coexistence",
        "DeletionMarker",
        "MetadataBody",
    }
    assert components["DeletionMarker"]["kind"] == "part"
    assert components["DeletionMarker"]["targetability"]["delete"] is True
    assert components["DeletionMarker"]["targetability"]["deleteDependents"] == []

    assert len(discovery["parameterGroups"]) == 1
    group = discovery["parameterGroups"][0]
    assert group["nativeRef"] == "Parameters"
    assert group["groupKind"] == "varset"
    assert group["ownerComponentNativeRef"] == "metadata_coexistence"

    parameters = _parameters(payload)
    assert set(parameters) == {"pilotValue"}
    pilot = parameters["pilotValue"]
    assert pilot["nativeTypeId"] == "App::PropertyFloat"
    assert pilot["valueType"] == "number"
    assert pilot["currentValue"] == 10.0
    assert pilot["unit"] is None
    assert pilot["supported"] is True
    assert pilot["observable"] is True
    assert pilot["writable"] is True

    metadata = _metadata(payload)
    assert set(metadata) == {
        "mass",
        "material",
        "measured_length",
        "revision",
        "sequence",
        "tagged",
        "tolerance",
    }
    assert metadata["measured_length"]["supported"] is False
    assert metadata["measured_length"]["nativeReadable"] is True


def test_cube_fixture_discovers_length_parameters_and_feature_set(
    tmp_path: Path,
) -> None:
    payload = _run_discovery(CANONICAL_CUBE, tmp_path)
    discovery = payload["discovery"]

    assert payload["document"]["name"] == "cube"
    assert payload["document"]["touchedBefore"] is False
    assert discovery["rootComponentNativeRef"] == "cube"

    components = _components(payload)
    assert set(components) == {
        "cube",
        "Body",
        "Body001",
        "Body002",
        "Body003",
    }
    for name in ("Body", "Body001", "Body002", "Body003"):
        assert components[name]["kind"] == "part"
        assert components[name]["parentNativeRef"] == "cube"

    features = _features(payload)
    assert len(features) == 16
    assert {
        "Sketch",
        "Pad",
        "Sketch001",
        "Pocket",
        "Chamfer",
        "Pad001",
        "Pocket001",
        "Fillet",
        "Pad002",
        "Pad003",
        "Pad004",
    }.issubset(set(features))
    assert features["Pad"]["componentNativeRef"] == "Body"
    assert features["Pad001"]["componentNativeRef"] == "Body001"
    assert features["Pad003"]["componentNativeRef"] == "Body002"
    assert features["Pad004"]["componentNativeRef"] == "Body003"

    assert len(discovery["parameterGroups"]) == 1
    group = discovery["parameterGroups"][0]
    assert group["nativeRef"] == "VarSet"
    assert group["groupKind"] == "varset"
    assert group["ownerComponentNativeRef"] == "cube"

    parameters = _parameters(payload)
    assert set(parameters) == {
        "boxChamfer",
        "boxHeight",
        "boxLength",
        "boxWidth",
        "holeDia",
    }
    expected = {
        "boxChamfer": 3.0,
        "boxHeight": 40.0,
        "boxLength": 50.0,
        "boxWidth": 30.0,
        "holeDia": 12.0,
    }
    for name, value in expected.items():
        candidate = parameters[name]
        assert candidate["nativeTypeId"] == "App::PropertyLength"
        assert candidate["nativeValueKind"] == "length"
        assert candidate["valueType"] == "number"
        assert candidate["currentValue"] == value
        assert candidate["unit"] == "mm"
        assert candidate["supported"] is True
        assert candidate["observable"] is True
        assert candidate["writable"] is True

    assert discovery["metadata"] == []


def test_assembly_fixture_discovers_assembly_components_and_excludes_links(
    tmp_path: Path,
) -> None:
    payload = _run_discovery(ASSEMBLY_ROOT, tmp_path)
    discovery = payload["discovery"]

    assert payload["document"]["name"] == "assembly_root"
    assert discovery["rootComponentNativeRef"] == "assembly_root"

    components = _components(payload)
    assert set(components) == {
        "assembly_root",
        "Assembly",
        "InternalBody",
        "SupportedAssembly",
    }
    assert components["Assembly"]["kind"] == "assembly"
    assert components["SupportedAssembly"]["kind"] == "assembly"
    assert components["InternalBody"]["kind"] == "part"
    assert components["InternalBody"]["parentNativeRef"] == "assembly_root"

    features = _features(payload)
    assert features == {}

    diagnostics = discovery["diagnostics"]
    codes = {item["code"] for item in diagnostics}
    assert "unsupported_link" in codes
    assert "unsupported_assembly_member" in codes
    assert "unsupported_object_type" in codes
    diagnostic_refs = {item["nativeRef"] for item in diagnostics}
    assert "Link01" in diagnostic_refs
    assert "NestedLink" in diagnostic_refs
    assert "Joints" in diagnostic_refs
    assert "Holder" in diagnostic_refs

    assert discovery["parameterGroups"] == []
    assert discovery["parameters"] == []
    assert discovery["metadata"] == []
    assert not any(
        name.startswith(
            (
                "Link",
                "Shared",
                "Cross",
                "Nested",
                "Array",
                "Marker",
                "Missing",
            )
        )
        for name in components
    )


def test_repeated_real_discovery_is_byte_identical(tmp_path: Path) -> None:
    first_payload = _run_discovery(CANONICAL_CUBE, tmp_path / "first")
    second_payload = _run_discovery(CANONICAL_CUBE, tmp_path / "second")

    assert json.dumps(first_payload["discovery"], sort_keys=True) == json.dumps(
        second_payload["discovery"], sort_keys=True
    )
