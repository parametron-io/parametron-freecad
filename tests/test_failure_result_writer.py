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

MODULE_NAME = "parametron_freecad.runtime.failure_result_writer"


def _failure():
    from parametron_freecad.runtime.failure_output_contract import StructuredFailure

    return StructuredFailure(
        boundary="execution_entrypoint",
        category="execution",
        code="runtime_failure",
        message="parameter assignment failed",
        stage="parameter_assignment",
    )


class FailureResultWriterImportSafetyTests(unittest.TestCase):
    def test_import_succeeds_without_freecad(self) -> None:
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad", "Import", "TechDrawGui"}
        original_import = builtins.__import__

        previous = sys.modules.pop(MODULE_NAME, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root_name = name.split(".", maxsplit=1)[0]
            if root_name in guarded_names:
                raise AssertionError(f"{root_name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module(MODULE_NAME)

        self.assertIsInstance(module, types.ModuleType)
        self.assertTrue(hasattr(module, "write_failure_result"))
        for guarded_name in guarded_names:
            self.assertNotIn(guarded_name, sys.modules)


class FailureResultWriterTests(unittest.TestCase):
    def test_write_failure_result_writes_canonical_failed_result(self) -> None:
        from parametron_freecad.runtime.failure_result_writer import write_failure_result

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"
            write_failure_result(path, _failure())
            raw = path.read_bytes()

        self.assertEqual(
            raw,
            (
                b'{"failure":{"boundary":"execution_entrypoint",'
                b'"category":"execution","code":"runtime_failure",'
                b'"message":"parameter assignment failed",'
                b'"stage":"parameter_assignment"},'
                b'"schemaVersion":"1.0","status":"failed"}\n'
            ),
        )
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(
            set(payload["failure"]),
            {"boundary", "category", "code", "message", "stage"},
        )

    def test_equivalent_inputs_produce_byte_stable_output(self) -> None:
        from parametron_freecad.runtime.failure_result_writer import write_failure_result

        with tempfile.TemporaryDirectory() as tmp_dir:
            first = Path(tmp_dir) / "first.json"
            second = Path(tmp_dir) / "second.json"
            write_failure_result(first, _failure())
            write_failure_result(second, _failure())

            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_repeated_writes_overwrite_with_same_bytes(self) -> None:
        from parametron_freecad.runtime.failure_result_writer import write_failure_result

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"
            write_failure_result(path, _failure())
            first = path.read_bytes()
            path.write_bytes(b"stale bytes")
            write_failure_result(path, _failure())

            self.assertEqual(path.read_bytes(), first)

    def test_writer_does_not_mutate_structured_failure(self) -> None:
        from parametron_freecad.runtime.failure_result_writer import write_failure_result

        failure = _failure()
        original = (
            failure.boundary,
            failure.category,
            failure.code,
            failure.message,
            failure.stage,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            write_failure_result(Path(tmp_dir) / "result.json", failure)

        self.assertEqual(
            (
                failure.boundary,
                failure.category,
                failure.code,
                failure.message,
                failure.stage,
            ),
            original,
        )
        with self.assertRaises(FrozenInstanceError):
            failure.message = "changed"

    def test_unwritable_destination_raises_narrow_write_error(self) -> None:
        from parametron_freecad.runtime.failure_result_writer import (
            FailureResultWriteError,
            write_failure_result,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            directory_path = Path(tmp_dir) / "result.json"
            directory_path.mkdir()

            with self.assertRaises(FailureResultWriteError) as ctx:
                write_failure_result(directory_path, _failure())

        self.assertIn("failed to write failure result file", str(ctx.exception))

    def test_invalid_failure_payload_raises_narrow_write_error(self) -> None:
        from parametron_freecad.runtime.failure_output_contract import StructuredFailure
        from parametron_freecad.runtime.failure_result_writer import (
            FailureResultWriteError,
            write_failure_result,
        )

        invalid = StructuredFailure(
            boundary="execution_entrypoint",
            category="execution",
            code="runtime_failure",
            message="",
            stage="parameter_assignment",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(FailureResultWriteError) as ctx:
                write_failure_result(Path(tmp_dir) / "result.json", invalid)

        self.assertIn("message", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
