"""Fake FreeCAD document/object support for capture discovery tests.

These fakes implement only the read-only native interfaces used by
``parametron_freecad.capture.discovery``. They do not import FreeCAD.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TYPE_BASES: dict[str, set[str]] = {
    "App::Document": {"App::Document"},
    "App::Part": {"App::Part"},
    "Assembly::AssemblyObject": {"Assembly::AssemblyObject"},
    "PartDesign::Body": {"PartDesign::Body", "Part::Feature"},
    "PartDesign::Feature": {"PartDesign::Feature", "Part::Feature"},
    "PartDesign::Pad": {"PartDesign::Pad", "PartDesign::Feature", "Part::Feature"},
    "PartDesign::Pocket": {
        "PartDesign::Pocket",
        "PartDesign::Feature",
        "Part::Feature",
    },
    "PartDesign::Chamfer": {
        "PartDesign::Chamfer",
        "PartDesign::Feature",
        "Part::Feature",
    },
    "Sketcher::SketchObject": {"Sketcher::SketchObject", "Part::Feature"},
    "Part::Box": {"Part::Box", "Part::Feature"},
    "Part::FeaturePython": {"Part::FeaturePython", "Part::Feature"},
    "App::VarSet": {"App::VarSet"},
    "App::Origin": {"App::Origin"},
    "App::Line": {"App::Line", "App::DatumFeature"},
    "App::Plane": {"App::Plane", "App::DatumFeature"},
    "App::Point": {"App::Point", "App::DatumFeature"},
    "App::Link": {"App::Link"},
    "Assembly::AssemblyLink": {"Assembly::AssemblyLink"},
    "Assembly::JointGroup": {"Assembly::JointGroup"},
    "Assembly::Joint": {"Assembly::Joint"},
    "App::DocumentObjectGroup": {"App::DocumentObjectGroup"},
    "Spreadsheet::Sheet": {"Spreadsheet::Sheet"},
    "App::FeaturePython": {"App::FeaturePython"},
    "TechDraw::DrawPage": {"TechDraw::DrawPage"},
    "TechDraw::DrawViewPart": {
        "TechDraw::DrawViewPart",
        "TechDraw::DrawView",
    },
    "TechDraw::DrawProjGroup": {
        "TechDraw::DrawProjGroup",
        "TechDraw::DrawView",
    },
    "TechDraw::DrawProjGroupItem": {
        "TechDraw::DrawProjGroupItem",
        "TechDraw::DrawViewPart",
        "TechDraw::DrawView",
    },
    "TechDraw::DrawViewClip": {
        "TechDraw::DrawViewClip",
        "TechDraw::DrawView",
    },
    "TechDraw::DrawViewAnnotation": {
        "TechDraw::DrawViewAnnotation",
        "TechDraw::DrawView",
    },
    "TechDraw::DrawViewSymbol": {
        "TechDraw::DrawViewSymbol",
        "TechDraw::DrawView",
    },
    "TechDraw::DrawSVGTemplate": {"TechDraw::DrawSVGTemplate"},
}


class FakeUnit:
    """Minimal native Quantity Unit evidence."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def __str__(self) -> str:
        return f"Unit: {self.symbol} (1,0,0,0,0,0,0,0) [Length]"


class FakeQuantity:
    """Minimal native Quantity value evidence."""

    def __init__(self, value: float, unit: str = "mm") -> None:
        self.Value = value
        self.Unit = FakeUnit(unit)


@dataclass(frozen=True, slots=True)
class FakeProperty:
    """One fake native property descriptor."""

    type_id: str | None
    group: str = ""
    status: tuple[str | int, ...] = ()
    value: Any = None
    readable: bool = True
    status_available: bool = True
    group_available: bool = True
    type_available: bool = True


def property_string(
    value: str = "",
    *,
    group: str = "",
    status: tuple[str | int, ...] = (21,),
    readable: bool = True,
    status_available: bool = True,
    group_available: bool = True,
    type_available: bool = True,
) -> FakeProperty:
    return FakeProperty(
        "App::PropertyString",
        group=group,
        status=status,
        value=value,
        readable=readable,
        status_available=status_available,
        group_available=group_available,
        type_available=type_available,
    )


def property_bool(
    value: bool = False,
    *,
    group: str = "",
    status: tuple[str | int, ...] = (21,),
    readable: bool = True,
    status_available: bool = True,
    group_available: bool = True,
    type_available: bool = True,
) -> FakeProperty:
    return FakeProperty(
        "App::PropertyBool",
        group=group,
        status=status,
        value=value,
        readable=readable,
        status_available=status_available,
        group_available=group_available,
        type_available=type_available,
    )


def property_float(
    value: float = 0.0,
    *,
    group: str = "",
    status: tuple[str | int, ...] = (21,),
    readable: bool = True,
    status_available: bool = True,
    group_available: bool = True,
    type_available: bool = True,
) -> FakeProperty:
    return FakeProperty(
        "App::PropertyFloat",
        group=group,
        status=status,
        value=value,
        readable=readable,
        status_available=status_available,
        group_available=group_available,
        type_available=type_available,
    )


