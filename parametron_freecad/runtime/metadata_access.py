"""Shared deterministic metadata owner and property access helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from parametron_freecad.execution.manifest_contract import (
    METADATA_VALUE_KIND_BOOLEAN,
    METADATA_VALUE_KIND_INTEGER,
    METADATA_VALUE_KIND_NUMBER,
    METADATA_VALUE_KIND_STRING,
)

METADATA_NATIVE_VALUE_KINDS = {
    "App::PropertyString": METADATA_VALUE_KIND_STRING,
    "App::PropertyBool": METADATA_VALUE_KIND_BOOLEAN,
    "App::PropertyFloat": METADATA_VALUE_KIND_NUMBER,
    "App::PropertyFloatConstraint": METADATA_VALUE_KIND_NUMBER,
    "App::PropertyInteger": METADATA_VALUE_KIND_INTEGER,
    "App::PropertyIntegerConstraint": METADATA_VALUE_KIND_INTEGER,
}


class MetadataAccessError(ValueError):
    """Base class for deterministic metadata access failures."""


class MetadataAccessDocumentError(MetadataAccessError):
    """Raised when a document cannot support metadata access."""


class MetadataAccessOwnerNotFoundError(MetadataAccessError):
    """Raised when getObject returns None for an exact owner id."""


class MetadataAccessPropertyNotFoundError(MetadataAccessError):
    """Raised when an exact metadata property does not exist on an owner."""


class MetadataAccessPropertyInspectionError(MetadataAccessError):
    """Raised when native property presence or type inspection cannot complete."""


class MetadataAccessPropertyReadError(MetadataAccessError):
    """Raised when a metadata property cannot be read from a resolved owner."""


class UnsupportedMetadataPropertyTypeError(MetadataAccessError):
    """Raised when a native property type is outside the metadata contract."""


@dataclass(frozen=True, slots=True)
class ResolvedMetadataOwner:
    """A FreeCAD owner object resolved by exact owner id."""

    owner_id: str
    owner: Any


@dataclass(frozen=True, slots=True)
class ResolvedMetadataProperty:
    """An exact native metadata property with its type, kind, and raw value."""

    property_name: str
    native_type_id: str
    value_kind: str
    value: Any


def validate_metadata_access_document(document: Any) -> None:
    """Validate that a document exposes callable getObject for metadata access."""

    _require_callable_get_object(document)


def resolve_metadata_owner(document: Any, owner_id: str) -> ResolvedMetadataOwner:
    """Resolve an exact FreeCAD metadata owner id through document.getObject."""

    get_object = _require_callable_get_object(document)

    try:
        owner = get_object(owner_id)
    except Exception as exc:
        raise MetadataAccessDocumentError(
            f"failed to resolve metadata owner '{owner_id}'"
        ) from exc

    if owner is None:
        raise MetadataAccessOwnerNotFoundError(
            f"metadata owner '{owner_id}' was not found"
        )

    return ResolvedMetadataOwner(owner_id=owner_id, owner=owner)


def require_metadata_property(
    owner: Any,
    key: str,
    *,
    owner_id: str = "",
) -> str:
    """Require an exact native property and return its native type id."""

    exact_key = _require_exact_metadata_key(key, owner_id)
    properties = _read_properties_list(owner, owner_id)

    try:
        present = exact_key in properties
    except Exception as exc:
        raise MetadataAccessPropertyInspectionError(
            f"failed to inspect native PropertiesList on owner {owner_id!r}"
        ) from exc

    if not present:
        raise MetadataAccessPropertyNotFoundError(
            f"metadata property {exact_key!r} was not found on owner {owner_id!r}"
        )

    get_property_type = _require_property_type_inspector(owner, owner_id)
    try:
        native_type_id = get_property_type(exact_key)
    except Exception as exc:
        raise MetadataAccessPropertyInspectionError(
            f"failed to inspect native type of metadata property "
            f"{exact_key!r} on owner {owner_id!r}"
        ) from exc

    if not isinstance(native_type_id, str) or native_type_id == "":
        raise MetadataAccessPropertyInspectionError(
            f"owner {owner_id!r} returned an invalid native type for metadata "
            f"property {exact_key!r}"
        )

    return native_type_id


def metadata_value_kind_for_native_type(native_type_id: str) -> str:
    """Return the metadata value kind for a supported native property type."""

    try:
        return METADATA_NATIVE_VALUE_KINDS[native_type_id]
    except KeyError:
        raise UnsupportedMetadataPropertyTypeError(
            f"unsupported native metadata property type {native_type_id!r}"
        ) from None


def read_metadata_property(
    owner: Any,
    key: str,
    *,
    owner_id: str = "",
) -> ResolvedMetadataProperty:
    """Read an exact native metadata property with its native type id."""

    exact_key = _require_exact_metadata_key(key, owner_id)
    native_type_id = require_metadata_property(
        owner,
        exact_key,
        owner_id=owner_id,
    )
    value_kind = metadata_value_kind_for_native_type(native_type_id)

    try:
        value = getattr(owner, exact_key)
    except Exception as exc:
        raise MetadataAccessPropertyReadError(
            f"failed to read metadata property {exact_key!r} on owner {owner_id!r}"
        ) from exc

    return ResolvedMetadataProperty(
        property_name=exact_key,
        native_type_id=native_type_id,
        value_kind=value_kind,
        value=value,
    )


def read_metadata_value(
    owner: Any,
    key: str,
    *,
    owner_id: str = "",
) -> Any:
    """Read an exact metadata attribute/property from a resolved owner."""

    return read_metadata_property(owner, key, owner_id=owner_id).value


def _require_exact_metadata_key(key: Any, owner_id: str) -> str:
    if not isinstance(key, str) or key == "" or key != key.strip() or "\x00" in key:
        raise MetadataAccessPropertyNotFoundError(
            f"metadata property key {key!r} on owner {owner_id!r} is not an "
            "exact native property name"
        )
    return key


def _read_properties_list(owner: Any, owner_id: str) -> Any:
    try:
        properties = owner.PropertiesList
    except AttributeError as exc:
        raise MetadataAccessPropertyInspectionError(
            f"owner {owner_id!r} does not expose native PropertiesList"
        ) from exc
    except Exception as exc:
        raise MetadataAccessPropertyInspectionError(
            f"failed to inspect native PropertiesList on owner {owner_id!r}"
        ) from exc
    return properties


def _require_property_type_inspector(owner: Any, owner_id: str) -> Callable[[str], Any]:
    try:
        inspector = owner.getTypeIdOfProperty
    except AttributeError as exc:
        raise MetadataAccessPropertyInspectionError(
            f"owner {owner_id!r} does not expose native property type inspection"
        ) from exc
    except Exception as exc:
        raise MetadataAccessPropertyInspectionError(
            f"failed to access native property type inspection on owner {owner_id!r}"
        ) from exc

    if not callable(inspector):
        raise MetadataAccessPropertyInspectionError(
            f"owner {owner_id!r} does not provide callable native property "
            "type inspection"
        )
    return inspector


def _require_callable_get_object(document: Any) -> Callable[[str], Any]:
    get_object = getattr(document, "getObject", None)
    if not callable(get_object):
        raise MetadataAccessDocumentError(
            "document does not provide callable getObject for metadata access"
        )

    return get_object


__all__ = [
    "METADATA_NATIVE_VALUE_KINDS",
    "MetadataAccessDocumentError",
    "MetadataAccessError",
    "MetadataAccessOwnerNotFoundError",
    "MetadataAccessPropertyInspectionError",
    "MetadataAccessPropertyNotFoundError",
    "MetadataAccessPropertyReadError",
    "ResolvedMetadataOwner",
    "ResolvedMetadataProperty",
    "UnsupportedMetadataPropertyTypeError",
    "metadata_value_kind_for_native_type",
    "read_metadata_property",
    "read_metadata_value",
    "require_metadata_property",
    "resolve_metadata_owner",
    "validate_metadata_access_document",
]
