"""Ordinary-Python tests for FreeCAD-native capture discovery."""

from __future__ import annotations

import json
import unittest

from capture_discovery_support import (
    FakeDocument,
    FakeObject,
    FakeProperty,
    app_part,
    assembly_object,
    body,
    drawing_annotation,
    drawing_page,
    drawing_symbol,
    drawing_view,
    drawing_view_clip,
    pad,
    part_box,
    projection_group,
    projection_item,
    property_bool,
    property_float,
    property_integer,
    property_length,
    property_string,
    sketch,
    suppressed_property,
    var_set,
    visibility_property,
)

from parametron_freecad.capture import (
    CaptureDiscoveryDocumentError,
    CaptureDiscoveryInspectionError,
    discover_capture_candidates,
)


def _components(discovery) -> dict[str, object]:
    return {item.native_ref: item for item in discovery.components}


def _features(discovery) -> dict[str, object]:
    return {item.native_ref: item for item in discovery.features}


def _parameters(discovery) -> dict[str, object]:
    return {item.property.native_key: item for item in discovery.parameters}


def _metadata(discovery) -> dict[str, object]:
    return {item.property.native_key: item for item in discovery.metadata}


class SinglePartDiscoveryTests(unittest.TestCase):
    def _document(self) -> FakeDocument:
        body_object = body(
            "MetadataBody",
            properties={
                "material": property_string("PLA", group="Metadata"),
                "tagged": property_bool(False, group="Metadata"),
                "mass": property_float(1.5, group="Metadata"),
                "revision": property_integer(1, group="Metadata"),
                "tolerance": property_float(0.5, group="Metadata"),
                "sequence": property_integer(10, group="Metadata"),
                "measured_length": property_length(12.5, group="Metadata"),
                "readonly_meta": property_string(
                    "locked",
                    group="Metadata",
                    status=("ReadOnly",),
                ),
            },
        )
        sketch_object = sketch("ProfileSketch", in_list=[body_object])
        pad_object = pad("Pad", in_list=[body_object], out_list=[sketch_object])
        body_object.Group = [sketch_object, pad_object]
        body_object.OutList = [sketch_object, pad_object]
        sketch_object.InList = [body_object, pad_object]
        origin = FakeObject("Origin", "App::Origin")
        axis = FakeObject("X_Axis", "App::Line")
        return FakeDocument(
            "metadata_source",
            label="metadata-source",
            objects=[body_object, sketch_object, pad_object, origin, axis],
        )

    def test_single_part_document_synthesizes_root_assembly(self) -> None:
        discovery = discover_capture_candidates(self._document())

        self.assertEqual(discovery.document.name, "metadata_source")
        self.assertEqual(discovery.document.label, "metadata-source")
        self.assertEqual(discovery.document.object_count, 5)
        self.assertEqual(discovery.root_component_native_ref, "metadata_source")

        components = _components(discovery)
        self.assertEqual(set(components), {"metadata_source", "MetadataBody"})
        root = components["metadata_source"]
        self.assertTrue(root.synthetic)
        self.assertEqual(root.kind, "assembly")
        self.assertEqual(root.cad_type, "App::Document")
        self.assertIsNone(root.parent_native_ref)
        self.assertEqual(root.native_path, "metadata_source")
        self.assertEqual(root.quantity, 1)
        self.assertEqual(root.material, "")
        self.assertFalse(root.targetability.suppress)
        self.assertFalse(root.targetability.delete)

        body_component = components["MetadataBody"]
        self.assertFalse(body_component.synthetic)
        self.assertEqual(body_component.kind, "part")
        self.assertEqual(body_component.cad_type, "PartDesign::Body")
        self.assertEqual(body_component.parent_native_ref, "metadata_source")
        self.assertEqual(
            body_component.native_path,
            "metadata_source/MetadataBody",
        )

    def test_features_and_targetability_are_discovered(self) -> None:
        discovery = discover_capture_candidates(self._document())

        features = _features(discovery)
        self.assertEqual(set(features), {"Pad", "ProfileSketch"})
        self.assertEqual(
            features["Pad"].component_native_ref,
            "MetadataBody",
        )
        self.assertEqual(
            features["Pad"].native_path,
            "metadata_source/MetadataBody/Pad",
        )
        self.assertEqual(features["Pad"].owner_scoped_key, "Pad")
        self.assertTrue(features["Pad"].targetability.suppress)
        self.assertTrue(features["Pad"].targetability.unsuppress)
        self.assertTrue(features["Pad"].targetability.hide)
        self.assertFalse(features["Pad"].targetability.delete)
        self.assertEqual(
            features["Pad"].targetability.delete_dependents,
            ("MetadataBody",),
        )

        sketch_feature = features["ProfileSketch"]
        self.assertFalse(sketch_feature.targetability.suppress)
        self.assertTrue(sketch_feature.targetability.hide)
        self.assertFalse(sketch_feature.targetability.delete)
        self.assertEqual(
            sketch_feature.targetability.delete_dependents,
            ("MetadataBody", "Pad"),
        )

        body_component = _components(discovery)["MetadataBody"]
        self.assertFalse(body_component.targetability.suppress)
        self.assertTrue(body_component.targetability.hide)
        self.assertTrue(body_component.targetability.delete)
        self.assertEqual(body_component.targetability.delete_dependents, ())

    def test_metadata_candidates_preserve_support_and_capability(self) -> None:
        discovery = discover_capture_candidates(self._document())

        metadata = _metadata(discovery)
        self.assertEqual(
            set(metadata),
            {
                "mass",
                "material",
                "measured_length",
                "readonly_meta",
                "revision",
                "sequence",
                "tagged",
                "tolerance",
            },
        )
        for candidate in metadata.values():
            self.assertEqual(candidate.owner_kind, "component")
            self.assertEqual(candidate.owner_native_ref, "MetadataBody")
            self.assertEqual(candidate.component_native_ref, "MetadataBody")
            self.assertEqual(candidate.owner_scoped_key, candidate.property.native_key)

        self.assertEqual(metadata["material"].property.current_value, "PLA")
        self.assertEqual(metadata["material"].property.value_type, "string")
        self.assertTrue(metadata["material"].property.supported)
        self.assertTrue(metadata["material"].property.writable)

        self.assertIs(metadata["tagged"].property.current_value, False)
        self.assertEqual(metadata["tagged"].property.value_type, "boolean")
        self.assertTrue(metadata["tagged"].property.supported)

        self.assertEqual(metadata["mass"].property.native_value_kind, "float")
        self.assertEqual(metadata["revision"].property.native_value_kind, "integer")
        self.assertEqual(metadata["tolerance"].property.native_value_kind, "float")
        self.assertEqual(metadata["sequence"].property.native_value_kind, "integer")

        measured = metadata["measured_length"].property
        self.assertEqual(measured.native_type_id, "App::PropertyLength")
        self.assertEqual(measured.native_value_kind, "length")
        self.assertTrue(measured.native_readable)
        self.assertFalse(measured.supported)
        self.assertFalse(measured.observable)
        self.assertFalse(measured.writable)
        self.assertIsNone(measured.value_type)
        self.assertIsNone(measured.current_value)
        self.assertIsNone(measured.unit)
        self.assertEqual(
            measured.unsupported_reason,
            "unsupported_native_metadata_type",
        )

        readonly = metadata["readonly_meta"].property
        self.assertTrue(readonly.supported)
        self.assertTrue(readonly.observable)
        self.assertFalse(readonly.writable)
        self.assertEqual(readonly.property_status, ("ReadOnly",))

    def test_feature_metadata_and_document_metadata_are_discovered(self) -> None:
        document = self._document()
        sketch_object = next(
            item for item in document.Objects if item.Name == "ProfileSketch"
        )
        sketch_object._properties["feature_note"] = property_string(
            "feature",
            group="Metadata",
        )
        sketch_object.PropertiesList = list(sketch_object._properties)
        sketch_object._properties["_ExternalGeoVersion"] = property_integer(
            1,
            group="Compatibility",
            status=(24, 26),
        )
        sketch_object.PropertiesList = list(sketch_object._properties)
        document._properties["document_note"] = property_string(
            "document",
            group="Metadata",
        )
        document.PropertiesList = list(document._properties)

        discovery = discover_capture_candidates(document)

        metadata = _metadata(discovery)
        self.assertIn("feature_note", metadata)
        self.assertIn("document_note", metadata)
        self.assertNotIn("_ExternalGeoVersion", metadata)

        feature_note = metadata["feature_note"]
        self.assertEqual(feature_note.owner_kind, "feature")
        self.assertEqual(feature_note.owner_native_ref, "ProfileSketch")
        self.assertEqual(feature_note.component_native_ref, "MetadataBody")

        document_note = metadata["document_note"]
        self.assertEqual(document_note.owner_kind, "component")
        self.assertEqual(document_note.owner_native_ref, "metadata_source")
        self.assertEqual(document_note.component_native_ref, "metadata_source")

    def test_candidates_do_not_contain_semantic_names_or_ids(self) -> None:
        mapping = discover_capture_candidates(self._document()).to_mapping()

        for candidate in (
            mapping["components"]
            + mapping["features"]
            + mapping["parameterGroups"]
            + mapping["parameters"]
            + mapping["metadata"]
        ):
            self.assertNotIn("id", candidate)
            self.assertNotIn("name", candidate)
            self.assertNotIn("displayName", candidate)

    def test_discovery_does_not_mutate_fake_document(self) -> None:
        document = self._document()
        before = _document_snapshot(document)

        discover_capture_candidates(document)

        self.assertEqual(_document_snapshot(document), before)


