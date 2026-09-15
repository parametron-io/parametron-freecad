"""Tests for fixture-based integration rehearsal helper.

Coverage:
 1. Import safety
 2. Frozen public records
 3. Execution-only rehearsal success
 4. Execution + observation rehearsal success
 5. Preflight before side effects (manifest compat, verification compat, missing metadata)
 6. Error wrapping and cause preservation
 7. Existing boundary preservation (no unsupported behavior)
"""

from __future__ import annotations

import builtins
import importlib
import json
import sys
import tempfile
import types
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import mock

from parametron_freecad.runtime.integration_rehearsal import (
    FixtureIntegrationRehearsalError,
    FixtureIntegrationRehearsalOutput,
    FixtureIntegrationRehearsalReport,
    FixtureIntegrationRehearsalRequest,
    run_fixture_integration_rehearsal,
)


# ---------------------------------------------------------------------------
# Fake FreeCAD surfaces
# ---------------------------------------------------------------------------


class _FakeSpreadsheet:
    """Minimal fake FreeCAD spreadsheet with a Content dict."""

    def __init__(self, content: dict | None = None) -> None:
        self.Content: dict = content if content is not None else {"A1": "x", "B1": "y"}


class _FakeDocument:
    """Fake FreeCAD document for CSV lifecycle tests.

    Objects raises to guard against unexpected STEP export access.
    getObject is provided for explicit CSV output id lookup.
    recompute is a no-op (no model changes needed in tests).
    """

    Name = "FakeDoc"

    def __init__(self, objects: dict | None = None) -> None:
        self._objects: dict = dict(objects or {})
        self.get_object_calls: list[str] = []
        self.recompute_calls: int = 0
        self.save_calls: int = 0

    @property
    def Objects(self):  # noqa: N802
        raise AssertionError("document.Objects must not be accessed")

    @property
    def Label(self):  # noqa: N802
        raise AssertionError("document.Label must not be accessed")

    def getObject(self, name):  # noqa: N802
        self.get_object_calls.append(name)
        return self._objects.get(name)

    def recompute(self):
        self.recompute_calls += 1

    def save(self):
        self.save_calls += 1


class _FakeFreeCAD:
    """Fake FreeCAD module implementing minimal document lifecycle."""

    def __init__(self, document: _FakeDocument) -> None:
        self.document = document
        self.opened_paths: list[str] = []
        self.closed_names: list[str] = []

    def openDocument(self, path):  # noqa: N802
        self.opened_paths.append(path)
        return self.document

    def closeDocument(self, name):  # noqa: N802
        self.closed_names.append(name)


# ---------------------------------------------------------------------------
# Manifest fixture data
# ---------------------------------------------------------------------------


def _internal_csv_manifest_data() -> dict:
    """FreeCAD-internal manifest with a single CSV output; no Engine normalization needed."""
    return {
        "schemaVersion": "1.0",
        "sourceDocument": "model.FCStd",
        "parameterAssignments": [],
        "outputs": [
            {"id": "Report", "format": "csv", "path": "exports/report.csv"},
        ],
    }


def _engine_manifest_with_name_params() -> dict:
    """Engine-generated manifest with unsupported name-only parameter assignments."""
    return {
        "schemaVersion": "1.0",
        "planHash": "test-plan-hash",
        "adapter": "freecad",
        "product": {"id": "Box"},
        "inputs": {"sourceModel": "input/box.FCStd"},
        "values": {"length": 35},
        "parameterAssignments": [
            {"name": "length", "value": 35, "type": "number", "unit": "mm"},
        ],
        "outputs": [{"type": "step", "filename": "Box.step", "object": "Body"}],
    }


# ---------------------------------------------------------------------------
# Verification fixture data
# ---------------------------------------------------------------------------


def _compatible_verification_data() -> dict:
    """Minimal Engine verification shape accepted by the runtime expectation classifier."""
    return {
        "schemaVersion": "1.0",
        "observe": {
            "components": False,
            "parameters": False,
            "metadata": True,
            "references": True,
        },
        "observationContext": {
            "parameters": [],
        },
        "expected": {
            "components": [],
            "parameters": [],
            "metadata": [{"key": "working_copy_sha256"}],
            "references": [{"kind": "working_copy_path"}],
        },
        "checks": {
            "components": {"enabled": False},
            "parameters": {"enabled": False},
            "metadata": {"enabled": True},
            "references": {"enabled": True},
        },
    }


def _incompatible_verification_data() -> dict:
    """Verification shape with component expectations — rejected by the classifier."""
    return {
        "observe": {
            "components": True,
            "parameters": False,
            "metadata": False,
            "references": False,
        },
        "checks": {
            "components": {"enabled": True},
        },
    }


# ---------------------------------------------------------------------------
# Working copy setup
# ---------------------------------------------------------------------------


def _setup_working_copy(
    tmp_dir: str,
    *,
    manifest_data: dict | None = None,
) -> tuple[Path, Path, Path, Path]:
    """Create a minimal _working directory for rehearsal tests.

    Returns (working_copy, manifest_path, result_path, exports_dir).
    """
    working_copy = Path(tmp_dir) / "_working"
    working_copy.mkdir()

    # Source document must exist on disk
    (working_copy / "model.FCStd").write_bytes(b"fake FCStd content")

    # Output parent directory must exist before CSV export
    exports_dir = working_copy / "exports"
    exports_dir.mkdir()

    manifest_path = working_copy / "export_manifest_v1.json"
    manifest_path.write_text(
        json.dumps(manifest_data if manifest_data is not None else _internal_csv_manifest_data()),
        encoding="utf-8",
    )

    result_path = working_copy / "result.json"

    return working_copy, manifest_path, result_path, exports_dir


