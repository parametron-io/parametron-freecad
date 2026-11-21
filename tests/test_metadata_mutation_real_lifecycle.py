"""Permanent real-FreeCAD metadata mutation and observation proof.

Engine revision: ``3e21f5c439d312f6ad247492a57000e80efbe1e2``.

The committed ``prm.export-manifest.json`` and ``prm.verification.json`` were
materialized by the normal Engine pipeline from
``tests/fixtures/metadata_mutation``. A temporary runtime captured the exact
files Engine passed to the runtime and exited without performing CAD work::

    nix develop <engine-repo> --command go build -C <engine-repo> \
      -o /tmp/parametron-engine ./cmd/parametron
    PARAMETRON_FREECAD_RUNTIME=<capture-runtime> \
      PARAMETRON_CAPTURE_DIR=<capture-dir> \
      /tmp/parametron-engine \
      --project <freecad-repo>/tests/fixtures/metadata_mutation \
      --out <engine-out>

No runtime contract was authored locally. The manifest is byte-identical across
equivalent clean Engine runs. The verification request snapshot differs only in
Engine's run-specific absolute materialization path under
``expected.references[0].name``; the deterministic authored expectations and the
observation context are stable, and the FreeCAD proof observes its own working
copy root rather than echoing that path.

Committed digests:

- ``input/metadata-coexistence.FCStd``:
  ``b6a09b7f7092db0efb594026e8e6dc3eb5fff49fa78582851e2961e0e15910c0``
- ``prm.export-manifest.json``:
  ``4f588142c08397990349089dca6b9a27ca5ff1956c4b916473840a0de88c2fdd``
- ``prm.verification.json``:
  ``a36e5c6b6cb35ff8a8e18a0ce1a4f58f379a2db2df7bd8a34e2e8df63fef351e``
- source ``input/metadata-source.FCStd`` from the #66 bundle:
  ``acfa263a582cb95d4c19e2711f241508b1f88e611ebca7a59c34a0d2b0b99f34``

The real tests run through the production ``run_execution_entrypoint`` on a
temporary working copy. The committed source fixture is never modified.
"""

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
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "metadata_mutation"
FIXTURE_PATH = FIXTURE_DIR / "input" / "metadata-coexistence.FCStd"
SOURCE_FIXTURE_PATH = FIXTURE_DIR / "input" / "metadata-source.FCStd"
MANIFEST_PATH = FIXTURE_DIR / "prm.export-manifest.json"
VERIFICATION_PATH = FIXTURE_DIR / "prm.verification.json"
RUNNER = Path(__file__).parent / "freecad_metadata_mutation_lifecycle_runner.py"

FIXTURE_SHA256 = "b6a09b7f7092db0efb594026e8e6dc3eb5fff49fa78582851e2961e0e15910c0"
SOURCE_FIXTURE_SHA256 = (
    "acfa263a582cb95d4c19e2711f241508b1f88e611ebca7a59c34a0d2b0b99f34"
)
MANIFEST_SHA256 = "4f588142c08397990349089dca6b9a27ca5ff1956c4b916473840a0de88c2fdd"
VERIFICATION_SHA256 = "a36e5c6b6cb35ff8a8e18a0ce1a4f58f379a2db2df7bd8a34e2e8df63fef351e"

EXPECTED_MANIFEST = {
    "schemaVersion": "1.0",
    "sourceDocument": "source/metadata-coexistence.FCStd",
    "parameterAssignments": [
        {"target": "Parameters.pilotValue", "value": 12.5, "valueKind": "float"}
    ],
    "partMutations": {
        "metadata": [
            {
                "object": "MetadataBody",
                "property": "mass",
                "value": 12.5,
                "valueKind": "number",
            },
            {
                "object": "MetadataBody",
                "property": "material",
                "value": "S235JR",
                "valueKind": "string",
            },
            {
                "object": "MetadataBody",
                "property": "revision",
                "value": 7,
                "valueKind": "integer",
            },
            {
                "object": "MetadataBody",
                "property": "sequence",
                "value": 20,
                "valueKind": "integer",
            },
            {
                "object": "MetadataBody",
                "property": "tagged",
                "value": True,
                "valueKind": "boolean",
            },
            {
                "object": "MetadataBody",
                "property": "tolerance",
                "value": 0.75,
                "valueKind": "number",
            },
        ],
        "suppression": [{"object": "Pad", "suppressed": True}],
        "visibility": [{"object": "MetadataBody", "visible": False}],
        "deletion": [{"object": "DeletionMarker"}],
    },
    "outputs": [],
}