class NaturalRootDiscoveryTests(unittest.TestCase):
    def test_app_part_is_used_as_natural_root(self) -> None:
        body_object = body("Body")
        pad_object = pad("Pad", in_list=[body_object])
        body_object.Group = [pad_object]
        body_object.OutList = [pad_object]
        box = part_box("Box", in_list=[])
        part = app_part("Assembly", group=[body_object, box])
        body_object.InList = [part]
        box.InList = [part]

        discovery = discover_capture_candidates(
            FakeDocument("natural_part", objects=[part, body_object, pad_object, box])
        )

        self.assertEqual(discovery.root_component_native_ref, "Assembly")
        components = _components(discovery)
        self.assertFalse(components["Assembly"].synthetic)
        self.assertEqual(components["Assembly"].kind, "assembly")
        self.assertIsNone(components["Assembly"].parent_native_ref)
        self.assertEqual(components["Body"].parent_native_ref, "Assembly")
        self.assertEqual(components["Box"].parent_native_ref, "Assembly")
        self.assertEqual(components["Body"].native_path, "Assembly/Body")
        self.assertEqual(components["Box"].native_path, "Assembly/Box")
        self.assertEqual(
            _features(discovery)["Pad"].native_path,
            "Assembly/Body/Pad",
        )

    def test_nested_app_parts_form_component_hierarchy(self) -> None:
        box = part_box("Box")
        nested = app_part("NestedPart", group=[box])
        body_object = body("Body")
        root = app_part("Root", group=[nested, body_object])
        box.InList = [nested]
        nested.InList = [root]
        body_object.InList = [root]

        discovery = discover_capture_candidates(
            FakeDocument("nested", objects=[root, nested, body_object, box])
        )

        self.assertEqual(discovery.root_component_native_ref, "Root")
        components = _components(discovery)
        self.assertEqual(components["NestedPart"].parent_native_ref, "Root")
        self.assertEqual(components["Body"].parent_native_ref, "Root")
        self.assertEqual(components["Box"].parent_native_ref, "NestedPart")
        self.assertEqual(
            [item.native_path for item in discovery.components],
            ["Root", "Root/Body", "Root/NestedPart", "Root/NestedPart/Box"],
        )

    def test_assembly_object_can_be_natural_root(self) -> None:
        body_object = body("Body")
        root = assembly_object("Assembly", group=[body_object])
        body_object.InList = [root]

        discovery = discover_capture_candidates(
            FakeDocument("assembly_document", objects=[root, body_object])
        )

        self.assertEqual(discovery.root_component_native_ref, "Assembly")
        components = _components(discovery)
        self.assertFalse(components["Assembly"].synthetic)
        self.assertEqual(components["Assembly"].kind, "assembly")
        self.assertEqual(components["Body"].parent_native_ref, "Assembly")

    def test_multiple_top_level_components_synthesize_root(self) -> None:
        body_a = body("BodyA")
        body_b = body("BodyB")

        discovery = discover_capture_candidates(
            FakeDocument("multiple", objects=[body_b, body_a])
        )

        self.assertEqual(discovery.root_component_native_ref, "multiple")
        components = _components(discovery)
        self.assertTrue(components["multiple"].synthetic)
        self.assertEqual(components["BodyA"].parent_native_ref, "multiple")
        self.assertEqual(components["BodyB"].parent_native_ref, "multiple")