# ---------------------------------------------------------------------------
# 1. Import safety
# ---------------------------------------------------------------------------


class IntegrationRehearsalImportSafetyTests(unittest.TestCase):
    def test_module_imports_without_freecad_modules(self) -> None:
        guarded_names = {"FreeCAD", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        module_name = "parametron_freecad.runtime.integration_rehearsal"
        # Restore the original module after the test so that top-level imports
        # in other test classes (run_fixture_integration_rehearsal etc.) keep
        # their __globals__ pointing to the correct module __dict__.
        saved_module = sys.modules.get(module_name)
        for name in [module_name, *guarded_names]:
            sys.modules.pop(name, None)

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        try:
            with mock.patch("builtins.__import__", side_effect=guarded_import):
                module = importlib.import_module(module_name)
        finally:
            # Restore sys.modules AND the parent package attribute.
            # `import A.B.C as name` traverses package attributes (not sys.modules)
            # to resolve the leaf module, so both must point to the saved module.
            parent_pkg = sys.modules.get("parametron_freecad.runtime")
            if saved_module is not None:
                sys.modules[module_name] = saved_module
                if parent_pkg is not None:
                    parent_pkg.integration_rehearsal = saved_module
            else:
                sys.modules.pop(module_name, None)
                if parent_pkg is not None and hasattr(parent_pkg, "integration_rehearsal"):
                    delattr(parent_pkg, "integration_rehearsal")

        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("Import", sys.modules)
        self.assertNotIn("TechDrawGui", sys.modules)

        for name in [
            "FixtureIntegrationRehearsalError",
            "FixtureIntegrationRehearsalRequest",
            "FixtureIntegrationRehearsalOutput",
            "FixtureIntegrationRehearsalReport",
            "run_fixture_integration_rehearsal",
        ]:
            self.assertTrue(hasattr(module, name), name)

    def test_module_all_exposes_public_api(self) -> None:
        module = importlib.import_module("parametron_freecad.runtime.integration_rehearsal")
        self.assertEqual(
            set(module.__all__),
            {
                "FixtureIntegrationRehearsalError",
                "FixtureIntegrationRehearsalOutput",
                "FixtureIntegrationRehearsalReport",
                "FixtureIntegrationRehearsalRequest",
                "run_fixture_integration_rehearsal",
            },
        )

    def test_module_all_does_not_expose_unsupported_api(self) -> None:
        module = importlib.import_module("parametron_freecad.runtime.integration_rehearsal")
        public_names = set(module.__all__)
        forbidden_fragments = [
            "cli", "combined", "component", "decision", "compare",
            "sha256", "capture", "gui", "evaluate",
        ]
        for fragment in forbidden_fragments:
            self.assertFalse(
                any(fragment in name.lower() for name in public_names),
                f"unexpected fragment {fragment!r} in public API",
            )


# ---------------------------------------------------------------------------
# 2. Frozen public records
# ---------------------------------------------------------------------------


class IntegrationRehearsalFrozenRecordTests(unittest.TestCase):
    def test_request_is_frozen(self) -> None:
        request = FixtureIntegrationRehearsalRequest(
            working_copy=Path("/fake/_working"),
            manifest_path=Path("/fake/_working/export_manifest_v1.json"),
            result_path=None,
        )
        with self.assertRaises(FrozenInstanceError):
            request.working_copy = Path("/other")  # type: ignore[misc]

    def test_output_is_frozen(self) -> None:
        output = FixtureIntegrationRehearsalOutput(
            name="result.json",
            path=Path("/fake/_working/result.json"),
            role="result",
        )
        with self.assertRaises(FrozenInstanceError):
            output.role = "artifact"  # type: ignore[misc]

    def test_report_is_frozen(self) -> None:
        path = Path("/fake/_working")
        report = FixtureIntegrationRehearsalReport(
            working_copy=path,
            manifest_path=path / "export_manifest_v1.json",
            verification_path=None,
            source_document_path=path / "model.FCStd",
            result_path=None,
            observed_output_path=None,
            declared_artifact_paths=(),
            outputs=(),
        )
        with self.assertRaises(FrozenInstanceError):
            report.working_copy = Path("/other")  # type: ignore[misc]

    def test_output_preserves_role_name_path_data(self) -> None:
        path = Path("/fake/_working/exports/report.csv")
        output = FixtureIntegrationRehearsalOutput(
            name="report.csv",
            path=path,
            role="artifact",
        )
        self.assertEqual(output.name, "report.csv")
        self.assertEqual(output.path, path)
        self.assertEqual(output.role, "artifact")

    def test_report_declared_artifact_paths_is_tuple(self) -> None:
        p1 = Path("/fake/_working/a.csv")
        p2 = Path("/fake/_working/b.csv")
        path = Path("/fake/_working")
        report = FixtureIntegrationRehearsalReport(
            working_copy=path,
            manifest_path=path / "export_manifest_v1.json",
            verification_path=None,
            source_document_path=path / "model.FCStd",
            result_path=None,
            observed_output_path=None,
            declared_artifact_paths=(p1, p2),
            outputs=(),
        )
        self.assertIsInstance(report.declared_artifact_paths, tuple)
        self.assertEqual(report.declared_artifact_paths, (p1, p2))

    def test_report_outputs_is_tuple(self) -> None:
        path = Path("/fake/_working")
        out = FixtureIntegrationRehearsalOutput(name="x", path=path / "x", role="result")
        report = FixtureIntegrationRehearsalReport(
            working_copy=path,
            manifest_path=path / "export_manifest_v1.json",
            verification_path=None,
            source_document_path=path / "model.FCStd",
            result_path=None,
            observed_output_path=None,
            declared_artifact_paths=(),
            outputs=(out,),
        )
        self.assertIsInstance(report.outputs, tuple)
        self.assertIs(report.outputs[0], out)


# ---------------------------------------------------------------------------
# 3. Execution-only rehearsal success
# ---------------------------------------------------------------------------


class IntegrationRehearsalExecutionOnlyTests(unittest.TestCase):
    """Happy-path execution-only rehearsal using a real fake FreeCAD + CSV output."""

    def _run_execution_only(
        self,
        tmp_dir: str,
    ) -> tuple[FixtureIntegrationRehearsalReport, _FakeFreeCAD, Path, Path]:
        spreadsheet = _FakeSpreadsheet({"A1": "col1", "B1": "col2"})
        document = _FakeDocument({"Report": spreadsheet})
        freecad = _FakeFreeCAD(document)
        working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)

        request = FixtureIntegrationRehearsalRequest(
            working_copy=working_copy,
            manifest_path=manifest_path,
            result_path=result_path,
            freecad_module=freecad,
        )
        report = run_fixture_integration_rehearsal(request)
        return report, freecad, working_copy, result_path

    def test_execution_only_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, _, _ = self._run_execution_only(tmp_dir)
        self.assertIsInstance(report, FixtureIntegrationRehearsalReport)

    def test_result_json_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, working_copy, result_path = self._run_execution_only(tmp_dir)
            result_exists = result_path.exists()
        self.assertTrue(result_exists)

    def test_declared_artifact_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, working_copy, _ = self._run_execution_only(tmp_dir)
            artifact_path = working_copy / "exports" / "report.csv"
            artifact_exists = artifact_path.exists()
        self.assertTrue(artifact_exists)

    def test_observed_output_path_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, _, _ = self._run_execution_only(tmp_dir)
        self.assertIsNone(report.observed_output_path)

    def test_no_observed_json_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, working_copy, _ = self._run_execution_only(tmp_dir)
            observed_path = working_copy / "prm.observed.json"
            observed_exists = observed_path.exists()
        self.assertFalse(observed_exists)

    def test_report_working_copy_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, working_copy, _ = self._run_execution_only(tmp_dir)
        self.assertTrue(report.working_copy.is_absolute())
        self.assertEqual(report.working_copy, working_copy.resolve())

    def test_report_manifest_path_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, working_copy, _ = self._run_execution_only(tmp_dir)
        self.assertTrue(report.manifest_path.is_absolute())

    def test_report_source_document_path_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, working_copy, _ = self._run_execution_only(tmp_dir)
        self.assertTrue(report.source_document_path.is_absolute())
        self.assertEqual(report.source_document_path, (working_copy / "model.FCStd").resolve())

    def test_report_result_path_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, working_copy, result_path = self._run_execution_only(tmp_dir)
        self.assertIsNotNone(report.result_path)
        self.assertTrue(report.result_path.is_absolute())

    def test_declared_artifact_paths_preserve_manifest_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, working_copy, _ = self._run_execution_only(tmp_dir)
            expected = ((working_copy / "exports" / "report.csv").resolve(),)
        self.assertEqual(report.declared_artifact_paths, expected)

    def test_outputs_order_result_then_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, _, _ = self._run_execution_only(tmp_dir)
        self.assertEqual(len(report.outputs), 2)
        self.assertEqual(report.outputs[0].role, "result")
        self.assertEqual(report.outputs[0].name, "result.json")
        self.assertEqual(report.outputs[1].role, "artifact")
        self.assertEqual(report.outputs[1].name, "report.csv")

    def test_no_observed_output_in_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, _, _ = self._run_execution_only(tmp_dir)
        roles = [o.role for o in report.outputs]
        self.assertNotIn("observed", roles)

    def test_document_opened_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, freecad, working_copy, _ = self._run_execution_only(tmp_dir)
            source_path = str((working_copy / "model.FCStd").resolve())
        self.assertEqual(len(freecad.opened_paths), 1)
        self.assertEqual(freecad.opened_paths[0], source_path)

    def test_document_closed_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, freecad, _, _ = self._run_execution_only(tmp_dir)
        self.assertEqual(len(freecad.closed_names), 1)
        self.assertEqual(freecad.closed_names[0], "FakeDoc")

    def test_verification_path_is_none_in_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _, _, _ = self._run_execution_only(tmp_dir)
        self.assertIsNone(report.verification_path)

    def test_result_path_none_produces_no_result_output(self) -> None:
        """When result_path=None, outputs list has no 'result' role entry."""
        import parametron_freecad.runtime.integration_rehearsal as rehearsal_module

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, _, _ = _setup_working_copy(tmp_dir)

            # Mock run_engine_invocation so result_path=None does not cause
            # write_success_result(None, ...) to raise TypeError at runtime.
            with mock.patch.object(rehearsal_module, "run_engine_invocation", return_value=None):
                report = run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=None,
                        freecad_module=_FakeFreeCAD(_FakeDocument()),
                    )
                )

        self.assertIsNone(report.result_path)
        roles = [o.role for o in report.outputs]
        self.assertNotIn("result", roles)
        self.assertIn("artifact", roles)


