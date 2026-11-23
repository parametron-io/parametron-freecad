"""Atomic canonical writer tests for the GUI-free capture core."""

from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from capture_support import valid_mapping

from parametron_freecad.capture import (
    CAPTURE_CONTRACT_FILENAME,
    CaptureContractError,
    CaptureDocument,
    CaptureWriteError,
    canonical_capture_bytes,
    write_capture_document,
)


class CaptureWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)
        self.document = CaptureDocument.from_mapping(valid_mapping())

    def _write(self, path: Path, *, overwrite: bool) -> None:
        write_capture_document(path, self.document, overwrite=overwrite)

    def _temporary_files(self) -> list[Path]:
        return sorted(self.directory.glob(".*.tmp"))

    def test_filename_constant_is_the_engine_contract_name(self) -> None:
        self.assertEqual(CAPTURE_CONTRACT_FILENAME, "prm.cad.json")

    def test_writes_new_file_with_canonical_bytes(self) -> None:
        path = self.directory / CAPTURE_CONTRACT_FILENAME

        self._write(path, overwrite=False)

        self.assertEqual(path.read_bytes(), canonical_capture_bytes(self.document))
        self.assertEqual(self._temporary_files(), [])

    def test_accepts_string_path(self) -> None:
        path = self.directory / "capture.json"

        write_capture_document(str(path), self.document, overwrite=False)

        self.assertTrue(path.is_file())

    def test_existing_file_is_not_overwritten_without_explicit_decision(
        self,
    ) -> None:
        path = self.directory / CAPTURE_CONTRACT_FILENAME
        path.write_bytes(b"existing\n")

        with self.assertRaises(CaptureWriteError) as raised:
            self._write(path, overwrite=False)

        self.assertIn("target already exists", str(raised.exception))
        self.assertEqual(path.read_bytes(), b"existing\n")
        self.assertEqual(self._temporary_files(), [])

    def test_explicit_overwrite_replaces_existing_file(self) -> None:
        path = self.directory / CAPTURE_CONTRACT_FILENAME
        path.write_bytes(b"existing\n")

        self._write(path, overwrite=True)

        self.assertEqual(path.read_bytes(), canonical_capture_bytes(self.document))
        self.assertEqual(self._temporary_files(), [])

    def test_overwrite_decision_is_required(self) -> None:
        path = self.directory / CAPTURE_CONTRACT_FILENAME

        with self.assertRaises(TypeError):
            write_capture_document(path, self.document)  # type: ignore[call-arg]

    def test_overwrite_decision_must_be_boolean(self) -> None:
        path = self.directory / CAPTURE_CONTRACT_FILENAME

        with self.assertRaises(TypeError):
            write_capture_document(
                path,
                self.document,
                overwrite=1,  # type: ignore[arg-type]
            )

    def test_invalid_document_creates_no_file_and_no_temporary_file(self) -> None:
        path = self.directory / CAPTURE_CONTRACT_FILENAME
        invalid = dataclasses.replace(self.document, schema_version="2.0")

        with self.assertRaises(CaptureContractError):
            write_capture_document(path, invalid, overwrite=False)

        self.assertFalse(path.exists())
        self.assertEqual(self._temporary_files(), [])

    def test_invalid_document_does_not_replace_existing_file(self) -> None:
        path = self.directory / CAPTURE_CONTRACT_FILENAME
        path.write_bytes(b"existing\n")
        invalid = dataclasses.replace(self.document, schema_version="2.0")

        with self.assertRaises(CaptureContractError):
            write_capture_document(path, invalid, overwrite=True)

        self.assertEqual(path.read_bytes(), b"existing\n")
        self.assertEqual(self._temporary_files(), [])

    def test_missing_parent_directory_is_a_write_error(self) -> None:
        path = self.directory / "missing" / CAPTURE_CONTRACT_FILENAME

        with self.assertRaises(CaptureWriteError) as raised:
            self._write(path, overwrite=False)

        self.assertIn("parent directory does not exist", str(raised.exception))

    def test_directory_destination_is_a_write_error(self) -> None:
        path = self.directory / CAPTURE_CONTRACT_FILENAME
        path.mkdir()

        with self.assertRaises(CaptureWriteError):
            self._write(path, overwrite=True)

        self.assertTrue(path.is_dir())
        self.assertEqual(self._temporary_files(), [])

    def test_repeated_writes_are_byte_identical(self) -> None:
        path = self.directory / CAPTURE_CONTRACT_FILENAME

        self._write(path, overwrite=False)
        first = path.read_bytes()
        self._write(path, overwrite=True)
        second = path.read_bytes()

        self.assertEqual(first, second)

    def test_written_file_revalidates_and_round_trips(self) -> None:
        path = self.directory / CAPTURE_CONTRACT_FILENAME
        self._write(path, overwrite=False)

        written = json.loads(path.read_text(encoding="utf-8"))
        round_tripped = CaptureDocument.from_mapping(written)

        self.assertEqual(
            canonical_capture_bytes(round_tripped),
            canonical_capture_bytes(self.document),
        )


if __name__ == "__main__":
    unittest.main()
