"""GUI-free tests for the workbench four-tab capture panel state and session."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

WORKBENCH_ROOT = Path(__file__).resolve().parents[1] / "workbench"
if str(WORKBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKBENCH_ROOT))

from parametron_workbench import (  # noqa: E402
    CapturePanelError,
    CapturePanelOptions,
    CapturePanelState,
    CaptureSession,
    CaptureTab,
    build_default_semantic_selection,
    load_semantic_selection,
)

from parametron_freecad.capture import (  # noqa: E402
    discover_capture_candidates,
    load_project_context,
    resolve_selected_model,
)
from tests.capture_discovery_support import (  # noqa: E402
    FakeDocument,
    FakeProperty,
    app_part,
    body,
    pad,
    property_integer,
    property_length,
    property_string,
    var_set,
)


def _write_project(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "input").mkdir(exist_ok=True)
    (root / "input" / "model.FCStd").write_bytes(b"native bytes")
    (root / "prm.project.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "projectId": "panel-project",
                "dsl": "model.dsl",
                "resources": {"models": {"model": "input/model.FCStd"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _discovery():
    vset = var_set(
        "VarSet",
        properties={
            "boxLength": property_length(50.0),
            "boxWidth": property_length(30.0),
            "count": property_integer(3),
            "vec": FakeProperty("App::PropertyVector", value=None),
        },
    )
    pad_a = pad("Pad")
    body_a = body(
        "Body",
        group=[pad_a],
        properties={
            "material": property_string("PLA", group="Metadata"),
            "measured": property_length(12.0, group="Metadata"),
        },
    )
    pad_b = pad("Pad2")
    body_b = body("Body2", group=[pad_b])
    root = app_part("root", group=[body_a, body_b, vset])
    document = FakeDocument("model", objects=[root, body_a, pad_a, body_b, pad_b, vset])
    return discover_capture_candidates(document)


def _state():
    discovery = _discovery()
    return CapturePanelState(
        discovery,
        build_default_semantic_selection(discovery, cad_system_min_version="1.1.4"),
    )


class PanelGatingTests(unittest.TestCase):
    def test_initial_state_only_enables_parts_tab(self) -> None:
        snapshot = _state().snapshot()
        self.assertTrue(snapshot.tabs[CaptureTab.PARTS].enabled)
        for tab in (
            CaptureTab.FEATURES,
            CaptureTab.PARAMETERS,
            CaptureTab.METADATA,
        ):
            self.assertFalse(snapshot.tabs[tab].enabled)
            self.assertTrue(snapshot.tabs[tab].reason)
        self.assertFalse(snapshot.has_captured_component)
        self.assertFalse(snapshot.can_review)

        root = next(row for row in snapshot.components if row.native_ref == "root")
        self.assertTrue(root.included)
        self.assertTrue(root.name_error)
        self.assertFalse(root.disabled)

    def test_naming_root_enables_other_tabs(self) -> None:
        state = _state()
        state.set_component_name("root", "Root")
        snapshot = state.snapshot()
        for tab in (
            CaptureTab.FEATURES,
            CaptureTab.PARAMETERS,
            CaptureTab.METADATA,
        ):
            self.assertTrue(snapshot.tabs[tab].enabled)
            self.assertEqual(snapshot.tabs[tab].reason, "")
        self.assertTrue(snapshot.has_captured_component)
        self.assertTrue(snapshot.can_review)

    def test_feature_cannot_be_included_before_component(self) -> None:
        state = _state()
        with self.assertRaises(CapturePanelError):
            state.set_feature_included("Pad", True)

    def test_excluding_component_cascades_to_descendants(self) -> None:
        state = _state()
        state.set_component_name("root", "Root")
        state.set_component_included("Body", True)
        state.set_component_name("Body", "Body")
        state.set_feature_included("Pad", True)
        state.set_feature_name("Pad", "Pad")
        self.assertTrue(
            next(
                row for row in state.snapshot().features if row.native_ref == "Pad"
            ).included
        )

        state.set_component_included("Body", False)
        snapshot = state.snapshot()
        body_row = next(row for row in snapshot.components if row.native_ref == "Body")
        pad_row = next(row for row in snapshot.features if row.native_ref == "Pad")
        self.assertFalse(body_row.included)
        self.assertFalse(pad_row.included)
        self.assertTrue(pad_row.disabled)

    def test_root_cannot_be_excluded(self) -> None:
        state = _state()
        with self.assertRaises(CapturePanelError):
            state.set_component_included("root", False)


class PanelIdentityTests(unittest.TestCase):
    def test_generated_previews_follow_naming_convention(self) -> None:
        state = _state()
        state.set_component_name("root", "Root")
        state.set_component_included("Body", True)
        state.set_component_name("Body", "Body")
        state.set_feature_included("Pad", True)
        state.set_feature_name("Pad", "Pad")
        state.set_group_included("VarSet", True)
        state.set_group_name("VarSet", "VarSet")
        state.set_parameter_included("root/VarSet/boxLength", True)
        state.set_parameter_name("root/VarSet/boxLength", "boxLength")

        snapshot = state.snapshot()
        ids = {row.native_ref: row.id_preview for row in snapshot.components}
        self.assertEqual(ids, {"root": "cmp.root", "Body": "cmp.body", "Body2": None})
        self.assertEqual(
            next(
                row for row in snapshot.features if row.native_ref == "Pad"
            ).id_preview,
            "fea.body.pad",
        )
        self.assertEqual(
            next(
                row
                for row in snapshot.parameters
                if row.native_path == "root/VarSet/boxLength"
            ).id_preview,
            "par.root.varSet.boxLength",
        )
        self.assertEqual(snapshot.errors, ())
        self.assertTrue(snapshot.can_review)

    def test_semantic_name_collision_is_reported(self) -> None:
        state = _state()
        state.set_component_name("root", "Pad")
        state.set_component_included("Body", True)
        state.set_component_name("Body", "Body")
        state.set_feature_included("Pad", True)
        state.set_feature_name("Pad", "Pad")

        snapshot = state.snapshot()
        self.assertTrue(
            any("collides" in error for error in snapshot.errors), snapshot.errors
        )
        self.assertFalse(snapshot.can_review)

    def test_invalid_semantic_name_is_reported(self) -> None:
        state = _state()
        state.set_component_name("root", "1 invalid")
        snapshot = state.snapshot()
        self.assertTrue(snapshot.errors)
        self.assertFalse(snapshot.can_review)

    def test_build_decisions_includes_only_selected(self) -> None:
        state = _state()
        state.set_options(CapturePanelOptions(capture_id="cap.test.v1"))
        state.set_component_name("root", "Root")
        state.set_component_included("Body", True)
        state.set_component_name("Body", "Body")
        state.set_feature_included("Pad", True)
        state.set_feature_name("Pad", "Pad")

        decisions = state.build_decisions()
        self.assertEqual(decisions.capture_id, "cap.test.v1")
        self.assertEqual(
            [item.native_ref for item in decisions.components],
            ["Body", "root"],
        )
        self.assertEqual([item.native_ref for item in decisions.features], ["Pad"])
        self.assertEqual(decisions.parameters, ())


class PanelParameterTests(unittest.TestCase):
    def _capture_root_and_group(self) -> CapturePanelState:
        state = _state()
        state.set_component_name("root", "Root")
        state.set_group_included("VarSet", True)
        state.set_group_name("VarSet", "VarSet")
        return state

    def test_parameter_rows_gated_and_resolved(self) -> None:
        state = _state()
        state.set_component_name("root", "Root")

        before = next(
            row
            for row in state.snapshot().parameters
            if row.native_path == "root/VarSet/boxLength"
        )
        self.assertTrue(before.disabled)
        self.assertIn("owner", before.disabled_reason)

        state.set_group_included("VarSet", True)
        state.set_group_name("VarSet", "VarSet")
        snapshot = state.snapshot()
        length = next(
            row
            for row in snapshot.parameters
            if row.native_path == "root/VarSet/boxLength"
        )
        self.assertFalse(length.disabled)
        self.assertEqual(length.semantic_type, "length")
        self.assertEqual(length.semantic_unit, "mm")
        self.assertEqual(length.native_unit, "mm")
        self.assertTrue(length.observable)
        self.assertTrue(length.writable)

        count = next(
            row for row in snapshot.parameters if row.native_path == "root/VarSet/count"
        )
        self.assertEqual(count.semantic_type, "count")
        self.assertEqual(count.semantic_unit, "count")

    def test_unsupported_parameter_is_disabled(self) -> None:
        state = self._capture_root_and_group()
        vector = next(
            row for row in state.snapshot().parameters if row.native_key == "vec"
        )
        self.assertTrue(vector.disabled)
        self.assertIn("scalar", vector.disabled_reason)
        with self.assertRaises(CapturePanelError):
            state.set_parameter_included("root/VarSet/vec", True)

    def test_parameter_requires_semantic_type_mapping(self) -> None:
        discovery = _discovery()
        selection = build_default_semantic_selection(discovery)
        state = CapturePanelState(
            discovery,
            type(selection)(
                mapping_id=selection.mapping_id,
                parameter_types=selection.parameter_types,
                native_type_to_semantic_type={},
                cad_system_min_version=selection.cad_system_min_version,
            ),
        )
        state.set_component_name("root", "Root")
        state.set_group_included("VarSet", True)
        state.set_group_name("VarSet", "VarSet")
        length = next(
            row
            for row in state.snapshot().parameters
            if row.native_path == "root/VarSet/boxLength"
        )
        self.assertTrue(length.disabled)
        self.assertIn("No semantic type", length.disabled_reason)

    def test_semantic_type_can_be_remapped(self) -> None:
        state = self._capture_root_and_group()
        state.set_parameter_semantic_type("App::PropertyInteger", "length")
        count = next(
            row
            for row in state.snapshot().parameters
            if row.native_path == "root/VarSet/count"
        )
        self.assertEqual(count.semantic_type, "length")
        self.assertEqual(
            state.build_semantic_selection().native_type_to_semantic_type[
                "App::PropertyInteger"
            ],
            "length",
        )


class PanelFeatureAndMetadataTests(unittest.TestCase):
    def _capture_body(self) -> CapturePanelState:
        state = _state()
        state.set_component_name("root", "Root")
        state.set_component_included("Body", True)
        state.set_component_name("Body", "Body")
        return state

    def test_feature_actions_default_and_narrowing(self) -> None:
        state = self._capture_body()
        state.set_feature_included("Pad", True)
        state.set_feature_name("Pad", "Pad")

        row = next(row for row in state.snapshot().features if row.native_ref == "Pad")
        self.assertIn("suppress", row.captured_actions)
        self.assertEqual(row.authorized_actions, row.captured_actions)

        state.set_feature_authorized_actions("Pad", frozenset({"suppress"}))
        row = next(row for row in state.snapshot().features if row.native_ref == "Pad")
        self.assertEqual(row.authorized_actions, ("suppress",))

        with self.assertRaises(CapturePanelError):
            state.set_feature_authorized_actions("Pad", frozenset({"explode"}))

    def test_metadata_supported_and_unsupported_states(self) -> None:
        state = _state()
        state.set_component_name("root", "Root")
        state.set_component_included("Body", True)
        state.set_component_name("Body", "Body")

        snapshot = state.snapshot()
        material = next(
            row for row in snapshot.metadata if row.native_key == "material"
        )
        measured = next(
            row for row in snapshot.metadata if row.native_key == "measured"
        )
        self.assertFalse(material.disabled)
        self.assertTrue(measured.disabled)
        self.assertIn("authorable", measured.disabled_reason)

        state.set_metadata_included("root/Body/material", True)
        self.assertIn(
            "meta.body.material",
            [row.id_preview for row in state.snapshot().metadata if row.included],
        )
        with self.assertRaises(CapturePanelError):
            state.set_metadata_included("root/Body/measured", True)

    def test_metadata_owner_must_be_captured(self) -> None:
        state = _state()
        state.set_component_name("root", "Root")
        with self.assertRaises(CapturePanelError):
            state.set_metadata_included("root/Body/material", True)


class PanelSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        _write_project(self.root)
        self.context = load_project_context(self.root)
        self.model = resolve_selected_model(self.context, "model")
        self.discovery = _discovery()

    def _session(self) -> CaptureSession:
        selection = load_semantic_selection(
            self.context, self.discovery, cad_system_min_version="1.1.4"
        )
        return CaptureSession(
            context=self.context,
            model=self.model,
            discovery=self.discovery,
            semantic_selection=selection,
        )

    def _fill_full_capture(self, session: CaptureSession) -> None:
        state = session.state
        state.set_component_name("root", "Root")
        state.set_component_included("Body", True)
        state.set_component_name("Body", "Body")
        state.set_feature_included("Pad", True)
        state.set_feature_name("Pad", "Pad")
        state.set_group_included("VarSet", True)
        state.set_group_name("VarSet", "VarSet")
        state.set_parameter_included("root/VarSet/boxLength", True)
        state.set_parameter_name("root/VarSet/boxLength", "boxLength")
        state.set_metadata_included("root/Body/material", True)

    def test_session_preview_and_commit(self) -> None:
        session = self._session()
        self._fill_full_capture(session)
        snapshot = session.snapshot()
        self.assertTrue(snapshot.can_review, snapshot.errors)

        source = self.root / "input" / "model.FCStd"
        mapping = self.root / "prm.project.json"
        source_before = source.read_bytes()
        mapping_before = mapping.read_bytes()

        plan = session.preview()
        self.assertEqual(plan.status, "create")
        self.assertFalse(plan.capture_path.exists())

        summary = session.commit(confirm_replace=False)
        self.assertTrue(summary.wrote_capture)
        self.assertTrue(summary.wrote_semantic)
        self.assertTrue(plan.capture_path.is_file())
        self.assertTrue(plan.semantic_path.is_file())
        self.assertEqual(source.read_bytes(), source_before)
        self.assertEqual(mapping.read_bytes(), mapping_before)

        repeat = self._session()
        self._fill_full_capture(repeat)
        self.assertEqual(repeat.preview().status, "unchanged")

    def test_session_uses_project_semantic_map_when_present(self) -> None:
        session = self._session()
        self._fill_full_capture(session)
        session.commit(confirm_replace=False)

        self.assertTrue((self.root / "prm.semantic-map.json").is_file())
        selection = load_semantic_selection(
            self.context, self.discovery, cad_system_min_version="1.1.4"
        )
        self.assertEqual(selection.mapping_id, "workbench-capture-v1")
        self.assertIn("App::PropertyLength", selection.native_type_to_semantic_type)


if __name__ == "__main__":
    unittest.main()
