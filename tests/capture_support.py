"""Shared valid capture payloads for GUI-free capture tests."""

from __future__ import annotations

from typing import Any


def empty_annotations() -> dict[str, str]:
    return {"description": "", "comment": "", "purpose": ""}


def targetability(
    *,
    suppress: bool = False,
    unsuppress: bool = False,
    hide: bool = False,
    unhide: bool = False,
    delete: bool = False,
) -> dict[str, bool]:
    return {
        "suppress": suppress,
        "unsuppress": unsuppress,
        "hide": hide,
        "unhide": unhide,
        "delete": delete,
    }


def valid_mapping() -> dict[str, Any]:
    """Return one minimal complete schema 1.0 capture draft.

    The semantic names are user-authored. Two identifiers are explicit
    advanced overrides (``cmp.root`` and ``cmp.part``) rather than generated
    names, matching the fixtures' use of overrides.
    """

    return {
        "schemaVersion": "1.0",
        "captureId": "cap.freecad.capture-core.v1",
        "adapter": {"name": "freecad", "version": ""},
        "cadSystem": {"name": "FreeCAD", "version": "1.1.4"},
        "sourceDocument": {
            "logicalId": "capture_core_model",
            "path": "input/capture-core.FCStd",
            "fingerprint": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        },
        "rootProduct": {"id": "cmp.root"},
        "annotations": {
            "description": "Capture core test document.",
            "comment": "",
            "purpose": "",
        },
        "entities": {
            "components": [
                {
                    "id": "cmp.root",
                    "kind": "assembly",
                    "name": "rootAssembly",
                    "displayName": "Root Assembly",
                    "cadType": "App::Document",
                    "quantity": 1,
                    "material": "",
                    "identitySource": {
                        "kind": "parent_scoped_path",
                        "path": "cmp.root",
                        "nativeRef": "CaptureCore",
                    },
                    "stabilityClass": "stable",
                    "targetability": targetability(),
                    "annotations": empty_annotations(),
                },
                {
                    "id": "cmp.part",
                    "kind": "part",
                    "name": "Enclosure",
                    "displayName": "Enclosure",
                    "cadType": "PartDesign::Body",
                    "quantity": 1,
                    "material": "PLA",
                    "identitySource": {
                        "kind": "parent_scoped_path",
                        "path": "cmp.root/Body",
                        "nativeRef": "Body",
                    },
                    "stabilityClass": "stable",
                    "targetability": targetability(hide=True, unhide=True),
                    "annotations": empty_annotations(),
                },
            ],
            "features": [
                {
                    "id": "fea.enclosure.pad",
                    "componentId": "cmp.part",
                    "name": "Pad",
                    "displayName": "Pad",
                    "cadType": "PartDesign::Pad",
                    "identitySource": {
                        "kind": "owner_scoped_key",
                        "ownerScopedKey": "Pad",
                        "nativeRef": "Pad",
                    },
                    "stabilityClass": "conditionally_stable",
                    "targetability": targetability(suppress=True, unsuppress=True),
                    "annotations": empty_annotations(),
                }
            ],
            "relationships": [
                {
                    "id": "rel.root.mount",
                    "kind": "relationship",
                    "componentId": "cmp.root",
                    "name": "mount",
                    "cadType": "App::FeaturePython",
                    "endpoints": ["cmp.part", "fea.enclosure.pad"],
                    "stabilityClass": "stable",
                    "targetability": targetability(),
                    "annotations": empty_annotations(),
                }
            ],
            "parameterGroups": [
                {
                    "id": "grp.root.parameters",
                    "ownerComponentId": "cmp.root",
                    "name": "Parameters",
                    "displayName": "Parameters",
                    "groupKind": "varset",
                    "cadType": "App::VarSet",
                    "observable": True,
                    "writable": True,
                    "identitySource": {
                        "kind": "owner_scoped_key",
                        "ownerScopedKey": "Parameters",
                        "nativeRef": "Parameters",
                    },
                    "stabilityClass": "stable",
                    "annotations": empty_annotations(),
                }
            ],
            "parameters": [
                {
                    "id": "par.root.parameters.length",
                    "ownerKind": "group",
                    "ownerId": "grp.root.parameters",
                    "componentId": "cmp.root",
                    "name": "length",
                    "displayName": "Length",
                    "cadType": "App::PropertyFloat",
                    "valueType": "number",
                    "observable": True,
                    "writable": True,
                    "currentValue": 10.0,
                    "unit": "mm",
                    "identitySource": {
                        "kind": "owner_scoped_key",
                        "ownerScopedKey": "length",
                        "groupScopedKey": "length",
                        "nativeRef": "Parameters.length",
                    },
                    "stabilityClass": "conditionally_stable",
                    "annotations": empty_annotations(),
                }
            ],
            "metadata": [
                {
                    "id": "meta.part.material",
                    "ownerKind": "component",
                    "ownerId": "cmp.part",
                    "componentId": "cmp.part",
                    "key": "material",
                    "displayName": "Material",
                    "cadType": "App::PropertyString",
                    "valueType": "string",
                    "observable": True,
                    "writable": True,
                    "currentValue": "PLA",
                    "stabilityClass": "stable",
                    "annotations": empty_annotations(),
                }
            ],
        },
        "structure": {
            "rootComponentId": "cmp.root",
            "nodes": [
                {
                    "componentId": "cmp.root",
                    "parentComponentId": "",
                    "children": ["cmp.part"],
                },
                {
                    "componentId": "cmp.part",
                    "parentComponentId": "cmp.root",
                    "children": [],
                },
            ],
        },
    }
