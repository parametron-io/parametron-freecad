"""Shared deterministic parameter object and property access helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ParameterAccessError(ValueError):
    """Base class for deterministic parameter access failures."""


class ParameterAccessDocumentError(ParameterAccessError):
    """Raised when a document cannot support parameter access."""


class ParameterAccessObjectNotFoundError(ParameterAccessError):
    """Raised when getObject returns None for an exact object name."""


class ParameterAccessPropertyReadError(ParameterAccessError):
    """Raised when a property cannot be read from a resolved object."""


class ParameterAccessPropertyWriteError(ParameterAccessError):
    """Raised when a property cannot be written on a resolved object."""


@dataclass(frozen=True, slots=True)
class ResolvedParameterObject:
    """A FreeCAD object resolved by exact object name."""

    object_name: str
    object: Any


def validate_parameter_access_document(document: Any) -> None:
    """Validate that a document exposes callable getObject for parameter access."""

    _require_callable_get_object(document)


def resolve_parameter_object(document: Any, object_name: str) -> ResolvedParameterObject:
    """Resolve an exact FreeCAD object name through document.getObject."""

    get_object = _require_callable_get_object(document)

    try:
        obj = get_object(object_name)
    except Exception as exc:
        raise ParameterAccessDocumentError(
            f"failed to resolve object '{object_name}'"
        ) from exc

    if obj is None:
        raise ParameterAccessObjectNotFoundError(
            f"object '{object_name}' was not found"
        )

    return ResolvedParameterObject(object_name=object_name, object=obj)


def read_parameter_property(
    obj: Any,
    property_name: str,
    *,
    object_name: str = "",
) -> Any:
    """Read an exact attribute/property from a resolved object."""

    del object_name

    try:
        return getattr(obj, property_name)
    except Exception as exc:
        raise ParameterAccessPropertyReadError(
            f"failed to read property '{property_name}'"
        ) from exc


def write_parameter_property(
    obj: Any,
    property_name: str,
    value: Any,
    *,
    object_name: str = "",
) -> None:
    """Write an exact attribute/property on a resolved object."""

    del object_name

    try:
        setattr(obj, property_name, value)
    except Exception as exc:
        raise ParameterAccessPropertyWriteError(
            f"failed to write property '{property_name}'"
        ) from exc


def _require_callable_get_object(document: Any) -> Callable[[str], Any]:
    get_object = getattr(document, "getObject", None)
    if not callable(get_object):
        raise ParameterAccessDocumentError(
            "document does not provide callable getObject for parameter access"
        )

    return get_object


__all__ = [
    "ParameterAccessDocumentError",
    "ParameterAccessError",
    "ParameterAccessObjectNotFoundError",
    "ParameterAccessPropertyReadError",
    "ParameterAccessPropertyWriteError",
    "ResolvedParameterObject",
    "read_parameter_property",
    "resolve_parameter_object",
    "validate_parameter_access_document",
    "write_parameter_property",
]
