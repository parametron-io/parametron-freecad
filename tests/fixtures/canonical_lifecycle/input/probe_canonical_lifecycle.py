#!/usr/bin/env python3
"""Read-only probe for the canonical lifecycle cube FreeCAD fixture.

Run under FreeCAD's Python environment with source and output --pass arguments.

The script does not intentionally mutate or save the document.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import FreeCAD as App

EXPECTED_OBJECTS = [
    "Body",
    "Sketch",
    "Pad",
    "Sketch001",
    "Pocket",
    "Chamfer",
    "TargetObject",
    "TargetBody",
    "Unsuppress_Feature",
    "Suppress_Feature",
    "UnhideFeature",
    "SafeDeleteObject",
    "HideObject",
]

EXPECTED_PARAMETERS = [
    "boxLength",
    "boxWidth",
    "boxHeight",
    "holeDia",
    "boxChamfer",
]


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def native_names(values):
    out = []
    for value in values:
        name = getattr(value, "Name", None)
        out.append(name if name is not None else repr(value))
    return sorted(out)


def property_snapshot(obj, name):
    if name not in getattr(obj, "PropertiesList", []):
        return None
    try:
        return {
            "type": obj.getTypeIdOfProperty(name),
            "group": obj.getGroupOfProperty(name),
            "editorMode": obj.getEditorMode(name),
            "value": getattr(obj, name),
        }
    except Exception as exc:
        return {"error": str(exc)}


def object_snapshot(obj):
    result = {
        "name": obj.Name,
        "label": obj.Label,
        "typeId": obj.TypeId,
        "propertiesList": sorted(obj.PropertiesList),
        "visibility": property_snapshot(obj, "Visibility"),
        "suppressed": property_snapshot(obj, "Suppressed"),
        "inList": native_names(getattr(obj, "InList", [])),
        "outList": native_names(getattr(obj, "OutList", [])),
    }

    if hasattr(obj, "Tip"):
        tip = obj.Tip
        result["tip"] = getattr(tip, "Name", None)

    if hasattr(obj, "Shape"):
        try:
            result["shapeNull"] = obj.Shape.isNull()
        except Exception as exc:
            result["shapeNullError"] = str(exc)

    return result


def exact_object_snapshot(doc, name):
    obj = doc.getObject(name)
    if obj is None:
        return {"exists": False}
    return {"exists": True, **object_snapshot(obj)}


def find_varset(doc):
    exact = doc.getObject("VarSet")
    if exact is not None:
        return exact

    matches = [obj for obj in doc.Objects if obj.TypeId == "App::VarSet"]
    if len(matches) == 1:
        return matches[0]
    return None


PASS_PREFIX = "--pass="


def _arguments():
    values = [
        argument[len(PASS_PREFIX) :]
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 2:
        raise RuntimeError("probe requires source and output --pass arguments")
    return values[0], values[1]


def main():
    path, output_path = _arguments()
    before_hash = sha256_file(path)
    doc = App.openDocument(path)

    try:
        varset = find_varset(doc)
        varset_result = None
        if varset is not None:
            varset_result = {
                "name": varset.Name,
                "label": varset.Label,
                "typeId": varset.TypeId,
                "parameters": {
                    name: property_snapshot(varset, name)
                    for name in EXPECTED_PARAMETERS
                },
            }

        result = {
            "source": {
                "path": path,
                "sha256BeforeOpen": before_hash,
            },
            "document": {
                "name": doc.Name,
                "label": doc.Label,
            },
            "varSet": varset_result,
            "objects": {name: exact_object_snapshot(doc, name) for name in EXPECTED_OBJECTS},
            "inventory": [
                object_snapshot(obj) for obj in sorted(doc.Objects, key=lambda obj: obj.Name)
            ],
        }
    finally:
        App.closeDocument(doc.Name)

    result["source"]["sha256AfterClose"] = sha256_file(path)
    result["source"]["unchanged"] = (
        result["source"]["sha256BeforeOpen"] == result["source"]["sha256AfterClose"]
    )

    Path(output_path).write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


main()
