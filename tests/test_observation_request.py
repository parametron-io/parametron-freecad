from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.runtime import observation_request


class ObservationRequestLoaderTests(unittest.TestCase):
    def _write(self, directory: str, content: str) -> Path:
        path = Path(directory) / "observation-request.json"
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_valid_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, '{"observe":{"metadata":true}}')
            self.assertEqual(
                observation_request.load_observation_request(path),
                {"observe": {"metadata": True}},
            )

    def test_malformed_json_is_wrapped_with_original_cause(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, '{"observe":')
            with self.assertRaises(observation_request.ObservationRequestError) as caught:
                observation_request.load_observation_request(path)
        self.assertIsNotNone(caught.exception.__cause__)
        self.assertIn("malformed JSON", str(caught.exception))

    def test_duplicate_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, '{"observe":{},"observe":{}}')
            with self.assertRaisesRegex(
                observation_request.ObservationRequestError, "duplicate object key"
            ):
                observation_request.load_observation_request(path)

    def test_non_standard_json_constants_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, '{"observe":{"metadata":NaN}}')
            with self.assertRaisesRegex(
                observation_request.ObservationRequestError, "malformed JSON constant"
            ):
                observation_request.load_observation_request(path)

    def test_non_object_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "[]")
            with self.assertRaisesRegex(
                observation_request.ObservationRequestError, "root must be a JSON object"
            ):
                observation_request.load_observation_request(path)

    def test_unsupported_request_structure_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, '{"observe":{"unknown":true}}')
            with self.assertRaisesRegex(
                observation_request.ObservationRequestError, "not compatible"
            ):
                observation_request.load_observation_request(path)

    def test_delegates_compatibility_and_does_not_mutate_loaded_data(self) -> None:
        decoded = {"observe": {"metadata": True}, "expected": {"metadata": []}}
        before = copy.deepcopy(decoded)
        loaded = mock.Mock(data=decoded)
        with mock.patch.object(
            observation_request, "load_parametron_verification_v1", return_value=loaded
        ) as load, mock.patch.object(
            observation_request, "require_engine_verification_expectations_compatible"
        ) as compatible:
            result = observation_request.load_observation_request(Path("request.json"))
        load.assert_called_once_with(Path("request.json"))
        compatible.assert_called_once_with(decoded)
        self.assertIs(result, decoded)
        self.assertEqual(decoded, before)

    def test_equivalent_json_inputs_load_to_equal_deterministic_data(self) -> None:
        first = {"observe": {"metadata": True}, "expected": {"metadata": []}}
        second = {"expected": {"metadata": []}, "observe": {"metadata": True}}
        with tempfile.TemporaryDirectory() as tmp:
            path_a = self._write(tmp, json.dumps(first))
            loaded_a = observation_request.load_observation_request(path_a)
            path_b = Path(tmp) / "equivalent.json"
            path_b.write_text(json.dumps(second), encoding="utf-8")
            loaded_b = observation_request.load_observation_request(path_b)
        self.assertEqual(loaded_a, loaded_b)


if __name__ == "__main__":
    unittest.main()
