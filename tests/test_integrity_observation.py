"""Integrity observation tests."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.runtime.evidence_sidecar import EvidenceSidecarWriteError
from parametron_freecad.runtime.integrity_observation import (
    INTEGRITY_EVIDENCE_FILENAME,
    INTEGRITY_STATUS_MISSING,
    INTEGRITY_STATUS_OBSERVED,
    INTEGRITY_STATUS_UNAVAILABLE,
    IntegrityBaselineError,
    IntegrityEvidenceError,
    IntegrityResultError,
    build_integrity_evidence_payload,
    observe_baseline_integrity,
    observe_persisted_result,
    prepare_integrity_observation,
    write_integrity_evidence,
)
from parametron_freecad.runtime.resource_inventory import (
    ResourceBinding,
    ResourceInventory,
)

_PRIMARY_COORDINATE = "source/Assembly.FCStd"
_SECONDARY_COORDINATE = "resources/component/Body.FCStd"
_PRIMARY_BYTES = b"primary-baseline"
_SECONDARY_BYTES = b"secondary-baseline"
_RESULT_BYTES = b"configured-result"


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class _FakeDocument:
    def __init__(self, file_name: str | Path | None) -> None:
        self.FileName = file_name


class IntegrityObservationTests(unittest.TestCase):
    def _inventory(
        self,
        tmp_dir: str,
        *,
        primary_digest: str | None = None,
        secondary_digest: str | None = None,
        secondary_bytes: bytes = _SECONDARY_BYTES,
    ) -> ResourceInventory:
        working = Path(tmp_dir) / "run" / "_working" / "attempt"
        primary = working / _PRIMARY_COORDINATE
        secondary = working / _SECONDARY_COORDINATE
        primary.parent.mkdir(parents=True)
        secondary.parent.mkdir(parents=True)
        primary.write_bytes(_PRIMARY_BYTES)
        secondary.write_bytes(secondary_bytes)

        return ResourceInventory(
            working_copy=working,
            bindings=(
                ResourceBinding(
                    logical_id="assembly",
                    kind="model",
                    materialized_coordinate=_PRIMARY_COORDINATE,
                    baseline_sha256=(
                        _digest(_PRIMARY_BYTES)
                        if primary_digest is None
                        else primary_digest
                    ),
                    expects_persisted_result=True,
                    resolved_path=primary,
                ),
                ResourceBinding(
                    logical_id="component",
                    kind="model",
                    materialized_coordinate=_SECONDARY_COORDINATE,
                    baseline_sha256=(
                        _digest(secondary_bytes)
                        if secondary_digest is None
                        else secondary_digest
                    ),
                    expects_persisted_result=False,
                    resolved_path=secondary,
                ),
            ),
        )

    def _outputs(self, inventory: ResourceInventory) -> Path:
        outputs = inventory.working_copy / "outputs"
        outputs.mkdir()
        return outputs

    def _completed_observation(
        self,
        inventory: ResourceInventory,
    ):
        observation = observe_baseline_integrity(inventory)
        inventory.bindings[0].resolved_path.write_bytes(_RESULT_BYTES)
        return observe_persisted_result(
            observation,
            document=_FakeDocument(inventory.bindings[0].resolved_path),
            opened_path=inventory.bindings[0].resolved_path,
        )

    def test_baseline_observes_primary_and_secondary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)

            observation = observe_baseline_integrity(inventory)

        self.assertEqual(
            tuple(resource.status for resource in observation.resources),
            (INTEGRITY_STATUS_OBSERVED, INTEGRITY_STATUS_OBSERVED),
        )
        self.assertEqual(
            observation.primary.baseline_sha256,
            _digest(_PRIMARY_BYTES),
        )
        self.assertEqual(
            observation.resources[1].baseline_sha256,
            _digest(_SECONDARY_BYTES),
        )
        self.assertIsNone(observation.primary.persisted_result)

    def test_baseline_reports_missing_secondary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            inventory.bindings[1].resolved_path.unlink()

            observation = observe_baseline_integrity(inventory)

        self.assertEqual(observation.resources[1].status, INTEGRITY_STATUS_MISSING)
        self.assertIsNone(observation.resources[1].baseline_sha256)
        self.assertEqual(observation.primary.status, INTEGRITY_STATUS_OBSERVED)

    def test_baseline_reports_unavailable_secondary_when_not_regular(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            secondary = inventory.bindings[1].resolved_path
            secondary.unlink()
            secondary.mkdir()

            observation = observe_baseline_integrity(inventory)

        self.assertEqual(
            observation.resources[1].status,
            INTEGRITY_STATUS_UNAVAILABLE,
        )
        self.assertIsNone(observation.resources[1].baseline_sha256)

    def test_baseline_missing_primary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            inventory.bindings[0].resolved_path.unlink()

            with self.assertRaisesRegex(
                IntegrityBaselineError,
                "selected source resource",
            ):
                observe_baseline_integrity(inventory)

    def test_baseline_non_regular_primary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            primary = inventory.bindings[0].resolved_path
            primary.unlink()
            primary.mkdir()

            with self.assertRaisesRegex(
                IntegrityBaselineError,
                "is not a regular file",
            ):
                observe_baseline_integrity(inventory)

    def test_baseline_primary_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir, primary_digest="0" * 64)

            with self.assertRaisesRegex(
                IntegrityBaselineError,
                "baseline digest mismatch",
            ):
                observe_baseline_integrity(inventory)

    def test_baseline_secondary_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir, secondary_digest="0" * 64)

            with self.assertRaisesRegex(
                IntegrityBaselineError,
                "baseline digest mismatch",
            ):
                observe_baseline_integrity(inventory)

    def test_baseline_primary_hash_failure_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)

            with mock.patch(
                "parametron_freecad.runtime.integrity_observation._sha256_file",
                side_effect=OSError("hash failure"),
            ):
                with self.assertRaisesRegex(
                    IntegrityBaselineError,
                    "could not be hashed",
                ):
                    observe_baseline_integrity(inventory)

    def test_baseline_secondary_hash_failure_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)

            with mock.patch(
                "parametron_freecad.runtime.integrity_observation._sha256_file",
                side_effect=[_digest(_PRIMARY_BYTES), OSError("hash failure")],
            ):
                observation = observe_baseline_integrity(inventory)

        self.assertEqual(observation.primary.status, INTEGRITY_STATUS_OBSERVED)
        self.assertEqual(
            observation.resources[1].status,
            INTEGRITY_STATUS_UNAVAILABLE,
        )

    def test_prepare_removes_stale_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            outputs = self._outputs(inventory)
            stale = outputs / INTEGRITY_EVIDENCE_FILENAME
            stale.write_bytes(b"stale")

            observation = prepare_integrity_observation(
                inventory,
                working_copy=inventory.working_copy,
                output_directory=outputs,
            )

            self.assertFalse(stale.exists())

        self.assertEqual(observation.primary.status, INTEGRITY_STATUS_OBSERVED)

    def test_prepare_requires_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)

            with self.assertRaisesRegex(
                IntegrityEvidenceError,
                "requires an existing output directory",
            ):
                prepare_integrity_observation(
                    inventory,
                    working_copy=inventory.working_copy,
                    output_directory=None,
                )

    def test_prepare_rejects_output_directory_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            outside = Path(tmp_dir) / "outside"
            outside.mkdir()

            with self.assertRaisesRegex(
                IntegrityEvidenceError,
                "destination is not usable",
            ):
                prepare_integrity_observation(
                    inventory,
                    working_copy=inventory.working_copy,
                    output_directory=outside,
                )

    def test_persisted_result_hashes_post_save_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            observation = observe_baseline_integrity(inventory)
            primary = inventory.bindings[0].resolved_path
            primary.write_bytes(_RESULT_BYTES)

            updated = observe_persisted_result(
                observation,
                document=_FakeDocument(primary),
                opened_path=primary,
            )

        result = updated.primary.persisted_result
        self.assertIsNotNone(result)
        self.assertEqual(result.coordinate, _PRIMARY_COORDINATE)
        self.assertEqual(result.sha256, _digest(_RESULT_BYTES))
        self.assertNotEqual(result.sha256, updated.primary.baseline_sha256)
        self.assertEqual(updated.primary.baseline_sha256, _digest(_PRIMARY_BYTES))

    def test_persisted_result_rejects_opened_path_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            observation = observe_baseline_integrity(inventory)

            with self.assertRaisesRegex(
                IntegrityResultError,
                "does not match the requested coordinate",
            ):
                observe_persisted_result(
                    observation,
                    document=_FakeDocument(inventory.bindings[0].resolved_path),
                    opened_path=inventory.bindings[1].resolved_path,
                )

    def test_persisted_result_rejects_document_filename_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            observation = observe_baseline_integrity(inventory)

            with self.assertRaisesRegex(
                IntegrityResultError,
                "saved document path does not match",
            ):
                observe_persisted_result(
                    observation,
                    document=_FakeDocument(inventory.bindings[1].resolved_path),
                    opened_path=inventory.bindings[0].resolved_path,
                )

    def test_persisted_result_rejects_relative_document_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            observation = observe_baseline_integrity(inventory)

            with self.assertRaisesRegex(
                IntegrityResultError,
                "is not absolute",
            ):
                observe_persisted_result(
                    observation,
                    document=_FakeDocument("relative.FCStd"),
                    opened_path=inventory.bindings[0].resolved_path,
                )

    def test_persisted_result_missing_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            observation = observe_baseline_integrity(inventory)
            inventory.bindings[0].resolved_path.unlink()

            with self.assertRaisesRegex(
                IntegrityResultError,
                "is missing",
            ):
                observe_persisted_result(
                    observation,
                    document=_FakeDocument(inventory.bindings[0].resolved_path),
                    opened_path=inventory.bindings[0].resolved_path,
                )

    def test_persisted_result_hash_failure_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            observation = observe_baseline_integrity(inventory)

            with mock.patch(
                "parametron_freecad.runtime.integrity_observation._sha256_file",
                side_effect=OSError("hash failure"),
            ):
                with self.assertRaisesRegex(
                    IntegrityResultError,
                    "could not be hashed",
                ):
                    observe_persisted_result(
                        observation,
                        document=_FakeDocument(inventory.bindings[0].resolved_path),
                        opened_path=inventory.bindings[0].resolved_path,
                    )

    def test_evidence_payload_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            updated = self._completed_observation(inventory)
            payload = build_integrity_evidence_payload(updated)

        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(
            [resource["logicalId"] for resource in payload["resources"]],
            ["assembly", "component"],
        )
        primary, secondary = payload["resources"]
        self.assertEqual(primary["materializedCoordinate"], _PRIMARY_COORDINATE)
        self.assertEqual(primary["status"], "observed")
        self.assertEqual(primary["baselineSha256"], _digest(_PRIMARY_BYTES))
        self.assertEqual(
            primary["persistedResult"],
            {
                "coordinate": _PRIMARY_COORDINATE,
                "sha256": _digest(_RESULT_BYTES),
            },
        )
        self.assertEqual(secondary["materializedCoordinate"], _SECONDARY_COORDINATE)
        self.assertEqual(secondary["status"], "observed")
        self.assertEqual(secondary["baselineSha256"], _digest(_SECONDARY_BYTES))
        self.assertIsNone(secondary["persistedResult"])

    def test_write_evidence_is_canonical_and_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            outputs = self._outputs(inventory)
            updated = self._completed_observation(inventory)

            target = write_integrity_evidence(
                updated,
                working_copy=inventory.working_copy,
                output_directory=outputs,
            )

            self.assertEqual(target, outputs / INTEGRITY_EVIDENCE_FILENAME)
            self.assertEqual(
                target.read_bytes(),
                dumps_canonical(build_integrity_evidence_payload(updated)).encode(),
            )
            self.assertEqual(
                sorted(path.name for path in outputs.iterdir()),
                [INTEGRITY_EVIDENCE_FILENAME],
            )

    def test_write_evidence_requires_completed_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            outputs = self._outputs(inventory)
            observation = observe_baseline_integrity(inventory)

            with self.assertRaisesRegex(
                IntegrityEvidenceError,
                "incomplete",
            ):
                write_integrity_evidence(
                    observation,
                    working_copy=inventory.working_copy,
                    output_directory=outputs,
                )

    def test_write_evidence_wraps_sidecar_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            outputs = self._outputs(inventory)
            updated = self._completed_observation(inventory)

            with mock.patch(
                "parametron_freecad.runtime.integrity_observation."
                "write_canonical_json_sidecar_atomically",
                side_effect=EvidenceSidecarWriteError("write failure"),
            ):
                with self.assertRaisesRegex(
                    IntegrityEvidenceError,
                    "could not be written",
                ):
                    write_integrity_evidence(
                        updated,
                        working_copy=inventory.working_copy,
                        output_directory=outputs,
                    )

    def test_write_evidence_rejects_output_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            outside = Path(tmp_dir) / "outside"
            outside.mkdir()
            updated = self._completed_observation(inventory)

            with self.assertRaisesRegex(
                IntegrityEvidenceError,
                "could not be written",
            ):
                write_integrity_evidence(
                    updated,
                    working_copy=inventory.working_copy,
                    output_directory=outside,
                )

    def test_write_evidence_overwrites_stale_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inventory = self._inventory(tmp_dir)
            outputs = self._outputs(inventory)
            stale = outputs / INTEGRITY_EVIDENCE_FILENAME
            stale.write_bytes(b"stale")
            updated = self._completed_observation(inventory)

            write_integrity_evidence(
                updated,
                working_copy=inventory.working_copy,
                output_directory=outputs,
            )

            self.assertEqual(
                stale.read_bytes(),
                dumps_canonical(build_integrity_evidence_payload(updated)).encode(),
            )


if __name__ == "__main__":
    unittest.main()
