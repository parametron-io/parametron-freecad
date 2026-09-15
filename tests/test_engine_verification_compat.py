"""Tests for Engine-generated verification contract compatibility.

Verifies that the FreeCAD observation runtime accepts minimal Engine-generated
prm.verification.json shapes and emits deterministic observed output for
the requested runtime-context categories without broadening observation behavior.

Coverage:
1. Import safety
2. Minimal Engine verification shape acceptance
3. Runtime-context metadata observation
4. Runtime-context reference observation
5. Disabled parameters (observe.parameters = false)
6. No component observation (observe.components = false)
7. No verification decisions in output
8. Document-backed behavior preserved
9. Mixed runtime-context and document-backed entries
10. Byte-level determinism
11. Error boundaries
"""

from __future__ import annotations

import builtins
import copy
import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import parametron_freecad.observation.engine_verification_compat as evc

# ---------------------------------------------------------------------------
# Module names
# ---------------------------------------------------------------------------

_COMPAT_MODULE = "parametron_freecad.observation.engine_verification_compat"
_OBSERVED_OUTPUT_MODULE = "parametron_freecad.observation.observed_output"

# ---------------------------------------------------------------------------
# Sentinel values — chosen to be clearly distinct from Engine expected values
# ---------------------------------------------------------------------------

_CALLER_SHA256 = "c" * 64
_CALLER_PATH = "/caller/supplied/model.FCStd"

_EXPECTED_ENGINE_SHA256 = "expected-engine-value-in-verification-json"
_EXPECTED_ENGINE_PATH = "/engine/generated/path/to/_working/model.FCStd"


# ---------------------------------------------------------------------------
# Canonical minimal Engine-generated verification shape
# ---------------------------------------------------------------------------


def _engine_verification_data() -> dict:
    """Return a fresh copy of the canonical minimal Engine verification shape."""
    return {
        "schemaVersion": "1.0",
        "observe": {
            "components": False,
            "parameters": False,
            "metadata": True,
            "references": True,
        },
        "observationContext": {
            "parameters": []
        },
        "expected": {
            "components": [],
            "parameters": [],
            "metadata": [
                {
                    "key": "working_copy_sha256",
                    "value": _EXPECTED_ENGINE_SHA256,
                }
            ],
            "references": [
                {
                    "kind": "working_copy_path",
                    "name": _EXPECTED_ENGINE_PATH,
                }
            ],
        },
        "checks": {
            "components": {"enabled": False},
            "parameters": {"enabled": False},
            "metadata": {"enabled": True},
            "references": {"enabled": True},
        },
    }


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class ForbiddenDocument:
    """Fake document where any FreeCAD object access raises AssertionError.

    Proves that Engine runtime-context paths do not touch FreeCAD objects.
    """

    @property
    def Objects(self):  # noqa: N802
        raise AssertionError("document.Objects must not be accessed")

    @property
    def Label(self):  # noqa: N802
        raise AssertionError("document.Label must not be accessed")

    def getObject(self, name):  # noqa: N802
        raise AssertionError(
            f"document.getObject({name!r}) must not be called"
        )


class FakeObject:
    """Minimal fake FreeCAD object with arbitrary properties."""

    def __init__(self, **properties):
        for name, value in properties.items():
            setattr(self, name, value)


class FakeDocument:
    """Fake FreeCAD document with explicit object map.

    Objects and Label raise on access. getObject is allowed only for
    explicitly registered names.
    """

    def __init__(self, objects: dict | None = None):
        self._objects: dict = dict(objects or {})
        self.calls: list[str] = []

    @property
    def Objects(self):  # noqa: N802
        raise AssertionError("document.Objects must not be accessed")

    @property
    def Label(self):  # noqa: N802
        raise AssertionError("document.Label must not be accessed")

    def getObject(self, name):  # noqa: N802
        self.calls.append(name)
        return self._objects.get(name)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _call_adapter(
    document,
    verification_data,
    *,
    working_copy_path=_CALLER_PATH,
    working_copy_sha256=_CALLER_SHA256,
):
    return evc.observe_engine_compatible_requested_scope(
        document,
        verification_data,
        working_copy_path=working_copy_path,
        working_copy_sha256=working_copy_sha256,
    )