class ParameterDiscoveryTests(unittest.TestCase):
    def _document(self) -> FakeDocument:
        body_object = body("Body")
        var_set_object = var_set(
            "Parameters",
            properties={
                "length": property_length(10.0, "mm", group="Base"),
                "width": property_float(2.5, group="Parameters"),
                "enabled": property_bool(True),
                "label_text": property_string("abc"),
                "count": property_integer(3),
                "readonly_value": property_float(4.0, status=("ReadOnly",)),
                "statusless": property_float(
                    5.0,
                    status_available=False,
                ),
                "vector": FakeProperty(
                    "App::PropertyVector",
                    group="Parameters",
                    value=object(),
                ),
                "unreadable": property_string(
                    "hidden",
                    readable=False,
                ),
                "missing_type": FakeProperty(
                    "App::PropertyString",
                    type_available=False,
                    value="x",
                ),
                "nonfinite": property_float(float("nan")),
                "mismatch": property_bool("not-a-bool"),
                "_internal": property_string("internal"),
            },
        )
        body_object.Group = [var_set_object]
        body_object.OutList = [var_set_object]
        var_set_object.InList = [body_object]
        return FakeDocument("parameters", objects=[body_object, var_set_object])

    def test_parameter_group_and_parameters_are_discovered(self) -> None:
        discovery = discover_capture_candidates(self._document())

        self.assertEqual(len(discovery.parameter_groups), 1)
        group = discovery.parameter_groups[0]
        self.assertEqual(group.native_ref, "Parameters")
        self.assertEqual(group.group_kind, "varset")
        self.assertEqual(group.owner_component_native_ref, "Body")
        self.assertEqual(group.native_path, "parameters/Body/Parameters")
        self.assertTrue(group.observable)
        self.assertTrue(group.writable)
        self.assertEqual(group.owner_scoped_key, "Parameters")

        parameters = _parameters(discovery)
        self.assertNotIn("Label", parameters)
        self.assertNotIn("Label2", parameters)
        self.assertNotIn("Visibility", parameters)
        self.assertNotIn("ExpressionEngine", parameters)
        self.assertNotIn("_internal", parameters)

        length = parameters["length"].property
        self.assertEqual(length.native_type_id, "App::PropertyLength")
        self.assertEqual(length.native_value_kind, "length")
        self.assertEqual(length.value_type, "number")
        self.assertEqual(length.current_value, 10.0)
        self.assertEqual(length.unit, "mm")
        self.assertTrue(length.supported)
        self.assertTrue(length.observable)
        self.assertTrue(length.writable)
        self.assertIsNone(length.unsupported_reason)

        self.assertEqual(parameters["width"].property.value_type, "number")
        self.assertEqual(parameters["enabled"].property.value_type, "boolean")
        self.assertIs(parameters["enabled"].property.current_value, True)
        self.assertEqual(parameters["label_text"].property.value_type, "string")
        self.assertEqual(parameters["label_text"].property.current_value, "abc")
        self.assertEqual(parameters["count"].property.native_value_kind, "integer")
        self.assertEqual(parameters["count"].property.current_value, 3)

        self.assertTrue(parameters["readonly_value"].property.supported)
        self.assertFalse(parameters["readonly_value"].property.writable)

        statusless = parameters["statusless"].property
        self.assertTrue(statusless.supported)
        self.assertTrue(statusless.observable)
        self.assertFalse(statusless.writable)
        self.assertFalse(statusless.property_status_available)

        vector = parameters["vector"].property
        self.assertFalse(vector.supported)
        self.assertTrue(vector.native_readable)
        self.assertEqual(
            vector.unsupported_reason,
            "unsupported_native_parameter_type",
        )
        self.assertIsNone(vector.value_type)
        self.assertIsNone(vector.current_value)
        self.assertIsNone(vector.unit)

        unreadable = parameters["unreadable"].property
        self.assertFalse(unreadable.supported)
        self.assertFalse(unreadable.native_readable)
        self.assertEqual(
            unreadable.unsupported_reason,
            "unreadable_native_property",
        )

        missing_type = parameters["missing_type"].property
        self.assertFalse(missing_type.supported)
        self.assertEqual(
            missing_type.unsupported_reason,
            "unreadable_native_property_type",
        )

        nonfinite = parameters["nonfinite"].property
        self.assertFalse(nonfinite.supported)
        self.assertEqual(
            nonfinite.unsupported_reason,
            "non_finite_numeric_value",
        )

        mismatch = parameters["mismatch"].property
        self.assertFalse(mismatch.supported)
        self.assertEqual(
            mismatch.unsupported_reason,
            "native_value_type_mismatch",
        )


