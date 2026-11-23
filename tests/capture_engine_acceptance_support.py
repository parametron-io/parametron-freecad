"""Test-only helpers for the capture-to-Engine acceptance proof.

The proof replays the committed capture decisions (semantic names, stable IDs,
authorized actions, metadata selections) against a fresh real-FreeCAD discovery
and regenerates both project-root outputs through the production orchestration
path. Replaying committed decisions keeps the committed DSL valid without any
hand-edited structural repair.

This module is FreeCAD-free and is imported by both the opt-in pytest proof and
the real-FreeCAD runner.
"""

from __future__ import annotations

from typing import Any

from parametron_freecad.capture import (
    Annotations,
    CaptureDecisions,
    CaptureDiscovery,
    ComponentDecision,
    FeatureDecision,
    FreeCADSemanticMapSelection,
    MetadataDecision,
    ParameterDecision,
    ParameterGroupDecision,
    SemanticParameterTypeSelection,
)

_ACTIONS = ("suppress", "unsuppress", "hide", "unhide", "delete")


def _native_ref(item: dict[str, Any]) -> str | None:
    identity = item.get("identitySource") or {}
    value = identity.get("nativeRef")
    return value if isinstance(value, str) and value else None


def _annotations(item: dict[str, Any]) -> Annotations:
    return Annotations.from_mapping(item["annotations"])


def replay_decisions(
    committed: dict[str, Any],
    discovery: CaptureDiscovery,
) -> CaptureDecisions:
    """Build explicit decisions that reproduce a committed capture document."""

    entities = committed["entities"]

    components_by_ref = {item.native_ref: item for item in discovery.components}
    features_by_ref = {item.native_ref: item for item in discovery.features}
    groups_by_ref = {item.native_ref: item for item in discovery.parameter_groups}
    parameters_by_path = {item.native_path: item for item in discovery.parameters}
    metadata_by_path = {item.native_path: item for item in discovery.metadata}

    component_native_by_id: dict[str, str] = {}
    feature_native_by_id: dict[str, str] = {}
    group_native_by_id: dict[str, str] = {}

    components: list[ComponentDecision] = []
    for item in entities["components"]:
        native_ref = _native_ref(item)
        if native_ref is None or native_ref not in components_by_ref:
            raise AssertionError(
                f"committed component {item['id']!r} has no current native selector"
            )
        component_native_by_id[item["id"]] = native_ref
        components.append(
            ComponentDecision(
                native_ref=native_ref,
                name=item["name"],
                id=item["id"],
                display_name=item.get("displayName", ""),
                quantity=item.get("quantity"),
                material=item.get("material"),
                stability_class=item.get("stabilityClass", ""),
                annotations=_annotations(item),
            )
        )

    features: list[FeatureDecision] = []
    for item in entities["features"]:
        native_ref = _native_ref(item)
        if native_ref is None or native_ref not in features_by_ref:
            raise AssertionError(
                f"committed feature {item['id']!r} has no current native selector"
            )
        feature_native_by_id[item["id"]] = native_ref
        authorized = frozenset(
            action for action in _ACTIONS if item["targetability"][action]
        )
        features.append(
            FeatureDecision(
                native_ref=native_ref,
                name=item["name"],
                id=item["id"],
                display_name=item.get("displayName", ""),
                stability_class=item.get("stabilityClass", ""),
                authorized_actions=authorized,
                annotations=_annotations(item),
            )
        )

    groups: list[ParameterGroupDecision] = []
    for item in entities["parameterGroups"]:
        native_ref = _native_ref(item)
        if native_ref is None or native_ref not in groups_by_ref:
            raise AssertionError(
                f"committed parameter group {item['id']!r} has no current native "
                "selector"
            )
        group_native_by_id[item["id"]] = native_ref
        groups.append(
            ParameterGroupDecision(
                native_ref=native_ref,
                name=item["name"],
                id=item["id"],
                display_name=item.get("displayName", ""),
                stability_class=item.get("stabilityClass", ""),
                annotations=_annotations(item),
            )
        )

    owner_native_by_id = {
        **component_native_by_id,
        **feature_native_by_id,
        **group_native_by_id,
    }

    parameter_lookup: dict[tuple[str, str, str], str] = {}
    for candidate in discovery.parameters:
        parameter_lookup[
            (
                candidate.owner_kind,
                candidate.owner_native_ref,
                candidate.property.native_key,
            )
        ] = candidate.native_path

    parameters: list[ParameterDecision] = []
    for item in entities["parameters"]:
        identity = item.get("identitySource") or {}
        owner_native = owner_native_by_id.get(item["ownerId"])
        key = identity.get("ownerScopedKey")
        native_path = (
            parameter_lookup.get((item["ownerKind"], owner_native, key))
            if owner_native is not None and isinstance(key, str)
            else None
        )
        if native_path is None or native_path not in parameters_by_path:
            raise AssertionError(
                f"committed parameter {item['id']!r} has no current native selector"
            )
        parameters.append(
            ParameterDecision(
                native_path=native_path,
                name=item["name"],
                id=item["id"],
                display_name=item.get("displayName", ""),
                stability_class=item.get("stabilityClass", ""),
                annotations=_annotations(item),
            )
        )

    metadata_lookup: dict[tuple[str, str, str], str] = {}
    for candidate in discovery.metadata:
        metadata_lookup[
            (
                candidate.owner_kind,
                candidate.owner_native_ref,
                candidate.property.native_key,
            )
        ] = candidate.native_path

    metadata: list[MetadataDecision] = []
    for item in entities["metadata"]:
        owner_native = owner_native_by_id.get(item["ownerId"])
        native_path = (
            metadata_lookup.get((item["ownerKind"], owner_native, item["key"]))
            if owner_native is not None
            else None
        )
        if native_path is None or native_path not in metadata_by_path:
            raise AssertionError(
                f"committed metadata {item['id']!r} has no current native selector"
            )
        metadata.append(
            MetadataDecision(
                native_path=native_path,
                id=item["id"],
                display_name=item.get("displayName", ""),
                stability_class=item.get("stabilityClass", ""),
                annotations=_annotations(item),
            )
        )

    return CaptureDecisions(
        components=tuple(components),
        features=tuple(features),
        parameter_groups=tuple(groups),
        parameters=tuple(parameters),
        metadata=tuple(metadata),
        capture_id=committed["captureId"],
        adapter_version=committed["adapter"]["version"],
        cad_system_version=committed["cadSystem"]["version"],
        annotations=Annotations.from_mapping(committed["annotations"]),
    )


def selection_from_committed_map(
    mapping: dict[str, Any],
) -> FreeCADSemanticMapSelection:
    """Extract the capture-relevant selection from a committed semantic map.

    Only the project selection fields are read. Stale projection sections in a
    committed map are intentionally ignored; the generated map is validated by
    the current contract.
    """

    parameter_types = tuple(
        SemanticParameterTypeSelection(
            name=name,
            value_kind=entry["valueKind"],
            default_unit=entry["defaultUnit"],
            coercion=entry["coercion"],
        )
        for name, entry in sorted(mapping["semanticTypes"]["parameterTypes"].items())
    )
    native_map = dict(
        mapping["captureToSemantic"]["parameters"][0]["semanticType"]["map"]
    )
    return FreeCADSemanticMapSelection(
        mapping_id=mapping["mappingId"],
        parameter_types=parameter_types,
        native_type_to_semantic_type=native_map,
        cad_system_min_version=mapping["cadSystem"]["minVersion"],
    )


__all__ = ["replay_decisions", "selection_from_committed_map"]