def _import_observed_output():
    return importlib.import_module(_OBSERVED_OUTPUT_MODULE)


# ===========================================================================
# 1. Import safety
# ===========================================================================


class ImportSafetyTests(unittest.TestCase):

    def test_module_imports_without_freecad(self) -> None:
        guarded = {"FreeCAD", "FreeCADGui", "freecad"}
        original_import = builtins.__import__
        original_module = sys.modules.get(_COMPAT_MODULE)

        for name in [_COMPAT_MODULE, *guarded]:
            sys.modules.pop(name, None)

        def _restore():
            if original_module is not None:
                sys.modules[_COMPAT_MODULE] = original_module
            else:
                sys.modules.pop(_COMPAT_MODULE, None)

        self.addCleanup(_restore)

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in guarded:
                raise AssertionError(f"{name} must not be imported")
            return original_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = importlib.import_module(_COMPAT_MODULE)

        self.assertIsInstance(module, types.ModuleType)
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_no_freecad_in_sys_modules_after_import(self) -> None:
        importlib.import_module(_COMPAT_MODULE)
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)

    def test_module_exposes_expected_public_surface(self) -> None:
        module = importlib.import_module(_COMPAT_MODULE)
        self.assertTrue(
            callable(getattr(module, "observe_engine_compatible_requested_scope", None))
        )
        self.assertTrue(
            issubclass(
                getattr(module, "EngineVerificationCompatibilityError"),
                ValueError,
            )
        )
        self.assertEqual(
            module.ENGINE_METADATA_KEY_WORKING_COPY_SHA256,
            "working_copy_sha256",
        )
        self.assertEqual(
            module.ENGINE_REFERENCE_KIND_WORKING_COPY_PATH,
            "working_copy_path",
        )


# ===========================================================================
# 2. Minimal Engine verification shape accepted
# ===========================================================================


class MinimalEngineShapeAcceptedTests(unittest.TestCase):

    def test_minimal_engine_shape_completes_without_error(self) -> None:
        result = _call_adapter(ForbiddenDocument(), _engine_verification_data())
        self.assertIsInstance(result, dict)

    def test_minimal_engine_shape_emits_only_metadata_and_references(self) -> None:
        result = _call_adapter(ForbiddenDocument(), _engine_verification_data())
        self.assertIn("metadata", result)
        self.assertIn("references", result)
        self.assertNotIn("parameters", result)
        self.assertNotIn("components", result)

    def test_schema_version_and_checks_not_in_observation_output(self) -> None:
        result = _call_adapter(ForbiddenDocument(), _engine_verification_data())
        self.assertNotIn("schemaVersion", result)
        self.assertNotIn("checks", result)

    def test_engine_shape_with_path_like_working_copy_path(self) -> None:
        result = _call_adapter(
            ForbiddenDocument(),
            _engine_verification_data(),
            working_copy_path=Path("/path/like/model.FCStd"),
        )
        self.assertIn("references", result)
        self.assertEqual(result["references"][0]["name"], "/path/like/model.FCStd")

    def test_full_canonical_shape_including_all_top_level_fields_accepted(
        self,
    ) -> None:
        data = _engine_verification_data()
        result = _call_adapter(ForbiddenDocument(), data)
        self.assertEqual(len(result.get("metadata", ())), 1)
        self.assertEqual(len(result.get("references", ())), 1)


# ===========================================================================
# 3. Runtime-context metadata observation
# ===========================================================================