class TargetabilityEvidenceTests(unittest.TestCase):
    def test_wrong_property_types_do_not_claim_capability(self) -> None:
        box = part_box(
            "Box",
            properties={
                "Suppressed": property_float(1.0),
                "Visibility": property_string("yes"),
            },
        )

        discovery = discover_capture_candidates(FakeDocument("caps", objects=[box]))
        targetability = _components(discovery)["Box"].targetability

        self.assertFalse(targetability.suppress)
        self.assertFalse(targetability.unsuppress)
        self.assertFalse(targetability.hide)
        self.assertFalse(targetability.unhide)

    def test_read_only_bool_property_does_not_claim_capability(self) -> None:
        box = part_box(
            "Box",
            properties={
                "Suppressed": suppressed_property(),
                "Visibility": FakeProperty(
                    "App::PropertyBool",
                    status=("ReadOnly",),
                    value=True,
                ),
            },
        )

        discovery = discover_capture_candidates(FakeDocument("caps", objects=[box]))
        targetability = _components(discovery)["Box"].targetability

        self.assertTrue(targetability.suppress)
        self.assertFalse(targetability.hide)

    def test_delete_requires_available_empty_dependents(self) -> None:
        dependent_a = body("BodyB")
        body_object = body(
            "BodyA",
            in_list=[dependent_a, dependent_a],
        )
        independent = body("BodyC")

        discovery = discover_capture_candidates(
            FakeDocument("delete", objects=[body_object, dependent_a, independent])
        )
        components = _components(discovery)

        self.assertFalse(components["BodyA"].targetability.delete)
        self.assertEqual(
            components["BodyA"].targetability.delete_dependents,
            ("BodyB",),
        )
        self.assertTrue(components["BodyA"].targetability.dependency_evidence_available)
        self.assertTrue(components["BodyC"].targetability.delete)

    def test_missing_dependency_evidence_does_not_authorize_delete(self) -> None:
        box = FakeObject(
            "Box",
            "Part::Box",
            properties={"Visibility": visibility_property()},
            include_relationships=False,
        )

        discovery = discover_capture_candidates(FakeDocument("caps", objects=[box]))
        targetability = _components(discovery)["Box"].targetability

        self.assertFalse(targetability.delete)
        self.assertFalse(targetability.dependency_evidence_available)
        self.assertEqual(targetability.delete_dependents, ())
        self.assertEqual(targetability.delete_dependencies, ())

    def test_natural_root_never_authorizes_delete(self) -> None:
        part = app_part("Assembly")

        discovery = discover_capture_candidates(
            FakeDocument("root_delete", objects=[part])
        )
        targetability = _components(discovery)["Assembly"].targetability

        self.assertFalse(targetability.delete)
        self.assertTrue(targetability.dependency_evidence_available)


