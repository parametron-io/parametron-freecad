"""Controlled-failure coverage for malformed verification contracts.

This is a test-only consolidation that proves malformed verification contract
inputs fail deterministically through the existing Phase 2 observation
boundaries without:

* writing observed output,
* accessing document state before request validation should fail,
* performing component observation,
* traversing ``document.Objects`` or doing Label lookup, or
* making any verification decision.

Three boundaries are covered:

1. The strict verification loader
   (``load_parametron_verification_v1``) for malformed on-disk
   ``parametron.verification.json`` files.
2. The already-decoded requested-scope boundary
   (``observe_requested_contract_scope``).
3. The runtime observed-output boundary
   (``generate_observed_output``).

All tests run under ordinary Python and never require FreeCAD.
"""

from __future__ import annotations

import copy
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


LOADER_MODULE = "parametron_freecad.observation.verification_loader"
SCOPE_MODULE = "parametron_freecad.observation.requested_scope_observation"
OUTPUT_MODULE = "parametron_freecad.observation.observed_output"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeObject:
    """Minimal fake document object exposing arbitrary properties."""

    def __init__(self, **properties):
        for name, value in properties.items():
            setattr(self, name, value)


class NoAccessDocument:
    """Document that fails loudly on ANY document-access surface.

    Used to prove that malformed request validation fails *before* any document
    access occurs. Reaching ``getObject``, ``Objects`` or ``Label`` raises an
    ``AssertionError`` which the observation boundaries do not catch, so it would
    surface as an unexpected error rather than the expected typed failure.
    """

    @property
    def Objects(self):  # noqa: N802 - mimic FreeCAD attribute name
        raise AssertionError("document.Objects must not be traversed")

    @property
    def Label(self):  # noqa: N802 - mimic FreeCAD attribute name
        raise AssertionError("document Label lookup must not be used")

    def getObject(self, name):  # noqa: N802 - mimic FreeCAD method name
        raise AssertionError(
            f"document.getObject({name!r}) must not be called before "
            "request validation failure"
        )


# ---------------------------------------------------------------------------
# Section 1 — Strict verification loader malformed-file failures
# ---------------------------------------------------------------------------


class _LoaderControlledFailureBase(unittest.TestCase):
    """Shared setup for loader controlled-failure tests."""

    def setUp(self):
        self.vl = importlib.import_module(LOADER_MODULE)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _write(self, content: str) -> Path:
        path = self.tmp / "parametron.verification.json"
        path.write_text(content, encoding="utf-8")
        return path

    def _load(self, content: str):
        return self.vl.load_parametron_verification_v1(self._write(content))


class TestLoaderMalformedContractFailures(_LoaderControlledFailureBase):
    """Malformed verification contract files fail with deterministic typed errors."""

    def test_malformed_json_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load("{not valid json")

    def test_truncated_json_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load('{"observe": {"parameters": true')

    def test_duplicate_keys_at_root_raise_duplicate_key_error(self):
        with self.assertRaises(self.vl.VerificationDuplicateKeyError):
            self._load('{"observe": {}, "observe": {}}')

    def test_duplicate_keys_nested_in_object_raise_duplicate_key_error(self):
        with self.assertRaises(self.vl.VerificationDuplicateKeyError):
            self._load('{"observe": {"parameters": true, "parameters": false}}')

    def test_duplicate_keys_inside_array_object_raise_duplicate_key_error(self):
        with self.assertRaises(self.vl.VerificationDuplicateKeyError):
            self._load(
                '{"expected": {"parameters": [{"id": "a", "id": "b"}]}}'
            )

    def test_nan_constant_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load('{"expected": {"parameters": [{"value": NaN}]}}')

    def test_infinity_constant_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load('{"expected": {"parameters": [{"value": Infinity}]}}')

    def test_negative_infinity_constant_raises_decode_error(self):
        with self.assertRaises(self.vl.VerificationDecodeError):
            self._load('{"expected": {"parameters": [{"value": -Infinity}]}}')

    def test_array_root_raises_root_type_error(self):
        with self.assertRaises(self.vl.VerificationRootTypeError):
            self._load("[]")

    def test_string_root_raises_root_type_error(self):
        with self.assertRaises(self.vl.VerificationRootTypeError):
            self._load('"observe"')

    def test_number_root_raises_root_type_error(self):
        with self.assertRaises(self.vl.VerificationRootTypeError):
            self._load("3.14")

    def test_boolean_root_raises_root_type_error(self):
        with self.assertRaises(self.vl.VerificationRootTypeError):
            self._load("true")

    def test_null_root_raises_root_type_error(self):
        with self.assertRaises(self.vl.VerificationRootTypeError):
            self._load("null")

    def test_all_malformed_inputs_are_verification_load_errors(self):
        malformed_inputs = (
            "{not valid json",
            '{"observe": {"parameters": true',
            '{"observe": {}, "observe": {}}',
            '{"observe": {"parameters": true, "parameters": false}}',
            '{"expected": {"parameters": [{"id": "a", "id": "b"}]}}',
            '{"value": NaN}',
            '{"value": Infinity}',
            '{"value": -Infinity}',
            "[]",
            '"observe"',
            "3.14",
            "true",
            "null",
        )
        for content in malformed_inputs:
            with self.subTest(content=content):
                with self.assertRaises(self.vl.VerificationLoadError):
                    self._load(content)