class RuntimeContextMetadataTests(unittest.TestCase):

    def _observe(self, **kwargs):
        return _call_adapter(
            ForbiddenDocument(), _engine_verification_data(), **kwargs
        )

    def test_one_metadata_entry_emitted(self) -> None:
        result = self._observe()
        self.assertEqual(len(result["metadata"]), 1)

    def test_metadata_key_is_working_copy_sha256(self) -> None:
        self.assertEqual(self._observe()["metadata"][0]["key"], "working_copy_sha256")

    def test_metadata_id_is_working_copy_sha256(self) -> None:
        self.assertEqual(self._observe()["metadata"][0]["id"], "working_copy_sha256")

    def test_metadata_owner_id_is_workingcopy(self) -> None:
        self.assertEqual(self._observe()["metadata"][0]["ownerId"], "workingCopy")

    def test_metadata_value_kind_is_string(self) -> None:
        self.assertEqual(self._observe()["metadata"][0]["valueKind"], "string")

    def test_metadata_value_comes_from_caller_sha256(self) -> None:
        result = self._observe(working_copy_sha256="caller-abc123")
        self.assertEqual(result["metadata"][0]["value"], "caller-abc123")

    def test_metadata_value_differs_from_expected_sha256(self) -> None:
        result = self._observe(working_copy_sha256="caller-abc123")
        self.assertNotEqual(result["metadata"][0]["value"], _EXPECTED_ENGINE_SHA256)

    def test_metadata_fields_in_observed_contract_order(self) -> None:
        result = self._observe()
        self.assertEqual(
            list(result["metadata"][0].keys()),
            ["id", "key", "ownerId", "value", "valueKind"],
        )

    def test_different_caller_sha256_changes_observed_value(self) -> None:
        a = _call_adapter(
            ForbiddenDocument(),
            _engine_verification_data(),
            working_copy_sha256="sha-a" * 12,
        )
        b = _call_adapter(
            ForbiddenDocument(),
            _engine_verification_data(),
            working_copy_sha256="sha-b" * 12,
        )
        self.assertNotEqual(a["metadata"][0]["value"], b["metadata"][0]["value"])


# ===========================================================================
# 4. Runtime-context reference observation
# ===========================================================================


class RuntimeContextReferenceTests(unittest.TestCase):

    def _observe(self, **kwargs):
        return _call_adapter(
            ForbiddenDocument(), _engine_verification_data(), **kwargs
        )

    def test_one_reference_entry_emitted(self) -> None:
        self.assertEqual(len(self._observe()["references"]), 1)

    def test_reference_kind_is_working_copy_path(self) -> None:
        self.assertEqual(self._observe()["references"][0]["kind"], "working_copy_path")

    def test_reference_name_comes_from_caller_path(self) -> None:
        result = self._observe(working_copy_path="/caller/path.FCStd")
        self.assertEqual(result["references"][0]["name"], "/caller/path.FCStd")

    def test_reference_name_differs_from_expected_path(self) -> None:
        result = self._observe(working_copy_path="/caller/path.FCStd")
        self.assertNotEqual(result["references"][0]["name"], _EXPECTED_ENGINE_PATH)

    def test_no_document_lookup_for_working_copy_path_reference(self) -> None:
        try:
            result = self._observe()
        except AssertionError as exc:
            self.fail(f"document.getObject unexpectedly called: {exc}")
        self.assertIn("references", result)

    def test_reference_fields_in_observed_contract_order(self) -> None:
        result = self._observe()
        self.assertEqual(list(result["references"][0].keys()), ["kind", "name"])

    def test_path_like_object_converted_to_string_name(self) -> None:
        result = _call_adapter(
            ForbiddenDocument(),
            _engine_verification_data(),
            working_copy_path=Path("/path/like/model.FCStd"),
        )
        self.assertEqual(result["references"][0]["name"], "/path/like/model.FCStd")

    def test_different_caller_paths_produce_different_names(self) -> None:
        a = _call_adapter(
            ForbiddenDocument(), _engine_verification_data(),
            working_copy_path="/path/a.FCStd",
        )
        b = _call_adapter(
            ForbiddenDocument(), _engine_verification_data(),
            working_copy_path="/path/b.FCStd",
        )
        self.assertNotEqual(
            a["references"][0]["name"],
            b["references"][0]["name"],
        )


