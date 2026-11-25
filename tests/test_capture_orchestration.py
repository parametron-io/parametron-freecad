"""GUI-free tests for capture orchestration, drift, preview, and writes."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from parametron_freecad.capture import (
    CaptureConfirmationRequiredError,
    CaptureDecisionError,
    CaptureDecisions,
    CaptureDriftError,
    CaptureOutputPlan,
    CapturePreflightError,
    CaptureProjectError,
    CaptureSourceError,
    CaptureUnsavedDocumentError,
    ComponentDecision,
    DrawingDecision,
    DrawingResourceEvidence,
    DrawingSheetDecision,
    EnginePreflightResult,
    EnginePreflightRunner,
    FeatureDecision,
    FreeCADSemanticMapSelection,
    MetadataDecision,
    ParameterDecision,
    ParameterGroupDecision,
    SemanticParameterTypeSelection,
    build_capture_document,
    canonical_capture_bytes,
    derive_capture_id,
    detect_capture_drift,
    diff_mappings,
    discover_capture_candidates,
    document_fingerprint,
    load_project_context,
    plan_capture_outputs,
    resolve_model_by_path,
    resolve_selected_model,
    verify_active_source,
    write_capture_outputs,
)
from tests.capture_discovery_support import (
    FakeDocument,
    app_part,
    body,
    drawing_page,
    drawing_view,
    pad,
    property_length,
    property_string,
    var_set,
)


def _write_project(
    root: Path,
    *,
    project_id: str = "capture-project",
    models: dict[str, bytes] | None = None,
    dsl: str = "model.dsl",
    version: str = "1.0",
    tables: dict[str, str] | None = None,
) -> None:
    mapping: dict[str, object] = {
        "version": version,
        "projectId": project_id,
        "dsl": dsl,
        "resources": {"models": {}},
    }
    root.mkdir(parents=True, exist_ok=True)
    for logical_id, relative in _DEFAULT_MODELS.items():
        mapping["resources"]["models"][logical_id] = relative  # type: ignore[index]
    if models is not None:
        mapping["resources"]["models"] = {}  # type: ignore[index]
        for relative, content in models.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            logical_id = Path(relative).stem.replace("-", "_")
            mapping["resources"]["models"][logical_id] = relative  # type: ignore[index]
    if tables is not None:
        mapping["tables"] = tables
    (root / "prm.project.json").write_text(
        json.dumps(mapping, sort_keys=True) + "\n", encoding="utf-8"
    )


_DEFAULT_MODELS = {"model": "input/model.FCStd"}


def _fake_discovery():
    vset = var_set(
        "VarSet",
        properties={
            "boxLength": property_length(50.0),
            "boxWidth": property_length(30.0),
        },
    )
    pad_obj = pad("Pad")
    body_obj = body(
        "Body",
        group=[pad_obj],
        properties={"material": property_string("PLA", group="Metadata")},
    )
    root = app_part("root", group=[body_obj, vset])
    document = FakeDocument("model", objects=[root, body_obj, pad_obj, vset])
    return discover_capture_candidates(document)


def _drawing_discovery():
    pad_obj = pad("Pad")
    body_obj = body("Body", group=[pad_obj])
    root = app_part("root", group=[body_obj])
    body_view = drawing_view("BodyView", source=[body_obj])
    feature_view = drawing_view("FeatureView", source=[pad_obj])
    page_a = drawing_page("PageA", label="Sheet A", views=[body_view])
    page_b = drawing_page("PageB", label="Sheet B", views=[feature_view])
    document = FakeDocument(
        "model",
        objects=[
            root,
            body_obj,
            pad_obj,
            body_view,
            feature_view,
            page_a,
            page_b,
        ],
    )
    return discover_capture_candidates(document)


def _drawing_decisions(
    *, drawings: tuple[DrawingDecision, ...] | None = None
) -> CaptureDecisions:
    if drawings is None:
        drawings = (
            DrawingDecision(
                name="Manufacturing",
                display_name="Manufacturing Drawing",
                sheets=(
                    DrawingSheetDecision(
                        native_ref="PageA",
                        name="assembly",
                        order=1,
                    ),
                    DrawingSheetDecision(
                        native_ref="PageB",
                        name="detail",
                        order=2,
                    ),
                ),
            ),
        )
    return CaptureDecisions(
        components=(
            ComponentDecision(native_ref="root", name="Root"),
            ComponentDecision(native_ref="Body", name="Body"),
        ),
        drawings=drawings,
        cad_system_version="1.1.4",
    )


def _full_decisions() -> CaptureDecisions:
    return CaptureDecisions(
        components=(
            ComponentDecision(native_ref="root", name="Root"),
            ComponentDecision(native_ref="Body", name="Body"),
        ),
        features=(FeatureDecision(native_ref="Pad", name="Pad"),),
        parameter_groups=(ParameterGroupDecision(native_ref="VarSet", name="VarSet"),),
        parameters=(
            ParameterDecision(native_path="root/VarSet/boxLength", name="boxLength"),
            ParameterDecision(native_path="root/VarSet/boxWidth", name="boxWidth"),
        ),
        metadata=(
            MetadataDecision(native_path="root/Body/material", display_name="Material"),
        ),
        cad_system_version="1.1.4",
    )


def _selection() -> FreeCADSemanticMapSelection:
    return FreeCADSemanticMapSelection(
        mapping_id="capture-project-v1",
        parameter_types=(
            SemanticParameterTypeSelection(
                "length", "number", "mm", "number_to_length"
            ),
        ),
        native_type_to_semantic_type={"App::PropertyLength": "length"},
        cad_system_min_version="1.1.4",
    )


class CaptureProjectContextTests(unittest.TestCase):
    def test_loads_valid_context_from_directory_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_project(root)

            from_directory = load_project_context(root)
            from_file = load_project_context(root / "prm.project.json")

        self.assertEqual(from_directory.project_id, "capture-project")
        self.assertEqual(from_directory.dsl, "model.dsl")
        self.assertEqual(from_directory.models, (from_directory.model("model"),))
        self.assertEqual(from_directory.model("model").path, "input/model.FCStd")
        self.assertEqual(from_file.to_mapping(), from_directory.to_mapping())

    def test_missing_mapping_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(CaptureProjectError):
                load_project_context(Path(temporary))

    def test_unknown_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_project(root)
            data = json.loads((root / "prm.project.json").read_text())
            data["extra"] = True
            (root / "prm.project.json").write_text(json.dumps(data))
            with self.assertRaises(CaptureProjectError) as raised:
                load_project_context(root)
        self.assertTrue(
            any("extra" in problem for problem in raised.exception.problems)
        )

    def test_unsupported_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_project(root, version="2.0")
            with self.assertRaises(CaptureProjectError):
                load_project_context(root)

    def test_escaping_and_absolute_paths_are_rejected(self) -> None:
        for relative in ("../escape.FCStd", "/abs.FCStd", "C:/abs.FCStd", "./"):
            with self.subTest(relative=relative):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    _write_project(root)
                    data = json.loads((root / "prm.project.json").read_text())
                    data["resources"]["models"] = {"model": relative}
                    (root / "prm.project.json").write_text(json.dumps(data))
                    with self.assertRaises(CaptureProjectError):
                        load_project_context(root)

    def test_explicit_selection_and_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_project(root)
            data = json.loads((root / "prm.project.json").read_text())
            data["resources"]["models"] = {
                "alpha": "input/model.FCStd",
                "beta": "input/model.FCStd",
            }
            (root / "prm.project.json").write_text(json.dumps(data))
            context = load_project_context(root)

            self.assertEqual(
                resolve_selected_model(context, "beta").path, "input/model.FCStd"
            )
            with self.assertRaises(CaptureProjectError):
                resolve_selected_model(context, "missing")
            with self.assertRaises(CaptureProjectError) as raised:
                resolve_model_by_path(context, "input/model.FCStd")
            self.assertTrue(
                any("ambiguous" in problem for problem in raised.exception.problems)
            )


class CaptureFingerprintAndSourceTests(unittest.TestCase):
    def test_fingerprint_is_stable_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "model.FCStd"
            path.write_bytes(b"native document bytes")
            first = document_fingerprint(path)
            second = document_fingerprint(path)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("sha256:"))
        self.assertEqual(len(first), len("sha256:") + 64)

    def test_verify_active_source_accepts_declared_saved_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "model.FCStd"
            path.write_bytes(b"bytes")
            document = mock.Mock()
            document.FileName = str(path)
            document.Name = "model"
            document.Label = "Model"
            document.isSaved.return_value = True

            evidence = verify_active_source(document, path)

        self.assertEqual(evidence.document_name, "model")
        self.assertTrue(evidence.saved)

    def test_verify_active_source_rejects_other_or_unsaved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "model.FCStd"
            path.write_bytes(b"bytes")
            other = Path(temporary) / "other.FCStd"
            other.write_bytes(b"other")

            document = mock.Mock()
            document.FileName = str(other)
            document.isSaved.return_value = True
            with self.assertRaises(CaptureSourceError):
                verify_active_source(document, path)

            document.FileName = str(path)
            document.isSaved.return_value = False
            with self.assertRaises(CaptureUnsavedDocumentError):
                verify_active_source(document, path)

            document = mock.Mock()
            document.FileName = ""
            with self.assertRaises(CaptureSourceError):
                verify_active_source(document, path)


class CaptureDecisionsTests(unittest.TestCase):
    def test_capture_id_derivation_is_deterministic(self) -> None:
        first = derive_capture_id("Capture Project", "model")
        second = derive_capture_id("Capture Project", "model")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("cap.freecad."))
        self.assertNotEqual(first, derive_capture_id("capture-project", "other"))

    def test_authorized_actions_must_be_a_frozenset(self) -> None:
        with self.assertRaises(TypeError):
            FeatureDecision(
                native_ref="Pad",
                name="Pad",
                authorized_actions=["suppress"],  # type: ignore[arg-type]
            )


class CaptureBuildDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        _write_project(self.root, models={"input/model.FCStd": b"native bytes"})
        self.context = load_project_context(self.root)
        self.model = resolve_selected_model(self.context, "model")
        self.discovery = _fake_discovery()

    def test_builds_valid_deterministic_document(self) -> None:
        first = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=_full_decisions(),
        )
        second = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=_full_decisions(),
        )

        mapping = first.to_mapping()
        self.assertEqual(
            canonical_capture_bytes(first), canonical_capture_bytes(second)
        )
        self.assertEqual(mapping["sourceDocument"]["logicalId"], "model")
        self.assertEqual(mapping["sourceDocument"]["path"], "input/model.FCStd")
        self.assertTrue(mapping["sourceDocument"]["fingerprint"].startswith("sha256:"))
        self.assertEqual(mapping["captureId"], "cap.freecad.capture-project-model")

        ids = {entry["id"] for entry in mapping["entities"]["components"]}
        self.assertEqual(ids, {"cmp.root", "cmp.body"})
        feature = mapping["entities"]["features"][0]
        self.assertEqual(feature["id"], "fea.body.pad")
        self.assertEqual(feature["targetability"]["suppress"], True)
        group = mapping["entities"]["parameterGroups"][0]
        self.assertEqual(group["id"], "grp.root.varSet")
        parameters = {item["id"]: item for item in mapping["entities"]["parameters"]}
        self.assertEqual(
            set(parameters),
            {"par.root.varSet.boxLength", "par.root.varSet.boxWidth"},
        )
        self.assertEqual(parameters["par.root.varSet.boxLength"]["unit"], "mm")
        self.assertNotIn("stabilityClass", parameters["par.root.varSet.boxLength"])
        metadata = mapping["entities"]["metadata"][0]
        self.assertEqual(metadata["id"], "meta.body.material")
        self.assertEqual(metadata["key"], "material")
        self.assertNotIn("identitySource", metadata)
        self.assertEqual(mapping["entities"]["drawings"], [])
        self.assertEqual(mapping["structure"]["rootComponentId"], "cmp.root")

    def test_root_component_is_required(self) -> None:
        decisions = _full_decisions()
        reduced = CaptureDecisions(
            components=(ComponentDecision(native_ref="Body", name="Body"),),
            features=decisions.features,
            parameter_groups=decisions.parameter_groups,
            parameters=decisions.parameters,
            metadata=decisions.metadata,
        )
        with self.assertRaises(CaptureDecisionError):
            build_capture_document(
                context=self.context,
                model=self.model,
                discovery=self.discovery,
                decisions=reduced,
            )

    def test_child_without_selected_parent_is_rejected(self) -> None:
        decisions = CaptureDecisions(
            components=(ComponentDecision(native_ref="root", name="Root"),),
            features=(FeatureDecision(native_ref="Pad", name="Pad"),),
        )
        with self.assertRaises(CaptureDecisionError):
            build_capture_document(
                context=self.context,
                model=self.model,
                discovery=self.discovery,
                decisions=decisions,
            )

    def test_unknown_native_selector_is_rejected(self) -> None:
        decisions = _full_decisions()
        replaced = CaptureDecisions(
            components=(
                decisions.components[0],
                ComponentDecision(native_ref="Ghost", name="Ghost"),
            ),
            features=decisions.features,
            parameter_groups=decisions.parameter_groups,
            parameters=decisions.parameters,
            metadata=decisions.metadata,
        )
        with self.assertRaises(CaptureDecisionError):
            build_capture_document(
                context=self.context,
                model=self.model,
                discovery=self.discovery,
                decisions=replaced,
            )

    def test_authorizing_unsupported_action_is_rejected(self) -> None:
        pad_candidate = next(
            item for item in self.discovery.features if item.native_ref == "Pad"
        )
        weakened_feature = replace(
            pad_candidate,
            targetability=replace(
                pad_candidate.targetability,
                suppress=False,
                unsuppress=False,
            ),
        )
        weakened = replace(self.discovery, features=(weakened_feature,))
        decisions = _full_decisions()
        replaced = CaptureDecisions(
            components=decisions.components,
            features=(
                FeatureDecision(
                    native_ref="Pad",
                    name="Pad",
                    authorized_actions=frozenset({"suppress"}),
                ),
            ),
            parameter_groups=decisions.parameter_groups,
            parameters=decisions.parameters,
            metadata=decisions.metadata,
        )
        with self.assertRaises(CaptureDecisionError):
            build_capture_document(
                context=self.context,
                model=self.model,
                discovery=weakened,
                decisions=replaced,
            )

    def test_explicit_id_and_stability_class_are_preserved(self) -> None:
        decisions = CaptureDecisions(
            components=(
                ComponentDecision(
                    native_ref="root",
                    name="Root",
                    id="cmp.assembly",
                    stability_class="stable",
                ),
                ComponentDecision(native_ref="Body", name="Body"),
            ),
            features=_full_decisions().features,
            parameter_groups=_full_decisions().parameter_groups,
            parameters=_full_decisions().parameters,
            metadata=_full_decisions().metadata,
        )
        mapping = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=decisions,
        ).to_mapping()

        root = next(
            item
            for item in mapping["entities"]["components"]
            if item["id"] == "cmp.assembly"
        )
        self.assertEqual(root["stabilityClass"], "stable")


class CaptureDrawingDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        _write_project(self.root, models={"input/model.FCStd": b"native bytes"})
        self.context = load_project_context(self.root)
        self.model = resolve_selected_model(self.context, "model")
        self.discovery = _drawing_discovery()

    def test_builds_embedded_drawing_with_ordered_sheets(self) -> None:
        mapping = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=_drawing_decisions(),
        ).to_mapping()

        self.assertEqual(len(mapping["entities"]["drawings"]), 1)
        drawing = mapping["entities"]["drawings"][0]
        self.assertEqual(drawing["id"], "drw.manufacturing")
        self.assertEqual(drawing["name"], "Manufacturing")
        self.assertEqual(drawing["displayName"], "Manufacturing Drawing")
        self.assertEqual(drawing["componentIds"], ["cmp.body"])
        self.assertEqual(drawing["resource"], {"topology": "embedded"})
        self.assertNotIn("identitySource", drawing)
        self.assertEqual(
            [sheet["id"] for sheet in drawing["sheets"]],
            ["sht.manufacturing.assembly", "sht.manufacturing.detail"],
        )
        self.assertEqual(
            [sheet["order"] for sheet in drawing["sheets"]],
            [1, 2],
        )
        self.assertEqual(
            [sheet["identitySource"]["nativeRef"] for sheet in drawing["sheets"]],
            ["PageA", "PageB"],
        )
        self.assertEqual(
            [sheet["cadType"] for sheet in drawing["sheets"]],
            ["TechDraw::DrawPage", "TechDraw::DrawPage"],
        )
        self.assertEqual(
            [sheet["displayName"] for sheet in drawing["sheets"]],
            ["Sheet A", "Sheet B"],
        )

    def test_feature_target_resolves_to_owning_component(self) -> None:
        mapping = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=_drawing_decisions(),
        ).to_mapping()

        drawing = mapping["entities"]["drawings"][0]
        self.assertEqual(drawing["componentIds"], ["cmp.body"])
        self.assertEqual(mapping["entities"]["features"], [])

    def test_multiple_drawings_are_supported(self) -> None:
        decisions = _drawing_decisions(
            drawings=(
                DrawingDecision(
                    name="Manufacturing",
                    sheets=(
                        DrawingSheetDecision(
                            native_ref="PageA",
                            name="assembly",
                            order=1,
                        ),
                    ),
                ),
                DrawingDecision(
                    name="Inspection",
                    sheets=(
                        DrawingSheetDecision(
                            native_ref="PageB",
                            name="detail",
                            order=1,
                        ),
                    ),
                ),
            )
        )
        mapping = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=decisions,
        ).to_mapping()

        self.assertEqual(
            [drawing["id"] for drawing in mapping["entities"]["drawings"]],
            ["drw.inspection", "drw.manufacturing"],
        )

    def test_unknown_page_and_duplicate_page_selection_are_rejected(self) -> None:
        with self.assertRaises(CaptureDecisionError):
            build_capture_document(
                context=self.context,
                model=self.model,
                discovery=self.discovery,
                decisions=_drawing_decisions(
                    drawings=(
                        DrawingDecision(
                            name="Manufacturing",
                            sheets=(
                                DrawingSheetDecision(
                                    native_ref="MissingPage",
                                    name="assembly",
                                    order=1,
                                ),
                            ),
                        ),
                    )
                ),
            )

        with self.assertRaises(CaptureDecisionError):
            build_capture_document(
                context=self.context,
                model=self.model,
                discovery=self.discovery,
                decisions=_drawing_decisions(
                    drawings=(
                        DrawingDecision(
                            name="First",
                            sheets=(
                                DrawingSheetDecision(
                                    native_ref="PageA",
                                    name="assembly",
                                    order=1,
                                ),
                            ),
                        ),
                        DrawingDecision(
                            name="Second",
                            sheets=(
                                DrawingSheetDecision(
                                    native_ref="PageA",
                                    name="detail",
                                    order=1,
                                ),
                            ),
                        ),
                    )
                ),
            )

    def test_invalid_sheet_orders_and_empty_sheets_are_rejected(self) -> None:
        for sheets in (
            (),
            (DrawingSheetDecision(native_ref="PageA", name="a", order=0),),
            (
                DrawingSheetDecision(native_ref="PageA", name="a", order=1),
                DrawingSheetDecision(native_ref="PageB", name="b", order=1),
            ),
        ):
            with self.subTest(sheets=sheets):
                with self.assertRaises(CaptureDecisionError):
                    build_capture_document(
                        context=self.context,
                        model=self.model,
                        discovery=self.discovery,
                        decisions=_drawing_decisions(
                            drawings=(
                                DrawingDecision(
                                    name="Manufacturing",
                                    sheets=sheets,
                                ),
                            )
                        ),
                    )

    def test_separate_page_resource_is_rejected_by_freecad_capture(self) -> None:
        discovery = replace(
            self.discovery,
            drawings=tuple(
                replace(
                    page,
                    resource=DrawingResourceEvidence(
                        "separate",
                        "drawing_doc",
                        "Drawing Document",
                    ),
                )
                for page in self.discovery.drawings
            ),
        )
        with self.assertRaises(CaptureDecisionError):
            build_capture_document(
                context=self.context,
                model=self.model,
                discovery=discovery,
                decisions=_drawing_decisions(),
            )

    def test_unselected_drawing_target_component_is_rejected(self) -> None:
        decisions = CaptureDecisions(
            components=(ComponentDecision(native_ref="root", name="Root"),),
            drawings=_drawing_decisions().drawings,
            cad_system_version="1.1.4",
        )
        with self.assertRaises(CaptureDecisionError):
            build_capture_document(
                context=self.context,
                model=self.model,
                discovery=self.discovery,
                decisions=decisions,
            )

    def test_drawing_drift_detects_sheet_changes(self) -> None:
        retained = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=_drawing_decisions(),
        ).to_mapping()
        self.assertEqual(detect_capture_drift(retained, copy.deepcopy(retained)), ())

        proposed = copy.deepcopy(retained)
        proposed["entities"]["drawings"][0]["sheets"][0]["cadType"] = (
            "TechDraw::DrawViewPart"
        )
        entries = detect_capture_drift(retained, proposed)
        self.assertTrue(
            any(
                entry.entity == "drawingSheet" and entry.code == "changed_native_type"
                for entry in entries
            ),
            entries,
        )

        proposed = copy.deepcopy(retained)
        proposed["entities"]["drawings"][0]["componentIds"] = ["cmp.root"]
        entries = detect_capture_drift(retained, proposed)
        self.assertTrue(
            any(
                entry.entity == "drawingSheet" and entry.code == "dependency_change"
                for entry in entries
            ),
            entries,
        )

        proposed = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=_drawing_decisions(
                drawings=(
                    DrawingDecision(
                        name="Inspection",
                        sheets=_drawing_decisions().drawings[0].sheets,
                    ),
                )
            ),
        ).to_mapping()
        entries = detect_capture_drift(retained, proposed)
        self.assertTrue(
            any(
                entry.entity == "drawingSheet"
                and entry.code == "semantic_identity_change"
                for entry in entries
            ),
            entries,
        )

    def test_removed_page_is_missing_drawing_sheet_drift(self) -> None:
        retained = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=_drawing_decisions(),
        ).to_mapping()
        proposed = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=_drawing_decisions(
                drawings=(
                    DrawingDecision(
                        name="Manufacturing",
                        sheets=(
                            DrawingSheetDecision(
                                native_ref="PageA",
                                name="assembly",
                                order=1,
                            ),
                        ),
                    ),
                )
            ),
        ).to_mapping()

        entries = detect_capture_drift(retained, proposed)
        self.assertTrue(
            any(
                entry.entity == "drawingSheet"
                and entry.code == "missing_native_selector"
                for entry in entries
            ),
            entries,
        )


class CaptureDriftTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        _write_project(self.root, models={"input/model.FCStd": b"native bytes"})
        self.context = load_project_context(self.root)
        self.model = resolve_selected_model(self.context, "model")
        self.discovery = _fake_discovery()
        self.retained = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=_full_decisions(),
        ).to_mapping()

    def test_unchanged_capture_has_no_drift(self) -> None:
        proposed = copy.deepcopy(self.retained)
        self.assertEqual(detect_capture_drift(self.retained, proposed), ())

    def test_missing_native_selector_is_drift(self) -> None:
        decisions = _full_decisions()
        reduced = CaptureDecisions(
            components=decisions.components,
            features=(),
            parameter_groups=decisions.parameter_groups,
            parameters=decisions.parameters,
            metadata=decisions.metadata,
        )
        proposed = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=reduced,
        ).to_mapping()
        entries = detect_capture_drift(self.retained, proposed)
        self.assertTrue(
            any(entry.code == "missing_native_selector" for entry in entries)
        )

    def test_changed_native_type_is_drift(self) -> None:
        proposed = copy.deepcopy(self.retained)
        proposed["entities"]["features"][0]["cadType"] = "PartDesign::Pocket"
        entries = detect_capture_drift(self.retained, proposed)
        self.assertTrue(any(entry.code == "changed_native_type" for entry in entries))

    def test_semantic_identity_change_is_drift(self) -> None:
        decisions = _full_decisions()
        renamed = CaptureDecisions(
            components=decisions.components,
            features=(FeatureDecision(native_ref="Pad", name="PadRenamed"),),
            parameter_groups=decisions.parameter_groups,
            parameters=decisions.parameters,
            metadata=decisions.metadata,
        )
        proposed = build_capture_document(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=renamed,
        ).to_mapping()
        entries = detect_capture_drift(self.retained, proposed)
        self.assertTrue(
            any(entry.code == "semantic_identity_change" for entry in entries)
        )

    def test_dependency_change_is_drift(self) -> None:
        proposed = copy.deepcopy(self.retained)
        proposed["entities"]["features"][0]["componentId"] = "cmp.other"
        entries = detect_capture_drift(self.retained, proposed)
        self.assertTrue(any(entry.code == "dependency_change" for entry in entries))


class CapturePlanAndWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        _write_project(self.root, models={"input/model.FCStd": b"native bytes"})
        self.context = load_project_context(self.root)
        self.model = resolve_selected_model(self.context, "model")
        self.discovery = _fake_discovery()

    def _plan(self, decisions: CaptureDecisions) -> CaptureOutputPlan:
        return plan_capture_outputs(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            decisions=decisions,
            semantic_selection=_selection(),
        )

    def test_create_then_unchanged(self) -> None:
        plan = self._plan(_full_decisions())
        self.assertEqual(plan.status, "create")
        self.assertFalse(plan.requires_confirmation)
        summary = write_capture_outputs(plan, confirm_replace=False)
        self.assertTrue(summary.wrote_capture)
        self.assertTrue(summary.wrote_semantic)
        self.assertTrue(plan.capture_path.is_file())
        self.assertTrue(plan.semantic_path.is_file())

        repeat = self._plan(_full_decisions())
        self.assertEqual(repeat.status, "unchanged")
        self.assertFalse(repeat.requires_confirmation)
        repeat_summary = write_capture_outputs(repeat, confirm_replace=False)
        self.assertFalse(repeat_summary.wrote_capture)
        self.assertFalse(repeat_summary.wrote_semantic)

    def test_merge_requires_confirmation_and_is_atomic(self) -> None:
        write_capture_outputs(self._plan(_full_decisions()), confirm_replace=False)
        before_capture = (self.root / "prm.cad.json").read_bytes()
        before_semantic = (self.root / "prm.semantic-map.json").read_bytes()

        decisions = _full_decisions()
        changed = CaptureDecisions(
            components=decisions.components,
            features=decisions.features,
            parameter_groups=decisions.parameter_groups,
            parameters=decisions.parameters,
            metadata=(
                MetadataDecision(
                    native_path="root/Body/material",
                    display_name="Material Name",
                ),
            ),
        )
        plan = self._plan(changed)
        self.assertEqual(plan.capture_status, "merge")
        self.assertTrue(plan.requires_confirmation)
        self.assertTrue(plan.capture_diff)

        with self.assertRaises(CaptureConfirmationRequiredError):
            write_capture_outputs(plan, confirm_replace=False)
        self.assertEqual((self.root / "prm.cad.json").read_bytes(), before_capture)
        self.assertEqual(
            (self.root / "prm.semantic-map.json").read_bytes(), before_semantic
        )

        summary = write_capture_outputs(plan, confirm_replace=True)
        self.assertTrue(summary.wrote_capture)
        self.assertEqual(
            (self.root / "prm.cad.json").read_bytes(),
            canonical_capture_bytes(plan.document),
        )

    def test_drift_blocks_planning(self) -> None:
        write_capture_outputs(self._plan(_full_decisions()), confirm_replace=False)
        decisions = _full_decisions()
        reduced = CaptureDecisions(
            components=decisions.components,
            features=(),
            parameter_groups=decisions.parameter_groups,
            parameters=decisions.parameters,
            metadata=decisions.metadata,
        )
        with self.assertRaises(CaptureDriftError):
            self._plan(reduced)

    def test_invalid_existing_capture_is_rejected(self) -> None:
        (self.root / "prm.cad.json").write_text("{", encoding="utf-8")
        with self.assertRaises(Exception):
            self._plan(_full_decisions())

    def test_source_and_project_mapping_are_unchanged(self) -> None:
        source = self.root / "input" / "model.FCStd"
        mapping = self.root / "prm.project.json"
        source_before = source.read_bytes()
        mapping_before = mapping.read_bytes()

        write_capture_outputs(self._plan(_full_decisions()), confirm_replace=True)

        self.assertEqual(source.read_bytes(), source_before)
        self.assertEqual(mapping.read_bytes(), mapping_before)

    def test_confirmation_must_be_bool(self) -> None:
        plan = self._plan(_full_decisions())
        with self.assertRaises(TypeError):
            write_capture_outputs(plan)  # type: ignore[call-arg]
        with self.assertRaises(TypeError):
            write_capture_outputs(plan, confirm_replace=1)  # type: ignore[arg-type]

    def test_plan_mapping_is_json_safe(self) -> None:
        plan = self._plan(_full_decisions())
        json.dumps(plan.to_mapping(), sort_keys=True)


class MappingDiffTests(unittest.TestCase):
    def test_diff_is_sorted_and_structural(self) -> None:
        existing = {"a": 1, "b": {"c": 2}}
        proposed = {"a": 2, "b": {"d": 3}}
        entries = diff_mappings(existing, proposed)
        self.assertEqual(
            [(entry.path, entry.change) for entry in entries],
            [("/a", "changed"), ("/b/c", "removed"), ("/b/d", "added")],
        )

    def test_new_document_diff(self) -> None:
        entries = diff_mappings(None, {"a": 1})
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].change, "added")


class EnginePreflightTests(unittest.TestCase):
    def _completed(self, returncode: int, stdout: str = "", stderr: str = ""):
        completed = mock.Mock()
        completed.returncode = returncode
        completed.stdout = stdout
        completed.stderr = stderr
        return completed

    def test_unavailable_engine_is_reported_not_failed(self) -> None:
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch("shutil.which", return_value=None),
        ):
            runner = EnginePreflightRunner()
            result = runner.run("/project")
            required = runner.require("/project")

        self.assertFalse(result.available)
        self.assertFalse(result.ran)
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(required.status, "unavailable")

    def test_command_shape_and_success(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured["kwargs"] = kwargs
            return self._completed(0, stdout="Validation succeeded")

        runner = EnginePreflightRunner(executable="parametron", runner=fake_run)
        result = runner.run("/project")

        self.assertEqual(
            captured["command"], ["parametron", "validate", "--project", "/project"]
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.stdout, "Validation succeeded")

    def test_failure_raises_only_from_require(self) -> None:
        def fake_run(command, **kwargs):
            return self._completed(1, stderr="boom")

        runner = EnginePreflightRunner(executable="parametron", runner=fake_run)
        result = runner.run("/project")
        self.assertEqual(result.status, "failed")
        with self.assertRaises(CapturePreflightError):
            runner.require("/project")

    def test_write_runs_preflight_after_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_project(root, models={"input/model.FCStd": b"native bytes"})
            context = load_project_context(root)
            plan = plan_capture_outputs(
                context=context,
                model=resolve_selected_model(context, "model"),
                discovery=_fake_discovery(),
                decisions=_full_decisions(),
                semantic_selection=_selection(),
            )
            runner = EnginePreflightRunner(
                executable="parametron",
                runner=lambda command, **kwargs: self._completed(1, stderr="boom"),
            )
            with self.assertRaises(CapturePreflightError):
                write_capture_outputs(plan, confirm_replace=False, preflight=runner)
            self.assertTrue(plan.capture_path.is_file())

    def test_result_mapping_is_json_safe(self) -> None:
        result = EnginePreflightResult(
            available=True,
            ran=True,
            status="ok",
            executable="parametron",
            returncode=0,
            stdout="ok",
            stderr="",
        )
        json.dumps(result.to_mapping(), sort_keys=True)


if __name__ == "__main__":
    unittest.main()
