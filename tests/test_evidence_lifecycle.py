"""Execute-lifecycle integration tests for engineering evidence sidecars."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest import mock

from parametron_freecad.execution.manifest_loader import LoadedManifest
from parametron_freecad.execution.manifest_validation import ManifestValidationResult
from parametron_freecad.runtime import entrypoints
from parametron_freecad.runtime.document_lifecycle import OpenedDocument

_SOURCE = "model.FCStd"
_SECONDARY = "resources/secondary.FCStd"
_MECHANISM = "freecad-1.1.4-assembly-group-individual-link"


def _manifest_data() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "sourceDocument": _SOURCE,
        "parameterAssignments": [],
        "outputs": [],
    }


def _patch_manifest(
    working: Path,
    source: Path,
    *,
    data: dict[str, Any] | None = None,
):
    loaded = LoadedManifest(
        path=working / "manifest.json",
        data=_manifest_data() if data is None else data,
    )
    return (
        mock.patch.object(entrypoints, "load_export_manifest_v1", return_value=loaded),
        mock.patch.object(
            entrypoints,
            "validate_export_manifest_v1",
            return_value=ManifestValidationResult(diagnostics=()),
        ),
        mock.patch.object(
            entrypoints, "resolve_source_document_path", return_value=source
        ),
    )


@contextmanager
def _patched_manifest(working: Path, source: Path, *, data=None) -> Iterator[None]:
    patches = _patch_manifest(working, source, data=data)
    with patches[0], patches[1], patches[2]:
        yield


def _occurrence_request() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "requirement": "optional",
        "scope": {
            "parent": {
                "resource": {
                    "projectId": "project",
                    "kind": "model",
                    "logicalId": "source",
                },
                "nativeKind": "object",
                "name": "Assembly",
            },
            "context": [],
            "mechanism": _MECHANISM,
        },
    }


def _fact_request() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "bindings": [
            {
                "kind": "bound_property",
                "subject": {
                    "resource": {
                        "projectId": "project",
                        "kind": "model",
                        "logicalId": "source",
                    },
                    "nativeKind": "object",
                    "name": "Props",
                },
                "context": [],
                "property": "Ratio",
                "valueKind": "number",
                "requirement": "optional",
            }
        ],
    }


def _integrity_request(working: Path, *, source_digest: str | None = None) -> Path:
    path = working / "integrity.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "resources": [
                    {
                        "logicalId": "source",
                        "kind": "model",
                        "materializedCoordinate": _SOURCE,
                        "baselineSha256": (
                            source_digest
                            if source_digest is not None
                            else hashlib.sha256(
                                (working / _SOURCE).read_bytes()
                            ).hexdigest()
                        ),
                        "expectsPersistedResult": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


class _LifecycleDependencies:
    def __init__(
        self,
        *,
        events: list[str],
        open_error: bool = False,
        observation=None,
        write_success_result=None,
    ) -> None:
        self.events = events
        self.open_error = open_error
        self.observation = observation
        self.write_success_result = write_success_result
        self.opened_count = 0
        self.closed_count = 0

    def dependencies(self) -> entrypoints._ExecutionEntrypointDependencies:
        @contextmanager
        def opened(module: Any, path: Path) -> Iterator[OpenedDocument]:
            del module
            if self.open_error:
                raise AssertionError("document must not open")
            self.opened_count += 1
            self.events.append("open")
            try:
                yield OpenedDocument(
                    path=path,
                    document=object(),
                    document_name="Document",
                )
            finally:
                self.closed_count += 1
                self.events.append("close")

        def assign(*args: Any) -> None:
            del args
            self.events.append("assign")

        def recompute(*args: Any) -> None:
            del args
            self.events.append("recompute")

        def save(*args: Any) -> None:
            del args
            self.events.append("save")

        def exporter(name: str):
            def export(*args: Any, **kwargs: Any) -> None:
                del args, kwargs
                self.events.append(name)

            return export

        def observe(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            self.events.append("observation")

        def result(*args: Any) -> None:
            del args
            self.events.append("result")

        return entrypoints._ExecutionEntrypointDependencies(
            apply_parameter_assignments=assign,
            recompute_document=recompute,
            save_document=save,
            export_step_artifacts=exporter("step"),
            export_csv_artifacts=exporter("csv"),
            export_pdf_artifacts=exporter("pdf"),
            opened_freecad_document=opened,
            write_success_result=self.write_success_result or result,
            run_observation_entrypoint=self.observation or observe,
        )


class EvidenceOutputDirectoryTests(unittest.TestCase):
    def _surface(
        self,
        root: Path,
        name: str,
    ) -> dict[str, Any]:
        if name == "traversal":
            return {"reference_traversal_request_path": root / "traversal.json"}
        if name == "observation":
            return {"observation_request_path": root / "observation.json"}
        if name == "integrity":
            return {"integrity_request_path": str(root / "integrity.json")}
        if name == "occurrence":
            (root / "prm.occurrence-request.json").write_text("{}", encoding="utf-8")
            return {}
        if name == "fact":
            (root / "prm.fact-request.json").write_text("{}", encoding="utf-8")
            return {}
        raise AssertionError(name)

    def _expected_stage(self, name: str) -> str:
        return {
            "traversal": "reference_traversal_output_containment",
            "observation": "observation_output",
            "integrity": "integrity_evidence",
            "occurrence": "occurrence_evidence",
            "fact": "fact_evidence",
        }[name]

    def test_every_evidence_surface_requires_output_directory(self) -> None:
        for name in ("traversal", "observation", "integrity", "occurrence", "fact"):
            for output_kind in ("missing", "absent"):
                with (
                    self.subTest(surface=name, output=output_kind),
                    tempfile.TemporaryDirectory() as tmp,
                ):
                    working = Path(tmp)
                    source = working / _SOURCE
                    source.write_bytes(b"source")
                    result = working / "result.json"
                    output = (
                        None if output_kind == "absent" else working / "missing-output"
                    )
                    kwargs = self._surface(working, name)
                    events: list[str] = []
                    dependencies = _LifecycleDependencies(
                        events=events, open_error=True
                    )

                    with (
                        _patched_manifest(working, source),
                        self.assertRaises(entrypoints.EvidenceOutputDirectoryError),
                    ):
                        entrypoints.run_execution_entrypoint(
                            working_copy=working,
                            manifest_path=working / "manifest.json",
                            result_path=result,
                            output_directory=output,
                            freecad_module=object(),
                            _dependencies=dependencies.dependencies(),
                            **kwargs,
                        )

                    self.assertEqual(events, [])
                    self.assertEqual(dependencies.opened_count, 0)
                    payload = json.loads(result.read_text(encoding="utf-8"))
                    self.assertEqual(payload["status"], "failed")
                    self.assertEqual(
                        payload["failure"]["stage"], self._expected_stage(name)
                    )

    def test_stale_evidence_is_removed_before_request_loading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / _SOURCE
            source.write_bytes(b"source")
            output = working / "output"
            output.mkdir()
            stale_names = (
                "prm.reference-traversal.json",
                "prm.observed.json",
                "prm.integrity-evidence.json",
                "prm.occurrence-evidence.json",
                "prm.fact-evidence.json",
            )
            for name in stale_names:
                (output / name).write_bytes(b"stale")
            traversal_request = working / "traversal.json"
            traversal_request.write_text("{}", encoding="utf-8")
            (working / "prm.occurrence-request.json").write_text("{}", encoding="utf-8")
            (working / "prm.fact-request.json").write_text("{}", encoding="utf-8")
            result = working / "result.json"
            events: list[str] = []
            dependencies = _LifecycleDependencies(events=events)

            with (
                _patched_manifest(working, source),
                self.assertRaises(entrypoints.ExecutionEntrypointError),
            ):
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=working / "manifest.json",
                    result_path=result,
                    output_directory=output,
                    observation_request_path=working / "observation.json",
                    reference_traversal_request_path=traversal_request,
                    integrity_request_path=str(working / "integrity.json"),
                    freecad_module=object(),
                    _dependencies=dependencies.dependencies(),
                )

            for name in (
                "prm.observed.json",
                "prm.integrity-evidence.json",
                "prm.occurrence-evidence.json",
                "prm.fact-evidence.json",
            ):
                self.assertFalse((output / name).exists(), name)
            trajectory = json.loads(
                (output / "prm.reference-traversal.json").read_text(encoding="utf-8")
            )
            self.assertEqual(trajectory["status"], "failed")
            payload = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(payload["failure"]["stage"], "request_validation")
            self.assertEqual(events, [])


class FailurePrecedenceTests(unittest.TestCase):
    def test_baseline_mismatch_precedes_occurrence_request_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / _SOURCE
            source.write_bytes(b"source")
            output = working / "output"
            output.mkdir()
            integrity_request = _integrity_request(working, source_digest="0" * 64)
            (working / "prm.occurrence-request.json").write_text("{}", encoding="utf-8")
            result = working / "result.json"
            events: list[str] = []
            dependencies = _LifecycleDependencies(events=events, open_error=True)

            with (
                _patched_manifest(working, source),
                self.assertRaises(entrypoints.ExecutionEntrypointError),
            ):
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=working / "manifest.json",
                    result_path=result,
                    output_directory=output,
                    integrity_request_path=str(integrity_request),
                    freecad_module=object(),
                    _dependencies=dependencies.dependencies(),
                )

            self.assertEqual(events, [])
            payload = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(payload["failure"]["stage"], "integrity_baseline")

    def test_output_directory_preflight_precedes_baseline_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / _SOURCE
            source.write_bytes(b"source")
            integrity_request = _integrity_request(working, source_digest="0" * 64)
            result = working / "result.json"
            events: list[str] = []
            dependencies = _LifecycleDependencies(events=events, open_error=True)

            with (
                _patched_manifest(working, source),
                self.assertRaises(entrypoints.EvidenceOutputDirectoryError),
            ):
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=working / "manifest.json",
                    result_path=result,
                    output_directory=None,
                    integrity_request_path=str(integrity_request),
                    freecad_module=object(),
                    _dependencies=dependencies.dependencies(),
                )

            self.assertEqual(events, [])
            payload = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(payload["failure"]["stage"], "integrity_evidence")

    def test_occurrence_request_precedes_fact_request_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / _SOURCE
            source.write_bytes(b"source")
            output = working / "output"
            output.mkdir()
            (working / "prm.occurrence-request.json").write_text("{}", encoding="utf-8")
            (working / "prm.fact-request.json").write_text("{}", encoding="utf-8")
            result = working / "result.json"
            events: list[str] = []
            dependencies = _LifecycleDependencies(events=events, open_error=True)

            with (
                _patched_manifest(working, source),
                self.assertRaises(entrypoints.ExecutionEntrypointError),
            ):
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=working / "manifest.json",
                    result_path=result,
                    output_directory=output,
                    freecad_module=object(),
                    _dependencies=dependencies.dependencies(),
                )

            self.assertEqual(events, [])
            payload = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(payload["failure"]["stage"], "occurrence_request")


class EvidenceOrderingTests(unittest.TestCase):
    def test_occurrence_and_fact_follow_observation_before_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / _SOURCE
            source.write_bytes(b"source")
            output = working / "output"
            output.mkdir()
            (working / "prm.occurrence-request.json").write_text(
                json.dumps(_occurrence_request()), encoding="utf-8"
            )
            (working / "prm.fact-request.json").write_text(
                json.dumps(_fact_request()), encoding="utf-8"
            )
            observation_request = working / "observation.json"
            observation_request.write_text("{}", encoding="utf-8")
            result = working / "result.json"
            events: list[str] = []
            occurrence_observation = object()
            fact_observation = object()

            def inspect_occurrence(*args: Any, **kwargs: Any) -> Any:
                del args, kwargs
                events.append("occurrence")
                return occurrence_observation

            def inspect_fact(*args: Any, **kwargs: Any) -> Any:
                del args, kwargs
                events.append("fact")
                return fact_observation

            def write_occurrence(*args: Any, **kwargs: Any) -> None:
                del args, kwargs
                self.assertIs(args[0] if args else None, occurrence_observation)
                events.append("occurrence-write")

            def write_fact(*args: Any, **kwargs: Any) -> None:
                del args, kwargs
                events.append("fact-write")

            dependencies = _LifecycleDependencies(events=events)

            with (
                _patched_manifest(working, source),
                mock.patch.object(
                    entrypoints,
                    "load_observation_request",
                    return_value={"observe": {}},
                ),
                mock.patch.object(
                    entrypoints,
                    "inspect_occurrence_evidence",
                    side_effect=inspect_occurrence,
                ),
                mock.patch.object(
                    entrypoints, "inspect_fact_evidence", side_effect=inspect_fact
                ),
                mock.patch.object(
                    entrypoints,
                    "write_occurrence_evidence",
                    side_effect=lambda observation, **kwargs: (
                        self.assertIs(observation, occurrence_observation),
                        events.append("occurrence-write"),
                    ),
                ),
                mock.patch.object(
                    entrypoints, "write_fact_evidence", side_effect=write_fact
                ),
            ):
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=working / "manifest.json",
                    result_path=result,
                    output_directory=output,
                    observation_request_path=observation_request,
                    freecad_module=object(),
                    _dependencies=dependencies.dependencies(),
                )

            self.assertEqual(
                events,
                [
                    "open",
                    "assign",
                    "recompute",
                    "save",
                    "step",
                    "csv",
                    "pdf",
                    "observation",
                    "occurrence",
                    "fact",
                    "occurrence-write",
                    "fact-write",
                    "close",
                    "result",
                ],
            )
            self.assertEqual(dependencies.opened_count, 1)
            self.assertEqual(dependencies.closed_count, 1)


class _FakeUnit:
    def __init__(self, token: str) -> None:
        self._token = token

    def __str__(self) -> str:
        return f"Unit: {self._token} (1,0,0,0,0,0,0,0) [Length]"


class _FakeQuantity:
    def __init__(self, value: float, unit: str = "mm") -> None:
        self.Value = value
        self.Unit = _FakeUnit(unit)


class _FakeObject:
    def __init__(self, name: str) -> None:
        self.Name = name
        self.TypeId = "App::FeaturePython"
        self._properties = {"Ratio": 3.25}

    @property
    def PropertiesList(self) -> list[str]:
        return list(self._properties)

    def __getattr__(self, name: str) -> Any:
        properties = self.__dict__.get("_properties", {})
        if name in properties:
            return properties[name]
        raise AttributeError(name)


class _FakeDocument:
    def __init__(self, file_name: Path) -> None:
        self.FileName = str(file_name)
        self.Name = file_name.stem
        self._objects = {"SecondaryProps": _FakeObject("SecondaryProps")}
        self.save_calls = 0
        self.recompute_calls = 0

    def getObject(self, name: str) -> Any:
        return self._objects.get(name)

    def save(self) -> None:
        self.save_calls += 1

    def recompute(self) -> None:
        self.recompute_calls += 1


class _FakeFreeCADModule:
    def __init__(self, secondary: _FakeDocument, events: list[str]) -> None:
        self.secondary = secondary
        self.events = events
        self.open_documents: dict[str, _FakeDocument] = {}

    def Version(self) -> tuple[str, str, str]:
        return ("1", "1", "4")

    def openDocument(self, path: str) -> _FakeDocument:
        self.open_documents[self.secondary.Name] = self.secondary
        return self.secondary

    def closeDocument(self, name: str) -> None:
        self.events.append(f"close-secondary:{name}")
        self.open_documents.pop(name, None)

    def listDocuments(self) -> tuple[str, ...]:
        return tuple(sorted(self.open_documents))

    def getDocument(self, name: str) -> _FakeDocument | None:
        return self.open_documents.get(name)


class SecondaryDocumentLifecycleTests(unittest.TestCase):
    def test_secondary_document_closes_before_selected_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            working = Path(tmp)
            source = working / _SOURCE
            source.write_bytes(b"source")
            secondary_path = working / _SECONDARY
            secondary_path.parent.mkdir(parents=True)
            secondary_path.write_bytes(b"secondary")
            output = working / "output"
            output.mkdir()
            integrity_request = working / "integrity.json"
            integrity_request.write_text(
                json.dumps(
                    {
                        "schemaVersion": "1.0",
                        "resources": [
                            {
                                "logicalId": "secondary",
                                "kind": "model",
                                "materializedCoordinate": _SECONDARY,
                                "baselineSha256": hashlib.sha256(
                                    secondary_path.read_bytes()
                                ).hexdigest(),
                                "expectsPersistedResult": False,
                            },
                            {
                                "logicalId": "source",
                                "kind": "model",
                                "materializedCoordinate": _SOURCE,
                                "baselineSha256": hashlib.sha256(
                                    source.read_bytes()
                                ).hexdigest(),
                                "expectsPersistedResult": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (working / "prm.fact-request.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "1.0",
                        "bindings": [
                            {
                                "kind": "bound_property",
                                "subject": {
                                    "resource": {
                                        "projectId": "project",
                                        "kind": "model",
                                        "logicalId": "secondary",
                                    },
                                    "nativeKind": "object",
                                    "name": "SecondaryProps",
                                },
                                "context": [],
                                "property": "Ratio",
                                "valueKind": "number",
                                "requirement": "optional",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = working / "result.json"
            events: list[str] = []
            secondary = _FakeDocument(secondary_path)
            module = _FakeFreeCADModule(secondary, events)

            @contextmanager
            def opened(freecad_module: Any, path: Path) -> Iterator[OpenedDocument]:
                del freecad_module
                events.append("open-source")
                document = _FakeDocument(path)
                try:
                    yield OpenedDocument(
                        path=path,
                        document=document,
                        document_name="Source",
                    )
                finally:
                    events.append("close-source")

            dependencies = _LifecycleDependencies(events=events)
            dependencies.dependencies = lambda: (
                entrypoints._ExecutionEntrypointDependencies(
                    apply_parameter_assignments=lambda *args: None,
                    recompute_document=lambda *args: None,
                    save_document=lambda *args: None,
                    export_step_artifacts=lambda *args, **kwargs: None,
                    export_csv_artifacts=lambda *args, **kwargs: None,
                    export_pdf_artifacts=lambda *args, **kwargs: None,
                    opened_freecad_document=opened,
                    write_success_result=lambda *args: events.append("result"),
                )
            )

            with _patched_manifest(working, source):
                entrypoints.run_execution_entrypoint(
                    working_copy=working,
                    manifest_path=working / "manifest.json",
                    result_path=result,
                    output_directory=output,
                    integrity_request_path=str(integrity_request),
                    freecad_module=module,
                    _dependencies=dependencies.dependencies(),
                )

            self.assertIn("close-secondary:secondary", events)
            self.assertLess(
                events.index("close-secondary:secondary"),
                events.index("close-source"),
            )
            self.assertEqual(secondary.save_calls, 0)
            self.assertEqual(secondary.recompute_calls, 0)
            evidence = json.loads(
                (output / "prm.fact-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(evidence["facts"][0]["availability"], "observed")


class SelectedSourceDigestTests(unittest.TestCase):
    def test_integrity_baseline_digest_is_reused_without_reading_bytes(self) -> None:
        class _Primary:
            baseline_sha256 = "a" * 64

        class _Observation:
            primary = _Primary()

        digest = entrypoints._selected_source_sha256(
            observation_enabled=True,
            integrity_observation=_Observation(),
            source_document_path=Path("/does/not/exist.FCStd"),
        )
        self.assertEqual(digest, "a" * 64)

    def test_observation_only_hashes_the_source_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / _SOURCE
            source.write_bytes(b"source-bytes")
            digest = entrypoints._selected_source_sha256(
                observation_enabled=True,
                integrity_observation=None,
                source_document_path=source,
            )
        self.assertEqual(digest, hashlib.sha256(b"source-bytes").hexdigest())


if __name__ == "__main__":
    unittest.main()
