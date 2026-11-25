"""Deterministic FreeCAD-native capture candidate discovery.

Discovery reads one already-open ``.FCStd`` document and returns native
candidates for the workbench. It never generates semantic names or stable IDs,
never writes native properties, never recomputes, and never saves the document.
Semantic naming, ID generation, file writing, project mapping, semantic maps,
and Engine preflight belong to the surrounding capture workflow.

The native facts captured here are:

* exact native object ``Name`` selectors and ``TypeId`` values;
* component/feature hierarchy from native ``Group`` membership;
* ``App::VarSet`` parameter groups and their scalar native properties;
* properties in the native ``Metadata`` property group;
* observable/writable capability evidence;
* ``App::PropertyBool`` Suppressed and Visibility target capability;
* conservative deletion evidence from native ``InList``/``OutList``;
* supported ``TechDraw::DrawPage`` sheets with deterministic page order,
  embedded/separate drawing-resource facts, page display labels, and captured
  component/feature targets resolved through native view ``Source``/``XSource``
  evidence.

Only ``TechDraw::DrawPage`` objects owned by the active document are emitted as
drawing candidates. Pages that are linked from a separate ``.FCStd`` resource
are diagnosed conservatively instead of being converted into candidates,
because active-document capture cannot prove their contents.

A single-part document, or a document without one unambiguous assembly
container, gets a synthetic document-level root assembly candidate. The
synthetic root uses ``App::Document`` as its native type and the document Name as
its native reference. If a natural ``App::Part`` or
``Assembly::AssemblyObject`` is the only top-level component, it is used as the
root instead.

Candidate order is deterministic: components/features/parameter groups by native
path, parameters/metadata by owner path then exact native key, drawing pages by
native page selector with a one-based ``pageOrder`` signal, drawing targets by
native reference, and diagnostics by code and native reference. Native
``InList``/``OutList`` names are sorted and deduplicated. Child lists are sorted
by native Name.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from parametron_freecad.capture.discovery_errors import (
    CaptureDiscoveryDocumentError,
    CaptureDiscoveryInspectionError,
)
from parametron_freecad.capture.native_probe import (
    bool_property_writable,
    document_label,
    group_members,
    is_derived_from,
    is_read_only_status,
    linked_objects,
    native_document_label,
    native_document_name,
    native_label,
    native_name_or_none,
    native_type_id,
    properties_list,
    property_group,
    property_status,
    property_type_id,
    read_native_value,
    relationship_names,
    require_document_name,
    require_native_objects,
)
from parametron_freecad.capture.native_types import (
    METADATA_NATIVE_TYPES,
    NATIVE_VALUE_KIND_BY_TYPE,
    PARAMETER_NATIVE_TYPES,
    QUANTITY_NATIVE_KINDS,
)

# ---------------------------------------------------------------------------
# Native type and property capability tables
# ---------------------------------------------------------------------------

_INTERNAL_VARSET_PROPERTIES = frozenset(
    {"ExpressionEngine", "Label", "Label2", "Visibility"}
)

_PARTDESIGN_DATUM_TYPES = frozenset(
    {
        "PartDesign::Plane",
        "PartDesign::Line",
        "PartDesign::Point",
        "PartDesign::CoordinateSystem",
    }
)
_APP_DATUM_TYPES = frozenset({"App::Origin", "App::Line", "App::Plane", "App::Point"})

_VALUE_TYPE_BY_NATIVE_KIND = {
    "string": "string",
    "boolean": "boolean",
    "float": "number",
    "integer": "number",
    "length": "number",
    "distance": "number",
    "angle": "number",
    "quantity": "number",
}

_EXCLUDED_DIAGNOSTIC_DETAILS = {
    "unsupported_link": "linked objects are outside active-document capture scope",
    "unsupported_assembly_member": (
        "assembly joints and joint groups are outside capture scope"
    ),
    "unsupported_object_group": (
        "plain document object groups are not components or features"
    ),
    "unsupported_parameter_group_type": (
        "only App::VarSet parameter groups are captured in v0"
    ),
    "unsupported_object_type": (
        "object type is outside supported component/feature capture"
    ),
    "unsupported_technical_drawing": (
        "technical drawing object is outside supported page discovery"
    ),
}

_TECHDRAW_PAGE_TYPE = "TechDraw::DrawPage"
_TECHDRAW_PROJECTION_GROUP_TYPE = "TechDraw::DrawProjGroup"
_TECHDRAW_VIEW_PART_TYPE = "TechDraw::DrawViewPart"
_TECHDRAW_VIEW_CONTAINER_TYPES = frozenset({"TechDraw::DrawViewClip"})

# ---------------------------------------------------------------------------
# Candidate records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DocumentEvidence:
    """Native active-document evidence."""

    name: str
    label: str
    object_count: int

    def to_mapping(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "objectCount": self.object_count,
        }


@dataclass(frozen=True, slots=True)
class TargetabilityEvidence:
    """Captured target capability and conservative deletion evidence."""

    suppress: bool
    unsuppress: bool
    hide: bool
    unhide: bool
    delete: bool
    delete_dependents: tuple[str, ...] = ()
    delete_dependencies: tuple[str, ...] = ()
    dependency_evidence_available: bool = False

    def to_mapping(self) -> dict[str, Any]:
        return {
            "suppress": self.suppress,
            "unsuppress": self.unsuppress,
            "hide": self.hide,
            "unhide": self.unhide,
            "delete": self.delete,
            "deleteDependents": list(self.delete_dependents),
            "deleteDependencies": list(self.delete_dependencies),
            "dependencyEvidenceAvailable": self.dependency_evidence_available,
        }


@dataclass(frozen=True, slots=True)
class ComponentCandidate:
    """Native component candidate without a semantic name or stable ID."""

    native_ref: str
    native_label: str
    cad_type: str
    kind: str
    synthetic: bool
    parent_native_ref: str | None
    native_path: str
    quantity: int
    material: str
    targetability: TargetabilityEvidence

    def to_mapping(self) -> dict[str, Any]:
        return {
            "nativeRef": self.native_ref,
            "nativeLabel": self.native_label,
            "cadType": self.cad_type,
            "kind": self.kind,
            "synthetic": self.synthetic,
            "parentNativeRef": self.parent_native_ref,
            "nativePath": self.native_path,
            "quantity": self.quantity,
            "material": self.material,
            "targetability": self.targetability.to_mapping(),
        }


@dataclass(frozen=True, slots=True)
class FeatureCandidate:
    """Native feature candidate without a semantic name or stable ID."""

    native_ref: str
    native_label: str
    cad_type: str
    component_native_ref: str
    native_path: str
    owner_scoped_key: str
    targetability: TargetabilityEvidence

    def to_mapping(self) -> dict[str, Any]:
        return {
            "nativeRef": self.native_ref,
            "nativeLabel": self.native_label,
            "cadType": self.cad_type,
            "componentNativeRef": self.component_native_ref,
            "nativePath": self.native_path,
            "ownerScopedKey": self.owner_scoped_key,
            "targetability": self.targetability.to_mapping(),
        }


@dataclass(frozen=True, slots=True)
class ParameterGroupCandidate:
    """Native App::VarSet parameter-group candidate."""

    native_ref: str
    native_label: str
    cad_type: str
    owner_component_native_ref: str
    native_path: str
    group_kind: str
    observable: bool
    writable: bool
    owner_scoped_key: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "nativeRef": self.native_ref,
            "nativeLabel": self.native_label,
            "cadType": self.cad_type,
            "ownerComponentNativeRef": self.owner_component_native_ref,
            "nativePath": self.native_path,
            "groupKind": self.group_kind,
            "observable": self.observable,
            "writable": self.writable,
            "ownerScopedKey": self.owner_scoped_key,
        }


@dataclass(frozen=True, slots=True)
class PropertyEvidence:
    """Read-only native scalar property evidence for parameters or metadata."""

    native_key: str
    native_type_id: str | None
    native_value_kind: str | None
    value_type: str | None
    current_value: Any
    unit: str | None
    observable: bool
    writable: bool
    supported: bool
    native_readable: bool
    property_status: tuple[str | int, ...]
    property_status_available: bool
    unsupported_reason: str | None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "nativeKey": self.native_key,
            "nativeTypeId": self.native_type_id,
            "nativeValueKind": self.native_value_kind,
            "valueType": self.value_type,
            "currentValue": self.current_value,
            "unit": self.unit,
            "observable": self.observable,
            "writable": self.writable,
            "supported": self.supported,
            "nativeReadable": self.native_readable,
            "propertyStatus": list(self.property_status),
            "propertyStatusAvailable": self.property_status_available,
            "unsupportedReason": self.unsupported_reason,
        }


@dataclass(frozen=True, slots=True)
class ParameterCandidate:
    """Group-owned native parameter candidate."""

    owner_kind: str
    owner_native_ref: str
    component_native_ref: str
    native_path: str
    owner_scoped_key: str
    group_scoped_key: str
    property: PropertyEvidence

    def to_mapping(self) -> dict[str, Any]:
        result = {
            "ownerKind": self.owner_kind,
            "ownerNativeRef": self.owner_native_ref,
            "componentNativeRef": self.component_native_ref,
            "nativePath": self.native_path,
            "ownerScopedKey": self.owner_scoped_key,
            "groupScopedKey": self.group_scoped_key,
        }
        result.update(self.property.to_mapping())
        return result


@dataclass(frozen=True, slots=True)
class MetadataCandidate:
    """Component- or feature-owned native metadata candidate."""

    owner_kind: str
    owner_native_ref: str
    component_native_ref: str
    native_path: str
    owner_scoped_key: str
    property: PropertyEvidence

    def to_mapping(self) -> dict[str, Any]:
        result = {
            "ownerKind": self.owner_kind,
            "ownerNativeRef": self.owner_native_ref,
            "componentNativeRef": self.component_native_ref,
            "nativePath": self.native_path,
            "ownerScopedKey": self.owner_scoped_key,
        }
        result.update(self.property.to_mapping())
        return result


@dataclass(frozen=True, slots=True)
class DrawingResourceEvidence:
    """Native storage facts for one technical drawing page resource."""

    topology: str
    document_name: str
    document_label: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "topology": self.topology,
            "documentName": self.document_name,
            "documentLabel": self.document_label,
        }


@dataclass(frozen=True, slots=True)
class DrawingTargetCandidate:
    """Captured component or feature referenced by a technical drawing view."""

    native_ref: str
    cad_type: str
    kind: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "nativeRef": self.native_ref,
            "cadType": self.cad_type,
            "kind": self.kind,
        }


@dataclass(frozen=True, slots=True)
class DrawingPageCandidate:
    """One native ``TechDraw::DrawPage`` sheet candidate without a semantic ID."""

    native_ref: str
    native_label: str
    cad_type: str
    page_order: int
    resource: DrawingResourceEvidence
    targets: tuple[DrawingTargetCandidate, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "nativeRef": self.native_ref,
            "nativeLabel": self.native_label,
            "cadType": self.cad_type,
            "pageOrder": self.page_order,
            "resource": self.resource.to_mapping(),
            "targets": [item.to_mapping() for item in self.targets],
        }


@dataclass(frozen=True, slots=True)
class DiscoveryDiagnostic:
    """Deterministic unsupported or ambiguous native discovery evidence."""

    code: str
    native_ref: str | None
    detail: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "nativeRef": self.native_ref,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class CaptureDiscovery:
    """Complete deterministic native discovery result for one active document."""

    document: DocumentEvidence
    root_component_native_ref: str
    components: tuple[ComponentCandidate, ...]
    features: tuple[FeatureCandidate, ...]
    parameter_groups: tuple[ParameterGroupCandidate, ...]
    parameters: tuple[ParameterCandidate, ...]
    metadata: tuple[MetadataCandidate, ...]
    drawings: tuple[DrawingPageCandidate, ...]
    diagnostics: tuple[DiscoveryDiagnostic, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "document": self.document.to_mapping(),
            "rootComponentNativeRef": self.root_component_native_ref,
            "components": [item.to_mapping() for item in self.components],
            "features": [item.to_mapping() for item in self.features],
            "parameterGroups": [item.to_mapping() for item in self.parameter_groups],
            "parameters": [item.to_mapping() for item in self.parameters],
            "metadata": [item.to_mapping() for item in self.metadata],
            "drawings": [item.to_mapping() for item in self.drawings],
            "diagnostics": [item.to_mapping() for item in self.diagnostics],
        }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def discover_capture_candidates(document: Any) -> CaptureDiscovery:
    """Discover deterministic native capture candidates for an open document.

    The caller owns document opening, working-copy preparation, and closing.
    This function only reads native state. It raises
    :class:`CaptureDiscoveryDocumentError` for an unusable document boundary and
    :class:`CaptureDiscoveryInspectionError` when required native evidence is
    unavailable.
    """

    document_name = require_document_name(document)
    objects = require_native_objects(document)
    object_by_name = {native_name_or_none(item): item for item in objects}

    diagnostics: set[DiscoveryDiagnostic] = set()
    component_parents: dict[str, str] = {}
    feature_parents: dict[str, str] = {}
    group_parents: dict[str, str] = {}

    containers = [
        item for item in objects if _is_component_container(item) or _is_body(item)
    ]
    for container in sorted(
        containers, key=lambda item: native_name_or_none(item) or ""
    ):
        container_name = native_name_or_none(container)
        if container_name is None:
            continue
        context = "body" if _is_body(container) else "container"
        members, available = group_members(container)
        if not available:
            diagnostics.add(
                DiscoveryDiagnostic(
                    code="invalid_native_group_member",
                    native_ref=container_name,
                    detail=(
                        "native Group contains a member without a nonblank string Name"
                    ),
                )
            )
        for member in members:
            member_name = native_name_or_none(member)
            if member_name is None or member_name == container_name:
                continue
            classification, diagnostic_code = _classify_object(member, context)
            if classification is None:
                _add_classification_diagnostic(
                    diagnostics,
                    diagnostic_code,
                    member_name,
                )
            elif classification == "component":
                _assign_parent(
                    component_parents,
                    member_name,
                    container_name,
                    "component",
                    diagnostics,
                )
            elif classification == "feature":
                _assign_parent(
                    feature_parents,
                    member_name,
                    container_name,
                    "feature",
                    diagnostics,
                )
            elif classification == "parameter_group":
                _assign_parent(
                    group_parents,
                    member_name,
                    container_name,
                    "parameter_group",
                    diagnostics,
                )

    top_components: list[str] = []
    top_features: list[str] = []
    for item in objects:
        name = native_name_or_none(item)
        if name is None:
            continue
        if (
            name in component_parents
            or name in feature_parents
            or name in group_parents
        ):
            continue
        classification, diagnostic_code = _classify_object(item, "root")
        if classification is None:
            _add_classification_diagnostic(diagnostics, diagnostic_code, name)
        elif classification == "component":
            top_components.append(name)
        elif classification == "feature":
            top_features.append(name)
        # Top-level parameter groups are discovered from all VarSet objects below.

    top_components.sort()
    top_features.sort()

    root_native_ref, root_is_synthetic = _select_root(
        document_name,
        object_by_name,
        top_components,
    )
    if root_is_synthetic and document_name in object_by_name:
        raise CaptureDiscoveryDocumentError(
            f'document Name "{document_name}" collides with a native object '
            "Name; synthetic document root cannot be represented unambiguously"
        )

    if root_is_synthetic:
        for name in top_components:
            _assign_parent(
                component_parents,
                name,
                root_native_ref,
                "component",
                diagnostics,
            )

    component_names = set(component_parents)
    component_names.add(root_native_ref)
    _normalize_component_parents(
        component_parents,
        component_names,
        root_native_ref,
        diagnostics,
    )
    component_paths = _component_paths(
        component_parents,
        component_names,
        root_native_ref,
        diagnostics,
    )

    components = _build_components(
        document,
        object_by_name,
        component_parents,
        component_paths,
        root_native_ref,
        root_is_synthetic,
    )

    feature_names = set(feature_parents)
    feature_names.update(top_features)
    features = _build_features(
        object_by_name,
        feature_parents,
        feature_names,
        component_paths,
        root_native_ref,
        diagnostics,
    )

    parameter_groups = _build_parameter_groups(
        objects,
        object_by_name,
        group_parents,
        component_paths,
        root_native_ref,
        diagnostics,
    )

    parameters = _build_parameters(
        object_by_name,
        parameter_groups,
        diagnostics,
    )

    metadata = _build_metadata(
        document,
        object_by_name,
        components,
        features,
        diagnostics,
    )

    drawings = _build_drawing_pages(
        document_name,
        document,
        object_by_name,
        component_names,
        feature_names,
        diagnostics,
    )
    _diagnose_technical_drawing_links(
        object_by_name,
        document_name,
        diagnostics,
    )

    return CaptureDiscovery(
        document=DocumentEvidence(
            name=document_name,
            label=document_label(document),
            object_count=len(objects),
        ),
        root_component_native_ref=root_native_ref,
        components=tuple(
            sorted(
                components,
                key=lambda item: (item.native_path, item.native_ref),
            )
        ),
        features=tuple(
            sorted(
                features,
                key=lambda item: (item.native_path, item.native_ref),
            )
        ),
        parameter_groups=tuple(
            sorted(
                parameter_groups,
                key=lambda item: (item.native_path, item.native_ref),
            )
        ),
        parameters=tuple(
            sorted(
                parameters,
                key=lambda item: (item.native_path, item.property.native_key),
            )
        ),
        metadata=tuple(
            sorted(
                metadata,
                key=lambda item: (item.native_path, item.property.native_key),
            )
        ),
        drawings=tuple(
            sorted(
                drawings,
                key=lambda item: item.native_ref,
            )
        ),
        diagnostics=tuple(
            sorted(
                diagnostics,
                key=lambda item: (
                    item.code,
                    item.native_ref or "",
                    item.detail,
                ),
            )
        ),
    )


# ---------------------------------------------------------------------------
# Classification and hierarchy
# ---------------------------------------------------------------------------


def _is_component_container(value: Any) -> bool:
    return is_derived_from(value, "App::Part") or is_derived_from(
        value,
        "Assembly::AssemblyObject",
    )


def _is_body(value: Any) -> bool:
    return is_derived_from(value, "PartDesign::Body")


def _is_varset(value: Any) -> bool:
    return is_derived_from(value, "App::VarSet")


def _is_sketch(value: Any) -> bool:
    return is_derived_from(value, "Sketcher::SketchObject")


def _is_datum(value: Any) -> bool:
    type_id = getattr(value, "TypeId", None)
    if isinstance(type_id, str) and (
        type_id in _APP_DATUM_TYPES or type_id in _PARTDESIGN_DATUM_TYPES
    ):
        return True
    return is_derived_from(value, "App::Origin") or is_derived_from(
        value,
        "App::DatumFeature",
    )


def _is_link(value: Any) -> bool:
    type_id = getattr(value, "TypeId", None)
    if isinstance(type_id, str) and (
        type_id.startswith("App::Link") or type_id == "Assembly::AssemblyLink"
    ):
        return True
    return is_derived_from(value, "App::Link") or is_derived_from(
        value,
        "Assembly::AssemblyLink",
    )


def _is_assembly_member(value: Any) -> bool:
    type_id = getattr(value, "TypeId", None)
    if isinstance(type_id, str):
        if type_id == "Assembly::AssemblyObject":
            return False
        if type_id.startswith("Assembly::"):
            return True
    return is_derived_from(value, "Assembly::Joint") or is_derived_from(
        value,
        "Assembly::JointGroup",
    )


def _is_object_group(value: Any) -> bool:
    type_id = getattr(value, "TypeId", None)
    if type_id == "App::DocumentObjectGroup":
        return True
    return is_derived_from(value, "App::DocumentObjectGroup")


def _is_spreadsheet(value: Any) -> bool:
    type_id = getattr(value, "TypeId", None)
    if type_id == "Spreadsheet::Sheet":
        return True
    return is_derived_from(value, "Spreadsheet::Sheet")


def _is_technical_drawing(value: Any) -> bool:
    type_id = getattr(value, "TypeId", None)
    return isinstance(type_id, str) and type_id.startswith("TechDraw::")


def _is_technical_drawing_page(value: Any) -> bool:
    type_id = getattr(value, "TypeId", None)
    return type_id == _TECHDRAW_PAGE_TYPE


def _is_technical_drawing_projection_group(value: Any) -> bool:
    type_id = getattr(value, "TypeId", None)
    return type_id == _TECHDRAW_PROJECTION_GROUP_TYPE


def _is_technical_drawing_view_part(value: Any) -> bool:
    return is_derived_from(value, _TECHDRAW_VIEW_PART_TYPE)


def _is_supported_technical_drawing_view(value: Any) -> bool:
    return _is_technical_drawing_view_part(value) or (
        _is_technical_drawing_projection_group(value)
    )


def _is_technical_drawing_view_container(value: Any) -> bool:
    type_id = getattr(value, "TypeId", None)
    return isinstance(type_id, str) and type_id in _TECHDRAW_VIEW_CONTAINER_TYPES


def _linked_object(value: Any) -> Any | None:
    try:
        return getattr(value, "LinkedObject", None)
    except Exception:
        return None


def _is_technical_drawing_link(value: Any) -> bool:
    if not _is_link(value):
        return False
    target = _linked_object(value)
    return target is not None and _is_technical_drawing(target)


def _is_partdesign_feature(value: Any) -> bool:
    if _is_body(value) or _is_datum(value):
        return False
    if is_derived_from(value, "PartDesign::Feature"):
        return True
    type_id = getattr(value, "TypeId", None)
    return isinstance(type_id, str) and type_id.startswith("PartDesign::")


def _is_generic_part_feature(value: Any) -> bool:
    if (
        _is_body(value)
        or _is_partdesign_feature(value)
        or _is_sketch(value)
        or _is_datum(value)
    ):
        return False
    return is_derived_from(value, "Part::Feature")


def _classify_object(
    value: Any,
    context: str,
) -> tuple[str | None, str | None]:
    if _is_datum(value):
        return None, None
    if _is_link(value):
        if _is_technical_drawing_link(value):
            return None, None
        return None, "unsupported_link"
    if _is_assembly_member(value):
        return None, "unsupported_assembly_member"
    if _is_object_group(value):
        return None, "unsupported_object_group"
    if _is_spreadsheet(value):
        return None, "unsupported_parameter_group_type"
    if _is_technical_drawing(value):
        return None, None
    if _is_varset(value):
        return "parameter_group", None

    if _is_component_container(value) or _is_body(value):
        return "component", None

    if context == "body":
        if _is_partdesign_feature(value) or _is_sketch(value):
            return "feature", None
        if _is_generic_part_feature(value):
            return "feature", None
        return None, "unsupported_object_type"

    if _is_partdesign_feature(value) or _is_sketch(value):
        return "feature", None
    if _is_generic_part_feature(value):
        return "component", None
    return None, "unsupported_object_type"


def _add_classification_diagnostic(
    diagnostics: set[DiscoveryDiagnostic],
    code: str | None,
    native_ref: str,
) -> None:
    if code is None:
        return
    detail = _EXCLUDED_DIAGNOSTIC_DETAILS.get(code, "unsupported native object")
    diagnostics.add(
        DiscoveryDiagnostic(
            code=code,
            native_ref=native_ref,
            detail=detail,
        )
    )


def _assign_parent(
    parents: dict[str, str],
    child: str,
    parent: str,
    kind: str,
    diagnostics: set[DiscoveryDiagnostic],
) -> None:
    existing = parents.get(child)
    if existing is None:
        parents[child] = parent
        return
    if existing == parent:
        return
    diagnostics.add(
        DiscoveryDiagnostic(
            code=f"conflicting_{kind}_parent",
            native_ref=child,
            detail=(
                f'first native parent "{existing}"; additional native parent "{parent}"'
            ),
        )
    )


def _select_root(
    document_name: str,
    object_by_name: dict[str, Any],
    top_components: list[str],
) -> tuple[str, bool]:
    if len(top_components) == 1:
        candidate_name = top_components[0]
        candidate = object_by_name.get(candidate_name)
        if candidate is not None and _is_component_container(candidate):
            return candidate_name, False
    return document_name, True


def _normalize_component_parents(
    component_parents: dict[str, str],
    component_names: set[str],
    root_native_ref: str,
    diagnostics: set[DiscoveryDiagnostic],
) -> None:
    for child, parent in tuple(component_parents.items()):
        if parent in component_names and child in component_names:
            continue
        diagnostics.add(
            DiscoveryDiagnostic(
                code="unknown_component_parent",
                native_ref=child,
                detail=(
                    f'component parent "{parent}" is not a captured component; '
                    f'using root "{root_native_ref}"'
                ),
            )
        )
        component_parents[child] = root_native_ref


def _component_paths(
    component_parents: dict[str, str],
    component_names: set[str],
    root_native_ref: str,
    diagnostics: set[DiscoveryDiagnostic],
) -> dict[str, str]:
    children: dict[str, list[str]] = {name: [] for name in component_names}
    for child, parent in component_parents.items():
        children.setdefault(parent, []).append(child)
    for values in children.values():
        values.sort()

    paths = {root_native_ref: root_native_ref}
    queue: deque[str] = deque([root_native_ref])
    visited = {root_native_ref}
    while queue:
        parent = queue.popleft()
        for child in children.get(parent, ()):
            if child in visited:
                diagnostics.add(
                    DiscoveryDiagnostic(
                        code="component_hierarchy_cycle",
                        native_ref=child,
                        detail=(
                            f'component "{child}" is referenced more than once '
                            f'from native parent "{parent}"'
                        ),
                    )
                )
                continue
            visited.add(child)
            paths[child] = f"{paths[parent]}/{child}"
            queue.append(child)

    for name in sorted(component_names):
        if name in paths:
            continue
        diagnostics.add(
            DiscoveryDiagnostic(
                code="unreachable_component",
                native_ref=name,
                detail=(
                    f'component "{name}" is not reachable from root "{root_native_ref}"'
                ),
            )
        )
        paths[name] = f"{root_native_ref}/{name}"
    return paths


# ---------------------------------------------------------------------------
# Candidate construction
# ---------------------------------------------------------------------------


def _build_components(
    document: Any,
    object_by_name: dict[str, Any],
    component_parents: dict[str, str],
    component_paths: dict[str, str],
    root_native_ref: str,
    root_is_synthetic: bool,
) -> list[ComponentCandidate]:
    components: list[ComponentCandidate] = []
    for name in sorted(component_paths):
        if name == root_native_ref and root_is_synthetic:
            components.append(
                ComponentCandidate(
                    native_ref=root_native_ref,
                    native_label=document_label(document),
                    cad_type=native_type_id(document, native_ref=root_native_ref),
                    kind="assembly",
                    synthetic=True,
                    parent_native_ref=None,
                    native_path=component_paths[name],
                    quantity=1,
                    material="",
                    targetability=_empty_targetability(),
                )
            )
            continue

        value = object_by_name.get(name)
        if value is None:
            raise CaptureDiscoveryInspectionError(
                f'component "{name}" is missing from native document Objects'
            )
        is_root = name == root_native_ref
        components.append(
            ComponentCandidate(
                native_ref=name,
                native_label=native_label(value),
                cad_type=native_type_id(value, native_ref=name),
                kind=(
                    "assembly" if is_root or _is_component_container(value) else "part"
                ),
                synthetic=False,
                parent_native_ref=component_parents.get(name),
                native_path=component_paths[name],
                quantity=1,
                material="",
                targetability=_targetability(value, is_root=is_root),
            )
        )
    return components


def _build_features(
    object_by_name: dict[str, Any],
    feature_parents: dict[str, str],
    feature_names: set[str],
    component_paths: dict[str, str],
    root_native_ref: str,
    diagnostics: set[DiscoveryDiagnostic],
) -> list[FeatureCandidate]:
    features: list[FeatureCandidate] = []
    for name in sorted(feature_names):
        value = object_by_name.get(name)
        if value is None:
            raise CaptureDiscoveryInspectionError(
                f'feature "{name}" is missing from native document Objects'
            )
        owner = feature_parents.get(name, root_native_ref)
        if owner not in component_paths:
            diagnostics.add(
                DiscoveryDiagnostic(
                    code="unknown_feature_component",
                    native_ref=name,
                    detail=(
                        f'feature component "{owner}" is not a captured '
                        f'component; using root "{root_native_ref}"'
                    ),
                )
            )
            owner = root_native_ref
        features.append(
            FeatureCandidate(
                native_ref=name,
                native_label=native_label(value),
                cad_type=native_type_id(value, native_ref=name),
                component_native_ref=owner,
                native_path=f"{component_paths[owner]}/{name}",
                owner_scoped_key=name,
                targetability=_targetability(value, is_root=False),
            )
        )
    return features


def _build_parameter_groups(
    objects: tuple[Any, ...],
    object_by_name: dict[str, Any],
    group_parents: dict[str, str],
    component_paths: dict[str, str],
    root_native_ref: str,
    diagnostics: set[DiscoveryDiagnostic],
) -> list[ParameterGroupCandidate]:
    groups: list[ParameterGroupCandidate] = []
    for value in objects:
        if not _is_varset(value):
            continue
        name = native_name_or_none(value)
        if name is None:
            continue
        owner = group_parents.get(name, root_native_ref)
        if owner not in component_paths:
            diagnostics.add(
                DiscoveryDiagnostic(
                    code="unknown_parameter_group_component",
                    native_ref=name,
                    detail=(
                        f'parameter group component "{owner}" is not a captured '
                        f'component; using root "{root_native_ref}"'
                    ),
                )
            )
            owner = root_native_ref
        groups.append(
            ParameterGroupCandidate(
                native_ref=name,
                native_label=native_label(value),
                cad_type=native_type_id(value, native_ref=name),
                owner_component_native_ref=owner,
                native_path=f"{component_paths[owner]}/{name}",
                group_kind="varset",
                observable=True,
                writable=True,
                owner_scoped_key=name,
            )
        )
    return groups


def _build_parameters(
    object_by_name: dict[str, Any],
    parameter_groups: list[ParameterGroupCandidate],
    diagnostics: set[DiscoveryDiagnostic],
) -> list[ParameterCandidate]:
    parameters: list[ParameterCandidate] = []
    for group in parameter_groups:
        value = object_by_name.get(group.native_ref)
        if value is None:
            raise CaptureDiscoveryInspectionError(
                f'parameter group "{group.native_ref}" is missing from native '
                "document Objects"
            )
        properties = properties_list(value)
        if properties is None:
            diagnostics.add(
                DiscoveryDiagnostic(
                    code="properties_unavailable",
                    native_ref=group.native_ref,
                    detail=(
                        "native PropertiesList is unavailable for parameter "
                        "group discovery"
                    ),
                )
            )
            continue
        for key in properties:
            if key in _INTERNAL_VARSET_PROPERTIES or key.startswith("_"):
                continue
            parameters.append(
                ParameterCandidate(
                    owner_kind="group",
                    owner_native_ref=group.native_ref,
                    component_native_ref=group.owner_component_native_ref,
                    native_path=f"{group.native_path}/{key}",
                    owner_scoped_key=key,
                    group_scoped_key=key,
                    property=_property_evidence(
                        value,
                        key,
                        capability="parameter",
                    ),
                )
            )
    return parameters


def _build_metadata(
    document: Any,
    object_by_name: dict[str, Any],
    components: list[ComponentCandidate],
    features: list[FeatureCandidate],
    diagnostics: set[DiscoveryDiagnostic],
) -> list[MetadataCandidate]:
    owners: list[tuple[str, str, str, str, Any]] = []
    for component in components:
        value = (
            document
            if component.synthetic
            else object_by_name.get(component.native_ref)
        )
        if value is None:
            raise CaptureDiscoveryInspectionError(
                f'component "{component.native_ref}" is missing from native '
                "document Objects"
            )
        owners.append(
            (
                component.native_path,
                "component",
                component.native_ref,
                component.native_ref,
                value,
            )
        )
    for feature in features:
        value = object_by_name.get(feature.native_ref)
        if value is None:
            raise CaptureDiscoveryInspectionError(
                f'feature "{feature.native_ref}" is missing from native '
                "document Objects"
            )
        owners.append(
            (
                feature.native_path,
                "feature",
                feature.native_ref,
                feature.component_native_ref,
                value,
            )
        )

    metadata: list[MetadataCandidate] = []
    for owner_path, owner_kind, owner_ref, component_ref, value in sorted(
        owners,
        key=lambda item: (item[0], item[1], item[2]),
    ):
        if not callable(getattr(value, "getGroupOfProperty", None)):
            diagnostics.add(
                DiscoveryDiagnostic(
                    code="property_group_inspection_unavailable",
                    native_ref=owner_ref,
                    detail=(
                        "native getGroupOfProperty is unavailable; metadata "
                        "candidates cannot be discovered"
                    ),
                )
            )
            continue
        properties = properties_list(value)
        if properties is None:
            diagnostics.add(
                DiscoveryDiagnostic(
                    code="properties_unavailable",
                    native_ref=owner_ref,
                    detail=(
                        "native PropertiesList is unavailable for metadata discovery"
                    ),
                )
            )
            continue
        for key in properties:
            if property_group(value, key) != "Metadata":
                continue
            metadata.append(
                MetadataCandidate(
                    owner_kind=owner_kind,
                    owner_native_ref=owner_ref,
                    component_native_ref=component_ref,
                    native_path=f"{owner_path}/{key}",
                    owner_scoped_key=key,
                    property=_property_evidence(
                        value,
                        key,
                        capability="metadata",
                    ),
                )
            )
    return metadata


def _build_drawing_pages(
    document_name: str,
    document: Any,
    object_by_name: dict[str, Any],
    component_names: set[str],
    feature_names: set[str],
    diagnostics: set[DiscoveryDiagnostic],
) -> list[DrawingPageCandidate]:
    handled: set[str] = set()
    page_names = sorted(
        name
        for name, value in object_by_name.items()
        if _is_technical_drawing_page(value)
    )

    drawings: list[DrawingPageCandidate] = []
    for page_order, name in enumerate(page_names, start=1):
        page = object_by_name[name]
        handled.add(name)
        _mark_technical_drawing_dependencies(page, handled)
        targets = _drawing_page_targets(
            document_name,
            page,
            object_by_name,
            component_names,
            feature_names,
            handled,
            diagnostics,
        )
        drawings.append(
            DrawingPageCandidate(
                native_ref=name,
                native_label=native_label(page),
                cad_type=native_type_id(page, native_ref=name),
                page_order=page_order,
                resource=_drawing_resource_evidence(
                    document_name,
                    document,
                    page,
                ),
                targets=targets,
            )
        )

    _diagnose_unhandled_technical_drawing_objects(
        object_by_name,
        handled,
        diagnostics,
    )
    return drawings


def _drawing_resource_evidence(
    document_name: str,
    document: Any,
    page: Any,
) -> DrawingResourceEvidence:
    page_document_name = native_document_name(page)
    if page_document_name is not None and page_document_name != document_name:
        return DrawingResourceEvidence(
            topology="separate",
            document_name=page_document_name,
            document_label=native_document_label(page),
        )
    return DrawingResourceEvidence(
        topology="embedded",
        document_name=document_name,
        document_label=document_label(document),
    )


def _drawing_page_targets(
    document_name: str,
    page: Any,
    object_by_name: dict[str, Any],
    component_names: set[str],
    feature_names: set[str],
    handled: set[str],
    diagnostics: set[DiscoveryDiagnostic],
) -> tuple[DrawingTargetCandidate, ...]:
    page_name = native_name_or_none(page)
    views, available = linked_objects(page, "Views")
    if not available:
        diagnostics.add(
            DiscoveryDiagnostic(
                code="technical_drawing_views_unavailable",
                native_ref=page_name,
                detail=(
                    "native Views is unavailable for technical drawing page discovery"
                ),
            )
        )

    target_kinds: dict[str, str] = {}
    queue: deque[Any] = deque(views)
    visited: set[str] = set()
    while queue:
        view = queue.popleft()
        view_name = native_name_or_none(view)
        if view_name is None:
            diagnostics.add(
                DiscoveryDiagnostic(
                    code="invalid_technical_drawing_view",
                    native_ref=page_name,
                    detail=(
                        "native page Views contains a view without a nonblank "
                        "string Name"
                    ),
                )
            )
            continue
        if view_name in visited:
            continue
        visited.add(view_name)
        handled.add(view_name)
        _mark_technical_drawing_dependencies(view, handled)

        if _is_supported_technical_drawing_view(view):
            _collect_drawing_view_sources(
                document_name,
                view,
                object_by_name,
                component_names,
                feature_names,
                target_kinds,
                diagnostics,
            )
        elif not _is_technical_drawing_view_container(view):
            diagnostics.add(
                DiscoveryDiagnostic(
                    code="unsupported_technical_drawing_view",
                    native_ref=view_name,
                    detail=(
                        "technical drawing view subtype is outside supported "
                        "model-source discovery"
                    ),
                )
            )

        nested, nested_available = linked_objects(view, "Views")
        if nested_available:
            queue.extend(nested)

    return tuple(
        DrawingTargetCandidate(
            native_ref=ref,
            cad_type=native_type_id(
                object_by_name[ref],
                native_ref=ref,
            ),
            kind=kind,
        )
        for ref, kind in sorted(target_kinds.items())
    )


def _collect_drawing_view_sources(
    document_name: str,
    view: Any,
    object_by_name: dict[str, Any],
    component_names: set[str],
    feature_names: set[str],
    target_kinds: dict[str, str],
    diagnostics: set[DiscoveryDiagnostic],
) -> None:
    view_name = native_name_or_none(view) or ""
    for attribute in ("Source", "XSource"):
        sources, available = linked_objects(view, attribute)
        if not available:
            diagnostics.add(
                DiscoveryDiagnostic(
                    code="technical_drawing_source_unavailable",
                    native_ref=view_name or None,
                    detail=(
                        f"native {attribute} is unavailable for technical "
                        "drawing source discovery"
                    ),
                )
            )
        for source in sources:
            _collect_drawing_source(
                document_name,
                view_name,
                attribute,
                source,
                object_by_name,
                component_names,
                feature_names,
                target_kinds,
                diagnostics,
            )


def _collect_drawing_source(
    document_name: str,
    view_name: str,
    attribute: str,
    source: Any,
    object_by_name: dict[str, Any],
    component_names: set[str],
    feature_names: set[str],
    target_kinds: dict[str, str],
    diagnostics: set[DiscoveryDiagnostic],
) -> None:
    source_name = native_name_or_none(source)
    if source_name is None:
        diagnostics.add(
            DiscoveryDiagnostic(
                code="unresolvable_technical_drawing_source",
                native_ref=view_name or None,
                detail=(
                    f"native {attribute} contains a source without a nonblank "
                    "string Name"
                ),
            )
        )
        return

    source_document_name = native_document_name(source)
    if source_document_name is None:
        diagnostics.add(
            DiscoveryDiagnostic(
                code="unresolvable_technical_drawing_source",
                native_ref=source_name,
                detail=(
                    f'drawing view "{view_name}" {attribute} source '
                    f'"{source_name}" has no resolvable native document'
                ),
            )
        )
        return

    if source_document_name != document_name:
        diagnostics.add(
            DiscoveryDiagnostic(
                code="separate_technical_drawing_source",
                native_ref=source_name,
                detail=(
                    f'drawing view "{view_name}" {attribute} source '
                    f'"{source_name}" belongs to document '
                    f'"{source_document_name}"; separate technical drawing '
                    "sources are outside active-document capture scope"
                ),
            )
        )
        return

    if source_name in component_names:
        target_kinds[source_name] = "component"
    elif source_name in feature_names:
        target_kinds[source_name] = "feature"
    else:
        diagnostics.add(
            DiscoveryDiagnostic(
                code="unresolvable_technical_drawing_source",
                native_ref=source_name,
                detail=(
                    f'drawing view "{view_name}" {attribute} source '
                    f'"{source_name}" is not a captured component or feature'
                ),
            )
        )


def _mark_technical_drawing_dependencies(value: Any, handled: set[str]) -> None:
    dependencies, available = linked_objects(value, "OutList")
    if not available:
        return
    for dependency in dependencies:
        name = native_name_or_none(dependency)
        if name is not None and _is_technical_drawing(dependency):
            handled.add(name)


def _diagnose_unhandled_technical_drawing_objects(
    object_by_name: dict[str, Any],
    handled: set[str],
    diagnostics: set[DiscoveryDiagnostic],
) -> None:
    for name in sorted(object_by_name):
        if name in handled:
            continue
        value = object_by_name[name]
        if not _is_technical_drawing(value):
            continue
        diagnostics.add(
            DiscoveryDiagnostic(
                code="unsupported_technical_drawing",
                native_ref=name,
                detail=_EXCLUDED_DIAGNOSTIC_DETAILS["unsupported_technical_drawing"],
            )
        )


def _diagnose_technical_drawing_links(
    object_by_name: dict[str, Any],
    document_name: str,
    diagnostics: set[DiscoveryDiagnostic],
) -> None:
    for name in sorted(object_by_name):
        value = object_by_name[name]
        if not _is_technical_drawing_link(value):
            continue
        target = _linked_object(value)
        target_name = native_name_or_none(target) or ""
        target_document_name = native_document_name(target)
        if target_document_name is None:
            topology = "unresolved"
        elif target_document_name == document_name:
            topology = "embedded"
        else:
            topology = "separate"
        diagnostics.add(
            DiscoveryDiagnostic(
                code="unsupported_technical_drawing_resource",
                native_ref=name,
                detail=(
                    f'linked technical drawing resource "{target_name}" '
                    f"({topology}) is outside active-document capture scope"
                ),
            )
        )


def _empty_targetability() -> TargetabilityEvidence:
    return TargetabilityEvidence(
        suppress=False,
        unsuppress=False,
        hide=False,
        unhide=False,
        delete=False,
        delete_dependents=(),
        delete_dependencies=(),
        dependency_evidence_available=False,
    )


def _targetability(value: Any, *, is_root: bool) -> TargetabilityEvidence:
    suppression = bool_property_writable(value, "Suppressed")
    visibility = bool_property_writable(value, "Visibility")
    dependents, in_list_available = relationship_names(value, "InList")
    dependencies, out_list_available = relationship_names(value, "OutList")
    evidence_available = in_list_available and out_list_available
    return TargetabilityEvidence(
        suppress=suppression,
        unsuppress=suppression,
        hide=visibility,
        unhide=visibility,
        delete=(evidence_available and not dependents and not is_root),
        delete_dependents=dependents,
        delete_dependencies=dependencies,
        dependency_evidence_available=evidence_available,
    )


def _property_evidence(
    value: Any,
    key: str,
    *,
    capability: str,
) -> PropertyEvidence:
    native_type = property_type_id(value, key)
    status, status_available = property_status(value, key)
    native_value = read_native_value(value, key)
    native_kind = (
        NATIVE_VALUE_KIND_BY_TYPE.get(native_type) if native_type is not None else None
    )

    if native_type is None:
        return PropertyEvidence(
            native_key=key,
            native_type_id=None,
            native_value_kind=None,
            value_type=None,
            current_value=None,
            unit=None,
            observable=False,
            writable=False,
            supported=False,
            native_readable=native_value.readable,
            property_status=status,
            property_status_available=status_available,
            unsupported_reason="unreadable_native_property_type",
        )

    supported_types = (
        PARAMETER_NATIVE_TYPES if capability == "parameter" else METADATA_NATIVE_TYPES
    )
    if native_type not in supported_types:
        return PropertyEvidence(
            native_key=key,
            native_type_id=native_type,
            native_value_kind=native_kind,
            value_type=None,
            current_value=None,
            unit=None,
            observable=False,
            writable=False,
            supported=False,
            native_readable=native_value.readable,
            property_status=status,
            property_status_available=status_available,
            unsupported_reason=f"unsupported_native_{capability}_type",
        )

    if not native_value.readable:
        reason = native_value.error or "unreadable_native_property"
        return PropertyEvidence(
            native_key=key,
            native_type_id=native_type,
            native_value_kind=native_kind,
            value_type=None,
            current_value=None,
            unit=None,
            observable=False,
            writable=False,
            supported=False,
            native_readable=False,
            property_status=status,
            property_status_available=status_available,
            unsupported_reason=reason,
        )

    if native_value.error is not None:
        return PropertyEvidence(
            native_key=key,
            native_type_id=native_type,
            native_value_kind=native_kind,
            value_type=None,
            current_value=None,
            unit=None,
            observable=False,
            writable=False,
            supported=False,
            native_readable=True,
            property_status=status,
            property_status_available=status_available,
            unsupported_reason=native_value.error,
        )

    value_type = (
        _VALUE_TYPE_BY_NATIVE_KIND.get(native_kind) if native_kind is not None else None
    )
    if not _native_value_matches_kind(native_value.python_kind, native_kind):
        return PropertyEvidence(
            native_key=key,
            native_type_id=native_type,
            native_value_kind=native_kind,
            value_type=None,
            current_value=None,
            unit=None,
            observable=False,
            writable=False,
            supported=False,
            native_readable=True,
            property_status=status,
            property_status_available=status_available,
            unsupported_reason="native_value_type_mismatch",
        )

    unit = (
        native_value.unit
        if capability == "parameter" and native_kind in QUANTITY_NATIVE_KINDS
        else None
    )
    return PropertyEvidence(
        native_key=key,
        native_type_id=native_type,
        native_value_kind=native_kind,
        value_type=value_type,
        current_value=native_value.scalar,
        unit=unit,
        observable=True,
        writable=status_available and not is_read_only_status(status),
        supported=True,
        native_readable=True,
        property_status=status,
        property_status_available=status_available,
        unsupported_reason=None,
    )


def _native_value_matches_kind(
    python_kind: str | None,
    native_kind: str | None,
) -> bool:
    if native_kind is None:
        return False
    if native_kind in QUANTITY_NATIVE_KINDS:
        return python_kind == "quantity"
    return python_kind == native_kind


__all__ = [
    "CaptureDiscovery",
    "ComponentCandidate",
    "DiscoveryDiagnostic",
    "DocumentEvidence",
    "DrawingPageCandidate",
    "DrawingResourceEvidence",
    "DrawingTargetCandidate",
    "FeatureCandidate",
    "MetadataCandidate",
    "ParameterCandidate",
    "ParameterGroupCandidate",
    "PropertyEvidence",
    "TargetabilityEvidence",
    "discover_capture_candidates",
]