# ===========================================================================
# 5. Disabled parameters
# ===========================================================================


class DisabledParametersTests(unittest.TestCase):

    def test_parameters_absent_when_observe_parameters_false(self) -> None:
        result = _call_adapter(ForbiddenDocument(), _engine_verification_data())
        self.assertNotIn("parameters", result)

    def test_empty_observation_context_parameters_accepted(self) -> None:
        data = _engine_verification_data()
        self.assertEqual(data["observationContext"]["parameters"], [])
        result = _call_adapter(ForbiddenDocument(), data)
        self.assertNotIn("parameters", result)

    def test_no_document_access_when_parameters_disabled(self) -> None:
        try:
            result = _call_adapter(ForbiddenDocument(), _engine_verification_data())
        except AssertionError as exc:
            self.fail(
                f"document access occurred during disabled parameter observation: {exc}"
            )
        self.assertNotIn("parameters", result)

    def test_nonempty_expected_parameters_not_observed_when_observe_false(
        self,
    ) -> None:
        data = _engine_verification_data()
        data["expected"]["parameters"] = [
            {"id": "p.x", "name": "X", "type": "number", "unit": "mm", "value": 5}
        ]
        result = _call_adapter(ForbiddenDocument(), data)
        self.assertNotIn("parameters", result)


# ===========================================================================
# 6. No component observation
# ===========================================================================


class NoComponentObservationTests(unittest.TestCase):

    def test_components_absent_when_observe_components_false(self) -> None:
        result = _call_adapter(ForbiddenDocument(), _engine_verification_data())
        self.assertNotIn("components", result)

    def test_no_document_objects_traversal(self) -> None:
        try:
            result = _call_adapter(ForbiddenDocument(), _engine_verification_data())
        except AssertionError as exc:
            self.fail(f"document.Objects accessed unexpectedly: {exc}")
        self.assertNotIn("components", result)

    def test_components_absent_even_when_observe_components_true(self) -> None:
        data = _engine_verification_data()
        data["observe"]["components"] = True
        result = _call_adapter(ForbiddenDocument(), data)
        self.assertNotIn("components", result)


# ===========================================================================
# 7. No verification decisions
# ===========================================================================


class NoVerificationDecisionsTests(unittest.TestCase):

    def test_output_contains_no_pass_fail_field(self) -> None:
        result = _call_adapter(ForbiddenDocument(), _engine_verification_data())
        for key in result:
            self.assertNotIn("pass", key.lower())
            self.assertNotIn("fail", key.lower())
            self.assertNotIn("decision", key.lower())

    def test_checks_field_not_in_observation_output(self) -> None:
        result = _call_adapter(ForbiddenDocument(), _engine_verification_data())
        self.assertNotIn("checks", result)

    def test_expected_value_ignored_observed_value_unconstrained(self) -> None:
        data = _engine_verification_data()
        data["expected"]["metadata"][0]["value"] = "some-expected-value"
        result = _call_adapter(
            ForbiddenDocument(), data,
            working_copy_sha256="completely-different-actual",
        )
        entry = result["metadata"][0]
        self.assertEqual(entry["value"], "completely-different-actual")
        self.assertNotIn("expected", entry)
        self.assertNotIn("match", entry)

    def test_checks_enabled_true_produces_no_output_field(self) -> None:
        data = _engine_verification_data()
        data["checks"]["metadata"]["enabled"] = True
        result = _call_adapter(ForbiddenDocument(), data)
        self.assertNotIn("checks", result)


# ===========================================================================
# 8. Document-backed behavior preserved
# ===========================================================================