class ExclusionAndHierarchyPolicyTests(unittest.TestCase):
    def test_links_joints_groups_and_spreadsheets_are_diagnostics(self) -> None:
        link = FakeObject("Link01", "App::Link")
        assembly_link = FakeObject("NestedLink", "Assembly::AssemblyLink")
        joint = FakeObject("Joint01", "Assembly::Joint")
        joint_group = FakeObject("Joints", "Assembly::JointGroup")
        group = FakeObject("Group01", "App::DocumentObjectGroup")
        sheet = FakeObject("Sheet", "Spreadsheet::Sheet")
        unknown = FakeObject("Holder", "App::FeaturePython")
        origin = FakeObject("Origin", "App::Origin")
        axis = FakeObject("X_Axis", "App::Line")

        discovery = discover_capture_candidates(
            FakeDocument(
                "excluded",
                objects=[
                    link,
                    assembly_link,
                    joint,
                    joint_group,
                    group,
                    sheet,
                    unknown,
                    origin,
                    axis,
                ],
            )
        )

        self.assertEqual(
            [item.native_ref for item in discovery.components],
            ["excluded"],
        )
        self.assertEqual(discovery.features, ())
        self.assertEqual(discovery.parameter_groups, ())
        codes = [item.code for item in discovery.diagnostics]
        self.assertIn("unsupported_link", codes)
        self.assertIn("unsupported_assembly_member", codes)
        self.assertIn("unsupported_object_group", codes)
        self.assertIn("unsupported_parameter_group_type", codes)
        self.assertIn("unsupported_object_type", codes)
        self.assertNotIn("unsupported_technical_drawing", codes)
        self.assertIn("Holder", [item.native_ref for item in discovery.diagnostics])
        self.assertNotIn("Origin", [item.native_ref for item in discovery.diagnostics])
        self.assertNotIn("X_Axis", [item.native_ref for item in discovery.diagnostics])

    def test_conflicting_native_parents_keep_first_parent_and_diagnose(self) -> None:
        box = part_box("Box")
        part_a = app_part("PartA", group=[box])
        part_b = app_part("PartB", group=[box])
        box.InList = [part_a, part_b]

        discovery = discover_capture_candidates(
            FakeDocument("conflict", objects=[part_b, part_a, box])
        )
        components = _components(discovery)

        self.assertEqual(components["Box"].parent_native_ref, "PartA")
        diagnostics = [
            item
            for item in discovery.diagnostics
            if item.code == "conflicting_component_parent"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].native_ref, "Box")
        self.assertIn("PartA", diagnostics[0].detail)
        self.assertIn("PartB", diagnostics[0].detail)

    def test_component_cycle_does_not_hang_and_is_diagnosed(self) -> None:
        part_a = FakeObject("PartA", "App::Part")
        part_b = FakeObject("PartB", "App::Part")
        part_a.Group = [part_b]
        part_b.Group = [part_a]

        discovery = discover_capture_candidates(
            FakeDocument("cycle", objects=[part_a, part_b])
        )

        self.assertEqual(discovery.root_component_native_ref, "cycle")
        components = _components(discovery)
        self.assertIn("PartA", components)
        self.assertIn("PartB", components)
        codes = {item.code for item in discovery.diagnostics}
        self.assertIn("unreachable_component", codes)