EXPECTED_OBSERVATION_CONTEXT = {
    "parameters": [
        {
            "id": "par.root.varset.pilotValue",
            "name": "pilotValue",
            "groupName": "Parameters",
        }
    ],
    "targetState": {
        "existence": [{"destination": "part", "object": "DeletionMarker"}],
        "suppression": [{"destination": "part", "object": "Pad"}],
        "visibility": [{"destination": "part", "object": "MetadataBody"}],
    },
}

EXPECTED_EXPECTED_METADATA = [
    {
        "key": "working_copy_sha256",
        "value": FIXTURE_SHA256,
    },
    {
        "id": "meta.enclosure.mass",
        "key": "mass",
        "ownerId": "MetadataBody",
        "value": 12.5,
        "valueKind": "number",
    },
    {
        "id": "meta.enclosure.material",
        "key": "material",
        "ownerId": "MetadataBody",
        "value": "S235JR",
        "valueKind": "string",
    },
    {
        "id": "meta.enclosure.revision",
        "key": "revision",
        "ownerId": "MetadataBody",
        "value": 7,
        "valueKind": "integer",
    },
    {
        "id": "meta.enclosure.sequence",
        "key": "sequence",
        "ownerId": "MetadataBody",
        "value": 20,
        "valueKind": "integer",
    },
    {
        "id": "meta.enclosure.tagged",
        "key": "tagged",
        "ownerId": "MetadataBody",
        "value": True,
        "valueKind": "boolean",
    },
    {
        "id": "meta.enclosure.tolerance",
        "key": "tolerance",
        "ownerId": "MetadataBody",
        "value": 0.75,
        "valueKind": "number",
    },
]

EXPECTED_OBSERVED_METADATA = [
    {
        "id": "working_copy_sha256",
        "key": "working_copy_sha256",
        "ownerId": "workingCopy",
        "value": FIXTURE_SHA256,
        "valueKind": "string",
    },
    {
        "id": "meta.enclosure.mass",
        "key": "mass",
        "ownerId": "MetadataBody",
        "value": 12.5,
        "valueKind": "number",
    },
    {
        "id": "meta.enclosure.material",
        "key": "material",
        "ownerId": "MetadataBody",
        "value": "S235JR",
        "valueKind": "string",
    },
    {
        "id": "meta.enclosure.revision",
        "key": "revision",
        "ownerId": "MetadataBody",
        "value": 7,
        "valueKind": "integer",
    },
    {
        "id": "meta.enclosure.sequence",
        "key": "sequence",
        "ownerId": "MetadataBody",
        "value": 20,
        "valueKind": "integer",
    },
    {
        "id": "meta.enclosure.tagged",
        "key": "tagged",
        "ownerId": "MetadataBody",
        "value": True,
        "valueKind": "boolean",
    },
    {
        "id": "meta.enclosure.tolerance",
        "key": "tolerance",
        "ownerId": "MetadataBody",
        "value": 0.75,
        "valueKind": "number",
    },
]

EXPECTED_OBSERVED_PARAMETERS = [
    {
        "groupId": "Parameters",
        "id": "par.root.varset.pilotValue",
        "name": "pilotValue",
        "value": 12.5,
        "valueKind": "number",
    }
]

EXPECTED_TARGET_STATE = {
    "existence": [
        {
            "destination": "part",
            "object": "DeletionMarker",
            "status": "absent",
        }
    ],
    "suppression": [
        {
            "destination": "part",
            "object": "Pad",
            "status": "observed",
            "value": True,
        }
    ],
    "visibility": [
        {
            "destination": "part",
            "object": "MetadataBody",
            "status": "observed",
            "value": False,
        }
    ],
}

EXPECTED_MUTATED_METADATA = {
    "material": {
        "present": True,
        "typeId": "App::PropertyString",
        "value": "S235JR",
    },
    "tagged": {
        "present": True,
        "typeId": "App::PropertyBool",
        "value": True,
    },
    "mass": {
        "present": True,
        "typeId": "App::PropertyFloat",
        "value": 12.5,
    },
    "revision": {
        "present": True,
        "typeId": "App::PropertyInteger",
        "value": 7,
    },
    "tolerance": {
        "present": True,
        "typeId": "App::PropertyFloatConstraint",
        "value": 0.75,
    },
    "sequence": {
        "present": True,
        "typeId": "App::PropertyIntegerConstraint",
        "value": 20,
    },
    "measured_length": {
        "present": True,
        "typeId": "App::PropertyLength",
        "value": 12.5,
    },
}