class DocumentBackedBehaviorPreservedTests(unittest.TestCase):

    def test_document_backed_metadata_still_delegated(self) -> None:
        doc = FakeDocument({"Doc": FakeObject(Author="Jane")})
        verification_data = {
            "observe": {"metadata": True},
            "expected": {
                "metadata": [
                    {"id": "m.author", "key": "Author", "ownerId": "Doc"},
                ]
            },
        }
        result = _call_adapter(doc, verification_data)
        self.assertIn("metadata", result)
        entry = result["metadata"][0]
        self.assertEqual(entry["id"], "m.author")
        self.assertEqual(entry["value"], "Jane")
        self.assertIn("Doc", doc.calls)

    def test_document_backed_reference_still_delegated(self) -> None:
        doc = FakeDocument({"Sketch001": FakeObject()})
        verification_data = {
            "observe": {"references": True},
            "expected": {
                "references": [
                    {"kind": "constraint", "name": "Sketch001"},
                ]
            },
        }
        result = _call_adapter(doc, verification_data)
        self.assertIn("references", result)
        entry = result["references"][0]
        self.assertEqual(entry["kind"], "constraint")
        self.assertEqual(entry["name"], "Sketch001")
        self.assertIn("Sketch001", doc.calls)

    def test_no_observe_field_returns_empty_dict(self) -> None:
        result = _call_adapter(ForbiddenDocument(), {"expected": {}})
        self.assertEqual(result, {})

    def test_non_mapping_verification_data_raises(self) -> None:
        from parametron_freecad.observation.requested_scope_observation import (
            RequestedScopeObservationRequestError,
        )
        with self.assertRaises(RequestedScopeObservationRequestError):
            _call_adapter(ForbiddenDocument(), "not a mapping")

    def test_metadata_with_id_and_owner_id_not_treated_as_engine_request(
        self,
    ) -> None:
        doc = FakeDocument({"Owner": FakeObject(Key="value123")})
        verification_data = {
            "observe": {"metadata": True},
            "expected": {
                "metadata": [
                    # Has id + ownerId → document-backed, NOT Engine runtime-context
                    {"id": "m.key", "key": "Key", "ownerId": "Owner"},
                ]
            },
        }
        result = _call_adapter(doc, verification_data)
        entry = result["metadata"][0]
        self.assertEqual(entry["id"], "m.key")
        self.assertIn("Owner", doc.calls)


# ===========================================================================
# 9. Mixed runtime-context + document-backed entries
# ===========================================================================


