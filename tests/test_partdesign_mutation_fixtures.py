"""Permanent Task 1 fixture-contract tests for the PartDesign mutation fixture.

These tests lock the committed fixture and its generator as a stable
foundation for later Parametron mutation-runtime work (suppress, unsuppress,
hide, unhide, safe delete, unsafe-delete rejection). They intentionally do
NOT execute any of those runtime behaviors; they only prove the fixture and
generator preconditions those behaviors will depend on.
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
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "partdesign_mutations"
FIXTURE_FILENAME = "partdesign-mutations.FCStd"
FIXTURE_PATH = FIXTURE_DIR / FIXTURE_FILENAME
GENERATOR = REPOSITORY_ROOT / "scripts" / "generate_partdesign_mutation_fixtures.py"
RUNNER = Path(__file__).parent / "freecad_partdesign_mutation_fixture_runner.py"

# Locks drift in the exact committed asset. This is an integrity lock only:
# it does NOT assert that fresh generator runs reproduce identical FCStd
# archive bytes. See test_generator_two_independent_runs_are_semantically_reproducible.
EXPECTED_FIXTURE_SHA256 = (
    "7187abe907ca6240bdc7cd07fb5ce7a52cf9192e3ba6d6153c581f18b328057a"
)

EXPECTED_PERSISTED_DOCUMENT_NAME = "partdesign_mutations"
EXPECTED_PERSISTED_DOCUMENT_LABEL = "partdesign-mutations"

EXPECTED_TYPE_IDS = {
    "MutationBody": "PartDesign::Body",
    "BaseSketch": "Sketcher::SketchObject",
    "IntermediatePad": "PartDesign::Pad",
    "PocketSketch": "Sketcher::SketchObject",
    "IntermediatePocket": "PartDesign::Pocket",
    "TerminalChamfer": "PartDesign::Chamfer",
    "SafeDeleteMarker": "PartDesign::Feature",
}

EXPECTED_SUPPRESSED_STATES = {
    "IntermediatePad": False,
    "IntermediatePocket": False,
    "TerminalChamfer": True,
}

EXPECTED_VISIBILITY_STATES = {
    "MutationBody": True,
    "BaseSketch": False,
    "IntermediatePad": False,
    "PocketSketch": False,
    "IntermediatePocket": False,
    "TerminalChamfer": False,
    "SafeDeleteMarker": False,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CommittedFixtureHashLockTests(unittest.TestCase):
    """Pure-Python integrity lock. Requires no FreeCAD and never skips."""

    def test_committed_fixture_file_exists(self) -> None:
        self.assertTrue(FIXTURE_PATH.is_file(), f"missing fixture: {FIXTURE_PATH}")

    def test_committed_fixture_sha256_matches_locked_digest(self) -> None:
        # This proves the committed asset has not drifted. It intentionally
        # does not compare against a freshly regenerated FCStd's digest:
        # the generator's contract is semantic reproducibility, not FCStd
        # archive byte-reproducibility.
        self.assertEqual(_sha256(FIXTURE_PATH), EXPECTED_FIXTURE_SHA256)


class _RealFreeCADFixtureTestCase(unittest.TestCase):
    """Shared real-freecadcmd plumbing for fixture and generator tests."""

    @classmethod
    def setUpClass(cls) -> None:
        configured_host = os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd")
        cls.freecad_host = shutil.which(configured_host)
        if cls.freecad_host is None:
            message = f"FreeCAD host {configured_host!r} unavailable outside the Nix shell"
            if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
                raise AssertionError(message)
            raise unittest.SkipTest(message)
        cls.committed_fixture_sha256 = _sha256(FIXTURE_PATH)

    @classmethod
    def tearDownClass(cls) -> None:
        if _sha256(FIXTURE_PATH) != cls.committed_fixture_sha256:
            raise AssertionError("committed fixture bytes changed during tests")

    def _copy_committed_fixture(self, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        target = destination_dir / FIXTURE_FILENAME
        shutil.copyfile(FIXTURE_PATH, target)
        return target

    def _inspect(self, fcstd_path: Path) -> dict[str, object]:
        output = fcstd_path.parent / "semantic-inventory.json"
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
            command, capture_output=True, text=True, timeout=60, check=False
        )
        self.assertNotIn(
            "Exception while processing file",
            completed.stderr,
            completed.stderr,
        )
        self.assertTrue(output.is_file(), completed.stderr + completed.stdout)
        return json.loads(output.read_text(encoding="utf-8"))

    def _assert_full_semantic_contract(self, inventory: dict[str, object]) -> None:
        by_name = {item["name"]: item for item in inventory["objects"]}

        # (2) exact semantic-role inventory: no substitution, no missing,
        # no additional objects, and internal names rather than labels.
        self.assertEqual(set(by_name), set(EXPECTED_TYPE_IDS))
        for name, expected_type_id in EXPECTED_TYPE_IDS.items():
            self.assertEqual(by_name[name]["typeId"], expected_type_id, name)

        # document identity is part of the generator's stable contract.
        self.assertEqual(inventory["documentName"], EXPECTED_PERSISTED_DOCUMENT_NAME)
        self.assertEqual(inventory["documentLabel"], EXPECTED_PERSISTED_DOCUMENT_LABEL)

        # (5) Body / feature-history semantics.
        self.assertEqual(inventory["bodyTip"], "TerminalChamfer")
        self.assertEqual(inventory["padProfile"], "BaseSketch")
        self.assertIsNone(inventory["padBaseFeature"])
        self.assertEqual(inventory["pocketProfile"], "PocketSketch")
        self.assertEqual(inventory["pocketBaseFeature"], "IntermediatePad")
        self.assertEqual(inventory["chamferBase"], "IntermediatePocket")
        self.assertIn("IntermediatePad", by_name["BaseSketch"]["inList"])
        self.assertIn("IntermediatePocket", by_name["IntermediatePad"]["inList"])

        # (6) persisted suppression preconditions, proven as native bools.
        for name, expected_suppressed in EXPECTED_SUPPRESSED_STATES.items():
            self.assertEqual(
                by_name[name]["suppressedPropertyType"], "App::PropertyBool", name
            )
            self.assertEqual(by_name[name]["suppressed"], expected_suppressed, name)

        # (7) visibility preconditions, proven as native bools (no GUI/ViewObject).
        for name, expected_visible in EXPECTED_VISIBILITY_STATES.items():
            self.assertEqual(
                by_name[name]["visibilityPropertyType"], "App::PropertyBool", name
            )
            self.assertEqual(by_name[name]["visibility"], expected_visible, name)

        # (8) safe-delete structural role: unreferenced in both directions.
        self.assertEqual(by_name["SafeDeleteMarker"]["inList"], [])
        self.assertEqual(by_name["SafeDeleteMarker"]["outList"], [])

        # (10) reopened Body shape health.
        self.assertFalse(inventory["bodyShape"]["isNull"])
        self.assertTrue(inventory["bodyShape"]["isValid"])
        self.assertEqual(inventory["bodyShape"]["solidCount"], 1)


class CommittedPartDesignMutationFixtureTests(_RealFreeCADFixtureTestCase):
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


class PartDesignMutationGeneratorContractTests(_RealFreeCADFixtureTestCase):
    """Proves the generator's success path, reproducibility, and CLI safety."""

    def _generate(self, output: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            self.assertNotIn("Exception while processing file", completed.stderr, completed.stderr)

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

    def test_generator_two_independent_runs_are_semantically_reproducible(self) -> None:
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

        # Compare semantic facts only. FCStd archive byte equality between
        # run-a and run-b is NOT required and is never asserted here.
        self.assertEqual(inventory_a, inventory_b)
        self._assert_full_semantic_contract(inventory_a)
        self._assert_full_semantic_contract(inventory_b)

    def _assert_generation_rejected(
        self,
        completed: subprocess.CompletedProcess[str],
        expected_message_fragment: str,
        output: Path,
    ) -> None:
        self.assertIn("Exception while processing file", completed.stderr, completed.stderr)
        self.assertIn(expected_message_fragment, completed.stderr, completed.stderr)
        self.assertNotIn('"reproducibility"', completed.stdout)
        self.assertFalse(output.exists(), f"generator published rejected output: {output}")

    def test_generator_rejects_relative_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            relative_name = "relative-fixture-output"
            command = [self.freecad_host, str(GENERATOR), f"--pass={relative_name}"]
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=60, check=False, cwd=str(cwd)
            )
            self._assert_generation_rejected(
                completed, "must be absolute", cwd / relative_name
            )

    def test_generator_rejects_existing_destination_without_modifying_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            existing = Path(temporary) / "existing"
            existing.mkdir()
            sentinel = existing / "sentinel.txt"
            sentinel.write_text("do-not-touch", encoding="utf-8")
            before = _sha256(sentinel)

            completed = self._generate(existing)

            self.assertIn("Exception while processing file", completed.stderr, completed.stderr)
            self.assertIn("already exists", completed.stderr, completed.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "do-not-touch")
            self.assertEqual(_sha256(sentinel), before)
            self.assertEqual(sorted(p.name for p in existing.iterdir()), ["sentinel.txt"])

    def test_generator_rejects_missing_output_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            command = [self.freecad_host, str(GENERATOR)]
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=60, check=False, cwd=str(cwd)
            )
            self.assertIn("Exception while processing file", completed.stderr, completed.stderr)
            self.assertIn("exactly one --pass=", completed.stderr, completed.stderr)
            self.assertNotIn('"reproducibility"', completed.stdout)
            self.assertEqual(list(cwd.iterdir()), [])

    def test_generator_rejects_multiple_output_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path(temporary)
            first = cwd / "first-destination"
            second = cwd / "second-destination"
            command = [
                self.freecad_host,
                str(GENERATOR),
                f"--pass={first}",
                f"--pass={second}",
            ]
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=60, check=False, cwd=str(cwd)
            )
            self.assertIn("Exception while processing file", completed.stderr, completed.stderr)
            self.assertIn("exactly one --pass=", completed.stderr, completed.stderr)
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())

    def test_generator_rejects_execution_outside_nix_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "nix-guard-output"
            env = dict(os.environ)
            env.pop("IN_NIX_SHELL", None)
            completed = self._generate(output, env=env)
            self._assert_generation_rejected(
                completed, "must run inside nix develop", output
            )


if __name__ == "__main__":
    unittest.main()
