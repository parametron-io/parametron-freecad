from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.common.paths import WORKING_COPY_DIR_NAME
from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.runtime import headless


class FakeFreeCAD:
    def Version(self) -> list[str]:
        return ["1", "0", "0", "fake"]


class _FakeExecuteDocument:
    """Fake FreeCAD document for execute mode integration tests."""

    def __init__(
        self,
        name: str = "ParametronTestDoc",
        *,
        recompute_error: Exception | None = None,
    ) -> None:
        self.Name = name
        self._objects: dict = {}
        self.recompute_calls: int = 0
        self.recompute_error = recompute_error
        self.save_calls: int = 0
        self.save_as_calls: int = 0
        self.events: list[str] = []

    def getObject(self, name: str) -> object:
        return self._objects.get(name)

    def recompute(self) -> None:
        self.events.append("recompute")
        self.recompute_calls += 1
        if self.recompute_error is not None:
            raise self.recompute_error

    def save(self) -> None:
        self.events.append("save")
        self.save_calls += 1

    def saveAs(self, path: str) -> None:
        del path
        self.events.append("saveAs")
        self.save_as_calls += 1

    @property
    def Objects(self) -> list[object]:
        return []


class _FakeSpreadsheet:
    def __init__(self, content) -> None:
        self.Content = content


class _EventRecordingObject:
    def __init__(self, document: _FakeExecuteDocument, name: str) -> None:
        object.__setattr__(self, "_document", document)
        object.__setattr__(self, "_name", name)

    def __setattr__(self, key: str, value: object) -> None:
        self._document.events.append(f"assign:{self._name}.{key}={value!r}")
        object.__setattr__(self, key, value)


class _FakeExecuteFreeCAD:
    """Fake FreeCAD module for execute mode integration tests."""

    def __init__(self, document: _FakeExecuteDocument | None = None) -> None:
        self._document = document if document is not None else _FakeExecuteDocument()
        self.open_calls: list[str] = []
        self.close_calls: list[str] = []

    def openDocument(self, path: str) -> _FakeExecuteDocument:
        self.open_calls.append(path)
        return self._document

    def closeDocument(self, name: str) -> None:
        self._document.events.append(f"close:{name}")
        self.close_calls.append(name)