class MixedEntriesTests(unittest.TestCase):

    def _mixed_doc(self) -> FakeDocument:
        return FakeDocument({
            "Doc": FakeObject(Author="Alice"),
            "Sketch001": FakeObject(),
        })

    def _mixed_verification_data(self) -> dict:
        return {
            "observe": {
                "metadata": True,
                "references": True,
            },
            "expected": {
                "metadata": [
                    # Document-backed first (has id + ownerId → not Engine runtime)
                    {"id": "m.author", "key": "Author", "ownerId": "Doc"},
                    # Engine runtime-context second (no id, no ownerId)
                    {"key": "working_copy_sha256"},
                ],
                "references": [
                    # Engine runtime-context first
                    {"kind": "working_copy_path", "name": "/engine/path"},
                    # Document-backed second
                    {"kind": "constraint", "name": "Sketch001"},
                ],
            },
        }

    def test_mixed_metadata_request_order_preserved(self) -> None:
        result = _call_adapter(
            self._mixed_doc(),
            self._mixed_verification_data(),
            working_copy_sha256="mixed-sha256",
        )
        metadata = result["metadata"]
        self.assertEqual(len(metadata), 2)
        self.assertEqual(metadata[0]["id"], "m.author")
        self.assertEqual(metadata[0]["value"], "Alice")
        self.assertEqual(metadata[1]["key"], "working_copy_sha256")
        self.assertEqual(metadata[1]["value"], "mixed-sha256")

    def test_mixed_reference_request_order_preserved(self) -> None:
        result = _call_adapter(
            self._mixed_doc(),
            self._mixed_verification_data(),
            working_copy_path="/mixed/caller/path.FCStd",
        )
        references = result["references"]
        self.assertEqual(len(references), 2)
        self.assertEqual(references[0]["kind"], "working_copy_path")
        self.assertEqual(references[0]["name"], "/mixed/caller/path.FCStd")
        self.assertEqual(references[1]["kind"], "constraint")
        self.assertEqual(references[1]["name"], "Sketch001")

    def test_mixed_document_backed_value_from_document(self) -> None:
        result = _call_adapter(self._mixed_doc(), self._mixed_verification_data())
        self.assertEqual(result["metadata"][0]["value"], "Alice")

    def test_mixed_engine_entry_value_from_caller_not_expected(self) -> None:
        result = _call_adapter(
            self._mixed_doc(),
            self._mixed_verification_data(),
            working_copy_sha256="caller-specific-hash",
        )
        engine_entry = result["metadata"][1]
        self.assertEqual(engine_entry["value"], "caller-specific-hash")

    def test_mixed_metadata_contains_both_ids(self) -> None:
        result = _call_adapter(self._mixed_doc(), self._mixed_verification_data())
        ids = [e["id"] for e in result["metadata"]]
        self.assertIn("m.author", ids)
        self.assertIn("working_copy_sha256", ids)

    def test_mixed_references_contains_both_kinds(self) -> None:
        result = _call_adapter(self._mixed_doc(), self._mixed_verification_data())
        kinds = [e["kind"] for e in result["references"]]
        self.assertIn("working_copy_path", kinds)
        self.assertIn("constraint", kinds)


# ===========================================================================
# 10. Byte-level determinism through generate_observed_output
# ===========================================================================


