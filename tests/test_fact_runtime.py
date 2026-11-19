"""Runtime integration tests for fact evidence emission."""

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
from parametron_freecad.runtime.fact_evidence import FACT_EVIDENCE_FILENAME

_SOURCE_COORDINATE = "source/Facts.FCStd"
_SECONDARY_COORDINATE = "resources/Secondary.FCStd"


class _FakeUnit:
    def __init__(self, token: str) -> None:
        self._token = token

    def __str__(self) -> str:
        return f"Unit: {self._token} (1,0,0,0,0,0,0,0) [Length]"


class _FakeQuantity:
    def __init__(self, value: float, unit: str = "mm") -> None:
        self.Value = value
        self.Unit = _FakeUnit(unit)


class _FakeNativeObject:
    def __init__(self, name: str, type_id: str) -> None:
        self.Name = name
        self.TypeId = type_id
        self._properties: dict[str, object] = {}

    @property
    def PropertiesList(self) -> list[str]:
        return list(self._properties)

    def set(self, name: str, value: object) -> None:
        self._properties[name] = value

    def __getattr__(self, name: str) -> object:
        properties = self.__dict__.get("_properties", {})
        if name in properties:
            return properties[name]
        raise AttributeError(name)


class _FakeDocument:
    def __init__(self, file_name: str | Path) -> None:
        self.FileName = str(file_name)
        self.Name = Path(file_name).stem
        self._objects: dict[str, object] = {}
        self.save_calls = 0
        self.recompute_calls = 0

    def add(self, native_object: _FakeNativeObject) -> _FakeNativeObject:
        self._objects[native_object.Name] = native_object
        return native_object

    def getObject(self, name: str) -> object | None:
        return self._objects.get(name)

    def save(self) -> None:
        self.save_calls += 1

    def recompute(self) -> None:
        self.recompute_calls += 1


class _FakeFreeCADModule:
    def __init__(self) -> None:
        self.documents_by_path: dict[Path, _FakeDocument] = {}
        self.open_documents: dict[str, _FakeDocument] = {}
        self.open_calls: list[str] = []
        self.close_calls: list[str] = []

    def Version(self) -> tuple[str, str, str]:
        return ("1", "1", "4")

    def register(self, document: _FakeDocument) -> None:
        self.documents_by_path[Path(document.FileName).resolve()] = document

    def openDocument(self, path: str) -> _FakeDocument:
        self.open_calls.append(path)
        document = self.documents_by_path[Path(path).resolve()]
        self.open_documents[document.Name] = document
        return document

    def closeDocument(self, name: str) -> None:
        self.close_calls.append(name)
        self.open_documents.pop(name, None)

    def listDocuments(self) -> tuple[str, ...]:
        return tuple(sorted(self.open_documents))

    def getDocument(self, name: str) -> _FakeDocument | None:
        return self.open_documents.get(name)


def _source_document(working: Path) -> _FakeDocument:
    document = _FakeDocument(working / _SOURCE_COORDINATE)
    box = _FakeNativeObject("Box", "Part::Box")
    box.set("Length", _FakeQuantity(10.0, "mm"))
    props = _FakeNativeObject("Props", "App::FeaturePython")
    props.set("Ratio", 3.25)
    props.set("Count", 42)
    props.set("Enabled", True)
    props.set("PlainText", "bounded string")
    document.add(box)
    document.add(props)
    return document


def _subject(logical_id: str, name: str) -> dict[str, object]:
    return {
        "resource": {
            "projectId": "project",
            "kind": "model",
            "logicalId": logical_id,
        },
        "nativeKind": "object",
        "name": name,
    }


def _binding(
    logical_id: str,
    name: str,
    property_name: str,
    value_kind: str,
    *,
    unit: str | None = None,
    requirement: str = "optional",
) -> dict[str, object]:
    binding: dict[str, object] = {
        "kind": "bound_property",
        "subject": _subject(logical_id, name),
        "context": [],
        "property": property_name,
        "valueKind": value_kind,
        "requirement": requirement,
    }
    if unit is not None:
        binding["unit"] = unit
    return binding