class ErrorAndDeterminismTests(unittest.TestCase):
    def test_document_without_objects_is_rejected(self) -> None:
        with self.assertRaises(CaptureDiscoveryDocumentError):
            discover_capture_candidates(FakeDocument(include_objects=False))

    def test_non_iterable_objects_are_rejected(self) -> None:
        document = FakeDocument()
        document.Objects = 1

        with self.assertRaises(CaptureDiscoveryDocumentError):
            discover_capture_candidates(document)

    def test_object_without_name_is_rejected(self) -> None:
        anonymous = FakeObject("", "Part::Box")

        with self.assertRaises(CaptureDiscoveryDocumentError):
            discover_capture_candidates(FakeDocument("bad", objects=[anonymous]))

    def test_duplicate_object_names_are_rejected(self) -> None:
        first = FakeObject("Box", "Part::Box")
        second = FakeObject("Box", "Part::Box")

        with self.assertRaises(CaptureDiscoveryDocumentError):
            discover_capture_candidates(
                FakeDocument("duplicate", objects=[first, second])
            )

    def test_object_without_type_id_is_an_inspection_error(self) -> None:
        class MissingTypeIdContainer(FakeObject):
            def __init__(self) -> None:
                super().__init__("Container", "")

            def isDerivedFrom(self, type_id: str) -> bool:
                return type_id == "App::Part"

        with self.assertRaises(CaptureDiscoveryInspectionError):
            discover_capture_candidates(
                FakeDocument("bad", objects=[MissingTypeIdContainer()])
            )

    def test_synthetic_root_name_collision_is_rejected(self) -> None:
        body_object = body("collision")

        with self.assertRaises(CaptureDiscoveryDocumentError):
            discover_capture_candidates(
                FakeDocument("collision", objects=[body_object])
            )

    def test_discovery_is_deterministic_and_ordered(self) -> None:
        body_b = body("BodyB")
        body_a = body("BodyA")
        var_set_object = var_set(
            "Parameters",
            properties={
                "z_value": property_float(1.0),
                "a_value": property_float(2.0),
            },
        )
        body_a.Group = [var_set_object]
        body_a.OutList = [var_set_object]

        document = FakeDocument(
            "deterministic",
            objects=[body_b, var_set_object, body_a],
        )

        first = discover_capture_candidates(document).to_mapping()
        second = discover_capture_candidates(document).to_mapping()

        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps(first, sort_keys=True),
            json.dumps(second, sort_keys=True),
        )
        self.assertEqual(
            [item["nativePath"] for item in first["components"]],
            ["deterministic", "deterministic/BodyA", "deterministic/BodyB"],
        )
        self.assertEqual(
            [item["nativeKey"] for item in first["parameters"]],
            ["a_value", "z_value"],
        )
        self.assertNotIn("/home/", json.dumps(first, sort_keys=True))

    def test_document_shape_is_not_mutated(self) -> None:
        body_object = body("Body")
        var_set_object = var_set(
            "Parameters",
            properties={"length": property_length(10.0)},
        )
        body_object.Group = [var_set_object]
        body_object.OutList = [var_set_object]
        var_set_object.InList = [body_object]
        document = FakeDocument("immutable", objects=[body_object, var_set_object])
        before = _document_snapshot(document)

        discover_capture_candidates(document)

        self.assertEqual(_document_snapshot(document), before)