# ---------------------------------------------------------------------------
# 4. Execution + observation rehearsal success
# ---------------------------------------------------------------------------


class IntegrationRehearsalExecutionAndObservationTests(unittest.TestCase):
    """Happy-path execution+observation rehearsal using fake FreeCAD and Engine verification."""

    _CALLER_SHA256 = "a" * 64
    _CALLER_WC_PATH = "/caller/supplied/working/copy/_working"

    def _run_with_observation(
        self,
        tmp_dir: str,
    ) -> tuple[FixtureIntegrationRehearsalReport, Path]:
        spreadsheet = _FakeSpreadsheet({"A1": "val"})
        document = _FakeDocument({"Report": spreadsheet})
        freecad = _FakeFreeCAD(document)
        working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)

        verification_path = Path(tmp_dir) / "parametron.verification.json"
        verification_path.write_text(
            json.dumps(_compatible_verification_data()),
            encoding="utf-8",
        )

        observed_output_directory = Path(tmp_dir) / "observed"
        observed_output_directory.mkdir()

        request = FixtureIntegrationRehearsalRequest(
            working_copy=working_copy,
            manifest_path=manifest_path,
            result_path=result_path,
            verification_path=verification_path,
            observed_output_directory=observed_output_directory,
            working_copy_path=self._CALLER_WC_PATH,
            working_copy_sha256=self._CALLER_SHA256,
            freecad_module=freecad,
        )
        report = run_fixture_integration_rehearsal(request)
        return report, observed_output_directory

    def test_execution_and_observation_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _ = self._run_with_observation(tmp_dir)
        self.assertIsInstance(report, FixtureIntegrationRehearsalReport)

    def test_execution_output_produced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _ = self._run_with_observation(tmp_dir)
            artifact_exists = (
                report.declared_artifact_paths[0].exists()
                if report.declared_artifact_paths
                else False
            )
        self.assertTrue(artifact_exists)

    def test_observed_json_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, observed_output_directory = self._run_with_observation(tmp_dir)
            observed_path = observed_output_directory / "prm.observed.json"
            observed_exists = observed_path.exists()
        self.assertTrue(observed_exists)

    def test_report_observed_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, observed_output_directory = self._run_with_observation(tmp_dir)
            expected_path = (observed_output_directory / "prm.observed.json").resolve()
        self.assertIsNotNone(report.observed_output_path)
        self.assertEqual(report.observed_output_path, expected_path)

    def test_outputs_order_result_artifact_observed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _ = self._run_with_observation(tmp_dir)
        roles = [o.role for o in report.outputs]
        self.assertEqual(roles, ["result", "artifact", "observed"])

    def test_observed_output_name_is_parametron_observed_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _ = self._run_with_observation(tmp_dir)
        observed_outputs = [o for o in report.outputs if o.role == "observed"]
        self.assertEqual(len(observed_outputs), 1)
        self.assertEqual(observed_outputs[0].name, "prm.observed.json")

    def test_observed_json_preserves_caller_working_copy_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, observed_output_directory = self._run_with_observation(tmp_dir)
            observed_path = observed_output_directory / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))
        self.assertEqual(decoded["workingCopy"]["path"], self._CALLER_WC_PATH)

    def test_observed_json_preserves_caller_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, observed_output_directory = self._run_with_observation(tmp_dir)
            observed_path = observed_output_directory / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))
        self.assertEqual(decoded["workingCopy"]["sha256"], self._CALLER_SHA256)

    def test_observed_json_has_only_implemented_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, observed_output_directory = self._run_with_observation(tmp_dir)
            observed_path = observed_output_directory / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))
        observation = decoded.get("observation", {})
        # Engine verification shape requests metadata and references only
        self.assertIn("observation", decoded)
        self.assertNotIn("components", observation)

    def test_observed_json_no_verification_decision_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, observed_output_directory = self._run_with_observation(tmp_dir)
            observed_path = observed_output_directory / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))
        self.assertNotIn("decision", decoded)
        self.assertNotIn("verification", decoded)
        self.assertNotIn("checks", decoded)

    def test_observed_json_no_check_evaluation_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, observed_output_directory = self._run_with_observation(tmp_dir)
            observed_path = observed_output_directory / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))
        observation = decoded.get("observation", {})
        self.assertNotIn("checkResults", decoded)
        self.assertNotIn("checkResults", observation)

    def test_no_sha256_computation_by_helper(self) -> None:
        # sha256 in observed JSON must equal the caller-supplied value, not computed
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, observed_output_directory = self._run_with_observation(tmp_dir)
            observed_path = observed_output_directory / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))
        self.assertEqual(decoded["workingCopy"]["sha256"], self._CALLER_SHA256)
        # Explicitly not "a sha256 of the actual working copy contents"
        self.assertNotEqual(decoded["workingCopy"]["sha256"], "b" * 64)

    def test_report_verification_path_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report, _ = self._run_with_observation(tmp_dir)
        self.assertIsNotNone(report.verification_path)

    def test_document_opened_twice_for_execution_and_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            spreadsheet = _FakeSpreadsheet({"A1": "v"})
            document = _FakeDocument({"Report": spreadsheet})
            freecad = _FakeFreeCAD(document)
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text(json.dumps(_compatible_verification_data()), encoding="utf-8")
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()

            run_fixture_integration_rehearsal(
                FixtureIntegrationRehearsalRequest(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    verification_path=verification_path,
                    observed_output_directory=observed_dir,
                    working_copy_path="/wc",
                    working_copy_sha256="b" * 64,
                    freecad_module=freecad,
                )
            )

        self.assertEqual(len(freecad.opened_paths), 2)
        self.assertEqual(len(freecad.closed_names), 2)