class TestLoaderFailureDeterminism(_LoaderControlledFailureBase):
    """Loader failures are deterministic across repeated calls on the same input."""

    def test_decode_failure_is_repeatable(self):
        path = self._write("{not valid json")
        for _ in range(3):
            with self.assertRaises(self.vl.VerificationDecodeError):
                self.vl.load_parametron_verification_v1(path)

    def test_duplicate_key_failure_is_repeatable(self):
        path = self._write('{"observe": {}, "observe": {}}')
        for _ in range(3):
            with self.assertRaises(self.vl.VerificationDuplicateKeyError):
                self.vl.load_parametron_verification_v1(path)

    def test_root_type_failure_is_repeatable(self):
        path = self._write("[]")
        for _ in range(3):
            with self.assertRaises(self.vl.VerificationRootTypeError):
                self.vl.load_parametron_verification_v1(path)


class TestLoaderFailureSideEffects(_LoaderControlledFailureBase):
    """Loader failures require no FreeCAD and write no observed output."""

    def test_loader_failure_does_not_require_freecad(self):
        with self.assertRaises(self.vl.VerificationLoadError):
            self._load("{not valid json")
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_loader_failure_creates_no_observed_output(self):
        observed = self.tmp / "prm.observed.json"
        for content in ("{not valid json", "[]", '{"a": 1, "a": 2}'):
            with self.subTest(content=content):
                with self.assertRaises(self.vl.VerificationLoadError):
                    self._load(content)
                self.assertFalse(observed.exists())

    def test_loader_failure_writes_no_files_beyond_input(self):
        with self.assertRaises(self.vl.VerificationLoadError):
            self._load("{not valid json")
        self.assertEqual(
            sorted(p.name for p in self.tmp.iterdir()),
            ["parametron.verification.json"],
        )


# ---------------------------------------------------------------------------
# Section 2 — Already-decoded malformed verification data at requested scope
# ---------------------------------------------------------------------------


class _ScopeControlledFailureBase(unittest.TestCase):
    """Shared setup for requested-scope controlled-failure tests."""

    def setUp(self):
        self.mod = importlib.import_module(SCOPE_MODULE)
        self.param_mod = importlib.import_module(
            "parametron_freecad.observation.parameter_observation"
        )
        self.meta_mod = importlib.import_module(
            "parametron_freecad.observation.metadata_observation"
        )
        self.ref_mod = importlib.import_module(
            "parametron_freecad.observation.reference_observation"
        )

    def observe(self, document, verification_data):
        return self.mod.observe_requested_contract_scope(document, verification_data)


class TestScopeMalformedTopLevel(_ScopeControlledFailureBase):
    """Malformed top-level decoded contract surfaces fail before document access."""

    def test_non_mapping_verification_data_raises_request_error(self):
        for value in (None, 42, 3.5, "string", [], (), True):
            with self.subTest(value=value):
                with self.assertRaises(
                    self.mod.RequestedScopeObservationRequestError
                ):
                    self.observe(NoAccessDocument(), value)

    def test_non_mapping_observe_raises_request_error(self):
        for value in (None, 42, "string", [], True):
            with self.subTest(value=value):
                with self.assertRaises(
                    self.mod.RequestedScopeObservationRequestError
                ):
                    self.observe(NoAccessDocument(), {"observe": value})

    def test_request_error_is_scope_error_subclass(self):
        self.assertTrue(
            issubclass(
                self.mod.RequestedScopeObservationRequestError,
                self.mod.RequestedScopeObservationError,
            )
        )
        self.assertTrue(
            issubclass(self.mod.RequestedScopeObservationError, ValueError)
        )


