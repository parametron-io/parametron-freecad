"""Runtime integration tests for integrity evidence emission."""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest import mock

from parametron_freecad.runtime import entrypoints, headless
from parametron_freecad.execution.document_save import DocumentSaveError
from parametron_freecad.runtime.document_lifecycle import OpenedDocument
from parametron_freecad.runtime.entrypoints import _ExecutionEntrypointDependencies
from parametron_freecad.runtime.integrity_observation import (
    INTEGRITY_EVIDENCE_FILENAME,
    INTEGRITY_STATUS_MISSING,
    INTEGRITY_STATUS_OBSERVED,
    IntegrityEvidenceError,
)
from parametron_freecad.runtime.resource_inventory import (
    INTEGRITY_REQUEST_ENVIRONMENT_VARIABLE,
)

_PRIMARY_COORDINATE = "source/Assembly.FCStd"
_SECONDARY_COORDINATE = "resources/component/Body.FCStd"
_BASELINE_BYTES = b"baseline"
_SECONDARY_BYTES = b"secondary"
_RESULT_BYTES = b"configured-result"


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class _FakeDocument:
    def __init__(self, file_name: str | Path) -> None:
        self.FileName = file_name


class IntegrityRuntimeTests(unittest.TestCase):
    def _paths(self, tmp_dir: str) -> tuple[Path, Path, Path, Path]:
        working = Path(tmp_dir) / "run" / "_working" / "attempt"
        (working / "source").mkdir(parents=True)
        (working / "resources" / "component").mkdir(parents=True)
        (working / "outputs").mkdir()
        source = working / _PRIMARY_COORDINATE
        source.write_bytes(_BASELINE_BYTES)
        (working / _SECONDARY_COORDINATE).write_bytes(_SECONDARY_BYTES)
        manifest = working / "prm.export-manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "sourceDocument": _PRIMARY_COORDINATE,
                    "parameterAssignments": [],
                    "outputs": [],
                }
            ),
            encoding="utf-8",
        )
        return working, manifest, working / "prm.result.json", working / "outputs"

    def _request(
        self,
        path: Path,
        *,
        primary_digest: str = _digest(_BASELINE_BYTES),
        secondary_digest: str = _digest(_SECONDARY_BYTES),
    ) -> Path:
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "resources": [
                        {
                            "logicalId": "assembly",
                            "kind": "model",
                            "materializedCoordinate": _PRIMARY_COORDINATE,
                            "baselineSha256": primary_digest,
                            "expectsPersistedResult": True,
                        },
                        {
                            "logicalId": "component",
                            "kind": "model",
                            "materializedCoordinate": _SECONDARY_COORDINATE,
                            "baselineSha256": secondary_digest,
                            "expectsPersistedResult": False,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def _dependencies(
        self,
        *,
        source_path: Path,
        opened_path: Path | None = None,
        save_document: Any | None = None,
    ) -> _ExecutionEntrypointDependencies:
        @contextmanager
        def opened_document(
            freecad_module: Any,
            path: Path,
        ) -> Iterator[OpenedDocument]:
            del freecad_module
            resolved = opened_path if opened_path is not None else path
            yield OpenedDocument(
                path=resolved,
                document=_FakeDocument(resolved),
                document_name="Assembly",
            )

        def save(document: Any) -> None:
            del document
            source_path.write_bytes(_RESULT_BYTES)

        return _ExecutionEntrypointDependencies(
            apply_parameter_assignments=mock.Mock(),
            recompute_document=mock.Mock(),
            save_document=save if save_document is None else save_document,
            export_step_artifacts=mock.Mock(),
            export_csv_artifacts=mock.Mock(),
            export_pdf_artifacts=mock.Mock(),
            opened_freecad_document=opened_document,
        )

    def _run(
        self,
        *,
        working: Path,
        manifest: Path,
        result: Path,
        outputs: Path | None,
        request: Path,
        dependencies: _ExecutionEntrypointDependencies,
    ) -> None:
        entrypoints.run_execution_entrypoint(
            working_copy=working,
            manifest_path=manifest,
            result_path=result,
            output_directory=outputs,
            integrity_request_path=request,
            freecad_module=object(),
            _dependencies=dependencies,
        )

    def _evidence(self, outputs: Path) -> dict[str, Any]:
        return json.loads((outputs / INTEGRITY_EVIDENCE_FILENAME).read_text())

    def test_success_emits_baseline_and_persisted_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            request = self._request(working / "prm.integrity-request.json")
            stale = outputs / INTEGRITY_EVIDENCE_FILENAME
            stale.write_bytes(b"stale")

            self._run(
                working=working,
                manifest=manifest,
                result=result,
                outputs=outputs,
                request=request,
                dependencies=self._dependencies(
                    source_path=working / _PRIMARY_COORDINATE,
                ),
            )

            evidence = self._evidence(outputs)
            result_payload = json.loads(result.read_text(encoding="utf-8"))

        self.assertEqual(evidence["schemaVersion"], "1.0")
        self.assertEqual(
            [resource["logicalId"] for resource in evidence["resources"]],
            ["assembly", "component"],
        )
        primary, secondary = evidence["resources"]
        self.assertEqual(primary["status"], INTEGRITY_STATUS_OBSERVED)
        self.assertEqual(primary["baselineSha256"], _digest(_BASELINE_BYTES))
        self.assertEqual(
            primary["persistedResult"],
            {
                "coordinate": _PRIMARY_COORDINATE,
                "sha256": _digest(_RESULT_BYTES),
            },
        )
        self.assertEqual(secondary["status"], INTEGRITY_STATUS_OBSERVED)
        self.assertEqual(secondary["baselineSha256"], _digest(_SECONDARY_BYTES))
        self.assertIsNone(secondary["persistedResult"])
        self.assertEqual(result_payload["status"], "succeeded")

    def test_baseline_mismatch_fails_before_open_and_removes_stale_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            request = self._request(
                working / "prm.integrity-request.json",
                primary_digest="0" * 64,
            )
            stale = outputs / INTEGRITY_EVIDENCE_FILENAME
            stale.write_bytes(b"stale")
            opened = mock.Mock()

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                self._run(
                    working=working,
                    manifest=manifest,
                    result=result,
                    outputs=outputs,
                    request=request,
                    dependencies=_ExecutionEntrypointDependencies(
                        opened_freecad_document=opened,
                    ),
                )

            opened.assert_not_called()
            self.assertFalse(stale.exists())
            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "integrity_baseline")
            self.assertEqual(
                (working / _PRIMARY_COORDINATE).read_bytes(),
                _BASELINE_BYTES,
            )

    def test_missing_output_directory_fails_before_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, _outputs = self._paths(tmp_dir)
            request = self._request(working / "prm.integrity-request.json")
            opened = mock.Mock()

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                self._run(
                    working=working,
                    manifest=manifest,
                    result=result,
                    outputs=None,
                    request=request,
                    dependencies=_ExecutionEntrypointDependencies(
                        opened_freecad_document=opened,
                    ),
                )

            opened.assert_not_called()
            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "integrity_evidence")

    def test_save_failure_emits_no_success_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            request = self._request(working / "prm.integrity-request.json")
            stale = outputs / INTEGRITY_EVIDENCE_FILENAME
            stale.write_bytes(b"stale")

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                self._run(
                    working=working,
                    manifest=manifest,
                    result=result,
                    outputs=outputs,
                    request=request,
                    dependencies=self._dependencies(
                        source_path=working / _PRIMARY_COORDINATE,
                        save_document=mock.Mock(
                            side_effect=DocumentSaveError("save failed")
                        ),
                    ),
                )

            self.assertFalse(stale.exists())
            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "document_save")

    def test_missing_secondary_is_reported_without_content_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            (working / _SECONDARY_COORDINATE).unlink()
            request = self._request(working / "prm.integrity-request.json")

            self._run(
                working=working,
                manifest=manifest,
                result=result,
                outputs=outputs,
                request=request,
                dependencies=self._dependencies(
                    source_path=working / _PRIMARY_COORDINATE,
                ),
            )

            evidence = self._evidence(outputs)

        secondary = evidence["resources"][1]
        self.assertEqual(secondary["status"], INTEGRITY_STATUS_MISSING)
        self.assertEqual(secondary["baselineSha256"], "")
        self.assertIsNone(secondary["persistedResult"])

    def test_opened_document_mismatch_fails_at_result_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            request = self._request(working / "prm.integrity-request.json")

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                self._run(
                    working=working,
                    manifest=manifest,
                    result=result,
                    outputs=outputs,
                    request=request,
                    dependencies=self._dependencies(
                        source_path=working / _PRIMARY_COORDINATE,
                        opened_path=working / _SECONDARY_COORDINATE,
                    ),
                )

            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "integrity_result")
            self.assertFalse((outputs / INTEGRITY_EVIDENCE_FILENAME).exists())

    def test_evidence_write_failure_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            request = self._request(working / "prm.integrity-request.json")

            with mock.patch(
                "parametron_freecad.runtime.integrity_observation."
                "write_canonical_json_sidecar_atomically",
                side_effect=IntegrityEvidenceError("write failure"),
            ):
                with self.assertRaises(entrypoints.ExecutionEntrypointError):
                    self._run(
                        working=working,
                        manifest=manifest,
                        result=result,
                        outputs=outputs,
                        request=request,
                        dependencies=self._dependencies(
                            source_path=working / _PRIMARY_COORDINATE,
                        ),
                    )

            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "integrity_evidence")
            self.assertFalse((outputs / INTEGRITY_EVIDENCE_FILENAME).exists())

    def test_headless_requires_output_directory_for_environment_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, _outputs = self._paths(tmp_dir)
            request = self._request(working / "prm.integrity-request.json")

            stderr = io.StringIO()
            with mock.patch.dict(
                os.environ,
                {INTEGRITY_REQUEST_ENVIRONMENT_VARIABLE: str(request)},
            ):
                exit_code = headless.main(
                    argv=[
                        "execute",
                        "--working-copy",
                        str(working),
                        "--manifest",
                        str(manifest),
                        "--result",
                        str(result),
                    ],
                    stdout=io.StringIO(),
                    stderr=stderr,
                    freecad_module=object(),
                )

            self.assertEqual(exit_code, headless.EXECUTION_FAILURE_EXIT_CODE)
            self.assertIn("integrity_evidence", result.read_text(encoding="utf-8"))
            self.assertTrue(
                stderr.getvalue().startswith("parametron-freecad: execute failed:")
            )
            self.assertFalse(
                (working / "outputs" / INTEGRITY_EVIDENCE_FILENAME).exists()
            )
            self.assertTrue(request.exists())


if __name__ == "__main__":
    unittest.main()
