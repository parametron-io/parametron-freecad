"""Native occurrence evidence classification and determinism tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.runtime.occurrence_access import (
    OccurrenceNativeAccessError,
)
from parametron_freecad.runtime.occurrence_evidence import (
    CLASSIFICATION_AUXILIARY,
    CLASSIFICATION_OCCURRENCE,
    CLASSIFICATION_UNRESOLVED,
    CLASSIFICATION_UNSUPPORTED,
    COMPLETENESS_COMPLETE,
    COMPLETENESS_INCOMPLETE,
    COMPLETENESS_UNAVAILABLE,
    COMPLETENESS_UNSUPPORTED,
    OCCURRENCE_EVIDENCE_FILENAME,
    RESOLUTION_RESOLVED,
    DeclaredResourceBinding,
    DeclaredResourceResolver,
    inspect_occurrence_evidence,
    prepare_occurrence_evidence,
    resolver_from_inventory,
    write_occurrence_evidence,
)
from parametron_freecad.runtime.occurrence_request import (
    OCCURRENCE_MECHANISM_DIRECT_MEMBER,
    OCCURRENCE_REQUEST_FILENAME,
    load_occurrence_request,
)
from parametron_freecad.runtime.resource_inventory import load_resource_inventory

_SOURCE_COORDINATE = "assembly-root.FCStd"
_COMPONENT_A_COORDINATE = "resources/component-a.FCStd"
_COMPONENT_B_COORDINATE = "resources/component-b.FCStd"
_MISSING_COORDINATE = "resources/missing-component.FCStd"


class _FakeDocument:
    def __init__(self, file_name: str | Path) -> None:
        self.FileName = str(file_name)
        self._objects: dict[str, object] = {}

    def add(self, native_object: "_FakeNativeObject") -> "_FakeNativeObject":
        native_object.Document = self
        self._objects[native_object.Name] = native_object
        return native_object

    def getObject(self, name: str) -> object | None:
        return self._objects.get(name)


class _FakeNativeObject:
    def __init__(self, document: _FakeDocument, name: str, type_id: str) -> None:
        self.Document = document
        self.Name = name
        self.TypeId = type_id
        self.InList: list[object] = []
        self._valid = True

    def isValid(self) -> bool:
        return self._valid


class _FakeAssembly(_FakeNativeObject):
    def __init__(self, document: _FakeDocument, name: str = "Assembly") -> None:
        super().__init__(document, name, "Assembly::AssemblyObject")
        self.Group: list[object] = []

    def add(self, member: object) -> object:
        self.Group.append(member)
        member.InList.append(self)
        return member


class _FakeJointGroup(_FakeNativeObject):
    def __init__(self, document: _FakeDocument, name: str = "Joints") -> None:
        super().__init__(document, name, "Assembly::JointGroup")
        self.Group: list[object] = []


class _FakeLink(_FakeNativeObject):
    def __init__(self, document: _FakeDocument, name: str) -> None:
        super().__init__(document, name, "App::Link")
        self.ElementCount = 0
        self.LinkedObject: object | None = None

    @property
    def isomorphic(self) -> bool:
        return True


class _FakeAssemblyLink(_FakeNativeObject):
    def __init__(self, document: _FakeDocument, name: str) -> None:
        super().__init__(document, name, "Assembly::AssemblyLink")


class _FakeLinkElement(_FakeNativeObject):
    def __init__(self, document: _FakeDocument, name: str) -> None:
        super().__init__(document, name, "App::LinkElement")


def _request(tmp_dir: Path, *, context: list[dict] | None = None) -> object:
    path = tmp_dir / OCCURRENCE_REQUEST_FILENAME
    path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "requirement": "optional",
                "scope": {
                    "parent": {
                        "resource": {
                            "projectId": "project",
                            "kind": "model",
                            "logicalId": "assembly_root",
                        },
                        "nativeKind": "object",
                        "name": "Assembly",
                    },
                    "context": context or [],
                    "mechanism": OCCURRENCE_MECHANISM_DIRECT_MEMBER,
                },
            }
        ),
        encoding="utf-8",
    )
    return load_occurrence_request(path)


def _workspace(
    tmp_dir: Path,
    coordinates: tuple[str, ...],
) -> None:
    for coordinate in coordinates:
        path = tmp_dir / coordinate
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"native-document")


def _resolver(
    tmp_dir: Path,
    *,
    include_missing: bool = False,
) -> DeclaredResourceResolver:
    logical_by_coordinate = {
        _SOURCE_COORDINATE: "assembly_root",
        _COMPONENT_A_COORDINATE: "component_a",
        _COMPONENT_B_COORDINATE: "component_b",
        _MISSING_COORDINATE: "missing_component",
    }
    coordinates = [
        _SOURCE_COORDINATE,
        _COMPONENT_A_COORDINATE,
        _COMPONENT_B_COORDINATE,
    ]
    if include_missing:
        coordinates.append(_MISSING_COORDINATE)
    _workspace(tmp_dir, tuple(coordinates))
    (tmp_dir / _MISSING_COORDINATE).unlink(missing_ok=True)
    bindings = tuple(
        DeclaredResourceBinding(
            project_id="project",
            kind="model",
            logical_id=logical_by_coordinate[coordinate],
            coordinate=coordinate,
            resolved_path=(tmp_dir / coordinate).resolve(),
        )
        for coordinate in coordinates
    )
    return DeclaredResourceResolver(
        bindings=bindings,
        source_binding=bindings[0],
    )


class OccurrenceEvidenceTests(unittest.TestCase):
    def _component(
        self,
        document: _FakeDocument,
        name: str = "Body",
        type_id: str = "PartDesign::Body",
    ) -> _FakeNativeObject:
        return document.add(_FakeNativeObject(document, name, type_id))

    def _assembly(self, document: _FakeDocument) -> _FakeAssembly:
        assembly = _FakeAssembly(document)
        document.add(assembly)
        return assembly

    def test_ten_supported_links_remain_distinct_occurrences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            assembly = self._assembly(source_document)
            component_a = _FakeDocument(root / _COMPONENT_A_COORDINATE)
            body = self._component(component_a)
            for index in range(10):
                link = _FakeLink(source_document, f"Link{index:02d}")
                link.LinkedObject = body
                assembly.add(link)

            observation = inspect_occurrence_evidence(
                source_document,
                _request(root),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            )

        payload = observation.to_payload()
        self.assertEqual(observation.completeness, COMPLETENESS_COMPLETE)
        self.assertTrue(observation.inspection_completed)
        self.assertEqual(payload["schemaVersion"], "1.1")
        self.assertEqual(payload["kind"], "native_occurrence_evidence")
        self.assertEqual(payload["freecadVersion"], "1.1.4")
        self.assertEqual(payload["parent"]["document"], _SOURCE_COORDINATE)
        self.assertEqual(payload["parent"]["nativeType"], "Assembly::AssemblyObject")
        self.assertEqual(payload["diagnostics"], [])
        self.assertEqual(
            [member["name"] for member in payload["members"]],
            [f"Link{index:02d}" for index in range(10)],
        )
        for member in payload["members"]:
            self.assertEqual(member["classification"], CLASSIFICATION_OCCURRENCE)
            self.assertEqual(member["resolution"], RESOLUTION_RESOLVED)
            self.assertTrue(member["membershipCorroborated"])
            self.assertTrue(member["nativeStateValid"])
            self.assertEqual(member["elementCount"], 0)
            self.assertEqual(
                member["target"],
                {
                    "entity": {
                        "resource": {
                            "projectId": "project",
                            "kind": "model",
                            "logicalId": "component_a",
                        },
                        "nativeKind": "object",
                        "name": "Body",
                    },
                    "document": _COMPONENT_A_COORDINATE,
                    "nativeType": "PartDesign::Body",
                },
            )
        self.assertNotIn("quantity", dumps_canonical(payload))

    def test_shared_target_is_distinguished_by_member_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            assembly = self._assembly(source_document)
            body = self._component(_FakeDocument(root / _COMPONENT_A_COORDINATE))
            for name in ("SharedSourceA", "SharedSourceB"):
                link = _FakeLink(source_document, name)
                link.LinkedObject = body
                assembly.add(link)

            payload = inspect_occurrence_evidence(
                source_document,
                _request(root),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            ).to_payload()

        first, second = payload["members"]
        self.assertNotEqual(first["name"], second["name"])
        self.assertEqual(first["target"], second["target"])

    def test_duplicate_native_names_join_separate_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            assembly = self._assembly(source_document)
            body_a = self._component(_FakeDocument(root / _COMPONENT_A_COORDINATE))
            body_b = self._component(_FakeDocument(root / _COMPONENT_B_COORDINATE))
            for name, target in (("FromA", body_a), ("FromB", body_b)):
                link = _FakeLink(source_document, name)
                link.LinkedObject = target
                assembly.add(link)

            payload = inspect_occurrence_evidence(
                source_document,
                _request(root),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            ).to_payload()

        from_a, from_b = payload["members"]
        self.assertEqual(from_a["target"]["entity"]["name"], "Body")
        self.assertEqual(from_b["target"]["entity"]["name"], "Body")
        self.assertEqual(
            from_a["target"]["entity"]["resource"]["logicalId"], "component_a"
        )
        self.assertEqual(
            from_b["target"]["entity"]["resource"]["logicalId"], "component_b"
        )

    def test_mixed_inventory_reports_explicit_incomplete_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root, include_missing=True)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            assembly = self._assembly(source_document)
            body_a = self._component(_FakeDocument(root / _COMPONENT_A_COORDINATE))
            component_b = _FakeDocument(root / _COMPONENT_B_COORDINATE)
            body_b = self._component(component_b)
            part_b = self._component(component_b, "Part", "App::Part")
            missing_document = _FakeDocument(root / _MISSING_COORDINATE)
            placeholder = self._component(missing_document)

            for name, target in (
                ("SharedA", body_a),
                ("CrossResourceBody", body_b),
                ("PartLink", part_b),
                ("MissingTarget", placeholder),
            ):
                link = _FakeLink(source_document, name)
                link.LinkedObject = target
                assembly.add(link)

            array = _FakeLink(source_document, "ArrayLink")
            array.LinkedObject = body_a
            array.ElementCount = 2
            assembly.add(array)
            assembly.add(_FakeAssemblyLink(source_document, "NestedLink"))
            assembly.add(_FakeAssembly(source_document, "NestedObjectMember"))
            assembly.add(_FakeLinkElement(source_document, "LinkElement"))
            assembly.add(_FakeJointGroup(source_document, "Joints"))

            observation = inspect_occurrence_evidence(
                source_document,
                _request(root),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            )

        payload = observation.to_payload()
        members = {member["name"]: member for member in payload["members"]}
        self.assertEqual(observation.completeness, COMPLETENESS_INCOMPLETE)
        self.assertTrue(observation.inspection_completed)
        self.assertTrue(payload["diagnostics"])
        self.assertEqual(
            members["SharedA"]["classification"], CLASSIFICATION_OCCURRENCE
        )
        self.assertEqual(
            members["CrossResourceBody"]["target"]["entity"]["resource"]["logicalId"],
            "component_b",
        )
        self.assertEqual(members["PartLink"]["target"]["nativeType"], "App::Part")
        self.assertEqual(
            members["MissingTarget"]["classification"], CLASSIFICATION_UNRESOLVED
        )
        self.assertFalse(members["MissingTarget"]["nativeStateValid"])
        self.assertEqual(
            members["ArrayLink"]["classification"], CLASSIFICATION_UNSUPPORTED
        )
        self.assertEqual(
            members["NestedLink"]["classification"], CLASSIFICATION_UNSUPPORTED
        )
        self.assertEqual(
            members["NestedObjectMember"]["classification"],
            CLASSIFICATION_UNSUPPORTED,
        )
        self.assertEqual(
            members["LinkElement"]["classification"], CLASSIFICATION_UNSUPPORTED
        )
        self.assertEqual(members["Joints"]["classification"], CLASSIFICATION_AUXILIARY)
        self.assertEqual(
            members["Joints"]["contents"],
            {"inspectionCompleted": True, "group": []},
        )

    def test_non_empty_joint_group_is_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            assembly = self._assembly(source_document)
            joints = _FakeJointGroup(source_document, "Joints")
            joints.Group.append(
                _FakeNativeObject(source_document, "Joint", "Assembly::Joint")
            )
            assembly.add(joints)

            payload = inspect_occurrence_evidence(
                source_document,
                _request(root),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            ).to_payload()

        member = payload["members"][0]
        self.assertEqual(member["classification"], CLASSIFICATION_UNSUPPORTED)
        self.assertNotIn("contents", member)
        self.assertIn("non-empty joint group", member["diagnostic"])

    def test_unsupported_target_type_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            assembly = self._assembly(source_document)
            component_a = _FakeDocument(root / _COMPONENT_A_COORDINATE)
            marker = self._component(component_a, "Marker", "App::FeaturePython")
            link = _FakeLink(source_document, "MarkerLink")
            link.LinkedObject = marker
            assembly.add(link)

            payload = inspect_occurrence_evidence(
                source_document,
                _request(root),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            ).to_payload()

        self.assertEqual(
            payload["members"][0]["classification"], CLASSIFICATION_UNSUPPORTED
        )

    def test_missing_target_is_unresolved_despite_valid_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root, include_missing=True)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            assembly = self._assembly(source_document)
            missing_document = _FakeDocument(root / _MISSING_COORDINATE)
            placeholder = self._component(missing_document)
            self.assertTrue(placeholder.isValid())
            link = _FakeLink(source_document, "MissingTarget")
            link.LinkedObject = placeholder
            assembly.add(link)

            payload = inspect_occurrence_evidence(
                source_document,
                _request(root),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            ).to_payload()

        member = payload["members"][0]
        self.assertEqual(member["classification"], CLASSIFICATION_UNRESOLVED)
        self.assertFalse(member["nativeStateValid"])
        self.assertIn("is missing", member["diagnostic"])

    def test_ordinary_property_link_list_is_not_an_occurrence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            assembly = self._assembly(source_document)
            holder = _FakeNativeObject(source_document, "Holder", "App::FeaturePython")
            holder.References = [
                self._component(source_document, "Internal", "PartDesign::Body")
            ]
            source_document.add(holder)
            body = self._component(_FakeDocument(root / _COMPONENT_A_COORDINATE))
            link = _FakeLink(source_document, "Link")
            link.LinkedObject = body
            assembly.add(link)

            payload = inspect_occurrence_evidence(
                source_document,
                _request(root),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            ).to_payload()

        self.assertEqual(payload["group"], ["Link"])
        self.assertEqual([member["name"] for member in payload["members"]], ["Link"])

    def test_non_empty_context_is_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            self._assembly(source_document)
            payload = inspect_occurrence_evidence(
                source_document,
                _request(
                    root,
                    context=[
                        {
                            "parent": {
                                "resource": {
                                    "projectId": "project",
                                    "kind": "model",
                                    "logicalId": "nested",
                                },
                                "nativeKind": "object",
                                "name": "Nested",
                            },
                            "member": "NestedLink",
                        }
                    ],
                ),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            ).to_payload()

        self.assertEqual(payload["completeness"], COMPLETENESS_UNSUPPORTED)
        self.assertFalse(payload["inspectionCompleted"])
        self.assertEqual(payload["group"], [])
        self.assertEqual(payload["members"], [])
        self.assertTrue(payload["diagnostics"])
        self.assertEqual(payload["parent"]["document"], _SOURCE_COORDINATE)

    def test_unsupported_version_and_mechanism_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            self._assembly(source_document)
            for version in ("1.1.3", "unavailable"):
                with self.subTest(version=version):
                    payload = inspect_occurrence_evidence(
                        source_document,
                        _request(root),
                        source_document=_SOURCE_COORDINATE,
                        resolver=resolver,
                        freecad_version=version,
                    ).to_payload()
                    self.assertEqual(payload["completeness"], COMPLETENESS_UNSUPPORTED)
                    self.assertEqual(payload["members"], [])

    def test_missing_parent_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)

            payload = inspect_occurrence_evidence(
                source_document,
                _request(root),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            ).to_payload()

        self.assertEqual(payload["completeness"], COMPLETENESS_UNAVAILABLE)
        self.assertIsNone(payload["parent"])
        self.assertFalse(payload["inspectionCompleted"])
        self.assertEqual(payload["group"], [])
        self.assertEqual(payload["members"], [])
        self.assertTrue(payload["diagnostics"])

    def test_non_assembly_parent_is_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            source_document.add(
                _FakeNativeObject(source_document, "Assembly", "App::Part")
            )
            payload = inspect_occurrence_evidence(
                source_document,
                _request(root),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            ).to_payload()

        self.assertEqual(payload["completeness"], COMPLETENESS_UNSUPPORTED)
        self.assertEqual(payload["members"], [])

    def test_dangling_group_entry_is_a_native_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            assembly = self._assembly(source_document)
            assembly.Group.append(None)
            with self.assertRaises(OccurrenceNativeAccessError):
                inspect_occurrence_evidence(
                    source_document,
                    _request(root),
                    source_document=_SOURCE_COORDINATE,
                    resolver=resolver,
                    freecad_version="1.1.4",
                )

    def test_uncorroborated_group_entry_is_a_native_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            assembly = self._assembly(source_document)
            orphan = _FakeLink(source_document, "Orphan")
            assembly.Group.append(orphan)
            with self.assertRaises(OccurrenceNativeAccessError):
                inspect_occurrence_evidence(
                    source_document,
                    _request(root),
                    source_document=_SOURCE_COORDINATE,
                    resolver=resolver,
                    freecad_version="1.1.4",
                )

    def test_repeated_and_relocated_runs_are_byte_stable(self) -> None:
        def render(base: Path) -> bytes:
            resolver = _resolver(base)
            source_document = _FakeDocument(base / _SOURCE_COORDINATE)
            assembly = self._assembly(source_document)
            body = self._component(_FakeDocument(base / _COMPONENT_A_COORDINATE))
            for name in ("Second", "First", "Third"):
                link = _FakeLink(source_document, name)
                link.LinkedObject = body
                assembly.add(link)
            return dumps_canonical(
                inspect_occurrence_evidence(
                    source_document,
                    _request(base),
                    source_document=_SOURCE_COORDINATE,
                    resolver=resolver,
                    freecad_version="1.1.4",
                ).to_payload()
            ).encode("utf-8")

        with (
            tempfile.TemporaryDirectory() as first,
            tempfile.TemporaryDirectory() as second,
        ):
            first_bytes = render(Path(first))
            repeated = render(Path(first))
            relocated = render(Path(second))

        self.assertEqual(first_bytes, repeated)
        self.assertEqual(first_bytes, relocated)
        payload = json.loads(first_bytes)
        self.assertEqual(payload["group"], ["First", "Second", "Third"])

    def test_inventory_resolver_requires_selected_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _workspace(root, (_SOURCE_COORDINATE,))
            request_path = root / "prm.integrity-request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "1.0",
                        "resources": [
                            {
                                "logicalId": "assembly_root",
                                "kind": "model",
                                "materializedCoordinate": _SOURCE_COORDINATE,
                                "baselineSha256": "0" * 64,
                                "expectsPersistedResult": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            inventory = load_resource_inventory(
                request_path,
                working_copy=root,
                expected_source_path=root / _SOURCE_COORDINATE,
            )
            resolver = resolver_from_inventory(inventory, project_id="project")

        self.assertEqual(resolver.source_binding.logical_id, "assembly_root")
        self.assertEqual(resolver.source_binding.coordinate, _SOURCE_COORDINATE)

    def test_writer_removes_stale_sidecar_and_writes_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolver = _resolver(root)
            outputs = root / "outputs"
            outputs.mkdir()
            stale = outputs / OCCURRENCE_EVIDENCE_FILENAME
            stale.write_bytes(b"stale")
            source_document = _FakeDocument(root / _SOURCE_COORDINATE)
            self._assembly(source_document)
            observation = inspect_occurrence_evidence(
                source_document,
                _request(root),
                source_document=_SOURCE_COORDINATE,
                resolver=resolver,
                freecad_version="1.1.4",
            )

            prepare_occurrence_evidence(working_copy=root, output_directory=outputs)
            self.assertFalse(stale.exists())
            target = write_occurrence_evidence(
                observation,
                working_copy=root,
                output_directory=outputs,
            )
            content = target.read_bytes()

        self.assertEqual(target.name, OCCURRENCE_EVIDENCE_FILENAME)
        self.assertTrue(content.endswith(b"\n"))
        self.assertFalse(content.endswith(b"\n\n"))
        self.assertEqual(content, dumps_canonical(observation.to_payload()).encode())


if __name__ == "__main__":
    unittest.main()