class DeterminismTests(unittest.TestCase):

    def setUp(self):
        self.mod = _import_observed_output()

    def _generate(self, document, verification_data, output_dir, **kwargs):
        defaults = {
            "working_copy_path": _CALLER_PATH,
            "working_copy_sha256": _CALLER_SHA256,
            "output_directory": output_dir,
        }
        defaults.update(kwargs)
        return self.mod.generate_observed_output(
            document,
            verification_data,
            **defaults,
        )

    def _observed_path(self, output_dir):
        return self.mod.observed_json_path(output_dir)

    def test_repeated_run_same_directory_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._observed_path(tmp)
            self._generate(ForbiddenDocument(), _engine_verification_data(), tmp)
            first = path.read_bytes()
            self._generate(ForbiddenDocument(), _engine_verification_data(), tmp)
            second = path.read_bytes()
        self.assertEqual(first, second)

    def test_fresh_directories_produce_byte_identical_output(self) -> None:
        with tempfile.TemporaryDirectory() as dir_a:
            with tempfile.TemporaryDirectory() as dir_b:
                self._generate(ForbiddenDocument(), _engine_verification_data(), dir_a)
                self._generate(ForbiddenDocument(), _engine_verification_data(), dir_b)
                self.assertEqual(
                    self._observed_path(dir_a).read_bytes(),
                    self._observed_path(dir_b).read_bytes(),
                )

    def test_stale_file_overwritten_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._observed_path(tmp)
            path.write_text('{"stale":true}\nextra line\n', encoding="utf-8")
            self._generate(ForbiddenDocument(), _engine_verification_data(), tmp)
            first = path.read_bytes()
            self._generate(ForbiddenDocument(), _engine_verification_data(), tmp)
            second = path.read_bytes()
        self.assertEqual(first, second)
        text = first.decode("utf-8")
        self.assertNotIn("stale", text)
        self.assertEqual(text.count("\n"), 1)

    def test_output_utf8_with_single_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._generate(ForbiddenDocument(), _engine_verification_data(), tmp)
            text = self._observed_path(tmp).read_bytes().decode("utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(text.count("\n"), 1)

    def test_canonical_top_level_fields_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._generate(ForbiddenDocument(), _engine_verification_data(), tmp)
            decoded = json.loads(self._observed_path(tmp).read_text(encoding="utf-8"))
        self.assertEqual(
            set(decoded.keys()),
            {"schemaVersion", "workingCopy", "observation"},
        )
        self.assertEqual(decoded["schemaVersion"], "1.0")
        self.assertEqual(decoded["workingCopy"]["path"], _CALLER_PATH)
        self.assertEqual(decoded["workingCopy"]["sha256"], _CALLER_SHA256)

    def test_observation_contains_metadata_and_references_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._generate(ForbiddenDocument(), _engine_verification_data(), tmp)
            decoded = json.loads(self._observed_path(tmp).read_text(encoding="utf-8"))
        observation = decoded["observation"]
        self.assertEqual(set(observation.keys()), {"metadata", "references"})
        self.assertNotIn("parameters", observation)
        self.assertNotIn("components", observation)

    def test_metadata_value_from_caller_in_written_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._generate(
                ForbiddenDocument(), _engine_verification_data(), tmp,
                working_copy_sha256="written-sha256-test",
            )
            decoded = json.loads(self._observed_path(tmp).read_text(encoding="utf-8"))
        metadata = decoded["observation"]["metadata"]
        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0]["key"], "working_copy_sha256")
        self.assertEqual(metadata[0]["value"], "written-sha256-test")
        self.assertEqual(metadata[0]["valueKind"], "string")

    def test_reference_name_from_caller_in_written_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._generate(
                ForbiddenDocument(), _engine_verification_data(), tmp,
                working_copy_path="/written/path/test.FCStd",
            )
            decoded = json.loads(self._observed_path(tmp).read_text(encoding="utf-8"))
        references = decoded["observation"]["references"]
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0]["kind"], "working_copy_path")
        self.assertEqual(references[0]["name"], "/written/path/test.FCStd")

    def test_input_verification_data_not_mutated(self) -> None:
        data = _engine_verification_data()
        before = copy.deepcopy(data)
        with tempfile.TemporaryDirectory() as tmp:
            self._generate(ForbiddenDocument(), data, tmp)
            self._generate(ForbiddenDocument(), data, tmp)
        self.assertEqual(data, before)


# ===========================================================================
# 11. Error boundaries
# ===========================================================================


class ErrorBoundaryAdapterTests(unittest.TestCase):

    def test_empty_sha256_raises_compatibility_error(self) -> None:
        with self.assertRaises(evc.EngineVerificationCompatibilityError):
            _call_adapter(
                ForbiddenDocument(), _engine_verification_data(),
                working_copy_sha256="",
            )

    def test_non_string_sha256_raises_compatibility_error(self) -> None:
        with self.assertRaises(evc.EngineVerificationCompatibilityError):
            _call_adapter(
                ForbiddenDocument(), _engine_verification_data(),
                working_copy_sha256=12345,
            )

    def test_empty_path_raises_compatibility_error(self) -> None:
        with self.assertRaises(evc.EngineVerificationCompatibilityError):
            _call_adapter(
                ForbiddenDocument(), _engine_verification_data(),
                working_copy_path="",
            )

    def test_non_path_like_path_raises_compatibility_error(self) -> None:
        with self.assertRaises(evc.EngineVerificationCompatibilityError):
            _call_adapter(
                ForbiddenDocument(), _engine_verification_data(),
                working_copy_path=12345,
            )


