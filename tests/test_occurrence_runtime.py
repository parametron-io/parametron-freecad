"""Runtime integration tests for occurrence evidence emission."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest import mock

from parametron_freecad.runtime import entrypoints
from parametron_freecad.runtime.document_lifecycle import OpenedDocument
from parametron_freecad.runtime.entrypoints import _ExecutionEntrypointDependencies
from parametron_freecad.runtime.occurrence_evidence import (
    OCCURRENCE_EVIDENCE_FILENAME,
)

_SOURCE_COORDINATE = "source/Assembly.FCStd"
_SECONDARY_COORDINATE = "resources/component-a.FCStd"


class _FakeFreeCADModule:
    def Version(self) -> tuple[str, str, str]:
        return ("1", "1", "4")


class _FakeDocument:
    def __init__(self, file_name: str | Path) -> None:
        self.FileName = str(file_name)
        self._objects: dict[str, object] = {}

    def add(self, native_object: "_FakeNativeObject") -> "_FakeNativeObject":
        native_object.Document = self
        self._objects[native_object.Name] = native_object
        return native_object

    def getObject(self, name: str) -> object | None:
        return self._objects.get(name)


class _FakeNativeObject:
    def __init__(self, document: _FakeDocument, name: str, type_id: str) -> None:
        self.Document = document
        self.Name = name
        self.TypeId = type_id
        self.InList: list[object] = []


class _FakeAssembly(_FakeNativeObject):
    def __init__(self, document: _FakeDocument) -> None:
        super().__init__(document, "Assembly", "Assembly::AssemblyObject")
        self.Group: list[object] = []

    def add(self, member: object) -> object:
        self.Group.append(member)
        member.InList.append(self)
        return member


class _FakeJointGroup(_FakeNativeObject):
    def __init__(self, document: _FakeDocument) -> None:
        super().__init__(document, "Joints", "Assembly::JointGroup")
        self.Group: list[object] = []


class _FakeLink(_FakeNativeObject):
    def __init__(self, document: _FakeDocument, name: str) -> None:
        super().__init__(document, name, "App::Link")
        self.ElementCount = 0
        self.LinkedObject: object | None = None


def _occurrence_request(logical_id: str = "assembly_root") -> dict[str, object]:
    return {
        "schemaVersion": "1.0",
        "requirement": "optional",
        "scope": {
            "parent": {
                "resource": {
                    "projectId": "project",
                    "kind": "model",
                    "logicalId": logical_id,
                },
                "nativeKind": "object",
                "name": "Assembly",
            },
            "context": [],
            "mechanism": "freecad-1.1.4-assembly-group-individual-link",
        },
    }


class OccurrenceRuntimeTests(unittest.TestCase):
    def _paths(self, tmp_dir: str) -> tuple[Path, Path, Path, Path]:
        working = Path(tmp_dir) / "run" / "_working" / "attempt"
        (working / "source").mkdir(parents=True)
        (working / "resources").mkdir(parents=True)
        (working / "outputs").mkdir()
        source = working / _SOURCE_COORDINATE
        source.write_bytes(b"source-document")
        (working / _SECONDARY_COORDINATE).write_bytes(b"component-document")
        manifest = working / "prm.export-manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "sourceDocument": _SOURCE_COORDINATE,
                    "parameterAssignments": [],
                    "outputs": [],
                }
            ),
            encoding="utf-8",
        )
        return working, manifest, working / "prm.result.json", working / "outputs"

    def _write_request(
        self,
        working: Path,
        payload: dict[str, object] | None = None,
    ) -> Path:
        request = working / "prm.occurrence-request.json"
        request.write_text(
            json.dumps(_occurrence_request() if payload is None else payload),
            encoding="utf-8",
        )
        return request

    def _integrity_request(self, working: Path) -> Path:
        request = working.parent / "prm.integrity-request.json"
        request.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "resources": [
                        {
                            "logicalId": "assembly_root",
                            "kind": "model",
                            "materializedCoordinate": _SOURCE_COORDINATE,
                            "baselineSha256": hashlib.sha256(
                                (working / _SOURCE_COORDINATE).read_bytes()
                            ).hexdigest(),
                            "expectsPersistedResult": True,
                        },
                        {
                            "logicalId": "component_a",
                            "kind": "model",
                            "materializedCoordinate": _SECONDARY_COORDINATE,
                            "baselineSha256": hashlib.sha256(
                                (working / _SECONDARY_COORDINATE).read_bytes()
                            ).hexdigest(),
                            "expectsPersistedResult": False,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        return request

    def _document(
        self,
        working: Path,
        *,
        dangling: bool = False,
        target_coordinate: str = _SOURCE_COORDINATE,
    ) -> _FakeDocument:
        document = _FakeDocument(working / _SOURCE_COORDINATE)
        assembly = _FakeAssembly(document)
        document.add(assembly)
        target_document = _FakeDocument(working / target_coordinate)
        body = target_document.add(
            _FakeNativeObject(target_document, "Body", "PartDesign::Body")
        )
        link = _FakeLink(document, "Link01")
        link.LinkedObject = body
        assembly.add(link)
        assembly.add(_FakeJointGroup(document))
        if dangling:
            assembly.Group.append(None)
        return document

    def _dependencies(
        self,
        *,
        document: _FakeDocument,
        opened_calls: list[Path] | None = None,
    ) -> _ExecutionEntrypointDependencies:
        @contextmanager
        def opened_document(
            freecad_module: Any,
            path: Path,
        ) -> Iterator[OpenedDocument]:
            del freecad_module
            if opened_calls is not None:
                opened_calls.append(path)
            yield OpenedDocument(
                path=path,
                document=document,
                document_name="Assembly",
            )

        return _ExecutionEntrypointDependencies(
            apply_parameter_assignments=mock.Mock(),
            recompute_document=mock.Mock(),
            save_document=mock.Mock(),
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
        dependencies: _ExecutionEntrypointDependencies,
        integrity_request: Path | None = None,
    ) -> None:
        entrypoints.run_execution_entrypoint(
            working_copy=working,
            manifest_path=manifest,
            result_path=result,
            output_directory=outputs,
            integrity_request_path=integrity_request,
            freecad_module=_FakeFreeCADModule(),
            _dependencies=dependencies,
        )

    def test_discovered_request_writes_complete_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            self._write_request(working)

            self._run(
                working=working,
                manifest=manifest,
                result=result,
                outputs=outputs,
                dependencies=self._dependencies(
                    document=self._document(working),
                ),
            )

            evidence = json.loads(
                (outputs / OCCURRENCE_EVIDENCE_FILENAME).read_text(encoding="utf-8")
            )
            result_payload = json.loads(result.read_text(encoding="utf-8"))
            rendered = json.dumps(evidence)

        self.assertEqual(result_payload["status"], "succeeded")
        self.assertEqual(evidence["schemaVersion"], "1.1")
        self.assertEqual(evidence["kind"], "native_occurrence_evidence")
        self.assertEqual(evidence["completeness"], "complete")
        self.assertTrue(evidence["inspectionCompleted"])
        self.assertEqual(evidence["group"], ["Joints", "Link01"])
        self.assertEqual(len(evidence["members"]), 2)
        occurrence = next(
            member
            for member in evidence["members"]
            if member["classification"] == "occurrence"
        )
        self.assertEqual(occurrence["target"]["document"], _SOURCE_COORDINATE)
        self.assertEqual(
            occurrence["target"]["entity"]["resource"]["logicalId"],
            "assembly_root",
        )
        self.assertNotIn("components", evidence)
        self.assertNotIn(str(working), rendered)
        self.assertFalse((outputs / "prm.observed.json").exists())

    def test_inventory_target_identity_joins_declared_resource(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            self._write_request(working)
            integrity_request = self._integrity_request(working)

            self._run(
                working=working,
                manifest=manifest,
                result=result,
                outputs=outputs,
                integrity_request=integrity_request,
                dependencies=self._dependencies(
                    document=self._document(
                        working,
                        target_coordinate=_SECONDARY_COORDINATE,
                    ),
                ),
            )

            evidence = json.loads(
                (outputs / OCCURRENCE_EVIDENCE_FILENAME).read_text(encoding="utf-8")
            )

        occurrence = next(
            member
            for member in evidence["members"]
            if member["classification"] == "occurrence"
        )
        self.assertEqual(evidence["completeness"], "complete")
        self.assertEqual(
            occurrence["target"],
            {
                "entity": {
                    "resource": {
                        "projectId": "project",
                        "kind": "model",
                        "logicalId": "component_a",
                    },
                    "nativeKind": "object",
                    "name": "Body",
                },
                "document": _SECONDARY_COORDINATE,
                "nativeType": "PartDesign::Body",
            },
        )

    def test_parent_must_be_selected_source_when_inventory_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            self._write_request(working, _occurrence_request("other_resource"))
            integrity_request = self._integrity_request(working)
            opened_calls: list[Path] = []

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                self._run(
                    working=working,
                    manifest=manifest,
                    result=result,
                    outputs=outputs,
                    integrity_request=integrity_request,
                    dependencies=self._dependencies(
                        document=self._document(working),
                        opened_calls=opened_calls,
                    ),
                )

            self.assertEqual(opened_calls, [])
            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "occurrence_request")
            self.assertFalse((outputs / OCCURRENCE_EVIDENCE_FILENAME).exists())

    def test_malformed_request_fails_before_open_and_removes_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            request = working / "prm.occurrence-request.json"
            request.write_text('{"schemaVersion":"2.0"}', encoding="utf-8")
            stale = outputs / OCCURRENCE_EVIDENCE_FILENAME
            stale.write_bytes(b"stale")
            opened_calls: list[Path] = []

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                self._run(
                    working=working,
                    manifest=manifest,
                    result=result,
                    outputs=outputs,
                    dependencies=self._dependencies(
                        document=self._document(working),
                        opened_calls=opened_calls,
                    ),
                )

            self.assertEqual(opened_calls, [])
            self.assertFalse(stale.exists())
            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "occurrence_request")

    def test_missing_output_directory_fails_before_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, _outputs = self._paths(tmp_dir)
            self._write_request(working)
            opened_calls: list[Path] = []

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                self._run(
                    working=working,
                    manifest=manifest,
                    result=result,
                    outputs=None,
                    dependencies=self._dependencies(
                        document=self._document(working),
                        opened_calls=opened_calls,
                    ),
                )

            self.assertEqual(opened_calls, [])
            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "occurrence_evidence")

    def test_dangling_group_entry_fails_at_occurrence_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            self._write_request(working)
            stale = outputs / OCCURRENCE_EVIDENCE_FILENAME
            stale.write_bytes(b"stale")

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                self._run(
                    working=working,
                    manifest=manifest,
                    result=result,
                    outputs=outputs,
                    dependencies=self._dependencies(
                        document=self._document(working, dangling=True),
                    ),
                )

            self.assertFalse(stale.exists())
            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "occurrence_evidence")


if __name__ == "__main__":
    unittest.main()
