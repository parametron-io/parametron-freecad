"""
Tests proving malformed manifest inputs fail deterministically at the
loader/validation/headless boundary without CAD execution or output creation.

Covers: syntactically malformed JSON, duplicate JSON keys, NaN/Infinity/-Infinity
constants, non-object root values, and structurally invalid manifests.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.common.paths import WORKING_COPY_DIR_NAME
from parametron_freecad.runtime import headless


class _FakeDoc:
    """Minimal fake FreeCAD document for early-failure tests."""

    def __init__(self) -> None:
        self.Name = "FakeDoc"
        self.events: list[str] = []
        self._objects: dict = {}

    def recompute(self) -> None:
        self.events.append("recompute")

    def getObject(self, name: str) -> object:
        return self._objects.get(name)

    @property
    def Objects(self) -> list:
        return []


class _FakeFreeCAD:
    """Minimal fake FreeCAD module tracking document open/close calls."""

    def __init__(self) -> None:
        self.open_calls: list[str] = []
        self.close_calls: list[str] = []
        self._doc = _FakeDoc()

    def openDocument(self, path: str) -> _FakeDoc:
        self.open_calls.append(path)
        return self._doc

    def closeDocument(self, name: str) -> None:
        self._doc.events.append(f"close:{name}")
        self.close_calls.append(name)


class _MalformedManifestBase(unittest.TestCase):
    """Base class with setUp/tearDown and assertion helpers."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.working = self.tmp / WORKING_COPY_DIR_NAME
        self.working.mkdir()
        self.manifest_path = self.working / "export_manifest_v1.json"
        self.result_path = self.working / "result.json"
        self.fake_freecad = _FakeFreeCAD()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _write_manifest(self, content: str) -> None:
        self.manifest_path.write_text(content, encoding="utf-8")

    def _run(self) -> tuple[int, io.StringIO, io.StringIO]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = headless.main(
            argv=[
                "execute",
                "--working-copy", str(self.working),
                "--manifest", str(self.manifest_path),
                "--result", str(self.result_path),
            ],
            stdout=stdout,
            stderr=stderr,
            freecad_module=self.fake_freecad,
        )
        return exit_code, stdout, stderr

    def _assert_controlled_failure(
        self, exit_code: int, stdout: io.StringIO, stderr: io.StringIO
    ) -> None:
        """Assert the full headless controlled-failure contract."""
        self.assertEqual(exit_code, headless.EXECUTION_FAILURE_EXIT_CODE)
        self.assertEqual(stdout.getvalue(), "")
        err = stderr.getvalue()
        self.assertTrue(
            err.startswith(headless.EXECUTION_FAILURE_MESSAGE_PREFIX),
            msg=f"stderr {err!r} does not start with expected failure prefix",
        )
        self.assertTrue(
            err.endswith("\n"), msg=f"stderr {err!r} does not end with newline"
        )
        self.assertEqual(
            err.count("\n"), 1, msg=f"stderr {err!r} is not single-line"
        )
        self.assertNotIn(
            "Traceback", err, msg=f"stderr {err!r} contains Traceback"
        )

    def _assert_failed_result_json(self, *, stage: str) -> None:
        self.assertTrue(self.result_path.exists())
        payload = json.loads(self.result_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(set(payload.keys()), {"schemaVersion", "status", "failure"})
        failure = payload["failure"]
        self.assertEqual(failure["boundary"], "execution_entrypoint")
        self.assertEqual(failure["category"], "execution")
        self.assertEqual(failure["code"], "runtime_failure")
        self.assertEqual(failure["stage"], stage)
        self.assertIsInstance(failure["message"], str)
        self.assertEqual(failure["message"], " ".join(failure["message"].split()))
        self.assertNotIn("Traceback", failure["message"])


# ─── Syntactically malformed JSON ────────────────────────────────────────────


class TestMalformedJsonHeadless(_MalformedManifestBase):
    """Syntactically malformed JSON manifests fail at the load boundary."""

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest('{"key": BAD_JSON_VALUE}')

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_loading")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])


class TestTruncatedJsonHeadless(_MalformedManifestBase):
    """Truncated JSON manifests fail at the load boundary."""

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest('{"schemaVersion": "1.0", "sourceDoc')

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_loading")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])


# ─── Duplicate JSON keys ──────────────────────────────────────────────────────


class TestDuplicateRootKeyHeadless(_MalformedManifestBase):
    """Duplicate root JSON object keys fail at the load boundary."""

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest('{"schemaVersion": "1.0", "schemaVersion": "2.0"}')

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_loading")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])


class TestDuplicateNestedKeyHeadless(_MalformedManifestBase):
    """Duplicate keys inside nested objects fail at the load boundary."""

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest('{"outer": {"key": 1, "key": 2}}')

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_loading")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])


class TestDuplicateArrayObjectKeyHeadless(_MalformedManifestBase):
    """Duplicate keys inside array-contained objects fail at the load boundary."""

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest('{"outputs": [{"id": "out", "id": "out2"}]}')

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_loading")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])


# ─── NaN / Infinity / -Infinity constants ────────────────────────────────────


class TestNanHeadless(_MalformedManifestBase):
    """NaN constants fail at the load boundary as ManifestDecodeError."""

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest('{"value": NaN}')

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_loading")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])


class TestInfinityHeadless(_MalformedManifestBase):
    """Infinity constants fail at the load boundary as ManifestDecodeError."""

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest('{"value": Infinity}')

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_loading")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])


class TestNegativeInfinityHeadless(_MalformedManifestBase):
    """-Infinity constants fail at the load boundary as ManifestDecodeError."""

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest('{"value": -Infinity}')

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_loading")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])


# ─── Non-object root values ───────────────────────────────────────────────────


class TestNonObjectRootHeadless(_MalformedManifestBase):
    """Non-object JSON root values fail at the load boundary."""

    def _check(self, json_text: str) -> None:
        self._write_manifest(json_text)
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)
        self._assert_failed_result_json(stage="manifest_loading")
        self.assertEqual(
            self.fake_freecad.open_calls,
            [],
            msg=f"no document should be opened for root {json_text!r}",
        )

    def test_array_root_fails(self) -> None:
        self._check('[1, 2, 3]')

    def test_string_root_fails(self) -> None:
        self._check('"just a string"')

    def test_number_root_fails(self) -> None:
        self._check('42')

    def test_boolean_root_fails(self) -> None:
        self._check('true')

    def test_null_root_fails(self) -> None:
        self._check('null')


