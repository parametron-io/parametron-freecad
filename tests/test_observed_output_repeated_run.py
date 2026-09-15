"""Repeated-run byte-stability tests for observed output generation.

These tests exercise the public behavior of
``parametron_freecad.observation.observed_output.generate_observed_output``
under ordinary Python with fake/injected document objects. They never require
FreeCAD, never evaluate verification decisions, never observe components, never
perform Label lookup, and never traverse ``document.Objects``.

The focus is byte-level determinism: repeated calls with equivalent inputs must
produce byte-identical ``prm.observed.json`` output.
"""

from __future__ import annotations

import copy
import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


MODULE_NAME = "parametron_freecad.observation.observed_output"


def _import_module():
    return importlib.import_module(MODULE_NAME)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeObject:
    """Minimal fake document object exposing arbitrary properties."""

    def __init__(self, **properties):
        for name, value in properties.items():
            setattr(self, name, value)


class FakeDocument:
    """Fake FreeCAD document exposing only getObject.

    ``Objects`` and ``Label`` deliberately raise if accessed, proving no
    discovery traversal or Label lookup occurs during observed output
    generation.
    """

    def __init__(self, objects=None):
        self._objects = dict(objects or {})
        self.calls = []

    @property
    def Objects(self):  # noqa: N802 - mimic FreeCAD attribute name
        raise AssertionError("document.Objects must not be accessed")

    @property
    def Label(self):  # noqa: N802 - mimic FreeCAD attribute name
        raise AssertionError("document Label lookup must not be used")

    def getObject(self, name):  # noqa: N802 - mimic FreeCAD method name
        self.calls.append(name)
        return self._objects.get(name)


# ---------------------------------------------------------------------------
# Document and verification-data builders
# ---------------------------------------------------------------------------


def _full_document():
    """Document covering every supported value kind across categories."""
    return FakeDocument(
        {
            "Spreadsheet": FakeObject(
                Length=10.0,  # number/float
                Count=5,  # integer
                Enabled=True,  # boolean
            ),
            "Doc": FakeObject(
                Author="Jane",  # string
                Revision=3,  # integer
            ),
            "Sketch001": FakeObject(),
            "Body": FakeObject(),
        }
    )


def _full_verification_data():
    """Verification mapping requesting parameters, metadata and references.

    Includes nested dictionaries and lists in deliberately non-alphabetical
    request order so non-mutation and ordering assertions are meaningful.
    """
    return {
        "observe": {
            "references": True,
            "metadata": True,
            "parameters": True,
        },
        "observationContext": {
            "parameters": [
                {"id": "p.length", "name": "Length", "groupName": "Spreadsheet"},
                {"id": "p.count", "name": "Count", "groupName": "Spreadsheet"},
                {"id": "p.enabled", "name": "Enabled", "groupName": "Spreadsheet"},
            ]
        },
        "expected": {
            "metadata": [
                {"id": "m.author", "key": "Author", "ownerId": "Doc"},
                {"id": "m.revision", "key": "Revision", "ownerId": "Doc"},
            ],
            "references": [
                {"kind": "constraint", "name": "Sketch001"},
                {"kind": "part", "name": "Body"},
            ],
        },
    }


_WORKING_COPY_PATH = "/work/model.FCStd"
_WORKING_COPY_SHA256 = "a" * 64


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _ObservedOutputTestCase(unittest.TestCase):
    def setUp(self):
        self.mod = _import_module()

    def generate(self, document, verification_data, output_directory, **kwargs):
        defaults = {
            "working_copy_path": _WORKING_COPY_PATH,
            "working_copy_sha256": _WORKING_COPY_SHA256,
            "output_directory": output_directory,
        }
        defaults.update(kwargs)
        return self.mod.generate_observed_output(
            document,
            verification_data,
            **defaults,
        )

    def observed_path(self, output_directory):
        return self.mod.observed_json_path(output_directory)


# ---------------------------------------------------------------------------
# Section 1 — Same output directory repeated run is byte-stable
# ---------------------------------------------------------------------------


