from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "reference_traversal"
RUNNER = Path(__file__).parent / "freecad_reference_fixture_runner.py"
GENERATOR = REPOSITORY_ROOT / "scripts" / "generate_reference_traversal_fixtures.py"
SOURCE_DOCUMENT = "reference-root.FCStd"
OUTPUT_FILENAME = "parametron.reference-traversal.json"

MAPPINGS = [
    {
        "sourceObjectName": "ExternalSourceOne",
        "sourceProperty": "ExternalLink",
        "referenceMechanism": "App::PropertyXLink",
        "targetObjectName": "SharedTarget",
        "targetDocumentPath": "references/reference-a.FCStd",
    },
    {
        "sourceObjectName": "ExternalSourceTwo",
        "sourceProperty": "ExternalLink",
        "referenceMechanism": "App::PropertyXLink",
        "targetObjectName": "SharedTarget",
        "targetDocumentPath": "references/reference-a.FCStd",
    },
    {
        "sourceObjectName": "MissingSource",
        "sourceProperty": "MissingLink",
        "referenceMechanism": "App::PropertyXLink",
        "targetObjectName": "MissingTarget",
        "targetDocumentPath": "references/missing-target.FCStd",
    },
    {
        "sourceObjectName": "SecondExternalSource",
        "sourceProperty": "ExternalLink",
        "referenceMechanism": "App::PropertyXLink",
        "targetObjectName": "SecondTarget",
        "targetDocumentPath": "references/reference-b.FCStd",
    },
]

FROZEN_NODE_IDS = {
    ("document", SOURCE_DOCUMENT, None): "document:dcb70b9cce6a92c321167746025daaefe3f9737d8ad451acc82c3eae71868cca",
    ("object", SOURCE_DOCUMENT, "InternalSource"): "object:07793d63ff00e9e43720eca43a8b72e268fd73bf02274a6b72fc193e0020a905",
    ("object", SOURCE_DOCUMENT, "ExternalSourceTwo"): "object:3888b40c7d3d5d7a648642824e6f0440eed2c0ac7d5c0cda295285c99b1db228",
    ("object", SOURCE_DOCUMENT, "SecondExternalSource"): "object:5b7d456be9c0a4a0f699d3e5fe9b491fe3eabf22658d5a10ef7edac382a9ee32",
    ("object", SOURCE_DOCUMENT, "ExternalSourceOne"): "object:c9c8bfa66deb6eecfe5e03ffffd5f9e78327873ba772830e6c23a5d89fbcc2eb",
    ("object", SOURCE_DOCUMENT, "MissingSource"): "object:d869fc40d63a8beb6592d0a332bd176ed697a1155e20fde8b30e8f5967cfe87a",
    ("object", SOURCE_DOCUMENT, "InternalTarget"): "object:da7fbe4587bf67f2992abc4f29803dbaa28c00822e532720c87c3f7b90233b68",
    ("object", "references/missing-target.FCStd", "MissingTarget"): "object:da9b5becc8fbdacaf5d3535bdcbf2a0b3bfed64360dad1d3fc29f5c867a686fd",
    ("object", "references/reference-a.FCStd", "SharedTarget"): "object:dbfbbcf7f61d238e135f7fe9267027f50e8d117bb12405894818010a15934fc2",
    ("object", "references/reference-b.FCStd", "SecondTarget"): "object:dab993f9c2112f461e5185edbdc1db2750615c0c21fa895e4f2e48be68c57efc",
}


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _independent_node_id(kind: str, document_path: str, object_name: str | None) -> str:
    identity = (kind, document_path) if object_name is None else (
        kind,
        document_path,
        object_name,
    )
    return f"{kind}:{hashlib.sha256(_canonical_bytes(identity)).hexdigest()}"