class TestScopeMalformedParameterRequest(_ScopeControlledFailureBase):
    """Malformed parameter request shapes fail before document access."""

    def test_observation_context_not_mapping_fails_before_document_access(self):
        data = {
            "observe": {"parameters": True},
            "observationContext": "not-a-mapping",
        }
        with self.assertRaises(self.param_mod.ParameterObservationRequestError):
            self.observe(NoAccessDocument(), data)

    def test_binding_not_mapping_fails_before_document_access(self):
        data = {
            "observe": {"parameters": True},
            "observationContext": {"parameters": ["not-a-binding"]},
        }
        with self.assertRaises(self.param_mod.ParameterObservationRequestError):
            self.observe(NoAccessDocument(), data)

    def test_binding_missing_fields_fails_before_document_access(self):
        data = {
            "observe": {"parameters": True},
            "observationContext": {"parameters": [{"id": "p.length"}]},
        }
        with self.assertRaises(self.param_mod.ParameterObservationRequestError):
            self.observe(NoAccessDocument(), data)


class TestScopeMalformedMetadataRequest(_ScopeControlledFailureBase):
    """Malformed metadata request shapes fail before document access."""

    def test_expected_not_mapping_fails_before_document_access(self):
        data = {
            "observe": {"metadata": True},
            "expected": "not-a-mapping",
        }
        with self.assertRaises(self.meta_mod.MetadataObservationRequestError):
            self.observe(NoAccessDocument(), data)

    def test_metadata_request_not_mapping_fails_before_document_access(self):
        data = {
            "observe": {"metadata": True},
            "expected": {"metadata": ["not-a-request"]},
        }
        with self.assertRaises(self.meta_mod.MetadataObservationRequestError):
            self.observe(NoAccessDocument(), data)

    def test_metadata_request_missing_fields_fails_before_document_access(self):
        data = {
            "observe": {"metadata": True},
            "expected": {"metadata": [{"id": "m.author"}]},
        }
        with self.assertRaises(self.meta_mod.MetadataObservationRequestError):
            self.observe(NoAccessDocument(), data)


class TestScopeMalformedReferenceRequest(_ScopeControlledFailureBase):
    """Malformed reference request shapes fail before document access."""

    def test_expected_not_mapping_fails_before_document_access(self):
        data = {
            "observe": {"references": True},
            "expected": "not-a-mapping",
        }
        with self.assertRaises(self.ref_mod.ReferenceObservationRequestError):
            self.observe(NoAccessDocument(), data)

    def test_reference_request_not_mapping_fails_before_document_access(self):
        data = {
            "observe": {"references": True},
            "expected": {"references": ["not-a-request"]},
        }
        with self.assertRaises(self.ref_mod.ReferenceObservationRequestError):
            self.observe(NoAccessDocument(), data)

    def test_reference_request_missing_fields_fails_before_document_access(self):
        data = {
            "observe": {"references": True},
            "expected": {"references": [{"kind": "constraint"}]},
        }
        with self.assertRaises(self.ref_mod.ReferenceObservationRequestError):
            self.observe(NoAccessDocument(), data)


class TestScopeFailureSideEffects(_ScopeControlledFailureBase):
    """Requested-scope failures write nothing and do not mutate inputs."""

    def _malformed_cases(self):
        return (
            {"observe": "not-a-mapping"},
            {
                "observe": {"parameters": True},
                "observationContext": {"parameters": ["not-a-binding"]},
            },
            {
                "observe": {"metadata": True},
                "expected": {"metadata": [{"id": "m.author"}]},
            },
            {
                "observe": {"references": True},
                "expected": {"references": [{"kind": "constraint"}]},
            },
        )

    def test_scope_failures_write_no_files(self):
        # Each malformed surface raises a typed ValueError subclass; the
        # top-level surface raises RequestedScopeObservationError while the
        # category surfaces raise their own request errors unwrapped.
        for data in self._malformed_cases():
            with self.subTest(data=data):
                with tempfile.TemporaryDirectory() as tmp:
                    with mock.patch(
                        "builtins.open",
                        side_effect=AssertionError("must not open files"),
                    ):
                        with self.assertRaises(ValueError):
                            self.observe(NoAccessDocument(), data)
                    self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_scope_failures_do_not_mutate_input(self):
        for data in self._malformed_cases():
            with self.subTest(data=data):
                before = copy.deepcopy(data)
                with self.assertRaises(ValueError):
                    self.observe(NoAccessDocument(), data)
                self.assertEqual(data, before)


# ---------------------------------------------------------------------------
# Section 3 — Observed-output boundary controlled failure
# ---------------------------------------------------------------------------


