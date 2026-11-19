"""Runtime integration tests for declared resource inventory consumption."""

from __future__ import annotations

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
from parametron_freecad.runtime.document_lifecycle import OpenedDocument
from parametron_freecad.runtime.entrypoints import _ExecutionEntrypointDependencies
from parametron_freecad.runtime.resource_inventory import (
    INTEGRITY_REQUEST_ENVIRONMENT_VARIABLE,
)

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64


class ResourceInventoryRuntimeTests(unittest.TestCase):
    def _paths(self, tmp_dir: str) -> tuple[Path, Path, Path]:
        working = Path(tmp_dir) / "run" / "_working" / "attempt"
        (working / "source").mkdir(parents=True)
        source = working / "source" / "Assembly.FCStd"
        source.write_bytes(b"source")
        manifest = working / "prm.export-manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "sourceDocument": "source/Assembly.FCStd",
                    "parameterAssignments": [],
                    "outputs": [],
                }
            ),
            encoding="utf-8",
        )
        return working, manifest, working / "prm.result.json"

    def _request(
        self,
        path: Path,
        *,
        selected_digest: str = _DIGEST_A,
    ) -> Path:
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "resources": [
                        {
                            "logicalId": "assembly",
                            "kind": "model",
                            "materializedCoordinate": "source/Assembly.FCStd",
                            "baselineSha256": selected_digest,
                            "expectsPersistedResult": True,
                        },
                        {
                            "logicalId": "component",
                            "kind": "model",
                            "materializedCoordinate": "resources/component/Body.FCStd",
                            "baselineSha256": _DIGEST_B,
                            "expectsPersistedResult": False,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_invalid_inventory_fails_before_document_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result = self._paths(tmp_dir)
            request = working / "prm.integrity-request.json"
            request.write_text(
                '{"schemaVersion":"2.0","resources":[]}', encoding="utf-8"
            )
            opened = mock.Mock()

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=result,
                    integrity_request_path=request,
                    freecad_module=object(),
                    _dependencies=_ExecutionEntrypointDependencies(
                        opened_freecad_document=opened,
                    ),
                )

            opened.assert_not_called()
            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["status"], "failed")
            self.assertEqual(failure["failure"]["stage"], "resource_inventory")

    def test_valid_inventory_is_consumed_without_writing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result = self._paths(tmp_dir)
            request = self._request(working / "prm.integrity-request.json")
            opened_calls: list[Path] = []

            @contextmanager
            def opened_document(
                freecad_module: Any,
                path: Path,
            ) -> Iterator[OpenedDocument]:
                opened_calls.append(path)
                yield OpenedDocument(
                    path=path,
                    document=object(),
                    document_name="Assembly",
                )

            with mock.patch.object(
                entrypoints,
                "write_success_result",
            ) as write_success_result:
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=manifest,
                    result_path=result,
                    integrity_request_path=request,
                    freecad_module=object(),
                    _dependencies=_ExecutionEntrypointDependencies(
                        apply_parameter_assignments=mock.Mock(),
                        recompute_document=mock.Mock(),
                        save_document=mock.Mock(),
                        export_step_artifacts=mock.Mock(),
                        export_csv_artifacts=mock.Mock(),
                        export_pdf_artifacts=mock.Mock(),
                        opened_freecad_document=opened_document,
                        write_success_result=write_success_result,
                    ),
                )

            self.assertEqual(opened_calls, [working / "source" / "Assembly.FCStd"])
            write_success_result.assert_called_once()
            self.assertFalse((working / "prm.integrity-evidence.json").exists())
            self.assertFalse(
                (working / "outputs" / "prm.integrity-evidence.json").exists()
            )

    def test_headless_forwards_environment_integrity_request_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result = self._paths(tmp_dir)
            request = self._request(working / "prm.integrity-request.json")

            with (
                mock.patch.object(
                    headless,
                    "run_execution_entrypoint",
                ) as run_execution_entrypoint,
                mock.patch.dict(
                    os.environ,
                    {INTEGRITY_REQUEST_ENVIRONMENT_VARIABLE: str(request)},
                ),
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
                    stderr=io.StringIO(),
                    freecad_module=object(),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                run_execution_entrypoint.call_args.kwargs["integrity_request_path"],
                str(request),
            )

    def test_headless_omits_integrity_request_when_environment_is_unset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result = self._paths(tmp_dir)

            with (
                mock.patch.object(
                    headless,
                    "run_execution_entrypoint",
                ) as run_execution_entrypoint,
                mock.patch.dict(
                    os.environ,
                    {},
                    clear=True,
                ),
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
                    stderr=io.StringIO(),
                    freecad_module=object(),
                )

            self.assertEqual(exit_code, 0)
            self.assertIsNone(
                run_execution_entrypoint.call_args.kwargs["integrity_request_path"]
            )


if __name__ == "__main__":
    unittest.main()
