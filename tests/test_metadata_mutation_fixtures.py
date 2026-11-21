"""Permanent real-FreeCAD metadata mutation fixture contract tests.

These tests lock the committed fixture, its generator, and its native metadata
property contract. They prove the fixture's starting structure only; they do
not execute metadata mutation or observation.
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
FIXTURE_FILENAME = "metadata-source.FCStd"
FIXTURE_PATH = FIXTURE_DIR / "input" / FIXTURE_FILENAME
GENERATOR = REPOSITORY_ROOT / "scripts" / "generate_metadata_mutation_fixtures.py"
RUNNER = Path(__file__).parent / "freecad_metadata_mutation_fixture_runner.py"

# Locks drift in the exact committed asset. This is an integrity lock only:
# it does not assert that fresh generator runs reproduce identical FCStd
# archive bytes.
EXPECTED_FIXTURE_SHA256 = (
    "acfa263a582cb95d4c19e2711f241508b1f88e611ebca7a59c34a0d2b0b99f34"
)

EXPECTED_DOCUMENT_NAME = "metadata_source"
EXPECTED_DOCUMENT_LABEL = "metadata-source"

EXPECTED_OBJECTS = {
    "MetadataBody": "PartDesign::Body",
    "ProfileSketch": "Sketcher::SketchObject",
    "Pad": "PartDesign::Pad",
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CommittedMetadataMutationFixtureHashLockTests(unittest.TestCase):
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


class _RealFreeCADMetadataFixtureTestCase(unittest.TestCase):
    """Shared real-freecadcmd plumbing for metadata fixture tests."""

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

    @classmethod
    def tearDownClass(cls) -> None:
        if _sha256(FIXTURE_PATH) != cls.committed_fixture_sha256:
            raise AssertionError(
                "committed fixture bytes changed during metadata fixture tests"
            )

    def _copy_committed_fixture(self, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        target = destination_dir / FIXTURE_FILENAME
        shutil.copyfile(FIXTURE_PATH, target)
        return target

    def _inspect(self, fcstd_path: Path) -> dict[str, object]:
        output = fcstd_path.parent / "metadata-inventory.json"
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
        self.assertEqual(
            inventory["bodyShape"],
            {"isNull": False, "isValid": True, "solidCount": 1},
        )

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


class CommittedMetadataMutationFixtureTests(_RealFreeCADMetadataFixtureTestCase):
    """Proves the committed fixture itself against real FreeCAD."""

    def test_committed_fixture_matches_full_semantic_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "committed")
            inventory = self._inspect(copy_path)
        self._assert_full_semantic_contract(inventory)

    def test_committed_fixture_unchanged_immediately_after_real_freecad_inspection(
        self,
    ) -> None:
        before = _sha256(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "inspect")
            self._inspect(copy_path)
        after = _sha256(FIXTURE_PATH)
        self.assertEqual(before, after)
        self.assertEqual(after, EXPECTED_FIXTURE_SHA256)


class MetadataMutationGeneratorContractTests(_RealFreeCADMetadataFixtureTestCase):
    """Proves the generator success path, reproducibility, and CLI safety."""

    def _generate(
        self,
        output: Path,
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [self.freecad_host, str(GENERATOR), f"--pass={output}"]
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=env,
            cwd=str(output.parent),
        )

    def test_generator_success_path_matches_full_semantic_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "generated"
            completed = self._generate(output)
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr + completed.stdout,
            )
            self.assertNotIn(
                "Exception while processing file",
                completed.stderr,
                completed.stderr,
            )

            stdout_payload = json.loads(completed.stdout.strip().splitlines()[0])
            self.assertEqual(stdout_payload["reproducibility"], "semantic")
            self.assertEqual(stdout_payload["documents"], [FIXTURE_FILENAME])
            self.assertEqual(stdout_payload["output"], str(output))

            self.assertTrue(output.is_dir())
            generated_fcstd = output / FIXTURE_FILENAME
            self.assertTrue(generated_fcstd.is_file())
            self.assertEqual(list(output.rglob("*.FCBak")), [])

            inventory = self._inspect(generated_fcstd)
        self._assert_full_semantic_contract(inventory)

    def test_generator_two_independent_runs_are_semantically_reproducible(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            run_a_dir = base / "run-a"
            run_b_dir = base / "run-b"

            completed_a = self._generate(run_a_dir)
            self.assertEqual(completed_a.returncode, 0, completed_a.stderr)
            completed_b = self._generate(run_b_dir)
            self.assertEqual(completed_b.returncode, 0, completed_b.stderr)

            inventory_a = self._inspect(run_a_dir / FIXTURE_FILENAME)
            inventory_b = self._inspect(run_b_dir / FIXTURE_FILENAME)

        self.assertEqual(inventory_a, inventory_b)
        self._assert_full_semantic_contract(inventory_a)
        self._assert_full_semantic_contract(inventory_b)

    def _assert_generation_rejected(
        self,
        completed: subprocess.CompletedProcess[str],
        expected_message_fragment: str,
        output: Path,
    ) -> None:
        self.assertIn(
            "Exception while processing file",
            completed.stderr,
            completed.stderr,
        )
        self.assertIn(expected_message_fragment, completed.stderr, completed.stderr)
        self.assertNotIn('"reproducibility"', completed.stdout)
        self.assertFalse(
            output.exists(), f"generator published rejected output: {output}"
        )

    def test_generator_rejects_relative_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            relative_name = "relative-metadata-fixture"
            command = [
                self.freecad_host,
                str(GENERATOR),
                f"--pass={relative_name}",
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                cwd=str(cwd),
            )
            self._assert_generation_rejected(
                completed,
                "must be absolute",
                cwd / relative_name,
            )

    def test_generator_rejects_existing_destination_without_modifying_it(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            existing = Path(temporary) / "existing"
            existing.mkdir()
            sentinel = existing / "sentinel.txt"
            sentinel.write_text("do not modify", encoding="utf-8")

            completed = self._generate(existing)

            self.assertIn(
                "Exception while processing file",
                completed.stderr,
                completed.stderr,
            )
            self.assertIn(
                "output already exists",
                completed.stderr,
                completed.stderr,
            )
            self.assertEqual(
                sentinel.read_text(encoding="utf-8"),
                "do not modify",
            )
            self.assertEqual(
                sorted(path.name for path in existing.iterdir()),
                ["sentinel.txt"],
            )

    def test_generator_rejects_missing_output_argument(self) -> None:
        completed = subprocess.run(
            [self.freecad_host, str(GENERATOR)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertIn(
            "Exception while processing file",
            completed.stderr,
            completed.stderr,
        )
        self.assertIn(
            "exactly one --pass",
            completed.stderr,
            completed.stderr,
        )

    def test_generator_rejects_multiple_output_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            completed = subprocess.run(
                [
                    self.freecad_host,
                    str(GENERATOR),
                    f"--pass={first}",
                    f"--pass={second}",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            self.assertIn(
                "Exception while processing file",
                completed.stderr,
                completed.stderr,
            )
            self.assertIn(
                "exactly one --pass",
                completed.stderr,
                completed.stderr,
            )
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())

    def test_generator_rejects_execution_outside_nix_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "outside-nix"
            env = os.environ.copy()
            env.pop("IN_NIX_SHELL", None)
            completed = self._generate(output, env=env)
            self._assert_generation_rejected(
                completed,
                "inside nix develop",
                output,
            )


if __name__ == "__main__":
    unittest.main()