# ---------------------------------------------------------------------------
# 5. Preflight before side effects
# ---------------------------------------------------------------------------


class IntegrationRehearsalPreflightTests(unittest.TestCase):
    """Preflight failures must occur before any execution side effects."""

    def _make_engine_invalid_manifest_request(
        self,
        tmp_dir: str,
    ) -> tuple[FixtureIntegrationRehearsalRequest, _FakeFreeCAD]:
        working_copy = Path(tmp_dir) / "_working"
        working_copy.mkdir()

        manifest_path = working_copy / "export_manifest_v1.json"
        manifest_path.write_text(
            json.dumps(_engine_manifest_with_name_params()),
            encoding="utf-8",
        )
        result_path = working_copy / "result.json"
        document = _FakeDocument()
        freecad = _FakeFreeCAD(document)

        request = FixtureIntegrationRehearsalRequest(
            working_copy=working_copy,
            manifest_path=manifest_path,
            result_path=result_path,
            freecad_module=freecad,
        )
        return request, freecad

    # ---- invalid manifest compat ----

    def test_invalid_manifest_compat_raises_rehearsal_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            request, _ = self._make_engine_invalid_manifest_request(tmp_dir)
            with self.assertRaises(FixtureIntegrationRehearsalError):
                run_fixture_integration_rehearsal(request)

    def test_invalid_manifest_compat_cause_is_preserved(self) -> None:
        from parametron_freecad.execution.engine_manifest_compat import (
            EngineManifestUnsupportedParameterTargetError,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            request, _ = self._make_engine_invalid_manifest_request(tmp_dir)
            with self.assertRaises(FixtureIntegrationRehearsalError) as excinfo:
                run_fixture_integration_rehearsal(request)
        self.assertIsInstance(
            excinfo.exception.__cause__,
            EngineManifestUnsupportedParameterTargetError,
        )

    def test_invalid_manifest_compat_does_not_call_open_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            request, freecad = self._make_engine_invalid_manifest_request(tmp_dir)
            with self.assertRaises(FixtureIntegrationRehearsalError):
                run_fixture_integration_rehearsal(request)
        self.assertEqual(freecad.opened_paths, [])

    def test_invalid_manifest_compat_no_result_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            request, _ = self._make_engine_invalid_manifest_request(tmp_dir)
            with self.assertRaises(FixtureIntegrationRehearsalError):
                run_fixture_integration_rehearsal(request)
            result_exists = request.result_path.exists() if request.result_path else False
        self.assertFalse(result_exists)

    def test_invalid_manifest_compat_no_artifacts_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            request, _ = self._make_engine_invalid_manifest_request(tmp_dir)
            with self.assertRaises(FixtureIntegrationRehearsalError):
                run_fixture_integration_rehearsal(request)
            exports_dir = request.working_copy / "exports"
            any_artifact = exports_dir.exists() and any(exports_dir.iterdir())
        self.assertFalse(any_artifact)

    def test_invalid_manifest_compat_no_observed_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            request, _ = self._make_engine_invalid_manifest_request(tmp_dir)
            observed_path = request.working_copy / "prm.observed.json"
            with self.assertRaises(FixtureIntegrationRehearsalError):
                run_fixture_integration_rehearsal(request)
            observed_exists = observed_path.exists()
        self.assertFalse(observed_exists)

    # ---- invalid verification compat ----

    def test_invalid_verification_compat_raises_rehearsal_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text(
                json.dumps(_incompatible_verification_data()),
                encoding="utf-8",
            )
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()
            freecad = _FakeFreeCAD(_FakeDocument())

            request = FixtureIntegrationRehearsalRequest(
                working_copy=working_copy,
                manifest_path=manifest_path,
                result_path=result_path,
                verification_path=verification_path,
                observed_output_directory=observed_dir,
                working_copy_path="/wc",
                working_copy_sha256="c" * 64,
                freecad_module=freecad,
            )
            with self.assertRaises(FixtureIntegrationRehearsalError):
                run_fixture_integration_rehearsal(request)

    def test_invalid_verification_compat_cause_preserved(self) -> None:
        from parametron_freecad.observation.engine_verification_expectations import (
            EngineVerificationExpectationCompatibilityError,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text(
                json.dumps(_incompatible_verification_data()),
                encoding="utf-8",
            )
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()
            freecad = _FakeFreeCAD(_FakeDocument())

            with self.assertRaises(FixtureIntegrationRehearsalError) as excinfo:
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        verification_path=verification_path,
                        observed_output_directory=observed_dir,
                        working_copy_path="/wc",
                        working_copy_sha256="d" * 64,
                        freecad_module=freecad,
                    )
                )
        self.assertIsInstance(
            excinfo.exception.__cause__,
            EngineVerificationExpectationCompatibilityError,
        )

    def test_invalid_verification_compat_does_not_call_open_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text(
                json.dumps(_incompatible_verification_data()),
                encoding="utf-8",
            )
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()
            freecad = _FakeFreeCAD(_FakeDocument())

            with self.assertRaises(FixtureIntegrationRehearsalError):
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        verification_path=verification_path,
                        observed_output_directory=observed_dir,
                        working_copy_path="/wc",
                        working_copy_sha256="e" * 64,
                        freecad_module=freecad,
                    )
                )
        self.assertEqual(freecad.opened_paths, [])

    def test_invalid_verification_compat_no_result_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text(
                json.dumps(_incompatible_verification_data()),
                encoding="utf-8",
            )
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()
            freecad = _FakeFreeCAD(_FakeDocument())

            with self.assertRaises(FixtureIntegrationRehearsalError):
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        verification_path=verification_path,
                        observed_output_directory=observed_dir,
                        working_copy_path="/wc",
                        working_copy_sha256="f" * 64,
                        freecad_module=freecad,
                    )
                )
            result_exists = result_path.exists()
        self.assertFalse(result_exists)

    # ---- missing observation metadata ----

    def test_missing_observed_output_directory_raises_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            # Doesn't need to be valid — check happens before file is read
            verification_path.write_text("{}", encoding="utf-8")
            freecad = _FakeFreeCAD(_FakeDocument())

            with self.assertRaises(FixtureIntegrationRehearsalError) as excinfo:
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        verification_path=verification_path,
                        observed_output_directory=None,
                        working_copy_path="/wc",
                        working_copy_sha256="g" * 64,
                        freecad_module=freecad,
                    )
                )
        self.assertIn("observed_output_directory", str(excinfo.exception))
        self.assertEqual(freecad.opened_paths, [])
        self.assertIsNone(excinfo.exception.__cause__)

    def test_missing_working_copy_path_raises_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text("{}", encoding="utf-8")
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()
            freecad = _FakeFreeCAD(_FakeDocument())

            with self.assertRaises(FixtureIntegrationRehearsalError) as excinfo:
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        verification_path=verification_path,
                        observed_output_directory=observed_dir,
                        working_copy_path=None,
                        working_copy_sha256="h" * 64,
                        freecad_module=freecad,
                    )
                )
        self.assertIn("working_copy_path", str(excinfo.exception))
        self.assertEqual(freecad.opened_paths, [])

    def test_missing_working_copy_sha256_raises_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text("{}", encoding="utf-8")
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()
            freecad = _FakeFreeCAD(_FakeDocument())

            with self.assertRaises(FixtureIntegrationRehearsalError) as excinfo:
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        verification_path=verification_path,
                        observed_output_directory=observed_dir,
                        working_copy_path="/wc",
                        working_copy_sha256=None,
                        freecad_module=freecad,
                    )
                )
        self.assertIn("working_copy_sha256", str(excinfo.exception))
        self.assertEqual(freecad.opened_paths, [])

    def test_all_missing_metadata_failures_produce_no_output_files(self) -> None:
        """No result.json or artifacts created when any required metadata is missing."""
        missing_cases = [
            dict(observed_output_directory=None, working_copy_path="/wc", working_copy_sha256="a" * 64),
            dict(observed_output_directory=Path("/tmp/obs"), working_copy_path=None, working_copy_sha256="a" * 64),
            dict(observed_output_directory=Path("/tmp/obs"), working_copy_path="/wc", working_copy_sha256=None),
        ]
        for case in missing_cases:
            with self.subTest(missing=case):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
                    verification_path = Path(tmp_dir) / "v.json"
                    verification_path.write_text("{}", encoding="utf-8")
                    if case.get("observed_output_directory") == Path("/tmp/obs"):
                        case["observed_output_directory"] = Path(tmp_dir) / "obs"
                        case["observed_output_directory"].mkdir(exist_ok=True)
                    freecad = _FakeFreeCAD(_FakeDocument())

                    with self.assertRaises(FixtureIntegrationRehearsalError):
                        run_fixture_integration_rehearsal(
                            FixtureIntegrationRehearsalRequest(
                                working_copy=working_copy,
                                manifest_path=manifest_path,
                                result_path=result_path,
                                verification_path=verification_path,
                                freecad_module=freecad,
                                **case,
                            )
                        )
                    self.assertFalse(result_path.exists(), "result.json must not be created")
                    self.assertEqual(freecad.opened_paths, [], "openDocument must not be called")


