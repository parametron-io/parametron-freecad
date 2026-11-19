"""Bounded native FreeCAD access for occurrence inspection.

This module performs read-only access to already-opened documents. It never
opens, mutates, saves, or recursively discovers native documents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

NATIVE_TYPE_APP_LINK = "App::Link"
NATIVE_TYPE_APP_LINK_ELEMENT = "App::LinkElement"
NATIVE_TYPE_APP_PART = "App::Part"
NATIVE_TYPE_ASSEMBLY_OBJECT = "Assembly::AssemblyObject"
NATIVE_TYPE_ASSEMBLY_LINK = "Assembly::AssemblyLink"
NATIVE_TYPE_JOINT_GROUP = "Assembly::JointGroup"
NATIVE_TYPE_PART_FEATURE = "Part::Feature"
NATIVE_TYPE_PARTDESIGN_BODY = "PartDesign::Body"

SUPPORTED_OCCURRENCE_TARGET_TYPES = frozenset(
    {
        NATIVE_TYPE_PARTDESIGN_BODY,
        NATIVE_TYPE_PART_FEATURE,
        NATIVE_TYPE_APP_PART,
    }
)


class OccurrenceNativeAccessError(ValueError):
    """Raised when native occurrence state cannot be represented safely."""


def native_type_id(native_object: Any) -> str:
    """Return one stable native type identity."""
    value = getattr(native_object, "TypeId", None)
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or "\x00" in value
    ):
        raise OccurrenceNativeAccessError("native object has no stable type identity")
    return value


def native_object_name(native_object: Any) -> str:
    """Return one stable native object name."""
    value = getattr(native_object, "Name", None)
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or "\x00" in value
    ):
        raise OccurrenceNativeAccessError("native object has no stable object identity")
    return value


def find_native_object(document: Any, name: str) -> Any | None:
    """Return one native object by exact name without creating it."""
    get_object = getattr(document, "getObject", None)
    if not callable(get_object):
        raise OccurrenceNativeAccessError(
            "native document does not provide object lookup"
        )
    try:
        return get_object(name)
    except Exception as exc:
        raise OccurrenceNativeAccessError(
            "native document object lookup failed"
        ) from exc


def native_group_members(parent: Any) -> tuple[Any, ...]:
    """Return the complete native Group inventory, rejecting dangling entries."""
    group = getattr(parent, "Group", None)
    if group is None:
        raise OccurrenceNativeAccessError("native assembly has no Group inventory")
    try:
        members = tuple(group)
    except TypeError as exc:
        raise OccurrenceNativeAccessError(
            "native assembly Group is not iterable"
        ) from exc
    for member in members:
        if member is None:
            raise OccurrenceNativeAccessError("native Group contains a dangling member")
    return members


def require_membership_corroborated(parent: Any, member: Any) -> None:
    """Require the Group entry and the member's InList to agree exactly."""
    group = getattr(parent, "Group", None)
    in_list = getattr(member, "InList", None)
    if group is None or in_list is None:
        raise OccurrenceNativeAccessError(
            "native Group membership cannot be corroborated"
        )
    try:
        listed_in_group = any(candidate is member for candidate in group)
        identifies_parent = any(candidate is parent for candidate in in_list)
    except TypeError as exc:
        raise OccurrenceNativeAccessError(
            "native Group membership is not iterable"
        ) from exc
    if not listed_in_group or not identifies_parent:
        raise OccurrenceNativeAccessError(
            "native Group entry does not corroborate parent membership"
        )


def native_element_count(member: Any) -> int | None:
    """Return the native ElementCount when the object exposes one."""
    value = getattr(member, "ElementCount", None)
    if value is None:
        return None
    if isinstance(value, bool):
        raise OccurrenceNativeAccessError("native ElementCount is not an integer")
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise OccurrenceNativeAccessError(
            "native ElementCount is not an integer"
        ) from exc
    if count < 0:
        raise OccurrenceNativeAccessError("native ElementCount must not be negative")
    return count


def native_linked_object(member: Any) -> Any | None:
    """Return the native link target, including placeholder objects."""
    try:
        return getattr(member, "LinkedObject", None)
    except Exception:
        return None


def native_document_file_name(native_object: Any) -> str | Path | None:
    """Return the native document file name without resolving it."""
    document = getattr(native_object, "Document", None)
    if document is None:
        return None
    file_name = getattr(document, "FileName", None)
    if isinstance(file_name, (str, Path)) and str(file_name):
        return file_name
    return None


def native_object_exists(document: Any, name: str) -> bool:
    """Require the named object to exist in the actual native document."""
    if document is None:
        return False
    get_object = getattr(document, "getObject", None)
    if not callable(get_object):
        return False
    try:
        candidate = get_object(name)
    except Exception:
        return False
    return candidate is not None and getattr(candidate, "Name", None) == name


def native_group_contents(member: Any) -> tuple[str, ...] | None:
    """Return an auxiliary member's child inventory when fully inspectable."""
    group = getattr(member, "Group", None)
    if group is None:
        return None
    try:
        children: Iterable[Any] = tuple(group)
    except TypeError:
        return None
    names: list[str] = []
    for child in children:
        if child is None:
            return None
        name = getattr(child, "Name", None)
        if not isinstance(name, str) or not name:
            return None
        names.append(name)
    return tuple(names)


__all__ = [
    "NATIVE_TYPE_APP_LINK",
    "NATIVE_TYPE_APP_LINK_ELEMENT",
    "NATIVE_TYPE_APP_PART",
    "NATIVE_TYPE_ASSEMBLY_LINK",
    "NATIVE_TYPE_ASSEMBLY_OBJECT",
    "NATIVE_TYPE_JOINT_GROUP",
    "NATIVE_TYPE_PARTDESIGN_BODY",
    "NATIVE_TYPE_PART_FEATURE",
    "SUPPORTED_OCCURRENCE_TARGET_TYPES",
    "OccurrenceNativeAccessError",
    "find_native_object",
    "native_document_file_name",
    "native_element_count",
    "native_group_contents",
    "native_group_members",
    "native_linked_object",
    "native_object_exists",
    "native_object_name",
    "native_type_id",
    "require_membership_corroborated",
]
