"""GUI-free, FreeCAD-free capture orchestration.

This module composes the pieces built by earlier capture issues into one
deterministic operation:

1. explicit project context and selected model (``project``);
2. explicit user decisions (``decisions``);
3. native discovery candidates (``discovery``);
4. a schema 1.0 ``prm.cad.json`` document;
5. a versioned ``prm.semantic-map.json`` generated from explicit selections;
6. drift detection against retained capture;
7. deterministic previews and atomic, confirmed project-root writes.

It never imports FreeCAD, never opens a document, and never modifies the project
mapping or source document. The native caller verifies that the active document
is the declared saved source (``native_session``) before invoking this layer.

The Engine remains the final semantic/schema authority. This layer validates
capture invariants and produces contract-shaped output; it does not duplicate
Engine planning or verification decisions.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parametron_freecad.capture.canonical import canonical_capture_bytes
from parametron_freecad.capture.decisions import (
    CaptureDecisions,
    ComponentDecision,
    DrawingDecision,
    DrawingSheetDecision,
    FeatureDecision,
    MetadataDecision,
    ParameterDecision,
    derive_capture_id,
)
from parametron_freecad.capture.discovery import (
    CaptureDiscovery,
    ComponentCandidate,
    DrawingPageCandidate,
    FeatureCandidate,
    MetadataCandidate,
    ParameterCandidate,
    TargetabilityEvidence,
)
from parametron_freecad.capture.engine_preflight import EnginePreflightRunner
from parametron_freecad.capture.errors import CaptureContractError
from parametron_freecad.capture.fingerprint import document_fingerprint
from parametron_freecad.capture.model import (
    CaptureDocument,
    NamedVersion,
    SourceDocument,
    Targetability,
)
from parametron_freecad.capture.naming import (
    generate_component_id,
    generate_drawing_id,
    generate_drawing_sheet_id,
    generate_feature_id,
    generate_group_owned_parameter_id,
    generate_metadata_id,
    generate_parameter_group_id,
    generate_parameter_id,
)
from parametron_freecad.capture.orchestration_errors import (
    CaptureConfirmationRequiredError,
    CaptureDecisionError,
    CaptureDriftEntry,
    CaptureDriftError,
)
from parametron_freecad.capture.project import (
    CaptureProjectContext,
    ProjectModel,
    resolve_model_source_path,
)
from parametron_freecad.capture.semantic_map import (
    SEMANTIC_MAP_FILENAME,
    FreeCADSemanticMapSelection,
    SemanticMapUpdatePlan,
    build_semantic_map,
    plan_semantic_map_update,
    write_semantic_map,
)
from parametron_freecad.capture.writer import (
    CAPTURE_CONTRACT_FILENAME,
    write_capture_document,
)
from parametron_freecad.common.strict_json import StrictJsonError, loads_strict_json

_ACTION_FIELDS = ("suppress", "unsuppress", "hide", "unhide", "delete")


# ---------------------------------------------------------------------------
# Deterministic mapping diff
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MappingDiffEntry:
    """One deterministic difference between retained and proposed JSON."""

    path: str
    change: str
    existing: Any = None
    proposed: Any = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "change": self.change,
            "existing": copy.deepcopy(self.existing),
            "proposed": copy.deepcopy(self.proposed),
        }


def diff_mappings(
    existing: Mapping[str, Any] | None,
    proposed: Mapping[str, Any],
) -> tuple[MappingDiffEntry, ...]:
    """Return a sorted JSON-pointer diff between two mappings."""

    entries: list[MappingDiffEntry] = []
    if existing is None:
        entries.append(
            MappingDiffEntry(path="", change="added", existing=None, proposed=proposed)
        )
        return tuple(entries)
    _diff(existing, proposed, "", entries)
    return tuple(sorted(entries, key=lambda entry: (entry.path, entry.change)))


def _diff(
    existing: Any,
    proposed: Any,
    path: str,
    entries: list[MappingDiffEntry],
) -> None:
    if isinstance(existing, Mapping) and isinstance(proposed, Mapping):
        for key in sorted(set(existing) | set(proposed)):
            child_path = f"{path}/{_pointer_escape(str(key))}"
            if key not in existing:
                entries.append(
                    MappingDiffEntry(
                        path=child_path,
                        change="added",
                        existing=None,
                        proposed=proposed[key],
                    )
                )
            elif key not in proposed:
                entries.append(
                    MappingDiffEntry(
                        path=child_path,
                        change="removed",
                        existing=existing[key],
                        proposed=None,
                    )
                )
            else:
                _diff(existing[key], proposed[key], child_path, entries)
        return

    if existing != proposed:
        entries.append(
            MappingDiffEntry(
                path=path,
                change="changed",
                existing=existing,
                proposed=proposed,
            )
        )


def _pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


# ---------------------------------------------------------------------------
# Capture document construction
# ---------------------------------------------------------------------------


def build_capture_document(
    *,
    context: CaptureProjectContext,
    model: ProjectModel,
    discovery: CaptureDiscovery,
    decisions: CaptureDecisions,
    fingerprint: str | None = None,
) -> CaptureDocument:
    """Build one validated schema 1.0 capture document.

    ``fingerprint`` defaults to a ``sha256`` fingerprint of the saved source
    document bytes. The caller should verify the active document is saved and
    is the declared source before relying on that default.
    """

    if not isinstance(context, CaptureProjectContext):
        raise TypeError("build_capture_document requires CaptureProjectContext")
    if not isinstance(decisions, CaptureDecisions):
        raise TypeError("build_capture_document requires CaptureDecisions")

    source_path = resolve_model_source_path(context, model)
    computed_fingerprint = (
        fingerprint if fingerprint is not None else document_fingerprint(source_path)
    )

    mapping = _build_capture_mapping(
        context=context,
        model=model,
        discovery=discovery,
        decisions=decisions,
        fingerprint=computed_fingerprint,
    )
    return CaptureDocument.from_mapping(mapping)


def _build_capture_mapping(
    *,
    context: CaptureProjectContext,
    model: ProjectModel,
    discovery: CaptureDiscovery,
    decisions: CaptureDecisions,
    fingerprint: str,
) -> dict[str, Any]:
    problems: list[str] = []

    components_by_ref = _index_by(
        discovery.components, "nativeRef", lambda item: item.native_ref, problems
    )
    features_by_ref = _index_by(
        discovery.features, "nativeRef", lambda item: item.native_ref, problems
    )
    groups_by_ref = _index_by(
        discovery.parameter_groups, "nativeRef", lambda item: item.native_ref, problems
    )
    parameters_by_path = _index_by(
        discovery.parameters, "nativePath", lambda item: item.native_path, problems
    )
    metadata_by_path = _index_by(
        discovery.metadata, "nativePath", lambda item: item.native_path, problems
    )
    pages_by_ref = _index_by(
        discovery.drawings,
        "technical drawing page",
        lambda item: item.native_ref,
        problems,
    )

    component_decisions = _unique_decisions(
        decisions.components, "nativeRef", lambda item: item.native_ref, problems
    )
    feature_decisions = _unique_decisions(
        decisions.features, "nativeRef", lambda item: item.native_ref, problems
    )
    group_decisions = _unique_decisions(
        decisions.parameter_groups,
        "nativeRef",
        lambda item: item.native_ref,
        problems,
    )
    parameter_decisions = _unique_decisions(
        decisions.parameters, "nativePath", lambda item: item.native_path, problems
    )
    metadata_decisions = _unique_decisions(
        decisions.metadata, "nativePath", lambda item: item.native_path, problems
    )

    _require_known(component_decisions, components_by_ref, "component", problems)
    _require_known(feature_decisions, features_by_ref, "feature", problems)
    _require_known(group_decisions, groups_by_ref, "parameter group", problems)
    _require_known(parameter_decisions, parameters_by_path, "parameter", problems)
    _require_known(metadata_decisions, metadata_by_path, "metadata", problems)

    root_ref = discovery.root_component_native_ref
    if root_ref not in component_decisions:
        problems.append(
            f'root component "{root_ref}" must be included in capture decisions'
        )

    if problems:
        raise CaptureDecisionError(problems)

    # Top-down component closure.
    for ref, decision in component_decisions.items():
        candidate = components_by_ref[ref]
        if ref == root_ref:
            if candidate.parent_native_ref is not None:
                problems.append(
                    f'root component "{ref}" must not declare a parent '
                    f'("{candidate.parent_native_ref}")'
                )
            continue
        parent = candidate.parent_native_ref
        if parent is None:
            problems.append(
                f'component "{ref}" selected for capture has no native parent'
            )
        elif parent not in component_decisions:
            problems.append(
                f'component "{ref}" selected for capture requires its parent '
                f'"{parent}" to be selected'
            )

    for ref in feature_decisions:
        owner = features_by_ref[ref].component_native_ref
        if owner not in component_decisions:
            problems.append(
                f'feature "{ref}" selected for capture requires its component '
                f'"{owner}" to be selected'
            )
    for ref in group_decisions:
        owner = groups_by_ref[ref].owner_component_native_ref
        if owner not in component_decisions:
            problems.append(
                f'parameter group "{ref}" selected for capture requires its '
                f'component "{owner}" to be selected'
            )
    for path_key in parameter_decisions:
        candidate = parameters_by_path[path_key]
        if not candidate.property.supported:
            problems.append(
                f'parameter "{path_key}" cannot be captured: native type is not '
                "supported"
            )
            continue
        _require_owner_selected(
            candidate.owner_kind,
            candidate.owner_native_ref,
            component_decisions,
            feature_decisions,
            group_decisions,
            f'parameter "{path_key}"',
            problems,
        )
    for path_key in metadata_decisions:
        candidate = metadata_by_path[path_key]
        if not candidate.property.supported:
            problems.append(
                f'metadata "{path_key}" cannot be captured: native type is not '
                "supported"
            )
            continue
        _require_owner_selected(
            candidate.owner_kind,
            candidate.owner_native_ref,
            component_decisions,
            feature_decisions,
            group_decisions,
            f'metadata "{path_key}"',
            problems,
        )

    if problems:
        raise CaptureDecisionError(problems)

    component_ids, identity_paths = _component_identities(
        components_by_ref,
        component_decisions,
        root_ref,
    )
    feature_ids = {
        ref: (
            decision.id
            or generate_feature_id(
                component_ids[features_by_ref[ref].component_native_ref],
                decision.name,
                entity_path=f"features[{ref}].name",
            )
        )
        for ref, decision in feature_decisions.items()
    }
    group_ids = {
        ref: (
            decision.id
            or generate_parameter_group_id(
                component_ids[groups_by_ref[ref].owner_component_native_ref],
                decision.name,
                entity_path=f"parameterGroups[{ref}].name",
            )
        )
        for ref, decision in group_decisions.items()
    }
    parameter_ids = _parameter_ids(
        parameters_by_path,
        parameter_decisions,
        component_ids,
        feature_ids,
        group_ids,
    )
    metadata_ids = _metadata_ids(
        metadata_by_path,
        metadata_decisions,
        component_ids,
        feature_ids,
    )

    drawing_entries = _build_drawings(
        decisions.drawings,
        pages_by_ref,
        features_by_ref,
        component_decisions,
        component_ids,
        problems,
    )
    if problems:
        raise CaptureDecisionError(problems)

    components: list[dict[str, Any]] = []
    for ref in sorted(component_decisions):
        candidate = components_by_ref[ref]
        decision = component_decisions[ref]
        entry: dict[str, Any] = {
            "id": component_ids[ref],
            "kind": candidate.kind,
            "name": decision.name,
            "displayName": _display_name(decision.display_name, candidate),
            "cadType": candidate.cad_type,
            "quantity": (
                candidate.quantity if decision.quantity is None else decision.quantity
            ),
            "material": (
                candidate.material if decision.material is None else decision.material
            ),
            "identitySource": {
                "kind": "parent_scoped_path",
                "path": identity_paths[ref],
                "nativeRef": candidate.native_ref,
            },
            "targetability": _targetability_mapping(candidate.targetability),
            "annotations": decision.annotations.to_mapping(),
        }
        if decision.stability_class:
            entry["stabilityClass"] = decision.stability_class
        components.append(entry)

    features: list[dict[str, Any]] = []
    for ref in sorted(feature_decisions):
        candidate = features_by_ref[ref]
        decision = feature_decisions[ref]
        entry = {
            "id": feature_ids[ref],
            "componentId": component_ids[candidate.component_native_ref],
            "name": decision.name,
            "displayName": _display_name(decision.display_name, candidate),
            "cadType": candidate.cad_type,
            "identitySource": {
                "kind": "owner_scoped_key",
                "ownerScopedKey": candidate.owner_scoped_key,
                "nativeRef": candidate.native_ref,
            },
            "targetability": _authorized_targetability_mapping(
                candidate.targetability,
                decision,
                f"features[{ref}].authorizedActions",
            ),
            "annotations": decision.annotations.to_mapping(),
        }
        if decision.stability_class:
            entry["stabilityClass"] = decision.stability_class
        features.append(entry)

    groups: list[dict[str, Any]] = []
    for ref in sorted(group_decisions):
        candidate = groups_by_ref[ref]
        decision = group_decisions[ref]
        entry = {
            "id": group_ids[ref],
            "ownerComponentId": component_ids[candidate.owner_component_native_ref],
            "name": decision.name,
            "displayName": _display_name(decision.display_name, candidate),
            "groupKind": candidate.group_kind,
            "cadType": candidate.cad_type,
            "observable": candidate.observable,
            "writable": candidate.writable,
            "identitySource": {
                "kind": "owner_scoped_key",
                "ownerScopedKey": candidate.owner_scoped_key,
                "nativeRef": candidate.native_ref,
            },
            "annotations": decision.annotations.to_mapping(),
        }
        if decision.stability_class:
            entry["stabilityClass"] = decision.stability_class
        groups.append(entry)

    parameters: list[dict[str, Any]] = []
    for path_key in sorted(parameter_decisions):
        candidate = parameters_by_path[path_key]
        decision = parameter_decisions[path_key]
        owner_id = _owner_id(
            candidate,
            component_ids,
            feature_ids,
            group_ids,
        )
        identity: dict[str, Any] = {
            "kind": "owner_scoped_key",
            "ownerScopedKey": candidate.owner_scoped_key,
            "nativeRef": candidate.native_path,
        }
        if candidate.owner_kind == "group":
            identity["groupScopedKey"] = candidate.group_scoped_key
        entry = {
            "id": parameter_ids[path_key],
            "ownerKind": candidate.owner_kind,
            "ownerId": owner_id,
            "componentId": component_ids[candidate.component_native_ref],
            "name": decision.name,
            "displayName": decision.display_name,
            "cadType": candidate.property.native_type_id,
            "valueType": candidate.property.value_type,
            "observable": candidate.property.observable,
            "writable": candidate.property.writable,
            "currentValue": candidate.property.current_value,
            "identitySource": identity,
            "annotations": decision.annotations.to_mapping(),
        }
        if candidate.property.unit:
            entry["unit"] = candidate.property.unit
        if decision.stability_class:
            entry["stabilityClass"] = decision.stability_class
        parameters.append(entry)

    metadata: list[dict[str, Any]] = []
    for path_key in sorted(metadata_decisions):
        candidate = metadata_by_path[path_key]
        decision = metadata_decisions[path_key]
        owner_id = _owner_id(
            candidate,
            component_ids,
            feature_ids,
            group_ids,
        )
        entry = {
            "id": metadata_ids[path_key],
            "ownerKind": candidate.owner_kind,
            "ownerId": owner_id,
            "componentId": component_ids[candidate.component_native_ref],
            "key": candidate.property.native_key,
            "displayName": decision.display_name,
            "cadType": candidate.property.native_type_id,
            "valueType": candidate.property.value_type,
            "observable": candidate.property.observable,
            "writable": candidate.property.writable,
            "currentValue": candidate.property.current_value,
            "annotations": decision.annotations.to_mapping(),
        }
        if decision.stability_class:
            entry["stabilityClass"] = decision.stability_class
        metadata.append(entry)

    structure = _structure(components_by_ref, component_ids, root_ref)

    capture_id = decisions.capture_id or derive_capture_id(
        context.project_id, model.logical_id
    )

    return {
        "schemaVersion": "1.0",
        "captureId": capture_id,
        "adapter": NamedVersion("freecad", decisions.adapter_version).to_mapping(),
        "cadSystem": NamedVersion("FreeCAD", decisions.cad_system_version).to_mapping(),
        "sourceDocument": SourceDocument(
            logical_id=model.logical_id,
            path=model.path,
            fingerprint=fingerprint,
        ).to_mapping(),
        "rootProduct": {"id": component_ids[root_ref]},
        "annotations": decisions.annotations.to_mapping(),
        "entities": {
            "components": components,
            "features": features,
            "relationships": [],
            "parameterGroups": groups,
            "parameters": parameters,
            "metadata": metadata,
            "drawings": drawing_entries,
        },
        "structure": structure,
    }


def _index_by(
    items: tuple[Any, ...],
    label: str,
    key: Any,
    problems: list[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        value = key(item)
        if value in result:
            problems.append(f'discovery reports duplicate {label} "{value}"')
            continue
        result[value] = item
    return result


def _unique_decisions(
    decisions: tuple[Any, ...],
    label: str,
    key: Any,
    problems: list[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for decision in decisions:
        value = key(decision)
        if value in result:
            problems.append(f'capture decisions repeat {label} "{value}"')
            continue
        result[value] = decision
    return result


def _require_known(
    decisions: Mapping[str, Any],
    candidates: Mapping[str, Any],
    label: str,
    problems: list[str],
) -> None:
    for value in sorted(decisions):
        if value not in candidates:
            problems.append(f'capture decision selects unknown {label} "{value}"')


def _require_owner_selected(
    owner_kind: str,
    owner_native_ref: str,
    components: Mapping[str, Any],
    features: Mapping[str, Any],
    groups: Mapping[str, Any],
    subject: str,
    problems: list[str],
) -> None:
    if owner_kind == "component":
        selected = owner_native_ref in components
    elif owner_kind == "feature":
        selected = owner_native_ref in features
    elif owner_kind == "group":
        selected = owner_native_ref in groups
    else:
        problems.append(f'{subject} has unsupported owner kind "{owner_kind}"')
        return
    if not selected:
        problems.append(
            f'{subject} requires its owner "{owner_native_ref}" to be selected'
        )


def _display_name(decision_value: str | None, candidate: Any) -> str:
    if decision_value is not None:
        return decision_value
    label = getattr(candidate, "native_label", "")
    return label if label else ""


def _targetability(evidence: TargetabilityEvidence) -> Targetability:
    return Targetability(
        suppress=bool(evidence.suppress),
        unsuppress=bool(evidence.unsuppress),
        hide=bool(evidence.hide),
        unhide=bool(evidence.unhide),
        delete=bool(evidence.delete),
    )


def _targetability_mapping(evidence: TargetabilityEvidence) -> dict[str, bool]:
    return _targetability(evidence).to_mapping()


def _authorized_targetability_mapping(
    evidence: TargetabilityEvidence,
    decision: FeatureDecision,
    entity_path: str,
) -> dict[str, bool]:
    authorized = decision.authorized_actions
    if authorized is None:
        return _targetability_mapping(evidence)
    unknown = sorted(set(authorized) - set(_ACTION_FIELDS))
    if unknown:
        raise CaptureDecisionError(
            [f"{entity_path} contains unsupported actions: {', '.join(unknown)}"]
        )
    unsupported = sorted(
        action for action in authorized if not bool(getattr(evidence, action))
    )
    if unsupported:
        raise CaptureDecisionError(
            [
                (
                    f"{entity_path} authorizes actions the native evidence does "
                    f"not support: {', '.join(unsupported)}"
                )
            ]
        )
    return Targetability(
        suppress="suppress" in authorized,
        unsuppress="unsuppress" in authorized,
        hide="hide" in authorized,
        unhide="unhide" in authorized,
        delete="delete" in authorized,
    ).to_mapping()


def _component_identities(
    components_by_ref: Mapping[str, ComponentCandidate],
    decisions: Mapping[str, ComponentDecision],
    root_ref: str,
) -> tuple[dict[str, str], dict[str, str]]:
    ids: dict[str, str] = {}
    for ref in sorted(decisions):
        decision = decisions[ref]
        ids[ref] = decision.id or generate_component_id(
            decision.name, entity_path=f"components[{ref}].name"
        )

    identity_paths: dict[str, str] = {}

    def path_for(ref: str, active: tuple[str, ...] = ()) -> str:
        existing = identity_paths.get(ref)
        if existing is not None:
            return existing
        if ref in active:
            raise CaptureDecisionError(
                [f'component "{ref}" has a cyclic native parent chain']
            )
        if ref == root_ref:
            identity_paths[ref] = ids[ref]
            return identity_paths[ref]
        parent = components_by_ref[ref].parent_native_ref
        assert parent is not None
        value = f"{path_for(parent, active + (ref,))}/{ref}"
        identity_paths[ref] = value
        return value

    for ref in sorted(decisions):
        path_for(ref)
    return ids, identity_paths


def _parameter_ids(
    parameters_by_path: Mapping[str, ParameterCandidate],
    decisions: Mapping[str, ParameterDecision],
    component_ids: Mapping[str, str],
    feature_ids: Mapping[str, str],
    group_ids: Mapping[str, str],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for path_key in sorted(decisions):
        decision = decisions[path_key]
        candidate = parameters_by_path[path_key]
        if decision.id:
            result[path_key] = decision.id
            continue
        if candidate.owner_kind == "group":
            result[path_key] = generate_group_owned_parameter_id(
                component_ids[candidate.component_native_ref],
                group_ids[candidate.owner_native_ref],
                decision.name,
                entity_path=f"parameters[{path_key}].name",
            )
        else:
            owner_id = _owner_id(candidate, component_ids, feature_ids, group_ids)
            result[path_key] = generate_parameter_id(
                owner_id,
                decision.name,
                entity_path=f"parameters[{path_key}].name",
            )
    return result


def _metadata_ids(
    metadata_by_path: Mapping[str, MetadataCandidate],
    decisions: Mapping[str, MetadataDecision],
    component_ids: Mapping[str, str],
    feature_ids: Mapping[str, str],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for path_key in sorted(decisions):
        decision = decisions[path_key]
        if decision.id:
            result[path_key] = decision.id
            continue
        candidate = metadata_by_path[path_key]
        if candidate.owner_kind == "component":
            owner_id = component_ids[candidate.owner_native_ref]
        elif candidate.owner_kind == "feature":
            owner_id = feature_ids[candidate.owner_native_ref]
        else:
            raise CaptureDecisionError(
                [
                    (
                        f'metadata "{path_key}" has unsupported owner kind '
                        f'"{candidate.owner_kind}"'
                    )
                ]
            )
        result[path_key] = generate_metadata_id(
            owner_id,
            candidate.property.native_key,
            entity_path=f"metadata[{path_key}].key",
        )
    return result


def _build_drawings(
    decisions: tuple[DrawingDecision, ...],
    pages_by_ref: Mapping[str, DrawingPageCandidate],
    features_by_ref: Mapping[str, FeatureCandidate],
    component_decisions: Mapping[str, ComponentDecision],
    component_ids: Mapping[str, str],
    problems: list[str],
) -> list[dict[str, Any]]:
    if not decisions:
        return []

    entries: list[dict[str, Any]] = []
    selected_pages: dict[str, int] = {}
    for drawing_index, decision in enumerate(decisions):
        location = f"drawings[{drawing_index}]"
        if not decision.sheets:
            problems.append(f"{location} must select at least one drawing sheet")
            continue

        drawing_id = decision.id or generate_drawing_id(
            decision.name,
            entity_path=f"{location}.name",
        )
        drawing_components: set[str] = set()
        sheets: list[dict[str, Any]] = []
        seen_orders: dict[int, int] = {}

        for sheet_index, sheet in enumerate(decision.sheets):
            sheet_location = f"{location}.sheets[{sheet_index}]"
            page = pages_by_ref.get(sheet.native_ref)
            if page is None:
                problems.append(
                    f"{sheet_location} selects unknown technical drawing page "
                    f'"{sheet.native_ref}"'
                )
                continue
            previous = selected_pages.get(page.native_ref)
            if previous is not None:
                problems.append(
                    f'technical drawing page "{page.native_ref}" is selected by '
                    f"more than one drawing ({previous} and {drawing_index})"
                )
                continue
            selected_pages[page.native_ref] = drawing_index

            if page.resource.topology != "embedded":
                problems.append(
                    f'{sheet_location} page "{page.native_ref}" has unsupported '
                    f'drawing resource topology "{page.resource.topology}"'
                )
                continue

            if sheet.order < 1:
                problems.append(f"{sheet_location}.order must be a positive integer")
            elif sheet.order in seen_orders:
                problems.append(
                    f"{sheet_location}.order duplicates order already declared "
                    f"at {location}.sheets[{seen_orders[sheet.order]}].order"
                )
            else:
                seen_orders[sheet.order] = sheet_index

            for target in page.targets:
                if target.kind == "component":
                    if target.native_ref not in component_decisions:
                        problems.append(
                            f"{sheet_location} target component "
                            f'"{target.native_ref}" must be selected for capture'
                        )
                    else:
                        drawing_components.add(component_ids[target.native_ref])
                    continue
                if target.kind == "feature":
                    feature = features_by_ref.get(target.native_ref)
                    if feature is None:
                        problems.append(
                            f"{sheet_location} target feature "
                            f'"{target.native_ref}" is not a discovered feature'
                        )
                        continue
                    owner = feature.component_native_ref
                    if owner not in component_decisions:
                        problems.append(
                            f"{sheet_location} target feature "
                            f'"{target.native_ref}" requires component "{owner}" '
                            "to be selected for capture"
                        )
                    else:
                        drawing_components.add(component_ids[owner])
                    continue
                problems.append(
                    f'{sheet_location} target "{target.native_ref}" has '
                    f'unsupported kind "{target.kind}"'
                )

            sheet_id = sheet.id or generate_drawing_sheet_id(
                drawing_id,
                sheet.name,
                entity_path=f"{sheet_location}.name",
            )
            display_name = (
                page.native_label if sheet.display_name is None else sheet.display_name
            )
            sheets.append(
                {
                    "id": sheet_id,
                    "name": sheet.name,
                    "displayName": display_name,
                    "order": sheet.order,
                    "cadType": page.cad_type,
                    "identitySource": {
                        "kind": "native_ref",
                        "nativeRef": page.native_ref,
                    },
                }
            )

        if not drawing_components:
            problems.append(
                f'{location} "{decision.name}" must reference at least one '
                "captured component"
            )

        entries.append(
            {
                "id": drawing_id,
                "name": decision.name,
                "displayName": (
                    decision.name
                    if decision.display_name is None
                    else decision.display_name
                ),
                "componentIds": sorted(drawing_components),
                "resource": {"topology": "embedded"},
                "sheets": sorted(
                    sheets,
                    key=lambda item: (item["order"], item["id"]),
                ),
            }
        )

    return sorted(entries, key=lambda item: item["id"])


def _owner_id(
    candidate: ParameterCandidate | MetadataCandidate,
    component_ids: Mapping[str, str],
    feature_ids: Mapping[str, str],
    group_ids: Mapping[str, str],
) -> str:
    if candidate.owner_kind == "component":
        return component_ids[candidate.owner_native_ref]
    if candidate.owner_kind == "feature":
        return feature_ids[candidate.owner_native_ref]
    if candidate.owner_kind == "group":
        return group_ids[candidate.owner_native_ref]
    raise CaptureDecisionError(
        [
            (
                f'native candidate "{candidate.native_path}" has unsupported '
                f'owner kind "{candidate.owner_kind}"'
            )
        ]
    )


def _structure(
    components_by_ref: Mapping[str, ComponentCandidate],
    component_ids: Mapping[str, str],
    root_ref: str,
) -> dict[str, Any]:
    children: dict[str, list[str]] = {ref: [] for ref in component_ids}
    for ref in component_ids:
        candidate = components_by_ref[ref]
        if ref == root_ref:
            continue
        parent = candidate.parent_native_ref
        if parent is not None and parent in component_ids:
            children[parent].append(ref)

    nodes: list[dict[str, Any]] = []
    for ref in sorted(component_ids, key=lambda value: component_ids[value]):
        candidate = components_by_ref[ref]
        parent_id = (
            ""
            if ref == root_ref or candidate.parent_native_ref is None
            else component_ids[candidate.parent_native_ref]
        )
        nodes.append(
            {
                "componentId": component_ids[ref],
                "parentComponentId": parent_id,
                "children": sorted(component_ids[child] for child in children[ref]),
            }
        )
    return {"rootComponentId": component_ids[root_ref], "nodes": nodes}


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


def detect_capture_drift(
    existing: Mapping[str, Any],
    proposed: Mapping[str, Any],
) -> tuple[CaptureDriftEntry, ...]:
    """Compare retained capture against a freshly built capture document.

    Drift is reported when a retained entity's native selector disappeared,
    its native type changed, its owning structural dependency changed, or its
    retained stable identifier no longer matches the freshly generated one.
    Newly added entities are not drift; they are ordinary additions.
    """

    existing_index = _entity_index(existing)
    proposed_index = _entity_index(proposed)

    entries: list[CaptureDriftEntry] = []
    for key, retained in existing_index.items():
        candidate = proposed_index.get(key)
        if candidate is None:
            entries.append(
                CaptureDriftEntry(
                    "missing_native_selector",
                    native_ref=retained.get("nativeRef"),
                    entity=retained["entity"],
                    detail=(
                        f'retained {retained["entity"]} "{retained["id"]}" no '
                        "longer resolves to current native evidence"
                    ),
                )
            )
            continue

        if retained.get("cadType") != candidate.get("cadType"):
            entries.append(
                CaptureDriftEntry(
                    "changed_native_type",
                    native_ref=retained.get("nativeRef"),
                    entity=retained["entity"],
                    detail=(
                        f'native type changed from "{retained.get("cadType")}" '
                        f'to "{candidate.get("cadType")}"'
                    ),
                )
            )

        if retained.get("dependency") != candidate.get("dependency"):
            entries.append(
                CaptureDriftEntry(
                    "dependency_change",
                    native_ref=retained.get("nativeRef"),
                    entity=retained["entity"],
                    detail=(
                        "ownership or hierarchy changed from "
                        f"{retained.get('dependency')!r} to "
                        f"{candidate.get('dependency')!r}"
                    ),
                )
            )

        if retained.get("generatedId") != candidate.get("generatedId"):
            entries.append(
                CaptureDriftEntry(
                    "semantic_identity_change",
                    native_ref=retained.get("nativeRef"),
                    entity=retained["entity"],
                    detail=(
                        "retained stable ID differs from the current semantic "
                        f"decision: retained={retained.get('generatedId')!r} "
                        f"current={candidate.get('generatedId')!r}"
                    ),
                )
            )

    return tuple(entries)


def _entity_index(mapping: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    entities = mapping.get("entities")
    if not isinstance(entities, Mapping):
        return {}
    result: dict[tuple[str, str], dict[str, Any]] = {}

    def add(
        entity: str,
        identity: Mapping[str, Any],
        item: Mapping[str, Any],
        dependency: str,
    ) -> None:
        native_ref = identity.get("nativeRef")
        if not isinstance(native_ref, str) or native_ref == "":
            return
        result[(entity, native_ref)] = {
            "entity": entity,
            "nativeRef": native_ref,
            "cadType": item.get("cadType"),
            "id": item.get("id"),
            "generatedId": item.get("id"),
            "dependency": dependency,
        }

    def _list(name: str) -> tuple[Mapping[str, Any], ...]:
        value = entities.get(name)
        if not isinstance(value, (list, tuple)):
            return ()
        return tuple(item for item in value if isinstance(item, Mapping))

    def _nested_list(
        item: Mapping[str, Any], name: str
    ) -> tuple[Mapping[str, Any], ...]:
        value = item.get(name)
        if not isinstance(value, (list, tuple)):
            return ()
        return tuple(entry for entry in value if isinstance(entry, Mapping))

    for item in _list("components"):
        identity = item.get("identitySource") or {}
        add(
            "component",
            identity,
            item,
            f"parent:{identity.get('path')}",
        )
    for item in _list("features"):
        identity = item.get("identitySource") or {}
        add("feature", identity, item, f"component:{item.get('componentId')}")
    for item in _list("parameterGroups"):
        identity = item.get("identitySource") or {}
        add(
            "parameterGroup",
            identity,
            item,
            f"component:{item.get('ownerComponentId')}",
        )
    for item in _list("parameters"):
        identity = item.get("identitySource") or {}
        add(
            "parameter",
            identity,
            item,
            f"owner:{item.get('ownerKind')}:{item.get('ownerId')}",
        )
    for item in _list("metadata"):
        identity = item.get("identitySource") or {}
        native_ref = identity.get("nativeRef")
        key = item.get("key")
        if not isinstance(native_ref, str) or native_ref == "":
            # Metadata is keyed by exact owner scope and native key.
            owner = f"{item.get('ownerKind')}:{item.get('ownerId')}"
            if isinstance(key, str):
                result[("metadata", f"{owner}:{key}")] = {
                    "entity": "metadata",
                    "nativeRef": None,
                    "cadType": item.get("cadType"),
                    "id": item.get("id"),
                    "generatedId": item.get("id"),
                    "dependency": f"owner:{owner}",
                }
            continue
        add(
            "metadata",
            identity,
            item,
            f"owner:{item.get('ownerKind')}:{item.get('ownerId')}",
        )

    for item in _list("drawings"):
        identity = item.get("identitySource") or {}
        resource = item.get("resource") or {}
        component_ids = item.get("componentIds")
        components = (
            ",".join(sorted(component_ids))
            if isinstance(component_ids, (list, tuple))
            else ""
        )
        dependency = (
            f"resource:{resource.get('topology')}:{resource.get('path') or ''}"
            f":components:{components}"
        )
        add("drawing", identity, item, dependency)
        drawing_id = item.get("id")
        for sheet in _nested_list(item, "sheets"):
            sheet_identity = sheet.get("identitySource") or {}
            add(
                "drawingSheet",
                sheet_identity,
                sheet,
                f"drawing:{drawing_id}:components:{components}",
            )
    return result


# ---------------------------------------------------------------------------
# Preview planning and atomic writing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CaptureOutputPlan:
    """Deterministic preview plan for both project-root capture outputs."""

    project_root: Path
    capture_path: Path
    semantic_path: Path
    status: str
    capture_status: str
    semantic_status: str
    capture_diff: tuple[MappingDiffEntry, ...]
    semantic_plan: SemanticMapUpdatePlan
    document: CaptureDocument
    semantic_map: Mapping[str, Any]
    requires_confirmation: bool
    drift: tuple[CaptureDriftEntry, ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "projectRoot": str(self.project_root),
            "capturePath": str(self.capture_path),
            "semanticPath": str(self.semantic_path),
            "status": self.status,
            "captureStatus": self.capture_status,
            "semanticStatus": self.semantic_status,
            "requiresConfirmation": self.requires_confirmation,
            "captureDiff": [entry.to_mapping() for entry in self.capture_diff],
            "semanticDiff": [entry.to_mapping() for entry in self.semantic_plan.diff],
            "drift": [entry.to_mapping() for entry in self.drift],
        }


@dataclass(frozen=True, slots=True)
class CaptureWriteSummary:
    """Result of one confirmed atomic write of both capture outputs."""

    capture_path: Path
    semantic_path: Path
    capture_status: str
    semantic_status: str
    wrote_capture: bool
    wrote_semantic: bool

    def to_mapping(self) -> dict[str, Any]:
        return {
            "capturePath": str(self.capture_path),
            "semanticPath": str(self.semantic_path),
            "captureStatus": self.capture_status,
            "semanticStatus": self.semantic_status,
            "wroteCapture": self.wrote_capture,
            "wroteSemantic": self.wrote_semantic,
        }


def plan_capture_outputs(
    *,
    context: CaptureProjectContext,
    model: ProjectModel,
    discovery: CaptureDiscovery,
    decisions: CaptureDecisions,
    semantic_selection: FreeCADSemanticMapSelection,
    source_fingerprint: str | None = None,
) -> CaptureOutputPlan:
    """Plan deterministic create/no-op/merge output without writing."""

    document = build_capture_document(
        context=context,
        model=model,
        discovery=discovery,
        decisions=decisions,
        fingerprint=source_fingerprint,
    )
    proposed = document.to_mapping()

    capture_path = context.root / CAPTURE_CONTRACT_FILENAME
    semantic_path = context.root / SEMANTIC_MAP_FILENAME

    existing = _load_existing_capture(capture_path)
    drift: tuple[CaptureDriftEntry, ...] = ()
    if existing is not None:
        drift = detect_capture_drift(existing, proposed)
        if drift:
            raise CaptureDriftError(drift)

    if existing is None:
        capture_status = "create"
        capture_diff = diff_mappings(None, proposed)
    else:
        existing_bytes = canonical_capture_bytes(existing)
        proposed_bytes = canonical_capture_bytes(proposed)
        if existing_bytes == proposed_bytes:
            capture_status = "unchanged"
            capture_diff = ()
        else:
            capture_status = "merge"
            capture_diff = diff_mappings(existing, proposed)

    semantic_map = build_semantic_map(semantic_selection)
    semantic_plan = plan_semantic_map_update(semantic_path, semantic_map)
    semantic_status = semantic_plan.status

    if capture_status == "unchanged" and semantic_status == "unchanged":
        status = "unchanged"
    elif capture_status == "create" and semantic_status == "create":
        status = "create"
    else:
        status = "merge"

    requires_confirmation = capture_status == "merge" or semantic_status == "merge"

    return CaptureOutputPlan(
        project_root=context.root,
        capture_path=capture_path,
        semantic_path=semantic_path,
        status=status,
        capture_status=capture_status,
        semantic_status=semantic_status,
        capture_diff=capture_diff,
        semantic_plan=semantic_plan,
        document=document,
        semantic_map=semantic_map,
        requires_confirmation=requires_confirmation,
        drift=drift,
    )


def _load_existing_capture(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise CaptureContractError([f"existing capture path is not a file: {path}"])
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise CaptureContractError(
            [f"existing capture file could not be read: {path}: {exc}"]
        ) from exc
    try:
        decoded = loads_strict_json(content)
    except StrictJsonError as exc:
        raise CaptureContractError(
            [f"existing capture JSON is invalid at {path}: {exc}"]
        ) from exc
    if not isinstance(decoded, Mapping):
        raise CaptureContractError(
            [f"existing capture at {path} must be a JSON object"]
        )
    # Validate by round-tripping through the contract model.
    CaptureDocument.from_mapping(decoded)
    return dict(decoded)


def write_capture_outputs(
    plan: CaptureOutputPlan,
    *,
    confirm_replace: bool,
    preflight: EnginePreflightRunner | None = None,
) -> CaptureWriteSummary:
    """Atomically write both outputs with one explicit confirmation decision.

    ``confirm_replace`` is required and must be an exact bool. Existing
    differing files are never replaced when it is ``False``. Each output file
    is written atomically; both are fully validated before any file is touched.

    When ``preflight`` is supplied it runs after writing and its failure is
    re-raised after the per-file atomic writes have completed.
    """

    if not isinstance(confirm_replace, bool):
        raise TypeError("confirm_replace must be an explicit bool decision")
    if not isinstance(plan, CaptureOutputPlan):
        raise TypeError("write_capture_outputs requires CaptureOutputPlan")

    if plan.status == "unchanged":
        return CaptureWriteSummary(
            capture_path=plan.capture_path,
            semantic_path=plan.semantic_path,
            capture_status=plan.capture_status,
            semantic_status=plan.semantic_status,
            wrote_capture=False,
            wrote_semantic=False,
        )

    if plan.requires_confirmation and not confirm_replace:
        paths = []
        if plan.capture_status == "merge":
            paths.append(str(plan.capture_path))
        if plan.semantic_status == "merge":
            paths.append(str(plan.semantic_path))
        raise CaptureConfirmationRequiredError(paths)

    wrote_capture = plan.capture_status != "unchanged"
    wrote_semantic = plan.semantic_status != "unchanged"

    if wrote_capture:
        write_capture_document(
            plan.capture_path,
            plan.document,
            overwrite=plan.capture_status == "merge",
        )
    if wrote_semantic:
        write_semantic_map(
            plan.semantic_path,
            plan.semantic_map,
            confirm_replace=confirm_replace,
        )

    summary = CaptureWriteSummary(
        capture_path=plan.capture_path,
        semantic_path=plan.semantic_path,
        capture_status=plan.capture_status,
        semantic_status=plan.semantic_status,
        wrote_capture=wrote_capture,
        wrote_semantic=wrote_semantic,
    )
    if preflight is not None:
        preflight.require(plan.project_root)
    return summary


__all__ = [
    "SEMANTIC_MAP_FILENAME",
    "CaptureOutputPlan",
    "CaptureWriteSummary",
    "MappingDiffEntry",
    "build_capture_document",
    "detect_capture_drift",
    "diff_mappings",
    "plan_capture_outputs",
    "write_capture_outputs",
]