EXPECTED_BASELINE_METADATA = {
    "material": {
        "present": True,
        "typeId": "App::PropertyString",
        "value": "PLA",
    },
    "tagged": {
        "present": True,
        "typeId": "App::PropertyBool",
        "value": False,
    },
    "mass": {
        "present": True,
        "typeId": "App::PropertyFloat",
        "value": 1.5,
    },
    "revision": {
        "present": True,
        "typeId": "App::PropertyInteger",
        "value": 1,
    },
    "tolerance": {
        "present": True,
        "typeId": "App::PropertyFloatConstraint",
        "value": 0.5,
    },
    "sequence": {
        "present": True,
        "typeId": "App::PropertyIntegerConstraint",
        "value": 10,
    },
    "measured_length": {
        "present": True,
        "typeId": "App::PropertyLength",
        "value": 12.5,
    },
}

EXPECTED_METADATA_GROUP_PROPERTIES = sorted(EXPECTED_MUTATED_METADATA)
EXPECTED_BODY_SHAPE = {"isNull": False, "isValid": True, "solidCount": 1}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MetadataMutationEngineContractTests(unittest.TestCase):
    """Locks the Engine-authored contracts and their semantic expectations."""

    def test_committed_contract_and_fixture_hashes(self) -> None:
        self.assertEqual(_sha256(FIXTURE_PATH), FIXTURE_SHA256)
        self.assertEqual(_sha256(SOURCE_FIXTURE_PATH), SOURCE_FIXTURE_SHA256)
        self.assertEqual(_sha256(MANIFEST_PATH), MANIFEST_SHA256)
        self.assertEqual(_sha256(VERIFICATION_PATH), VERIFICATION_SHA256)

    def test_fixture_is_not_an_lfs_pointer(self) -> None:
        self.assertFalse(
            FIXTURE_PATH.read_bytes().startswith(
                b"version https://git-lfs.github.com/spec/v1"
            ),
            "fixture must be fetched from Git LFS before native tests run",
        )

    def test_manifest_is_the_exact_native_runtime_contract(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(manifest, EXPECTED_MANIFEST)

    def test_manifest_does_not_leak_semantic_target_names(self) -> None:
        text = MANIFEST_PATH.read_text(encoding="utf-8")

        for semantic_name in ("Enclosure", "SacrificialMarker"):
            with self.subTest(semantic_name=semantic_name):
                self.assertNotIn(semantic_name, text)

    def test_verification_request_has_exact_authored_expectations(self) -> None:
        request = json.loads(VERIFICATION_PATH.read_text(encoding="utf-8"))

        self.assertEqual(request["schemaVersion"], "1.0")
        self.assertEqual(
            request["observe"],
            {
                "components": False,
                "parameters": True,
                "metadata": True,
                "references": True,
                "targetState": True,
            },
        )
        self.assertEqual(
            request["observationContext"],
            EXPECTED_OBSERVATION_CONTEXT,
        )
        self.assertEqual(
            request["expected"]["metadata"],
            EXPECTED_EXPECTED_METADATA,
        )
        self.assertEqual(
            request["expected"]["parameters"],
            [
                {
                    "id": "par.root.varset.pilotValue",
                    "name": "pilotValue",
                    "type": "number",
                    "unit": "mm",
                    "value": 12.5,
                }
            ],
        )
        self.assertEqual(request["expected"]["components"], [])
        self.assertEqual(
            request["checks"],
            {
                "components": {"enabled": False},
                "parameters": {"enabled": True},
                "metadata": {"enabled": True},
                "references": {"enabled": True},
            },
        )

    def test_verification_reference_is_engine_materialization_snapshot(self) -> None:
        request = json.loads(VERIFICATION_PATH.read_text(encoding="utf-8"))
        references = request["expected"]["references"]

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0]["kind"], "working_copy_path")
        self.assertTrue(Path(references[0]["name"]).is_absolute())