def _node(
    sequence: int,
    *,
    kind: str,
    document_path: str,
    object_name: str | None,
    label: str | None,
    state: str = "resolved",
    object_type: str | None = "App::FeaturePython",
) -> dict[str, object]:
    return {
        "sequence": sequence,
        "id": FROZEN_NODE_IDS[(kind, document_path, object_name)],
        "kind": kind,
        "state": state,
        "documentPath": document_path,
        "objectName": object_name,
        "objectType": object_type,
        "label": label,
        "diagnostic": None,
    }


def _edge(
    sequence: int,
    *,
    source_name: str,
    target_identity: tuple[str, str, str | None],
    kind: str,
    source_property: str,
    mechanism: str,
    state: str = "resolved",
) -> dict[str, object]:
    return {
        "sequence": sequence,
        "source": FROZEN_NODE_IDS[("object", SOURCE_DOCUMENT, source_name)],
        "target": FROZEN_NODE_IDS[target_identity],
        "kind": kind,
        "sourceProperty": source_property,
        "referenceMechanism": mechanism,
        "state": state,
        "diagnostic": None,
    }


def _expected_payload(*, mapped: bool) -> dict[str, object]:
    nodes = [
        _node(
            0,
            kind="document",
            document_path=SOURCE_DOCUMENT,
            object_name=None,
            object_type=None,
            label="reference-root",
        ),
        _node(1, kind="object", document_path=SOURCE_DOCUMENT, object_name="InternalSource", label="InternalSource"),
    ]
    edges = [
        _edge(
            0,
            source_name="InternalSource",
            target_identity=("object", SOURCE_DOCUMENT, "InternalTarget"),
            kind="document_internal_reference",
            source_property="InternalLink",
            mechanism="App::PropertyLink",
        )
    ]
    if mapped:
        nodes.extend([
            _node(2, kind="object", document_path=SOURCE_DOCUMENT, object_name="ExternalSourceTwo", label="ExternalSourceTwo"),
            _node(3, kind="object", document_path=SOURCE_DOCUMENT, object_name="SecondExternalSource", label="SecondExternalSource"),
            _node(4, kind="object", document_path=SOURCE_DOCUMENT, object_name="ExternalSourceOne", label="ExternalSourceOne"),
            _node(5, kind="object", document_path=SOURCE_DOCUMENT, object_name="MissingSource", label="MissingSource"),
            _node(6, kind="object", document_path=SOURCE_DOCUMENT, object_name="InternalTarget", label="InternalTarget"),
            _node(7, kind="object", document_path="references/missing-target.FCStd", object_name="MissingTarget", object_type=None, label=None, state="missing"),
            _node(8, kind="object", document_path="references/reference-a.FCStd", object_name="SharedTarget", label="SharedTarget"),
            _node(9, kind="object", document_path="references/reference-b.FCStd", object_name="SecondTarget", label="SecondTarget"),
        ])
        edges.extend([
            _edge(1, source_name="ExternalSourceTwo", target_identity=("object", "references/reference-a.FCStd", "SharedTarget"), kind="external_document_reference", source_property="ExternalLink", mechanism="App::PropertyXLink"),
            _edge(2, source_name="SecondExternalSource", target_identity=("object", "references/reference-b.FCStd", "SecondTarget"), kind="external_document_reference", source_property="ExternalLink", mechanism="App::PropertyXLink"),
            _edge(3, source_name="ExternalSourceOne", target_identity=("object", "references/reference-a.FCStd", "SharedTarget"), kind="external_document_reference", source_property="ExternalLink", mechanism="App::PropertyXLink"),
            _edge(4, source_name="MissingSource", target_identity=("object", "references/missing-target.FCStd", "MissingTarget"), kind="external_document_reference", source_property="MissingLink", mechanism="App::PropertyXLink", state="missing"),
        ])
    else:
        nodes.append(
            _node(2, kind="object", document_path=SOURCE_DOCUMENT, object_name="InternalTarget", label="InternalTarget")
        )
    return {
        "schemaVersion": "2.0",
        "kind": "raw_reference_traversal",
        "boundary": "reference_traversal_entrypoint",
        "operation": "reference_traversal",
        "status": "succeeded",
        "sourceDocument": SOURCE_DOCUMENT,
        "nodes": nodes,
        "edges": edges,
        "diagnostics": [],
    }


