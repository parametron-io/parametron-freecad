"""Native occurrence evidence for the supported Assembly Group mechanism."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parametron_freecad.common.paths import resolve_path
from parametron_freecad.runtime.evidence_sidecar import (
    EvidenceSidecarError,
    EvidenceSidecarWriteError,
    remove_evidence_sidecar,
    write_canonical_json_sidecar_atomically,
)
from parametron_freecad.runtime.occurrence_access import (
    NATIVE_TYPE_APP_LINK,
    NATIVE_TYPE_APP_LINK_ELEMENT,
    NATIVE_TYPE_ASSEMBLY_LINK,
    NATIVE_TYPE_ASSEMBLY_OBJECT,
    NATIVE_TYPE_JOINT_GROUP,
    SUPPORTED_OCCURRENCE_TARGET_TYPES,
    OccurrenceNativeAccessError,
    find_native_object,
    native_document_file_name,
    native_element_count,
    native_group_contents,
    native_group_members,
    native_linked_object,
    native_object_exists,
    native_object_name,
    native_type_id,
    require_membership_corroborated,
)
from parametron_freecad.runtime.occurrence_request import (
    OCCURRENCE_MECHANISM_DIRECT_MEMBER,
    OccurrenceEntity,
    OccurrenceRequest,
    OccurrenceRequestError,
    OccurrenceResourceIdentity,
    OccurrenceScope,
)
from parametron_freecad.runtime.resource_inventory import ResourceInventory

OCCURRENCE_EVIDENCE_FILENAME = "prm.occurrence-evidence.json"
OCCURRENCE_EVIDENCE_SCHEMA_VERSION = "1.1"
OCCURRENCE_EVIDENCE_KIND = "native_occurrence_evidence"
OCCURRENCE_SUPPORTED_FREECAD_VERSION = "1.1.4"

COMPLETENESS_COMPLETE = "complete"
COMPLETENESS_INCOMPLETE = "incomplete"
COMPLETENESS_UNSUPPORTED = "unsupported"
COMPLETENESS_UNAVAILABLE = "unavailable"

CLASSIFICATION_OCCURRENCE = "occurrence"
CLASSIFICATION_AUXILIARY = "auxiliary"
CLASSIFICATION_UNRESOLVED = "unresolved"
CLASSIFICATION_UNSUPPORTED = "unsupported"

RESOLUTION_RESOLVED = "resolved"
RESOLUTION_UNRESOLVED = "unresolved"
RESOLUTION_UNSUPPORTED = "unsupported"
RESOLUTION_UNAVAILABLE = "unavailable"

DECLARED_STATUS_RESOLVED = "resolved"
DECLARED_STATUS_MISSING = "missing"
DECLARED_STATUS_UNDECLARED = "undeclared"
DECLARED_STATUS_AMBIGUOUS = "ambiguous"
DECLARED_STATUS_UNAVAILABLE = "unavailable"

_UNHANDLED_CLASSIFICATIONS = frozenset(
    {CLASSIFICATION_UNRESOLVED, CLASSIFICATION_UNSUPPORTED}
)


class OccurrenceObservationError(ValueError):
    """Raised when occurrence evidence cannot be observed or emitted."""


class OccurrenceEvidenceError(OccurrenceObservationError):
    """Raised when occurrence evidence cannot be written safely."""


@dataclass(frozen=True, slots=True)
class DeclaredResourceBinding:
    """One attempted-relative declared resource joined to a native path."""

    project_id: str
    kind: str
    logical_id: str
    coordinate: str
    resolved_path: Path

    def identity(self) -> OccurrenceResourceIdentity:
        return OccurrenceResourceIdentity(
            project_id=self.project_id,
            kind=self.kind,
            logical_id=self.logical_id,
        )


@dataclass(frozen=True, slots=True)
class DeclaredDocumentResolution:
    """Result of joining a native document path to declared resource identity."""

    status: str
    binding: DeclaredResourceBinding | None = None
    diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class DeclaredResourceResolver:
    """Mapping-driven declared-resource resolver for occurrence targets."""

    bindings: tuple[DeclaredResourceBinding, ...]
    source_binding: DeclaredResourceBinding
    undeclared_diagnostic: str = "native document is not a declared resource"

    def binding_for_coordinate(self, coordinate: str) -> DeclaredResourceBinding | None:
        for binding in self.bindings:
            if binding.coordinate == coordinate:
                return binding
        return None

    def resolve_native_document_path(
        self,
        file_name: str | Path | None,
    ) -> DeclaredDocumentResolution:
        if not isinstance(file_name, (str, Path)) or not str(file_name):
            return DeclaredDocumentResolution(
                status=DECLARED_STATUS_UNAVAILABLE,
                diagnostic="native document has no stable file identity",
            )

        candidate = Path(file_name).expanduser()
        if not candidate.is_absolute():
            return DeclaredDocumentResolution(
                status=DECLARED_STATUS_UNAVAILABLE,
                diagnostic="native document path is not absolute",
            )

        resolved = resolve_path(candidate)
        matches = tuple(
            binding for binding in self.bindings if binding.resolved_path == resolved
        )
        if len(matches) == 1:
            binding = matches[0]
            if not binding.resolved_path.is_file():
                return DeclaredDocumentResolution(
                    status=DECLARED_STATUS_MISSING,
                    binding=binding,
                    diagnostic=(f"target document {binding.coordinate!r} is missing"),
                )
            return DeclaredDocumentResolution(
                status=DECLARED_STATUS_RESOLVED,
                binding=binding,
            )
        if not matches:
            return DeclaredDocumentResolution(
                status=DECLARED_STATUS_UNDECLARED,
                diagnostic=self.undeclared_diagnostic,
            )
        return DeclaredDocumentResolution(
            status=DECLARED_STATUS_AMBIGUOUS,
            diagnostic="target document matches multiple declared resources",
        )


def resolver_from_inventory(
    inventory: ResourceInventory,
    *,
    project_id: str,
) -> DeclaredResourceResolver:
    """Join the declared integrity inventory to a mapping-driven resolver."""
    bindings = tuple(
        DeclaredResourceBinding(
            project_id=project_id,
            kind=binding.kind,
            logical_id=binding.logical_id,
            coordinate=binding.materialized_coordinate,
            resolved_path=binding.resolved_path,
        )
        for binding in inventory.bindings
    )
    selected = inventory.selected_source_binding
    source_binding = next(
        (
            binding
            for binding in bindings
            if binding.resolved_path == selected.resolved_path
        ),
        None,
    )
    if source_binding is None:
        raise OccurrenceEvidenceError(
            "selected source resource is not declared in the resource inventory"
        )
    return DeclaredResourceResolver(
        bindings=bindings,
        source_binding=source_binding,
    )


def resolver_from_selected_source(
    *,
    parent_resource: OccurrenceResourceIdentity,
    source_document: str,
    source_path: str | Path,
) -> DeclaredResourceResolver:
    """Resolve only the selected source coordinate without a declared inventory."""
    binding = DeclaredResourceBinding(
        project_id=parent_resource.project_id,
        kind=parent_resource.kind,
        logical_id=parent_resource.logical_id,
        coordinate=source_document,
        resolved_path=resolve_path(source_path),
    )
    return DeclaredResourceResolver(
        bindings=(binding,),
        source_binding=binding,
        undeclared_diagnostic="declared resource inventory is unavailable",
    )


def require_occurrence_parent_source(
    request: OccurrenceRequest,
    inventory: ResourceInventory,
    *,
    source_document: str,
) -> None:
    """Require the requested parent to be the selected declared source."""
    binding = inventory.binding_for_coordinate(source_document)
    parent = request.scope.parent
    if (
        binding is None
        or binding.resolved_path != inventory.selected_source_binding.resolved_path
        or binding.logical_id != parent.resource.logical_id
        or binding.kind != parent.resource.kind
    ):
        raise OccurrenceRequestError(
            "occurrence request parent is not the selected source resource"
        )


def resolve_freecad_version(freecad_module: Any) -> str:
    """Return the bounded three-component FreeCAD version token."""
    version = getattr(freecad_module, "Version", None)
    value: Any = None
    if callable(version):
        try:
            value = version()
        except Exception:
            value = None
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        return ".".join(str(part) for part in value[:3])
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "unavailable"


@dataclass(frozen=True, slots=True)
class OccurrenceMemberTarget:
    """Resolved native target carrying declared identity and coordinate."""

    binding: DeclaredResourceBinding
    native_type: str
    name: str

    def to_entity_payload(self) -> dict[str, Any]:
        return {
            "resource": self.binding.identity().to_payload(),
            "nativeKind": "object",
            "name": self.name,
        }

    def to_payload(self) -> dict[str, Any]:
        return {
            "entity": self.to_entity_payload(),
            "document": self.binding.coordinate,
            "nativeType": self.native_type,
        }


@dataclass(frozen=True, slots=True)
class OccurrenceMemberContents:
    """Explicit auxiliary child inspection result."""

    inspection_completed: bool
    group: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "inspectionCompleted": self.inspection_completed,
            "group": list(self.group),
        }


@dataclass(frozen=True, slots=True)
class OccurrenceMemberEvidence:
    """One classified native Group member."""

    name: str
    native_type: str
    element_count: int | None
    membership_corroborated: bool
    classification: str
    resolution: str
    native_state_valid: bool
    target: OccurrenceMemberTarget | None
    diagnostic: str | None
    contents: OccurrenceMemberContents | None = None

    def to_payload(self, parent_payload: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "parent": parent_payload,
            "nativeType": self.native_type,
            "elementCount": self.element_count,
            "membershipCorroborated": self.membership_corroborated,
            "classification": self.classification,
            "resolution": self.resolution,
            "nativeStateValid": self.native_state_valid,
            "target": None if self.target is None else self.target.to_payload(),
        }
        if self.diagnostic is not None:
            payload["diagnostic"] = self.diagnostic
        if self.contents is not None:
            payload["contents"] = self.contents.to_payload()
        return payload


@dataclass(frozen=True, slots=True)
class OccurrenceParentEvidence:
    """Observed occurrence parent entity."""

    entity: OccurrenceEntity
    document: str
    native_type: str

    def to_entity_payload(self) -> dict[str, Any]:
        return self.entity.to_payload()

    def to_payload(self) -> dict[str, Any]:
        return {
            "entity": self.to_entity_payload(),
            "document": self.document,
            "nativeType": self.native_type,
        }


@dataclass(frozen=True, slots=True)
class OccurrenceEvidenceObservation:
    """Complete native occurrence observation for one requested scope."""

    scope: OccurrenceScope
    freecad_version: str
    parent: OccurrenceParentEvidence | None
    completeness: str
    inspection_completed: bool
    group: tuple[str, ...]
    members: tuple[OccurrenceMemberEvidence, ...]
    diagnostics: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        parent_payload = (
            None if self.parent is None else self.parent.to_entity_payload()
        )
        members = []
        for member in self.members:
            if parent_payload is None:
                raise OccurrenceEvidenceError(
                    "occurrence member requires an observed parent entity"
                )
            members.append(member.to_payload(parent_payload))
        return {
            "schemaVersion": OCCURRENCE_EVIDENCE_SCHEMA_VERSION,
            "kind": OCCURRENCE_EVIDENCE_KIND,
            "freecadVersion": self.freecad_version,
            "scope": self.scope.to_payload(),
            "parent": None if self.parent is None else self.parent.to_payload(),
            "completeness": self.completeness,
            "inspectionCompleted": self.inspection_completed,
            "group": list(self.group),
            "members": members,
            "diagnostics": list(self.diagnostics),
        }


def inspect_occurrence_evidence(
    document: Any,
    request: OccurrenceRequest,
    *,
    source_document: str,
    resolver: DeclaredResourceResolver,
    freecad_version: str,
) -> OccurrenceEvidenceObservation:
    """Inspect the requested Assembly Group on an already-opened document."""
    scope = request.scope
    scope_supported = (
        scope.mechanism == OCCURRENCE_MECHANISM_DIRECT_MEMBER
        and freecad_version == OCCURRENCE_SUPPORTED_FREECAD_VERSION
        and len(scope.context) == 0
    )

    parent_object = find_native_object(document, scope.parent.name)
    if parent_object is None:
        return _unavailable_observation(
            scope,
            freecad_version,
            "requested parent native object is unavailable",
        )

    parent_evidence = OccurrenceParentEvidence(
        entity=scope.parent,
        document=source_document,
        native_type=native_type_id(parent_object),
    )

    if not scope_supported:
        return OccurrenceEvidenceObservation(
            scope=scope,
            freecad_version=freecad_version,
            parent=parent_evidence,
            completeness=COMPLETENESS_UNSUPPORTED,
            inspection_completed=False,
            group=(),
            members=(),
            diagnostics=(_unsupported_scope_diagnostic(request, freecad_version),),
        )

    if parent_evidence.native_type != NATIVE_TYPE_ASSEMBLY_OBJECT:
        return OccurrenceEvidenceObservation(
            scope=scope,
            freecad_version=freecad_version,
            parent=parent_evidence,
            completeness=COMPLETENESS_UNSUPPORTED,
            inspection_completed=False,
            group=(),
            members=(),
            diagnostics=("requested parent is not an Assembly::AssemblyObject",),
        )

    group_objects = native_group_members(parent_object)
    ordered_members = _order_group_members(group_objects)
    group_names = tuple(native_object_name(member) for member in ordered_members)

    member_evidence = tuple(
        _classify_member(member, parent_object, resolver) for member in ordered_members
    )

    diagnostics = tuple(
        f"{member.name}: {member.diagnostic}"
        for member in member_evidence
        if member.diagnostic is not None
    )
    unhandled = any(
        member.classification in _UNHANDLED_CLASSIFICATIONS
        for member in member_evidence
    )
    completeness = COMPLETENESS_INCOMPLETE if unhandled else COMPLETENESS_COMPLETE

    return OccurrenceEvidenceObservation(
        scope=scope,
        freecad_version=freecad_version,
        parent=parent_evidence,
        completeness=completeness,
        inspection_completed=True,
        group=group_names,
        members=member_evidence,
        diagnostics=diagnostics,
    )


def prepare_occurrence_evidence(
    *,
    working_copy: str | Path,
    output_directory: str | Path | None,
) -> None:
    """Validate the evidence destination and remove a stale sidecar."""
    if output_directory is None:
        raise OccurrenceEvidenceError(
            "occurrence evidence requires an existing output directory"
        )
    try:
        remove_evidence_sidecar(
            working_copy=working_copy,
            output_directory=output_directory,
            filename=OCCURRENCE_EVIDENCE_FILENAME,
        )
    except (EvidenceSidecarError, EvidenceSidecarWriteError) as exc:
        raise OccurrenceEvidenceError(
            "occurrence evidence destination is not usable"
        ) from exc


def write_occurrence_evidence(
    observation: OccurrenceEvidenceObservation,
    *,
    working_copy: str | Path,
    output_directory: str | Path | None,
) -> Path:
    """Write the canonical occurrence evidence sidecar for a successful run."""
    if output_directory is None:
        raise OccurrenceEvidenceError(
            "occurrence evidence requires an existing output directory"
        )
    try:
        return write_canonical_json_sidecar_atomically(
            working_copy=working_copy,
            output_directory=output_directory,
            filename=OCCURRENCE_EVIDENCE_FILENAME,
            payload=observation.to_payload(),
        )
    except (EvidenceSidecarError, EvidenceSidecarWriteError) as exc:
        raise OccurrenceEvidenceError(
            "occurrence evidence could not be written"
        ) from exc


def _order_group_members(group_objects: tuple[Any, ...]) -> tuple[Any, ...]:
    named: list[tuple[str, Any]] = []
    seen: set[str] = set()
    for member in group_objects:
        name = native_object_name(member)
        if name in seen:
            raise OccurrenceNativeAccessError(
                "native Group contains duplicate object identity"
            )
        seen.add(name)
        named.append((name, member))
    named.sort(key=lambda item: item[0])
    return tuple(member for _, member in named)


def _classify_member(
    member: Any,
    parent_object: Any,
    resolver: DeclaredResourceResolver,
) -> OccurrenceMemberEvidence:
    name = native_object_name(member)
    member_type = native_type_id(member)
    require_membership_corroborated(parent_object, member)

    if member_type == NATIVE_TYPE_APP_LINK:
        return _classify_app_link(member, name, member_type, resolver)

    if member_type == NATIVE_TYPE_JOINT_GROUP:
        contents = native_group_contents(member)
        if contents is None:
            return _unsupported(
                name,
                member_type,
                "native joint group contents are unavailable",
            )
        if contents:
            return _unsupported(
                name,
                member_type,
                f"non-empty joint group with {len(contents)} member(s) is unsupported",
            )
        return OccurrenceMemberEvidence(
            name=name,
            native_type=member_type,
            element_count=None,
            membership_corroborated=True,
            classification=CLASSIFICATION_AUXILIARY,
            resolution=RESOLUTION_RESOLVED,
            native_state_valid=True,
            target=None,
            diagnostic=None,
            contents=OccurrenceMemberContents(
                inspection_completed=True,
                group=(),
            ),
        )

    if member_type == NATIVE_TYPE_ASSEMBLY_OBJECT:
        return _unsupported(
            name,
            member_type,
            "nested Assembly::AssemblyObject member is unsupported",
        )
    if member_type == NATIVE_TYPE_ASSEMBLY_LINK:
        return _unsupported(
            name,
            member_type,
            "nested Assembly::AssemblyLink member is unsupported",
        )
    if member_type == NATIVE_TYPE_APP_LINK_ELEMENT:
        return _unsupported(
            name,
            member_type,
            "App::LinkElement member is unsupported",
        )
    return _unsupported(
        name,
        member_type,
        f"member native type {member_type!r} is unsupported",
    )


def _classify_app_link(
    member: Any,
    name: str,
    member_type: str,
    resolver: DeclaredResourceResolver,
) -> OccurrenceMemberEvidence:
    element_count = native_element_count(member)
    if element_count is None:
        return _unsupported(
            name,
            member_type,
            "native App::Link has no ElementCount",
        )
    if element_count != 0:
        return _unsupported(
            name,
            member_type,
            f"linked element array with ElementCount {element_count} is unsupported",
            element_count=element_count,
        )

    linked = native_linked_object(member)
    if linked is None:
        return _unresolved(
            name,
            member_type,
            element_count,
            "native App::Link has no resolved target",
        )

    try:
        target_name = native_object_name(linked)
        target_type = native_type_id(linked)
    except OccurrenceNativeAccessError:
        return _unresolved(
            name,
            member_type,
            element_count,
            "native link target has no stable object identity",
        )

    resolution = resolver.resolve_native_document_path(
        native_document_file_name(linked)
    )
    if resolution.status != DECLARED_STATUS_RESOLVED or resolution.binding is None:
        return _unresolved(
            name,
            member_type,
            element_count,
            resolution.diagnostic or "target document identity is unavailable",
            resolution=(
                RESOLUTION_UNRESOLVED
                if resolution.status == DECLARED_STATUS_MISSING
                else RESOLUTION_UNAVAILABLE
            ),
        )

    if not native_object_exists(getattr(linked, "Document", None), target_name):
        return _unresolved(
            name,
            member_type,
            element_count,
            f"target object {target_name!r} is missing from its native document",
        )

    if target_type not in SUPPORTED_OCCURRENCE_TARGET_TYPES:
        return _unsupported(
            name,
            member_type,
            f"target native type {target_type!r} is unsupported",
            element_count=element_count,
        )

    return OccurrenceMemberEvidence(
        name=name,
        native_type=member_type,
        element_count=element_count,
        membership_corroborated=True,
        classification=CLASSIFICATION_OCCURRENCE,
        resolution=RESOLUTION_RESOLVED,
        native_state_valid=True,
        target=OccurrenceMemberTarget(
            binding=resolution.binding,
            native_type=target_type,
            name=target_name,
        ),
        diagnostic=None,
    )


def _unsupported(
    name: str,
    member_type: str,
    diagnostic: str,
    *,
    element_count: int | None = None,
) -> OccurrenceMemberEvidence:
    return OccurrenceMemberEvidence(
        name=name,
        native_type=member_type,
        element_count=element_count,
        membership_corroborated=True,
        classification=CLASSIFICATION_UNSUPPORTED,
        resolution=RESOLUTION_UNSUPPORTED,
        native_state_valid=True,
        target=None,
        diagnostic=diagnostic,
    )


def _unresolved(
    name: str,
    member_type: str,
    element_count: int,
    diagnostic: str,
    *,
    resolution: str = RESOLUTION_UNRESOLVED,
) -> OccurrenceMemberEvidence:
    return OccurrenceMemberEvidence(
        name=name,
        native_type=member_type,
        element_count=element_count,
        membership_corroborated=True,
        classification=CLASSIFICATION_UNRESOLVED,
        resolution=resolution,
        native_state_valid=False,
        target=None,
        diagnostic=diagnostic,
    )


def _unavailable_observation(
    scope: OccurrenceScope,
    freecad_version: str,
    diagnostic: str,
) -> OccurrenceEvidenceObservation:
    return OccurrenceEvidenceObservation(
        scope=scope,
        freecad_version=freecad_version,
        parent=None,
        completeness=COMPLETENESS_UNAVAILABLE,
        inspection_completed=False,
        group=(),
        members=(),
        diagnostics=(diagnostic,),
    )


def _unsupported_scope_diagnostic(
    request: OccurrenceRequest,
    freecad_version: str,
) -> str:
    scope = request.scope
    if scope.mechanism != OCCURRENCE_MECHANISM_DIRECT_MEMBER:
        return f"occurrence mechanism {scope.mechanism!r} is unsupported"
    if freecad_version != OCCURRENCE_SUPPORTED_FREECAD_VERSION:
        return f"FreeCAD version {freecad_version!r} is unsupported"
    return "nested occurrence context is unsupported"


__all__ = [
    "CLASSIFICATION_AUXILIARY",
    "CLASSIFICATION_OCCURRENCE",
    "CLASSIFICATION_UNRESOLVED",
    "CLASSIFICATION_UNSUPPORTED",
    "COMPLETENESS_COMPLETE",
    "COMPLETENESS_INCOMPLETE",
    "COMPLETENESS_UNAVAILABLE",
    "COMPLETENESS_UNSUPPORTED",
    "DeclaredDocumentResolution",
    "DeclaredResourceBinding",
    "DeclaredResourceResolver",
    "OCCURRENCE_EVIDENCE_FILENAME",
    "OCCURRENCE_EVIDENCE_KIND",
    "OCCURRENCE_EVIDENCE_SCHEMA_VERSION",
    "OCCURRENCE_SUPPORTED_FREECAD_VERSION",
    "OccurrenceEvidenceError",
    "OccurrenceEvidenceObservation",
    "OccurrenceMemberContents",
    "OccurrenceMemberEvidence",
    "OccurrenceMemberTarget",
    "OccurrenceObservationError",
    "OccurrenceParentEvidence",
    "RESOLUTION_RESOLVED",
    "RESOLUTION_UNAVAILABLE",
    "RESOLUTION_UNRESOLVED",
    "RESOLUTION_UNSUPPORTED",
    "inspect_occurrence_evidence",
    "prepare_occurrence_evidence",
    "require_occurrence_parent_source",
    "resolve_freecad_version",
    "resolver_from_inventory",
    "resolver_from_selected_source",
    "write_occurrence_evidence",
]
