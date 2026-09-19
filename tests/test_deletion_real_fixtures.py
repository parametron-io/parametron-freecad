"""Permanent real-FreeCAD coverage for issue #4 native deletion.

These tests prove that ``parametron_freecad.execution.deletion
.apply_deletion_mutations(...)`` performs genuine native FreeCAD deletion,
dependency rejection, and post-delete validity enforcement, against the
existing committed PartDesign mutation fixture and a fresh test-owned
in-memory document.

Every fixture-based test operates on a temporary copy of the committed
fixture; the committed ``.FCStd`` bytes are proven unchanged before and
after each test class runs. The invalid-post-delete-state proof creates its
document entirely in memory and never touches the committed fixture file.

This module deliberately does not exercise suppression, visibility
mutation, save/reopen, or schema-2 execute wiring: those remain out of
scope for the native deletion consumer under test.
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
RUNNER = Path(__file__).parent / "freecad_deletion_runner.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


class _RealFreeCADDeletionTestCase(unittest.TestCase):
    """Shared real-freecadcmd plumbing for deletion fixture tests."""

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
            raise AssertionError("committed fixture bytes changed during deletion tests")

    def _copy_committed_fixture(self, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        target = destination_dir / FIXTURE_FILENAME
        shutil.copyfile(FIXTURE_PATH, target)
        return target

    def _run(self, request: dict[str, object], work_dir: Path) -> dict[str, object]:
        work_dir.mkdir(parents=True, exist_ok=True)
        request_path = work_dir / "request.json"
        output_path = work_dir / "output.json"
        if output_path.exists():
            output_path.unlink()
        request_path.write_bytes(_canonical_bytes(request))
        command = [
            self.freecad_host,
            "-P",
            str(REPOSITORY_ROOT),
            str(RUNNER),
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

    def _run_fixture(
        self,
        fcstd_path: Path,
        object_names: list[str],
        mutations: list[dict[str, object]],
        work_dir: Path,
    ) -> dict[str, object]:
        return self._run(
            {
                "mode": "fixture",
                "sourcePath": str(fcstd_path),
                "objects": object_names,
                "mutations": mutations,
            },
            work_dir,
        )

    def _run_invalid_state(self, work_dir: Path) -> dict[str, object]:
        return self._run({"mode": "invalid_state"}, work_dir)


class SafeFixtureDeletionTests(_RealFreeCADDeletionTestCase):
    """Proves SafeDeleteMarker is genuinely deletable through production code."""

    def test_safe_delete_marker_is_removed_through_production_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copy_path = self._copy_committed_fixture(base / "safe")
            result = self._run_fixture(
                copy_path,
                ["SafeDeleteMarker", "MutationBody"],
                [{"object": "SafeDeleteMarker"}],
                base / "work",
            )

        self.assertIsNone(result["error"], result["error"])

        # Existed natively before deletion.
        self.assertIsNotNone(result["before"]["SafeDeleteMarker"])
        self.assertEqual(
            result["before"]["SafeDeleteMarker"]["typeId"], "PartDesign::Feature"
        )
        self.assertIn("SafeDeleteMarker", result["beforeInventory"])

        # document.getObject("SafeDeleteMarker") is None afterward.
        self.assertIsNone(result["after"]["SafeDeleteMarker"])
        self.assertNotIn("SafeDeleteMarker", result["afterInventory"])

        # MutationBody survives and reports non-null, native-valid Shape
        # evidence via the recompute the production consumer performed.
        self.assertIsNotNone(result["after"]["MutationBody"])
        self.assertEqual(result["after"]["MutationBody"]["typeId"], "PartDesign::Body")
        self.assertIn("MutationBody", result["afterInventory"])

        # No unrelated fixture objects disappeared: exactly one object
        # (SafeDeleteMarker) is missing from the after inventory.
        before_set = set(result["beforeInventory"])
        after_set = set(result["afterInventory"])
        self.assertEqual(before_set - after_set, {"SafeDeleteMarker"})
        self.assertEqual(after_set - before_set, set())

    def test_committed_fixture_bytes_unchanged_after_safe_deletion(self) -> None:
        before = _sha256(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copy_path = self._copy_committed_fixture(base / "safe-integrity")
            self._run_fixture(
                copy_path,
                ["SafeDeleteMarker"],
                [{"object": "SafeDeleteMarker"}],
                base / "work",
            )
        after = _sha256(FIXTURE_PATH)
        self.assertEqual(before, after)


class UnsafeFixtureDeletionTests(_RealFreeCADDeletionTestCase):
    """Proves BaseSketch is rejected because IntermediatePad depends on it."""

    def test_base_sketch_deletion_is_rejected_through_production_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copy_path = self._copy_committed_fixture(base / "unsafe")
            result = self._run_fixture(
                copy_path,
                ["BaseSketch", "IntermediatePad"],
                [{"object": "BaseSketch"}],
                base / "work",
            )

        self.assertIsNotNone(result["error"])
        self.assertEqual(result["error"]["type"], "UnsafeDeletionTargetError")
        self.assertIn("BaseSketch", result["error"]["message"])
        self.assertIn("IntermediatePad", result["error"]["message"])

        # Both objects remain present; no native removal occurred.
        self.assertIsNotNone(result["after"]["BaseSketch"])
        self.assertEqual(result["after"]["BaseSketch"]["typeId"], "Sketcher::SketchObject")
        self.assertIsNotNone(result["after"]["IntermediatePad"])
        self.assertEqual(result["after"]["IntermediatePad"]["typeId"], "PartDesign::Pad")

        # The fixture copy's object inventory is completely unchanged by the
        # rejected request.
        self.assertEqual(result["beforeInventory"], result["afterInventory"])

    def test_committed_fixture_bytes_unchanged_after_unsafe_rejection(self) -> None:
        before = _sha256(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copy_path = self._copy_committed_fixture(base / "unsafe-integrity")
            self._run_fixture(
                copy_path,
                ["BaseSketch"],
                [{"object": "BaseSketch"}],
                base / "work",
            )
        after = _sha256(FIXTURE_PATH)
        self.assertEqual(before, after)


class MissingTargetRealFreeCADTests(_RealFreeCADDeletionTestCase):
    """Proves a nonexistent exact native name fails through the controlled boundary."""

    def test_missing_target_produces_controlled_failure_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copy_path = self._copy_committed_fixture(base / "missing")
            result = self._run_fixture(
                copy_path,
                ["SafeDeleteMarker"],
                [{"object": "DoesNotExistAnywhere"}],
                base / "work",
            )

        self.assertIsNotNone(result["error"])
        self.assertEqual(result["error"]["type"], "DeletionTargetNotFoundError")
        self.assertIn("DoesNotExistAnywhere", result["error"]["message"])

        # No mutation occurred: inventory is unchanged.
        self.assertEqual(result["beforeInventory"], result["afterInventory"])
        self.assertIsNotNone(result["after"]["SafeDeleteMarker"])

    def test_committed_fixture_bytes_unchanged_after_missing_target(self) -> None:
        before = _sha256(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copy_path = self._copy_committed_fixture(base / "missing-integrity")
            self._run_fixture(
                copy_path,
                [],
                [{"object": "DoesNotExistAnywhere"}],
                base / "work",
            )
        after = _sha256(FIXTURE_PATH)
        self.assertEqual(before, after)


class InvalidPostDeleteNativeStateTests(_RealFreeCADDeletionTestCase):
    """Proves the consumer cannot report success when post-delete Body state is invalid.

    Uses a fresh test-owned, in-memory document (never derived from or
    touching the committed fixture) containing an unreferenced
    ``App::DocumentObjectGroup`` deletion candidate and a genuinely invalid
    (empty, freshly-recomputed) ``PartDesign::Body``. The removable object
    itself has no relationship whatsoever to the empty Body; this proves the
    production consumer reaches and enforces the document-level native
    validity boundary on the resulting post-operation document state, not
    that the deleted object caused the Body's invalidity.
    """

    def test_invalid_body_state_prevents_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = self._run_invalid_state(Path(temporary))

        self.assertIsNotNone(result["error"])
        self.assertEqual(result["error"]["type"], "DeletionValidityError")
        self.assertEqual(result["error"]["causeType"], "InvalidNativeCadStateError")
        self.assertIn("EmptyBody", result["error"]["message"])
        self.assertIn("null", result["error"]["message"])

        # Destructive no-rollback semantics: the safely removable object was
        # actually removed even though the overall deletion entry reports
        # failure via the post-delete validity boundary.
        self.assertFalse(result["safeRemovableStillPresent"])
        self.assertTrue(result["emptyBodyStillPresent"])

    def test_invalid_state_probe_never_touches_committed_fixture(self) -> None:
        before = _sha256(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            self._run_invalid_state(Path(temporary))
        after = _sha256(FIXTURE_PATH)
        self.assertEqual(before, after)


class RepeatedRunDeterminismTests(_RealFreeCADDeletionTestCase):
    """Proves stable classification and diagnostics across independent processes.

    Each sub-test launches two fully independent freecadcmd processes and
    compares the normalized, test-observed JSON results. No temporary path
    or other environmental noise is compared.
    """

    def test_safe_deletion_result_is_stable_across_independent_processes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copy_a = self._copy_committed_fixture(base / "run-a")
            copy_b = self._copy_committed_fixture(base / "run-b")
            result_a = self._run_fixture(
                copy_a,
                ["SafeDeleteMarker", "MutationBody"],
                [{"object": "SafeDeleteMarker"}],
                base / "work-a",
            )
            result_b = self._run_fixture(
                copy_b,
                ["SafeDeleteMarker", "MutationBody"],
                [{"object": "SafeDeleteMarker"}],
                base / "work-b",
            )

        self.assertEqual(result_a["error"], result_b["error"])
        self.assertEqual(result_a["after"], result_b["after"])
        self.assertEqual(result_a["afterInventory"], result_b["afterInventory"])

    def test_unsafe_rejection_result_is_stable_across_independent_processes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copy_a = self._copy_committed_fixture(base / "run-a")
            copy_b = self._copy_committed_fixture(base / "run-b")
            result_a = self._run_fixture(
                copy_a,
                ["BaseSketch", "IntermediatePad"],
                [{"object": "BaseSketch"}],
                base / "work-a",
            )
            result_b = self._run_fixture(
                copy_b,
                ["BaseSketch", "IntermediatePad"],
                [{"object": "BaseSketch"}],
                base / "work-b",
            )

        self.assertEqual(result_a["error"], result_b["error"])
        self.assertEqual(result_a["after"], result_b["after"])
        self.assertEqual(result_a["afterInventory"], result_b["afterInventory"])

    def test_invalid_state_diagnostic_is_stable_across_independent_processes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            result_a = self._run_invalid_state(base / "work-a")
            result_b = self._run_invalid_state(base / "work-b")

        self.assertEqual(result_a["error"], result_b["error"])
        self.assertEqual(
            result_a["safeRemovableStillPresent"], result_b["safeRemovableStillPresent"]
        )
        self.assertEqual(
            result_a["emptyBodyStillPresent"], result_b["emptyBodyStillPresent"]
        )


class FixtureIntegrityTests(_RealFreeCADDeletionTestCase):
    """Proves the committed fixture is never modified by deletion tests."""

    def test_committed_fixture_unchanged_after_full_workflow(self) -> None:
        before = _sha256(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            safe_copy = self._copy_committed_fixture(base / "safe")
            unsafe_copy = self._copy_committed_fixture(base / "unsafe")
            self._run_fixture(
                safe_copy,
                ["SafeDeleteMarker"],
                [{"object": "SafeDeleteMarker"}],
                base / "work-safe",
            )
            self._run_fixture(
                unsafe_copy,
                ["BaseSketch"],
                [{"object": "BaseSketch"}],
                base / "work-unsafe",
            )
        after = _sha256(FIXTURE_PATH)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
