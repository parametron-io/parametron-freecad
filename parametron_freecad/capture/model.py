"""Immutable schema 1.0 capture records and mapping conversion.

The records mirror the Engine-owned ``prm.cad.json`` contract. ``from_mapping``
validates shape, policy, and reference consistency before constructing records.
``to_mapping`` returns a fresh JSON-ready mapping and never mutates the input or
the record. Optional fields are omitted when absent so canonical output matches
the Engine contract's ``omitempty`` behavior.

This module is GUI-free and FreeCAD-free.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from parametron_freecad.capture.validation import validate_capture_document


class _Unset:
    """Sentinel type for an absent optional ``currentValue``."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


_UNSET = _Unset()


@dataclass(frozen=True, slots=True)
class Annotations:
    description: str = ""
    comment: str = ""
    purpose: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Annotations:
        return cls(
            description=value["description"],
            comment=value["comment"],
            purpose=value["purpose"],
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "comment": self.comment,
            "purpose": self.purpose,
        }


@dataclass(frozen=True, slots=True)
class NamedVersion:
    name: str
    version: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> NamedVersion:
        return cls(name=value["name"], version=value["version"])

    def to_mapping(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version}


@dataclass(frozen=True, slots=True)
class SourceDocument:
    logical_id: str
    path: str
    fingerprint: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SourceDocument:
        return cls(
            logical_id=value["logicalId"],
            path=value["path"],
            fingerprint=value["fingerprint"],
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "logicalId": self.logical_id,
            "path": self.path,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class RootProduct:
    id: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RootProduct:
        return cls(id=value["id"])

    def to_mapping(self) -> dict[str, Any]:
        return {"id": self.id}


@dataclass(frozen=True, slots=True)
class IdentitySource:
    kind: str
    path: str | None = None
    owner_scoped_key: str | None = None
    group_scoped_key: str | None = None
    native_ref: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> IdentitySource:
        native_ref = value.get("nativeRef")
        return cls(
            kind=value["kind"],
            path=value.get("path"),
            owner_scoped_key=value.get("ownerScopedKey"),
            group_scoped_key=value.get("groupScopedKey"),
            native_ref=native_ref or None,
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {"kind": self.kind}
        if self.path is not None:
            result["path"] = self.path
        if self.owner_scoped_key is not None:
            result["ownerScopedKey"] = self.owner_scoped_key
        if self.group_scoped_key is not None:
            result["groupScopedKey"] = self.group_scoped_key
        if self.native_ref:
            result["nativeRef"] = self.native_ref
        return result


@dataclass(frozen=True, slots=True)
class Targetability:
    suppress: bool = False
    unsuppress: bool = False
    hide: bool = False
    unhide: bool = False
    delete: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Targetability:
        return cls(
            suppress=value["suppress"],
            unsuppress=value["unsuppress"],
            hide=value["hide"],
            unhide=value["unhide"],
            delete=value["delete"],
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "suppress": self.suppress,
            "unsuppress": self.unsuppress,
            "hide": self.hide,
            "unhide": self.unhide,
            "delete": self.delete,
        }


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SourceFile:
        return cls(path=value["path"])

    def to_mapping(self) -> dict[str, Any]:
        return {"path": self.path}


@dataclass(frozen=True, slots=True)
class Component:
    id: str
    kind: str
    name: str
    display_name: str
    cad_type: str
    quantity: int
    material: str = ""
    identity_source: IdentitySource | None = None
    stability_class: str = ""
    source_file: SourceFile | None = None
    targetability: Targetability = field(default_factory=Targetability)
    annotations: Annotations = field(default_factory=Annotations)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Component:
        identity = value.get("identitySource")
        source_file = value.get("sourceFile")
        return cls(
            id=value["id"],
            kind=value["kind"],
            name=value["name"],
            display_name=value["displayName"],
            cad_type=value["cadType"],
            quantity=value["quantity"],
            material=value["material"],
            identity_source=(
                IdentitySource.from_mapping(identity)
                if isinstance(identity, Mapping)
                else None
            ),
            stability_class=value.get("stabilityClass", ""),
            source_file=(
                SourceFile.from_mapping(source_file)
                if isinstance(source_file, Mapping)
                else None
            ),
            targetability=Targetability.from_mapping(value["targetability"]),
            annotations=Annotations.from_mapping(value["annotations"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "displayName": self.display_name,
            "cadType": self.cad_type,
            "quantity": self.quantity,
            "material": self.material,
        }
        if self.identity_source is not None:
            result["identitySource"] = self.identity_source.to_mapping()
        if self.stability_class:
            result["stabilityClass"] = self.stability_class
        if self.source_file is not None:
            result["sourceFile"] = self.source_file.to_mapping()
        result["targetability"] = self.targetability.to_mapping()
        result["annotations"] = self.annotations.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class Feature:
    id: str
    component_id: str
    name: str
    display_name: str
    cad_type: str
    identity_source: IdentitySource | None = None
    stability_class: str = ""
    targetability: Targetability = field(default_factory=Targetability)
    annotations: Annotations = field(default_factory=Annotations)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Feature:
        identity = value.get("identitySource")
        return cls(
            id=value["id"],
            component_id=value["componentId"],
            name=value["name"],
            display_name=value["displayName"],
            cad_type=value["cadType"],
            identity_source=(
                IdentitySource.from_mapping(identity)
                if isinstance(identity, Mapping)
                else None
            ),
            stability_class=value.get("stabilityClass", ""),
            targetability=Targetability.from_mapping(value["targetability"]),
            annotations=Annotations.from_mapping(value["annotations"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "componentId": self.component_id,
            "name": self.name,
            "displayName": self.display_name,
            "cadType": self.cad_type,
        }
        if self.identity_source is not None:
            result["identitySource"] = self.identity_source.to_mapping()
        if self.stability_class:
            result["stabilityClass"] = self.stability_class
        result["targetability"] = self.targetability.to_mapping()
        result["annotations"] = self.annotations.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class Relationship:
    id: str
    kind: str
    component_id: str
    name: str
    cad_type: str
    endpoints: tuple[str, ...]
    identity_source: IdentitySource | None = None
    stability_class: str = ""
    targetability: Targetability = field(default_factory=Targetability)
    annotations: Annotations = field(default_factory=Annotations)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Relationship:
        identity = value.get("identitySource")
        return cls(
            id=value["id"],
            kind=value["kind"],
            component_id=value["componentId"],
            name=value["name"],
            cad_type=value["cadType"],
            endpoints=tuple(value["endpoints"]),
            identity_source=(
                IdentitySource.from_mapping(identity)
                if isinstance(identity, Mapping)
                else None
            ),
            stability_class=value.get("stabilityClass", ""),
            targetability=Targetability.from_mapping(value["targetability"]),
            annotations=Annotations.from_mapping(value["annotations"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "componentId": self.component_id,
            "name": self.name,
            "cadType": self.cad_type,
            "endpoints": list(self.endpoints),
        }
        if self.identity_source is not None:
            result["identitySource"] = self.identity_source.to_mapping()
        if self.stability_class:
            result["stabilityClass"] = self.stability_class
        result["targetability"] = self.targetability.to_mapping()
        result["annotations"] = self.annotations.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class ParameterGroup:
    id: str
    owner_component_id: str
    name: str
    display_name: str
    group_kind: str
    cad_type: str
    observable: bool
    writable: bool
    identity_source: IdentitySource | None = None
    stability_class: str = ""
    annotations: Annotations = field(default_factory=Annotations)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ParameterGroup:
        identity = value.get("identitySource")
        return cls(
            id=value["id"],
            owner_component_id=value["ownerComponentId"],
            name=value["name"],
            display_name=value["displayName"],
            group_kind=value["groupKind"],
            cad_type=value["cadType"],
            observable=value["observable"],
            writable=value["writable"],
            identity_source=(
                IdentitySource.from_mapping(identity)
                if isinstance(identity, Mapping)
                else None
            ),
            stability_class=value.get("stabilityClass", ""),
            annotations=Annotations.from_mapping(value["annotations"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "ownerComponentId": self.owner_component_id,
            "name": self.name,
            "displayName": self.display_name,
            "groupKind": self.group_kind,
            "cadType": self.cad_type,
            "observable": self.observable,
            "writable": self.writable,
        }
        if self.identity_source is not None:
            result["identitySource"] = self.identity_source.to_mapping()
        if self.stability_class:
            result["stabilityClass"] = self.stability_class
        result["annotations"] = self.annotations.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class Parameter:
    id: str
    owner_kind: str
    owner_id: str
    component_id: str
    name: str
    display_name: str
    cad_type: str
    value_type: str
    observable: bool
    writable: bool
    current_value: Any = _UNSET
    unit: str = ""
    identity_source: IdentitySource | None = None
    stability_class: str = ""
    annotations: Annotations = field(default_factory=Annotations)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Parameter:
        identity = value.get("identitySource")
        current_value = value["currentValue"] if "currentValue" in value else _UNSET
        return cls(
            id=value["id"],
            owner_kind=value["ownerKind"],
            owner_id=value["ownerId"],
            component_id=value["componentId"],
            name=value["name"],
            display_name=value["displayName"],
            cad_type=value["cadType"],
            value_type=value["valueType"],
            observable=value["observable"],
            writable=value["writable"],
            current_value=current_value,
            unit=value.get("unit", ""),
            identity_source=(
                IdentitySource.from_mapping(identity)
                if isinstance(identity, Mapping)
                else None
            ),
            stability_class=value.get("stabilityClass", ""),
            annotations=Annotations.from_mapping(value["annotations"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "ownerKind": self.owner_kind,
            "ownerId": self.owner_id,
            "componentId": self.component_id,
            "name": self.name,
            "displayName": self.display_name,
            "cadType": self.cad_type,
            "valueType": self.value_type,
            "observable": self.observable,
            "writable": self.writable,
        }
        if self.current_value is not _UNSET:
            result["currentValue"] = self.current_value
        if self.unit:
            result["unit"] = self.unit
        if self.identity_source is not None:
            result["identitySource"] = self.identity_source.to_mapping()
        if self.stability_class:
            result["stabilityClass"] = self.stability_class
        result["annotations"] = self.annotations.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class Metadata:
    id: str
    owner_kind: str
    owner_id: str
    component_id: str
    key: str
    display_name: str
    cad_type: str
    value_type: str
    observable: bool
    writable: bool
    current_value: Any = _UNSET
    identity_source: IdentitySource | None = None
    stability_class: str = ""
    annotations: Annotations = field(default_factory=Annotations)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Metadata:
        identity = value.get("identitySource")
        current_value = value["currentValue"] if "currentValue" in value else _UNSET
        return cls(
            id=value["id"],
            owner_kind=value["ownerKind"],
            owner_id=value["ownerId"],
            component_id=value["componentId"],
            key=value["key"],
            display_name=value["displayName"],
            cad_type=value["cadType"],
            value_type=value["valueType"],
            observable=value["observable"],
            writable=value["writable"],
            current_value=current_value,
            identity_source=(
                IdentitySource.from_mapping(identity)
                if isinstance(identity, Mapping)
                else None
            ),
            stability_class=value.get("stabilityClass", ""),
            annotations=Annotations.from_mapping(value["annotations"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "ownerKind": self.owner_kind,
            "ownerId": self.owner_id,
            "componentId": self.component_id,
            "key": self.key,
            "displayName": self.display_name,
            "cadType": self.cad_type,
            "valueType": self.value_type,
            "observable": self.observable,
            "writable": self.writable,
        }
        if self.current_value is not _UNSET:
            result["currentValue"] = self.current_value
        if self.identity_source is not None:
            result["identitySource"] = self.identity_source.to_mapping()
        if self.stability_class:
            result["stabilityClass"] = self.stability_class
        result["annotations"] = self.annotations.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class StructureNode:
    component_id: str
    parent_component_id: str = ""
    children: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StructureNode:
        return cls(
            component_id=value["componentId"],
            parent_component_id=value["parentComponentId"],
            children=tuple(value["children"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "componentId": self.component_id,
            "parentComponentId": self.parent_component_id,
            "children": list(self.children),
        }


@dataclass(frozen=True, slots=True)
class Structure:
    root_component_id: str
    nodes: tuple[StructureNode, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Structure:
        return cls(
            root_component_id=value["rootComponentId"],
            nodes=tuple(StructureNode.from_mapping(node) for node in value["nodes"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "rootComponentId": self.root_component_id,
            "nodes": [node.to_mapping() for node in self.nodes],
        }


@dataclass(frozen=True, slots=True)
class Entities:
    components: tuple[Component, ...] = ()
    features: tuple[Feature, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    parameter_groups: tuple[ParameterGroup, ...] = ()
    parameters: tuple[Parameter, ...] = ()
    metadata: tuple[Metadata, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Entities:
        return cls(
            components=tuple(
                Component.from_mapping(item) for item in value["components"]
            ),
            features=tuple(Feature.from_mapping(item) for item in value["features"]),
            relationships=tuple(
                Relationship.from_mapping(item) for item in value["relationships"]
            ),
            parameter_groups=tuple(
                ParameterGroup.from_mapping(item) for item in value["parameterGroups"]
            ),
            parameters=tuple(
                Parameter.from_mapping(item) for item in value["parameters"]
            ),
            metadata=tuple(Metadata.from_mapping(item) for item in value["metadata"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "components": [component.to_mapping() for component in self.components],
            "features": [feature.to_mapping() for feature in self.features],
            "relationships": [
                relationship.to_mapping() for relationship in self.relationships
            ],
            "parameterGroups": [group.to_mapping() for group in self.parameter_groups],
            "parameters": [parameter.to_mapping() for parameter in self.parameters],
            "metadata": [entry.to_mapping() for entry in self.metadata],
        }


@dataclass(frozen=True, slots=True)
class CaptureDocument:
    schema_version: str
    capture_id: str
    adapter: NamedVersion
    cad_system: NamedVersion
    source_document: SourceDocument
    root_product: RootProduct
    annotations: Annotations
    entities: Entities
    structure: Structure

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> CaptureDocument:
        validate_capture_document(value)
        return cls(
            schema_version=value["schemaVersion"],
            capture_id=value["captureId"],
            adapter=NamedVersion.from_mapping(value["adapter"]),
            cad_system=NamedVersion.from_mapping(value["cadSystem"]),
            source_document=SourceDocument.from_mapping(value["sourceDocument"]),
            root_product=RootProduct.from_mapping(value["rootProduct"]),
            annotations=Annotations.from_mapping(value["annotations"]),
            entities=Entities.from_mapping(value["entities"]),
            structure=Structure.from_mapping(value["structure"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "captureId": self.capture_id,
            "adapter": self.adapter.to_mapping(),
            "cadSystem": self.cad_system.to_mapping(),
            "sourceDocument": self.source_document.to_mapping(),
            "rootProduct": self.root_product.to_mapping(),
            "annotations": self.annotations.to_mapping(),
            "entities": self.entities.to_mapping(),
            "structure": self.structure.to_mapping(),
        }

    def validate(self) -> None:
        """Validate this record against the capture contract and policy."""

        validate_capture_document(self.to_mapping())


__all__ = [
    "Annotations",
    "CaptureDocument",
    "Component",
    "Entities",
    "Feature",
    "IdentitySource",
    "Metadata",
    "NamedVersion",
    "Parameter",
    "ParameterGroup",
    "Relationship",
    "RootProduct",
    "SourceDocument",
    "SourceFile",
    "Structure",
    "StructureNode",
    "Targetability",
]
