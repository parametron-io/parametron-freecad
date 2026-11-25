"""Explicit user decisions that shape one capture operation.

Discovery produces native candidates without semantic names or stable IDs. A
capture operation is defined by explicit decisions that select candidates and
bind them to user-authored semantic names and stable identifiers. Nothing in
this module derives a semantic name from native data, and no decision is
inferred from a native label.

The decision records are immutable and FreeCAD-free. Structural validation
(top-down coverage, discovery matching, ID/name policy) happens in the
orchestration layer where both decisions and discovery evidence are available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from parametron_freecad.capture.model import Annotations

_CAPTURE_ID_PREFIX = "cap.freecad."
_CAPTURE_ID_SLUG = re.compile(r"[^a-z0-9]+")


def derive_capture_id(project_id: str, logical_id: str) -> str:
    """Derive a deterministic capture identifier from stable project context.

    The identifier depends only on the project and selected model logical IDs.
    It never depends on the clock, host, fingerprint, or native document name,
    so equivalent unchanged captures keep an equivalent identifier.
    """

    combined = f"{project_id} {logical_id}"
    slug = _CAPTURE_ID_SLUG.sub("-", combined.strip().lower()).strip("-")
    if slug == "":
        slug = "capture"
    return f"{_CAPTURE_ID_PREFIX}{slug}"


def _normalized_actions(
    actions: frozenset[str] | None,
) -> frozenset[str] | None:
    if actions is None:
        return None
    if not isinstance(actions, frozenset):
        raise TypeError("authorized_actions must be a frozenset or None")
    return actions


@dataclass(frozen=True, slots=True)
class ComponentDecision:
    """User decision for one captured component candidate."""

    native_ref: str
    name: str
    id: str = ""
    display_name: str | None = None
    quantity: int | None = None
    material: str | None = None
    stability_class: str = ""
    annotations: Annotations = field(default_factory=Annotations)


@dataclass(frozen=True, slots=True)
class FeatureDecision:
    """User decision for one captured feature candidate.

    ``authorized_actions`` may narrow, but never extend, the captured native
    target capability. ``None`` keeps the captured capability.
    """

    native_ref: str
    name: str
    id: str = ""
    display_name: str | None = None
    stability_class: str = ""
    authorized_actions: frozenset[str] | None = None
    annotations: Annotations = field(default_factory=Annotations)

    def __post_init__(self) -> None:
        _normalized_actions(self.authorized_actions)


@dataclass(frozen=True, slots=True)
class ParameterGroupDecision:
    """User decision for one captured parameter-group candidate."""

    native_ref: str
    name: str
    id: str = ""
    display_name: str | None = None
    stability_class: str = ""
    annotations: Annotations = field(default_factory=Annotations)


@dataclass(frozen=True, slots=True)
class ParameterDecision:
    """User decision for one captured parameter candidate (keyed by native path)."""

    native_path: str
    name: str
    id: str = ""
    display_name: str = ""
    stability_class: str = ""
    annotations: Annotations = field(default_factory=Annotations)


@dataclass(frozen=True, slots=True)
class MetadataDecision:
    """User selection and decision for one captured metadata candidate."""

    native_path: str
    id: str = ""
    display_name: str = ""
    stability_class: str = ""
    annotations: Annotations = field(default_factory=Annotations)


@dataclass(frozen=True, slots=True)
class DrawingSheetDecision:
    """User decision for one discovered technical drawing page."""

    native_ref: str
    name: str
    order: int
    id: str = ""
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class DrawingDecision:
    """User decision grouping discovered pages into one logical drawing."""

    name: str
    sheets: tuple[DrawingSheetDecision, ...]
    id: str = ""
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class CaptureDecisions:
    """Complete explicit decision set for one capture operation."""

    components: tuple[ComponentDecision, ...] = ()
    features: tuple[FeatureDecision, ...] = ()
    parameter_groups: tuple[ParameterGroupDecision, ...] = ()
    parameters: tuple[ParameterDecision, ...] = ()
    metadata: tuple[MetadataDecision, ...] = ()
    drawings: tuple[DrawingDecision, ...] = ()
    capture_id: str = ""
    adapter_version: str = ""
    cad_system_version: str = ""
    annotations: Annotations = field(default_factory=Annotations)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "captureId": self.capture_id,
            "adapterVersion": self.adapter_version,
            "cadSystemVersion": self.cad_system_version,
            "annotations": self.annotations.to_mapping(),
            "components": [
                {
                    "nativeRef": item.native_ref,
                    "name": item.name,
                    "id": item.id,
                }
                for item in self.components
            ],
            "features": [
                {
                    "nativeRef": item.native_ref,
                    "name": item.name,
                    "id": item.id,
                    "authorizedActions": (
                        None
                        if item.authorized_actions is None
                        else sorted(item.authorized_actions)
                    ),
                }
                for item in self.features
            ],
            "parameterGroups": [
                {"nativeRef": item.native_ref, "name": item.name, "id": item.id}
                for item in self.parameter_groups
            ],
            "parameters": [
                {"nativePath": item.native_path, "name": item.name, "id": item.id}
                for item in self.parameters
            ],
            "metadata": [
                {"nativePath": item.native_path, "id": item.id}
                for item in self.metadata
            ],
            "drawings": [
                {
                    "name": item.name,
                    "id": item.id,
                    "sheets": [
                        {
                            "nativeRef": sheet.native_ref,
                            "name": sheet.name,
                            "order": sheet.order,
                            "id": sheet.id,
                        }
                        for sheet in item.sheets
                    ],
                }
                for item in self.drawings
            ],
        }


__all__ = [
    "CaptureDecisions",
    "ComponentDecision",
    "DrawingDecision",
    "DrawingSheetDecision",
    "FeatureDecision",
    "MetadataDecision",
    "ParameterDecision",
    "ParameterGroupDecision",
    "derive_capture_id",
]
