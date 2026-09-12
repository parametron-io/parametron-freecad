from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.common.paths import WORKING_COPY_DIR_NAME
from parametron_freecad.runtime import headless


class _AssignableObject:
    def __init__(self, name: str) -> None:
        self.Name = name
        self.Length = 0.0


class _Spreadsheet:
    def __init__(self, content: dict[str, object]) -> None:
        self.Content = dict(content)


class _Page:
    def __init__(self, name: str) -> None:
        self.Name = name


class _StepObject:
    def __init__(self, name: str) -> None:
        self.Name = name


class _Document:
    def __init__(self, *, recompute_error: Exception | None = None) -> None:
        self.Name = "RepeatedRunDoc"
        self._objects = {
            "Box": _AssignableObject("Box"),
            "Report": _Spreadsheet({"A1": "part", "B1": "length", "A2": "Box", "B2": 100}),
            "Drawing": _Page("Drawing"),
            "part": _StepObject("Body"),
            "first-step": _StepObject("Body"),
            "second-step": _StepObject("Pad"),
        }
        self.recompute_error = recompute_error
        self.recompute_calls = 0
        self.save_calls = 0

    def getObject(self, name: str) -> object | None:
        return self._objects.get(name)

    @property
    def Objects(self):
        raise AssertionError("STEP export must not access document.Objects")

    def recompute(self) -> None:
        self.recompute_calls += 1
        if self.recompute_error is not None:
            raise self.recompute_error

    def save(self) -> None:
        self.save_calls += 1


class _FreeCAD:
    def __init__(self, *, recompute_error: Exception | None = None) -> None:
        self.recompute_error = recompute_error
        self.open_calls: list[str] = []
        self.close_calls: list[str] = []
        self.documents: list[_Document] = []

    def openDocument(self, path: str) -> _Document:
        self.open_calls.append(path)
        document = _Document(recompute_error=self.recompute_error)
        self.documents.append(document)
        return document

    def closeDocument(self, document_name: str) -> None:
        self.close_calls.append(document_name)


class _ImportExporter:
    def export(self, objects: list[object], path: str) -> None:
        names = ",".join(getattr(obj, "Name", "") for obj in objects)
        Path(path).write_bytes(f"STEP\nobjects={names}\n".encode("utf-8"))


class _TechDrawGuiExporter:
    def exportPageAsPdf(self, page: object, path: str) -> None:
        name = getattr(page, "Name", "")
        Path(path).write_bytes(f"PDF\npage={name}\n".encode("utf-8"))


