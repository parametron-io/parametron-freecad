from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.common.paths import WORKING_COPY_DIR_NAME
from parametron_freecad.runtime import headless


class HeadlessMissingWorkingCopyTests(unittest.TestCase):
    _OUTPUTS = [
        {"id": "part", "format": "step", "path": "exports/part.step"},
        {"id": "report", "format": "csv", "path": "exports/report.csv"},
        {"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"},
    ]

    def _run_main(self, argv: list[str]) -> tuple[int, io.StringIO, io.StringIO]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = headless.main(argv=argv, stdout=stdout, stderr=stderr)
        return exit_code, stdout, stderr

    def _execute_argv(self, working: Path, manifest: Path, result: Path) -> list[str]:
        return [
            "execute",
            "--working-copy", str(working),
            "--manifest", str(manifest),
            "--result", str(result),
        ]

    def _make_working_copy(self, root: Path) -> Path:
        working = root / WORKING_COPY_DIR_NAME
        working.mkdir()
        return working

    def _write_manifest(
        self,
        path: Path,
        *,
        source_document: str = "model.FCStd",
        outputs: list[dict] | None = None,
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "sourceDocument": source_document,
                    "parameterAssignments": [],
                    "outputs": self._OUTPUTS if outputs is None else outputs,
                }
            ),
            encoding="utf-8",
        )

    def _create_symlink_or_skip(self, target: Path, link_path: Path) -> None:
        try:
            link_path.symlink_to(target)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is unavailable on this platform")

    def _assert_failure_shape(
        self,
        exit_code: int,
        stdout: io.StringIO,
        stderr: io.StringIO,
        *,
        expected_exit_code: int,
        expected_prefix: str,
    ) -> None:
        self.assertEqual(exit_code, expected_exit_code)
        self.assertEqual(stdout.getvalue(), "")
        err = stderr.getvalue()
        self.assertTrue(
            err.startswith(expected_prefix),
            msg=f"stderr {err!r} does not start with {expected_prefix!r}",
        )
        self.assertTrue(err.endswith("\n"), msg=f"stderr {err!r} is not newline-terminated")
        self.assertEqual(err.count("\n"), 1, msg=f"stderr {err!r} is not single-line")
        self.assertNotIn("Traceback", err)

    def _artifact_paths(self, working: Path) -> list[Path]:
        return [working / output["path"] for output in self._OUTPUTS]

    def _assert_no_files_created(self, result: Path, artifact_paths: list[Path]) -> None:
        self.assertFalse(result.exists())
        for artifact_path in artifact_paths:
            self.assertFalse(artifact_path.exists(), msg=f"{artifact_path} was created")

    def _assert_failed_result(
        self,
        result: Path,
        artifact_paths: list[Path],
        *,
        stage: str,
    ) -> None:
        self.assertTrue(result.exists())
        payload = json.loads(result.read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(payload["status"], "failed")
        failure = payload["failure"]
        self.assertEqual(failure["boundary"], "execution_entrypoint")
        self.assertEqual(failure["category"], "execution")
        self.assertEqual(failure["code"], "runtime_failure")
        self.assertEqual(failure["stage"], stage)
        self.assertEqual(failure["message"], " ".join(failure["message"].split()))
        for artifact_path in artifact_paths:
            self.assertFalse(artifact_path.exists(), msg=f"{artifact_path} was created")

    def _assert_invalid_arguments(self, run: tuple[int, io.StringIO, io.StringIO]) -> None:
        self._assert_failure_shape(
            *run,
            expected_exit_code=headless.ARGUMENT_ERROR_EXIT_CODE,
            expected_prefix=headless.INVALID_ARGUMENTS_MESSAGE_PREFIX,
        )

    def _assert_execute_failure(self, run: tuple[int, io.StringIO, io.StringIO]) -> None:
        self._assert_failure_shape(
            *run,
            expected_exit_code=headless.EXECUTION_FAILURE_EXIT_CODE,
            expected_prefix=headless.EXECUTION_FAILURE_MESSAGE_PREFIX,
        )

    def _run_with_downstream_guards(
        self,
        argv: list[str],
    ) -> tuple[tuple[int, io.StringIO, io.StringIO], tuple[mock.Mock, ...]]:
        with mock.patch(
            "parametron_freecad.runtime.headless.import_module",
            side_effect=AssertionError("FreeCAD module resolution must not be reached"),
        ), mock.patch(
            "parametron_freecad.runtime.headless.opened_freecad_document",
        ) as opened_document, mock.patch(
            "parametron_freecad.runtime.headless.export_step_artifacts",
        ) as step_export, mock.patch(
            "parametron_freecad.runtime.headless.export_csv_artifacts",
        ) as csv_export, mock.patch(
            "parametron_freecad.runtime.headless.export_pdf_artifacts",
        ) as pdf_export:
            run = self._run_main(argv)

        return run, (opened_document, step_export, csv_export, pdf_export)

    def _assert_downstream_not_reached(self, guarded_calls: tuple[mock.Mock, ...]) -> None:
        for guarded_call in guarded_calls:
            guarded_call.assert_not_called()

    # --- argument-level working-copy failures ---

    def test_execute_working_copy_path_does_not_exist_is_invalid_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working = root / WORKING_COPY_DIR_NAME
            result = working / "result.json"
            artifacts = self._artifact_paths(working)

            run, guarded_calls = self._run_with_downstream_guards(
                self._execute_argv(working, working / "export_manifest_v1.json", result)
            )

            self._assert_invalid_arguments(run)
            self._assert_downstream_not_reached(guarded_calls)
            self._assert_no_files_created(result, artifacts)

    def test_execute_working_copy_file_is_invalid_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working_file = root / WORKING_COPY_DIR_NAME
            working_file.write_text("not a directory", encoding="utf-8")
            result = root / "result.json"

            run, guarded_calls = self._run_with_downstream_guards(
                self._execute_argv(working_file, working_file, result)
            )

            self._assert_invalid_arguments(run)
            self._assert_downstream_not_reached(guarded_calls)
            self._assert_no_files_created(result, [root / "exports" / "part.step"])

    def test_execute_working_copy_arbitrary_safe_name_preserves_containment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working = root / "project"
            working.mkdir()
            manifest = working / "export_manifest_v1.json"
            self._write_manifest(manifest)
            (working / "model.FCStd").write_bytes(b"")
            result = working / "result.json"

            invocation = headless.parse_headless_arguments(
                self._execute_argv(working, manifest, result)
            )

            self.assertEqual(invocation.working_copy, working.resolve())
            self.assertEqual(invocation.result, result.resolve())
            self._assert_no_files_created(result, self._artifact_paths(working))

    def test_execute_working_copy_nested_execution_leaf_is_authoritative_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            parent_working = root / "product" / WORKING_COPY_DIR_NAME
            child = parent_working / "execution-a"
            child.mkdir(parents=True)
            manifest = child / "export_manifest_v1.json"
            self._write_manifest(manifest)
            (child / "model.FCStd").write_bytes(b"")
            result = child / "result.json"

            invocation = headless.parse_headless_arguments(
                self._execute_argv(child, manifest, result)
            )

            self.assertEqual(invocation.working_copy, child.resolve())
            self.assertNotEqual(invocation.working_copy, parent_working.resolve())
            self._assert_no_files_created(result, self._artifact_paths(child))
            self.assertEqual(
                {path.relative_to(parent_working) for path in parent_working.rglob("*")},
                {Path("execution-a"), Path("execution-a/export_manifest_v1.json"), Path("execution-a/model.FCStd")},
            )

    def test_execute_working_copy_traversal_to_non_root_is_invalid_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working = self._make_working_copy(root)
            outside = root / "outside"
            outside.mkdir()
            traversal_path = working / ".." / "outside"
            result = outside / "result.json"

            run, guarded_calls = self._run_with_downstream_guards(
                self._execute_argv(traversal_path, outside / "export_manifest_v1.json", result)
            )

            self._assert_invalid_arguments(run)
            self._assert_downstream_not_reached(guarded_calls)
            self._assert_no_files_created(result, self._artifact_paths(outside))

    def test_execute_working_copy_symlink_to_non_root_is_invalid_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "real_project"
            target.mkdir()
            working_link = root / WORKING_COPY_DIR_NAME
            self._create_symlink_or_skip(target, working_link)
            result = target / "result.json"

            run, guarded_calls = self._run_with_downstream_guards(
                self._execute_argv(working_link, working_link / "export_manifest_v1.json", result)
            )

            self._assert_invalid_arguments(run)
            self._assert_downstream_not_reached(guarded_calls)
            self._assert_no_files_created(result, self._artifact_paths(target))

    # --- manifest/result containment failures ---

    def test_execute_manifest_inside_missing_working_copy_is_invalid_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working = root / WORKING_COPY_DIR_NAME
            manifest = working / "export_manifest_v1.json"
            result = working / "result.json"

            run, guarded_calls = self._run_with_downstream_guards(
                self._execute_argv(working, manifest, result)
            )

            self._assert_invalid_arguments(run)
            self._assert_downstream_not_reached(guarded_calls)
            self._assert_no_files_created(result, self._artifact_paths(working))

    def test_execute_manifest_outside_working_copy_is_invalid_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working = self._make_working_copy(root)
            manifest = root / "export_manifest_v1.json"
            self._write_manifest(manifest)
            result = working / "result.json"

            run, guarded_calls = self._run_with_downstream_guards(
                self._execute_argv(working, manifest, result)
            )

            self._assert_invalid_arguments(run)
            self._assert_downstream_not_reached(guarded_calls)
            self._assert_no_files_created(result, self._artifact_paths(working))

    def test_execute_result_outside_working_copy_is_invalid_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working = self._make_working_copy(root)
            manifest = working / "export_manifest_v1.json"
            self._write_manifest(manifest)
            result = root / "result.json"

            run, guarded_calls = self._run_with_downstream_guards(
                self._execute_argv(working, manifest, result)
            )

            self._assert_invalid_arguments(run)
            self._assert_downstream_not_reached(guarded_calls)
            self._assert_no_files_created(result, self._artifact_paths(working))

    # --- valid CLI, invalid sourceDocument ---

    def test_execute_missing_source_document_fails_before_freecad_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working = self._make_working_copy(root)
            manifest = working / "export_manifest_v1.json"
            self._write_manifest(manifest, source_document="missing.FCStd")
            result = working / "result.json"

            run, guarded_calls = self._run_with_downstream_guards(
                self._execute_argv(working, manifest, result)
            )

            self._assert_execute_failure(run)
            self._assert_downstream_not_reached(guarded_calls)
            self._assert_failed_result(
                result,
                self._artifact_paths(working),
                stage="source_document_resolution",
            )

    def test_execute_source_document_traversal_escape_fails_before_freecad_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working = self._make_working_copy(root)
            outside = root / "outside.FCStd"
            outside.write_bytes(b"outside")
            manifest = working / "export_manifest_v1.json"
            self._write_manifest(manifest, source_document="../outside.FCStd")
            result = working / "result.json"

            run, guarded_calls = self._run_with_downstream_guards(
                self._execute_argv(working, manifest, result)
            )

            self._assert_execute_failure(run)
            self._assert_downstream_not_reached(guarded_calls)
            self._assert_failed_result(
                result,
                self._artifact_paths(working),
                stage="source_document_resolution",
            )

    def test_execute_source_document_symlink_escape_fails_before_freecad_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            working = self._make_working_copy(root)
            outside = root / "outside.FCStd"
            outside.write_bytes(b"outside")
            link = working / "linked.FCStd"
            self._create_symlink_or_skip(outside, link)
            manifest = working / "export_manifest_v1.json"
            self._write_manifest(manifest, source_document="linked.FCStd")
            result = working / "result.json"

            run, guarded_calls = self._run_with_downstream_guards(
                self._execute_argv(working, manifest, result)
            )

            self._assert_execute_failure(run)
            self._assert_downstream_not_reached(guarded_calls)
            self._assert_failed_result(
                result,
                self._artifact_paths(working),
                stage="source_document_resolution",
            )


if __name__ == "__main__":
    unittest.main()
