"""Canonical Engine target-state requests and raw FreeCAD observation evidence."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from parametron_freecad.observation.observation_ordering import (
    ObservationOrderingRequestError,
    order_observation_payload,
)
from parametron_freecad.observation.engine_verification_compat import observe_engine_compatible_requested_scope
from parametron_freecad.observation.observed_output import ObservedOutputError, generate_observed_output
from parametron_freecad.observation.observed_writer import ObservedPayloadError, build_observed_payload
from parametron_freecad.observation.requested_scope_observation import observe_requested_contract_scope
from parametron_freecad.observation.target_state_observation import (
    TargetStateObservationError,
    requested_target_state,
)
from parametron_freecad.runtime.observation_request import ObservationRequestError, load_observation_request


def identity(destination="part", object_name="Pad"):
    return {"destination": destination, "object": object_name}


def request(*, suppression=(), visibility=(), existence=()):
    return {
        "schemaVersion": "1.0",
        "observe": {"targetState": True},
        "observationContext": {"targetState": {
            "suppression": list(suppression), "visibility": list(visibility), "existence": list(existence),
        }},
    }


class NativeObject:
    def __init__(self, **properties):
        self.PropertiesList = list(properties)
        for name, value in properties.items():
            setattr(self, name, value)
        self.types = {name: "App::PropertyBool" for name in properties}
        self.queries = []

    def getTypeIdOfProperty(self, name):
        self.queries.append(name)
        return self.types[name]

    @property
    def ViewObject(self):
        raise AssertionError("GUI state must never be read")


class Document:
    def __init__(self, objects):
        self.objects = objects
        self.lookups = []

    def getObject(self, name):
        self.lookups.append(name)
        return self.objects.get(name)

    @property
    def Objects(self):
        raise AssertionError("whole-document traversal is forbidden")


class RequestContractTests(unittest.TestCase):
    def test_absent_and_explicit_false_need_no_context(self):
        for value in ({"observe": {"metadata": True}}, {"schemaVersion": "1.0", "observe": {"targetState": False}}):
            with self.subTest(value=value):
                self.assertIsNone(requested_target_state(value))

    def test_presence_schema_and_families(self):
        valid = request(existence=[identity()])
        self.assertEqual(requested_target_state(valid)["existence"], (identity(),))
        variants = []
        item = copy.deepcopy(valid); del item["observationContext"]; variants.append(item)
        item = copy.deepcopy(valid); item["observe"]["targetState"] = False; variants.append(item)
        item = copy.deepcopy(valid); item["observe"]["targetState"] = "true"; variants.append(item)
        item = copy.deepcopy(valid); item["schemaVersion"] = "2.0"; variants.append(item)
        item = copy.deepcopy(valid); item["observationContext"]["targetState"]["extra"] = []; variants.append(item)
        for family in ("suppression", "visibility", "existence"):
            item = copy.deepcopy(valid); del item["observationContext"]["targetState"][family]; variants.append(item)
        variants.append(request())
        item = copy.deepcopy(valid); del item["observe"]["targetState"]; variants.append(item)
        for invalid in variants:
            with self.subTest(invalid=invalid), self.assertRaises(TargetStateObservationError):
                requested_target_state(invalid)

    def test_identity_validation_in_every_family(self):
        bad = [
            {"destination": "body", "object": "Pad"},
            identity("Part"), identity(object_name=""), identity(object_name="  "),
            identity(object_name=" Pad"), identity(object_name="Pad "),
            identity(object_name="Pa\x00d"), {"object": "Pad"},
            {"destination": "part"}, {**identity(), "label": "Pad"}, "Pad",
        ]
        for family in ("suppression", "visibility", "existence"):
            for entry in bad:
                with self.subTest(family=family, entry=entry), self.assertRaises(TargetStateObservationError):
                    requested_target_state(request(**{family: [entry]}))

    def test_duplicates_are_family_local_and_destination_is_identity(self):
        for family in ("suppression", "visibility", "existence"):
            with self.subTest(family=family), self.assertRaises(TargetStateObservationError):
                requested_target_state(request(**{family: [identity(), identity()]}))
        valid = request(suppression=[identity(), identity("assembly")], visibility=[identity()], existence=[identity()])
        self.assertEqual(len(requested_target_state(valid)["suppression"]), 2)

    def test_actual_request_loader_accepts_and_rejects_target_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prm.verification.json"
            good = request(visibility=[identity()])
            path.write_text(json.dumps(good), encoding="utf-8")
            self.assertEqual(load_observation_request(path), good)
            bad = request(visibility=[identity(object_name=" Pad")])
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ObservationRequestError):
                load_observation_request(path)


class NativeEvidenceTests(unittest.TestCase):
    def observe(self, document, **families):
        return observe_requested_contract_scope(document, request(**families))["targetState"]

    def test_suppression_true_false_missing_and_unavailable(self):
        true = NativeObject(Suppressed=True)
        false = NativeObject(Suppressed=False)
        wrong = NativeObject(Suppressed=True); wrong.types["Suppressed"] = "App::PropertyString"
        non_boolean = NativeObject(Suppressed=1)
        document = Document({"A": true, "B": false, "Wrong": wrong, "Value": non_boolean, "NoProperty": NativeObject()})
        entries = [identity(object_name=n) for n in ("Wrong", "B", "Missing", "A", "Value", "NoProperty")]
        actual = self.observe(document, suppression=entries)
        self.assertEqual(actual["suppression"], (
            {**identity(object_name="A"), "status": "observed", "value": True},
            {**identity(object_name="B"), "status": "observed", "value": False},
            {**identity(object_name="Missing"), "status": "target_missing"},
            {**identity(object_name="NoProperty"), "status": "unavailable"},
            {**identity(object_name="Value"), "status": "unavailable"},
            {**identity(object_name="Wrong"), "status": "unavailable"},
        ))
        self.assertEqual(actual["visibility"], ())
        self.assertEqual(actual["existence"], ())
        self.assertEqual(true.queries, ["Suppressed"])

    def test_visibility_reads_app_property_and_preserves_live_value(self):
        true = NativeObject(Visibility=True)
        false = NativeObject(Visibility=False)
        wrong = NativeObject(Visibility=True); wrong.types["Visibility"] = "App::PropertyString"
        document = Document({"Pad": true, "Hidden": false, "Wrong": wrong, "NoProperty": NativeObject()})
        actual = self.observe(document, visibility=[identity(object_name=n) for n in ("Pad", "Hidden", "Missing", "Wrong", "NoProperty")])
        self.assertEqual(actual["visibility"], (
            {**identity(object_name="Hidden"), "status": "observed", "value": False},
            {**identity(object_name="Missing"), "status": "target_missing"},
            {**identity(object_name="NoProperty"), "status": "unavailable"},
            {**identity(), "status": "observed", "value": True},
            {**identity(object_name="Wrong"), "status": "unavailable"},
        ))
        self.assertEqual(true.queries, ["Visibility"])
        self.assertEqual(actual["suppression"], ())

    def test_existence_uses_exact_lookup_only(self):
        doc = Document({"Pad": NativeObject(Suppressed=True, Visibility=False)})
        actual = self.observe(doc, existence=[identity(object_name="pad"), identity()])
        self.assertEqual(actual["existence"], (
            {**identity(), "status": "exists"},
            {**identity(object_name="pad"), "status": "absent"},
        ))
        self.assertEqual(doc.lookups, ["Pad", "pad"])
        self.assertEqual(doc.objects["Pad"].queries, [])

    def test_same_name_across_destinations_and_families(self):
        doc = Document({"Pad": NativeObject(Suppressed=False, Visibility=True)})
        actual = self.observe(doc, suppression=[identity("part"), identity("assembly")], visibility=[identity()], existence=[identity()])
        self.assertEqual([entry["destination"] for entry in actual["suppression"]], ["assembly", "part"])
        self.assertEqual(actual["visibility"][0]["value"], True)
        self.assertEqual(actual["existence"][0]["status"], "exists")

    def test_native_lookup_exception_is_failure(self):
        class BrokenDocument(Document):
            def getObject(self, name):
                raise RuntimeError("native failure")
        for family in ("suppression", "visibility", "existence"):
            with self.subTest(family=family), self.assertRaises(TargetStateObservationError):
                self.observe(BrokenDocument({}), **{family: [identity()]})


class ResultContractTests(unittest.TestCase):
    def test_each_family_sorts_destination_then_case_sensitive_object(self):
        names = [identity("part", "b"), identity("assembly", "Z"), identity("part", "B")]
        target = {
            "suppression": [{**entry, "status": "target_missing"} for entry in names],
            "visibility": [{**entry, "status": "unavailable"} for entry in reversed(names)],
            "existence": [{**entry, "status": "absent"} for entry in names],
        }
        before = copy.deepcopy(target)
        ordered = order_observation_payload({"targetState": target})["targetState"]
        for family in target:
            self.assertEqual([(entry["destination"], entry["object"]) for entry in ordered[family]], [
                ("assembly", "Z"), ("part", "B"), ("part", "b"),
            ])
        self.assertEqual(target, before)

    def test_boolean_status_value_shapes(self):
        accepted = [
            {**identity(), "status": "observed", "value": True},
            {**identity(), "status": "observed", "value": False},
            {**identity(), "status": "target_missing"},
            {**identity(), "status": "unavailable"},
        ]
        rejected = [
            {**identity(), "status": "observed"},
            {**identity(), "status": "observed", "value": 1},
            {**identity(), "status": "target_missing", "value": False},
            {**identity(), "status": "unavailable", "value": True},
            {**identity(), "status": "absent"},
            {**identity(), "status": "observed", "value": True, "extra": 1},
            {"object": "Pad", "status": "target_missing"},
        ]
        for family in ("suppression", "visibility"):
            for entry in accepted:
                with self.subTest(family=family, entry=entry):
                    self.assertEqual(order_observation_payload({"targetState": {family: [entry], **{f: [] for f in ("suppression", "visibility", "existence") if f != family}}})["targetState"][family][0], entry)
            for entry in rejected:
                with self.subTest(family=family, entry=entry), self.assertRaises(ObservationOrderingRequestError):
                    order_observation_payload({"targetState": {family: [entry], **{f: [] for f in ("suppression", "visibility", "existence") if f != family}}})

    def test_existence_statuses_and_duplicates(self):
        for status in ("exists", "absent", "unavailable"):
            evidence = {**identity(), "status": status}
            self.assertEqual(order_observation_payload({"targetState": {"suppression": [], "visibility": [], "existence": [evidence]}})["targetState"]["existence"][0], evidence)
        for evidence in ({**identity(), "status": "target_missing"}, {**identity(), "status": "exists", "value": True}, {**identity(), "status": "unknown"}):
            with self.subTest(evidence=evidence), self.assertRaises(ObservationOrderingRequestError):
                order_observation_payload({"targetState": {"suppression": [], "visibility": [], "existence": [evidence]}})
        for family in ("suppression", "visibility", "existence"):
            item = {**identity(), "status": "exists" if family == "existence" else "target_missing"}
            value = {f: [] for f in ("suppression", "visibility", "existence")}
            value[family] = [item, item]
            with self.assertRaises(ObservationOrderingRequestError):
                order_observation_payload({"targetState": value})

    def test_writer_wraps_invalid_target_state(self):
        with self.assertRaises(ObservedPayloadError):
            build_observed_payload(working_copy_path="/work/model.FCStd", working_copy_sha256="hash", observation_data={"targetState": {"existence": []}})


class OutputTests(unittest.TestCase):
    def test_engine_runtime_context_merge_retains_target_state(self):
        data = request(existence=[identity()])
        data["observe"].update(metadata=True, references=True)
        data["expected"] = {
            "metadata": [{"key": "working_copy_sha256"}],
            "references": [{"kind": "working_copy_path"}],
        }
        observed = observe_engine_compatible_requested_scope(
            Document({"Pad": NativeObject()}), data,
            working_copy_path="/work/model.FCStd", working_copy_sha256="hash",
        )
        self.assertEqual(list(observed), ["metadata", "references", "targetState"])
        self.assertEqual(observed["metadata"][0]["value"], "hash")
        self.assertEqual(observed["references"][0]["name"], "/work/model.FCStd")
        self.assertEqual(observed["targetState"]["existence"][0]["status"], "exists")

    def test_target_state_absence_keeps_existing_output_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            generate_observed_output(
                Document({}), {"observe": {"metadata": True}, "expected": {"metadata": []}},
                working_copy_path="/work/model.FCStd", working_copy_sha256="hash", output_directory=directory,
            )
            observation = json.loads((Path(directory) / "prm.observed.json").read_bytes())["observation"]
            self.assertEqual(observation, {"metadata": []})

    def test_permutations_produce_identical_atomic_output(self):
        entries = [identity("part", "b"), identity("assembly", "Z"), identity("part", "B")]
        doc = Document({"Z": NativeObject(Visibility=True), "B": NativeObject(Visibility=False), "b": NativeObject(Visibility=True)})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "prm.observed.json"
            first = request(visibility=entries)
            generate_observed_output(doc, first, working_copy_path="/work/model.FCStd", working_copy_sha256="hash", output_directory=directory)
            initial = output.read_bytes()
            second = request(visibility=list(reversed(entries)))
            generate_observed_output(doc, second, working_copy_path="/work/model.FCStd", working_copy_sha256="hash", output_directory=directory)
            self.assertEqual(output.read_bytes(), initial)
            parsed = json.loads(initial)
            self.assertEqual(parsed["schemaVersion"], "1.0")
            self.assertEqual(parsed["workingCopy"], {"path": "/work/model.FCStd", "sha256": "hash"})
            self.assertEqual([item["object"] for item in parsed["observation"]["targetState"]["visibility"]], ["Z", "B", "b"])
            self.assertEqual(list(Path(directory).iterdir()), [output])

    def test_failure_preserves_stale_file_and_never_fabricates_evidence(self):
        class Broken:
            def getObject(self, name):
                raise RuntimeError("lookup failed")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "prm.observed.json"
            output.write_bytes(b"stale")
            for invalid in (request(existence=[identity(object_name=" Bad")]), request(existence=[identity()])):
                document = Document({}) if invalid["observationContext"]["targetState"]["existence"][0]["object"] == " Bad" else Broken()
                with self.assertRaises(ObservedOutputError):
                    generate_observed_output(document, invalid, working_copy_path="/work/model.FCStd", working_copy_sha256="hash", output_directory=directory)
                self.assertEqual(output.read_bytes(), b"stale")
                self.assertEqual(list(Path(directory).iterdir()), [output])

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ObservedOutputError):
                generate_observed_output(
                    Broken(), request(existence=[identity()]),
                    working_copy_path="/work/model.FCStd", working_copy_sha256="hash", output_directory=directory,
                )
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