def property_integer(
    value: int = 0,
    *,
    group: str = "",
    status: tuple[str | int, ...] = (21,),
    readable: bool = True,
    status_available: bool = True,
    group_available: bool = True,
    type_available: bool = True,
) -> FakeProperty:
    return FakeProperty(
        "App::PropertyInteger",
        group=group,
        status=status,
        value=value,
        readable=readable,
        status_available=status_available,
        group_available=group_available,
        type_available=type_available,
    )


def property_length(
    value: float,
    unit: str = "mm",
    *,
    group: str = "",
    status: tuple[str | int, ...] = (21,),
    readable: bool = True,
    status_available: bool = True,
    group_available: bool = True,
    type_available: bool = True,
) -> FakeProperty:
    return FakeProperty(
        "App::PropertyLength",
        group=group,
        status=status,
        value=FakeQuantity(value, unit),
        readable=readable,
        status_available=status_available,
        group_available=group_available,
        type_available=type_available,
    )


class FakeObject:
    """Minimal read-only native DocumentObject fake."""

    def __init__(
        self,
        name: str,
        type_id: str,
        *,
        label: str | None = None,
        properties: dict[str, FakeProperty] | None = None,
        group: list[Any] | None = None,
        in_list: list[Any] | None = None,
        out_list: list[Any] | None = None,
        include_properties: bool = True,
        include_group: bool = True,
        include_relationships: bool = True,
    ) -> None:
        self.Name = name
        self.Label = label if label is not None else name
        self.TypeId = type_id
        self._properties = dict(properties or {})
        if include_properties:
            self.PropertiesList = list(self._properties)
        if include_group:
            self.Group = list(group or [])
        if include_relationships:
            self.InList = list(in_list or [])
            self.OutList = list(out_list or [])

    def isDerivedFrom(self, type_id: str) -> bool:
        return type_id in TYPE_BASES.get(self.TypeId, {self.TypeId})

    def getTypeIdOfProperty(self, name: str) -> str:
        descriptor = self._properties.get(name)
        if descriptor is None or not descriptor.type_available:
            raise AttributeError(name)
        assert descriptor.type_id is not None
        return descriptor.type_id

    def getGroupOfProperty(self, name: str) -> str:
        descriptor = self._properties.get(name)
        if descriptor is None or not descriptor.group_available:
            raise AttributeError(name)
        return descriptor.group

    def getPropertyStatus(self, name: str) -> tuple[str | int, ...]:
        descriptor = self._properties.get(name)
        if descriptor is None or not descriptor.status_available:
            raise AttributeError(name)
        return descriptor.status

    def __getattr__(self, name: str) -> Any:
        properties = self.__dict__.get("_properties", {})
        descriptor = properties.get(name)
        if descriptor is None or not descriptor.readable:
            raise AttributeError(name)
        return descriptor.value


class FakeDocument:
    """Minimal read-only native App::Document fake."""

    def __init__(
        self,
        name: str = "capture_document",
        *,
        label: str | None = None,
        objects: list[Any] | None = None,
        properties: dict[str, FakeProperty] | None = None,
        include_objects: bool = True,
        include_properties: bool = True,
    ) -> None:
        self.Name = name
        self.Label = label if label is not None else name
        self.TypeId = "App::Document"
        self._properties = dict(properties or {})
        if include_properties:
            self.PropertiesList = list(self._properties)
        if include_objects:
            self.Objects = list(objects or [])
        for value in self.Objects if include_objects else ():
            try:
                value.Document = self
            except Exception:
                continue

    def isDerivedFrom(self, type_id: str) -> bool:
        return type_id == "App::Document"

    def getTypeIdOfProperty(self, name: str) -> str:
        descriptor = self._properties.get(name)
        if descriptor is None or not descriptor.type_available:
            raise AttributeError(name)
        assert descriptor.type_id is not None
        return descriptor.type_id

    def getGroupOfProperty(self, name: str) -> str:
        descriptor = self._properties.get(name)
        if descriptor is None or not descriptor.group_available:
            raise AttributeError(name)
        return descriptor.group

    def getPropertyStatus(self, name: str) -> tuple[str | int, ...]:
        descriptor = self._properties.get(name)
        if descriptor is None or not descriptor.status_available:
            raise AttributeError(name)
        return descriptor.status

    def __getattr__(self, name: str) -> Any:
        properties = self.__dict__.get("_properties", {})
        descriptor = properties.get(name)
        if descriptor is None or not descriptor.readable:
            raise AttributeError(name)
        return descriptor.value


def visibility_property(value: bool = True) -> FakeProperty:
    return FakeProperty(
        "App::PropertyBool",
        status=("Hidden", "Output", "NoModify"),
        value=value,
    )


def suppressed_property(value: bool = False) -> FakeProperty:
    return FakeProperty("App::PropertyBool", status=(), value=value)


