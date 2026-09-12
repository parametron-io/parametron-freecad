from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from parametron_freecad.common.canonical_json import (
    dumps_canonical,
    write_canonical_json,
)


class CanonicalJsonTests(unittest.TestCase):
    def test_dumps_canonical_sorts_top_level_keys_and_appends_one_newline(
        self,
    ) -> None:
        value = {"b": 1, "a": 2}

        result = dumps_canonical(value)

        self.assertEqual(result, '{"a":2,"b":1}\n')
        self.assertTrue(result.endswith("\n"))
        self.assertFalse(result.endswith("\n\n"))

    def test_dumps_canonical_sorts_nested_dictionary_keys(self) -> None:
        value = {
            "z": {"b": 1, "a": 2},
            "a": {"d": 4, "c": 3},
        }

        result = dumps_canonical(value)

        self.assertEqual(result, '{"a":{"c":3,"d":4},"z":{"a":2,"b":1}}\n')

    def test_dumps_canonical_preserves_list_order(self) -> None:
        value = {"items": [{"b": 2, "a": 1}, 3, 2, 1]}

        result = dumps_canonical(value)

        self.assertEqual(result, '{"items":[{"a":1,"b":2},3,2,1]}\n')

    def test_dumps_canonical_uses_compact_separators(self) -> None:
        value = {"outer": {"alpha": 1, "beta": [1, 2]}}

        result = dumps_canonical(value)

        self.assertEqual(result, '{"outer":{"alpha":1,"beta":[1,2]}}\n')
        self.assertNotIn(": ", result)
        self.assertNotIn(", ", result)

    def test_dumps_canonical_preserves_non_ascii_unescaped(self) -> None:
        value = {"message": "çağrı 東京"}

        result = dumps_canonical(value)

        self.assertEqual(result, '{"message":"çağrı 東京"}\n')
        self.assertNotIn("\\u", result)

    def test_write_canonical_json_writes_utf8_bytes_matching_dumps(
        self,
    ) -> None:
        value = {"message": "çağrı 東京", "value": 7}

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"

            write_canonical_json(path, value)

            self.assertEqual(
                path.read_bytes(),
                dumps_canonical(value).encode("utf-8"),
            )

    def test_repeated_writes_produce_identical_bytes(self) -> None:
        value = {"b": [3, 2, 1], "a": {"y": "yes", "x": "no"}}

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"

            write_canonical_json(path, value)
            first = path.read_bytes()

            write_canonical_json(path, value)
            second = path.read_bytes()

            self.assertEqual(first, second)

    def test_writing_existing_file_replaces_stale_content(self) -> None:
        value = {"a": 1}

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"
            path.write_text("stale data\nwith extra lines\n", encoding="utf-8")

            write_canonical_json(path, value)

            self.assertEqual(path.read_text(encoding="utf-8"), '{"a":1}\n')

    def test_unsupported_values_raise_type_error(self) -> None:
        class UnsupportedValue:
            pass

        with self.assertRaises(TypeError):
            dumps_canonical({"value": UnsupportedValue()})

    def test_serialization_does_not_mutate_input(self) -> None:
        value = {
            "b": [
                {"y": 2, "x": 1},
                {"nested": ["first", {"beta": 2, "alpha": 1}]},
            ],
            "a": {"delta": [3, 2, 1], "charlie": {"two": 2, "one": 1}},
        }
        original = copy.deepcopy(value)

        dumps_canonical(value)

        self.assertEqual(value, original)


if __name__ == "__main__":
    unittest.main()
