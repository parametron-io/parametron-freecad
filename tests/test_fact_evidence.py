"""Native fact evidence classification, availability, and determinism tests."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.runtime.fact_evidence import (
    FACT_AVAILABILITY_OBSERVED,
    FACT_AVAILABILITY_UNAVAILABLE,
    FACT_AVAILABILITY_UNSUPPORTED,
    FACT_EVIDENCE_FILENAME,
    RequiredFactUnavailableError,
    inspect_fact_evidence,
    prepare_fact_evidence,
    write_fact_evidence,
)
from parametron_freecad.runtime.fact_request import (
    FACT_REQUEST_FILENAME,
    load_fact_request,
)
from parametron_freecad.runtime.resource_inventory import load_resource_inventory

_SOURCE_COORDINATE = "source/Facts.FCStd"
_SECONDARY_COORDINATE = "resources/Secondary.FCStd"


class _FakeUnit:
    def __init__(self, token: str) -> None:
        self._token = token

    def __str__(self) -> str:
        return f"Unit: {self._token} (1,0,0,0,0,0,0,0) [Length]"


class _FakeQuantity:
    def __init__(self, value: float, unit: str = "mm") -> None:
        self.Value = value
        self.Unit = _FakeUnit(unit)


class _FakeNativeObject:
    def __init__(self, name: str, type_id: str) -> None:
        self.Name = name
        self.TypeId = type_id
        self._properties: dict[str, object] = {}

    @property
    def PropertiesList(self) -> list[str]:
        return list(self._properties)

    def set(self, name: str, value: object) -> None:
        self._properties[name] = value

    def __getattr__(self, name: str) -> object:
        properties = self.__dict__.get("_properties", {})
        if name in properties:
            return properties[name]
        raise AttributeError(name)


class _FakeDocument:
    def __init__(self, file_name: str | Path) -> None:
        self.FileName = str(file_name)
        self.Name = Path(file_name).stem
        self._objects: dict[str, object] = {}
        self.save_calls = 0
        self.recompute_calls = 0

    def add(self, native_object: _FakeNativeObject) -> _FakeNativeObject:
        self._objects[native_object.Name] = native_object
        return native_object

    def getObject(self, name: str) -> object | None:
        return self._objects.get(name)

    def save(self) -> None:
        self.save_calls += 1

    def recompute(self) -> None:
        self.recompute_calls += 1


class _FakeFreeCADModule:
    def __init__(self) -> None:
        self.documents_by_path: dict[Path, _FakeDocument] = {}
        self.open_documents: dict[str, _FakeDocument] = {}
        self.open_calls: list[str] = []
        self.close_calls: list[str] = []

    def Version(self) -> tuple[str, str, str]:
        return ("1", "1", "4")

    def register(self, document: _FakeDocument) -> None:
        self.documents_by_path[Path(document.FileName).resolve()] = document

    def openDocument(self, path: str) -> _FakeDocument:
        self.open_calls.append(path)
        document = self.documents_by_path[Path(path).resolve()]
        self.open_documents[document.Name] = document
        return document

    def closeDocument(self, name: str) -> None:
        self.close_calls.append(name)
        self.open_documents.pop(name, None)

    def listDocuments(self) -> tuple[str, ...]:
        return tuple(sorted(self.open_documents))

    def getDocument(self, name: str) -> _FakeDocument | None:
        return self.open_documents.get(name)


def _write_workspace(tmp_dir: Path, coordinates: tuple[str, ...]) -> None:
    for coordinate in coordinates:
        path = tmp_dir / coordinate
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"native-document")


def _inventory(
    tmp_dir: Path,
    entries: tuple[tuple[str, str], ...],
) -> object:
    ordered = sorted(entries, key=lambda item: item[0])
    _write_workspace(tmp_dir, tuple(coordinate for _, coordinate in ordered))
    resources = []
    for index, (logical_id, coordinate) in enumerate(ordered):
        resources.append(
            {
                "logicalId": logical_id,
                "kind": "model",
                "materializedCoordinate": coordinate,
                "baselineSha256": hashlib.sha256(
                    (tmp_dir / coordinate).read_bytes()
                ).hexdigest(),
                "expectsPersistedResult": index == 0,
            }
        )
    request_path = tmp_dir / "prm.integrity-request.json"
    request_path.write_text(
        json.dumps({"schemaVersion": "1.0", "resources": resources}),
        encoding="utf-8",
    )
    return load_resource_inventory(request_path, working_copy=tmp_dir)


def _subject(
    logical_id: str,
    name: str,
    *,
    project_id: str = "project",
) -> dict[str, object]:
    return {
        "resource": {
            "projectId": project_id,
            "kind": "model",
            "logicalId": logical_id,
        },
        "nativeKind": "object",
        "name": name,
    }


def _binding(
    logical_id: str,
    name: str,
    property_name: str,
    value_kind: str,
    *,
    unit: str | None = None,
    requirement: str = "optional",
    context: list[dict] | None = None,
) -> dict[str, object]:
    binding: dict[str, object] = {
        "kind": "bound_property",
        "subject": _subject(logical_id, name),
        "context": context or [],
        "property": property_name,
        "valueKind": value_kind,
        "requirement": requirement,
    }
    if unit is not None:
        binding["unit"] = unit
    return binding


def _request(tmp_dir: Path, bindings: list[dict[str, object]]) -> object:
    path = tmp_dir / FACT_REQUEST_FILENAME
    path.write_text(
        json.dumps({"schemaVersion": "1.0", "bindings": bindings}),
        encoding="utf-8",
    )
    return load_fact_request(path)


def _source_document(tmp_dir: Path) -> _FakeDocument:
    document = _FakeDocument(tmp_dir / _SOURCE_COORDINATE)
    box = _FakeNativeObject("Box", "Part::Box")
    box.set("Length", _FakeQuantity(10.0, "mm"))
    props = _FakeNativeObject("Props", "App::FeaturePython")
    props.set("Ratio", 3.25)
    props.set("Count", 42)
    props.set("Enabled", True)
    props.set("PlainText", "bounded string")
    props.set("SpecialText", "a<&>\u2028b")
    props.set("EmptyText", "")
    props.set("NonIntegral", 4.5)
    props.set("NotANumber", "text")
    props.set("PositiveInfinity", float("inf"))
    document.add(box)
    document.add(props)
    return document


def _facts_by_property(payload: dict) -> dict[tuple[str, str], dict]:
    return {
        (fact["subject"]["entity"]["name"], fact["property"]): fact
        for fact in payload["facts"]
    }


class FactEvidenceTests(unittest.TestCase):
    def test_observes_typed_scalars_with_explicit_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _inventory(root, (("source", _SOURCE_COORDINATE),))
            document = _source_document(root)
            request = _request(
                root,
                [
                    _binding("source", "Box", "Length", "number", unit="mm"),
                    _binding("source", "Props", "Ratio", "number"),
                    _binding("source", "Props", "Count", "integer"),
                    _binding("source", "Props", "Enabled", "boolean"),
                    _binding("source", "Props", "PlainText", "string"),
                    _binding("source", "Props", "EmptyText", "string"),
                ],
            )

            payload = inspect_fact_evidence(
                document,
                request,
                source_path=root / _SOURCE_COORDINATE,
                inventory=inventory,
                freecad_module=_FakeFreeCADModule(),
                freecad_version="1.1.4",
            ).to_payload()

        facts = _facts_by_property(payload)
        self.assertEqual(payload["schemaVersion"], "1.0")
        self.assertEqual(payload["kind"], "native_fact_evidence")
        self.assertEqual(payload["freecadVersion"], "1.1.4")

        self.assertEqual(
            facts[("Box", "Length")]["availability"],
            FACT_AVAILABILITY_OBSERVED,
        )
        self.assertEqual(facts[("Box", "Length")]["valueKind"], "number")
        self.assertEqual(facts[("Box", "Length")]["value"], 10.0)
        self.assertEqual(facts[("Box", "Length")]["unit"], "mm")
        self.assertEqual(
            facts[("Box", "Length")]["subject"]["document"],
            _SOURCE_COORDINATE,
        )
        self.assertEqual(facts[("Box", "Length")]["subject"]["nativeType"], "Part::Box")

        self.assertEqual(facts[("Props", "Ratio")]["valueKind"], "number")
        self.assertEqual(facts[("Props", "Ratio")]["value"], 3.25)
        self.assertNotIn("unit", facts[("Props", "Ratio")])

        self.assertEqual(facts[("Props", "Count")]["valueKind"], "integer")
        self.assertEqual(facts[("Props", "Count")]["value"], 42)
        self.assertEqual(facts[("Props", "Enabled")]["valueKind"], "boolean")
        self.assertIs(facts[("Props", "Enabled")]["value"], True)
        self.assertEqual(facts[("Props", "PlainText")]["valueKind"], "string")
        self.assertEqual(facts[("Props", "PlainText")]["value"], "bounded string")
        self.assertEqual(facts[("Props", "EmptyText")]["value"], "")

    def test_unavailable_and_unsupported_never_substitute_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _inventory(root, (("source", _SOURCE_COORDINATE),))
            document = _source_document(root)
            request = _request(
                root,
                [
                    _binding("source", "Props", "Missing", "number"),
                    _binding("source", "Ghost", "Length", "number"),
                    _binding("source", "Props", "SpecialText", "string"),
                    _binding("source", "Box", "Length", "number", unit="kg"),
                    _binding("source", "Props", "NonIntegral", "integer"),
                    _binding("source", "Props", "NotANumber", "number"),
                    _binding("source", "Props", "PositiveInfinity", "number"),
                ],
            )

            payload = inspect_fact_evidence(
                document,
                request,
                source_path=root / _SOURCE_COORDINATE,
                inventory=inventory,
                freecad_module=_FakeFreeCADModule(),
                freecad_version="1.1.4",
            ).to_payload()

        facts = _facts_by_property(payload)
        expected = {
            ("Props", "Missing"): FACT_AVAILABILITY_UNAVAILABLE,
            ("Ghost", "Length"): FACT_AVAILABILITY_UNAVAILABLE,
            ("Props", "SpecialText"): FACT_AVAILABILITY_UNSUPPORTED,
            ("Box", "Length"): FACT_AVAILABILITY_UNSUPPORTED,
            ("Props", "NonIntegral"): FACT_AVAILABILITY_UNSUPPORTED,
            ("Props", "NotANumber"): FACT_AVAILABILITY_UNSUPPORTED,
            ("Props", "PositiveInfinity"): FACT_AVAILABILITY_UNSUPPORTED,
        }
        for key, availability in expected.items():
            with self.subTest(key=key):
                fact = facts[key]
                self.assertEqual(fact["availability"], availability)
                self.assertNotIn("value", fact)
                self.assertNotIn("valueKind", fact)
                self.assertTrue(fact["diagnostic"])
        self.assertEqual(facts[("Ghost", "Length")]["subject"]["nativeType"], "")
        self.assertEqual(
            facts[("Ghost", "Length")]["subject"]["document"],
            _SOURCE_COORDINATE,
        )
        self.assertIn("disagrees", facts[("Box", "Length")]["diagnostic"])
        self.assertIn(
            "non-finite",
            facts[("Props", "PositiveInfinity")]["diagnostic"],
        )

    def test_required_unavailable_fact_fails_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _inventory(root, (("source", _SOURCE_COORDINATE),))
            request = _request(
                root,
                [
                    _binding(
                        "source",
                        "Props",
                        "Missing",
                        "number",
                        requirement="required",
                    )
                ],
            )
            with self.assertRaises(RequiredFactUnavailableError):
                inspect_fact_evidence(
                    _source_document(root),
                    request,
                    source_path=root / _SOURCE_COORDINATE,
                    inventory=inventory,
                    freecad_module=_FakeFreeCADModule(),
                    freecad_version="1.1.4",
                )

    def test_context_binding_is_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _inventory(root, (("source", _SOURCE_COORDINATE),))
            # A context frame may not repeat the subject entity, so use a
            # distinct parent identity. The context itself is unsupported.
            context = [
                {
                    "parent": _subject("secondary", "SecondaryProps"),
                    "member": "Link",
                }
            ]
            request = _request(
                root,
                [
                    _binding(
                        "source",
                        "Props",
                        "Ratio",
                        "number",
                        context=context,
                    )
                ],
            )

            payload = inspect_fact_evidence(
                _source_document(root),
                request,
                source_path=root / _SOURCE_COORDINATE,
                inventory=inventory,
                freecad_module=_FakeFreeCADModule(),
                freecad_version="1.1.4",
            ).to_payload()

        fact = payload["facts"][0]
        self.assertEqual(fact["availability"], FACT_AVAILABILITY_UNSUPPORTED)
        self.assertIn("context", fact["diagnostic"])
        self.assertNotIn("value", fact)

    def test_secondary_resource_is_opened_read_only_and_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _inventory(
                root,
                (("source", _SOURCE_COORDINATE), ("secondary", _SECONDARY_COORDINATE)),
            )
            module = _FakeFreeCADModule()
            secondary = _FakeDocument(root / _SECONDARY_COORDINATE)
            secondary_props = _FakeNativeObject("SecondaryProps", "App::FeaturePython")
            secondary_props.set("SecondaryLength", _FakeQuantity(20.0, "mm"))
            secondary.add(secondary_props)
            module.register(secondary)
            request = _request(
                root,
                [
                    _binding(
                        "secondary",
                        "SecondaryProps",
                        "SecondaryLength",
                        "number",
                        unit="mm",
                    )
                ],
            )

            payload = inspect_fact_evidence(
                _source_document(root),
                request,
                source_path=root / _SOURCE_COORDINATE,
                inventory=inventory,
                freecad_module=module,
                freecad_version="1.1.4",
            ).to_payload()

        fact = payload["facts"][0]
        self.assertEqual(fact["availability"], FACT_AVAILABILITY_OBSERVED)
        self.assertEqual(fact["value"], 20.0)
        self.assertEqual(fact["unit"], "mm")
        self.assertEqual(fact["subject"]["document"], _SECONDARY_COORDINATE)
        self.assertEqual(module.open_calls, [str(root / _SECONDARY_COORDINATE)])
        self.assertEqual(module.close_calls, [secondary.Name])
        self.assertEqual(secondary.save_calls, 0)
        self.assertEqual(secondary.recompute_calls, 0)

    def test_missing_inventory_reports_explicit_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_workspace(root, (_SOURCE_COORDINATE,))
            request = _request(
                root,
                [_binding("source", "Props", "Ratio", "number")],
            )
            payload = inspect_fact_evidence(
                _source_document(root),
                request,
                source_path=root / _SOURCE_COORDINATE,
                inventory=None,
                freecad_module=_FakeFreeCADModule(),
                freecad_version="1.1.4",
            ).to_payload()

        fact = payload["facts"][0]
        self.assertEqual(fact["availability"], FACT_AVAILABILITY_UNAVAILABLE)
        self.assertEqual(fact["subject"]["document"], "")
        self.assertEqual(fact["subject"]["nativeType"], "")
        self.assertIn("inventory", fact["diagnostic"])
        self.assertNotIn("value", fact)

    def test_missing_declared_coordinate_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _inventory(
                root,
                (("source", _SOURCE_COORDINATE), ("secondary", _SECONDARY_COORDINATE)),
            )
            (root / _SECONDARY_COORDINATE).unlink()
            module = _FakeFreeCADModule()
            request = _request(
                root,
                [
                    _binding(
                        "secondary",
                        "SecondaryProps",
                        "SecondaryLength",
                        "number",
                        unit="mm",
                    )
                ],
            )
            payload = inspect_fact_evidence(
                _source_document(root),
                request,
                source_path=root / _SOURCE_COORDINATE,
                inventory=inventory,
                freecad_module=module,
                freecad_version="1.1.4",
            ).to_payload()

        fact = payload["facts"][0]
        self.assertEqual(fact["availability"], FACT_AVAILABILITY_UNAVAILABLE)
        self.assertIn("missing", fact["diagnostic"])
        self.assertEqual(fact["subject"]["document"], _SECONDARY_COORDINATE)
        self.assertEqual(module.open_calls, [])

    def test_repeated_and_shuffled_requests_are_byte_stable(self) -> None:
        bindings = [
            _binding("source", "Props", "Ratio", "number"),
            _binding("source", "Props", "Count", "integer"),
            _binding("source", "Box", "Length", "number", unit="mm"),
        ]

        def render(order: list[dict[str, object]]) -> bytes:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                inventory = _inventory(root, (("source", _SOURCE_COORDINATE),))
                request = _request(root, order)
                return dumps_canonical(
                    inspect_fact_evidence(
                        _source_document(root),
                        request,
                        source_path=root / _SOURCE_COORDINATE,
                        inventory=inventory,
                        freecad_module=_FakeFreeCADModule(),
                        freecad_version="1.1.4",
                    ).to_payload()
                ).encode("utf-8")

        first = render(bindings)
        repeated = render(bindings)
        shuffled = render(list(reversed(bindings)))

        self.assertEqual(first, repeated)
        self.assertEqual(first, shuffled)
        payload = json.loads(first)
        self.assertEqual(
            [fact["property"] for fact in payload["facts"]],
            ["Length", "Count", "Ratio"],
        )

    def test_canonical_string_boundaries_are_explicit(self) -> None:
        supported = [
            "plain text",
            'quote"backslash\\',
            "line\nfeed",
            "tab\tseparated",
            "",
            "unicode-\u00e9",
            "control-\x01",
        ]
        unsupported = ["a<b", "a>b", "a&b", "line\u2028sep", "paragraph\u2029sep"]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = _inventory(root, (("source", _SOURCE_COORDINATE),))
            document = _source_document(root)
            props = document.getObject("Props")
            for index, value in enumerate(supported + unsupported):
                props.set(f"String{index}", value)
            bindings = [
                _binding("source", "Props", f"String{index}", "string")
                for index in range(len(supported) + len(unsupported))
            ]
            payload = inspect_fact_evidence(
                document,
                _request(root, bindings),
                source_path=root / _SOURCE_COORDINATE,
                inventory=inventory,
                freecad_module=_FakeFreeCADModule(),
                freecad_version="1.1.4",
            ).to_payload()

        facts = _facts_by_property(payload)
        for index, value in enumerate(supported):
            with self.subTest(value=value):
                self.assertEqual(
                    facts[("Props", f"String{index}")]["availability"],
                    FACT_AVAILABILITY_OBSERVED,
                )
                self.assertEqual(facts[("Props", f"String{index}")]["value"], value)
        for offset, value in enumerate(unsupported):
            index = len(supported) + offset
            with self.subTest(value=value):
                self.assertEqual(
                    facts[("Props", f"String{index}")]["availability"],
                    FACT_AVAILABILITY_UNSUPPORTED,
                )
                self.assertNotIn("value", facts[("Props", f"String{index}")])

    def test_writer_removes_stale_sidecar_and_writes_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outputs = root / "outputs"
            outputs.mkdir()
            stale = outputs / FACT_EVIDENCE_FILENAME
            stale.write_bytes(b"stale")
            inventory = _inventory(root, (("source", _SOURCE_COORDINATE),))
            observation = inspect_fact_evidence(
                _source_document(root),
                _request(
                    root,
                    [_binding("source", "Props", "Ratio", "number")],
                ),
                source_path=root / _SOURCE_COORDINATE,
                inventory=inventory,
                freecad_module=_FakeFreeCADModule(),
                freecad_version="1.1.4",
            )

            prepare_fact_evidence(working_copy=root, output_directory=outputs)
            self.assertFalse(stale.exists())
            target = write_fact_evidence(
                observation,
                working_copy=root,
                output_directory=outputs,
            )
            content = target.read_bytes()

        self.assertEqual(target.name, FACT_EVIDENCE_FILENAME)
        self.assertTrue(content.endswith(b"\n"))
        self.assertFalse(content.endswith(b"\n\n"))
        self.assertEqual(content, dumps_canonical(observation.to_payload()).encode())


if __name__ == "__main__":
    unittest.main()
