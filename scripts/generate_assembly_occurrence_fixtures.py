"""Generate the committed real-FreeCAD Assembly occurrence fixture bundle.

Run only through the repository Nix shell and FreeCAD host:

    nix develop --command freecadcmd \
      scripts/generate_assembly_occurrence_fixtures.py \
      --pass=/absolute/output/directory

The bundle intentionally omits ``resources/missing-component.FCStd`` so the
runtime can observe a missing external target without a placeholder shortcut.
The generated documents are semantically reproducible. FreeCAD's ``.FCStd``
archive bytes are not expected to be identical across regeneration runs.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import FreeCAD as App

EXPECTED_FREECAD_VERSION = ("1", "1", "4")
PASS_PREFIX = "--pass="

SOURCE_DOCUMENT = "assembly-root.FCStd"
COMPONENT_A_COORDINATE = "resources/component-a.FCStd"
COMPONENT_B_COORDINATE = "resources/component-b.FCStd"
MISSING_COMPONENT_COORDINATE = "resources/missing-component.FCStd"
NESTED_ASSEMBLY_COORDINATE = "resources/nested-assembly.FCStd"

SUPPORTED_ASSEMBLY = "SupportedAssembly"
MIXED_ASSEMBLY = "Assembly"
SUPPORTED_LINK_NAMES = tuple(f"Link{index:02d}" for index in range(1, 11))


def _output_directory() -> Path:
    values = [
        argument[len(PASS_PREFIX) :]
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 1 or not values[0]:
        raise RuntimeError(
            "generator requires exactly one --pass=/absolute/output/directory"
        )
    output = Path(values[0])
    if not output.is_absolute():
        raise RuntimeError("fixture output directory must be absolute")
    return output


def _require_environment() -> None:
    if not os.environ.get("IN_NIX_SHELL"):
        raise RuntimeError("fixture generation must run inside nix develop")
    if tuple(App.Version()[:3]) != EXPECTED_FREECAD_VERSION:
        raise RuntimeError(
            "fixture generation requires FreeCAD "
            + ".".join(EXPECTED_FREECAD_VERSION)
            + "; observed "
            + ".".join(App.Version()[:3])
        )


def _close_all_documents() -> None:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)


def _save(document: App.Document) -> None:
    document.recompute()
    document.save()
    file_name = getattr(document, "FileName", None)
    if not file_name or not Path(file_name).is_file():
        raise RuntimeError(f"FreeCAD save produced no file for {document.Name!r}")


def _save_as(document: App.Document, path: Path) -> None:
    document.recompute()
    document.saveAs(str(path))
    if not path.is_file():
        raise RuntimeError(f"FreeCAD produced no file for {document.Name!r}")


def _new_document(name: str) -> App.Document:
    document = App.newDocument(name)
    if document is None:
        raise RuntimeError(f"FreeCAD did not create document {name!r}")
    return document


def _add(document: App.Document, type_id: str, name: str):
    native_object = document.addObject(type_id, name)
    if native_object is None:
        raise RuntimeError(f"FreeCAD did not create object {name!r}")
    native_object.Label = name
    return native_object


def _add_assembly(document: App.Document, name: str):
    assembly = _add(document, "Assembly::AssemblyObject", name)
    if assembly.TypeId != "Assembly::AssemblyObject":
        raise RuntimeError(f"unexpected assembly type for {name!r}")
    return assembly


def _add_link(assembly, name: str, target):
    link = assembly.newObject("App::Link", name)
    if link is None:
        raise RuntimeError(f"FreeCAD did not create link {name!r}")
    link.LinkedObject = target
    if link.ElementCount != 0:
        raise RuntimeError(f"unexpected ElementCount for link {name!r}")
    return link


def _generate(staging: Path) -> None:
    resources = staging / "resources"
    resources.mkdir(parents=True)

    component_a = _new_document("OccurrenceComponentA")
    body_a = _add(component_a, "PartDesign::Body", "Body")
    _save_as(component_a, staging / COMPONENT_A_COORDINATE)

    component_b = _new_document("OccurrenceComponentB")
    body_b = _add(component_b, "PartDesign::Body", "Body")
    part_b = _add(component_b, "App::Part", "Part")
    marker_b = _add(component_b, "App::FeaturePython", "Marker")
    _save_as(component_b, staging / COMPONENT_B_COORDINATE)

    missing_component = _new_document("OccurrenceMissingComponent")
    body_missing = _add(missing_component, "PartDesign::Body", "Body")
    _save_as(missing_component, staging / MISSING_COMPONENT_COORDINATE)

    nested_document = _new_document("OccurrenceNestedAssembly")
    nested_assembly = _add_assembly(nested_document, "NestedAssembly")
    _save_as(nested_document, staging / NESTED_ASSEMBLY_COORDINATE)

    root = _new_document("AssemblyOccurrenceRoot")
    supported_assembly = _add_assembly(root, SUPPORTED_ASSEMBLY)
    mixed_assembly = _add_assembly(root, MIXED_ASSEMBLY)
    root.saveAs(str(staging / SOURCE_DOCUMENT))

    for name in SUPPORTED_LINK_NAMES:
        _add_link(supported_assembly, name, body_a)

    for name in ("SharedSourceA", "SharedSourceB"):
        _add_link(mixed_assembly, name, body_a)
    _add_link(mixed_assembly, "CrossResourceBody", body_b)
    _add_link(mixed_assembly, "PartLink", part_b)
    _add_link(mixed_assembly, "MarkerLink", marker_b)
    _add_link(mixed_assembly, "MissingTarget", body_missing)

    nested_link = mixed_assembly.newObject(
        "Assembly::AssemblyLink",
        "NestedLink",
    )
    if nested_link is None:
        raise RuntimeError("FreeCAD did not create the nested assembly link")
    nested_link.LinkedObject = nested_assembly

    array_link = _add_link(mixed_assembly, "ArrayLink", body_a)
    array_link.ElementCount = 1
    if array_link.ElementCount != 1:
        raise RuntimeError("FreeCAD did not apply the LinkArray shape")

    joints = _add(root, "Assembly::JointGroup", "Joints")
    mixed_assembly.addObject(joints)
    if list(joints.Group):
        raise RuntimeError("generated empty joint group is not empty")

    internal_body = _add(root, "PartDesign::Body", "InternalBody")
    holder = _add(root, "App::FeaturePython", "Holder")
    holder.addProperty("App::PropertyLinkList", "References")
    holder.References = [internal_body]

    _save(root)
    _close_all_documents()

    for backup in staging.rglob("*.FCBak"):
        backup.unlink()
    # The missing component must never be committed: it proves native target
    # observation without relying on an in-memory placeholder object.
    (staging / MISSING_COMPONENT_COORDINATE).unlink(missing_ok=True)
    for backup in resources.glob("missing-component.*"):
        if backup.suffix == ".FCBak":
            backup.unlink(missing_ok=True)


def _require_group(assembly, expected: dict[str, str]) -> None:
    observed = {member.Name: member.TypeId for member in assembly.Group}
    if observed != expected:
        raise RuntimeError(
            f"generated Group mismatch for {assembly.Name!r}: {observed!r}"
        )


def _validate(staging: Path) -> None:
    _close_all_documents()
    root = App.openDocument(str(staging / SOURCE_DOCUMENT))
    if root is None:
        raise RuntimeError("FreeCAD failed to reopen the generated occurrence fixture")
    try:
        supported = root.getObject(SUPPORTED_ASSEMBLY)
        if supported is None or supported.TypeId != "Assembly::AssemblyObject":
            raise RuntimeError("generated fixture lacks the supported assembly")
        _require_group(
            supported,
            {name: "App::Link" for name in SUPPORTED_LINK_NAMES},
        )
        for member in supported.Group:
            if member.ElementCount != 0 or member.LinkedObject is None:
                raise RuntimeError(
                    f"supported occurrence {member.Name!r} is not a direct link"
                )

        mixed = root.getObject(MIXED_ASSEMBLY)
        if mixed is None or mixed.TypeId != "Assembly::AssemblyObject":
            raise RuntimeError("generated fixture lacks the mixed assembly")
        _require_group(
            mixed,
            {
                "SharedSourceA": "App::Link",
                "SharedSourceB": "App::Link",
                "CrossResourceBody": "App::Link",
                "PartLink": "App::Link",
                "MarkerLink": "App::Link",
                "MissingTarget": "App::Link",
                "NestedLink": "Assembly::AssemblyLink",
                "ArrayLink": "App::Link",
                "Joints": "Assembly::JointGroup",
            },
        )
        array_link = root.getObject("ArrayLink")
        if array_link is None or array_link.ElementCount != 1:
            raise RuntimeError("generated fixture lacks the LinkArray shape")
        joints = root.getObject("Joints")
        if joints is None or list(joints.Group):
            raise RuntimeError("generated fixture lacks an empty joint group")
        if mixed not in joints.InList:
            raise RuntimeError("generated joint group does not identify its parent")
        part_link = root.getObject("PartLink")
        if (
            part_link is None
            or part_link.LinkedObject is None
            or part_link.LinkedObject.TypeId != "App::Part"
        ):
            raise RuntimeError("generated fixture lacks an App::Part target")
        if (staging / MISSING_COMPONENT_COORDINATE).exists():
            raise RuntimeError("generated fixture must omit the missing component")
        holder = root.getObject("Holder")
        if holder is None or list(holder.References) == []:
            raise RuntimeError("generated fixture lacks the ordinary reference list")
        if holder in supported.Group or holder in mixed.Group:
            raise RuntimeError("ordinary reference holder must not be a Group member")
    finally:
        _close_all_documents()


def main() -> None:
    _require_environment()
    output = _output_directory()
    if output.exists():
        raise RuntimeError(f"fixture output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        _generate(staging)
        _validate(staging)
        staging.replace(output)
    except Exception:
        _close_all_documents()
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(
        json.dumps(
            {
                "freecadVersion": list(App.Version()[:3]),
                "output": str(output),
                "documents": [
                    SOURCE_DOCUMENT,
                    COMPONENT_A_COORDINATE,
                    COMPONENT_B_COORDINATE,
                    NESTED_ASSEMBLY_COORDINATE,
                ],
                "missingDocuments": [MISSING_COMPONENT_COORDINATE],
                "reproducibility": "semantic",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


main()