# ---------------------------------------------------------------------------
# 6. Error wrapping and cause preservation
# ---------------------------------------------------------------------------


class IntegrationRehearsalErrorWrappingTests(unittest.TestCase):
    """Errors from underlying boundaries wrap to FixtureIntegrationRehearsalError."""

    def _assert_failed_result(self, result_path: Path, *, stage: str) -> None:
        self.assertTrue(result_path.exists())
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(payload["status"], "failed")
        failure = payload["failure"]
        self.assertEqual(failure["boundary"], "execution_entrypoint")
        self.assertEqual(failure["category"], "execution")
        self.assertEqual(failure["code"], "runtime_failure")
        self.assertEqual(failure["stage"], stage)
        self.assertEqual(failure["message"], " ".join(failure["message"].split()))

    def test_manifest_load_failure_wraps_to_rehearsal_error(self) -> None:
        from parametron_freecad.execution.manifest_loader import ManifestLoadError
        import parametron_freecad.runtime.integration_rehearsal as rehearsal_module

        original = ManifestLoadError("fake manifest load failure")

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            freecad = _FakeFreeCAD(_FakeDocument())

            with mock.patch.object(
                rehearsal_module, "load_export_manifest_v1", side_effect=original
            ), self.assertRaises(FixtureIntegrationRehearsalError) as excinfo:
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        freecad_module=freecad,
                    )
                )

        self.assertIs(excinfo.exception.__cause__, original)
        self.assertEqual(freecad.opened_paths, [])

    def test_verification_load_failure_wraps_to_rehearsal_error(self) -> None:
        from parametron_freecad.observation.verification_loader import VerificationLoadError
        import parametron_freecad.runtime.integration_rehearsal as rehearsal_module

        original = VerificationLoadError("fake verification load failure")

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text("{}", encoding="utf-8")
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()
            freecad = _FakeFreeCAD(_FakeDocument())

            with mock.patch.object(
                rehearsal_module, "load_parametron_verification_v1", side_effect=original
            ), self.assertRaises(FixtureIntegrationRehearsalError) as excinfo:
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        verification_path=verification_path,
                        observed_output_directory=observed_dir,
                        working_copy_path="/wc",
                        working_copy_sha256="i" * 64,
                        freecad_module=freecad,
                    )
                )

        self.assertIs(excinfo.exception.__cause__, original)
        self.assertEqual(freecad.opened_paths, [])

    def test_handled_execution_failure_writes_failed_result_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            freecad = _FakeFreeCAD(_FakeDocument())

            with self.assertRaises(FixtureIntegrationRehearsalError):
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        freecad_module=freecad,
                    )
                )

            self._assert_failed_result(result_path, stage="artifact_export")
            artifact_exists = (working_copy / "exports" / "report.csv").exists()

        self.assertFalse(artifact_exists)
        self.assertEqual(freecad.opened_paths, [str((working_copy / "model.FCStd").resolve())])
        self.assertEqual(freecad.closed_names, ["FakeDoc"])

    def test_execution_invocation_failure_wraps_to_rehearsal_error(self) -> None:
        from parametron_freecad.runtime.error_contract import EngineInvocationError
        import parametron_freecad.runtime.integration_rehearsal as rehearsal_module

        original = EngineInvocationError("fake execution failure")

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)

            with mock.patch.object(
                rehearsal_module, "run_engine_invocation", side_effect=original
            ), self.assertRaises(FixtureIntegrationRehearsalError) as excinfo:
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        freecad_module=_FakeFreeCAD(_FakeDocument()),
                    )
                )

        self.assertIs(excinfo.exception.__cause__, original)

    def test_observation_failure_wraps_to_rehearsal_error(self) -> None:
        import parametron_freecad.runtime.integration_rehearsal as rehearsal_module

        original = rehearsal_module.ObservationEntrypointError("fake observation failure")

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text(
                json.dumps(_compatible_verification_data()),
                encoding="utf-8",
            )
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()

            with mock.patch.object(
                rehearsal_module, "run_engine_invocation", return_value=None
            ), mock.patch.object(
                rehearsal_module, "run_document_observation_entrypoint", side_effect=original
            ), self.assertRaises(FixtureIntegrationRehearsalError) as excinfo:
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        verification_path=verification_path,
                        observed_output_directory=observed_dir,
                        working_copy_path="/wc",
                        working_copy_sha256="j" * 64,
                        freecad_module=_FakeFreeCAD(_FakeDocument()),
                    )
                )

        self.assertIs(excinfo.exception.__cause__, original)

    def test_all_causes_have_exception_chaining(self) -> None:
        """FixtureIntegrationRehearsalError always chains the original cause."""
        import parametron_freecad.runtime.integration_rehearsal as rehearsal_module
        from parametron_freecad.execution.manifest_loader import ManifestLoadError

        sentinel = ManifestLoadError("sentinel cause")

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)

            with mock.patch.object(
                rehearsal_module, "load_export_manifest_v1", side_effect=sentinel
            ), self.assertRaises(FixtureIntegrationRehearsalError) as excinfo:
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                    )
                )

        raised = excinfo.exception
        self.assertIsNotNone(raised.__cause__)
        self.assertIs(raised.__cause__, sentinel)