class DrawingDiscoveryTests(unittest.TestCase):
    def _body_and_feature(self) -> tuple[object, object]:
        pad_object = pad("Pad")
        body_object = body("Body", group=[pad_object])
        return body_object, pad_object

    def test_document_without_pages_has_no_drawing_candidates(self) -> None:
        body_object, pad_object = self._body_and_feature()
        discovery = discover_capture_candidates(
            FakeDocument("model", objects=[body_object, pad_object])
        )

        self.assertEqual(discovery.drawings, ())

    def test_single_page_discovers_label_order_resource_and_targets(self) -> None:
        body_object, pad_object = self._body_and_feature()
        view = drawing_view("BodyView", source=[body_object])
        page = drawing_page("Page", label="Main sheet", views=[view])

        discovery = discover_capture_candidates(
            FakeDocument(
                "drawing_doc",
                label="Drawing Document",
                objects=[body_object, pad_object, view, page],
            )
        )
        self.assertEqual([item.native_ref for item in discovery.drawings], ["Page"])
        candidate = discovery.drawings[0]

        self.assertEqual(candidate.native_label, "Main sheet")
        self.assertEqual(candidate.cad_type, "TechDraw::DrawPage")
        self.assertEqual(candidate.page_order, 1)
        self.assertEqual(candidate.resource.topology, "embedded")
        self.assertEqual(candidate.resource.document_name, "drawing_doc")
        self.assertEqual(candidate.resource.document_label, "Drawing Document")
        self.assertEqual(
            [(item.native_ref, item.cad_type, item.kind) for item in candidate.targets],
            [("Body", "PartDesign::Body", "component")],
        )

    def test_component_and_feature_targets_are_sorted_by_native_ref(self) -> None:
        body_object, pad_object = self._body_and_feature()
        view = drawing_view("View", source=[pad_object, body_object])
        page = drawing_page("Page", views=[view])

        discovery = discover_capture_candidates(
            FakeDocument("drawing_doc", objects=[body_object, pad_object, view, page])
        )
        targets = discovery.drawings[0].targets

        self.assertEqual(
            [(item.native_ref, item.kind) for item in targets],
            [("Body", "component"), ("Pad", "feature")],
        )

    def test_part_and_assembly_sources_resolve_as_components(self) -> None:
        part = app_part("Part")
        assembly = assembly_object("Assembly")
        view = drawing_view("View", source=[part, assembly])
        page = drawing_page("Page", views=[view])

        discovery = discover_capture_candidates(
            FakeDocument(
                "drawing_doc",
                objects=[part, assembly, view, page],
            )
        )

        self.assertEqual(
            [(item.native_ref, item.kind) for item in discovery.drawings[0].targets],
            [("Assembly", "component"), ("Part", "component")],
        )

    def test_multiple_pages_are_ordered_by_native_selector(self) -> None:
        page_b = drawing_page("PageB", label="Second sheet")
        page_a = drawing_page("PageA", label="First sheet")

        discovery = discover_capture_candidates(
            FakeDocument("drawing_doc", objects=[page_b, page_a])
        )

        self.assertEqual(
            [
                (item.native_ref, item.native_label, item.page_order)
                for item in discovery.drawings
            ],
            [
                ("PageA", "First sheet", 1),
                ("PageB", "Second sheet", 2),
            ],
        )

    def test_projection_group_item_sources_are_collected(self) -> None:
        body_object, pad_object = self._body_and_feature()
        front = projection_item("Front", source=[body_object])
        top = projection_item("Top", source=[body_object])
        group = projection_group("Projections", views=[front, top])
        page = drawing_page("Page", views=[group])

        discovery = discover_capture_candidates(
            FakeDocument(
                "drawing_doc",
                objects=[body_object, pad_object, group, page],
            )
        )

        self.assertEqual(
            [item.native_ref for item in discovery.drawings[0].targets],
            ["Body"],
        )
        self.assertEqual(discovery.diagnostics, ())

    def test_view_container_is_transparent_for_supported_views(self) -> None:
        body_object, pad_object = self._body_and_feature()
        view = drawing_view("BodyView", source=[body_object])
        clip = drawing_view_clip("Clip", views=[view])
        page = drawing_page("Page", views=[clip])

        discovery = discover_capture_candidates(
            FakeDocument(
                "drawing_doc",
                objects=[body_object, pad_object, clip, page],
            )
        )

        self.assertEqual(
            [item.native_ref for item in discovery.drawings[0].targets],
            ["Body"],
        )
        codes = {item.code for item in discovery.diagnostics}
        self.assertNotIn("unsupported_technical_drawing_view", codes)

    def test_empty_page_is_still_a_candidate(self) -> None:
        page = drawing_page("Page", views=[])

        discovery = discover_capture_candidates(
            FakeDocument("drawing_doc", objects=[page])
        )

        self.assertEqual(len(discovery.drawings), 1)
        self.assertEqual(discovery.drawings[0].targets, ())
        self.assertEqual(discovery.diagnostics, ())

    def test_unsupported_view_subtype_is_diagnosed(self) -> None:
        note = drawing_annotation("Note", label="Note")
        page = drawing_page("Page", views=[note])

        discovery = discover_capture_candidates(
            FakeDocument("drawing_doc", objects=[note, page])
        )

        diagnostics = [
            item
            for item in discovery.diagnostics
            if item.code == "unsupported_technical_drawing_view"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].native_ref, "Note")
        self.assertEqual(discovery.drawings[0].targets, ())

    def test_separate_document_source_is_diagnosed(self) -> None:
        external_body = body("ExternalBody")
        FakeDocument("external_model", objects=[external_body])
        view = drawing_view("View", source=[external_body])
        page = drawing_page("Page", views=[view])

        discovery = discover_capture_candidates(
            FakeDocument("drawing_doc", objects=[view, page])
        )

        diagnostics = [
            item
            for item in discovery.diagnostics
            if item.code == "separate_technical_drawing_source"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].native_ref, "ExternalBody")
        self.assertIn("external_model", diagnostics[0].detail)
        self.assertEqual(discovery.drawings[0].targets, ())

    def test_xsource_external_link_is_diagnosed(self) -> None:
        external_body = body("ExternalBody")
        FakeDocument("external_model", objects=[external_body])
        view = drawing_view("View", x_source=[external_body])
        page = drawing_page("Page", views=[view])

        discovery = discover_capture_candidates(
            FakeDocument("drawing_doc", objects=[view, page])
        )

        codes = {item.code for item in discovery.diagnostics}
        self.assertIn("separate_technical_drawing_source", codes)
        self.assertEqual(discovery.drawings[0].targets, ())

    def test_source_without_document_is_unresolvable(self) -> None:
        orphan_source = body("OrphanSource")
        view = drawing_view("View", source=[orphan_source])
        page = drawing_page("Page", views=[view])

        discovery = discover_capture_candidates(
            FakeDocument("drawing_doc", objects=[view, page])
        )

        diagnostics = [
            item
            for item in discovery.diagnostics
            if item.code == "unresolvable_technical_drawing_source"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].native_ref, "OrphanSource")

    def test_uncaptured_source_is_unresolvable(self) -> None:
        sheet = FakeObject("SourceSheet", "Spreadsheet::Sheet")
        view = drawing_view("View", source=[sheet])
        page = drawing_page("Page", views=[view])

        discovery = discover_capture_candidates(
            FakeDocument("drawing_doc", objects=[sheet, view, page])
        )

        diagnostics = [
            item
            for item in discovery.diagnostics
            if item.code == "unresolvable_technical_drawing_source"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].native_ref, "SourceSheet")

    def test_unavailable_views_and_sources_are_diagnosed(self) -> None:
        page = FakeObject("Page", "TechDraw::DrawPage")
        view = FakeObject("View", "TechDraw::DrawViewPart")
        page_with_view = drawing_page("PageWithView", views=[view])

        discovery = discover_capture_candidates(
            FakeDocument(
                "drawing_doc",
                objects=[page, view, page_with_view],
            )
        )

        codes = {item.code for item in discovery.diagnostics}
        self.assertIn("technical_drawing_views_unavailable", codes)
        self.assertIn("technical_drawing_source_unavailable", codes)
        self.assertEqual(len(discovery.drawings), 2)

    def test_orphan_technical_drawing_object_is_diagnosed(self) -> None:
        orphan = drawing_symbol("OrphanSymbol")

        discovery = discover_capture_candidates(
            FakeDocument("drawing_doc", objects=[orphan])
        )

        diagnostics = [
            item
            for item in discovery.diagnostics
            if item.code == "unsupported_technical_drawing"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].native_ref, "OrphanSymbol")
        self.assertEqual(discovery.drawings, ())

    def test_linked_technical_drawing_resource_reports_topology(self) -> None:
        page = drawing_page("Page")
        FakeDocument("drawing_doc", objects=[page])
        separate_link = FakeObject("SeparatePageLink", "App::Link")
        separate_link.LinkedObject = page
        local_page = drawing_page("LocalPage")
        document = FakeDocument(
            "model_doc",
            objects=[separate_link, local_page],
        )
        local_link = FakeObject("LocalPageLink", "App::Link")
        local_link.LinkedObject = local_page
        local_link.Document = document
        document.Objects.append(local_link)

        discovery = discover_capture_candidates(document)

        details = {
            item.native_ref: item.detail
            for item in discovery.diagnostics
            if item.code == "unsupported_technical_drawing_resource"
        }
        self.assertIn("(separate)", details["SeparatePageLink"])
        self.assertIn("(embedded)", details["LocalPageLink"])
        self.assertEqual(
            [item.native_ref for item in discovery.drawings], ["LocalPage"]
        )

    def test_drawing_mapping_has_no_semantic_identity(self) -> None:
        body_object, pad_object = self._body_and_feature()
        view = drawing_view("View", source=[body_object])
        page = drawing_page("Page", views=[view])

        mapping = discover_capture_candidates(
            FakeDocument(
                "drawing_doc",
                objects=[body_object, pad_object, view, page],
            )
        ).to_mapping()

        drawing = mapping["drawings"][0]
        self.assertEqual(
            set(drawing),
            {
                "nativeRef",
                "nativeLabel",
                "cadType",
                "pageOrder",
                "resource",
                "targets",
            },
        )
        self.assertEqual(
            set(drawing["resource"]),
            {"topology", "documentName", "documentLabel"},
        )
        self.assertEqual(
            set(drawing["targets"][0]),
            {"nativeRef", "cadType", "kind"},
        )

    def test_drawing_discovery_is_deterministic(self) -> None:
        def build():
            body_object, pad_object = self._body_and_feature()
            first = drawing_view("ViewA", source=[body_object])
            second = drawing_view("ViewB", source=[body_object])
            page_b = drawing_page("PageB", views=[second])
            page_a = drawing_page("PageA", views=[first])
            return discover_capture_candidates(
                FakeDocument(
                    "drawing_doc",
                    objects=[
                        page_b,
                        page_a,
                        second,
                        first,
                        pad_object,
                        body_object,
                    ],
                )
            ).to_mapping()

        self.assertEqual(
            json.dumps(build(), sort_keys=True),
            json.dumps(build(), sort_keys=True),
        )