class _RealFreeCADLifecycleTestCase(unittest.TestCase):
    """Shared real-freecadcmd lifecycle plumbing."""

    @classmethod
    def setUpClass(cls) -> None:
        configured_host = os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd")
        cls.freecad_host = shutil.which(configured_host)
        if cls.freecad_host is None:
            message = (
                f"FreeCAD host {configured_host!r} unavailable outside the Nix shell"
            )
            if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
                raise AssertionError(message)
            raise unittest.SkipTest(message)
        cls.committed_digests = {
            path: _sha256(path)
            for path in (
                FIXTURE_PATH,
                SOURCE_FIXTURE_PATH,
                MANIFEST_PATH,
                VERIFICATION_PATH,
            )
        }

    @classmethod
    def tearDownClass(cls) -> None:
        for path, expected in cls.committed_digests.items():
            actual = _sha256(path)
            if actual != expected:
                raise AssertionError(f"committed asset changed during tests: {path}")

    def _new_root(self, temporary: str, label: str) -> Path:
        root = Path(temporary) / label
        (root / "source").mkdir(parents=True)
        (root / "outputs").mkdir()
        shutil.copyfile(
            FIXTURE_PATH,
            root / "source" / FIXTURE_PATH.name,
        )
        return root

    def _prepare_execute_root(self, temporary: str, label: str) -> Path:
        root = self._new_root(temporary, label)
        shutil.copyfile(MANIFEST_PATH, root / "prm.export-manifest.json")
        shutil.copyfile(VERIFICATION_PATH, root / "prm.verification.json")
        return root

    def _prepare_failure_root(
        self,
        temporary: str,
        label: str,
        entry: dict[str, object],
    ) -> Path:
        root = self._new_root(temporary, label)
        manifest = {
            "schemaVersion": "1.0",
            "sourceDocument": "source/metadata-coexistence.FCStd",
            "parameterAssignments": [],
            "outputs": [],
            "partMutations": {"metadata": [entry]},
        }
        (root / "prm.export-manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        return root

    def _run(self, root: Path, mode: str) -> dict[str, object]:
        summary_path = root / "summary.json"
        if summary_path.exists():
            summary_path.unlink()
        completed = subprocess.run(
            [
                self.freecad_host,
                "-P",
                str(REPOSITORY_ROOT),
                str(RUNNER),
                f"--pass={root}",
                f"--pass={mode}",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertNotIn(
            "Exception while processing file",
            completed.stderr,
            completed.stderr,
        )
        self.assertTrue(
            summary_path.is_file(),
            completed.stderr + completed.stdout,
        )
        return json.loads(summary_path.read_text(encoding="utf-8"))

    def _assert_baseline_native(self, native: dict[str, object]) -> None:
        self.assertEqual(native["metadata"], EXPECTED_BASELINE_METADATA)
        self.assertEqual(native["bodyShape"], EXPECTED_BODY_SHAPE)
        self.assertTrue(native["bodyVisibility"])
        self.assertFalse(native["padSuppressed"])
        self.assertEqual(native["parameterValue"], 10.0)
        self.assertTrue(native["markerPresent"])
        self.assertFalse(native["supplierPresent"])
        self.assertEqual(native["sketchReadOnlyValue"], 1)
        self.assertEqual(
            native["metadataGroupProperties"],
            EXPECTED_METADATA_GROUP_PROPERTIES,
        )


class MetadataMutationRealLifecycleTests(_RealFreeCADLifecycleTestCase):
    """Proves the positive metadata mutation and observation lifecycle."""

    def test_complete_metadata_coexistence_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._prepare_execute_root(temporary, "execute")
            summary = self._run(root, "execute")

            self.assertIsNone(summary["error"])
            self.assertEqual(
                summary["result"],
                {"artifacts": [], "schemaVersion": "1.0", "status": "succeeded"},
            )
            self.assertEqual(summary["sourceDigestBefore"], FIXTURE_SHA256)
            self.assertNotEqual(summary["sourceDigestAfter"], FIXTURE_SHA256)
            self.assertEqual(
                summary["sourceDigestAfter"],
                _sha256(root / "source" / FIXTURE_PATH.name),
            )

            observed = summary["observed"]
            self.assertIsNotNone(observed)
            self.assertEqual(observed["schemaVersion"], "1.0")
            self.assertEqual(
                observed["workingCopy"],
                {"path": str(root), "sha256": FIXTURE_SHA256},
            )
            self.assertEqual(
                observed["observation"]["metadata"],
                EXPECTED_OBSERVED_METADATA,
            )
            self.assertEqual(
                observed["observation"]["parameters"],
                EXPECTED_OBSERVED_PARAMETERS,
            )
            self.assertEqual(
                observed["observation"]["targetState"],
                EXPECTED_TARGET_STATE,
            )
            self.assertEqual(
                observed["observation"]["references"],
                [{"kind": "working_copy_path", "name": str(root)}],
            )

            native = summary["native"]
            self.assertEqual(native["metadata"], EXPECTED_MUTATED_METADATA)
            self.assertEqual(native["bodyShape"], EXPECTED_BODY_SHAPE)
            self.assertFalse(native["bodyVisibility"])
            self.assertTrue(native["padSuppressed"])
            self.assertEqual(native["parameterValue"], 12.5)
            self.assertFalse(native["markerPresent"])
            self.assertFalse(native["supplierPresent"])
            self.assertEqual(native["sketchReadOnlyValue"], 1)
            self.assertEqual(
                native["metadataGroupProperties"],
                EXPECTED_METADATA_GROUP_PROPERTIES,
            )
            for name in EXPECTED_METADATA_GROUP_PROPERTIES:
                self.assertIn(name, native["bodyProperties"])

        self.assertEqual(_sha256(FIXTURE_PATH), FIXTURE_SHA256)

    def test_repeated_execution_produces_equivalent_normalized_evidence(self) -> None:
        outcomes = []
        for label in ("first", "second"):
            with tempfile.TemporaryDirectory() as temporary:
                root = self._prepare_execute_root(temporary, label)
                summary = self._run(root, "execute")
                observed = summary["observed"]
                outcomes.append(
                    {
                        "result": summary["result"],
                        "metadata": observed["observation"]["metadata"],
                        "parameters": observed["observation"]["parameters"],
                        "targetState": observed["observation"]["targetState"],
                        "workingCopySha256": observed["workingCopy"]["sha256"],
                        "native": summary["native"],
                        "sourceDigestBefore": summary["sourceDigestBefore"],
                    }
                )

        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(
            outcomes[0]["metadata"],
            EXPECTED_OBSERVED_METADATA,
        )
        self.assertEqual(
            outcomes[0]["sourceDigestBefore"],
            FIXTURE_SHA256,
        )


class MetadataMutationRealFailureTests(_RealFreeCADLifecycleTestCase):
    """Proves deterministic native metadata failures on the committed fixture."""

    def _assert_metadata_failure(
        self,
        summary: dict[str, object],
        *,
        cause_type: str,
        message_substring: str,
    ) -> None:
        self.assertEqual(
            summary["result"]["status"],
            "failed",
        )
        failure = summary["result"]["failure"]
        self.assertEqual(failure["stage"], "metadata")
        self.assertEqual(failure["boundary"], "execution_entrypoint")
        self.assertEqual(failure["code"], "runtime_failure")
        self.assertIn(message_substring, failure["message"])

        self.assertEqual(summary["error"]["type"], "ExecutionEntrypointError")
        self.assertEqual(summary["error"]["causeType"], cause_type)
        self.assertEqual(summary["sourceDigestBefore"], FIXTURE_SHA256)
        self.assertEqual(summary["sourceDigestAfter"], FIXTURE_SHA256)
        self.assertIsNone(summary["observed"])
        self._assert_baseline_native(summary["native"])

    def test_missing_property_fails_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._prepare_failure_root(
                temporary,
                "missing",
                {
                    "object": "MetadataBody",
                    "property": "supplier",
                    "value": "ACME",
                    "valueKind": "string",
                },
            )
            summary = self._run(root, "failure")

        self._assert_metadata_failure(
            summary,
            cause_type="MetadataMutationPropertyNotFoundError",
            message_substring="supplier",
        )
        self.assertFalse(summary["native"]["supplierPresent"])
        self.assertNotIn("supplier", summary["native"]["bodyProperties"])

    def test_unsupported_native_type_fails_predictably(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._prepare_failure_root(
                temporary,
                "unsupported",
                {
                    "object": "MetadataBody",
                    "property": "measured_length",
                    "value": 15.0,
                    "valueKind": "number",
                },
            )
            summary = self._run(root, "failure")

        self._assert_metadata_failure(
            summary,
            cause_type="MetadataMutationUnsupportedPropertyTypeError",
            message_substring="App::PropertyLength",
        )
        self.assertEqual(
            summary["native"]["metadata"]["measured_length"]["value"],
            12.5,
        )

    def test_read_only_property_fails_predictably(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._prepare_failure_root(
                temporary,
                "read-only",
                {
                    "object": "ProfileSketch",
                    "property": "_ExternalGeoVersion",
                    "value": 2,
                    "valueKind": "integer",
                },
            )
            summary = self._run(root, "failure")

        self._assert_metadata_failure(
            summary,
            cause_type="MetadataMutationNotWritableError",
            message_substring="not writable",
        )
        self.assertEqual(summary["native"]["sketchReadOnlyValue"], 1)

    def test_value_kind_mismatch_fails_predictably(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._prepare_failure_root(
                temporary,
                "mismatch",
                {
                    "object": "MetadataBody",
                    "property": "revision",
                    "value": "seven",
                    "valueKind": "string",
                },
            )
            summary = self._run(root, "failure")

        self._assert_metadata_failure(
            summary,
            cause_type="MetadataMutationValueKindMismatchError",
            message_substring="incompatible",
        )
        self.assertEqual(
            summary["native"]["metadata"]["revision"]["value"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
