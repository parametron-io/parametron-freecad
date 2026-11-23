"""Read-only duck-typed helpers for FreeCAD-native capture discovery.

The helpers operate on an already-open FreeCAD document object and its native
DocumentObjects. They never write properties, recompute, save, or change
geometry. FreeCAD itself is never imported here, so the module is safe under
ordinary Python and inside ``freecadcmd``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from parametron_freecad.capture.discovery_errors import (
    CaptureDiscoveryDocumentError,
    CaptureDiscoveryInspectionError,
)

# FreeCAD 1.1.4 reports these numeric status tokens for native read-only
# properties such as ``_ExternalGeoVersion``, ``FullyConstrained``, and
# ``_ElementMapVersion``. String tokens are preferred when present.
_READ_ONLY_STATUS_STRINGS = frozenset({"ReadOnly", "Immutable"})
_READ_ONLY_STATUS_NUMBERS = frozenset({24, 25})
_QUANTITY_UNIT_PREFIX = "Unit: "


@dataclass(frozen=True, slots=True)
class NativeValueEvidence:
    """Read-only evidence for one native property value."""

    readable: bool
    scalar: Any = None
    unit: str | None = None
    python_kind: str | None = None
    error: str | None = None


def require_document_name(document: Any) -> str:
    """Return the exact native document name or raise a document error."""

    name = getattr(document, "Name", None)
    if not isinstance(name, str) or name.strip() == "":
        raise CaptureDiscoveryDocumentError(
            "capture discovery requires a document with a nonblank native Name"
        )
    return name


def document_label(document: Any) -> str:
    """Return the native document Label, or an empty string when unavailable."""

    label = getattr(document, "Label", None)
    return label if isinstance(label, str) else ""


def require_native_objects(document: Any) -> tuple[Any, ...]:
    """Return native document objects in stable Name order.

    Objects must expose a nonblank string Name. Duplicate names are rejected
    because they cannot yield a deterministic native identity.
    """

    try:
        objects = document.Objects
    except AttributeError as exc:
        raise CaptureDiscoveryDocumentError(
            "document does not expose native Objects for capture discovery"
        ) from exc
    except Exception as exc:
        raise CaptureDiscoveryInspectionError(
            "document native Objects inspection failed"
        ) from exc

    try:
        iterator = iter(objects)
    except Exception as exc:
        raise CaptureDiscoveryDocumentError(
            "document native Objects is not iterable for capture discovery"
        ) from exc

    by_name: dict[str, Any] = {}
    for value in iterator:
        name = native_name_or_none(value)
        if name is None:
            raise CaptureDiscoveryDocumentError(
                "document native Objects contains an object without a nonblank "
                "string Name"
            )
        if name in by_name:
            raise CaptureDiscoveryDocumentError(
                f'document native Objects contains duplicate Name "{name}"'
            )
        by_name[name] = value

    return tuple(by_name[name] for name in sorted(by_name))


def native_name_or_none(value: Any) -> str | None:
    """Return a nonblank native Name, or None when the evidence is unusable."""

    name = getattr(value, "Name", None)
    if not isinstance(name, str) or name.strip() == "":
        return None
    return name


def require_native_name(value: Any, *, context: str) -> str:
    """Return a nonblank native Name or raise an inspection error."""

    name = native_name_or_none(value)
    if name is None:
        raise CaptureDiscoveryInspectionError(
            f"{context} does not expose a nonblank native Name"
        )
    return name


def native_label(value: Any) -> str:
    """Return a native Label string, or an empty string when unavailable."""

    label = getattr(value, "Label", None)
    return label if isinstance(label, str) else ""


def native_type_id(value: Any, *, native_ref: str) -> str:
    """Return the exact native TypeId or raise an inspection error."""

    type_id = getattr(value, "TypeId", None)
    if not isinstance(type_id, str) or type_id.strip() == "":
        raise CaptureDiscoveryInspectionError(
            f'native object "{native_ref}" does not expose a nonblank TypeId'
        )
    return type_id


def is_derived_from(value: Any, type_id: str) -> bool:
    """Return True when native type evidence proves the requested derivation."""

    if getattr(value, "TypeId", None) == type_id:
        return True
    predicate = getattr(value, "isDerivedFrom", None)
    if not callable(predicate):
        return False
    try:
        return predicate(type_id) is True
    except Exception:
        return False


def properties_list(value: Any) -> tuple[str, ...] | None:
    """Return sorted native property names, or None when unavailable."""

    try:
        properties = value.PropertiesList
    except AttributeError:
        return None
    except Exception:
        return None
    try:
        items = tuple(properties)
    except Exception:
        return None

    names: list[str] = []
    for item in items:
        if not isinstance(item, str) or item == "":
            return None
        names.append(item)
    return tuple(sorted(set(names)))


def property_type_id(value: Any, key: str) -> str | None:
    """Return the exact native property type, or None when unavailable."""

    inspector = getattr(value, "getTypeIdOfProperty", None)
    if not callable(inspector):
        return None
    try:
        type_id = inspector(key)
    except Exception:
        return None
    if not isinstance(type_id, str) or type_id.strip() == "":
        return None
    return type_id


def property_group(value: Any, key: str) -> str | None:
    """Return the native property group name, or None when unavailable."""

    inspector = getattr(value, "getGroupOfProperty", None)
    if not callable(inspector):
        return None
    try:
        group = inspector(key)
    except Exception:
        return None
    return group if isinstance(group, str) else None


def property_status(
    value: Any,
    key: str,
) -> tuple[tuple[str | int, ...], bool]:
    """Return normalized native property status tokens and availability."""

    inspector = getattr(value, "getPropertyStatus", None)
    if not callable(inspector):
        return (), False
    try:
        status = inspector(key)
    except Exception:
        return (), False

    if isinstance(status, str):
        return (status,), True
    try:
        items = tuple(status)
    except Exception:
        return (), False

    normalized: list[str | int] = []
    for item in items:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, int) and not isinstance(item, bool):
            normalized.append(item)
        else:
            return tuple(normalized), False
    return tuple(normalized), True


def is_read_only_status(status: tuple[str | int, ...]) -> bool:
    """Return True when native status evidence marks a property read-only."""

    for item in status:
        if isinstance(item, str) and item in _READ_ONLY_STATUS_STRINGS:
            return True
        if isinstance(item, int) and item in _READ_ONLY_STATUS_NUMBERS:
            return True
    return False


def has_property(value: Any, key: str, type_id: str) -> bool:
    """Return True when a property is present with the exact native TypeId."""

    names = properties_list(value)
    if names is None or key not in names:
        return False
    return property_type_id(value, key) == type_id


def bool_property_writable(value: Any, key: str) -> bool:
    """Return conservative native bool-property write capability.

    The property must exist as ``App::PropertyBool`` and native status evidence
    must be available and must not mark it read-only/immutable.
    """

    if not has_property(value, key, "App::PropertyBool"):
        return False
    status, available = property_status(value, key)
    if not available:
        return False
    return not is_read_only_status(status)


def read_native_value(value: Any, key: str) -> NativeValueEvidence:
    """Read one native property value without changing native state."""

    try:
        native_value = getattr(value, key)
    except AttributeError:
        return NativeValueEvidence(
            readable=False,
            error="unreadable_native_property",
        )
    except Exception:
        return NativeValueEvidence(
            readable=False,
            error="unreadable_native_property",
        )

    if isinstance(native_value, bool):
        return NativeValueEvidence(
            readable=True,
            scalar=native_value,
            python_kind="boolean",
        )
    if isinstance(native_value, str):
        return NativeValueEvidence(
            readable=True,
            scalar=native_value,
            python_kind="string",
        )
    if isinstance(native_value, int):
        return NativeValueEvidence(
            readable=True,
            scalar=native_value,
            python_kind="integer",
        )
    if isinstance(native_value, float):
        if not math.isfinite(native_value):
            return NativeValueEvidence(
                readable=True,
                python_kind="float",
                error="non_finite_numeric_value",
            )
        return NativeValueEvidence(
            readable=True,
            scalar=native_value,
            python_kind="float",
        )

    if hasattr(native_value, "Value") and hasattr(native_value, "Unit"):
        numeric_value = getattr(native_value, "Value", None)
        if (
            isinstance(numeric_value, bool)
            or not isinstance(numeric_value, (int, float))
            or not math.isfinite(numeric_value)
        ):
            return NativeValueEvidence(
                readable=True,
                python_kind="quantity",
                error="non_finite_numeric_value",
            )
        return NativeValueEvidence(
            readable=True,
            scalar=float(numeric_value),
            unit=quantity_unit_string(native_value),
            python_kind="quantity",
        )

    return NativeValueEvidence(
        readable=True,
        error="non_scalar_native_value",
    )


def quantity_unit_string(value: Any) -> str | None:
    """Return a deterministic unit token for a native Quantity value."""

    unit = getattr(value, "Unit", None)
    if unit is None:
        return None
    text = str(unit)
    if text.startswith(_QUANTITY_UNIT_PREFIX):
        text = text[len(_QUANTITY_UNIT_PREFIX) :]
    for marker in (" (", " ["):
        index = text.find(marker)
        if index >= 0:
            text = text[:index]
    text = text.strip()
    return text or None


def relationship_names(
    value: Any,
    attribute: str,
) -> tuple[tuple[str, ...], bool]:
    """Return sorted unique native relationship names and availability."""

    try:
        related = getattr(value, attribute)
    except AttributeError:
        return (), False
    except Exception:
        return (), False

    try:
        items = tuple(related)
    except Exception:
        return (), False

    names: list[str] = []
    available = True
    for item in items:
        linked = item[0] if isinstance(item, tuple) and item else item
        name = native_name_or_none(linked)
        if name is None:
            available = False
            continue
        names.append(name)
    return tuple(sorted(set(names))), available


def group_members(value: Any) -> tuple[tuple[Any, ...], bool]:
    """Return native Group members in stable Name order and availability."""

    try:
        members = value.Group
    except AttributeError:
        return (), False
    except Exception:
        return (), False

    try:
        items = tuple(members)
    except Exception:
        return (), False

    by_name: dict[str, Any] = {}
    available = True
    for item in items:
        linked = item[0] if isinstance(item, tuple) and item else item
        name = native_name_or_none(linked)
        if name is None:
            available = False
            continue
        by_name.setdefault(name, linked)
    return tuple(by_name[name] for name in sorted(by_name)), available


__all__ = [
    "NativeValueEvidence",
    "bool_property_writable",
    "document_label",
    "group_members",
    "has_property",
    "is_derived_from",
    "is_read_only_status",
    "native_label",
    "native_name_or_none",
    "native_type_id",
    "properties_list",
    "property_group",
    "property_status",
    "property_type_id",
    "quantity_unit_string",
    "read_native_value",
    "relationship_names",
    "require_document_name",
    "require_native_name",
    "require_native_objects",
]