def body(
    name: str,
    *,
    properties: dict[str, FakeProperty] | None = None,
    group: list[Any] | None = None,
    in_list: list[Any] | None = None,
    out_list: list[Any] | None = None,
) -> FakeObject:
    values = {
        "Visibility": visibility_property(),
        "Shape": FakeProperty("Part::PropertyPartShape"),
        **(properties or {}),
    }
    return FakeObject(
        name,
        "PartDesign::Body",
        properties=values,
        group=group,
        in_list=in_list,
        out_list=out_list,
    )


def sketch(
    name: str,
    *,
    properties: dict[str, FakeProperty] | None = None,
    in_list: list[Any] | None = None,
    out_list: list[Any] | None = None,
) -> FakeObject:
    values = {"Visibility": visibility_property(), **(properties or {})}
    return FakeObject(
        name,
        "Sketcher::SketchObject",
        properties=values,
        in_list=in_list,
        out_list=out_list,
    )


def pad(
    name: str,
    *,
    properties: dict[str, FakeProperty] | None = None,
    in_list: list[Any] | None = None,
    out_list: list[Any] | None = None,
) -> FakeObject:
    values = {
        "Visibility": visibility_property(),
        "Suppressed": suppressed_property(),
        **(properties or {}),
    }
    return FakeObject(
        name,
        "PartDesign::Pad",
        properties=values,
        in_list=in_list,
        out_list=out_list,
    )


def var_set(
    name: str,
    *,
    properties: dict[str, FakeProperty] | None = None,
) -> FakeObject:
    values = {
        "ExpressionEngine": FakeProperty("App::PropertyExpressionEngine"),
        "Label": property_string(name, group="Base", status=(27,)),
        "Label2": property_string("", group="Base", status=("Output", 26)),
        "Visibility": visibility_property(),
        **(properties or {}),
    }
    return FakeObject(name, "App::VarSet", properties=values)


def app_part(
    name: str,
    *,
    group: list[Any] | None = None,
    properties: dict[str, FakeProperty] | None = None,
) -> FakeObject:
    return FakeObject(
        name,
        "App::Part",
        properties={"Visibility": visibility_property(), **(properties or {})},
        group=group,
    )


def assembly_object(
    name: str,
    *,
    group: list[Any] | None = None,
    properties: dict[str, FakeProperty] | None = None,
) -> FakeObject:
    return FakeObject(
        name,
        "Assembly::AssemblyObject",
        properties={"Visibility": visibility_property(), **(properties or {})},
        group=group,
    )


def part_box(
    name: str,
    *,
    properties: dict[str, FakeProperty] | None = None,
    in_list: list[Any] | None = None,
    out_list: list[Any] | None = None,
) -> FakeObject:
    return FakeObject(
        name,
        "Part::Box",
        properties={"Visibility": visibility_property(), **(properties or {})},
        in_list=in_list,
        out_list=out_list,
    )


def link_list(value: list[Any] | None = None) -> FakeProperty:
    return FakeProperty(
        "App::PropertyLinkList",
        status=(21,),
        value=list(value or []),
    )


def drawing_page(
    name: str,
    *,
    label: str | None = None,
    views: list[Any] | None = None,
    properties: dict[str, FakeProperty] | None = None,
) -> FakeObject:
    return FakeObject(
        name,
        "TechDraw::DrawPage",
        label=label,
        properties={"Views": link_list(views), **(properties or {})},
    )


def drawing_view(
    name: str,
    *,
    label: str | None = None,
    source: list[Any] | None = None,
    x_source: list[Any] | None = None,
    views: list[Any] | None = None,
    properties: dict[str, FakeProperty] | None = None,
) -> FakeObject:
    values = {
        "Source": link_list(source),
        "XSource": link_list(x_source),
        **(properties or {}),
    }
    if views is not None:
        values["Views"] = link_list(views)
    return FakeObject(
        name,
        "TechDraw::DrawViewPart",
        label=label,
        properties=values,
    )


def projection_group(
    name: str,
    *,
    label: str | None = None,
    source: list[Any] | None = None,
    x_source: list[Any] | None = None,
    views: list[Any] | None = None,
) -> FakeObject:
    return FakeObject(
        name,
        "TechDraw::DrawProjGroup",
        label=label,
        properties={
            "Source": link_list(source),
            "XSource": link_list(x_source),
            "Views": link_list(views),
        },
    )


def projection_item(
    name: str,
    *,
    label: str | None = None,
    source: list[Any] | None = None,
    x_source: list[Any] | None = None,
) -> FakeObject:
    return FakeObject(
        name,
        "TechDraw::DrawProjGroupItem",
        label=label,
        properties={
            "Source": link_list(source),
            "XSource": link_list(x_source),
        },
    )


def drawing_annotation(name: str, *, label: str | None = None) -> FakeObject:
    return FakeObject(name, "TechDraw::DrawViewAnnotation", label=label)


def drawing_symbol(name: str, *, label: str | None = None) -> FakeObject:
    return FakeObject(name, "TechDraw::DrawViewSymbol", label=label)


def drawing_view_clip(
    name: str,
    *,
    views: list[Any] | None = None,
) -> FakeObject:
    return FakeObject(
        name,
        "TechDraw::DrawViewClip",
        properties={"Views": link_list(views)},
    )
