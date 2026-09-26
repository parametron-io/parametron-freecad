"""Permanent real-FreeCAD coverage for issue #3 post-mutation validity.

These tests prove that ``parametron_freecad.execution.post_mutation_validity``
observes genuine native FreeCAD evidence: healthy Body shape health and
native dependency relationships from the existing committed PartDesign
mutation fixture, and a genuinely invalid (null) native shape from a
freshly created, test-owned, empty ``PartDesign::Body`` that is never
persisted to or derived from the committed fixture.

Every fixture-based test operates on a temporary copy of the committed
fixture; the committed ``.FCStd`` bytes are proven unchanged before and
after each test class runs. The empty-Body invalid-state proof creates its
document entirely in memory and never touches the committed fixture file.

This module deliberately does not exercise deletion, suppression, visibility
mutation, save, or canonical execute wiring: those remain out of scope for
the read-only validity/dependency inspection primitives under test.
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
RUNNER = Path(__file__).parent / "freecad_post_mutation_validity_runner.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


class _RealFreeCADValidityTestCase(unittest.TestCase):
    """Shared real-freecadcmd plumbing for post-mutation validity tests."""

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
            raise AssertionError("committed fixture bytes changed during validity tests")

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

    def _run_inspect(
        self, fcstd_path: Path, object_names: list[str], work_dir: Path
    ) -> dict[str, object]:
        return self._run(
            {
                "mode": "inspect",
                "sourcePath": str(fcstd_path),
                "objects": object_names,
            },
            work_dir,
        )

    def _run_empty_body(self, work_dir: Path) -> dict[str, object]:
        return self._run({"mode": "empty_body"}, work_dir)


class HealthyFixtureShapeEvidenceTests(_RealFreeCADValidityTestCase):
    """Proves the fixture's supported Body reports native healthy state.

    Per the locked fixture contract in test_partdesign_mutation_fixtures.py,
    MutationBody's Shape is non-null, valid, and reports exactly one solid.
    That solid count is asserted here as a property of this specific locked
    fixture, not as a universal production validity rule.
    """

    def test_mutation_body_reports_healthy_native_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "healthy")
            payload = self._run_inspect(
                copy_path, ["MutationBody"], Path(temporary) / "run"
            )

        validity_runs = payload["results"]["MutationBody"]["validity"]
        for run in validity_runs:
            self.assertTrue(run["ok"], run)
            self.assertEqual(run["objectName"], "MutationBody")
            self.assertIs(run["isNull"], False)
            self.assertIs(run["isValid"], True)
            self.assertEqual(run["solidCount"], 1)

    def test_inspection_does_not_mutate_fixture_object_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "readonly")
            payload = self._run_inspect(
                copy_path,
                ["MutationBody", "TerminalChamfer", "SafeDeleteMarker"],
                Path(temporary) / "run",
            )

        self.assertEqual(payload["before"], payload["after"])


class RealDependencyEvidenceTests(_RealFreeCADValidityTestCase):
    """Proves native dependency inspection against the fixture's locked graph.

    Uses only relationships already established as contractual by
    test_partdesign_mutation_fixtures.py: SafeDeleteMarker is unreferenced in
    both directions, and BaseSketch is depended upon by IntermediatePad (via
    its native InList).
    """

    def test_safe_delete_marker_has_no_native_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "marker")
            payload = self._run_inspect(
                copy_path, ["SafeDeleteMarker"], Path(temporary) / "run"
            )

        for run in payload["results"]["SafeDeleteMarker"]["dependency"]:
            self.assertTrue(run["ok"], run)
            self.assertEqual(run["dependents"], [])
            self.assertEqual(run["dependencies"], [])

    def test_base_sketch_dependency_chain_is_observed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "sketch")
            payload = self._run_inspect(
                copy_path, ["BaseSketch"], Path(temporary) / "run"
            )

        for run in payload["results"]["BaseSketch"]["dependency"]:
            self.assertTrue(run["ok"], run)
            self.assertIn("IntermediatePad", run["dependents"])
            self.assertEqual(run["dependencies"], [])
            # Deterministic lexical ordering and deduplication.
            self.assertEqual(run["dependents"], sorted(set(run["dependents"])))

    def test_intermediate_pad_reports_both_dependents_and_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copy_path = self._copy_committed_fixture(Path(temporary) / "pad")
            payload = self._run_inspect(
                copy_path, ["IntermediatePad"], Path(temporary) / "run"
            )

        for run in payload["results"]["IntermediatePad"]["dependency"]:
            self.assertTrue(run["ok"], run)
            self.assertIn("IntermediatePocket", run["dependents"])
            self.assertIn("BaseSketch", run["dependencies"])


class RealInvalidNativeStateTests(_RealFreeCADValidityTestCase):
    """Proves InvalidNativeCadStateError is driven by genuine native evidence.

    Uses a freshly created, test-owned, empty PartDesign::Body in a
    brand-new in-memory document (no relation to the committed fixture and
    no deletion involved). A body with no features genuinely reports a null
    native Shape once recomputed; this was independently verified against
    real FreeCAD before writing this assertion, and is not assumed.
    """

    def test_empty_partdesign_body_is_reported_as_invalid_native_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload = self._run_empty_body(Path(temporary))

        for run in payload["validity"]:
            self.assertFalse(run["ok"], run)
            self.assertEqual(run["type"], "InvalidNativeCadStateError")
            self.assertIn("EmptyBody", run["message"])
            self.assertIn("null", run["message"])

    def test_empty_body_probe_never_touches_committed_fixture(self) -> None:
        before = _sha256(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            self._run_empty_body(Path(temporary))
        after = _sha256(FIXTURE_PATH)
        self.assertEqual(before, after)


class RepeatedRunDeterminismTests(_RealFreeCADValidityTestCase):
    """Proves stability of evidence and diagnostics across independent runs.

    Each sub-test launches two fully independent freecadcmd processes
    against two independent temporary fixture copies (or two independent
    empty-Body probes) and compares the normalized, test-observed JSON
    results. No temporary path or other environmental noise is compared.
    """

    def test_healthy_evidence_is_stable_across_independent_processes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copy_a = self._copy_committed_fixture(base / "run-a")
            copy_b = self._copy_committed_fixture(base / "run-b")
            payload_a = self._run_inspect(copy_a, ["MutationBody"], base / "work-a")
            payload_b = self._run_inspect(copy_b, ["MutationBody"], base / "work-b")

        self.assertEqual(
            payload_a["results"]["MutationBody"],
            payload_b["results"]["MutationBody"],
        )

    def test_dependency_ordering_is_stable_across_independent_processes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copy_a = self._copy_committed_fixture(base / "run-a")
            copy_b = self._copy_committed_fixture(base / "run-b")
            payload_a = self._run_inspect(copy_a, ["IntermediatePocket"], base / "work-a")
            payload_b = self._run_inspect(copy_b, ["IntermediatePocket"], base / "work-b")

        self.assertEqual(
            payload_a["results"]["IntermediatePocket"]["dependency"],
            payload_b["results"]["IntermediatePocket"]["dependency"],
        )

    def test_invalid_state_diagnostic_is_stable_across_independent_processes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            payload_a = self._run_empty_body(base / "work-a")
            payload_b = self._run_empty_body(base / "work-b")

        self.assertEqual(payload_a["validity"], payload_b["validity"])


class FixtureIntegrityTests(_RealFreeCADValidityTestCase):
    """Proves the committed fixture is never modified by validity tests."""

    def test_committed_fixture_unchanged_after_full_workflow(self) -> None:
        before = _sha256(FIXTURE_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            copy_path = self._copy_committed_fixture(base / "integrity")
            self._run_inspect(
                copy_path,
                ["MutationBody", "BaseSketch", "SafeDeleteMarker"],
                base / "work",
            )
        after = _sha256(FIXTURE_PATH)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