def _document_snapshot(document: FakeDocument) -> object:
    return {
        "name": document.Name,
        "label": document.Label,
        "type_id": document.TypeId,
        "properties": {
            key: _property_snapshot(value)
            for key, value in document._properties.items()
        },
        "properties_list": list(getattr(document, "PropertiesList", ())),
        "objects": [
            {
                "name": item.Name,
                "label": item.Label,
                "type_id": item.TypeId,
                "properties": {
                    key: _property_snapshot(value)
                    for key, value in item._properties.items()
                },
                "properties_list": list(getattr(item, "PropertiesList", ())),
                "group": [member.Name for member in getattr(item, "Group", ())],
                "in_list": [member.Name for member in getattr(item, "InList", ())],
                "out_list": [member.Name for member in getattr(item, "OutList", ())],
            }
            for item in getattr(document, "Objects", ())
        ],
    }


def _property_snapshot(value: FakeProperty) -> object:
    native_value = value.value
    if isinstance(native_value, (str, bool, int, float)) or native_value is None:
        value_snapshot: object = native_value
    elif hasattr(native_value, "Value") and hasattr(native_value, "Unit"):
        value_snapshot = (
            "quantity",
            native_value.Value,
            str(native_value.Unit),
        )
    else:
        value_snapshot = (
            "object",
            id(native_value),
            type(native_value).__name__,
        )
    return (
        value.type_id,
        value.group,
        value.status,
        value.readable,
        value.status_available,
        value.group_available,
        value.type_available,
        value_snapshot,
    )


if __name__ == "__main__":
    unittest.main()
