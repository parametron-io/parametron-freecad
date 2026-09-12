from __future__ import annotations

import copy
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.execution.result_writer import (
    RESULT_SCHEMA_VERSION,
    RESULT_STATUS_SUCCEEDED,
    ResultWriteError,
    write_success_result,
)


class ResultWriterImportSafetyTests(unittest.TestCase):
    def test_module_import_is_safe_under_ordinary_python(self) -> None:
        module_name = "parametron_freecad.execution.result_writer"
        original_import = __import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "FreeCAD":
                raise AssertionError("FreeCAD should not be imported at module import time")
            return original_import(name, globals, locals, fromlist, level)

        previous = sys.modules.pop(module_name, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(module_name, previous)
            if previous is not None
            else sys.modules.pop(module_name, None)
        )

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module(module_name)

        self.assertEqual(module.RESULT_SCHEMA_VERSION, "1.0")
        self.assertEqual(module.RESULT_STATUS_SUCCEEDED, "succeeded")


class ResultWriterTests(unittest.TestCase):
    def test_write_success_result_writes_canonical_manifest_ordered_payload(self) -> None:
        outputs = [
            {"id": "drawing", "format": "pdf", "path": "exports/drawing.pdf", "ignored": "x"},
            {"id": "part", "format": "step", "path": "exports/part.step"},
            {"id": "report", "format": "csv", "path": "exports/report.csv"},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"

            write_success_result(path, outputs)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                (
                    '{"artifacts":['
                    '{"format":"pdf","id":"drawing","path":"exports/drawing.pdf"},'
                    '{"format":"step","id":"part","path":"exports/part.step"},'
                    '{"format":"csv","id":"report","path":"exports/report.csv"}'
                    '],"schemaVersion":"1.0","status":"succeeded"}\n'
                ),
            )

    def test_write_success_result_artifact_entries_contain_exactly_format_id_and_path(self) -> None:
        outputs = [
            {
                "id": "part",
                "format": "step",
                "path": "artifacts/part.step",
                "extra": {"should": "be omitted"},
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"

            write_success_result(path, outputs)

            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            payload,
            {
                "artifacts": [
                    {
                        "format": "step",
                        "id": "part",
                        "path": "artifacts/part.step",
                    }
                ],
                "schemaVersion": RESULT_SCHEMA_VERSION,
                "status": RESULT_STATUS_SUCCEEDED,
            },
        )
        self.assertEqual(set(payload["artifacts"][0].keys()), {"format", "id", "path"})

    def test_write_success_result_preserves_manifest_declared_relative_and_absolute_paths(self) -> None:
        outputs = [
            {"id": "relative", "format": "csv", "path": "exports/report.csv"},
            {"id": "absolute", "format": "pdf", "path": "/tmp/fake/drawing.pdf"},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"

            write_success_result(path, outputs)

            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            payload["artifacts"],
            [
                {"format": "csv", "id": "relative", "path": "exports/report.csv"},
                {"format": "pdf", "id": "absolute", "path": "/tmp/fake/drawing.pdf"},
            ],
        )

    def test_write_success_result_does_not_infer_result_json_artifact(self) -> None:
        outputs = [{"id": "part", "format": "step", "path": "exports/part.step"}]

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"

            write_success_result(path, outputs)

            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(len(payload["artifacts"]), 1)
        self.assertNotIn(
            {"format": "json", "id": "result", "path": "result.json"},
            payload["artifacts"],
        )

    def test_repeated_writes_with_identical_inputs_produce_byte_identical_output(self) -> None:
        outputs = [
            {"id": "part", "format": "step", "path": "exports/part.step"},
            {"id": "report", "format": "csv", "path": "exports/report.csv"},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"

            write_success_result(path, outputs)
            first = path.read_bytes()

            write_success_result(path, outputs)
            second = path.read_bytes()

        self.assertEqual(first, second)
        self.assertTrue(first.endswith(b"\n"))
        self.assertFalse(first.endswith(b"\n\n"))
        self.assertEqual(first.rstrip(b"\n"), first[:-1])

    def test_write_success_result_does_not_mutate_outputs_or_output_dictionaries(self) -> None:
        outputs = [
            {"id": "part", "format": "step", "path": "exports/part.step", "extra": ["x", "y"]},
            {"id": "report", "format": "csv", "path": "exports/report.csv"},
        ]
        original = copy.deepcopy(outputs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            write_success_result(Path(tmp_dir) / "result.json", outputs)

        self.assertEqual(outputs, original)

    def test_write_success_result_wraps_canonical_write_failures_with_deterministic_text(self) -> None:
        path = Path("/tmp/fake/result.json")

        with mock.patch(
            "parametron_freecad.execution.result_writer.write_canonical_json",
            side_effect=OSError("boom"),
        ):
            with self.assertRaisesRegex(
                ResultWriteError,
                r"^failed to write result file /tmp/fake/result\.json: boom$",
            ) as ctx:
                write_success_result(path, [])

        self.assertEqual(str(ctx.exception), "failed to write result file /tmp/fake/result.json: boom")

    def test_write_success_result_wraps_real_directory_target_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(
                ResultWriteError,
                r"^failed to write result file .*: ",
            ) as ctx:
                write_success_result(Path(tmp_dir), [])

        self.assertIn("failed to write result file", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