class ErrorBoundaryObservedOutputTests(unittest.TestCase):

    def setUp(self):
        self.mod = _import_observed_output()

    def _generate(self, document, verification_data, output_dir, **kwargs):
        defaults = {
            "working_copy_path": _CALLER_PATH,
            "working_copy_sha256": _CALLER_SHA256,
            "output_directory": output_dir,
        }
        defaults.update(kwargs)
        return self.mod.generate_observed_output(
            document,
            verification_data,
            **defaults,
        )

    def test_generate_wraps_compatibility_error_in_observed_output_error(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(self.mod.ObservedOutputError) as excinfo:
                self._generate(
                    ForbiddenDocument(), _engine_verification_data(), tmp,
                    working_copy_sha256="",
                )
        self.assertIsInstance(
            excinfo.exception.__cause__,
            evc.EngineVerificationCompatibilityError,
        )

    def test_generate_wraps_invalid_path_in_observed_output_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(self.mod.ObservedOutputError) as excinfo:
                self._generate(
                    ForbiddenDocument(), _engine_verification_data(), tmp,
                    working_copy_path="",
                )
        self.assertIsInstance(
            excinfo.exception.__cause__,
            evc.EngineVerificationCompatibilityError,
        )


class ErrorBoundaryEntrypointTests(unittest.TestCase):

    def setUp(self):
        from parametron_freecad.runtime import entrypoints
        self.entrypoints = entrypoints
        self.observed_output_mod = _import_observed_output()

    def test_observation_entrypoint_wraps_observed_output_error_with_cause(
        self,
    ) -> None:
        original = self.observed_output_mod.ObservedOutputError("fake failure")

        with mock.patch.object(
            self.entrypoints,
            "generate_observed_output",
            side_effect=original,
        ), self.assertRaises(
            self.entrypoints.ObservationEntrypointError
        ) as excinfo:
            self.entrypoints.run_observation_entrypoint(
                ForbiddenDocument(),
                _engine_verification_data(),
                working_copy_path=_CALLER_PATH,
                working_copy_sha256=_CALLER_SHA256,
                output_directory="/tmp/out",
            )

        self.assertEqual(str(excinfo.exception), "fake failure")
        self.assertIs(excinfo.exception.__cause__, original)


class ErrorBoundaryEngineInvocationTests(unittest.TestCase):

    def setUp(self):
        self.observed_output_mod = _import_observed_output()

    def test_engine_invocation_observe_wraps_observation_entrypoint_error(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints, invocation

        original = entrypoints.ObservationEntrypointError("fake observation failure")

        with mock.patch.object(
            invocation, "run_observation_entrypoint", side_effect=original
        ), self.assertRaises(invocation.EngineInvocationObservationError) as excinfo:
            invocation.run_engine_invocation(
                invocation.EngineRuntimeInvocation(
                    mode="observe",
                    observation=invocation.ObservationInvocation(
                        document=ForbiddenDocument(),
                        verification_data=_engine_verification_data(),
                        working_copy_path=_CALLER_PATH,
                        working_copy_sha256=_CALLER_SHA256,
                        output_directory="/tmp/out",
                    ),
                )
            )

        self.assertEqual(str(excinfo.exception), "fake observation failure")
        self.assertIs(excinfo.exception.__cause__, original)

    def test_engine_invocation_observe_full_error_chain_on_invalid_sha256(
        self,
    ) -> None:
        from parametron_freecad.runtime import entrypoints, invocation

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(
                invocation.EngineInvocationObservationError
            ) as excinfo:
                invocation.run_engine_invocation(
                    invocation.EngineRuntimeInvocation(
                        mode="observe",
                        observation=invocation.ObservationInvocation(
                            document=ForbiddenDocument(),
                            verification_data=_engine_verification_data(),
                            working_copy_path=_CALLER_PATH,
                            working_copy_sha256="",  # invalid → full error chain
                            output_directory=tmp,
                        ),
                    )
                )

        cause = excinfo.exception.__cause__
        self.assertIsInstance(cause, entrypoints.ObservationEntrypointError)
        inner = cause.__cause__
        self.assertIsInstance(inner, self.observed_output_mod.ObservedOutputError)
        compat_error = inner.__cause__
        self.assertIsInstance(compat_error, evc.EngineVerificationCompatibilityError)


if __name__ == "__main__":
    unittest.main()