class HeadlessCliArgumentTests(unittest.TestCase):
    def assert_success_result_payload(
        self,
        result_path: Path,
        outputs: list[dict],
    ) -> None:
        self.assertTrue(result_path.exists())
        self.assertEqual(
            result_path.read_bytes(),
            dumps_canonical(
                {
                    "artifacts": [
                        {
                            "format": output["format"],
                            "id": output["id"],
                            "path": output["path"],
                        }
                        for output in outputs
                    ],
                    "schemaVersion": "1.0",
                    "status": "succeeded",
                }
            ).encode("utf-8"),
        )

    def assert_failed_result_payload(
        self,
        result_path: Path,
        *,
        stage: str,
        category: str = "execution",
        code: str = "runtime_failure",
        substring: str | None = None,
    ) -> None:
        self.assertTrue(result_path.exists())
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(payload["status"], "failed")
        self.assertNotIn("artifacts", payload)
        failure = payload["failure"]
        self.assertEqual(failure["boundary"], "execution_entrypoint")
        self.assertEqual(failure["category"], category)
        self.assertEqual(failure["code"], code)
        self.assertEqual(failure["stage"], stage)
        self.assertEqual(failure["message"], " ".join(failure["message"].split()))
        self.assertNotIn("Traceback", failure["message"])
        if substring is not None:
            self.assertIn(substring, failure["message"])

    def _run_main(
        self,
        argv: list[str],
        freecad_module: object = None,
    ) -> tuple[int, io.StringIO, io.StringIO]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = headless.main(
            argv=argv,
            stdout=stdout,
            stderr=stderr,
            freecad_module=freecad_module,
        )
        return exit_code, stdout, stderr

    def _make_working_copy(self, tmp_dir: str) -> Path:
        working = Path(tmp_dir) / WORKING_COPY_DIR_NAME
        working.mkdir()
        return working

    def create_symlink_or_skip(self, target: Path, link_path: Path) -> None:
        try:
            link_path.symlink_to(target)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is unavailable on this platform")

    def _make_valid_manifest_content(self, *, source_document: str = "model.FCStd") -> str:
        return json.dumps({
            "schemaVersion": "1.0",
            "sourceDocument": source_document,
            "parameterAssignments": [],
            "outputs": [],
        })

    def _make_manifest_content(
        self,
        *,
        source_document: str = "model.FCStd",
        assignments: list | None = None,
        outputs: list | None = None,
    ) -> str:
        return json.dumps({
            "schemaVersion": "1.0",
            "sourceDocument": source_document,
            "parameterAssignments": assignments if assignments is not None else [],
            "outputs": outputs if outputs is not None else [],
        })

    def _make_working_copy_with_source(
        self, tmp_dir: str, *, source_name: str = "model.FCStd"
    ) -> tuple[Path, Path]:
        """Return (working_copy, source_file) with a valid manifest already written."""
        working = self._make_working_copy(tmp_dir)
        manifest = working / "export_manifest_v1.json"
        manifest.write_text(
            self._make_valid_manifest_content(source_document=source_name),
            encoding="utf-8",
        )
        source = working / source_name
        source.write_bytes(b"")
        return working, source

    def assert_execute_runtime_failure(
        self,
        exit_code: int,
        stdout: io.StringIO,
        stderr: io.StringIO,
        *,
        substring: str,
    ) -> None:
        self.assertEqual(exit_code, headless.EXECUTION_FAILURE_EXIT_CODE)
        self.assertEqual(stdout.getvalue(), "")
        err = stderr.getvalue()
        self.assertTrue(
            err.startswith(headless.EXECUTION_FAILURE_MESSAGE_PREFIX),
            msg=f"stderr {err!r} does not start with the expected failure prefix",
        )
        self.assertIn(substring, err, msg=f"expected {substring!r} in stderr {err!r}")
        self.assertTrue(err.endswith("\n"), msg=f"stderr {err!r} does not end with newline")
        self.assertEqual(err.count("\n"), 1, msg=f"stderr {err!r} has more than one line")
        self.assertNotIn("Traceback", err)

    def assert_invalid_arguments(
        self,
        exit_code: int,
        stdout: io.StringIO,
        stderr: io.StringIO,
    ) -> None:
        self.assertEqual(exit_code, headless.ARGUMENT_ERROR_EXIT_CODE)
        self.assertEqual(stdout.getvalue(), "")
        err = stderr.getvalue()
        self.assertTrue(
            err.startswith(headless.INVALID_ARGUMENTS_MESSAGE_PREFIX),
            msg=f"stderr {err!r} does not start with the expected prefix",
        )
        self.assertTrue(err.endswith("\n"), msg=f"stderr {err!r} does not end with newline")
        self.assertEqual(err.count("\n"), 1, msg=f"stderr {err!r} has more than one line")
        self.assertNotIn("Traceback", err)
        self.assertNotIn("usage:", err.lower())

    def test_execute_observation_optional_argument_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working, _ = self._make_working_copy_with_source(tmp)
            request = working / "request.json"
            request.write_text('{"observe":{}}', encoding="utf-8")
            base = [
                "execute", "--working-copy", str(working),
                "--manifest", str(working / "export_manifest_v1.json"),
                "--result", str(working / "result.json"),
            ]
            original = headless.parse_headless_arguments(base)
            output_only = headless.parse_headless_arguments(
                [*base, "--output-dir", str(working / "output")]
            )
            observed = headless.parse_headless_arguments(
                [*base, "--output-dir", str(working / "output"),
                 "--observation-request", str(request)]
            )
        self.assertIsNone(original.output_dir)
        self.assertIsNone(original.observation_request)
        self.assertIsNotNone(output_only.output_dir)
        self.assertIsNone(output_only.observation_request)
        self.assertEqual(observed.observation_request, request.resolve())

    def test_observation_request_requires_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working, _ = self._make_working_copy_with_source(tmp)
            request = working / "request.json"
            request.write_text("{}", encoding="utf-8")
            argv = ["execute", "--working-copy", str(working), "--manifest",
                    str(working / "export_manifest_v1.json"), "--result",
                    str(working / "result.json"), "--observation-request", str(request)]
            with self.assertRaisesRegex(headless.HeadlessArgumentError, "requires --output-dir"):
                headless.parse_headless_arguments(argv)

    def test_optional_paths_reject_empty_and_whitespace_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working, _ = self._make_working_copy_with_source(tmp)
            base = ["execute", "--working-copy", str(working), "--manifest",
                    str(working / "export_manifest_v1.json"), "--result",
                    str(working / "result.json")]
            for option in ("--output-dir", "--observation-request"):
                for value in ("", "   "):
                    with self.subTest(option=option, value=value), self.assertRaisesRegex(
                        headless.HeadlessArgumentError, "must not be empty"
                    ):
                        headless.parse_headless_arguments([*base, option, value])

    def test_observation_paths_must_be_confined_and_have_required_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working, _ = self._make_working_copy_with_source(tmp)
            outside = Path(tmp) / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            request_dir = working / "request-dir"
            request_dir.mkdir()
            output_file = working / "output-file"
            output_file.write_text("x", encoding="utf-8")
            base = ["execute", "--working-copy", str(working), "--manifest",
                    str(working / "export_manifest_v1.json"), "--result",
                    str(working / "result.json")]
            cases = (
                (["--output-dir", str(working / "out"), "--observation-request", str(outside)], "outside"),
                (["--output-dir", str(Path(tmp) / "outside-output")], "outside"),
                (["--output-dir", str(working / "out"), "--observation-request", str(working / "missing.json")], "expected existing file"),
                (["--output-dir", str(working / "out"), "--observation-request", str(request_dir)], "expected existing file"),
                (["--output-dir", str(output_file)], "not a directory"),
            )
            for arguments, message in cases:
                with self.subTest(arguments=arguments), self.assertRaisesRegex(
                    headless.HeadlessArgumentError, message
                ):
                    headless.parse_headless_arguments([*base, *arguments])

    def test_reference_traversal_request_optional_argument_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working, _ = self._make_working_copy_with_source(tmp)
            request = working / "traversal-request.json"
            request.write_text("not loaded by argument validation", encoding="utf-8")
            output = working / "output"
            output.mkdir()
            base = [
                "execute",
                "--working-copy",
                str(working),
                "--manifest",
                str(working / "export_manifest_v1.json"),
                "--result",
                str(working / "result.json"),
            ]

            absent = headless.parse_headless_arguments(base)
            present = headless.parse_headless_arguments(
                [
                    *base,
                    "--output-dir",
                    str(output),
                    "--reference-traversal-request",
                    str(request),
                ]
            )

        self.assertIsNone(absent.reference_traversal_request)
        self.assertEqual(present.reference_traversal_request, request.resolve())

    def test_reference_traversal_requires_existing_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working, _ = self._make_working_copy_with_source(tmp)
            request = working / "traversal-request.json"
            request.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(
                headless.HeadlessArgumentError,
                "must be an existing directory when reference traversal",
            ):
                headless.parse_headless_arguments(
                    [
                        "execute",
                        "--working-copy",
                        str(working),
                        "--manifest",
                        str(working / "export_manifest_v1.json"),
                        "--result",
                        str(working / "result.json"),
                        "--output-dir",
                        str(working / "missing-output"),
                        "--reference-traversal-request",
                        str(request),
                    ]
                )

    def test_reference_traversal_request_requires_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working, _ = self._make_working_copy_with_source(tmp)
            request = working / "traversal-request.json"
            request.write_text("{}", encoding="utf-8")
            argv = [
                "execute",
                "--working-copy",
                str(working),
                "--manifest",
                str(working / "export_manifest_v1.json"),
                "--result",
                str(working / "result.json"),
                "--reference-traversal-request",
                str(request),
            ]

            with self.assertRaisesRegex(
                headless.HeadlessArgumentError,
                "--reference-traversal-request requires --output-dir",
            ):
                headless.parse_headless_arguments(argv)

    def test_reference_traversal_request_rejects_empty_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working, _ = self._make_working_copy_with_source(tmp)
            base = [
                "execute",
                "--working-copy",
                str(working),
                "--manifest",
                str(working / "export_manifest_v1.json"),
                "--result",
                str(working / "result.json"),
                "--output-dir",
                str(working / "output"),
            ]
            for value in ("", "   "):
                with self.subTest(value=value), self.assertRaisesRegex(
                    headless.HeadlessArgumentError, "must not be empty"
                ):
                    headless.parse_headless_arguments(
                        [*base, "--reference-traversal-request", value]
                    )

    def test_reference_traversal_request_must_be_confined_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working, _ = self._make_working_copy_with_source(tmp)
            outside = Path(tmp) / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            request_dir = working / "request-dir"
            request_dir.mkdir()
            base = [
                "execute",
                "--working-copy",
                str(working),
                "--manifest",
                str(working / "export_manifest_v1.json"),
                "--result",
                str(working / "result.json"),
                "--output-dir",
                str(working / "output"),
            ]
            cases = (
                (outside, "outside"),
                (working / "missing.json", "expected existing file"),
                (request_dir, "expected existing file"),
            )
            for path, message in cases:
                with self.subTest(path=path), self.assertRaisesRegex(
                    headless.HeadlessArgumentError, message
                ):
                    headless.parse_headless_arguments(
                        [*base, "--reference-traversal-request", str(path)]
                    )

    def test_reference_traversal_argument_validation_does_not_load_content(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working, _ = self._make_working_copy_with_source(tmp)
            request = working / "traversal-request.json"
            request.write_bytes(b"\xff malformed and not UTF-8")
            output = working / "output"
            output.mkdir()

            invocation = headless.parse_headless_arguments(
                [
                    "execute",
                    "--working-copy",
                    str(working),
                    "--manifest",
                    str(working / "export_manifest_v1.json"),
                    "--result",
                    str(working / "result.json"),
                    "--output-dir",
                    str(output),
                    "--reference-traversal-request",
                    str(request),
                ]
            )

        self.assertEqual(invocation.reference_traversal_request, request.resolve())

    # --- smoke mode ---

    def test_no_args_with_fake_freecad_returns_success_and_stable_json(self) -> None:
        exit_code, stdout, stderr = self._run_main([], freecad_module=FakeFreeCAD())

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["host"], "freecadcmd")
        self.assertIn("freecadVersion", payload)

    def test_explicit_smoke_with_fake_freecad_returns_same_as_no_args(self) -> None:
        stdout_no_args = io.StringIO()
        stdout_smoke = io.StringIO()

        exit_no_args = headless.main(
            argv=[],
            stdout=stdout_no_args,
            stderr=io.StringIO(),
            freecad_module=FakeFreeCAD(),
        )
        exit_smoke = headless.main(
            argv=["smoke"],
            stdout=stdout_smoke,
            stderr=io.StringIO(),
            freecad_module=FakeFreeCAD(),
        )

        self.assertEqual(exit_no_args, 0)
        self.assertEqual(exit_smoke, 0)
        self.assertEqual(stdout_no_args.getvalue(), stdout_smoke.getvalue())

    def test_no_args_freecad_unavailable_returns_exit_code_2_and_exact_stderr(
        self,
    ) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch(
            "parametron_freecad.runtime.headless.import_module",
            side_effect=ImportError("No module named FreeCAD"),
        ):
            exit_code = headless.main(argv=[], stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, headless.FREECAD_UNAVAILABLE_EXIT_CODE)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            stderr.getvalue(),
            f"{headless.FREECAD_UNAVAILABLE_MESSAGE}\n",
        )

    def test_explicit_smoke_freecad_unavailable_returns_exit_code_2(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch(
            "parametron_freecad.runtime.headless.import_module",
            side_effect=ImportError("No module named FreeCAD"),
        ):
            exit_code = headless.main(argv=["smoke"], stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, headless.FREECAD_UNAVAILABLE_EXIT_CODE)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            stderr.getvalue(),
            f"{headless.FREECAD_UNAVAILABLE_MESSAGE}\n",
        )

    # --- valid execute mode: FreeCAD required after pre-validation ---

    def test_execute_valid_args_no_freecad_returns_freecad_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, _source = self._make_working_copy_with_source(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            result_path = working / "result.json"

            with mock.patch(
                "parametron_freecad.runtime.headless.import_module",
                side_effect=ImportError("No module named FreeCAD"),
            ):
                exit_code, stdout, stderr = self._run_main([
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ])

            self.assertEqual(exit_code, headless.FREECAD_UNAVAILABLE_EXIT_CODE)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(
                stderr.getvalue(),
                f"{headless.FREECAD_UNAVAILABLE_MESSAGE}\n",
            )

    def test_execute_valid_args_no_freecad_writes_failed_result_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, _source = self._make_working_copy_with_source(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            result_path = working / "result.json"

            with mock.patch(
                "parametron_freecad.runtime.headless.import_module",
                side_effect=ImportError("No module named FreeCAD"),
            ):
                self._run_main([
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ])

            self.assert_failed_result_payload(
                result_path,
                category="freecad_unavailable",
                code="freecad_unavailable",
                stage="freecad_resolution",
                substring="FreeCAD module is not available",
            )

    def test_execute_valid_args_requires_freecad_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, _source = self._make_working_copy_with_source(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            result_path = working / "result.json"

            with mock.patch(
                "parametron_freecad.runtime.headless.import_module",
                side_effect=ImportError("No module named FreeCAD"),
            ):
                exit_code, _stdout, _stderr = self._run_main([
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ])

            self.assertEqual(exit_code, headless.FREECAD_UNAVAILABLE_EXIT_CODE)

    # --- valid execute mode with fake FreeCAD ---

    def test_execute_valid_args_with_fake_freecad_returns_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, _source = self._make_working_copy_with_source(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            result_path = working / "result.json"

            exit_code, stdout, stderr = self._run_main(
                [
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ],
                freecad_module=_FakeExecuteFreeCAD(),
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assert_success_result_payload(result_path, [])

    def test_execute_valid_args_with_fake_freecad_writes_result_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, _source = self._make_working_copy_with_source(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            result_path = working / "result.json"

            exit_code, _stdout, _stderr = self._run_main(
                [
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ],
                freecad_module=_FakeExecuteFreeCAD(),
            )

            self.assert_success_result_payload(result_path, [])

    def test_execute_valid_args_with_fake_freecad_opens_source_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, source = self._make_working_copy_with_source(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            result_path = working / "result.json"

            fake_freecad = _FakeExecuteFreeCAD()

            exit_code, _stdout, _stderr = self._run_main(
                [
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ],
                freecad_module=fake_freecad,
            )

            self.assertEqual(len(fake_freecad.open_calls), 1)
            self.assertEqual(fake_freecad.open_calls[0], str(source.resolve()))

    def test_execute_valid_args_with_fake_freecad_closes_document_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, _source = self._make_working_copy_with_source(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            result_path = working / "result.json"

            fake_freecad = _FakeExecuteFreeCAD()

            exit_code, _stdout, _stderr = self._run_main(
                [
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ],
                freecad_module=fake_freecad,
            )

            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])

    # --- assignment application through execute mode ---

    def test_execute_with_assignments_applies_values_to_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            result_path = working / "result.json"

            assignments = [
                {"target": "Box.Length", "value": 100.0, "valueKind": "scalar"},
            ]
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(assignments=assignments),
                encoding="utf-8",
            )

            fake_obj = _EventRecordingObject(document=None, name="Box")
            doc = _FakeExecuteDocument()
            object.__setattr__(fake_obj, "_document", doc)
            doc._objects["Box"] = fake_obj
            fake_freecad = _FakeExecuteFreeCAD(document=doc)

            exit_code, _stdout, _stderr = self._run_main(
                [
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ],
                freecad_module=fake_freecad,
            )

            self.assertEqual(fake_obj.Length, 100.0)
            self.assertEqual(exit_code, 0)
            self.assertEqual(doc.recompute_calls, 1)
            self.assertEqual(
                doc.events,
                ["assign:Box.Length=100.0", "recompute", "save", "close:ParametronTestDoc"],
            )
            self.assertEqual(doc.save_calls, 1)
            self.assertEqual(doc.save_as_calls, 0)
            self.assert_success_result_payload(result_path, [])

    def test_execute_assignment_failure_still_closes_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            result_path = working / "result.json"

            assignments = [
                {"target": "Box.Length", "value": 100.0, "valueKind": "scalar"},
            ]
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(assignments=assignments),
                encoding="utf-8",
            )

            doc = _FakeExecuteDocument()
            fake_freecad = _FakeExecuteFreeCAD(document=doc)

            self._run_main(
                [
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ],
                freecad_module=fake_freecad,
            )

            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            self.assert_failed_result_payload(
                result_path,
                stage="parameter_assignment",
                substring="object 'Box' was not found",
            )

    def test_execute_assignment_failure_returns_failure_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            result_path = working / "result.json"

            assignments = [
                {"target": "Missing.Prop", "value": 1.0, "valueKind": "scalar"},
            ]
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(assignments=assignments),
                encoding="utf-8",
            )

            doc = _FakeExecuteDocument()
            fake_freecad = _FakeExecuteFreeCAD(document=doc)

            exit_code, stdout, stderr = self._run_main(
                [
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ],
                freecad_module=fake_freecad,
            )

            self.assertEqual(exit_code, headless.EXECUTION_FAILURE_EXIT_CODE)
            self.assertEqual(stdout.getvalue(), "")
            err = stderr.getvalue()
            self.assertTrue(
                err.startswith(headless.EXECUTION_FAILURE_MESSAGE_PREFIX),
                msg=f"stderr {err!r} does not start with failure prefix",
            )
            self.assertNotIn("Traceback", err)

    # --- recompute ---

    def test_execute_recomputes_document_once_before_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, _source = self._make_working_copy_with_source(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            result_path = working / "result.json"

            doc = _FakeExecuteDocument()
            fake_freecad = _FakeExecuteFreeCAD(document=doc)

            exit_code, _stdout, _stderr = self._run_main(
                [
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ],
                freecad_module=fake_freecad,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(doc.recompute_calls, 1)
            self.assertEqual(doc.events, ["recompute", "save", "close:ParametronTestDoc"])
            self.assertEqual(doc.save_calls, 1)
            self.assertEqual(doc.save_as_calls, 0)
            self.assert_success_result_payload(result_path, [])

    def test_execute_calls_csv_export_then_pdf_export_after_recompute_and_before_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            exports_dir = working / "exports"
            exports_dir.mkdir()
            result_path = working / "result.json"
            doc = _FakeExecuteDocument()
            fake_obj = _EventRecordingObject(document=doc, name="Box")
            doc._objects["Box"] = fake_obj
            fake_freecad = _FakeExecuteFreeCAD(document=doc)
            export_calls: list[tuple[str, object, list[dict], Path]] = []
            assignments = [
                {"target": "Box.Length", "value": 100.0, "valueKind": "scalar"},
            ]
            outputs = [
                {"id": "report", "format": "csv", "path": "exports/report.csv"},
                {"id": "part", "format": "step", "path": "exports/part.step"},
                {"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"},
            ]
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(assignments=assignments, outputs=outputs),
                encoding="utf-8",
            )
            original_write_success_result = headless.write_success_result

            def fake_export_step_artifacts(document, received_outputs, *, working_copy, import_module=None) -> None:
                del import_module
                export_calls.append(("step", document, list(received_outputs), working_copy))
                document.events.append("step-export")

            def fake_export_csv_artifacts(document, received_outputs, *, working_copy) -> None:
                export_calls.append(("csv", document, list(received_outputs), working_copy))
                document.events.append("csv-export")

            def fake_export_pdf_artifacts(document, received_outputs, *, working_copy, techdraw_gui_module=None) -> None:
                del techdraw_gui_module
                export_calls.append(("pdf", document, list(received_outputs), working_copy))
                document.events.append("pdf-export")

            def fake_write_success_result(path, received_outputs) -> None:
                doc.events.append("result-write")
                original_write_success_result(path, received_outputs)

            with mock.patch(
                "parametron_freecad.runtime.headless.export_step_artifacts",
                side_effect=fake_export_step_artifacts,
            ), mock.patch(
                "parametron_freecad.runtime.headless.export_csv_artifacts",
                side_effect=fake_export_csv_artifacts,
            ), mock.patch(
                "parametron_freecad.runtime.headless.export_pdf_artifacts",
                side_effect=fake_export_pdf_artifacts,
            ), mock.patch(
                "parametron_freecad.runtime.headless.write_success_result",
                side_effect=fake_write_success_result,
            ):
                exit_code, stdout, stderr = self._run_main(
                    [
                        "execute",
                        "--working-copy", str(working),
                        "--manifest", str(manifest),
                        "--result", str(result_path),
                    ],
                    freecad_module=fake_freecad,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(
                doc.events,
                [
                    "assign:Box.Length=100.0",
                    "recompute",
                    "save",
                    "step-export",
                    "csv-export",
                    "pdf-export",
                    "close:ParametronTestDoc",
                    "result-write",
                ],
            )
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            self.assertEqual(
                export_calls,
                [
                    ("step", doc, outputs, working.resolve()),
                    ("csv", doc, outputs, working.resolve()),
                    ("pdf", doc, outputs, working.resolve()),
                ],
            )
            self.assert_success_result_payload(result_path, outputs)

    def test_execute_csv_export_failure_returns_controlled_error_and_closes_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            exports_dir = working / "exports"
            exports_dir.mkdir()
            result_path = working / "result.json"
            outputs = [{"id": "MissingSheet", "format": "csv", "path": "exports/report.csv"}]
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(outputs=outputs),
                encoding="utf-8",
            )

            doc = _FakeExecuteDocument()
            fake_freecad = _FakeExecuteFreeCAD(document=doc)

            exit_code, stdout, stderr = self._run_main(
                [
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ],
                freecad_module=fake_freecad,
            )

            self.assert_execute_runtime_failure(
                exit_code,
                stdout,
                stderr,
                substring="document.getObject returned no spreadsheet object (id='MissingSheet')",
            )
            self.assertEqual(doc.events, ["recompute", "save", "close:ParametronTestDoc"])
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            self.assertFalse((exports_dir / "report.csv").exists())
            self.assert_failed_result_payload(
                result_path,
                stage="artifact_export",
                substring="document.getObject returned no spreadsheet object",
            )

    def test_execute_successful_csv_export_writes_result_file_and_returns_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            exports_dir = working / "exports"
            exports_dir.mkdir()
            result_path = working / "result.json"
            csv_path = exports_dir / "report.csv"
            outputs = [{"id": "Sheet", "format": "csv", "path": "exports/report.csv"}]
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(outputs=outputs),
                encoding="utf-8",
            )

            doc = _FakeExecuteDocument()
            doc._objects["Sheet"] = _FakeSpreadsheet({"B1": "right", "A1": "left"})
            fake_freecad = _FakeExecuteFreeCAD(document=doc)

            exit_code, stdout, stderr = self._run_main(
                [
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ],
                freecad_module=fake_freecad,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(doc.events, ["recompute", "save", "close:ParametronTestDoc"])
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            self.assertEqual(csv_path.read_bytes(), b"left,right\n")
            self.assert_success_result_payload(result_path, outputs)

    def test_execute_success_writes_manifest_ordered_result_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            (working / "exports").mkdir()
            result_path = working / "result.json"
            outputs = [
                {"id": "part", "format": "step", "path": "exports/part.step"},
                {"id": "report", "format": "csv", "path": "exports/report.csv"},
                {"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"},
            ]
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(outputs=outputs),
                encoding="utf-8",
            )
            doc = _FakeExecuteDocument()
            fake_freecad = _FakeExecuteFreeCAD(document=doc)

            with mock.patch(
                "parametron_freecad.runtime.headless.export_step_artifacts",
            ), mock.patch(
                "parametron_freecad.runtime.headless.export_csv_artifacts",
            ), mock.patch(
                "parametron_freecad.runtime.headless.export_pdf_artifacts",
            ):
                exit_code, stdout, stderr = self._run_main(
                    [
                        "execute",
                        "--working-copy", str(working),
                        "--manifest", str(manifest),
                        "--result", str(result_path),
                    ],
                    freecad_module=fake_freecad,
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(doc.events, ["recompute", "save", "close:ParametronTestDoc"])
            self.assert_success_result_payload(result_path, outputs)
            self.assertEqual(
                json.loads(result_path.read_text(encoding="utf-8")),
                {
                    "artifacts": [
                        {"format": "step", "id": "part", "path": "exports/part.step"},
                        {"format": "csv", "id": "report", "path": "exports/report.csv"},
                        {"format": "pdf", "id": "drawing", "path": "exports/drawing.pdf"},
                    ],
                    "schemaVersion": "1.0",
                    "status": "succeeded",
                },
            )

    def test_execute_step_export_failure_returns_controlled_error_and_closes_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            result_path = working / "result.json"
            outputs = [{"id": "part", "format": "step", "path": "part.step"}]
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(outputs=outputs),
                encoding="utf-8",
            )

            doc = _FakeExecuteDocument()
            fake_freecad = _FakeExecuteFreeCAD(document=doc)

            def fake_export_step_artifacts(document, received_outputs, *, working_copy, import_module=None) -> None:
                del received_outputs, working_copy, import_module
                document.events.append("step-export")
                raise headless.StepArtifactExportError("fake step export boom")

            with mock.patch(
                "parametron_freecad.runtime.headless.export_step_artifacts",
                side_effect=fake_export_step_artifacts,
            ):
                exit_code, stdout, stderr = self._run_main(
                    [
                        "execute",
                        "--working-copy", str(working),
                        "--manifest", str(manifest),
                        "--result", str(result_path),
                    ],
                    freecad_module=fake_freecad,
                )

            self.assert_execute_runtime_failure(
                exit_code,
                stdout,
                stderr,
                substring="fake step export boom",
            )
            self.assertEqual(doc.recompute_calls, 1)
            self.assertEqual(doc.events, ["recompute", "save", "step-export", "close:ParametronTestDoc"])
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            self.assert_failed_result_payload(
                result_path,
                stage="artifact_export",
                substring="fake step export boom",
            )

    def test_execute_pdf_export_failure_returns_controlled_error_and_closes_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            exports_dir = working / "exports"
            exports_dir.mkdir()
            result_path = working / "result.json"
            outputs = [{"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf"}]
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(outputs=outputs),
                encoding="utf-8",
            )

            doc = _FakeExecuteDocument()
            fake_freecad = _FakeExecuteFreeCAD(document=doc)

            def fake_export_pdf_artifacts(
                document,
                received_outputs,
                *,
                working_copy,
                techdraw_gui_module=None,
            ) -> None:
                del received_outputs, working_copy, techdraw_gui_module
                document.events.append("pdf-export")
                raise headless.PdfArtifactExportError("fake pdf export boom")

            with mock.patch(
                "parametron_freecad.runtime.headless.export_pdf_artifacts",
                side_effect=fake_export_pdf_artifacts,
            ):
                exit_code, stdout, stderr = self._run_main(
                    [
                        "execute",
                        "--working-copy", str(working),
                        "--manifest", str(manifest),
                        "--result", str(result_path),
                    ],
                    freecad_module=fake_freecad,
                )

            self.assert_execute_runtime_failure(
                exit_code,
                stdout,
                stderr,
                substring="fake pdf export boom",
            )
            self.assertEqual(doc.recompute_calls, 1)
            self.assertEqual(doc.events, ["recompute", "save", "pdf-export", "close:ParametronTestDoc"])
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            self.assertFalse((exports_dir / "drawing.pdf").exists())
            self.assert_failed_result_payload(
                result_path,
                stage="artifact_export",
                substring="fake pdf export boom",
            )

    def test_execute_result_write_failure_returns_controlled_error_and_closes_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            result_path = working / "result.json"
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(outputs=[]),
                encoding="utf-8",
            )
            doc = _FakeExecuteDocument()
            fake_freecad = _FakeExecuteFreeCAD(document=doc)

            with mock.patch(
                "parametron_freecad.runtime.headless.write_success_result",
                side_effect=headless.ResultWriteError("failed to write result file fake/result.json: boom"),
            ):
                exit_code, stdout, stderr = self._run_main(
                    [
                        "execute",
                        "--working-copy", str(working),
                        "--manifest", str(manifest),
                        "--result", str(result_path),
                    ],
                    freecad_module=fake_freecad,
                )

            self.assert_execute_runtime_failure(
                exit_code,
                stdout,
                stderr,
                substring="failed to write result file fake/result.json: boom",
            )
            self.assertEqual(doc.events, ["recompute", "save", "close:ParametronTestDoc"])
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            self.assertFalse(result_path.exists())

    def test_execute_recompute_failure_returns_controlled_error_and_closes_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            result_path = working / "result.json"
            step_path = working / "output.step"
            csv_path = working / "output.csv"
            pdf_path = working / "output.pdf"

            assignments = [
                {"target": "Box.Length", "value": 100.0, "valueKind": "scalar"},
            ]
            outputs = [
                {"id": "part", "format": "step", "path": "output.step"},
                {"id": "report", "format": "csv", "path": "output.csv"},
                {"id": "drawing", "format": "pdf", "path": "output.pdf"},
            ]
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(assignments=assignments, outputs=outputs),
                encoding="utf-8",
            )

            doc = _FakeExecuteDocument(recompute_error=RuntimeError("fake recompute boom"))
            fake_obj = _EventRecordingObject(document=doc, name="Box")
            doc._objects["Box"] = fake_obj
            fake_freecad = _FakeExecuteFreeCAD(document=doc)

            exit_code, stdout, stderr = self._run_main(
                [
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ],
                freecad_module=fake_freecad,
            )

            self.assert_execute_runtime_failure(
                exit_code,
                stdout,
                stderr,
                substring="document recompute raised an exception: fake recompute boom",
            )
            self.assertEqual(fake_obj.Length, 100.0)
            self.assertEqual(doc.recompute_calls, 1)
            self.assertEqual(
                doc.events,
                ["assign:Box.Length=100.0", "recompute", "close:ParametronTestDoc"],
            )
            self.assertEqual(fake_freecad.close_calls, ["ParametronTestDoc"])
            self.assertEqual(doc.save_calls, 0)
            self.assertEqual(doc.save_as_calls, 0)
            self.assert_failed_result_payload(
                result_path,
                stage="recompute",
                substring="document recompute raised an exception: fake recompute boom",
            )
            self.assertFalse(step_path.exists())
            self.assertFalse(csv_path.exists())
            self.assertFalse(pdf_path.exists())

    # --- no output side effects ---

    def test_execute_does_not_create_step_artifact_when_step_export_is_stubbed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            source = working / "model.FCStd"
            source.write_bytes(b"")
            result_path = working / "result.json"

            outputs = [{"id": "part", "format": "step", "path": "output.step"}]
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(outputs=outputs),
                encoding="utf-8",
            )

            fake_freecad = _FakeExecuteFreeCAD()

            with mock.patch("parametron_freecad.runtime.headless.export_step_artifacts"):
                self._run_main(
                    [
                        "execute",
                        "--working-copy", str(working),
                        "--manifest", str(manifest),
                        "--result", str(result_path),
                    ],
                    freecad_module=fake_freecad,
                )

            self.assertFalse((working / "output.step").exists())
            self.assert_success_result_payload(result_path, outputs)

    # --- manifest validation failure ---

    def test_execute_invalid_manifest_fails_with_controlled_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text("{}", encoding="utf-8")
            result_path = working / "result.json"

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
                "--result", str(result_path),
            ])

            self.assert_execute_runtime_failure(
                exit_code, stdout, stderr, substring="manifest validation failed"
            )

    def test_execute_invalid_manifest_writes_failed_result_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text("{}", encoding="utf-8")
            result_path = working / "result.json"

            self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
                "--result", str(result_path),
            ])

            self.assert_failed_result_payload(
                result_path,
                stage="manifest_validation",
                substring="manifest validation failed",
            )

    def test_execute_invalid_manifest_does_not_require_freecad(self) -> None:
        original_import = __import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "FreeCAD":
                raise AssertionError("FreeCAD must not be imported during manifest validation failure")
            return original_import(name, globals, locals, fromlist, level)

        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text("{}", encoding="utf-8")
            result_path = working / "result.json"

            with mock.patch("builtins.__import__", side_effect=guarded_import):
                exit_code, _stdout, _stderr = self._run_main([
                    "execute",
                    "--working-copy", str(working),
                    "--manifest", str(manifest),
                    "--result", str(result_path),
                ])

            self.assertEqual(exit_code, headless.EXECUTION_FAILURE_EXIT_CODE)

    # --- sourceDocument boundary enforcement ---

    def test_execute_source_document_traversal_escape_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            outside = Path(tmp_dir) / "source.FCStd"
            outside.write_bytes(b"")
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_valid_manifest_content(source_document="../source.FCStd"),
                encoding="utf-8",
            )
            result_path = working / "result.json"

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
                "--result", str(result_path),
            ])

            self.assert_execute_runtime_failure(
                exit_code, stdout, stderr, substring="sourceDocument"
            )
            self.assert_failed_result_payload(result_path, stage="source_document_resolution")

    def test_execute_source_document_absolute_escape_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            outside = Path(tmp_dir) / "source.FCStd"
            outside.write_bytes(b"")
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_valid_manifest_content(source_document=str(outside)),
                encoding="utf-8",
            )
            result_path = working / "result.json"

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
                "--result", str(result_path),
            ])

            self.assert_execute_runtime_failure(
                exit_code, stdout, stderr, substring="sourceDocument"
            )
            self.assert_failed_result_payload(result_path, stage="source_document_resolution")

    def test_execute_source_document_missing_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_valid_manifest_content(source_document="nonexistent.FCStd"),
                encoding="utf-8",
            )
            result_path = working / "result.json"

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
                "--result", str(result_path),
            ])

            self.assert_execute_runtime_failure(
                exit_code, stdout, stderr, substring="sourceDocument"
            )
            self.assert_failed_result_payload(result_path, stage="source_document_resolution")

    def test_execute_source_document_symlink_escape_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            outside = Path(tmp_dir) / "real_source.FCStd"
            outside.write_bytes(b"")
            link_path = working / "link_source.FCStd"
            self.create_symlink_or_skip(outside, link_path)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text(
                self._make_valid_manifest_content(source_document="link_source.FCStd"),
                encoding="utf-8",
            )
            result_path = working / "result.json"

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
                "--result", str(result_path),
            ])

            self.assert_execute_runtime_failure(
                exit_code, stdout, stderr, substring="sourceDocument"
            )
            self.assert_failed_result_payload(result_path, stage="source_document_resolution")

    # --- missing required execute arguments ---

    def test_execute_missing_all_args_is_invalid(self) -> None:
        exit_code, stdout, stderr = self._run_main(["execute"])
        self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_missing_working_copy_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text("{}", encoding="utf-8")

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--manifest", str(manifest),
                "--result", str(working / "result.json"),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_missing_manifest_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--result", str(working / "result.json"),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_missing_result_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text("{}", encoding="utf-8")

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    # --- invalid working-copy path ---

    def test_execute_working_copy_nonexistent_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / WORKING_COPY_DIR_NAME

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(missing),
                "--manifest", str(missing / "export_manifest_v1.json"),
                "--result", str(missing / "result.json"),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_working_copy_is_file_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / WORKING_COPY_DIR_NAME
            file_path.write_text("not a directory", encoding="utf-8")

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(file_path),
                "--manifest", str(file_path),
                "--result", str(Path(tmp_dir) / "result.json"),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_working_copy_arbitrary_safe_name_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            supplied_root = Path(tmp_dir) / "model_output"
            supplied_root.mkdir()
            manifest = supplied_root / "export_manifest_v1.json"
            manifest.write_text(self._make_valid_manifest_content(), encoding="utf-8")
            (supplied_root / "model.FCStd").write_bytes(b"")

            invocation = headless.parse_headless_arguments([
                "execute",
                "--working-copy", str(supplied_root),
                "--manifest", str(manifest),
                "--result", str(supplied_root / "result.json"),
            ])
            self.assertEqual(invocation.working_copy, supplied_root.resolve())
            self.assertEqual(invocation.manifest, manifest.resolve())
            self.assertEqual(invocation.result, (supplied_root / "result.json").resolve())

    def test_execute_working_copy_nested_execution_leaf_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent_working = Path(tmp_dir) / "product" / WORKING_COPY_DIR_NAME
            supplied_leaf = parent_working / "execution-a"
            supplied_leaf.mkdir(parents=True)
            manifest = supplied_leaf / "export_manifest_v1.json"
            manifest.write_text(self._make_valid_manifest_content(), encoding="utf-8")
            (supplied_leaf / "model.FCStd").write_bytes(b"")

            invocation = headless.parse_headless_arguments([
                "execute",
                "--working-copy", str(supplied_leaf),
                "--manifest", str(manifest),
                "--result", str(supplied_leaf / "result.json"),
            ])
            self.assertEqual(invocation.working_copy, supplied_leaf.resolve())
            self.assertNotEqual(invocation.working_copy, parent_working.resolve())

    def test_execute_working_copy_direct_working_root_remains_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, _source = self._make_working_copy_with_source(tmp_dir)
            invocation = headless.parse_headless_arguments([
                "execute", "--working-copy", str(working),
                "--manifest", str(working / "export_manifest_v1.json"),
                "--result", str(working / "result.json"),
            ])
            self.assertEqual(invocation.working_copy, working.resolve())

    def test_execute_working_copy_root_symlink_is_canonicalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "actual-execution"
            target.mkdir()
            manifest = target / "export_manifest_v1.json"
            manifest.write_text(self._make_valid_manifest_content(), encoding="utf-8")
            (target / "model.FCStd").write_bytes(b"")
            supplied_link = Path(tmp_dir) / "execution-link"
            self.create_symlink_or_skip(target, supplied_link)

            invocation = headless.parse_headless_arguments([
                "execute", "--working-copy", str(supplied_link),
                "--manifest", str(supplied_link / "export_manifest_v1.json"),
                "--result", str(supplied_link / "result.json"),
            ])
            self.assertEqual(invocation.working_copy, target.resolve())
            self.assertEqual(invocation.result, (target / "result.json").resolve())

    def test_execute_rejects_sibling_execution_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent = Path(tmp_dir) / "product" / WORKING_COPY_DIR_NAME
            execution_a = parent / "execution-a"
            execution_b = parent / "execution-b"
            execution_a.mkdir(parents=True)
            execution_b.mkdir()
            manifest_a = execution_a / "export_manifest_v1.json"
            manifest_b = execution_b / "export_manifest_v1.json"
            for manifest in (manifest_a, manifest_b):
                manifest.write_text(self._make_valid_manifest_content(), encoding="utf-8")
            (execution_a / "model.FCStd").write_bytes(b"")
            request_b = execution_b / "request.json"
            request_b.write_text("{}", encoding="utf-8")
            base = ["execute", "--working-copy", str(execution_a)]
            cases = {
                "manifest": ["--manifest", str(manifest_b), "--result", str(execution_a / "result.json")],
                "result": ["--manifest", str(manifest_a), "--result", str(execution_b / "result.json")],
                "output": ["--manifest", str(manifest_a), "--result", str(execution_a / "result.json"), "--output-dir", str(execution_b / "outputs")],
                "observation": ["--manifest", str(manifest_a), "--result", str(execution_a / "result.json"), "--output-dir", str(execution_a / "outputs"), "--observation-request", str(request_b)],
            }
            for surface, arguments in cases.items():
                with self.subTest(surface=surface), self.assertRaisesRegex(
                    headless.HeadlessArgumentError, "escapes parent directory"
                ):
                    headless.parse_headless_arguments([*base, *arguments])

    def test_execute_rejects_parent_working_root_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent = Path(tmp_dir) / "product" / WORKING_COPY_DIR_NAME
            leaf = parent / "execution-a"
            leaf.mkdir(parents=True)
            manifest = leaf / "export_manifest_v1.json"
            manifest.write_text(self._make_valid_manifest_content(), encoding="utf-8")
            shared_manifest = parent / "shared.json"
            shared_manifest.write_text(self._make_valid_manifest_content(), encoding="utf-8")
            base = ["execute", "--working-copy", str(leaf)]
            cases = (
                ["--manifest", str(shared_manifest), "--result", str(leaf / "result.json")],
                ["--manifest", str(manifest), "--result", str(parent / "shared-result.json")],
            )
            for arguments in cases:
                with self.subTest(arguments=arguments), self.assertRaisesRegex(
                    headless.HeadlessArgumentError, "escapes parent directory"
                ):
                    headless.parse_headless_arguments([*base, *arguments])

    def test_execute_supplied_leaf_rejects_symlink_escapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent = Path(tmp_dir) / "product" / WORKING_COPY_DIR_NAME
            leaf = parent / "execution-a"
            outside = parent / "shared"
            leaf.mkdir(parents=True)
            outside.mkdir()
            manifest = leaf / "export_manifest_v1.json"
            manifest.write_text(self._make_valid_manifest_content(), encoding="utf-8")
            outside_manifest = outside / "manifest.json"
            outside_manifest.write_text(self._make_valid_manifest_content(), encoding="utf-8")
            outside_request = outside / "request.json"
            outside_request.write_text("{}", encoding="utf-8")
            manifest_link = leaf / "manifest-link.json"
            output_link = leaf / "output-link"
            request_link = leaf / "request-link.json"
            self.create_symlink_or_skip(outside_manifest, manifest_link)
            self.create_symlink_or_skip(outside, output_link)
            self.create_symlink_or_skip(outside_request, request_link)
            base = ["execute", "--working-copy", str(leaf)]
            cases = (
                ["--manifest", str(manifest_link), "--result", str(leaf / "result.json")],
                ["--manifest", str(manifest), "--result", str(leaf / "result.json"), "--output-dir", str(output_link)],
                ["--manifest", str(manifest), "--result", str(leaf / "result.json"), "--output-dir", str(leaf / "outputs"), "--observation-request", str(request_link)],
            )
            for arguments in cases:
                with self.subTest(arguments=arguments), self.assertRaisesRegex(
                    headless.HeadlessArgumentError, "escapes parent directory"
                ):
                    headless.parse_headless_arguments([*base, *arguments])

    def test_execute_nested_source_document_uses_supplied_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            leaf = Path(tmp_dir) / "product" / WORKING_COPY_DIR_NAME / "execution-a"
            source = leaf / "source" / "model.FCStd"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"")
            manifest = leaf / "export_manifest_v1.json"
            manifest.write_text(
                self._make_valid_manifest_content(source_document="source/model.FCStd"),
                encoding="utf-8",
            )
            result = leaf / "result.json"
            with mock.patch.dict(sys.modules, {"Import": mock.Mock()}):
                exit_code, stdout, stderr = self._run_main([
                    "execute", "--working-copy", str(leaf), "--manifest", str(manifest),
                    "--result", str(result),
                ], freecad_module=_FakeExecuteFreeCAD())
            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assert_success_result_payload(result, [])

    def test_execute_rejects_artifact_path_in_sibling_execution_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent = Path(tmp_dir) / "product" / WORKING_COPY_DIR_NAME
            leaf = parent / "execution-a"
            sibling = parent / "execution-b"
            leaf.mkdir(parents=True)
            sibling.mkdir()
            (leaf / "model.FCStd").write_bytes(b"")
            manifest = leaf / "export_manifest_v1.json"
            manifest.write_text(
                self._make_manifest_content(
                    outputs=[{"id": "part", "format": "step", "path": "../execution-b/part.step"}]
                ),
                encoding="utf-8",
            )
            result = leaf / "result.json"
            document = _FakeExecuteDocument()
            document._objects["part"] = object()
            with mock.patch.dict(sys.modules, {"Import": mock.Mock()}):
                exit_code, stdout, stderr = self._run_main([
                    "execute", "--working-copy", str(leaf), "--manifest", str(manifest),
                    "--result", str(result),
                ], freecad_module=_FakeExecuteFreeCAD(document=document))
            self.assert_execute_runtime_failure(
                exit_code, stdout, stderr,
                substring="STEP output path escapes working copy (id='part')",
            )
            self.assert_failed_result_payload(result, stage="artifact_export")
            self.assertFalse((sibling / "part.step").exists())

    # --- invalid manifest path ---

    def test_execute_manifest_nonexistent_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(working / "missing.json"),
                "--result", str(working / "result.json"),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_manifest_is_directory_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            subdir = working / "subdir"
            subdir.mkdir()

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(subdir),
                "--result", str(working / "result.json"),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_manifest_outside_working_copy_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            outside = Path(tmp_dir) / "outside.json"
            outside.write_text("{}", encoding="utf-8")

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(outside),
                "--result", str(working / "result.json"),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_manifest_traversal_outside_working_copy_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            outside = Path(tmp_dir) / "outside.json"
            outside.write_text("{}", encoding="utf-8")

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(working / ".." / "outside.json"),
                "--result", str(working / "result.json"),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    # --- invalid result path ---

    def test_execute_result_outside_working_copy_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text("{}", encoding="utf-8")

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
                "--result", str(Path(tmp_dir) / "outside_result.json"),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_result_traversal_outside_working_copy_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text("{}", encoding="utf-8")

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
                "--result", str(working / ".." / "outside_result.json"),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_result_symlink_escape_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text("{}", encoding="utf-8")
            link_path = working / "link_to_outside"
            self.create_symlink_or_skip(Path("..") / "outside_result.json", link_path)

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
                "--result", str(link_path),
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_invalid_result_does_not_create_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text("{}", encoding="utf-8")
            outside = Path(tmp_dir) / "outside_result.json"

            self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
                "--result", str(outside),
            ])

            self.assertFalse(outside.exists())

    # --- unknown command / unknown options ---

    def test_unknown_command_is_invalid(self) -> None:
        exit_code, stdout, stderr = self._run_main(["unknown"])
        self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_execute_unknown_option_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._make_working_copy(tmp_dir)
            manifest = working / "export_manifest_v1.json"
            manifest.write_text("{}", encoding="utf-8")

            exit_code, stdout, stderr = self._run_main([
                "execute",
                "--working-copy", str(working),
                "--manifest", str(manifest),
                "--result", str(working / "result.json"),
                "--unknown",
            ])
            self.assert_invalid_arguments(exit_code, stdout, stderr)

    def test_smoke_unknown_option_is_invalid(self) -> None:
        exit_code, stdout, stderr = self._run_main(["smoke", "--unknown"])
        self.assert_invalid_arguments(exit_code, stdout, stderr)

    # --- observation CLI remains unsupported ---

    def test_observe_command_is_rejected_before_runtime_delegation(self) -> None:
        from parametron_freecad.observation import observed_writer, verification_loader
        from parametron_freecad.runtime import entrypoints

        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.object(
            headless, "run_execution_entrypoint"
        ) as run_execution, mock.patch.object(
            entrypoints,
            "run_observation_entrypoint",
            side_effect=AssertionError("observe CLI must not delegate to observation"),
        ) as run_observation, mock.patch.object(
            entrypoints,
            "run_document_observation_entrypoint",
            side_effect=AssertionError(
                "observe CLI must not open observation documents"
            ),
        ) as run_document_observation, mock.patch.object(
            entrypoints,
            "generate_observed_output",
            side_effect=AssertionError("observe CLI must not generate observed output"),
        ) as generate_observed, mock.patch.object(
            headless,
            "import_module",
            side_effect=AssertionError("observe CLI must not resolve FreeCAD"),
        ) as import_module, mock.patch.object(
            verification_loader,
            "load_parametron_verification_v1",
            side_effect=AssertionError("observe CLI must not load verification files"),
        ) as load_verification, mock.patch.object(
            observed_writer,
            "write_observed_json",
            side_effect=AssertionError("observe CLI must not write observed output"),
        ) as write_observed:
            exit_code = headless.main(
                argv=["observe"],
                stdout=stdout,
                stderr=stderr,
                freecad_module=FakeFreeCAD(),
            )

        self.assert_invalid_arguments(exit_code, stdout, stderr)
        self.assertEqual(
            stderr.getvalue(),
            f"{headless.INVALID_ARGUMENTS_MESSAGE_PREFIX}unknown command: observe\n",
        )
        run_execution.assert_not_called()
        run_observation.assert_not_called()
        run_document_observation.assert_not_called()
        generate_observed.assert_not_called()
        import_module.assert_not_called()
        load_verification.assert_not_called()
        write_observed.assert_not_called()

    def test_observe_command_creates_no_output_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, _source = self._make_working_copy_with_source(tmp_dir)
            result_path = working / "result.json"
            observed_path = working / "prm.observed.json"
            artifact_path = working / "exports" / "part.step"
            initial_files = {path.relative_to(working) for path in working.rglob("*")}

            exit_code, stdout, stderr = self._run_main(["observe"])

            self.assert_invalid_arguments(exit_code, stdout, stderr)
            self.assertIn("unknown command: observe", stderr.getvalue())
            self.assertFalse(result_path.exists())
            self.assertFalse(observed_path.exists())
            self.assertFalse(artifact_path.exists())
            final_files = {path.relative_to(working) for path in working.rglob("*")}
            self.assertEqual(final_files, initial_files)

    def test_execute_observe_flag_is_rejected_before_runtime_delegation(self) -> None:
        from parametron_freecad.observation import observed_writer, verification_loader
        from parametron_freecad.runtime import entrypoints

        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.object(
            headless, "run_execution_entrypoint"
        ) as run_execution, mock.patch.object(
            entrypoints,
            "run_observation_entrypoint",
            side_effect=AssertionError("execute --observe must not observe"),
        ) as run_observation, mock.patch.object(
            entrypoints,
            "run_document_observation_entrypoint",
            side_effect=AssertionError(
                "execute --observe must not open observation documents"
            ),
        ) as run_document_observation, mock.patch.object(
            entrypoints,
            "generate_observed_output",
            side_effect=AssertionError(
                "execute --observe must not generate observed output"
            ),
        ) as generate_observed, mock.patch.object(
            headless,
            "import_module",
            side_effect=AssertionError("execute --observe must not resolve FreeCAD"),
        ) as import_module, mock.patch.object(
            verification_loader,
            "load_parametron_verification_v1",
            side_effect=AssertionError(
                "execute --observe must not load verification files"
            ),
        ) as load_verification, mock.patch.object(
            observed_writer,
            "write_observed_json",
            side_effect=AssertionError(
                "execute --observe must not write observed output"
            ),
        ) as write_observed:
            exit_code = headless.main(
                argv=[
                    "execute",
                    "--working-copy",
                    "/fake/working-copy",
                    "--manifest",
                    "/fake/working-copy/export_manifest_v1.json",
                    "--result",
                    "/fake/working-copy/result.json",
                    "--observe",
                ],
                stdout=stdout,
                stderr=stderr,
                freecad_module=FakeFreeCAD(),
            )

        self.assert_invalid_arguments(exit_code, stdout, stderr)
        self.assertEqual(
            stderr.getvalue(),
            f"{headless.INVALID_ARGUMENTS_MESSAGE_PREFIX}unrecognized arguments: --observe\n",
        )
        run_execution.assert_not_called()
        run_observation.assert_not_called()
        run_document_observation.assert_not_called()
        generate_observed.assert_not_called()
        import_module.assert_not_called()
        load_verification.assert_not_called()
        write_observed.assert_not_called()

    def test_execute_observe_flag_creates_no_output_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, _source = self._make_working_copy_with_source(tmp_dir)
            manifest_path = working / "export_manifest_v1.json"
            result_path = working / "result.json"
            observed_path = working / "prm.observed.json"
            artifact_path = working / "exports" / "part.step"
            initial_files = {path.relative_to(working) for path in working.rglob("*")}

            exit_code, stdout, stderr = self._run_main(
                [
                    "execute",
                    "--working-copy",
                    str(working),
                    "--manifest",
                    str(manifest_path),
                    "--result",
                    str(result_path),
                    "--observe",
                ],
                freecad_module=FakeFreeCAD(),
            )

            self.assert_invalid_arguments(exit_code, stdout, stderr)
            self.assertIn("unrecognized arguments: --observe", stderr.getvalue())
            self.assertFalse(result_path.exists())
            self.assertFalse(observed_path.exists())
            self.assertFalse(artifact_path.exists())
            final_files = {path.relative_to(working) for path in working.rglob("*")}
            self.assertEqual(final_files, initial_files)


if __name__ == "__main__":
    unittest.main()