class _OutputControlledFailureBase(unittest.TestCase):
    """Shared setup for observed-output controlled-failure tests."""

    _WORKING_COPY_PATH = "/work/model.FCStd"
    _WORKING_COPY_SHA256 = "a" * 64

    def setUp(self):
        self.mod = importlib.import_module(OUTPUT_MODULE)

    def generate(self, document, verification_data, output_directory):
        return self.mod.generate_observed_output(
            document,
            verification_data,
            working_copy_path=self._WORKING_COPY_PATH,
            working_copy_sha256=self._WORKING_COPY_SHA256,
            output_directory=output_directory,
        )

    def observed_path(self, output_directory):
        return self.mod.observed_json_path(output_directory)

    def _malformed_cases(self):
        return (
            "not-a-mapping",
            {"observe": "not-a-mapping"},
            {
                "observe": {"parameters": True},
                "observationContext": {"parameters": ["not-a-binding"]},
            },
        )


class TestOutputBoundaryControlledFailure(_OutputControlledFailureBase):
    """Malformed decoded verification data fails at the observed-output boundary."""

    def test_non_mapping_verification_data_raises_observed_output_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(self.mod.ObservedOutputError):
                self.generate(NoAccessDocument(), "not-a-mapping", tmp)

    def test_non_mapping_observe_raises_observed_output_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(self.mod.ObservedOutputError):
                self.generate(NoAccessDocument(), {"observe": "not-a-mapping"}, tmp)

    def test_malformed_parameter_surface_raises_before_document_access(self):
        data = {
            "observe": {"parameters": True},
            "observationContext": {"parameters": ["not-a-binding"]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(self.mod.ObservedOutputError):
                self.generate(NoAccessDocument(), data, tmp)

    def test_original_error_is_wrapped_as_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                self.generate(NoAccessDocument(), "not-a-mapping", tmp)
            except self.mod.ObservedOutputError as exc:
                self.assertIsNotNone(exc.__cause__)
            else:
                self.fail("ObservedOutputError was not raised")

    def test_observed_output_error_is_value_error(self):
        self.assertTrue(issubclass(self.mod.ObservedOutputError, ValueError))


class TestOutputBoundaryNoWrite(_OutputControlledFailureBase):
    """No parametron.observed.json is written on malformed decoded data."""

    def test_no_observed_file_created_on_failure(self):
        for data in self._malformed_cases():
            with self.subTest(data=data):
                with tempfile.TemporaryDirectory() as tmp:
                    observed = self.observed_path(tmp)
                    with self.assertRaises(self.mod.ObservedOutputError):
                        self.generate(NoAccessDocument(), data, tmp)
                    self.assertFalse(observed.exists())
                    self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_stale_observed_file_not_replaced_with_success_payload(self):
        stale_text = '{"stale": true, "leftover": [1, 2, 3]}\n'
        for data in self._malformed_cases():
            with self.subTest(data=data):
                with tempfile.TemporaryDirectory() as tmp:
                    observed = self.observed_path(tmp)
                    observed.write_text(stale_text, encoding="utf-8")

                    with self.assertRaises(self.mod.ObservedOutputError):
                        self.generate(NoAccessDocument(), data, tmp)

                    self.assertTrue(observed.exists())
                    self.assertEqual(
                        observed.read_text(encoding="utf-8"), stale_text
                    )


class TestOutputBoundaryNoDocumentAccess(_OutputControlledFailureBase):
    """No document access or component observation occurs before validation fails.

    ``NoAccessDocument`` raises ``AssertionError`` from ``getObject``,
    ``Objects`` and ``Label``. Because ``generate_observed_output`` only wraps
    the typed observation errors, any premature document access would surface as
    an uncaught ``AssertionError`` instead of the expected ``ObservedOutputError``.
    """

    def test_failure_surfaces_as_observed_output_error_only(self):
        for data in self._malformed_cases():
            with self.subTest(data=data):
                with tempfile.TemporaryDirectory() as tmp:
                    with self.assertRaises(self.mod.ObservedOutputError):
                        self.generate(NoAccessDocument(), data, tmp)

    def test_components_request_makes_no_decision_and_writes_empty_observation(self):
        # A components-only request is unsupported and intentionally ignored.
        # It must not traverse Objects (NoAccessDocument would raise) and must
        # not make any verification decision; observation stays empty.
        import json

        with tempfile.TemporaryDirectory() as tmp:
            observed = self.observed_path(tmp)
            self.generate(NoAccessDocument(), {"observe": {"components": True}}, tmp)

            decoded = json.loads(observed.read_text(encoding="utf-8"))
            self.assertEqual(decoded["observation"], {})
            self.assertNotIn("components", decoded["observation"])


class TestOutputBoundaryImportSafety(_OutputControlledFailureBase):
    """Controlled failures at the output boundary require no FreeCAD."""

    def test_failure_does_not_require_freecad(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(self.mod.ObservedOutputError):
                self.generate(NoAccessDocument(), "not-a-mapping", tmp)
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)
        self.assertNotIn("freecad", sys.modules)


if __name__ == "__main__":
    unittest.main()