class TestSameDirectoryRepeatedRun(_ObservedOutputTestCase):
    def test_repeated_same_directory_run_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self.observed_path(tmp_dir)

            self.generate(_full_document(), _full_verification_data(), tmp_dir)
            first = path.read_bytes()

            self.generate(_full_document(), _full_verification_data(), tmp_dir)
            second = path.read_bytes()

            self.assertEqual(first, second)
            self.assertTrue(path.exists())
            self.assertEqual(path, Path(tmp_dir) / "prm.observed.json")

    def test_output_is_utf8_with_single_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self.observed_path(tmp_dir)
            self.generate(_full_document(), _full_verification_data(), tmp_dir)

            raw = path.read_bytes()
            text = raw.decode("utf-8")  # raises if not valid UTF-8

            self.assertTrue(text.endswith("\n"))
            self.assertFalse(text.endswith("\n\n"))
            self.assertEqual(text.count("\n"), 1)

    def test_canonical_top_level_fields_present(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self.observed_path(tmp_dir)
            self.generate(_full_document(), _full_verification_data(), tmp_dir)

            decoded = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(
                set(decoded.keys()),
                {"schemaVersion", "workingCopy", "observation"},
            )
            self.assertEqual(decoded["schemaVersion"], "1.0")
            self.assertEqual(
                set(decoded["workingCopy"].keys()),
                {"path", "sha256"},
            )

    def test_only_requested_supported_categories_are_present(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self.observed_path(tmp_dir)
            data = {
                "observe": {"parameters": True},
                "observationContext": {
                    "parameters": [
                        {"id": "p.count", "name": "Count", "groupName": "Spreadsheet"}
                    ]
                },
            }
            self.generate(_full_document(), data, tmp_dir)

            decoded = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(set(decoded["observation"].keys()), {"parameters"})
            self.assertNotIn("metadata", decoded["observation"])
            self.assertNotIn("references", decoded["observation"])

    def test_decoded_structure_ordering_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self.observed_path(tmp_dir)

            self.generate(_full_document(), _full_verification_data(), tmp_dir)
            first_decoded = json.loads(path.read_text(encoding="utf-8"))

            self.generate(_full_document(), _full_verification_data(), tmp_dir)
            second_decoded = json.loads(path.read_text(encoding="utf-8"))

            observation = first_decoded["observation"]
            # Category key ordering is stable across runs.
            self.assertEqual(
                list(observation.keys()),
                list(second_decoded["observation"].keys()),
            )
            # List item ordering follows request order deterministically.
            self.assertEqual(
                [item["id"] for item in observation["parameters"]],
                ["p.length", "p.count", "p.enabled"],
            )
            self.assertEqual(
                [item["id"] for item in observation["metadata"]],
                ["m.author", "m.revision"],
            )
            self.assertEqual(
                [item["name"] for item in observation["references"]],
                ["Sketch001", "Body"],
            )

    def test_supported_value_kinds_are_observed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self.observed_path(tmp_dir)
            self.generate(_full_document(), _full_verification_data(), tmp_dir)

            decoded = json.loads(path.read_text(encoding="utf-8"))
            params = {p["id"]: p for p in decoded["observation"]["parameters"]}

            self.assertEqual(params["p.length"]["valueKind"], "number")
            self.assertEqual(params["p.count"]["valueKind"], "integer")
            self.assertEqual(params["p.enabled"]["valueKind"], "boolean")

            metadata = {m["id"]: m for m in decoded["observation"]["metadata"]}
            self.assertEqual(metadata["m.author"]["valueKind"], "string")
            self.assertEqual(metadata["m.revision"]["valueKind"], "integer")


# ---------------------------------------------------------------------------
# Section 2 — Equivalent fresh output directories are byte-stable
# ---------------------------------------------------------------------------


class TestEquivalentFreshDirectories(_ObservedOutputTestCase):
    def test_two_fresh_directories_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as dir_a:
            with tempfile.TemporaryDirectory() as dir_b:
                self.generate(_full_document(), _full_verification_data(), dir_a)
                self.generate(_full_document(), _full_verification_data(), dir_b)

                path_a = self.observed_path(dir_a)
                path_b = self.observed_path(dir_b)

                self.assertEqual(path_a.name, "prm.observed.json")
                self.assertEqual(path_b.name, "prm.observed.json")

                self.assertEqual(path_a.read_bytes(), path_b.read_bytes())
                self.assertEqual(
                    json.loads(path_a.read_text(encoding="utf-8")),
                    json.loads(path_b.read_text(encoding="utf-8")),
                )


# ---------------------------------------------------------------------------
# Section 3 — Deterministic overwrite of stale observed file
# ---------------------------------------------------------------------------


class TestStaleFileOverwrite(_ObservedOutputTestCase):
    def test_stale_content_is_overwritten_and_runs_are_stable(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self.observed_path(tmp_dir)
            path.write_text(
                '{"stale":true,"leftover":[1,2,3]}\nextra trailing line\n',
                encoding="utf-8",
            )

            self.generate(_full_document(), _full_verification_data(), tmp_dir)
            first = path.read_bytes()

            self.generate(_full_document(), _full_verification_data(), tmp_dir)
            second = path.read_bytes()

            self.assertEqual(first, second)

            text = first.decode("utf-8")
            self.assertNotIn("stale", text)
            self.assertNotIn("leftover", text)
            self.assertNotIn("extra trailing line", text)
            self.assertEqual(text.count("\n"), 1)

            decoded = json.loads(text)
            self.assertNotIn("stale", decoded)
            self.assertNotIn("leftover", decoded)
            self.assertEqual(
                set(decoded.keys()),
                {"schemaVersion", "workingCopy", "observation"},
            )


# ---------------------------------------------------------------------------
# Section 4 — Input mapping is not mutated across repeated generation
# ---------------------------------------------------------------------------


class TestInputNonMutation(_ObservedOutputTestCase):
    def test_verification_mapping_unchanged_after_repeated_generation(self):
        verification_data = _full_verification_data()
        before = copy.deepcopy(verification_data)

        with tempfile.TemporaryDirectory() as tmp_dir:
            self.generate(_full_document(), verification_data, tmp_dir)
            self.generate(_full_document(), verification_data, tmp_dir)
            self.generate(_full_document(), verification_data, tmp_dir)

        self.assertEqual(verification_data, before)

    def test_nested_request_ordering_and_fields_unchanged(self):
        verification_data = _full_verification_data()
        before = copy.deepcopy(verification_data)

        with tempfile.TemporaryDirectory() as tmp_dir:
            self.generate(_full_document(), verification_data, tmp_dir)

        self.assertEqual(
            [b["id"] for b in verification_data["observationContext"]["parameters"]],
            [b["id"] for b in before["observationContext"]["parameters"]],
        )
        self.assertEqual(
            [m["id"] for m in verification_data["expected"]["metadata"]],
            [m["id"] for m in before["expected"]["metadata"]],
        )
        self.assertEqual(
            [r["name"] for r in verification_data["expected"]["references"]],
            [r["name"] for r in before["expected"]["references"]],
        )
        self.assertEqual(
            list(verification_data["observe"].keys()),
            list(before["observe"].keys()),
        )


# ---------------------------------------------------------------------------
# Section 5 — Components remain unsupported and require no Objects traversal
# ---------------------------------------------------------------------------


class TestComponentsUnsupported(_ObservedOutputTestCase):
    def test_components_only_emits_no_observation_categories(self):
        # FakeDocument.Objects raises if touched, proving no traversal.
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self.observed_path(tmp_dir)
            self.generate(
                FakeDocument(),
                {"observe": {"components": True}},
                tmp_dir,
            )

            decoded = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("components", decoded["observation"])
            self.assertEqual(decoded["observation"], {})

    def test_components_alongside_supported_categories_omits_components(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self.observed_path(tmp_dir)
            data = _full_verification_data()
            data["observe"]["components"] = True

            self.generate(_full_document(), data, tmp_dir)

            decoded = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("components", decoded["observation"])
            self.assertEqual(
                set(decoded["observation"].keys()),
                {"parameters", "metadata", "references"},
            )

    def test_components_request_is_byte_stable_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self.observed_path(tmp_dir)
            data = _full_verification_data()
            data["observe"]["components"] = True

            self.generate(_full_document(), copy.deepcopy(data), tmp_dir)
            first = path.read_bytes()
            self.generate(_full_document(), copy.deepcopy(data), tmp_dir)
            second = path.read_bytes()

            self.assertEqual(first, second)


# ---------------------------------------------------------------------------
# Section 6 — Import safety (ordinary Python, no FreeCAD)
# ---------------------------------------------------------------------------


class TestImportSafety(unittest.TestCase):
    def test_import_does_not_require_freecad(self):
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad"}
        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            if name in guarded_names:
                raise AssertionError(f"{name} must not be imported")
            return real_import(name, *args, **kwargs)

        previous = sys.modules.pop(MODULE_NAME, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_module()

        self.assertIsInstance(module, types.ModuleType)
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_no_freecad_in_sys_modules_after_import(self):
        _import_module()
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("FreeCADGui", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_module_exposes_expected_public_surface(self):
        module = _import_module()
        self.assertTrue(hasattr(module, "generate_observed_output"))
        self.assertTrue(callable(module.generate_observed_output))
        self.assertTrue(hasattr(module, "ObservedOutputError"))
        self.assertTrue(issubclass(module.ObservedOutputError, ValueError))


if __name__ == "__main__":
    unittest.main()
