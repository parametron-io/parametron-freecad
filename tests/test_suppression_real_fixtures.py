"""Permanent real-FreeCAD suppression coverage for issue #1 (Stage 2).

These tests prove that ``parametron_freecad.execution.suppression
.apply_suppression_mutations(...)`` actually mutates native FreeCAD state
against the existing committed PartDesign mutation fixture. Every test
operates on a temporary copy of the committed fixture; the committed
``.FCStd`` bytes are proven unchanged before and after each test class runs.

This module deliberately does not exercise recompute, save, reopen,
visibility mutation, deletion, or schema-2 execute wiring: those remain out
of scope for the native suppression primitive under test.
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
RUNNER = Path(__file__).parent / "freecad_suppression_runner.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


class _RealFreeCADSuppressionTestCase(unittest.TestCase):
    """Shared real-freecadcmd plumbing for suppression fixture tests."""

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
            raise AssertionError("committed fixture bytes changed during suppression tests")

    def _copy_committed_fixture(self, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        target = destination_dir / FIXTURE_FILENAME
        shutil.copyfile(FIXTURE_PATH, target)
        return target

    def _run_suppression(
        self,
        fcstd_path: Path,
        object_names: list[str],
        mutations: list[dict[str, object]],
    ) -> dict[str, object]:
        request_path = fcstd_path.parent / "suppression-request.json"
        output_path = fcstd_path.parent / "suppression-output.json"
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


class TerminalChamferUnsuppressionTests(_RealFreeCADSuppressionTestCase):
    """Proves TerminalChamfer: Suppressed True -> False through production code."""

    def test_terminal_chamfer_unsuppression_through_production_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "chamfer")
            result = self._run_suppression(
                copy_path,
                ["TerminalChamfer"],
                [{"object": "TerminalChamfer", "suppressed": False}],
            )

        self.assertIsNone(result["error"], result["error"])

        before = result["before"]["TerminalChamfer"]
        after = result["after"]["TerminalChamfer"]

        self.assertEqual(before["suppressedPropertyType"], "App::PropertyBool")
        self.assertIs(before["suppressed"], True)
        self.assertEqual(after["suppressedPropertyType"], "App::PropertyBool")
        self.assertIs(after["suppressed"], False)

        # Visibility independence: suppression must not touch Visibility.
        self.assertEqual(before["visibilityPropertyType"], "App::PropertyBool")
        self.assertEqual(before["visibility"], after["visibility"])


class IntermediateFeatureSuppressionTests(_RealFreeCADSuppressionTestCase):
    """Proves at least one intermediate PartDesign feature: False -> True."""

    def _assert_false_to_true(self, object_name: str) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / object_name.lower())
            result = self._run_suppression(
                copy_path,
                [object_name],
                [{"object": object_name, "suppressed": True}],
            )

        self.assertIsNone(result["error"], result["error"])

        before = result["before"][object_name]
        after = result["after"][object_name]

        self.assertEqual(before["suppressedPropertyType"], "App::PropertyBool")
        self.assertIs(before["suppressed"], False)
        self.assertEqual(after["suppressedPropertyType"], "App::PropertyBool")
        self.assertIs(after["suppressed"], True)

        self.assertEqual(before["visibilityPropertyType"], "App::PropertyBool")
        self.assertEqual(before["visibility"], after["visibility"])

    def test_intermediate_pad_suppression_through_production_consumer(self) -> None:
        self._assert_false_to_true("IntermediatePad")

    def test_intermediate_pocket_suppression_through_production_consumer(self) -> None:
        self._assert_false_to_true("IntermediatePocket")


class IndependentFixtureCopyTests(_RealFreeCADSuppressionTestCase):
    """Proves suppression and unsuppression use independent fixture copies."""

    def test_suppression_and_unsuppression_do_not_share_a_fixture_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            unsuppress_copy = self._copy_committed_fixture(base / "unsuppress")
            suppress_copy = self._copy_committed_fixture(base / "suppress")

            self.assertNotEqual(unsuppress_copy, suppress_copy)

            unsuppress_result = self._run_suppression(
                unsuppress_copy,
                ["TerminalChamfer"],
                [{"object": "TerminalChamfer", "suppressed": False}],
            )
            suppress_result = self._run_suppression(
                suppress_copy,
                ["IntermediatePad"],
                [{"object": "IntermediatePad", "suppressed": True}],
            )

        self.assertIsNone(unsuppress_result["error"])
        self.assertIsNone(suppress_result["error"])
        self.assertIs(unsuppress_result["after"]["TerminalChamfer"]["suppressed"], False)
        self.assertIs(suppress_result["after"]["IntermediatePad"]["suppressed"], True)


class UnsupportedNativeTargetRealFreeCADTests(_RealFreeCADSuppressionTestCase):
    """Proves a real fixture object without native Suppressed is rejected cleanly.

    BaseSketch (Sketcher::SketchObject) genuinely lacks a native Suppressed
    property in this fixture; this is not a fabricated case.
    """

    def test_base_sketch_lacks_native_suppressed_support(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "unsupported")
            result = self._run_suppression(
                copy_path,
                ["BaseSketch"],
                [{"object": "BaseSketch", "suppressed": True}],
            )

        before = result["before"]["BaseSketch"]
        after = result["after"]["BaseSketch"]

        # Confirms the real native capability surface: no Suppressed property.
        self.assertIsNone(before["suppressedPropertyType"])
        self.assertIsNone(before["suppressed"])

        self.assertIsNotNone(result["error"])
        self.assertEqual(result["error"]["type"], "UnsupportedSuppressionTargetError")

        # No synthetic Suppressed property was created as a side effect.
        self.assertIsNone(after["suppressedPropertyType"])
        self.assertIsNone(after["suppressed"])
        self.assertEqual(before["visibility"], after["visibility"])


class OriginalFixtureIntegrityTests(_RealFreeCADSuppressionTestCase):
    """Proves suppression tests never modify the committed fixture bytes."""

    def test_committed_fixture_unchanged_after_suppression_and_unsuppression(self) -> None:
        before = _sha256(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "integrity")
            self._run_suppression(
                copy_path,
                ["TerminalChamfer"],
                [{"object": "TerminalChamfer", "suppressed": False}],
            )
        after = _sha256(FIXTURE_PATH)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