class FactRuntimeTests(unittest.TestCase):
    def _paths(self, tmp_dir: str) -> tuple[Path, Path, Path, Path]:
        working = Path(tmp_dir) / "run" / "_working" / "attempt"
        (working / "source").mkdir(parents=True)
        (working / "resources").mkdir(parents=True)
        (working / "outputs").mkdir()
        (working / _SOURCE_COORDINATE).write_bytes(b"source-document")
        (working / _SECONDARY_COORDINATE).write_bytes(b"secondary-document")
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

    def _write_request(self, working: Path, bindings: list[dict]) -> Path:
        request = working / "prm.fact-request.json"
        request.write_text(
            json.dumps({"schemaVersion": "1.0", "bindings": bindings}),
            encoding="utf-8",
        )
        return request

    def _integrity_request(
        self,
        working: Path,
        *,
        include_secondary: bool = False,
    ) -> Path:
        resources = []
        if include_secondary:
            resources.append(
                {
                    "logicalId": "secondary",
                    "kind": "model",
                    "materializedCoordinate": _SECONDARY_COORDINATE,
                    "baselineSha256": hashlib.sha256(
                        (working / _SECONDARY_COORDINATE).read_bytes()
                    ).hexdigest(),
                    "expectsPersistedResult": False,
                }
            )
        resources.append(
            {
                "logicalId": "source",
                "kind": "model",
                "materializedCoordinate": _SOURCE_COORDINATE,
                "baselineSha256": hashlib.sha256(
                    (working / _SOURCE_COORDINATE).read_bytes()
                ).hexdigest(),
                "expectsPersistedResult": True,
            }
        )
        request = working.parent / "prm.integrity-request.json"
        request.write_text(
            json.dumps({"schemaVersion": "1.0", "resources": resources}),
            encoding="utf-8",
        )
        return request

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
                document_name="Facts",
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
        freecad_module: Any,
        integrity_request: Path | None = None,
    ) -> None:
        entrypoints.run_execution_entrypoint(
            working_copy=working,
            manifest_path=manifest,
            result_path=result,
            output_directory=outputs,
            integrity_request_path=integrity_request,
            freecad_module=freecad_module,
            _dependencies=dependencies,
        )

    def test_discovered_fact_request_writes_typed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            self._write_request(
                working,
                [
                    _binding("source", "Box", "Length", "number", unit="mm"),
                    _binding("source", "Props", "Ratio", "number"),
                    _binding("source", "Props", "Count", "integer"),
                    _binding("source", "Props", "Enabled", "boolean"),
                    _binding("source", "Props", "PlainText", "string"),
                ],
            )
            integrity_request = self._integrity_request(working)

            self._run(
                working=working,
                manifest=manifest,
                result=result,
                outputs=outputs,
                integrity_request=integrity_request,
                freecad_module=_FakeFreeCADModule(),
                dependencies=self._dependencies(
                    document=_source_document(working),
                ),
            )

            evidence = json.loads(
                (outputs / FACT_EVIDENCE_FILENAME).read_text(encoding="utf-8")
            )
            result_payload = json.loads(result.read_text(encoding="utf-8"))
            rendered = json.dumps(evidence)

        self.assertEqual(result_payload["status"], "succeeded")
        self.assertEqual(evidence["schemaVersion"], "1.0")
        self.assertEqual(evidence["kind"], "native_fact_evidence")
        facts = {fact["property"]: fact for fact in evidence["facts"]}
        self.assertEqual(facts["Length"]["value"], 10.0)
        self.assertEqual(facts["Length"]["unit"], "mm")
        self.assertEqual(facts["Ratio"]["value"], 3.25)
        self.assertEqual(facts["Count"]["value"], 42)
        self.assertIs(facts["Enabled"]["value"], True)
        self.assertEqual(facts["PlainText"]["value"], "bounded string")
        self.assertNotIn("components", evidence)
        self.assertNotIn(str(working), rendered)
        self.assertFalse((outputs / "prm.observed.json").exists())

    def test_secondary_subject_is_opened_read_only_and_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            self._write_request(
                working,
                [
                    _binding(
                        "secondary",
                        "SecondaryProps",
                        "SecondaryLength",
                        "number",
                        unit="mm",
                    )
                ],
            )
            integrity_request = self._integrity_request(working, include_secondary=True)
            module = _FakeFreeCADModule()
            secondary = _FakeDocument(working / _SECONDARY_COORDINATE)
            props = _FakeNativeObject("SecondaryProps", "App::FeaturePython")
            props.set("SecondaryLength", _FakeQuantity(20.0, "mm"))
            secondary.add(props)
            module.register(secondary)

            self._run(
                working=working,
                manifest=manifest,
                result=result,
                outputs=outputs,
                integrity_request=integrity_request,
                freecad_module=module,
                dependencies=self._dependencies(
                    document=_source_document(working),
                ),
            )

            evidence = json.loads(
                (outputs / FACT_EVIDENCE_FILENAME).read_text(encoding="utf-8")
            )

        fact = evidence["facts"][0]
        self.assertEqual(fact["availability"], "observed")
        self.assertEqual(fact["value"], 20.0)
        self.assertEqual(fact["subject"]["document"], _SECONDARY_COORDINATE)
        self.assertEqual(module.open_calls, [str(working / _SECONDARY_COORDINATE)])
        self.assertEqual(module.close_calls, [secondary.Name])
        self.assertEqual(secondary.save_calls, 0)
        self.assertEqual(secondary.recompute_calls, 0)

    def test_malformed_request_fails_before_open_and_removes_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            (working / "prm.fact-request.json").write_text(
                '{"schemaVersion":"2.0"}', encoding="utf-8"
            )
            stale = outputs / FACT_EVIDENCE_FILENAME
            stale.write_bytes(b"stale")
            opened_calls: list[Path] = []

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                self._run(
                    working=working,
                    manifest=manifest,
                    result=result,
                    outputs=outputs,
                    freecad_module=_FakeFreeCADModule(),
                    dependencies=self._dependencies(
                        document=_source_document(working),
                        opened_calls=opened_calls,
                    ),
                )

            self.assertEqual(opened_calls, [])
            self.assertFalse(stale.exists())
            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "fact_request")

    def test_missing_output_directory_fails_before_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, _outputs = self._paths(tmp_dir)
            self._write_request(
                working,
                [_binding("source", "Props", "Ratio", "number")],
            )
            opened_calls: list[Path] = []

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                self._run(
                    working=working,
                    manifest=manifest,
                    result=result,
                    outputs=None,
                    freecad_module=_FakeFreeCADModule(),
                    dependencies=self._dependencies(
                        document=_source_document(working),
                        opened_calls=opened_calls,
                    ),
                )

            self.assertEqual(opened_calls, [])
            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "fact_evidence")

    def test_required_unavailable_fails_at_fact_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            self._write_request(
                working,
                [
                    _binding(
                        "source",
                        "Props",
                        "Missing",
                        "number",
                        requirement="required",
                    )
                ],
            )
            integrity_request = self._integrity_request(working)
            stale = outputs / FACT_EVIDENCE_FILENAME
            stale.write_bytes(b"stale")

            with self.assertRaises(entrypoints.ExecutionEntrypointError):
                self._run(
                    working=working,
                    manifest=manifest,
                    result=result,
                    outputs=outputs,
                    integrity_request=integrity_request,
                    freecad_module=_FakeFreeCADModule(),
                    dependencies=self._dependencies(
                        document=_source_document(working),
                    ),
                )

            self.assertFalse(stale.exists())
            failure = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(failure["failure"]["stage"], "fact_evidence")

    def test_without_inventory_writes_explicit_unavailability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working, manifest, result, outputs = self._paths(tmp_dir)
            self._write_request(
                working,
                [_binding("source", "Props", "Ratio", "number")],
            )

            self._run(
                working=working,
                manifest=manifest,
                result=result,
                outputs=outputs,
                freecad_module=_FakeFreeCADModule(),
                dependencies=self._dependencies(
                    document=_source_document(working),
                ),
            )

            evidence = json.loads(
                (outputs / FACT_EVIDENCE_FILENAME).read_text(encoding="utf-8")
            )
            result_payload = json.loads(result.read_text(encoding="utf-8"))

        self.assertEqual(result_payload["status"], "succeeded")
        fact = evidence["facts"][0]
        self.assertEqual(fact["availability"], "unavailable")
        self.assertIn("inventory", fact["diagnostic"])
        self.assertNotIn("value", fact)
        self.assertNotIn("valueKind", fact)


if __name__ == "__main__":
    unittest.main()
