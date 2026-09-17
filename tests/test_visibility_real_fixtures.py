"""Permanent real-FreeCAD visibility coverage for issue #2.

These tests prove that ``parametron_freecad.execution.visibility
.apply_visibility_mutations(...)`` actually mutates native FreeCAD state
against the existing committed PartDesign mutation fixture. Every test
operates on a temporary copy of the committed fixture; the committed
``.FCStd`` bytes are proven unchanged before and after each test class runs.

This module deliberately does not exercise recompute, save, reopen,
suppression mutation, deletion, or schema-2 execute wiring: those remain out
of scope for the native visibility primitive under test.

Per the committed fixture's semantic contract (see
``test_partdesign_mutation_fixtures.py``), every fixture object supports
native ``Visibility`` as ``App::PropertyBool``. There is therefore no
genuinely appropriate real-fixture object to prove the unsupported-native-
visibility-capability path without altering the committed fixture; that
path remains covered by the focused fake-FreeCAD tests in
``test_visibility.py``.
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
RUNNER = Path(__file__).parent / "freecad_visibility_runner.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


class _RealFreeCADVisibilityTestCase(unittest.TestCase):
    """Shared real-freecadcmd plumbing for visibility fixture tests."""

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
            raise AssertionError("committed fixture bytes changed during visibility tests")

    def _copy_committed_fixture(self, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        target = destination_dir / FIXTURE_FILENAME
        shutil.copyfile(FIXTURE_PATH, target)
        return target

    def _run_visibility(
        self,
        fcstd_path: Path,
        object_names: list[str],
        mutations: list[dict[str, object]],
    ) -> dict[str, object]:
        request_path = fcstd_path.parent / "visibility-request.json"
        output_path = fcstd_path.parent / "visibility-output.json"
        if output_path.exists():
            output_path.unlink()
        request_path.write_bytes(
            _canonical_bytes({"objects": object_names, "mutations": mutations})
        )
        command = [
            self.freecad_host,
            "-P",
            str(REPOSITORY_ROOT),
            str(RUNNER),
            f"--pass={fcstd_path}",
            f"--pass={request_path}",
            f"--pass={output_path}",
        ]
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=60, check=False
        )
        self.assertNotIn(
            "Exception while processing file",
            completed.stderr,
            completed.stderr,
        )
        self.assertTrue(output_path.is_file(), completed.stderr + completed.stdout)
        return json.loads(output_path.read_text(encoding="utf-8"))


class MutationBodyHideTests(_RealFreeCADVisibilityTestCase):
    """Proves MutationBody: Visibility True -> False through production code.

    MutationBody's persisted precondition (Visibility == True) is locked by
    test_partdesign_mutation_fixtures.EXPECTED_VISIBILITY_STATES.
    """

    def test_mutation_body_hide_through_production_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "hide")
            result = self._run_visibility(
                copy_path,
                ["MutationBody"],
                [{"object": "MutationBody", "visible": False}],
            )

        self.assertIsNone(result["error"], result["error"])

        before = result["before"]["MutationBody"]
        after = result["after"]["MutationBody"]

        self.assertEqual(before["visibilityPropertyType"], "App::PropertyBool")
        self.assertIs(before["visibility"], True)
        self.assertEqual(after["visibilityPropertyType"], "App::PropertyBool")
        self.assertIs(after["visibility"], False)


class BaseSketchUnhideTests(_RealFreeCADVisibilityTestCase):
    """Proves BaseSketch: Visibility False -> True through production code.

    BaseSketch's persisted precondition (Visibility == False) is locked by
    test_partdesign_mutation_fixtures.EXPECTED_VISIBILITY_STATES. BaseSketch
    is a genuinely appropriate unhide target: unlike suppression (where
    BaseSketch lacks native Suppressed support entirely), BaseSketch does
    support native App::PropertyBool Visibility in this fixture.
    """

    def test_base_sketch_unhide_through_production_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "unhide")
            result = self._run_visibility(
                copy_path,
                ["BaseSketch"],
                [{"object": "BaseSketch", "visible": True}],
            )

        self.assertIsNone(result["error"], result["error"])

        before = result["before"]["BaseSketch"]
        after = result["after"]["BaseSketch"]

        self.assertEqual(before["visibilityPropertyType"], "App::PropertyBool")
        self.assertIs(before["visibility"], False)
        self.assertEqual(after["visibilityPropertyType"], "App::PropertyBool")
        self.assertIs(after["visibility"], True)


class SuppressionIndependenceTests(_RealFreeCADVisibilityTestCase):
    """Proves visibility mutation leaves native Suppressed state unchanged.

    TerminalChamfer's persisted precondition (Suppressed == True) is locked
    by test_partdesign_mutation_fixtures.EXPECTED_SUPPRESSED_STATES, giving
    a meaningful independent-axis check: a non-default Suppressed value that
    a defective implementation could plausibly disturb.
    """

    def test_visibility_mutation_does_not_alter_suppressed_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "independence")
            result = self._run_visibility(
                copy_path,
                ["TerminalChamfer"],
                [{"object": "TerminalChamfer", "visible": True}],
            )

        self.assertIsNone(result["error"], result["error"])

        before = result["before"]["TerminalChamfer"]
        after = result["after"]["TerminalChamfer"]

        self.assertEqual(before["suppressedPropertyType"], "App::PropertyBool")
        self.assertIs(before["suppressed"], True)
        self.assertEqual(after["suppressedPropertyType"], "App::PropertyBool")
        self.assertIs(after["suppressed"], True)

        self.assertEqual(before["visibilityPropertyType"], "App::PropertyBool")
        self.assertIs(before["visibility"], False)
        self.assertIs(after["visibility"], True)


class MissingTargetRealFreeCADTests(_RealFreeCADVisibilityTestCase):
    """Proves a missing exact object name is rejected cleanly through real FreeCAD."""

    def test_missing_object_raises_target_not_found_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "missing")
            result = self._run_visibility(
                copy_path,
                ["DoesNotExist"],
                [{"object": "DoesNotExist", "visible": False}],
            )

        self.assertIsNone(result["before"]["DoesNotExist"])
        self.assertIsNotNone(result["error"])
        self.assertEqual(result["error"]["type"], "VisibilityTargetNotFoundError")
        self.assertIsNone(result["after"]["DoesNotExist"])


class OriginalFixtureIntegrityTests(_RealFreeCADVisibilityTestCase):
    """Proves visibility tests never modify the committed fixture bytes."""

    def test_committed_fixture_unchanged_after_hide_and_unhide(self) -> None:
        before = _sha256(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "integrity")
            self._run_visibility(
                copy_path,
                ["MutationBody"],
                [{"object": "MutationBody", "visible": False}],
            )
        after = _sha256(FIXTURE_PATH)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
