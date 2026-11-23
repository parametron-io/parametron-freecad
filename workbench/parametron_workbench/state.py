"""GUI-free state model for the Parametron capture workbench panel.

The panel state is the testable heart of the four-tab capture UI. It holds the
user's explicit selections and semantic names, enforces top-down gating, and
computes per-row validation, generated ID previews, collision diagnostics, and
tab availability. It never imports FreeCAD, FreeCADGui, or Qt.

The authoritative capture contract validation still happens in
``parametron_freecad.capture`` when a review or write is requested. This state
provides immediate, deterministic UI feedback without duplicating document,
discovery, or serialization logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from parametron_freecad.capture import (
    CaptureDecisions,
    CaptureDiscovery,
    ComponentCandidate,
    ComponentDecision,
    FeatureCandidate,
    FeatureDecision,
    FreeCADSemanticMapSelection,
    MetadataCandidate,
    MetadataDecision,
    ParameterCandidate,
    ParameterDecision,
    ParameterGroupCandidate,
    ParameterGroupDecision,
    SemanticParameterTypeSelection,
    derive_capture_id,
    generate_component_id,
    generate_feature_id,
    generate_group_owned_parameter_id,
    generate_metadata_id,
    generate_parameter_group_id,
    generate_parameter_id,
    validate_semantic_name,
)
from parametron_freecad.capture.native_types import (
    METADATA_NATIVE_TYPES,
    PARAMETER_NATIVE_TYPES,
)

_ACTION_FIELDS = ("suppress", "unsuppress", "hide", "unhide", "delete")


class CapturePanelError(ValueError):
    """Raised when a panel state transition is not allowed."""


class CaptureTab(str, Enum):
    """The four top-down capture tabs."""

    PARTS = "parts"
    FEATURES = "features"
    PARAMETERS = "parameters"
    METADATA = "metadata"


@dataclass(frozen=True, slots=True)
class TabAvailability:
    """Whether a tab is enabled and, if not, why."""

    enabled: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ComponentRow:
    native_ref: str
    native_label: str
    cad_type: str
    kind: str
    synthetic: bool
    parent_native_ref: str | None
    included: bool
    name: str
    display_name: str
    id_preview: str | None
    name_error: str | None
    id_error: str | None
    disabled: bool
    disabled_reason: str


@dataclass(frozen=True, slots=True)
class FeatureRow:
    native_ref: str
    native_label: str
    cad_type: str
    component_native_ref: str
    included: bool
    name: str
    display_name: str
    id_preview: str | None
    name_error: str | None
    id_error: str | None
    disabled: bool
    disabled_reason: str
    captured_actions: tuple[str, ...]
    authorized_actions: tuple[str, ...]
    delete_dependents: tuple[str, ...]
    delete_dependencies: tuple[str, ...]
    dependency_evidence_available: bool


@dataclass(frozen=True, slots=True)
class ParameterRow:
    native_path: str
    native_key: str
    cad_type: str
    value_type: str
    native_unit: str
    semantic_type: str | None
    semantic_unit: str | None
    authorable: bool
    observable: bool
    writable: bool
    owner_kind: str
    owner_native_ref: str
    included: bool
    name: str
    display_name: str
    id_preview: str | None
    name_error: str | None
    id_error: str | None
    disabled: bool
    disabled_reason: str


@dataclass(frozen=True, slots=True)
class MetadataRow:
    native_path: str
    native_key: str
    cad_type: str
    value_type: str
    observable: bool
    writable: bool
    owner_kind: str
    owner_native_ref: str
    included: bool
    display_name: str
    id_preview: str | None
    id_error: str | None
    disabled: bool
    disabled_reason: str


@dataclass(frozen=True, slots=True)
class CapturePanelSnapshot:
    """Deterministic, render-ready view of the whole capture panel."""

    tabs: Mapping[CaptureTab, TabAvailability]
    components: tuple[ComponentRow, ...]
    features: tuple[FeatureRow, ...]
    parameters: tuple[ParameterRow, ...]
    metadata: tuple[MetadataRow, ...]
    errors: tuple[str, ...]
    can_review: bool
    has_captured_component: bool


@dataclass(frozen=True, slots=True)
class CapturePanelOptions:
    """Project-level capture options supplied by the session, not the UI."""

    capture_id: str = ""
    adapter_version: str = ""
    cad_system_version: str = ""


@dataclass
class _ComponentSelection:
    included: bool
    name: str = ""
    display_name: str | None = None


@dataclass
class _FeatureSelection:
    included: bool
    name: str = ""
    display_name: str | None = None
    authorized_actions: frozenset[str] | None = None


@dataclass
class _GroupSelection:
    included: bool
    name: str = ""
    display_name: str | None = None


@dataclass
class _ParameterSelection:
    included: bool
    name: str = ""
    display_name: str = ""


@dataclass
class _MetadataSelection:
    included: bool
    display_name: str = ""


class CapturePanelState:
    """Mutable four-tab capture state with deterministic snapshots."""

    def __init__(
        self,
        discovery: CaptureDiscovery,
        semantic_selection: FreeCADSemanticMapSelection,
        *,
        options: CapturePanelOptions | None = None,
    ) -> None:
        if not isinstance(discovery, CaptureDiscovery):
            raise TypeError("CapturePanelState requires CaptureDiscovery")
        if not isinstance(semantic_selection, FreeCADSemanticMapSelection):
            raise TypeError("CapturePanelState requires FreeCADSemanticMapSelection")

        self._discovery = discovery
        self._semantic_selection = semantic_selection
        self._options = options or CapturePanelOptions()
        self._root_ref = discovery.root_component_native_ref

        self._components_by_ref: dict[str, ComponentCandidate] = {
            item.native_ref: item for item in discovery.components
        }
        self._features_by_ref: dict[str, FeatureCandidate] = {
            item.native_ref: item for item in discovery.features
        }
        self._groups_by_ref: dict[str, ParameterGroupCandidate] = {
            item.native_ref: item for item in discovery.parameter_groups
        }
        self._parameters_by_path: dict[str, ParameterCandidate] = {
            item.native_path: item for item in discovery.parameters
        }
        self._metadata_by_path: dict[str, MetadataCandidate] = {
            item.native_path: item for item in discovery.metadata
        }

        self._parameter_types: dict[str, SemanticParameterTypeSelection] = {
            entry.name: entry for entry in semantic_selection.parameter_types
        }
        self._native_type_map: dict[str, str] = dict(
            semantic_selection.native_type_to_semantic_type
        )

        self._components: dict[str, _ComponentSelection] = {
            item.native_ref: _ComponentSelection(
                included=item.native_ref == self._root_ref,
            )
            for item in discovery.components
        }
        self._features: dict[str, _FeatureSelection] = {
            item.native_ref: _FeatureSelection(included=False)
            for item in discovery.features
        }
        self._groups: dict[str, _GroupSelection] = {
            item.native_ref: _GroupSelection(included=False)
            for item in discovery.parameter_groups
        }
        self._parameters: dict[str, _ParameterSelection] = {
            item.native_path: _ParameterSelection(included=False)
            for item in discovery.parameters
        }
        self._metadata: dict[str, _MetadataSelection] = {
            item.native_path: _MetadataSelection(included=False)
            for item in discovery.metadata
        }

    # -- queries ---------------------------------------------------------

    @property
    def discovery(self) -> CaptureDiscovery:
        return self._discovery

    @property
    def root_component_native_ref(self) -> str:
        return self._root_ref

    @property
    def options(self) -> CapturePanelOptions:
        return self._options

    def set_options(self, options: CapturePanelOptions) -> None:
        self._options = options

    # -- component selection --------------------------------------------

    def set_component_included(self, native_ref: str, included: bool) -> None:
        candidate = self._require_component(native_ref)
        if not isinstance(included, bool):
            raise TypeError("included must be a bool")
        if native_ref == self._root_ref:
            if not included:
                raise CapturePanelError("the root component must remain captured")
            self._components[native_ref].included = True
            return
        if included and not self._component_owner_included(candidate):
            raise CapturePanelError(
                f'component "{native_ref}" requires its parent '
                f'"{candidate.parent_native_ref}" to be captured first'
            )
        self._components[native_ref].included = included
        self._normalize()

    def set_component_name(self, native_ref: str, name: str) -> None:
        self._require_component(native_ref)
        self._components[native_ref].name = name

    def set_component_display_name(
        self, native_ref: str, display_name: str | None
    ) -> None:
        self._require_component(native_ref)
        self._components[native_ref].display_name = display_name

    # -- feature selection ----------------------------------------------

    def set_feature_included(self, native_ref: str, included: bool) -> None:
        candidate = self._require_feature(native_ref)
        if not isinstance(included, bool):
            raise TypeError("included must be a bool")
        if (
            included
            and not self._components.get(
                candidate.component_native_ref, _ComponentSelection(False)
            ).included
        ):
            raise CapturePanelError(
                f'feature "{native_ref}" requires its component '
                f'"{candidate.component_native_ref}" to be captured first'
            )
        self._features[native_ref].included = included
        self._normalize()

    def set_feature_name(self, native_ref: str, name: str) -> None:
        self._require_feature(native_ref)
        self._features[native_ref].name = name

    def set_feature_display_name(
        self, native_ref: str, display_name: str | None
    ) -> None:
        self._require_feature(native_ref)
        self._features[native_ref].display_name = display_name

    def set_feature_authorized_actions(
        self, native_ref: str, actions: frozenset[str] | None
    ) -> None:
        candidate = self._require_feature(native_ref)
        if actions is not None:
            if not isinstance(actions, frozenset):
                raise TypeError("authorized actions must be a frozenset or None")
            unknown = sorted(set(actions) - set(_ACTION_FIELDS))
            if unknown:
                raise CapturePanelError("unknown target actions: " + ", ".join(unknown))
            unsupported = sorted(
                action
                for action in actions
                if not bool(getattr(candidate.targetability, action))
            )
            if unsupported:
                raise CapturePanelError(
                    "target actions are not captured for "
                    f'"{native_ref}": ' + ", ".join(unsupported)
                )
        self._features[native_ref].authorized_actions = actions

    # -- parameter group selection --------------------------------------

    def set_group_included(self, native_ref: str, included: bool) -> None:
        candidate = self._require_group(native_ref)
        if not isinstance(included, bool):
            raise TypeError("included must be a bool")
        if (
            included
            and not self._components.get(
                candidate.owner_component_native_ref, _ComponentSelection(False)
            ).included
        ):
            raise CapturePanelError(
                f'parameter group "{native_ref}" requires its component '
                f'"{candidate.owner_component_native_ref}" to be captured first'
            )
        self._groups[native_ref].included = included
        self._normalize()

    def set_group_name(self, native_ref: str, name: str) -> None:
        self._require_group(native_ref)
        self._groups[native_ref].name = name

    def set_group_display_name(self, native_ref: str, display_name: str | None) -> None:
        self._require_group(native_ref)
        self._groups[native_ref].display_name = display_name

    # -- parameter selection --------------------------------------------

    def set_parameter_included(self, native_path: str, included: bool) -> None:
        candidate = self._require_parameter(native_path)
        if not isinstance(included, bool):
            raise TypeError("included must be a bool")
        if included:
            self._require_parameter_authorable(candidate)
            if not self._parameter_owner_included(candidate):
                raise CapturePanelError(
                    f'parameter "{native_path}" requires its owner '
                    f'"{candidate.owner_native_ref}" to be captured first'
                )
        self._parameters[native_path].included = included
        self._normalize()

    def set_parameter_name(self, native_path: str, name: str) -> None:
        self._require_parameter(native_path)
        self._parameters[native_path].name = name

    def set_parameter_display_name(self, native_path: str, display_name: str) -> None:
        self._require_parameter(native_path)
        self._parameters[native_path].display_name = display_name

    def set_parameter_semantic_type(
        self, native_type_id: str, semantic_type: str
    ) -> None:
        if semantic_type and semantic_type not in self._parameter_types:
            raise CapturePanelError(
                f"unknown semantic parameter type {semantic_type!r}"
            )
        if semantic_type:
            self._native_type_map[native_type_id] = semantic_type
        else:
            self._native_type_map.pop(native_type_id, None)
        self._normalize()

    # -- metadata selection ---------------------------------------------

    def set_metadata_included(self, native_path: str, included: bool) -> None:
        candidate = self._require_metadata(native_path)
        if not isinstance(included, bool):
            raise TypeError("included must be a bool")
        if included:
            self._require_metadata_authorable(candidate)
            if not self._metadata_owner_included(candidate):
                raise CapturePanelError(
                    f'metadata "{native_path}" requires its owner '
                    f'"{candidate.owner_native_ref}" to be captured first'
                )
        self._metadata[native_path].included = included
        self._normalize()

    def set_metadata_display_name(self, native_path: str, display_name: str) -> None:
        self._require_metadata(native_path)
        self._metadata[native_path].display_name = display_name

    # -- snapshot --------------------------------------------------------

    def snapshot(self) -> CapturePanelSnapshot:
        component_ids, component_errors = self._component_identities()
        feature_ids = self._feature_identities(component_ids)
        group_ids = self._group_identities(component_ids)
        parameter_ids = self._parameter_identities(
            component_ids, feature_ids, group_ids
        )
        metadata_ids = self._metadata_identities(component_ids, feature_ids)

        id_counts = self._count_ids(
            component_ids.items(),
            feature_ids.items(),
            group_ids.items(),
            parameter_ids.items(),
            metadata_ids.items(),
        )
        target_name_counts = self._count_names(
            (
                (ref, selection.name)
                for ref, selection in self._components.items()
                if selection.included
            ),
            (
                (ref, selection.name)
                for ref, selection in self._features.items()
                if selection.included
            ),
        )
        parameter_name_counts = self._count_names(
            (
                (path, selection.name)
                for path, selection in self._parameters.items()
                if selection.included
            ),
        )

        component_rows = self._component_rows(
            component_ids, component_errors, id_counts, target_name_counts
        )
        feature_rows = self._feature_rows(
            component_ids, feature_ids, id_counts, target_name_counts
        )
        parameter_rows = self._parameter_rows(
            parameter_ids,
            id_counts,
            parameter_name_counts,
        )
        metadata_rows = self._metadata_rows(metadata_ids, id_counts)

        captured = tuple(
            row for row in component_rows if row.included and row.name_error is None
        )
        has_captured_component = bool(captured)

        errors = self._collect_errors(
            component_rows,
            feature_rows,
            parameter_rows,
            metadata_rows,
        )

        gated = TabAvailability(
            enabled=has_captured_component,
            reason=(
                ""
                if has_captured_component
                else "Capture and name a part or assembly on the Part/Assembly "
                "tab first."
            ),
        )
        tabs = {
            CaptureTab.PARTS: TabAvailability(enabled=True),
            CaptureTab.FEATURES: gated,
            CaptureTab.PARAMETERS: gated,
            CaptureTab.METADATA: gated,
        }

        can_review = (
            has_captured_component
            and bool(self._components[self._root_ref].included)
            and not errors
        )

        return CapturePanelSnapshot(
            tabs=tabs,
            components=tuple(component_rows),
            features=tuple(feature_rows),
            parameters=tuple(parameter_rows),
            metadata=tuple(metadata_rows),
            errors=errors,
            can_review=can_review,
            has_captured_component=has_captured_component,
        )

    def build_semantic_selection(self) -> FreeCADSemanticMapSelection:
        """Return the current native-to-semantic map as a selection."""

        return FreeCADSemanticMapSelection(
            mapping_id=self._semantic_selection.mapping_id,
            parameter_types=self._semantic_selection.parameter_types,
            native_type_to_semantic_type=dict(self._native_type_map),
            cad_system_min_version=self._semantic_selection.cad_system_min_version,
        )

    def build_decisions(self) -> CaptureDecisions:
        """Return explicit decisions for the currently included entities."""

        return CaptureDecisions(
            components=tuple(
                ComponentDecision(
                    native_ref=ref,
                    name=selection.name,
                    display_name=selection.display_name,
                )
                for ref, selection in sorted(self._components.items())
                if selection.included
            ),
            features=tuple(
                FeatureDecision(
                    native_ref=ref,
                    name=selection.name,
                    display_name=selection.display_name,
                    authorized_actions=selection.authorized_actions,
                )
                for ref, selection in sorted(self._features.items())
                if selection.included
            ),
            parameter_groups=tuple(
                ParameterGroupDecision(
                    native_ref=ref,
                    name=selection.name,
                    display_name=selection.display_name,
                )
                for ref, selection in sorted(self._groups.items())
                if selection.included
            ),
            parameters=tuple(
                ParameterDecision(
                    native_path=path,
                    name=selection.name,
                    display_name=selection.display_name,
                )
                for path, selection in sorted(self._parameters.items())
                if selection.included
            ),
            metadata=tuple(
                MetadataDecision(
                    native_path=path,
                    display_name=selection.display_name,
                )
                for path, selection in sorted(self._metadata.items())
                if selection.included
            ),
            capture_id=self._options.capture_id,
            adapter_version=self._options.adapter_version,
            cad_system_version=self._options.cad_system_version,
        )

    def default_capture_id(self, project_id: str, logical_id: str) -> str:
        if self._options.capture_id:
            return self._options.capture_id
        return derive_capture_id(project_id, logical_id)

    def semantic_parameter_type_names(self) -> tuple[str, ...]:
        """Return the declared semantic parameter type names, sorted."""

        return tuple(sorted(self._parameter_types))

    # -- internal helpers ------------------------------------------------

    def _require_component(self, native_ref: str) -> ComponentCandidate:
        candidate = self._components_by_ref.get(native_ref)
        if candidate is None:
            raise CapturePanelError(f'unknown component "{native_ref}"')
        return candidate

    def _require_feature(self, native_ref: str) -> FeatureCandidate:
        candidate = self._features_by_ref.get(native_ref)
        if candidate is None:
            raise CapturePanelError(f'unknown feature "{native_ref}"')
        return candidate

    def _require_group(self, native_ref: str) -> ParameterGroupCandidate:
        candidate = self._groups_by_ref.get(native_ref)
        if candidate is None:
            raise CapturePanelError(f'unknown parameter group "{native_ref}"')
        return candidate

    def _require_parameter(self, native_path: str) -> ParameterCandidate:
        candidate = self._parameters_by_path.get(native_path)
        if candidate is None:
            raise CapturePanelError(f'unknown parameter "{native_path}"')
        return candidate

    def _require_metadata(self, native_path: str) -> MetadataCandidate:
        candidate = self._metadata_by_path.get(native_path)
        if candidate is None:
            raise CapturePanelError(f'unknown metadata "{native_path}"')
        return candidate

    def _component_owner_included(self, candidate: ComponentCandidate) -> bool:
        if candidate.native_ref == self._root_ref:
            return True
        parent = candidate.parent_native_ref
        return (
            parent is not None
            and self._components.get(parent, _ComponentSelection(False)).included
        )

    def _parameter_owner_included(self, candidate: ParameterCandidate) -> bool:
        if candidate.owner_kind == "component":
            return self._components.get(
                candidate.owner_native_ref, _ComponentSelection(False)
            ).included
        if candidate.owner_kind == "feature":
            return self._features.get(
                candidate.owner_native_ref, _FeatureSelection(False)
            ).included
        if candidate.owner_kind == "group":
            return self._groups.get(
                candidate.owner_native_ref, _GroupSelection(False)
            ).included
        return False

    def _metadata_owner_included(self, candidate: MetadataCandidate) -> bool:
        if candidate.owner_kind == "component":
            return self._components.get(
                candidate.owner_native_ref, _ComponentSelection(False)
            ).included
        if candidate.owner_kind == "feature":
            return self._features.get(
                candidate.owner_native_ref, _FeatureSelection(False)
            ).included
        return False

    def _require_parameter_authorable(self, candidate: ParameterCandidate) -> None:
        if (
            not candidate.property.supported
            or candidate.property.native_type_id not in PARAMETER_NATIVE_TYPES
        ):
            raise CapturePanelError(
                f'parameter "{candidate.native_path}" has an unsupported native type'
            )
        if candidate.property.native_type_id not in self._native_type_map:
            raise CapturePanelError(
                f'parameter "{candidate.native_path}" has no selected semantic type'
            )

    def _require_metadata_authorable(self, candidate: MetadataCandidate) -> None:
        if (
            not candidate.property.supported
            or candidate.property.native_type_id not in METADATA_NATIVE_TYPES
        ):
            raise CapturePanelError(
                f'metadata "{candidate.native_path}" has an unsupported native type'
            )

    def _normalize(self) -> None:
        """Force selection consistency after cascading exclusions."""

        for ref in sorted(self._components):
            selection = self._components[ref]
            if ref == self._root_ref:
                selection.included = True
                continue
            if selection.included and not self._component_owner_included(
                self._components_by_ref[ref]
            ):
                selection.included = False

        for ref in sorted(self._features):
            selection = self._features[ref]
            if (
                selection.included
                and not self._components.get(
                    self._features_by_ref[ref].component_native_ref,
                    _ComponentSelection(False),
                ).included
            ):
                selection.included = False

        for ref in sorted(self._groups):
            selection = self._groups[ref]
            if (
                selection.included
                and not self._components.get(
                    self._groups_by_ref[ref].owner_component_native_ref,
                    _ComponentSelection(False),
                ).included
            ):
                selection.included = False

        for path in sorted(self._parameters):
            selection = self._parameters[path]
            if not selection.included:
                continue
            candidate = self._parameters_by_path[path]
            if (
                not candidate.property.supported
                or candidate.property.native_type_id not in PARAMETER_NATIVE_TYPES
                or candidate.property.native_type_id not in self._native_type_map
                or not self._parameter_owner_included(candidate)
            ):
                selection.included = False

        for path in sorted(self._metadata):
            selection = self._metadata[path]
            if not selection.included:
                continue
            candidate = self._metadata_by_path[path]
            if (
                not candidate.property.supported
                or candidate.property.native_type_id not in METADATA_NATIVE_TYPES
                or not self._metadata_owner_included(candidate)
            ):
                selection.included = False

    def _component_identities(
        self,
    ) -> tuple[dict[str, str], dict[str, str | None]]:
        ids: dict[str, str] = {}
        errors: dict[str, str | None] = {}
        for ref in sorted(self._components):
            selection = self._components[ref]
            if not selection.included:
                continue
            name_error = _name_error(selection.name)
            if name_error is not None:
                errors[ref] = name_error
                continue
            ids[ref] = generate_component_id(selection.name)
        return ids, errors

    def _feature_identities(self, component_ids: Mapping[str, str]) -> dict[str, str]:
        ids: dict[str, str] = {}
        for ref in sorted(self._features):
            selection = self._features[ref]
            if not selection.included or _name_error(selection.name) is not None:
                continue
            parent_id = component_ids.get(
                self._features_by_ref[ref].component_native_ref
            )
            if parent_id is None:
                continue
            ids[ref] = generate_feature_id(parent_id, selection.name)
        return ids

    def _group_identities(self, component_ids: Mapping[str, str]) -> dict[str, str]:
        ids: dict[str, str] = {}
        for ref in sorted(self._groups):
            selection = self._groups[ref]
            if not selection.included or _name_error(selection.name) is not None:
                continue
            owner_id = component_ids.get(
                self._groups_by_ref[ref].owner_component_native_ref
            )
            if owner_id is None:
                continue
            ids[ref] = generate_parameter_group_id(owner_id, selection.name)
        return ids

    def _parameter_identities(
        self,
        component_ids: Mapping[str, str],
        feature_ids: Mapping[str, str],
        group_ids: Mapping[str, str],
    ) -> dict[str, str]:
        ids: dict[str, str] = {}
        for path in sorted(self._parameters):
            selection = self._parameters[path]
            if not selection.included or _name_error(selection.name) is not None:
                continue
            candidate = self._parameters_by_path[path]
            component_id = component_ids.get(candidate.component_native_ref)
            if component_id is None:
                continue
            if candidate.owner_kind == "group":
                group_id = group_ids.get(candidate.owner_native_ref)
                if group_id is None:
                    continue
                ids[path] = generate_group_owned_parameter_id(
                    component_id, group_id, selection.name
                )
            else:
                owner_id = self._owner_id(
                    candidate, component_ids, feature_ids, group_ids
                )
                if owner_id is None:
                    continue
                ids[path] = generate_parameter_id(owner_id, selection.name)
        return ids

    def _metadata_identities(
        self,
        component_ids: Mapping[str, str],
        feature_ids: Mapping[str, str],
    ) -> dict[str, str]:
        ids: dict[str, str] = {}
        for path in sorted(self._metadata):
            selection = self._metadata[path]
            if not selection.included:
                continue
            candidate = self._metadata_by_path[path]
            if candidate.owner_kind == "component":
                owner_id = component_ids.get(candidate.owner_native_ref)
            elif candidate.owner_kind == "feature":
                owner_id = feature_ids.get(candidate.owner_native_ref)
            else:
                owner_id = None
            if owner_id is None:
                continue
            ids[path] = generate_metadata_id(owner_id, candidate.property.native_key)
        return ids

    @staticmethod
    def _owner_id(
        candidate: ParameterCandidate,
        component_ids: Mapping[str, str],
        feature_ids: Mapping[str, str],
        group_ids: Mapping[str, str],
    ) -> str | None:
        if candidate.owner_kind == "component":
            return component_ids.get(candidate.owner_native_ref)
        if candidate.owner_kind == "feature":
            return feature_ids.get(candidate.owner_native_ref)
        if candidate.owner_kind == "group":
            return group_ids.get(candidate.owner_native_ref)
        return None

    @staticmethod
    def _count_ids(
        *groups: Any,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for group in groups:
            for _, identifier in group:
                counts[identifier] = counts.get(identifier, 0) + 1
        return counts

    @staticmethod
    def _count_names(*groups: Any) -> dict[str, int]:
        counts: dict[str, int] = {}
        for group in groups:
            for _, name in group:
                if _name_error(name) is None:
                    counts[name] = counts.get(name, 0) + 1
        return counts

    def _component_rows(
        self,
        component_ids: Mapping[str, str],
        component_errors: Mapping[str, str | None],
        id_counts: Mapping[str, int],
        name_counts: Mapping[str, int],
    ) -> list[ComponentRow]:
        rows: list[ComponentRow] = []
        for candidate in self._discovery.components:
            selection = self._components[candidate.native_ref]
            disabled, reason = self._component_disabled(candidate)
            identifier = component_ids.get(candidate.native_ref)
            rows.append(
                ComponentRow(
                    native_ref=candidate.native_ref,
                    native_label=candidate.native_label,
                    cad_type=candidate.cad_type,
                    kind=candidate.kind,
                    synthetic=candidate.synthetic,
                    parent_native_ref=candidate.parent_native_ref,
                    included=selection.included,
                    name=selection.name,
                    display_name=selection.display_name or "",
                    id_preview=identifier,
                    name_error=component_errors.get(candidate.native_ref),
                    id_error=_collision_error(
                        identifier,
                        id_counts,
                        name_counts,
                        selection.name,
                        selection.included,
                    ),
                    disabled=disabled,
                    disabled_reason=reason,
                )
            )
        return rows

    def _component_disabled(self, candidate: ComponentCandidate) -> tuple[bool, str]:
        if candidate.native_ref == self._root_ref:
            return False, ""
        if not self._component_owner_included(candidate):
            return (
                True,
                f'Capture parent "{candidate.parent_native_ref}" first.',
            )
        return False, ""

    def _feature_rows(
        self,
        component_ids: Mapping[str, str],
        feature_ids: Mapping[str, str],
        id_counts: Mapping[str, int],
        name_counts: Mapping[str, int],
    ) -> list[FeatureRow]:
        rows: list[FeatureRow] = []
        for candidate in self._discovery.features:
            selection = self._features[candidate.native_ref]
            owner_included = self._components.get(
                candidate.component_native_ref, _ComponentSelection(False)
            ).included
            disabled = not owner_included
            reason = (
                ""
                if owner_included
                else f'Capture component "{candidate.component_native_ref}" first.'
            )
            identifier = feature_ids.get(candidate.native_ref)
            captured = tuple(
                action
                for action in _ACTION_FIELDS
                if bool(getattr(candidate.targetability, action))
            )
            authorized = (
                captured
                if selection.authorized_actions is None
                else tuple(
                    action
                    for action in _ACTION_FIELDS
                    if action in selection.authorized_actions
                )
            )
            rows.append(
                FeatureRow(
                    native_ref=candidate.native_ref,
                    native_label=candidate.native_label,
                    cad_type=candidate.cad_type,
                    component_native_ref=candidate.component_native_ref,
                    included=selection.included,
                    name=selection.name,
                    display_name=selection.display_name or "",
                    id_preview=identifier,
                    name_error=(
                        _name_error(selection.name) if selection.included else None
                    ),
                    id_error=_collision_error(
                        identifier,
                        id_counts,
                        name_counts,
                        selection.name,
                        selection.included,
                    ),
                    disabled=disabled,
                    disabled_reason=reason,
                    captured_actions=captured,
                    authorized_actions=authorized,
                    delete_dependents=candidate.targetability.delete_dependents,
                    delete_dependencies=candidate.targetability.delete_dependencies,
                    dependency_evidence_available=(
                        candidate.targetability.dependency_evidence_available
                    ),
                )
            )
        return rows

    def _parameter_rows(
        self,
        parameter_ids: Mapping[str, str],
        id_counts: Mapping[str, int],
        name_counts: Mapping[str, int],
    ) -> list[ParameterRow]:
        rows: list[ParameterRow] = []
        for candidate in self._discovery.parameters:
            selection = self._parameters[candidate.native_path]
            authorable = (
                candidate.property.supported
                and candidate.property.native_type_id in PARAMETER_NATIVE_TYPES
            )
            semantic_name = None
            if candidate.property.native_type_id is not None:
                semantic_name = self._native_type_map.get(
                    candidate.property.native_type_id
                )
            semantic_unit = (
                self._parameter_types[semantic_name].default_unit
                if semantic_name in self._parameter_types
                else None
            )
            if not authorable:
                disabled = True
                reason = (
                    "Only supported native scalar properties can be captured as "
                    "parameters."
                )
            elif semantic_name is None:
                disabled = True
                reason = (
                    "No semantic type is selected for native type "
                    f'"{candidate.property.native_type_id}".'
                )
            elif not self._parameter_owner_included(candidate):
                disabled = True
                reason = f'Capture owner "{candidate.owner_native_ref}" first.'
            else:
                disabled = False
                reason = ""
            identifier = parameter_ids.get(candidate.native_path)
            rows.append(
                ParameterRow(
                    native_path=candidate.native_path,
                    native_key=candidate.property.native_key,
                    cad_type=candidate.property.native_type_id or "",
                    value_type=candidate.property.value_type or "",
                    native_unit=candidate.property.unit or "",
                    semantic_type=semantic_name,
                    semantic_unit=semantic_unit,
                    authorable=authorable,
                    observable=candidate.property.observable,
                    writable=candidate.property.writable,
                    owner_kind=candidate.owner_kind,
                    owner_native_ref=candidate.owner_native_ref,
                    included=selection.included,
                    name=selection.name,
                    display_name=selection.display_name,
                    id_preview=identifier,
                    name_error=(
                        _name_error(selection.name) if selection.included else None
                    ),
                    id_error=_collision_error(
                        identifier,
                        id_counts,
                        name_counts,
                        selection.name,
                        selection.included,
                    ),
                    disabled=disabled,
                    disabled_reason=reason,
                )
            )
        return rows

    def _metadata_rows(
        self,
        metadata_ids: Mapping[str, str],
        id_counts: Mapping[str, int],
    ) -> list[MetadataRow]:
        rows: list[MetadataRow] = []
        for candidate in self._discovery.metadata:
            selection = self._metadata[candidate.native_path]
            authorable = (
                candidate.property.supported
                and candidate.property.native_type_id in METADATA_NATIVE_TYPES
            )
            if not authorable:
                disabled = True
                reason = (
                    "Only existing String, Bool, Float, and Integer metadata is "
                    "authorable."
                )
            elif not self._metadata_owner_included(candidate):
                disabled = True
                reason = f'Capture owner "{candidate.owner_native_ref}" first.'
            else:
                disabled = False
                reason = ""
            identifier = metadata_ids.get(candidate.native_path)
            rows.append(
                MetadataRow(
                    native_path=candidate.native_path,
                    native_key=candidate.property.native_key,
                    cad_type=candidate.property.native_type_id or "",
                    value_type=candidate.property.value_type or "",
                    observable=candidate.property.observable,
                    writable=candidate.property.writable,
                    owner_kind=candidate.owner_kind,
                    owner_native_ref=candidate.owner_native_ref,
                    included=selection.included,
                    display_name=selection.display_name,
                    id_preview=identifier,
                    id_error=_id_collision_error(identifier, id_counts),
                    disabled=disabled,
                    disabled_reason=reason,
                )
            )
        return rows

    @staticmethod
    def _collect_errors(
        components: list[ComponentRow],
        features: list[FeatureRow],
        parameters: list[ParameterRow],
        metadata: list[MetadataRow],
    ) -> tuple[str, ...]:
        errors: list[str] = []
        for row in components:
            if row.included:
                if row.name_error:
                    errors.append(f"component {row.native_ref}: {row.name_error}")
                if row.id_error:
                    errors.append(f"component {row.native_ref}: {row.id_error}")
        for row in features:
            if row.included:
                if row.name_error:
                    errors.append(f"feature {row.native_ref}: {row.name_error}")
                if row.id_error:
                    errors.append(f"feature {row.native_ref}: {row.id_error}")
        for row in parameters:
            if row.included:
                if row.name_error:
                    errors.append(f"parameter {row.native_path}: {row.name_error}")
                if row.id_error:
                    errors.append(f"parameter {row.native_path}: {row.id_error}")
        for row in metadata:
            if row.included and row.id_error:
                errors.append(f"metadata {row.native_path}: {row.id_error}")
        return tuple(dict.fromkeys(errors))


def _name_error(name: str) -> str | None:
    if name == "" or name.strip() == "":
        return "a semantic name is required"
    try:
        validate_semantic_name(name)
    except ValueError as exc:
        return str(exc)
    return None


def _id_collision_error(
    identifier: str | None,
    id_counts: Mapping[str, int],
) -> str | None:
    if identifier is None:
        return None
    if id_counts.get(identifier, 0) > 1:
        return f'stable ID "{identifier}" collides with another captured entity'
    return None


def _collision_error(
    identifier: str | None,
    id_counts: Mapping[str, int],
    name_counts: Mapping[str, int],
    name: str,
    included: bool,
) -> str | None:
    if not included:
        return None
    error = _id_collision_error(identifier, id_counts)
    if error is not None:
        return error
    if _name_error(name) is None and name_counts.get(name, 0) > 1:
        return f'semantic name "{name}" collides with another captured entity'
    return None


__all__ = [
    "CapturePanelError",
    "CapturePanelOptions",
    "CapturePanelSnapshot",
    "CapturePanelState",
    "CaptureTab",
    "ComponentRow",
    "FeatureRow",
    "MetadataRow",
    "ParameterRow",
    "TabAvailability",
]