def _fixture_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*.FCStd"))
    }


class RealReferenceTraversalFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configured_host = os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd")
        cls.freecad_host = shutil.which(configured_host)
        cls.wrapper = shutil.which("parametron-freecad")
        missing = []
        if cls.freecad_host is None:
            missing.append(f"FreeCAD host {configured_host!r}")
        if cls.wrapper is None:
            missing.append("parametron-freecad wrapper")
        if missing:
            message = " and ".join(missing) + " unavailable outside the Nix shell"
            if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
                raise AssertionError(message)
            raise unittest.SkipTest(message)
        cls.committed_hashes = _fixture_hashes(FIXTURE_ROOT)

    @classmethod
    def tearDownClass(cls) -> None:
        if _fixture_hashes(FIXTURE_ROOT) != cls.committed_hashes:
            raise AssertionError("real FreeCAD fixture bytes changed during tests")

    def _copy_bundle(self, destination: Path) -> None:
        shutil.copytree(FIXTURE_ROOT, destination)

    def _write_request(self, path: Path, *, mapped: bool = True) -> None:
        path.write_bytes(_canonical_bytes({
            "schemaVersion": "2.0" if mapped else "1.0",
            **({"externalTargets": MAPPINGS} if mapped else {}),
        }))

    def _direct_payload(self, bundle: Path, *, mapped: bool = True) -> bytes:
        request = bundle.parent / ("mapped-request.json" if mapped else "legacy-request.json")
        output = bundle.parent / ("mapped-output.json" if mapped else "legacy-output.json")
        self._write_request(request, mapped=mapped)
        command = [
            self.freecad_host,
            "-P",
            str(REPOSITORY_ROOT),
            str(RUNNER),
            f"--pass={bundle / SOURCE_DOCUMENT}",
            f"--pass={request}",
            f"--pass={output}",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        return output.read_bytes()

    def test_runtime_native_save_persists_mutation_across_real_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            working = Path(temporary)
            source = working / "persistence.FCStd"
            manifest = working / "manifest.json"
            result = working / "result.json"
            proof = working / "proof.txt"
            script = working / "persistence_runner.py"
            manifest.write_bytes(_canonical_bytes({
                "schemaVersion": "1.0",
                "sourceDocument": source.name,
                "parameterAssignments": [
                    {"target": "Probe.Value", "value": 42, "valueKind": "scalar"}
                ],
                "outputs": [],
            }))
            script.write_text(
                """from pathlib import Path
import sys
import FreeCAD as App
from parametron_freecad.runtime.entrypoints import run_execution_entrypoint

values = [Path(arg[7:]) for arg in sys.argv if arg.startswith('--pass=')]
working, source, manifest, result, proof = values
created = App.newDocument('PersistenceProbe')
probe = created.addObject('App::FeaturePython', 'Probe')
probe.addProperty('App::PropertyInteger', 'Value')
probe.Value = 1
created.recompute()
created.saveAs(str(source))
App.closeDocument(created.Name)
run_execution_entrypoint(
    working_copy=working,
    manifest_path=manifest,
    result_path=result,
    freecad_module=App,
)
reopened = App.openDocument(str(source))
try:
    observed = reopened.getObject('Probe').Value
    if observed != 42:
        raise RuntimeError(f'persistence mismatch: {observed!r}')
    proof.write_text(str(observed), encoding='utf-8')
finally:
    App.closeDocument(reopened.Name)
""",
                encoding="utf-8",
            )
            command = [
                self.freecad_host,
                "-P",
                str(REPOSITORY_ROOT),
                str(script),
                f"--pass={working}",
                f"--pass={source}",
                f"--pass={manifest}",
                f"--pass={result}",
                f"--pass={proof}",
            ]
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=30, check=False
            )

            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            self.assertEqual(proof.read_text(encoding="utf-8"), "42")
            self.assertEqual(json.loads(result.read_text(encoding="utf-8"))["artifacts"], [])

    def test_frozen_node_ids_match_independent_public_formula(self) -> None:
        for identity, frozen in FROZEN_NODE_IDS.items():
            with self.subTest(identity=identity):
                self.assertEqual(_independent_node_id(*identity), frozen)

    def test_real_fixture_direct_traversal_matches_exact_schema_2_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "direct-real-bundle"
            self._copy_bundle(bundle)
            emitted = self._direct_payload(bundle)

        expected = _expected_payload(mapped=True)
        self.assertEqual(emitted, _canonical_bytes(expected))
        self.assertEqual(json.loads(emitted), expected)
        rendered = emitted.decode("utf-8")
        self.assertNotIn("unsupported_reference_value_shape", rendered)
        self.assertNotIn("Document.FileName", rendered)
        self.assertNotIn("timestamp", rendered.lower())
        self.assertEqual(
            sum(node["objectName"] == "SharedTarget" for node in expected["nodes"]),
            1,
        )
        self.assertEqual(
            sum(edge["target"] == FROZEN_NODE_IDS[("object", "references/reference-a.FCStd", "SharedTarget")] for edge in expected["edges"]),
            2,
        )

    def test_schema_1_request_behavior_remains_internal_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "legacy-real-bundle"
            self._copy_bundle(bundle)
            emitted = self._direct_payload(bundle, mapped=False)
        self.assertEqual(emitted, _canonical_bytes(_expected_payload(mapped=False)))

    def _run_runtime(self, working_root: Path) -> bytes:
        self._copy_bundle(working_root)
        output_directory = working_root / "outputs"
        output_directory.mkdir()
        manifest = working_root / "export_manifest_v1.json"
        manifest.write_bytes(_canonical_bytes({
            "schemaVersion": "1.0",
            "sourceDocument": SOURCE_DOCUMENT,
            "parameterAssignments": [],
            "outputs": [],
        }))
        request = working_root / "reference-request.json"
        self._write_request(request)
        result = working_root / "result.json"
        command = [
            self.wrapper,
            "execute",
            "--working-copy", str(working_root),
            "--manifest", str(manifest),
            "--result", str(result),
            "--output-dir", str(output_directory),
            "--reference-traversal-request", str(request),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertEqual(json.loads(result.read_bytes())["status"], "succeeded")
        return (output_directory / OUTPUT_FILENAME).read_bytes()

    def test_runtime_emission_is_relocation_and_repeated_run_byte_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first_root = base / "arbitrary-alpha"
            second_root = base / "nested-parent" / "nested-beta"
            second_root.parent.mkdir()
            first = self._run_runtime(first_root)
            repeated = self._run_runtime(base / "arbitrary-alpha-repeat")
            second = self._run_runtime(second_root)

        expected = _canonical_bytes(_expected_payload(mapped=True))
        self.assertEqual(first, expected)
        self.assertEqual(repeated, expected)
        self.assertEqual(second, expected)
        self.assertEqual(first, repeated)
        self.assertEqual(first, second)
        rendered = first.decode("utf-8")
        for prohibited in (str(base), "arbitrary-alpha", "nested-beta"):
            self.assertNotIn(prohibited, rendered)

    def test_maintenance_generator_is_semantically_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            regenerated = base / "regenerated"
            command = [
                self.freecad_host,
                str(GENERATOR),
                f"--pass={regenerated}",
            ]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            self.assertEqual(
                sorted(str(path.relative_to(regenerated)) for path in regenerated.rglob("*.FCStd")),
                [
                    "reference-root.FCStd",
                    "references/reference-a.FCStd",
                    "references/reference-b.FCStd",
                ],
            )
            committed = base / "committed-copy"
            self._copy_bundle(committed)
            self.assertEqual(self._direct_payload(regenerated), self._direct_payload(committed))


if __name__ == "__main__":
    unittest.main()