class HeadlessRepeatedRunTests(unittest.TestCase):
    def _make_manifest(
        self,
        *,
        assignments: list[dict] | None = None,
        outputs: list[dict] | None = None,
    ) -> dict:
        return {
            "schemaVersion": "1.0",
            "sourceDocument": "model.FCStd",
            "parameterAssignments": assignments
            if assignments is not None
            else [{"target": "Box.Length", "value": 100.0, "valueKind": "float"}],
            "outputs": outputs
            if outputs is not None
            else [
                {"id": "part", "format": "step", "path": "exports/part.step"},
                {"id": "Report", "format": "csv", "path": "reports/report.csv"},
                {"id": "Drawing", "format": "pdf", "path": "drawings/drawing.pdf"},
            ],
        }

    def _create_working_copy(self, root: Path, manifest: dict) -> tuple[Path, Path, Path]:
        working = root / WORKING_COPY_DIR_NAME
        working.mkdir()
        (working / "model.FCStd").write_bytes(b"fake source document\n")

        for output in manifest["outputs"]:
            (working / output["path"]).parent.mkdir(parents=True, exist_ok=True)

        manifest_path = working / "export_manifest_v1.json"
        manifest_path.write_text(dumps_canonical(manifest), encoding="utf-8")
        return working, manifest_path, working / "result.json"

    def _run_execute(
        self,
        working: Path,
        manifest_path: Path,
        result_path: Path,
        *,
        freecad_module: object | None = None,
    ) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        modules = {
            "Import": SimpleNamespace(export=_ImportExporter().export),
            "TechDrawGui": SimpleNamespace(
                exportPageAsPdf=_TechDrawGuiExporter().exportPageAsPdf
            ),
        }
        with mock.patch.dict("sys.modules", modules):
            exit_code = headless.main(
                argv=[
                    "execute",
                    "--working-copy",
                    str(working),
                    "--manifest",
                    str(manifest_path),
                    "--result",
                    str(result_path),
                ],
                stdout=stdout,
                stderr=stderr,
                freecad_module=freecad_module if freecad_module is not None else _FreeCAD(),
            )
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def _collect_bytes(
        self,
        working: Path,
        result_path: Path,
        outputs: list[dict],
    ) -> dict[str, bytes]:
        collected = {"result.json": result_path.read_bytes()}
        for output in outputs:
            collected[output["path"]] = (working / output["path"]).read_bytes()
        return collected

    def _assert_success_contract(
        self,
        run: tuple[int, str, str],
        result_bytes: bytes,
        outputs: list[dict],
    ) -> None:
        exit_code, stdout, stderr = run
        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertTrue(result_bytes.endswith(b"\n"))
        self.assertFalse(result_bytes.endswith(b"\n\n"))
        self.assertEqual(result_bytes.count(b"\n"), 1)
        self.assertEqual(
            json.loads(result_bytes.decode("utf-8"))["artifacts"],
            [
                {"format": output["format"], "id": output["id"], "path": output["path"]}
                for output in outputs
            ],
        )

    def test_repeated_equivalent_successful_execute_runs_are_byte_stable(self) -> None:
        manifest = self._make_manifest()

        with tempfile.TemporaryDirectory() as first_tmp, tempfile.TemporaryDirectory() as second_tmp:
            first_working, first_manifest, first_result = self._create_working_copy(
                Path(first_tmp),
                manifest,
            )
            second_working, second_manifest, second_result = self._create_working_copy(
                Path(second_tmp),
                manifest,
            )

            first_freecad = _FreeCAD()
            second_freecad = _FreeCAD()
            first_run = self._run_execute(first_working, first_manifest, first_result, freecad_module=first_freecad)
            second_run = self._run_execute(second_working, second_manifest, second_result, freecad_module=second_freecad)
            first_bytes = self._collect_bytes(first_working, first_result, manifest["outputs"])
            second_bytes = self._collect_bytes(
                second_working,
                second_result,
                manifest["outputs"],
            )

        self._assert_success_contract(first_run, first_bytes["result.json"], manifest["outputs"])
        self._assert_success_contract(second_run, second_bytes["result.json"], manifest["outputs"])
        self.assertEqual(first_run, second_run)
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual([doc.save_calls for doc in first_freecad.documents], [1])
        self.assertEqual([doc.save_calls for doc in second_freecad.documents], [1])

    def test_rerunning_execute_on_same_working_copy_overwrites_stably(self) -> None:
        manifest = self._make_manifest()

        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest_path, result_path = self._create_working_copy(
                Path(tmp_dir),
                manifest,
            )

            freecad = _FreeCAD()
            first_run = self._run_execute(working, manifest_path, result_path, freecad_module=freecad)
            first_bytes = self._collect_bytes(working, result_path, manifest["outputs"])

            result_path.write_bytes(b"stale result bytes that must be replaced")
            for output in manifest["outputs"]:
                (working / output["path"]).write_bytes(
                    b"stale artifact bytes that must be replaced"
                )

            second_run = self._run_execute(working, manifest_path, result_path, freecad_module=freecad)
            second_bytes = self._collect_bytes(working, result_path, manifest["outputs"])

        self._assert_success_contract(first_run, first_bytes["result.json"], manifest["outputs"])
        self._assert_success_contract(second_run, second_bytes["result.json"], manifest["outputs"])
        self.assertEqual(first_run, second_run)
        self.assertEqual(first_bytes, second_bytes)
        for contents in second_bytes.values():
            self.assertNotIn(b"stale", contents)
        self.assertEqual([doc.save_calls for doc in freecad.documents], [1, 1])

    def test_manifest_output_declaration_order_is_preserved_across_repeated_runs(self) -> None:
        outputs = [
            {"id": "first-step", "format": "step", "path": "mixed/first.step"},
            {"id": "Report", "format": "csv", "path": "mixed/report.csv"},
            {"id": "Drawing", "format": "pdf", "path": "mixed/drawing.pdf"},
            {"id": "second-step", "format": "step", "path": "mixed/second.step"},
        ]
        manifest = self._make_manifest(outputs=outputs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest_path, result_path = self._create_working_copy(
                Path(tmp_dir),
                manifest,
            )

            first_run = self._run_execute(working, manifest_path, result_path)
            first_result_bytes = result_path.read_bytes()
            first_artifacts = json.loads(first_result_bytes.decode("utf-8"))["artifacts"]
            second_run = self._run_execute(working, manifest_path, result_path)
            second_result_bytes = result_path.read_bytes()
            second_artifacts = json.loads(second_result_bytes.decode("utf-8"))["artifacts"]

        expected_artifacts = [
            {"format": output["format"], "id": output["id"], "path": output["path"]}
            for output in outputs
        ]
        self.assertEqual(first_run, (0, "", ""))
        self.assertEqual(second_run, (0, "", ""))
        self.assertEqual(first_artifacts, expected_artifacts)
        self.assertEqual(second_artifacts, expected_artifacts)
        self.assertEqual(first_result_bytes, second_result_bytes)

    def test_repeated_handled_execute_failure_is_stable(self) -> None:
        manifest = self._make_manifest(
            assignments=[],
            outputs=[],
        )

        with tempfile.TemporaryDirectory() as first_tmp, tempfile.TemporaryDirectory() as second_tmp:
            first_working, first_manifest, first_result = self._create_working_copy(
                Path(first_tmp),
                manifest,
            )
            second_working, second_manifest, second_result = self._create_working_copy(
                Path(second_tmp),
                manifest,
            )

            first_run = self._run_execute(
                first_working,
                first_manifest,
                first_result,
                freecad_module=_FreeCAD(recompute_error=RuntimeError("stable recompute boom")),
            )
            second_run = self._run_execute(
                second_working,
                second_manifest,
                second_result,
                freecad_module=_FreeCAD(recompute_error=RuntimeError("stable recompute boom")),
            )
            first_result_bytes = first_result.read_bytes()
            second_result_bytes = second_result.read_bytes()

        self.assertEqual(first_run[0], headless.EXECUTION_FAILURE_EXIT_CODE)
        self.assertEqual(second_run[0], headless.EXECUTION_FAILURE_EXIT_CODE)
        self.assertEqual(first_run, second_run)
        self.assertEqual(first_result_bytes, second_result_bytes)
        self.assertTrue(first_result_bytes.endswith(b"\n"))
        self.assertEqual(first_result_bytes.count(b"\n"), 1)
        failure_payload = json.loads(first_result_bytes.decode("utf-8"))
        self.assertEqual(failure_payload["schemaVersion"], "1.0")
        self.assertEqual(failure_payload["status"], "failed")
        self.assertEqual(failure_payload["failure"]["category"], "execution")
        self.assertEqual(failure_payload["failure"]["code"], "runtime_failure")
        self.assertEqual(failure_payload["failure"]["stage"], "recompute")
        self.assertIn(
            "document recompute raised an exception: stable recompute boom",
            failure_payload["failure"]["message"],
        )
        self.assertEqual(first_run[1], "")
        self.assertTrue(first_run[2].startswith(headless.EXECUTION_FAILURE_MESSAGE_PREFIX))
        self.assertTrue(first_run[2].endswith("\n"))
        self.assertEqual(first_run[2].count("\n"), 1)
        self.assertNotIn("Traceback", first_run[2])
        self.assertIn("document recompute raised an exception: stable recompute boom", first_run[2])


if __name__ == "__main__":
    unittest.main()