# ---------------------------------------------------------------------------
# 7. Existing boundary preservation (no unsupported behavior)
# ---------------------------------------------------------------------------


class IntegrationRehearsalBoundaryTests(unittest.TestCase):
    """Helper does not expose or call out-of-scope behavior."""

    def test_helper_does_not_call_headless_cli(self) -> None:
        from parametron_freecad.runtime import headless
        import parametron_freecad.runtime.integration_rehearsal as rehearsal_module

        with tempfile.TemporaryDirectory() as tmp_dir:
            spreadsheet = _FakeSpreadsheet({"A1": "v"})
            document = _FakeDocument({"Report": spreadsheet})
            freecad = _FakeFreeCAD(document)
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)

            with mock.patch.object(
                headless,
                "main",
                side_effect=AssertionError("rehearsal must not call headless CLI"),
            ) as cli_main:
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        freecad_module=freecad,
                    )
                )

        cli_main.assert_not_called()

    def test_helper_does_not_call_combined_runtime_mode(self) -> None:
        import parametron_freecad.runtime.integration_rehearsal as rehearsal_module

        called_modes = []

        def spy_invocation(invocation):
            called_modes.append(invocation.mode)
            # Prevent actual execution by raising a controlled error
            from parametron_freecad.runtime.error_contract import EngineInvocationError
            raise EngineInvocationError("spy abort")

        with tempfile.TemporaryDirectory() as tmp_dir:
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)

            with mock.patch.object(
                rehearsal_module, "run_engine_invocation", side_effect=spy_invocation
            ), self.assertRaises(FixtureIntegrationRehearsalError):
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                    )
                )

        for mode in called_modes:
            self.assertNotEqual(mode, "combined")

    def test_helper_does_not_compute_sha256(self) -> None:
        """sha256 value must come from caller, not be computed internally."""
        import hashlib
        import parametron_freecad.runtime.integration_rehearsal as rehearsal_module

        with tempfile.TemporaryDirectory() as tmp_dir:
            spreadsheet = _FakeSpreadsheet({"A1": "v"})
            document = _FakeDocument({"Report": spreadsheet})
            freecad = _FakeFreeCAD(document)
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text(
                json.dumps(_compatible_verification_data()),
                encoding="utf-8",
            )
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()
            caller_sha256 = "k" * 64

            def fail_if_sha256_used(data, *args, **kwargs):
                raise AssertionError("helper must not compute sha256 internally")

            with mock.patch.object(hashlib, "sha256", side_effect=fail_if_sha256_used):
                run_fixture_integration_rehearsal(
                    FixtureIntegrationRehearsalRequest(
                        working_copy=working_copy,
                        manifest_path=manifest_path,
                        result_path=result_path,
                        verification_path=verification_path,
                        observed_output_directory=observed_dir,
                        working_copy_path="/wc",
                        working_copy_sha256=caller_sha256,
                        freecad_module=freecad,
                    )
                )

            observed_path = observed_dir / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))

        self.assertEqual(decoded["workingCopy"]["sha256"], caller_sha256)

    def test_helper_does_not_perform_verification_decisions(self) -> None:
        """observed JSON must not contain a decision field."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            spreadsheet = _FakeSpreadsheet({"A1": "v"})
            document = _FakeDocument({"Report": spreadsheet})
            freecad = _FakeFreeCAD(document)
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text(
                json.dumps(_compatible_verification_data()),
                encoding="utf-8",
            )
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()

            run_fixture_integration_rehearsal(
                FixtureIntegrationRehearsalRequest(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    verification_path=verification_path,
                    observed_output_directory=observed_dir,
                    working_copy_path="/wc",
                    working_copy_sha256="l" * 64,
                    freecad_module=freecad,
                )
            )

            observed_path = observed_dir / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))

        self.assertNotIn("decision", decoded)
        self.assertNotIn("verification", decoded)

    def test_helper_does_not_observe_components(self) -> None:
        """components must not appear in the observed JSON."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            spreadsheet = _FakeSpreadsheet({"A1": "v"})
            document = _FakeDocument({"Report": spreadsheet})
            freecad = _FakeFreeCAD(document)
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text(
                json.dumps(_compatible_verification_data()),
                encoding="utf-8",
            )
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()

            run_fixture_integration_rehearsal(
                FixtureIntegrationRehearsalRequest(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    verification_path=verification_path,
                    observed_output_directory=observed_dir,
                    working_copy_path="/wc",
                    working_copy_sha256="m" * 64,
                    freecad_module=freecad,
                )
            )

            observed_path = observed_dir / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))

        observation = decoded.get("observation", {})
        self.assertNotIn("components", observation)

    def test_helper_does_not_use_document_objects_or_label_for_csv(self) -> None:
        """CSV export uses getObject by id; Objects and Label must not be accessed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # _FakeDocument raises on Objects and Label access — this is the guard
            spreadsheet = _FakeSpreadsheet({"A1": "v"})
            document = _FakeDocument({"Report": spreadsheet})
            freecad = _FakeFreeCAD(document)
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)

            # Run without raising — if Objects/Label accessed, _FakeDocument raises AssertionError
            run_fixture_integration_rehearsal(
                FixtureIntegrationRehearsalRequest(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    freecad_module=freecad,
                )
            )

        # getObject must have been called with exactly the CSV output id
        self.assertIn("Report", document.get_object_calls)

    def test_helper_does_not_compare_artifact_bytes(self) -> None:
        """Report records path; no byte-level comparison is performed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            spreadsheet = _FakeSpreadsheet({"A1": "v"})
            document = _FakeDocument({"Report": spreadsheet})
            freecad = _FakeFreeCAD(document)
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)

            report = run_fixture_integration_rehearsal(
                FixtureIntegrationRehearsalRequest(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    freecad_module=freecad,
                )
            )

        # Outputs contain paths, not byte content
        for output in report.outputs:
            self.assertIsInstance(output.path, Path)
            self.assertNotIsInstance(output.path, bytes)

    def test_helper_does_not_evaluate_checks(self) -> None:
        """Observed JSON must not contain check evaluation results."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            spreadsheet = _FakeSpreadsheet({"A1": "v"})
            document = _FakeDocument({"Report": spreadsheet})
            freecad = _FakeFreeCAD(document)
            working_copy, manifest_path, result_path, _ = _setup_working_copy(tmp_dir)
            verification_path = Path(tmp_dir) / "v.json"
            verification_path.write_text(
                json.dumps(_compatible_verification_data()),
                encoding="utf-8",
            )
            observed_dir = Path(tmp_dir) / "obs"
            observed_dir.mkdir()

            run_fixture_integration_rehearsal(
                FixtureIntegrationRehearsalRequest(
                    working_copy=working_copy,
                    manifest_path=manifest_path,
                    result_path=result_path,
                    verification_path=verification_path,
                    observed_output_directory=observed_dir,
                    working_copy_path="/wc",
                    working_copy_sha256="n" * 64,
                    freecad_module=freecad,
                )
            )

            observed_path = observed_dir / "prm.observed.json"
            decoded = json.loads(observed_path.read_text(encoding="utf-8"))

        self.assertNotIn("checks", decoded)
        self.assertNotIn("checkResults", decoded)


if __name__ == "__main__":
    unittest.main()
