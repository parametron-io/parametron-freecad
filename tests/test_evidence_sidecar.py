"""Atomic canonical evidence sidecar tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.runtime.evidence_sidecar import (
    EvidenceSidecarContainmentError,
    EvidenceSidecarError,
    EvidenceSidecarWriteError,
    resolve_evidence_sidecar_path,
    write_canonical_json_sidecar_atomically,
)


class EvidenceSidecarTests(unittest.TestCase):
    def _working_copy(self, tmp_dir: str) -> Path:
        working = Path(tmp_dir) / "run" / "_working" / "attempt"
        (working / "outputs").mkdir(parents=True)
        return working

    def test_writes_canonical_payload_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            payload = {"schemaVersion": "1.0", "values": [2, 1]}

            target = write_canonical_json_sidecar_atomically(
                working_copy=working,
                output_directory=working / "outputs",
                filename="prm.evidence.json",
                payload=payload,
            )

            self.assertEqual(target, working / "outputs" / "prm.evidence.json")
            self.assertEqual(
                target.read_bytes(),
                dumps_canonical(payload).encode("utf-8"),
            )
            self.assertEqual(
                sorted(path.name for path in (working / "outputs").iterdir()),
                ["prm.evidence.json"],
            )

    def test_relative_output_directory_resolves_inside_working_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)

            target = write_canonical_json_sidecar_atomically(
                working_copy=working,
                output_directory="outputs",
                filename="prm.evidence.json",
                payload={"a": 1},
            )

            self.assertEqual(target, working / "outputs" / "prm.evidence.json")

    def test_missing_output_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)

            with self.assertRaisesRegex(
                EvidenceSidecarContainmentError,
                "output directory must be an existing directory",
            ):
                resolve_evidence_sidecar_path(
                    working_copy=working,
                    output_directory=working / "missing",
                    filename="prm.evidence.json",
                )

    def test_output_directory_outside_working_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            outside = Path(tmp_dir) / "outside"
            outside.mkdir()

            with self.assertRaisesRegex(
                EvidenceSidecarContainmentError,
                "output directory must resolve inside the working copy",
            ):
                resolve_evidence_sidecar_path(
                    working_copy=working,
                    output_directory=outside,
                    filename="prm.evidence.json",
                )

    def test_output_directory_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            outside = Path(tmp_dir) / "outside"
            outside.mkdir()
            link = working / "linked-output"
            link.symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(
                EvidenceSidecarContainmentError,
                "output directory must resolve inside the working copy",
            ):
                resolve_evidence_sidecar_path(
                    working_copy=working,
                    output_directory=link,
                    filename="prm.evidence.json",
                )

    def test_sidecar_filename_must_be_plain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            for filename in ("", " ", "../prm.evidence.json", "nested/prm.json", ".."):
                with self.subTest(filename=filename):
                    with self.assertRaisesRegex(
                        EvidenceSidecarContainmentError,
                        "plain file name",
                    ):
                        resolve_evidence_sidecar_path(
                            working_copy=working,
                            output_directory=working / "outputs",
                            filename=filename,
                        )

    def test_existing_directory_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            target = working / "outputs" / "prm.evidence.json"
            target.mkdir()

            with self.assertRaisesRegex(
                EvidenceSidecarContainmentError,
                "must not be an existing directory",
            ):
                resolve_evidence_sidecar_path(
                    working_copy=working,
                    output_directory=working / "outputs",
                    filename="prm.evidence.json",
                )

    def test_atomic_replacement_overwrites_existing_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)
            target = working / "outputs" / "prm.evidence.json"
            target.write_bytes(b"stale")

            write_canonical_json_sidecar_atomically(
                working_copy=working,
                output_directory=working / "outputs",
                filename="prm.evidence.json",
                payload={"a": "new"},
            )

            self.assertEqual(
                target.read_bytes(), dumps_canonical({"a": "new"}).encode()
            )
            self.assertEqual(
                sorted(path.name for path in (working / "outputs").iterdir()),
                ["prm.evidence.json"],
            )

    def test_write_failure_is_wrapped_and_temporary_file_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)

            with mock.patch(
                "parametron_freecad.runtime.evidence_sidecar.os.replace",
                side_effect=OSError("replace failed"),
            ):
                with self.assertRaisesRegex(
                    EvidenceSidecarWriteError,
                    "failed to atomically write evidence sidecar",
                ):
                    write_canonical_json_sidecar_atomically(
                        working_copy=working,
                        output_directory=working / "outputs",
                        filename="prm.evidence.json",
                        payload={"a": 1},
                    )

            self.assertEqual(
                sorted(path.name for path in (working / "outputs").iterdir()),
                [],
            )

    def test_non_serializable_payload_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working = self._working_copy(tmp_dir)

            with self.assertRaisesRegex(
                EvidenceSidecarError,
                "not canonical-JSON serializable",
            ):
                write_canonical_json_sidecar_atomically(
                    working_copy=working,
                    output_directory=working / "outputs",
                    filename="prm.evidence.json",
                    payload={"a": {1, 2}},
                )

    def test_missing_working_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(
                EvidenceSidecarContainmentError,
                "working copy must be an existing directory",
            ):
                resolve_evidence_sidecar_path(
                    working_copy=Path(tmp_dir) / "missing",
                    output_directory=Path(tmp_dir) / "outputs",
                    filename="prm.evidence.json",
                )


if __name__ == "__main__":
    unittest.main()