# ─── Structurally invalid (but syntactically valid) manifests ─────────────────


class TestMissingRequiredFieldsHeadless(_MalformedManifestBase):
    """Manifests missing required fields fail at the validation boundary."""

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest(json.dumps({
            "schemaVersion": "1.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [],
            # "outputs" intentionally omitted
        }))

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_stderr_mentions_validation(self) -> None:
        _, _, stderr = self._run()
        self.assertIn("manifest validation failed", stderr.getvalue())

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_validation")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])


class TestAllRequiredFieldsMissingHeadless(_MalformedManifestBase):
    """Empty object manifest (all required fields absent) fails at validation."""

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest('{}')

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_validation")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])


class TestUnsupportedOutputFormatHeadless(_MalformedManifestBase):
    """Manifests with unsupported output format fail at the validation boundary."""

    _ARTIFACT_RELATIVE = "exports/model.stl"

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest(json.dumps({
            "schemaVersion": "1.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [],
            "outputs": [
                {"id": "out1", "format": "stl", "path": self._ARTIFACT_RELATIVE},
            ],
        }))

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_stderr_mentions_validation(self) -> None:
        _, _, stderr = self._run()
        self.assertIn("manifest validation failed", stderr.getvalue())

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_validation")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])

    def test_declared_artifact_not_created(self) -> None:
        self._run()
        self.assertFalse((self.working / self._ARTIFACT_RELATIVE).exists())

    def test_no_exporter_invoked(self) -> None:
        with mock.patch(
            "parametron_freecad.runtime.headless.export_step_artifacts"
        ) as mock_step, mock.patch(
            "parametron_freecad.runtime.headless.export_csv_artifacts"
        ) as mock_csv, mock.patch(
            "parametron_freecad.runtime.headless.export_pdf_artifacts"
        ) as mock_pdf:
            self._run()
        mock_step.assert_not_called()
        mock_csv.assert_not_called()
        mock_pdf.assert_not_called()


class TestInvalidSchemaVersionHeadless(_MalformedManifestBase):
    """Manifests with an invalid schemaVersion fail at the validation boundary."""

    def setUp(self) -> None:
        super().setUp()
        self._write_manifest(json.dumps({
            "schemaVersion": "99.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": [],
            "outputs": [],
        }))

    def test_controlled_failure_contract(self) -> None:
        exit_code, stdout, stderr = self._run()
        self._assert_controlled_failure(exit_code, stdout, stderr)

    def test_failed_result_json_created(self) -> None:
        self._run()
        self._assert_failed_result_json(stage="manifest_validation")

    def test_no_document_opened(self) -> None:
        self._run()
        self.assertEqual(self.fake_freecad.open_calls, [])


if __name__ == "__main__":
    unittest.main()
