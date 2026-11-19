"""Strict JSON decoding tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from parametron_freecad.common.strict_json import (
    StrictJsonError,
    load_strict_json_file,
    loads_strict_json,
)


class StrictJsonDecodeTests(unittest.TestCase):
    def test_valid_object_decodes(self) -> None:
        self.assertEqual(
            loads_strict_json(b'{"a":1,"b":[true,null]}'),
            {"a": 1, "b": [True, None]},
        )

    def test_duplicate_root_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(StrictJsonError, "duplicate JSON object key"):
            loads_strict_json('{"a":1,"a":2}')

    def test_duplicate_nested_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(StrictJsonError, "duplicate JSON object key"):
            loads_strict_json('{"outer":{"a":1,"a":2}}')

    def test_non_standard_constants_are_rejected(self) -> None:
        for content in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(content=content):
                with self.assertRaisesRegex(
                    StrictJsonError, "non-standard JSON constant"
                ):
                    loads_strict_json(content)

    def test_invalid_utf8_is_rejected(self) -> None:
        with self.assertRaisesRegex(StrictJsonError, "valid UTF-8"):
            loads_strict_json(b'{"a":"\xff"}')

    def test_trailing_content_is_rejected(self) -> None:
        with self.assertRaisesRegex(StrictJsonError, "invalid JSON"):
            loads_strict_json('{"a":1}{"b":2}')

    def test_invalid_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(StrictJsonError, "invalid JSON"):
            loads_strict_json("{")

    def test_non_text_content_is_rejected(self) -> None:
        with self.assertRaisesRegex(StrictJsonError, "bytes or text"):
            loads_strict_json(42)  # type: ignore[arg-type]

    def test_file_loader_reads_strict_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "request.json"
            path.write_text('{"schemaVersion":"1.0"}', encoding="utf-8")
            self.assertEqual(
                load_strict_json_file(path),
                {"schemaVersion": "1.0"},
            )

    def test_file_loader_reports_unreadable_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / "missing.json"
            with self.assertRaisesRegex(StrictJsonError, "could not be read"):
                load_strict_json_file(missing)


if __name__ == "__main__":
    unittest.main()
