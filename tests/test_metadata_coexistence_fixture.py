"""Permanent real-FreeCAD contract tests for the coexistence fixture.

These tests lock the derived ``metadata-coexistence.FCStd`` fixture used by the
metadata mutation and observation end-to-end proof. They do not execute the
normal execute lifecycle; that proof lives in the real lifecycle test module.

The source fixture from the metadata mutation fixture bundle is intentionally
not modified by the derivation.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "metadata_mutation"
SOURCE_FIXTURE_PATH = FIXTURE_DIR / "input" / "metadata-source.FCStd"
FIXTURE_PATH = FIXTURE_DIR / "input" / "metadata-coexistence.FCStd"
GENERATOR = REPOSITORY_ROOT / "scripts" / "generate_metadata_coexistence_fixture.py"
RUNNER = Path(__file__).parent / "freecad_metadata_coexistence_fixture_runner.py"

SOURCE_FIXTURE_SHA256 = (
    "acfa263a582cb95d4c19e2711f241508b1f88e611ebca7a59c34a0d2b0b99f34"
)
EXPECTED_FIXTURE_SHA256 = (
    "b6a09b7f7092db0efb594026e8e6dc3eb5fff49fa78582851e2961e0e15910c0"
)

EXPECTED_DOCUMENT_NAME = "metadata_coexistence"
EXPECTED_DOCUMENT_LABEL = "metadata-coexistence"

EXPECTED_OBJECTS = {
    "MetadataBody": "PartDesign::Body",
    "ProfileSketch": "Sketcher::SketchObject",
    "Pad": "PartDesign::Pad",
    "DeletionMarker": "Part::Box",
    "Parameters": "App::VarSet",
}

EXPECTED_METADATA_PROPERTIES = {
    "material": {
        "present": True,
        "typeId": "App::PropertyString",
        "value": "PLA",
    },
    "tagged": {
        "present": True,
        "typeId": "App::PropertyBool",
        "value": False,
    },
    "mass": {
        "present": True,
        "typeId": "App::PropertyFloat",
        "value": 1.5,
    },
    "revision": {
        "present": True,
        "typeId": "App::PropertyInteger",
        "value": 1,
    },
    "tolerance": {
        "present": True,
        "typeId": "App::PropertyFloatConstraint",
        "value": 0.5,
    },
    "sequence": {
        "present": True,
        "typeId": "App::PropertyIntegerConstraint",
        "value": 10,
    },
    "measured_length": {
        "present": True,
        "typeId": "App::PropertyLength",
        "value": 12.5,
    },
}

EXPECTED_METADATA_GROUP_PROPERTIES = sorted(EXPECTED_METADATA_PROPERTIES)
EXPECTED_MISSING_PROPERTY = "supplier"
EXPECTED_READ_ONLY_PROPERTY = {
    "name": "_ExternalGeoVersion",
    "present": True,
    "typeId": "App::PropertyInteger",
    "writeRejected": True,
    "errorType": "AttributeError",
}
EXPECTED_BODY_SHAPE = {"isNull": False, "isValid": True, "solidCount": 1}
EXPECTED_MARKER_SHAPE = {"isNull": False, "isValid": True, "solidCount": 1}
EXPECTED_DELETION_MARKER = {
    "name": "DeletionMarker",
    "typeId": "Part::Box",
    "inList": [],
    "outList": [],
    "shape": EXPECTED_MARKER_SHAPE,
}
EXPECTED_DELETION_CONSUMER = {
    "ok": True,
    "markerPresentAfter": False,
    "bodyShape": EXPECTED_BODY_SHAPE,
}
EXPECTED_PARAMETER_GROUP = {
    "name": "Parameters",
    "typeId": "App::VarSet",
    "property": "pilotValue",
    "propertyTypeId": "App::PropertyFloat",
    "value": 10.0,
    "inList": [],
    "outList": [],
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CommittedMetadataCoexistenceFixtureHashLockTests(unittest.TestCase):
    """Pure-Python integrity lock. Requires no FreeCAD and never skips."""

    def test_committed_fixture_file_exists(self) -> None:
        self.assertTrue(FIXTURE_PATH.is_file(), f"missing fixture: {FIXTURE_PATH}")

    def test_committed_fixture_sha256_matches_locked_digest(self) -> None:
        self.assertEqual(_sha256(FIXTURE_PATH), EXPECTED_FIXTURE_SHA256)

    def test_committed_fixture_is_not_an_lfs_pointer(self) -> None:
        self.assertFalse(
            FIXTURE_PATH.read_bytes().startswith(
                b"version https://git-lfs.github.com/spec/v1"
            ),
            "fixture must be fetched from Git LFS before native tests run",
        )

    def test_source_metadata_fixture_remains_unchanged(self) -> None:
        self.assertEqual(_sha256(SOURCE_FIXTURE_PATH), SOURCE_FIXTURE_SHA256)

    def test_generator_is_present(self) -> None:
        self.assertTrue(GENERATOR.is_file(), f"missing generator: {GENERATOR}")


class _RealFreeCADCoexistenceFixtureTestCase(unittest.TestCase):
    """Shared real-freecadcmd plumbing for coexistence fixture tests."""

    @classmethod
    def setUpClass(cls) -> None:
        configured_host = os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd")
        cls.freecad_host = shutil.which(configured_host)
        if cls.freecad_host is None:
            message = (
                f"FreeCAD host {configured_host!r} unavailable outside the Nix shell"
            )
            if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
                raise AssertionError(message)
            raise unittest.SkipTest(message)
        cls.committed_fixture_sha256 = _sha256(FIXTURE_PATH)
        cls.committed_source_sha256 = _sha256(SOURCE_FIXTURE_PATH)

    @classmethod
    def tearDownClass(cls) -> None:
        if _sha256(FIXTURE_PATH) != cls.committed_fixture_sha256:
            raise AssertionError(
                "committed coexistence fixture bytes changed during tests"
            )
        if _sha256(SOURCE_FIXTURE_PATH) != cls.committed_source_sha256:
            raise AssertionError(
                "committed source fixture bytes changed during coexistence tests"
            )

    def _copy_committed_fixture(self, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        target = destination_dir / FIXTURE_PATH.name
        shutil.copyfile(FIXTURE_PATH, target)
        return target

    def _inspect(self, fcstd_path: Path) -> dict[str, object]:
        output = fcstd_path.parent / "metadata-coexistence-inventory.json"
        if output.exists():
            output.unlink()
        command = [
            self.freecad_host,
            "-P",
            str(REPOSITORY_ROOT),
            str(RUNNER),
            f"--pass={fcstd_path}",
            f"--pass={output}",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertNotIn(
            "Exception while processing file",
            completed.stderr,
            completed.stderr,
        )
        self.assertTrue(output.is_file(), completed.stderr + completed.stdout)
        return json.loads(output.read_text(encoding="utf-8"))

    def _assert_full_semantic_contract(self, inventory: dict[str, object]) -> None:
        self.assertEqual(inventory["documentName"], EXPECTED_DOCUMENT_NAME)
        self.assertEqual(inventory["documentLabel"], EXPECTED_DOCUMENT_LABEL)

        by_name = {item["name"]: item for item in inventory["objects"]}
        self.assertEqual(set(by_name), set(EXPECTED_OBJECTS))
        for name, expected_type_id in EXPECTED_OBJECTS.items():
            self.assertEqual(by_name[name]["typeId"], expected_type_id, name)

        self.assertEqual(inventory["bodyTip"], "Pad")
        self.assertEqual(inventory["padProfile"], "ProfileSketch")
        self.assertEqual(inventory["bodyShape"], EXPECTED_BODY_SHAPE)

        self.assertEqual(
            inventory["metadataProperties"],
            EXPECTED_METADATA_PROPERTIES,
        )
        self.assertEqual(
            inventory["metadataGroupProperties"],
            EXPECTED_METADATA_GROUP_PROPERTIES,
        )
        self.assertEqual(inventory["missingProperty"], EXPECTED_MISSING_PROPERTY)
        self.assertFalse(inventory["missingPropertyPresent"])
        self.assertEqual(
            inventory["readOnlyProperty"],
            EXPECTED_READ_ONLY_PROPERTY,
        )

        self.assertEqual(
            inventory["deletionMarker"],
            EXPECTED_DELETION_MARKER,
        )
        self.assertEqual(
            inventory["deletionConsumer"],
            EXPECTED_DELETION_CONSUMER,
        )
        self.assertEqual(
            inventory["parameterGroup"],
            EXPECTED_PARAMETER_GROUP,
        )


class CommittedMetadataCoexistenceFixtureTests(_RealFreeCADCoexistenceFixtureTestCase):
    """Proves the committed coexistence fixture itself against real FreeCAD."""

    def test_committed_fixture_matches_full_semantic_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "committed")
            inventory = self._inspect(copy_path)
        self._assert_full_semantic_contract(inventory)

    def test_committed_fixture_unchanged_after_real_freecad_inspection(self) -> None:
        before = _sha256(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "inspect")
            self._inspect(copy_path)
        after = _sha256(FIXTURE_PATH)
        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_FIXTURE_SHA256)


if __name__ == "__main__":
    unittest.main()
